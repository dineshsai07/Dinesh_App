"""Hand gesture classification from MediaPipe 21-point hand landmarks."""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass


# MediaPipe hand landmark indices
WRIST = 0
THUMB_CMC, THUMB_MCP, THUMB_IP, THUMB_TIP = 1, 2, 3, 4
INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP = 5, 6, 7, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP = 9, 10, 11, 12
RING_MCP, RING_PIP, RING_DIP, RING_TIP = 13, 14, 15, 16
PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP = 17, 18, 19, 20


@dataclass
class GestureEvent:
    name: str
    confidence: float
    hand: str = "Right"  # Left / Right (mirrored selfie view)
    cursor_xy: tuple[float, float] | None = None  # normalised 0..1
    detail: str = ""


def _dist(a, b) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def _finger_extended(lms, tip: int, pip: int, mcp: int) -> bool:
    """True when fingertip is clearly further from wrist than the PIP joint."""
    wrist = lms[WRIST]
    return _dist(lms[tip], wrist) > _dist(lms[pip], wrist) * 1.08


def _thumb_extended(lms, handedness: str) -> bool:
    """Thumb tip away from palm centre along x (handedness-aware)."""
    tip, ip, mcp = lms[THUMB_TIP], lms[THUMB_IP], lms[THUMB_MCP]
    # Distance from tip to index MCP is a reliable open/closed signal.
    return _dist(tip, lms[INDEX_MCP]) > _dist(ip, lms[INDEX_MCP]) * 1.05 and _dist(tip, mcp) > 0.04


def classify_hand(lms, handedness: str = "Right") -> GestureEvent | None:
    """Classify a single hand into a discrete gesture."""
    if not lms or len(lms) < 21:
        return None

    idx = _finger_extended(lms, INDEX_TIP, INDEX_PIP, INDEX_MCP)
    mid = _finger_extended(lms, MIDDLE_TIP, MIDDLE_PIP, MIDDLE_MCP)
    ring = _finger_extended(lms, RING_TIP, RING_PIP, RING_MCP)
    pinky = _finger_extended(lms, PINKY_TIP, PINKY_PIP, PINKY_MCP)
    thumb = _thumb_extended(lms, handedness)
    extended = sum([idx, mid, ring, pinky, thumb])

    pinch_d = _dist(lms[THUMB_TIP], lms[INDEX_TIP])
    cursor = (lms[INDEX_TIP].x, lms[INDEX_TIP].y)

    # Pinch (click) — highest priority when tips nearly touch
    if pinch_d < 0.045 and idx:
        return GestureEvent("pinch", 0.92, handedness, cursor, f"pinch={pinch_d:.3f}")

    # Peace / victory
    if idx and mid and not ring and not pinky:
        return GestureEvent("peace", 0.9, handedness, cursor)

    # Point — only index
    if idx and not mid and not ring and not pinky and not thumb:
        return GestureEvent("point", 0.87, handedness, cursor)

    # Thumbs up — thumb out, fingers curled
    if thumb and not idx and not mid and not ring and not pinky:
        return GestureEvent("thumbs_up", 0.9, handedness, cursor)

    # Open palm / wave candidate
    if extended >= 4:
        return GestureEvent("open_palm", 0.85, handedness, (lms[WRIST].x, lms[WRIST].y))

    # Fist — nothing meaningfully extended
    if extended == 0 and pinch_d > 0.06:
        return GestureEvent("fist", 0.88, handedness, cursor)

    return GestureEvent("unknown", 0.3, handedness, cursor)


class GestureTracker:
    """Stabilise noisy per-frame classifications + detect swipes/waves."""

    def __init__(self, hold_frames: int = 4):
        self.hold_frames = hold_frames
        self._history: deque[str] = deque(maxlen=hold_frames)
        self._palm_trail: deque[tuple[float, float, float]] = deque(maxlen=10)
        self._last_emitted = ""
        self._cooldown_until = 0.0

    def update(self, gesture: GestureEvent | None, now: float) -> GestureEvent | None:
        if gesture is None:
            self._history.append("none")
            return None

        self._history.append(gesture.name)

        # Swipe / wave from open-palm trail
        if gesture.name == "open_palm" and gesture.cursor_xy:
            self._palm_trail.append((now, *gesture.cursor_xy))
            swipe = self._detect_swipe(now)
            if swipe and now >= self._cooldown_until:
                self._cooldown_until = now + 0.9
                self._last_emitted = swipe.name
                return swipe
        else:
            self._palm_trail.clear()

        # Require the same gesture for hold_frames before firing
        if len(self._history) < self.hold_frames:
            return None
        if len(set(self._history)) != 1:
            return None
        name = self._history[-1]
        if name in ("none", "unknown"):
            return None
        if name == self._last_emitted and now < self._cooldown_until:
            return None
        if now < self._cooldown_until and name == self._last_emitted:
            return None

        # Continuous gestures (point / pinch cursor) re-emit more often
        if name in ("point", "pinch"):
            if name == self._last_emitted and (now - getattr(self, "_last_t", 0)) < 0.05:
                return None
            self._last_t = now
            self._last_emitted = name
            return gesture

        # Discrete one-shots
        if name == self._last_emitted and now < self._cooldown_until:
            return None
        self._last_emitted = name
        self._cooldown_until = now + (1.2 if name in ("peace", "thumbs_up", "fist", "open_palm") else 0.5)
        return gesture

    def _detect_swipe(self, now: float) -> GestureEvent | None:
        if len(self._palm_trail) < 5:
            return None
        t0, x0, y0 = self._palm_trail[0]
        t1, x1, y1 = self._palm_trail[-1]
        dt = max(t1 - t0, 1e-3)
        dx, dy = x1 - x0, y1 - y0
        speed = math.hypot(dx, dy) / dt
        if speed < 0.8 or dt > 0.55:
            return None
        if abs(dx) > abs(dy) * 1.4:
            return GestureEvent("swipe_right" if dx > 0 else "swipe_left", 0.86, detail=f"dx={dx:.2f}")
        if abs(dy) > abs(dx) * 1.4:
            return GestureEvent("swipe_down" if dy > 0 else "swipe_up", 0.86, detail=f"dy={dy:.2f}")
        # Fast open-palm motion with little net displacement = wave
        path = 0.0
        prev = self._palm_trail[0]
        for pt in list(self._palm_trail)[1:]:
            path += math.hypot(pt[1] - prev[1], pt[2] - prev[2])
            prev = pt
        if path > 0.35 and abs(dx) < 0.12:
            return GestureEvent("wave", 0.84, detail=f"path={path:.2f}")
        return None
