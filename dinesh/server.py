#!/usr/bin/env python3
"""
Dinesh HUD server — FastAPI + WebSocket bridge to the agent.
Serves the cinematic interface and streams live state.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("DineshHUD")

try:
    import ollama
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles
except ImportError as e:
    print(f"\n  ✗  Missing dependency: {e}")
    print("     pip3 install fastapi uvicorn websockets --break-system-packages\n")
    sys.exit(1)

from config import FULL_CONTROL, LLM_MODEL, PROFILE, VISION_MODEL, WHISPER_MODEL
from models import warm_models
from audio import (
    pick_voice, preload_whisper_background, warm_audio_pipeline_background, get_whisper_model,
    record_until_silence, transcribe, speak, abort_listen, wake_match,
)
import numpy as np
import sounddevice as sd
from config import CHANNELS, SAMPLE_RATE
from agent import DineshAgent
from memory.store import list_memory, remember_fact
from memory.trainer import full_train_cycle
import config as cfg
from permissions import permission_report

try:
    from vision.controller import VisionController, VISION_AVAILABLE, apply_desktop_action, camera_permission_ok
except Exception as e:  # pragma: no cover
    VisionController = None  # type: ignore
    VISION_AVAILABLE = False
    apply_desktop_action = None  # type: ignore
    def camera_permission_ok():
        return False, str(e)

HUD_DIR = Path(__file__).resolve().parent / "hud"
app = FastAPI(title="Dinesh HUD")

voice = pick_voice()
agent = DineshAgent()
clients: set[WebSocket] = set()
state_lock = threading.Lock()
busy = False
busy_since = 0.0
BUSY_STALE_SECS = 90  # auto-unlock if something wedged
vision_ctrl = None

STATE = {
    "status": "idle",
    "transcript": "",
    "reply": "",
    "tools": [],
    "model": LLM_MODEL,
    "vision": VISION_MODEL,
    "whisper": WHISPER_MODEL,
    "voice": voice,
    "tier": PROFILE.tier,
    "ram_gb": PROFILE.ram_gb,
    "full_control": FULL_CONTROL,
    "vision_on": False,
    "vision_status": "off",
    "vision_available": bool(VISION_AVAILABLE),
    "perf": {
        "last_first_token_ms": None,
        "last_total_response_ms": None,
    },
}


async def broadcast(payload: dict[str, Any]):
    dead = []
    data = json.dumps(payload)
    for ws in list(clients):
        try:
            await ws.send_text(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        clients.discard(ws)


def push(event: str, **kwargs):
    payload = {"event": event, **kwargs}
    with state_lock:
        if "status" in kwargs:
            STATE["status"] = kwargs["status"]
        if "transcript" in kwargs:
            STATE["transcript"] = kwargs["transcript"]
        if "reply" in kwargs:
            STATE["reply"] = kwargs["reply"]
        if "tool" in kwargs:
            STATE["tools"] = (STATE["tools"] + [kwargs["tool"]])[-12:]
        if kwargs.get("clear_tools"):
            STATE["tools"] = []

    loop = getattr(app.state, "loop", None)
    if loop and loop.is_running():
        asyncio.run_coroutine_threadsafe(broadcast(payload), loop)


def _set_busy(on: bool):
    global busy, busy_since
    busy = on
    busy_since = time.time() if on else 0.0


def _maybe_clear_stale_busy() -> bool:
    """If busy flag is stuck, unlock so the HUD can accept commands again."""
    global busy
    if busy and busy_since and (time.time() - busy_since) > BUSY_STALE_SECS:
        logger.warning("Clearing stale busy lock (%.0fs)", time.time() - busy_since)
        abort_listen()
        _set_busy(False)
        push("status", status="idle", reply="Recovered from a stuck operation.")
        return True
    return False


def ensure_ollama() -> bool:
    try:
        ollama.list()
        return True
    except Exception:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(8):
            time.sleep(1)
            try:
                ollama.list()
                return True
            except Exception:
                continue
        return False


_orig_print_tool = None


def _hud_tool_step(step: int, name: str, detail: str):
    if _orig_print_tool:
        _orig_print_tool(step, name, detail)
    push("tool", tool={"step": step, "name": name, "detail": detail[:100]}, status="thinking")


def _cancel():
    abort_listen()
    _set_busy(False)
    push("status", status="idle", reply="Cancelled.")
    push("system", reply="Listening cancelled — try typing, or speak again.")


def _vision_event(payload: dict):
    event = payload.get("event", "vision")
    if "vision_on" in payload:
        STATE["vision_on"] = bool(payload["vision_on"])
    if "vision_status" in payload:
        STATE["vision_status"] = payload["vision_status"]
    push(event, **{k: v for k, v in payload.items() if k != "event"})


def _vision_action(action: str, detail: dict):
    """Map camera gestures / gaze onto HUD + desktop effects."""
    label = detail.get("gesture") or detail.get("gaze") or action
    push("tool", tool={"step": 0, "name": f"vision:{label}", "detail": detail.get("detail", "")[:80]})

    if action == "listen":
        if not busy:
            push("system", reply="👋 Wave detected — listening")
            threading.Thread(target=_run_listen, daemon=True).start()
        return
    if action == "cancel":
        push("system", reply="✊ Fist — cancelled")
        _cancel()
        return
    if action == "confirm":
        push("system", reply="👍 Confirmed")
        return

    # Desktop effects (mouse / scroll / screenshot)
    if apply_desktop_action is None:
        return
    result = apply_desktop_action(action, detail)
    if result:
        push("system", reply=f"👁 {result}")


def _set_vision(on: bool, preview: bool = False) -> str:
    global vision_ctrl
    if on:
        if not VISION_AVAILABLE:
            msg = "Install mediapipe + opencv-python, then restart."
            push("system", reply=msg)
            return msg
        ok, info = camera_permission_ok()
        if not ok:
            push("system", reply=info)
            push("vision", vision_on=False, hint=info)
            return info
        if vision_ctrl is None:
            vision_ctrl = VisionController(
                on_event=_vision_event,
                on_action=_vision_action,
                preview=preview,
            )
        else:
            vision_ctrl.preview = preview
        msg = vision_ctrl.start()
        push("system", reply=msg)
        return msg
    if vision_ctrl:
        msg = vision_ctrl.stop()
        push("system", reply=msg)
        STATE["vision_on"] = False
        STATE["vision_status"] = "off"
        return msg
    return "Vision already off"


# ── Wake word ──────────────────────────────────────────────────
wake_enabled = threading.Event()
_wake_thread: threading.Thread | None = None


def _wake_loop():
    """
    Background 'Hey Dinesh' listener.

    The mic is released while a command runs so it never fights with
    click-to-speak or the reply audio.
    """
    chunk_secs = 2
    chunk_size = int(SAMPLE_RATE * chunk_secs)
    model = get_whisper_model()
    try:
        while wake_enabled.is_set():
            if busy:
                time.sleep(0.4)
                continue

            heard: str | None = None
            with sd.InputStream(
                samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="float32",
                blocksize=chunk_size,
            ) as stream:
                while wake_enabled.is_set() and not busy:
                    chunk, _ = stream.read(chunk_size)
                    if not wake_enabled.is_set() or busy:
                        break
                    if float(np.sqrt(np.mean(chunk ** 2))) < 0.004:
                        continue
                    text = transcribe(chunk, model)
                    command = wake_match(text)
                    if command is None:
                        continue
                    push("system", reply=f"Wake word heard: “{text.strip()}”")
                    heard = command
                    break

            if heard is None:
                continue

            if len(heard) > 3:
                push("transcript", transcript=heard)
                _run_chat(heard)
            else:
                speak("Yes, sir?", voice, wait=True)
                _run_listen()
    except Exception as e:
        logger.exception("wake loop failed")
        push("error", reply=f"Wake word stopped: {e}", status="idle")
    finally:
        wake_enabled.clear()
        push("wake", wake=False)


def _set_wake(on: bool):
    global _wake_thread
    if on:
        if wake_enabled.is_set():
            return
        wake_enabled.set()
        _wake_thread = threading.Thread(target=_wake_loop, daemon=True)
        _wake_thread.start()
        push("wake", wake=True)
        push("system", reply="Wake word armed — say “Hey Dinesh”.")
    else:
        wake_enabled.clear()
        push("wake", wake=False)
        push("system", reply="Wake word disabled.")


def _run_chat(text: str):
    try:
        _set_busy(True)
        low = text.lower().strip()

        if low in ("memory", "mem"):
            reply = list_memory()
            push("reply", reply=reply, status="speaking")
            speak("Long-term memory report ready, sir.", voice, wait=True)
            push("status", status="idle")
            return

        if low.startswith("remember "):
            fact = text[9:].strip()
            reply = remember_fact(fact, source="hud") if fact else "Usage: remember <fact>"
            if fact:
                agent.refresh_memory_prompt()
            push("reply", reply=reply, status="speaking")
            speak("Committed to long-term memory, sir.", voice, wait=True)
            push("status", status="idle")
            return

        if low == "train":
            push("status", status="thinking", clear_tools=True, reply="Training cycle in progress…")
            speak("Beginning permanent training cycle.", voice)
            reply = full_train_cycle()
            agent.refresh_memory_prompt()
            STATE["model"] = cfg.LLM_MODEL
            push("boot", model=cfg.LLM_MODEL)
            push("reply", reply=reply, status="speaking")
            speak("Training complete. I will remember.", voice, wait=True)
            push("status", status="idle")
            return

        from nlu import normalize
        cleaned = normalize(text)
        hint = "Processing…"
        if cleaned.lower() != text.lower().strip():
            hint = f"Read as: {cleaned}"
        push(
            "transcript",
            transcript=text,
            status="thinking",
            clear_tools=True,
            hint=hint,
            understood=cleaned if cleaned != text else "",
        )

        import ui as ui_mod
        global _orig_print_tool
        _orig_print_tool = ui_mod.print_tool_step
        ui_mod.print_tool_step = _hud_tool_step

        # Live token stream into the HUD feed
        push("reply_start", status="thinking", hint=hint)

        started_at = time.perf_counter()
        first_token_at = {"value": None}

        def _on_token(delta: str):
            if first_token_at["value"] is None:
                first_token_at["value"] = time.perf_counter()
                first_ms = round((first_token_at["value"] - started_at) * 1000, 1)
                STATE["perf"]["last_first_token_ms"] = first_ms
            push("token", token=delta, status="thinking")

        reply = agent.chat(text, on_token=_on_token)
        total_ms = round((time.perf_counter() - started_at) * 1000, 1)
        STATE["perf"]["last_total_response_ms"] = total_ms

        ui_mod.print_tool_step = _orig_print_tool
        push(
            "reply",
            reply=reply,
            status="speaking",
            perf=STATE["perf"],
        )
        speak(reply, voice, wait=True)
        push("status", status="idle")
    except Exception as e:
        logger.exception("chat failed")
        push("error", reply=f"System fault: {e}", status="idle")
    finally:
        _set_busy(False)


def _run_listen():
    try:
        _set_busy(True)
        push(
            "status",
            status="listening",
            transcript="",
            reply="",
            hint="Speak now — Esc to cancel · stops after silence",
        )
        audio = record_until_silence()
        push("status", status="thinking", hint="Transcribing…")
        text = transcribe(audio, get_whisper_model())
        if len(text) < 2:
            push(
                "status",
                status="idle",
                transcript="(no speech detected)",
                hint="No speech heard — type below, or click the core and speak",
            )
            return
        # Hand off to chat — it echoes the transcript and manages busy state
        _set_busy(False)
        _run_chat(text)
    except TimeoutError as e:
        logger.warning("listen timeout: %s", e)
        push("error", reply=str(e), status="idle")
    except Exception as e:
        logger.exception("listen failed")
        push(
            "error",
            reply=f"Mic fault: {e}. Grant Microphone to Terminal, or type instead.",
            status="idle",
        )
    finally:
        if busy:
            _set_busy(False)
            if STATE.get("status") == "listening":
                push("status", status="idle")


def collect_telemetry() -> dict[str, Any]:
    """Live Mac metrics for the HUD gauges."""
    data: dict[str, Any] = {}
    try:
        # Fast-ish CPU sample via `ps` average of running processes (approx)
        out = subprocess.run(
            ["ps", "-A", "-o", "%cpu="],
            capture_output=True, text=True, timeout=2,
        ).stdout
        total = 0.0
        for line in out.splitlines():
            try:
                total += float(line.strip() or 0)
            except ValueError:
                pass
        ncpu = int(subprocess.check_output(["sysctl", "-n", "hw.ncpu"], text=True).strip() or "8")
        data["cpu"] = round(min(100.0, total / max(1, ncpu)), 1)
    except Exception:
        data["cpu"] = 0.0

    try:
        # macOS memory pressure accounts for reclaimable cache/compressed pages.
        pressure = subprocess.check_output(
            ["memory_pressure", "-Q"], text=True, timeout=3
        )
        free_match = re.search(r"free percentage:\s*(\d+)%", pressure)
        data["ram"] = float(100 - int(free_match.group(1))) if free_match else 0.0
    except Exception:
        data["ram"] = 0.0

    try:
        usage = shutil.disk_usage("/")
        pct = round(usage.used / usage.total * 100, 1)
        used_gb = usage.used / (1024 ** 3)
        total_gb = usage.total / (1024 ** 3)
        data["disk"] = {
            "pct": pct,
            "label": f"{used_gb:.0f}/{total_gb:.0f} GB",
        }
    except Exception:
        data["disk"] = {"pct": 0, "label": "—"}

    try:
        load = os.getloadavg()
        # Rough bar: load1 / ncpu
        ncpu = int(subprocess.check_output(["sysctl", "-n", "hw.ncpu"], text=True).strip() or "8")
        data["load"] = {
            "label": f"{load[0]:.2f} / {load[1]:.2f} / {load[2]:.2f}",
            "pct": round(min(100, load[0] / max(1, ncpu) * 100), 1),
        }
    except Exception:
        data["load"] = {"label": "—", "pct": 0}

    try:
        boot = subprocess.check_output(
            ["sysctl", "-n", "kern.boottime"], text=True, timeout=2
        )
        match = re.search(r"sec\s*=\s*(\d+)", boot)
        uptime_seconds = max(0, int(time.time()) - int(match.group(1))) if match else 0
        days, remainder = divmod(uptime_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes = remainder // 60
        data["uptime"] = (
            f"{days}d {hours}h" if days else f"{hours}h {minutes}m"
        )
    except Exception:
        data["uptime"] = "—"

    try:
        battery = subprocess.check_output(
            ["pmset", "-g", "batt"], text=True, timeout=2
        )
        pct_match = re.search(r"(\d+)%", battery)
        low_batt = battery.lower()
        # IMPORTANT: check "discharging" before "charging"
        # because "discharging" contains the substring "charging".
        if "discharging" in low_batt:
            state = "discharging"
        elif "charging" in low_batt:
            state = "charging"
        elif "charged" in low_batt:
            state = "charged"
        else:
            state = "battery"
        data["battery"] = {
            "pct": int(pct_match.group(1)) if pct_match else 0,
            "state": state,
        }
    except Exception:
        data["battery"] = {"pct": 0, "state": "unknown"}

    return data


def _telemetry_loop():
    while True:
        try:
            push("telemetry", telemetry=collect_telemetry())
        except Exception:
            logger.exception("telemetry failed")
        time.sleep(1.0)


@app.on_event("startup")
async def on_startup():
    app.state.loop = asyncio.get_running_loop()
    if not ensure_ollama():
        logger.error("Ollama not available")
    threading.Thread(target=lambda: warm_models(PROFILE), daemon=True).start()
    preload_whisper_background()
    warm_audio_pipeline_background()
    threading.Thread(target=_telemetry_loop, daemon=True).start()
    tel = {}
    try:
        tel = collect_telemetry()
    except Exception:
        pass
    push(
        "boot",
        status="idle",
        telemetry=tel,
        permissions=permission_report(),
        **{k: STATE[k] for k in (
            "model", "vision", "whisper", "voice", "tier", "ram_gb",
            "full_control", "vision_on", "vision_status", "vision_available",
        )},
    )


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    tel = {}
    try:
        tel = collect_telemetry()
    except Exception:
        pass
    await ws.send_text(json.dumps({
        "event": "hello",
        **STATE,
        "wake": wake_enabled.is_set(),
        "telemetry": tel,
        "permissions": permission_report(),
    }))
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            action = msg.get("action")

            if action == "cancel":
                _cancel()
                continue

            _maybe_clear_stale_busy()

            if action == "listen":
                if busy:
                    await ws.send_text(json.dumps({
                        "event": "status",
                        "status": "busy",
                        "hint": "Still working — press Esc to cancel",
                    }))
                else:
                    threading.Thread(target=_run_listen, daemon=True).start()

            elif action == "chat":
                text = (msg.get("text") or "").strip()
                if not text:
                    continue
                if busy:
                    await ws.send_text(json.dumps({
                        "event": "status",
                        "status": "busy",
                        "hint": "Still working — press Esc to cancel, then type again",
                    }))
                    continue
                threading.Thread(target=_run_chat, args=(text,), daemon=True).start()

            elif action == "wake":
                _set_wake(bool(msg.get("on")))

            elif action == "vision":
                threading.Thread(
                    target=_set_vision,
                    args=(bool(msg.get("on")), bool(msg.get("preview", False))),
                    daemon=True,
                ).start()

            elif action == "permissions":
                await ws.send_text(json.dumps({
                    "event": "permissions",
                    "permissions": permission_report(probe_camera=True),
                }))

            elif action == "ping":
                await ws.send_text(json.dumps({
                    "event": "pong",
                    "status": STATE.get("status"),
                    "busy": busy,
                    "wake": wake_enabled.is_set(),
                    "vision_on": STATE.get("vision_on"),
                }))

    except WebSocketDisconnect:
        clients.discard(ws)
    except Exception:
        clients.discard(ws)


@app.get("/")
async def index():
    return FileResponse(HUD_DIR / "index.html")


app.mount("/static", StaticFiles(directory=HUD_DIR), name="static")


def main():
    import uvicorn
    print("\n  Dinesh HUD →  http://127.0.0.1:8742\n")
    uvicorn.run(app, host="127.0.0.1", port=8742, log_level="info")


if __name__ == "__main__":
    main()
