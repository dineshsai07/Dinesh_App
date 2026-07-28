"""
Regression tests for persistent memory store behaviours.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from memory import store  # noqa: E402


def test_remember_and_stats(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "memory" / "dinesh_memory.db")
    monkeypatch.setattr(store, "TRAIN_DIR", tmp_path / "memory" / "training")

    store.init_db()
    store.remember_fact("my name is dinesh", source="test")
    store.remember_preference("voice", "ryan")
    store.remember_correction("opne", "open")
    store.log_turn("user", "hello")
    store.log_turn("assistant", "hi")
    store.add_episode("greeting roundtrip")

    stats = store.stats()
    assert stats["facts"] == 1
    assert stats["preferences"] == 1
    assert stats["corrections"] == 1
    assert stats["turns"] == 2
    assert stats["episodes"] == 1


def test_export_training_jsonl_contains_messages(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "memory" / "dinesh_memory.db")
    monkeypatch.setattr(store, "TRAIN_DIR", tmp_path / "memory" / "training")
    store.init_db()
    store.log_turn("user", "open safari")
    store.log_turn("assistant", "Opened Safari.")
    out = store.export_training_jsonl()
    data = out.read_text()
    assert '"messages"' in data
    assert "open safari" in data
