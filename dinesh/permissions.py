"""macOS permission checks — mic, camera, accessibility, screen recording."""

from __future__ import annotations

import subprocess
from typing import Any


def check_accessibility() -> bool:
    try:
        r = subprocess.run(
            ["osascript", "-e", 'tell application "System Events" to return "ok"'],
            capture_output=True, text=True, timeout=5,
        )
        return r.returncode == 0 and "ok" in r.stdout.lower()
    except Exception:
        return False


def check_microphone() -> tuple[bool, str]:
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        inputs = [d for d in devices if d.get("max_input_channels", 0) > 0]
        if not inputs:
            return False, "No microphone device found"
        # Opening a short stream is the only reliable entitlement probe.
        with sd.InputStream(channels=1, samplerate=16000, blocksize=1024):
            pass
        return True, "Microphone ready"
    except Exception as e:
        return False, f"Microphone blocked or unavailable: {e}"


def check_camera(probe: bool = False) -> tuple[bool, str]:
    """
    Camera check. Full probe opens the device (triggers the macOS dialog).
    Soft check only verifies OpenCV + model files exist.
    """
    try:
        from vision.controller import VISION_AVAILABLE, camera_permission_ok, HAND_MODEL, FACE_MODEL
    except Exception as e:
        return False, f"Vision stack unavailable: {e}"

    if not VISION_AVAILABLE:
        return False, "Install mediapipe and opencv-python"
    if not HAND_MODEL.exists() or not FACE_MODEL.exists():
        return False, "Vision models missing — re-run install.sh"
    if not probe:
        return True, "Vision libs ready (enable Camera permission to use)"
    return camera_permission_ok()


def check_screen() -> tuple[bool, str]:
    """Best-effort: screencapture usually works; Screen Recording is needed for GUI see_screen."""
    try:
        r = subprocess.run(
            ["screencapture", "-x", "-t", "png", "/tmp/.dinesh_perm_probe.png"],
            capture_output=True, text=True, timeout=8,
        )
        ok = r.returncode == 0
        return (True, "Screen capture OK") if ok else (False, "Screen Recording may be blocked")
    except Exception as e:
        return False, str(e)


def permission_report(probe_camera: bool = False) -> dict[str, Any]:
    mic_ok, mic_msg = check_microphone()
    cam_ok, cam_msg = check_camera(probe=probe_camera)
    acc_ok = check_accessibility()
    scr_ok, scr_msg = check_screen()
    items = [
        {
            "id": "microphone",
            "label": "Microphone",
            "ok": mic_ok,
            "detail": mic_msg,
            "fix": "System Settings → Privacy & Security → Microphone → enable Terminal (or the app that launches Dinesh)",
        },
        {
            "id": "camera",
            "label": "Camera",
            "ok": cam_ok,
            "detail": cam_msg,
            "fix": "System Settings → Privacy & Security → Camera → enable Terminal (or the app that launches Dinesh)",
        },
        {
            "id": "accessibility",
            "label": "Accessibility",
            "ok": acc_ok,
            "detail": "GUI control ready" if acc_ok else "Needed for mouse/keyboard control",
            "fix": "System Settings → Privacy & Security → Accessibility → enable Terminal (or the app that launches Dinesh)",
        },
        {
            "id": "screen",
            "label": "Screen Recording",
            "ok": scr_ok,
            "detail": scr_msg,
            "fix": "System Settings → Privacy & Security → Screen Recording → enable Terminal (or the app that launches Dinesh)",
        },
    ]
    return {
        "all_ok": all(i["ok"] for i in items),
        "items": items,
    }


def startup_checks():
    report = permission_report(probe_camera=False)
    for item in report["items"]:
        mark = "✓" if item["ok"] else "○"
        print(f"  {mark}  {item['label']}: {item['detail']}")
        if not item["ok"]:
            print(f"     → {item['fix']}")
    print()
