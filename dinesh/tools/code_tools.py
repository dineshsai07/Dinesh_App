"""
Python code execution — Open Interpreter pattern.

Give the model a short Python sandbox with Path, HOME, DESKTOP instead of
forcing every file task through fragile function calls.
"""

from __future__ import annotations

import io
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from config import DESKTOP_DIR, FULL_CONTROL, HOME_DIR


_HARD_BLOCK = ("os.system", "subprocess", "eval(", "exec(", "__import__", "socket", "ctypes", "pty")
_SOFT_BLOCK = ("shutil.rmtree", "os.remove", "os.rmdir", "Path.unlink", ".unlink(", ".rmdir(")


def run_python(code: str) -> str:
    """Run a short Python snippet. Prefers Path.mkdir / write_text for creation."""
    low = code
    for b in _HARD_BLOCK:
        if b in low:
            return f"Blocked unsafe call '{b}'."
    if not FULL_CONTROL:
        for b in _SOFT_BLOCK:
            if b in low:
                return f"Blocked destructive call '{b}'. Set DINESH_FULL_CONTROL=1 to allow."

    namespace = {
        "__builtins__": {
            "print": print, "len": len, "str": str, "int": int, "float": float,
            "list": list, "dict": dict, "range": range, "enumerate": enumerate,
            "zip": zip, "min": min, "max": max, "sum": sum, "open": open,
            "True": True, "False": False, "None": None, "Exception": Exception,
        },
        "Path": Path,
        "HOME": Path(HOME_DIR),
        "DESKTOP": Path(DESKTOP_DIR),
    }

    out_buf, err_buf = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(out_buf), redirect_stderr(err_buf):
            exec(code, namespace, namespace)  # noqa: S102
        out = (out_buf.getvalue() + err_buf.getvalue()).strip()
        return out[:4000] if out else "Python executed successfully (no output)."
    except Exception:
        return f"Python error:\n{traceback.format_exc()[-1500:]}"
