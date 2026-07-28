"""File and folder operations."""

import os
import shutil
import time
from pathlib import Path
from threading import Lock

from config import FULL_CONTROL

_CONFIRM_TTL_SECS = 120
_pending_lock = Lock()
_pending_delete = ""
_pending_until = 0.0


def create_file(path: str, content: str = "") -> str:
    full = os.path.expanduser(path)
    try:
        os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
        with open(full, "w") as f:
            f.write(content)
        return f"File created: {full}"
    except Exception as e:
        return f"Could not create file: {e}"


def read_file(path: str, max_chars: int = 8000) -> str:
    full = os.path.expanduser(path)
    try:
        with open(full, "r", errors="replace") as f:
            content = f.read(max_chars)
        if len(content) >= max_chars:
            content += "\n...[truncated]"
        return content or "(empty file)"
    except Exception as e:
        return f"Could not read file: {e}"


def write_file(path: str, content: str) -> str:
    full = os.path.expanduser(path)
    try:
        os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
        with open(full, "w") as f:
            f.write(content)
        return f"Wrote {len(content)} chars to {full}."
    except Exception as e:
        return f"Could not write file: {e}"


def append_file(path: str, content: str) -> str:
    full = os.path.expanduser(path)
    try:
        with open(full, "a") as f:
            f.write(content)
        return f"Appended to {full}."
    except Exception as e:
        return f"Could not append: {e}"


def create_folder(path: str) -> str:
    full = os.path.expanduser(path)
    try:
        os.makedirs(full, exist_ok=True)
        return f"Folder created: {full}"
    except Exception as e:
        return f"Could not create folder: {e}"


def list_files(folder: str = "~/Desktop") -> str:
    full = os.path.expanduser(folder)
    try:
        items = sorted(os.listdir(full))
        visible = [i for i in items if not i.startswith(".")]
        if not visible:
            return f"{folder} is empty."
        sample = visible[:40]
        out = f"Contents of {folder} ({len(visible)} items):\n"
        out += "\n".join(f"  • {i}" for i in sample)
        if len(visible) > 40:
            out += f"\n  ... and {len(visible) - 40} more."
        return out
    except Exception as e:
        return f"Could not list files: {e}"


def move_file(source: str, destination: str) -> str:
    src, dst = os.path.expanduser(source), os.path.expanduser(destination)
    try:
        os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
        shutil.move(src, dst)
        return f"Moved {src} → {dst}."
    except Exception as e:
        return f"Could not move: {e}"


def copy_file(source: str, destination: str) -> str:
    src, dst = os.path.expanduser(source), os.path.expanduser(destination)
    try:
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
            shutil.copy2(src, dst)
        return f"Copied {src} → {dst}."
    except Exception as e:
        return f"Could not copy: {e}"


def delete_path(path: str) -> str:
    global _pending_delete, _pending_until
    if not FULL_CONTROL:
        return "Delete blocked. Set DINESH_FULL_CONTROL=1 to enable destructive file operations."
    full = os.path.expanduser(path)
    confirm_prefix = "confirm:"
    if full.lower().startswith(confirm_prefix):
        candidate = os.path.expanduser(full[len(confirm_prefix):].strip())
        with _pending_lock:
            if (
                _pending_delete
                and time.time() <= _pending_until
                and candidate == _pending_delete
            ):
                full = candidate
                _pending_delete = ""
                _pending_until = 0.0
            else:
                return (
                    "No matching pending delete request. "
                    "Call delete_path once, then confirm with: confirm:/exact/path"
                )
    else:
        with _pending_lock:
            _pending_delete = full
            _pending_until = time.time() + _CONFIRM_TTL_SECS
        return (
            "Confirmation required for delete. "
            "Call delete_path again with: confirm:"
            f"{full}"
        )
    try:
        if os.path.isdir(full):
            shutil.rmtree(full)
        elif os.path.isfile(full):
            os.remove(full)
        else:
            return f"Path not found: {full}"
        return f"Deleted: {full}"
    except Exception as e:
        return f"Could not delete: {e}"
