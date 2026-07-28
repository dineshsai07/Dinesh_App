"""
Safety confirmation tests for shell and file tools.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import file_tools, shell_tools  # noqa: E402


def test_delete_requires_confirmation_in_full_control(tmp_path, monkeypatch):
    monkeypatch.setattr(file_tools, "FULL_CONTROL", True)
    target = tmp_path / "deleteme.txt"
    target.write_text("x")

    msg1 = file_tools.delete_path(str(target))
    assert "Confirmation required" in msg1
    assert target.exists()

    msg2 = file_tools.delete_path(f"confirm:{target}")
    assert "Deleted" in msg2
    assert not target.exists()


def test_risky_shell_requires_confirmation_in_full_control(monkeypatch):
    monkeypatch.setattr(shell_tools, "FULL_CONTROL", True)

    called = {"ran": False}

    class Dummy:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_run(*_args, **_kwargs):
        called["ran"] = True
        return Dummy()

    monkeypatch.setattr(shell_tools.subprocess, "run", fake_run)

    first = shell_tools.run_command("mv a b")
    assert "Confirmation required" in first
    assert called["ran"] is False

    second = shell_tools.run_command("confirm mv a b")
    assert "(exit 0)" in second
    assert called["ran"] is True
