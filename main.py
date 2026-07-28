#!/usr/bin/env python3
"""
D.I.N.E.S.H — portable setup & launcher for any Mac.

Usage:
  python3 main.py setup     # install deps, models, venv (first time)
  python3 main.py start     # start HUD as a background LaunchAgent
  python3 main.py stop      # stop the background HUD
  python3 main.py hud       # run HUD in the foreground (dev)
  python3 main.py cli       # terminal assistant
  python3 main.py status    # is the HUD up?

All paths are derived from this file's location — nothing is hardcoded
to a specific user's home directory. Safe to clone onto any Mac.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "dinesh"
VENV = ROOT / ".venv"
REQUIREMENTS = ROOT / "requirements.txt"
LAUNCH_LABEL = "com.dinesh.hud"
LAUNCH_PLIST = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_LABEL}.plist"
HUD_URL = "http://127.0.0.1:8742"
HUD_PORT = 8742
LOG_FILE = Path("/tmp/dinesh_hud.log")

VISION_MODELS = {
    "hand_landmarker.task": (
        "https://storage.googleapis.com/mediapipe-models/"
        "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
    ),
    "face_landmarker.task": (
        "https://storage.googleapis.com/mediapipe-models/"
        "face_landmarker/face_landmarker/float16/1/face_landmarker.task"
    ),
}


# ── helpers ────────────────────────────────────────────────────

def banner(title: str) -> None:
    print()
    print("  ╔══════════════════════════════════════════════════════╗")
    print(f"  ║  {title:<52}║")
    print("  ╚══════════════════════════════════════════════════════╝")
    print()


def info(msg: str) -> None:
    print(f"  {msg}")


def die(msg: str, code: int = 1) -> None:
    print(f"\n  ✗  {msg}\n", file=sys.stderr)
    raise SystemExit(code)


def run(cmd: list[str] | str, *, check: bool = True, capture: bool = False, env=None, cwd=None):
    if isinstance(cmd, str):
        cmd = ["bash", "-lc", cmd]
    return subprocess.run(
        cmd,
        check=check,
        capture_output=capture,
        text=True,
        env=env,
        cwd=cwd,
    )


def which(name: str) -> str | None:
    return shutil.which(name)


def ram_gb() -> int:
    try:
        out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip()
        return max(1, int(out) // (1024 ** 3))
    except Exception:
        return 16


def ensure_macos() -> None:
    if platform.system() != "Darwin":
        die("D.I.N.E.S.H currently supports macOS only.")
    machine = platform.machine()
    if machine not in ("arm64", "aarch64"):
        info(f"○  Detected {machine}. Apple Silicon (M1–M4) is recommended.")


def venv_python() -> Path:
    return VENV / "bin" / "python"


def venv_pip() -> Path:
    return VENV / "bin" / "pip"


def active_python() -> Path:
    """Prefer the project venv; fall back to the interpreter running main.py."""
    vp = venv_python()
    if vp.exists():
        return vp
    return Path(sys.executable)


def brew_shellenv() -> dict[str, str]:
    env = os.environ.copy()
    brew = which("brew")
    if not brew:
        for candidate in ("/opt/homebrew/bin/brew", "/usr/local/bin/brew"):
            if Path(candidate).exists():
                brew = candidate
                break
    if not brew:
        return env
    try:
        out = subprocess.check_output([brew, "shellenv"], text=True)
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("export ") and "=" in line:
                key, val = line[len("export "):].split("=", 1)
                env[key] = val.strip().strip('"')
        env["PATH"] = env.get("PATH", "") + f":{Path(brew).parent}"
    except Exception:
        pass
    return env


# ── setup steps ────────────────────────────────────────────────

def install_homebrew() -> None:
    if which("brew") or Path("/opt/homebrew/bin/brew").exists() or Path("/usr/local/bin/brew").exists():
        info("✓  Homebrew")
        return
    info("📦 Installing Homebrew (may ask for your password)…")
    script = urllib.request.urlopen(
        "https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh"
    ).read().decode()
    subprocess.run(["/bin/bash", "-c", script], check=True)
    # Make brew visible in this process
    for candidate in ("/opt/homebrew/bin/brew", "/usr/local/bin/brew"):
        if Path(candidate).exists():
            os.environ["PATH"] = f"{Path(candidate).parent}:{os.environ.get('PATH', '')}"
            zprofile = Path.home() / ".zprofile"
            line = f'eval "$({candidate} shellenv)"\n'
            if zprofile.exists():
                text = zprofile.read_text()
                if "brew shellenv" not in text:
                    zprofile.write_text(text + line)
            else:
                zprofile.write_text(line)
            break


def brew_install(*packages: str) -> None:
    env = brew_shellenv()
    brew = which("brew") or env.get("HOMEBREW_PREFIX", "/opt/homebrew") + "/bin/brew"
    if not Path(brew).exists() and not which("brew"):
        die("Homebrew not found after install.")
    brew_bin = which("brew") or brew
    info(f"📦 brew install {' '.join(packages)}")
    subprocess.run([brew_bin, "install", *packages], check=False, env=env)


def ensure_ollama() -> None:
    env = brew_shellenv()
    if which("ollama") or Path("/opt/homebrew/bin/ollama").exists():
        info("✓  Ollama")
    else:
        info("📦 Installing Ollama…")
        brew_install("ollama")
    # Start serve if needed
    try:
        urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2)
        info("✓  Ollama server")
        return
    except Exception:
        pass
    ollama = which("ollama") or "/opt/homebrew/bin/ollama"
    subprocess.Popen(
        [ollama, "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
        start_new_session=True,
    )
    for _ in range(15):
        try:
            urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=1)
            info("✓  Ollama server")
            return
        except Exception:
            time.sleep(1)
    info("○  Ollama may still be starting — pull will retry")


def ollama_pull(model: str) -> None:
    ollama = which("ollama") or "/opt/homebrew/bin/ollama"
    try:
        listed = subprocess.check_output([ollama, "list"], text=True, stderr=subprocess.DEVNULL)
        # Match exact tag or bare name already present
        names = {line.split()[0] for line in listed.splitlines()[1:] if line.strip()}
        if model in names or any(n.startswith(model.split(":")[0] + ":") for n in names):
            info(f"✓  {model} (already installed)")
            return
    except Exception:
        pass
    info(f"↓  Pulling {model} (this can take a while)…")
    subprocess.run([ollama, "pull", model], check=False)


def ensure_venv_and_deps() -> None:
    py = Path(sys.executable)
    if not VENV.exists():
        info(f"📦 Creating virtualenv at {VENV}")
        subprocess.run([str(py), "-m", "venv", str(VENV)], check=True)
    else:
        info("✓  Virtualenv")

    pip = str(venv_pip())
    info("📦 Installing Python packages into .venv…")
    subprocess.run([pip, "install", "--upgrade", "pip"], check=False)
    if REQUIREMENTS.exists():
        subprocess.run([pip, "install", "-r", str(REQUIREMENTS)], check=True)
    else:
        die(f"Missing {REQUIREMENTS}")

    # Optional LoRA stack
    info("📦 Optional mlx-lm (Apple Silicon fine-tuning)…")
    r = subprocess.run([pip, "install", "mlx-lm"], capture_output=True, text=True)
    if r.returncode == 0:
        info("✓  mlx-lm")
    else:
        info("○  mlx-lm skipped (optional)")

    info("🌐 Playwright Chromium…")
    subprocess.run(
        [str(venv_python()), "-m", "playwright", "install", "chromium"],
        check=False,
    )


def download_vision_models() -> None:
    dest = PKG / "vision_models"
    dest.mkdir(parents=True, exist_ok=True)
    info("👁  Vision models (hands + face)…")
    for name, url in VISION_MODELS.items():
        path = dest / name
        if path.exists() and path.stat().st_size > 100_000:
            info(f"✓  {name}")
            continue
        info(f"↓  {name}")
        try:
            urllib.request.urlretrieve(url, path)
        except Exception as e:
            info(f"○  failed to fetch {name}: {e}")


def init_memory_db() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PKG)
    r = subprocess.run(
        [str(active_python()), "-c", "from memory.store import init_db; init_db(); print('ok')"],
        cwd=str(PKG),
        env=env,
        capture_output=True,
        text=True,
    )
    if r.returncode == 0:
        info("✓  Long-term memory DB ready")
    else:
        info(f"○  Memory DB init skipped: {r.stderr.strip()[:120]}")


def write_daemon_wrapper() -> Path:
    """Write a path-relative daemon script that uses this checkout's venv."""
    wrapper = PKG / "start_hud_daemon.sh"
    py = active_python()
    content = f"""#!/bin/bash
# Auto-generated by main.py — do not hardcode machine-specific paths in git.
cd "$(cd "$(dirname "$0")" && pwd)"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export PYTHONPATH="$(pwd)"
exec "{py}" server.py
"""
    wrapper.write_text(content)
    wrapper.chmod(0o755)
    return wrapper


