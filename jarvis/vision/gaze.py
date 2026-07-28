"""Eye / head-pose signals from MediaPipe Face Landmarker."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

# Blendshape names of interest (MediaPipe Face Landmarker)
BLINK_L = "eyeBlinkLeft"
BLINK_R = "eyeBlinkRight"


@dataclass
class GazeEvent:
    name: str
    confidence: float
    detail: str = ""
    yaw: float = 0.0
    pitch: float = 0.0


class GazeTracker:
    """
    Double-blink → click.
    Sustained head yaw → scroll left/right.
    """

    def __init__(self):
        self._blink_times: list[float] = []
        self._eyes_closed = False
        self._last_scroll = 0.0
        self._yaw_ema = 0.0
        self._pitch_ema = 0.0

    def update(self, blendshapes, transform_matrix, now: float | None = None) -> list[GazeEvent]:
        now = now if now is not None else time.time()
        events: list[GazeEvent] = []

        blink_score = 0.0
        if blendshapes:
            scores = {b.category_name: b.score for b in blendshapes}
            blink_score = max(scores.get(BLINK_L, 0.0), scores.get(BLINK_R, 0.0))

        closed = blink_score > 0.55
        if closed and not self._eyes_closed:
            self._blink_times.append(now)
            # Keep only recent blinks
            self._blink_times = [t for t in self._blink_times if now - t < 1.1]
            if len(self._blink_times) >= 2:
                events.append(GazeEvent("double_blink", blink_score, "double blink"))
                self._blink_times.clear()
        self._eyes_closed = closed

        yaw, pitch = self._pose_from_matrix(transform_matrix)
        self._yaw_ema = 0.7 * self._yaw_ema + 0.3 * yaw
        self._pitch_ema = 0.7 * self._pitch_ema + 0.3 * pitch

        if now - self._last_scroll > 0.55:
            if self._yaw_ema > 0.28:
                events.append(GazeEvent("look_right", abs(self._yaw_ema), f"yaw={self._yaw_ema:.2f}", self._yaw_ema, self._pitch_ema))
                self._last_scroll = now
            elif self._yaw_ema < -0.28:
                events.append(GazeEvent("look_left", abs(self._yaw_ema), f"yaw={self._yaw_ema:.2f}", self._yaw_ema, self._pitch_ema))
                self._last_scroll = now
            elif self._pitch_ema > 0.25:
                events.append(GazeEvent("look_down", abs(self._pitch_ema), f"pitch={self._pitch_ema:.2f}", self._yaw_ema, self._pitch_ema))
                self._last_scroll = now
            elif self._pitch_ema < -0.25:
                events.append(GazeEvent("look_up", abs(self._pitch_ema), f"pitch={self._pitch_ema:.2f}", self._yaw_ema, self._pitch_ema))
                self._last_scroll = now

        return events

    @staticmethod
    def _pose_from_matrix(matrix) -> tuple[float, float]:
        """Extract approximate yaw / pitch from 4x4 facial transform."""
        if matrix is None:
            return 0.0, 0.0
        try:
            # mediapipe returns a flattened 4x4 or nested list
            m = list(matrix)
            if len(m) == 16:
                r00, r01, r02 = m[0], m[1], m[2]
                r10, r11, r12 = m[4], m[5], m[6]
                r20, r21, r22 = m[8], m[9], m[10]
            elif hasattr(matrix, "data"):
                d = list(matrix.data)
                r00, r01, r02 = d[0], d[1], d[2]
                r10, r11, r12 = d[4], d[5], d[6]
                r20, r21, r22 = d[8], d[9], d[10]
            else:
                return 0.0, 0.0
            # Standard rotation extraction
            pitch = math.asin(max(-1.0, min(1.0, -r12))) if abs(r12) <= 1 else 0.0
            yaw = math.atan2(r02, r22)
            return yaw, pitch
        except Exception:
            return 0.0, 0.0
