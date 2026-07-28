"""
VisionController — background camera loop that emits gesture / gaze events.

Action map (Iron Man mode):
  wave / open_palm   → wake / listen
  fist               → cancel
  thumbs_up          → confirm (system message)
  pinch              → mouse click at tip
  point              → move mouse cursor
  peace              → screenshot
  swipe_left/right   → scroll horizontal-ish (page scroll)
  swipe_up/down      → scroll
  double_blink       → mouse click
  look_left/right    → scroll
  look_up/down       → scroll
"""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Callable

logger = logging.getLogger("DineshVision")

MODELS_DIR = Path(__file__).resolve().parent.parent / "vision_models"
HAND_MODEL = MODELS_DIR / "hand_landmarker.task"
FACE_MODEL = MODELS_DIR / "face_landmarker.task"

VISION_AVAILABLE = False
_IMPORT_ERROR = ""

try:
    import cv2
    import mediapipe as mp
    import numpy as np
    from mediapipe.tasks import python as mpp
    from mediapipe.tasks.python import vision as mpv
    VISION_AVAILABLE = True
except Exception as e:  # pragma: no cover
    _IMPORT_ERROR = str(e)

from vision.gestures import GestureEvent, GestureTracker, classify_hand
from vision.gaze import GazeEvent, GazeTracker

EventCallback = Callable[[dict], None]
ActionCallback = Callable[[str, dict], None]


def camera_permission_ok() -> tuple[bool, str]:
    """Try to open the default camera. Triggers the macOS permission dialog once."""
    if not VISION_AVAILABLE:
        return False, f"Vision libs missing: {_IMPORT_ERROR or 'mediapipe/opencv'}"
    if not HAND_MODEL.exists() or not FACE_MODEL.exists():
        return False, "Vision models missing — run install.sh to download them"
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return False, (
            "Camera blocked. System Settings → Privacy & Security → Camera → "
            "enable Terminal (or the app that launches Dinesh), then restart Dinesh."
        )
    ok, _ = cap.read()
    cap.release()
    if not ok:
        return False, "Camera opened but returned no frames"
    return True, "Camera ready"


