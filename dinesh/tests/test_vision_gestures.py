"""Unit tests for gesture / gaze classifiers (no camera required)."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vision.gestures import GestureTracker, classify_hand
from vision.gaze import GazeTracker


def _lm(x, y, z=0.0):
    return SimpleNamespace(x=x, y=y, z=z)


def _hand(
    *,
    index_up=False,
    middle_up=False,
    ring_up=False,
    pinky_up=False,
    thumb_out=False,
    pinch=False,
):
    """Build a crude 21-point hand around the wrist at (0.5, 0.8)."""
    pts = [_lm(0.5, 0.8)] * 21
    pts = list(pts)
    # wrist + palm anchors
    pts[0] = _lm(0.5, 0.8)
    pts[5] = _lm(0.45, 0.6)   # index mcp
    pts[9] = _lm(0.5, 0.58)
    pts[13] = _lm(0.55, 0.6)
    pts[17] = _lm(0.6, 0.62)
    pts[2] = _lm(0.35, 0.7)   # thumb mcp
    pts[3] = _lm(0.32, 0.65)

    def finger(mcp, pip, tip, up):
        pts[mcp] = _lm(pts[mcp].x, 0.58)
        pts[pip] = _lm(pts[mcp].x, 0.45 if up else 0.62)
        pts[tip] = _lm(pts[mcp].x, 0.25 if up else 0.68)

    finger(5, 6, 8, index_up)
    finger(9, 10, 12, middle_up)
    finger(13, 14, 16, ring_up)
    finger(17, 18, 20, pinky_up)

    if thumb_out:
        pts[4] = _lm(0.22, 0.55)
    else:
        pts[4] = _lm(0.42, 0.62)

    if pinch:
        pts[4] = _lm(pts[8].x + 0.01, pts[8].y + 0.01)
        # keep index up so pinch classifier accepts it
        pts[6] = _lm(0.45, 0.45)
        pts[8] = _lm(0.45, 0.25)
        pts[4] = _lm(0.46, 0.26)

    return pts


class TestGestures:
    def test_open_palm(self):
        g = classify_hand(_hand(index_up=True, middle_up=True, ring_up=True, pinky_up=True, thumb_out=True))
        assert g and g.name == "open_palm"

    def test_fist(self):
        g = classify_hand(_hand())
        assert g and g.name == "fist"

    def test_peace(self):
        g = classify_hand(_hand(index_up=True, middle_up=True))
        assert g and g.name == "peace"

    def test_point(self):
        g = classify_hand(_hand(index_up=True))
        assert g and g.name == "point"

    def test_thumbs_up(self):
        g = classify_hand(_hand(thumb_out=True))
        assert g and g.name == "thumbs_up"

    def test_pinch(self):
        g = classify_hand(_hand(index_up=True, pinch=True))
        assert g and g.name == "pinch"

    def test_tracker_requires_hold(self):
        tr = GestureTracker(hold_frames=3)
        now = time.time()
        g = classify_hand(_hand(index_up=True, middle_up=True))
        assert tr.update(g, now) is None
        assert tr.update(g, now + 0.01) is None
        fired = tr.update(g, now + 0.02)
        assert fired and fired.name == "peace"


class TestGaze:
    def test_double_blink(self):
        gt = GazeTracker()
        blends = [
            SimpleNamespace(category_name="eyeBlinkLeft", score=0.8),
            SimpleNamespace(category_name="eyeBlinkRight", score=0.8),
        ]
        open_ = [SimpleNamespace(category_name="eyeBlinkLeft", score=0.0)]
        t0 = time.time()
        assert gt.update(blends, None, t0) == []  # first close
        gt.update(open_, None, t0 + 0.05)
        events = gt.update(blends, None, t0 + 0.2)  # second close
        assert any(e.name == "double_blink" for e in events)
