"""
Unit tests for audio helpers that do not require real microphone hardware.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import audio  # noqa: E402


def test_wake_match_returns_tail_after_name():
    assert audio.wake_match("hey dinesh open safari") == "open safari"


def test_wake_match_none_when_not_present():
    assert audio.wake_match("hello there") is None


def test_clean_speech_removes_markup_chars():
    cleaned = audio._clean_speech('`Hello` *world* #tag "sir"')
    assert "`" not in cleaned
    assert "*" not in cleaned
    assert "#" not in cleaned
    assert '"' not in cleaned
    assert "'sir'" in cleaned


def test_transcribe_uses_supplied_model(monkeypatch):
    class DummyModel:
        def transcribe(self, _tmp, **_kwargs):
            return {"text": "  done  "}

    def fake_write(_path, _audio, _rate):
        return None

    monkeypatch.setattr(audio.sf, "write", fake_write)
    text = audio.transcribe(np.zeros((10, 1), dtype="float32"), model=DummyModel())
    assert text == "done"