class VisionController:
    def __init__(
        self,
        on_event: EventCallback | None = None,
        on_action: ActionCallback | None = None,
        camera_index: int = 0,
        target_fps: float = 15.0,
        preview: bool = False,
    ):
        self.on_event = on_event
        self.on_action = on_action
        self.camera_index = camera_index
        self.target_fps = target_fps
        self.preview = preview
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._enabled = False
        self._gestures = GestureTracker()
        self._gaze = GazeTracker()
        self._last_status = ""
        self._cursor_armed = False  # only move mouse after a point gesture starts

    @property
    def enabled(self) -> bool:
        return self._enabled and self._thread is not None and self._thread.is_alive()

    def start(self) -> str:
        if not VISION_AVAILABLE:
            return f"Vision unavailable: {_IMPORT_ERROR}"
        ok, msg = camera_permission_ok()
        if not ok:
            return msg
        if self.enabled:
            return "Vision already running"
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="dinesh-vision", daemon=True)
        self._thread.start()
        self._enabled = True
        return "Vision online — hands and eyes are live"

    def stop(self) -> str:
        self._enabled = False
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.5)
        self._thread = None
        return "Vision offline"

    def _emit(self, payload: dict):
        if self.on_event:
            try:
                self.on_event(payload)
            except Exception:
                logger.exception("vision on_event failed")

    def _act(self, action: str, detail: dict | None = None):
        detail = detail or {}
        self._emit({"event": "vision_action", "action": action, **detail})
        if self.on_action:
            try:
                self.on_action(action, detail)
            except Exception:
                logger.exception("vision on_action failed")

    def _loop(self):
        hand_opts = mpv.HandLandmarkerOptions(
            base_options=mpp.BaseOptions(model_asset_path=str(HAND_MODEL)),
            num_hands=2,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            running_mode=mpv.RunningMode.VIDEO,
        )
        face_opts = mpv.FaceLandmarkerOptions(
            base_options=mpp.BaseOptions(model_asset_path=str(FACE_MODEL)),
            num_faces=1,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
            running_mode=mpv.RunningMode.VIDEO,
        )
        hands = mpv.HandLandmarker.create_from_options(hand_opts)
        face = mpv.FaceLandmarker.create_from_options(face_opts)

        cap = cv2.VideoCapture(self.camera_index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        if not cap.isOpened():
            self._emit({"event": "vision_error", "reply": "Camera failed to open"})
            self._enabled = False
            return

        self._emit({"event": "vision", "vision_on": True, "hint": "Hands & eyes online"})
        frame_interval = 1.0 / max(self.target_fps, 1.0)
        ts_ms = 0

        try:
            while not self._stop.is_set():
                t0 = time.time()
                ok, frame = cap.read()
                if not ok:
                    time.sleep(0.05)
                    continue

                # Mirror for natural interaction (selfie view)
                frame = cv2.flip(frame, 1)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                ts_ms += int(frame_interval * 1000)

                hres = hands.detect_for_video(mp_image, ts_ms)
                fres = face.detect_for_video(mp_image, ts_ms)

                status_bits = []
                now = time.time()

                # Hands
                if hres.hand_landmarks:
                    for i, lms in enumerate(hres.hand_landmarks):
                        hand_label = "Right"
                        if hres.handedness and i < len(hres.handedness):
                            cats = hres.handedness[i]
                            if cats:
                                hand_label = cats[0].category_name
                        raw = classify_hand(lms, hand_label)
                        stable = self._gestures.update(raw, now)
                        if stable:
                            status_bits.append(stable.name)
                            self._handle_gesture(stable)

                # Face / gaze
                if fres.face_landmarks:
                    status_bits.append("face")
                    blends = fres.face_blendshapes[0] if fres.face_blendshapes else None
                    matrix = None
                    if fres.facial_transformation_matrixes:
                        matrix = fres.facial_transformation_matrixes[0]
                    for ge in self._gaze.update(blends, matrix, now):
                        status_bits.append(ge.name)
                        self._handle_gaze(ge)

                label = " · ".join(status_bits) if status_bits else "watching"
                if label != self._last_status:
                    self._last_status = label
                    self._emit({"event": "vision_status", "vision_status": label})

                # Optional JPEG preview for HUD (throttled)
                if self.preview and int(now * 2) % 2 == 0:
                    small = cv2.resize(frame, (240, 180))
                    ok_j, buf = cv2.imencode(".jpg", small, [int(cv2.IMWRITE_JPEG_QUALITY), 55])
                    if ok_j:
                        import base64
                        self._emit({
                            "event": "vision_frame",
                            "jpeg": base64.b64encode(buf.tobytes()).decode("ascii"),
                        })

                elapsed = time.time() - t0
                time.sleep(max(0.0, frame_interval - elapsed))
        except Exception as e:
            logger.exception("vision loop crashed")
            self._emit({"event": "vision_error", "reply": f"Vision fault: {e}"})
        finally:
            cap.release()
            hands.close()
            face.close()
            self._enabled = False
            self._emit({"event": "vision", "vision_on": False, "hint": "Vision offline"})

    def _handle_gesture(self, g: GestureEvent):
        name = g.name
        detail = {"gesture": name, "hand": g.hand, "confidence": g.confidence, "detail": g.detail}
        if g.cursor_xy:
            # MediaPipe x is already mirrored; map to screen
            detail["nx"], detail["ny"] = g.cursor_xy

        if name in ("wave", "open_palm"):
            self._act("listen", detail)
        elif name == "fist":
            self._act("cancel", detail)
        elif name == "thumbs_up":
            self._act("confirm", detail)
        elif name == "peace":
            self._act("screenshot", detail)
        elif name == "pinch":
            self._act("click", detail)
        elif name == "point":
            self._cursor_armed = True
            self._act("move_cursor", detail)
        elif name.startswith("swipe_"):
            self._act(name, detail)
        else:
            self._emit({"event": "vision_gesture", **detail})

    def _handle_gaze(self, g: GazeEvent):
        detail = {"gaze": g.name, "confidence": g.confidence, "detail": g.detail, "yaw": g.yaw, "pitch": g.pitch}
        if g.name == "double_blink":
            self._act("click", detail)
        elif g.name == "look_left":
            self._act("scroll_left", detail)
        elif g.name == "look_right":
            self._act("scroll_right", detail)
        elif g.name == "look_up":
            self._act("scroll_up", detail)
        elif g.name == "look_down":
            self._act("scroll_down", detail)
        else:
            self._emit({"event": "vision_gaze", **detail})


def apply_desktop_action(action: str, detail: dict) -> str:
    """Execute low-level desktop effects for vision actions (mouse/scroll/screenshot)."""
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
    except Exception as e:
        return f"pyautogui unavailable: {e}"

    w, h = pyautogui.size()
    nx = float(detail.get("nx", 0.5))
    ny = float(detail.get("ny", 0.5))
    # Clamp into screen with a small margin
    x = int(max(5, min(w - 5, nx * w)))
    y = int(max(5, min(h - 5, ny * h)))

    if action == "move_cursor":
        pyautogui.moveTo(x, y, duration=0.05)
        return f"cursor → {x},{y}"
    if action == "click":
        if "nx" in detail:
            pyautogui.click(x, y)
            return f"click {x},{y}"
        pyautogui.click()
        return "click"
    if action == "screenshot":
        from tools.mac_tools import take_screenshot
        path = take_screenshot()
        return f"screenshot {path}"
    if action == "swipe_left" or action == "scroll_left":
        pyautogui.hscroll(-4)
        return "scroll left"
    if action == "swipe_right" or action == "scroll_right":
        pyautogui.hscroll(4)
        return "scroll right"
    if action in ("swipe_up", "scroll_up"):
        pyautogui.scroll(4)
        return "scroll up"
    if action in ("swipe_down", "scroll_down"):
        pyautogui.scroll(-4)
        return "scroll down"
    return ""
