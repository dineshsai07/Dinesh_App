"""
Vision control — camera + MediaPipe hands/face for gesture & gaze actions.

Runs entirely on-device (Apple Silicon). Requires Camera permission for the
app that launches Dinesh (Terminal / Python).
"""

from __future__ import annotations

from vision.controller import VisionController, VISION_AVAILABLE

__all__ = ["VisionController", "VISION_AVAILABLE"]