def write_launch_agent() -> Path:
    """Generate LaunchAgent plist for *this* install location."""
    wrapper = write_daemon_wrapper()
    workdir = PKG
    log = LOG_FILE
    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{LAUNCH_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{wrapper}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>{workdir}</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>{log}</string>
  <key>StandardErrorPath</key>
  <string>{log}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    <key>PYTHONPATH</key>
    <string>{workdir}</string>
  </dict>
</dict>
</plist>
"""
    LAUNCH_PLIST.parent.mkdir(parents=True, exist_ok=True)
    LAUNCH_PLIST.write_text(plist)
    return LAUNCH_PLIST


def uid() -> int:
    return os.getuid()


def launchctl(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(["launchctl", *args], check=check, capture_output=True, text=True)


def free_port(port: int = HUD_PORT) -> None:
    try:
        out = subprocess.check_output(
            ["lsof", f"-tiTCP:{port}", "-sTCP:LISTEN"], text=True
        ).strip()
        for pid in out.splitlines():
            subprocess.run(["kill", pid], check=False)
    except subprocess.CalledProcessError:
        pass


def hud_is_up() -> bool:
    try:
        with urllib.request.urlopen(HUD_URL, timeout=2) as r:
            return 200 <= r.status < 400
    except Exception:
        return False


def measure_first_response_latency(model: str = "qwen2.5:7b") -> dict[str, float]:
    """Measure first local generation latency from Ollama."""
    url = "http://127.0.0.1:11434/api/generate"
    payload = json.dumps(
        {"model": model, "prompt": "Reply with exactly: ok", "stream": False}
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=45) as r:
        body = json.loads(r.read().decode("utf-8"))
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
    eval_ms = round(float(body.get("eval_duration", 0)) / 1_000_000, 1)
    load_ms = round(float(body.get("load_duration", 0)) / 1_000_000, 1)
    return {
        "total_ms": elapsed_ms,
        "load_ms": load_ms,
        "eval_ms": eval_ms,
    }


# ── commands ───────────────────────────────────────────────────

def cmd_setup(_: argparse.Namespace) -> None:
    banner("D.I.N.E.S.H  ·  Setup for this Mac")
    ensure_macos()
    info(f"Install root: {ROOT}")
    info(f"Detected: {ram_gb()} GB RAM · {platform.machine()}")

    install_homebrew()
    brew_install("portaudio", "ffmpeg", "libsndfile")
    ensure_ollama()

    info("")
    info("📥 AI models…")
    ollama_pull("qwen2.5:7b")
    ollama_pull("moondream")
    if ram_gb() > 16:
        ollama_pull("llama3.2-vision")

    ensure_venv_and_deps()
    download_vision_models()
    init_memory_db()
    write_daemon_wrapper()

    banner("Setup complete")
    info("Grant once in System Settings → Privacy & Security:")
    info("  • Microphone, Camera, Accessibility, Screen Recording")
    info("    → enable Terminal (or the app you launch from)")
    info("")
    info("Next:")
    info("  python3 main.py start     # HUD at http://127.0.0.1:8742")
    info("  python3 main.py cli       # terminal mode")
    info("  python3 main.py stop      # stop background HUD")
    info("")


def cmd_start(_: argparse.Namespace) -> None:
    banner("D.I.N.E.S.H  ·  Starting HUD")
    if not venv_python().exists() and not (PKG / "server.py").exists():
        die("Run setup first:  python3 main.py setup")
    if not venv_python().exists():
        info("○  No .venv yet — run: python3 main.py setup")
        info("  Continuing with system Python…")

    ensure_ollama()
    plist = write_launch_agent()
    domain = f"gui/{uid()}"
    target = f"{domain}/{LAUNCH_LABEL}"

    launchctl("bootout", target)
    launchctl("unload", str(plist))
    free_port(HUD_PORT)
    time.sleep(0.8)

    r = launchctl("bootstrap", domain, str(plist))
    if r.returncode != 0:
        # older macOS fallback
        launchctl("load", str(plist))
    launchctl("enable", target)
    launchctl("kickstart", "-k", target)

    info("Waiting for HUD…")
    for i in range(25):
        if hud_is_up():
            info(f"✓  Ready → {HUD_URL}")
            subprocess.run(["open", HUD_URL], check=False)
            return
        time.sleep(1)
    info(f"○  Still starting — open {HUD_URL}")
    info(f"   Logs: {LOG_FILE}")
    subprocess.run(["open", HUD_URL], check=False)


def cmd_stop(_: argparse.Namespace) -> None:
    banner("D.I.N.E.S.H  ·  Stopping")
    domain = f"gui/{uid()}"
    target = f"{domain}/{LAUNCH_LABEL}"
    launchctl("bootout", target)
    if LAUNCH_PLIST.exists():
        launchctl("unload", str(LAUNCH_PLIST))
    free_port(HUD_PORT)
    info("✓  Stopped")


def cmd_hud(_: argparse.Namespace) -> None:
    """Foreground HUD (useful for debugging)."""
    banner("D.I.N.E.S.H  ·  HUD (foreground)")
    py = active_python()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PKG)
    free_port(HUD_PORT)
    subprocess.run(["open", HUD_URL], check=False)
    os.chdir(PKG)
    os.execve(str(py), [str(py), "server.py"], env)


def cmd_cli(_: argparse.Namespace) -> None:
    banner("D.I.N.E.S.H  ·  CLI")
    py = active_python()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PKG)
    os.chdir(PKG)
    os.execve(str(py), [str(py), "cli.py"], env)


def cmd_status(_: argparse.Namespace) -> None:
    up = hud_is_up()
    info(f"HUD: {'UP  ' + HUD_URL if up else 'DOWN'}")
    info(f"Install root: {ROOT}")
    info(f"Python: {active_python()}")
    info(f"Venv: {'yes' if venv_python().exists() else 'no — run setup'}")
    info(f"LaunchAgent: {'installed' if LAUNCH_PLIST.exists() else 'not installed'}")
    if LAUNCH_PLIST.exists():
        # show that plist points at THIS checkout (portable check)
        text = LAUNCH_PLIST.read_text()
        info(f"Plist targets this install: {'yes' if str(PKG) in text else 'NO — run start again'}")


def cmd_benchmark(_: argparse.Namespace) -> None:
    banner("D.I.N.E.S.H  ·  Performance benchmark")
    ensure_ollama()
    model = os.environ.get("DINESH_MODEL", "qwen2.5:7b")
    try:
        cold = measure_first_response_latency(model)
        warm = measure_first_response_latency(model)
    except Exception as e:
        die(f"Benchmark failed: {e}")
    info(f"Model: {model}")
    info(f"Cold response: {cold['total_ms']} ms (load {cold['load_ms']} ms, eval {cold['eval_ms']} ms)")
    info(f"Warm response: {warm['total_ms']} ms (load {warm['load_ms']} ms, eval {warm['eval_ms']} ms)")
    improvement = round(cold["total_ms"] - warm["total_ms"], 1)
    info(f"Warmup gain: {improvement} ms")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="main.py",
        description="D.I.N.E.S.H portable setup & launcher",
    )
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("setup", help="Install dependencies, models, and venv")
    sub.add_parser("start", help="Start HUD in the background")
    sub.add_parser("stop", help="Stop background HUD")
    sub.add_parser("hud", help="Run HUD in the foreground")
    sub.add_parser("cli", help="Terminal assistant")
    sub.add_parser("status", help="Show install / HUD status")
    sub.add_parser("benchmark", help="Measure cold vs warm response latency")
    return p


def main() -> None:
    if not PKG.is_dir():
        die(f"Expected package folder at {PKG}")
    parser = build_parser()
    args = parser.parse_args()
    commands = {
        "setup": cmd_setup,
        "start": cmd_start,
        "stop": cmd_stop,
        "hud": cmd_hud,
        "cli": cmd_cli,
        "status": cmd_status,
        "benchmark": cmd_benchmark,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
