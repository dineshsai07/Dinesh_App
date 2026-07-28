"""
Server-level tests for safety and telemetry helpers.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402


def test_maybe_clear_stale_busy_resets_state(monkeypatch):
    server._set_busy(True)
    server.busy_since = time.time() - (server.BUSY_STALE_SECS + 2)

    called = {"abort": False, "push": False}

    monkeypatch.setattr(server, "abort_listen", lambda: called.__setitem__("abort", True))
    monkeypatch.setattr(
        server,
        "push",
        lambda event, **kwargs: called.__setitem__("push", event == "status" and kwargs.get("status") == "idle"),
    )

    assert server._maybe_clear_stale_busy() is True
    assert called["abort"] is True
    assert called["push"] is True
    assert server.busy is False


def test_collect_telemetry_has_core_keys():
    data = server.collect_telemetry()
    for key in ("cpu", "ram", "disk", "load", "uptime", "battery"):
        assert key in data
