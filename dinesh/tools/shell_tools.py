"""Shell execution and system info."""

import os
import shutil
import subprocess
from datetime import datetime

from config import FULL_CONTROL, SHELL_TIMEOUT


def get_storage() -> str:
    try:
        usage = shutil.disk_usage("/")
        total = usage.total / (1024 ** 3)
        used = usage.used / (1024 ** 3)
        free = usage.free / (1024 ** 3)
        pct = (usage.used / usage.total) * 100
        return (
            f"Storage: {free:.1f} GB free of {total:.1f} GB total. "
            f"{pct:.0f}% used ({used:.1f} GB)."
        )
    except Exception as e:
        return f"Could not get storage: {e}"


def get_battery() -> str:
    try:
        r = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True)
        for line in r.stdout.split("\n"):
            if "%" in line:
                return line.strip()
        return "Battery information unavailable."
    except Exception:
        return "Battery information unavailable."


def get_time_and_date() -> str:
    now = datetime.now()
    return f"It is {now.strftime('%I:%M %p')} on {now.strftime('%A, %B %d, %Y')}."


def get_system_info() -> str:
    try:
        mem = subprocess.run(["vm_stat"], capture_output=True, text=True).stdout
        uptime = subprocess.run(["uptime"], capture_output=True, text=True).stdout.strip()
        pages_free = 0
        for line in mem.split("\n"):
            if "Pages free" in line:
                pages_free = int(line.split(":")[1].strip().rstrip(".")) * 4096
        free_mb = pages_free / (1024 ** 2)
        return f"System: {uptime}. Approximately {free_mb:.0f} MB RAM free."
    except Exception as e:
        return f"System info error: {e}"


def get_cpu_usage() -> str:
    """macOS CPU load from top."""
    try:
        r = subprocess.run(
            ["top", "-l", "1", "-n", "0"],
            capture_output=True, text=True, timeout=15,
        )
        cpu_line = ""
        load_line = ""
        for line in r.stdout.splitlines():
            if "CPU usage" in line:
                cpu_line = line.strip()
            if line.startswith("Load Avg"):
                load_line = line.strip()
        if not cpu_line:
            return "Could not read CPU usage."
        return f"{cpu_line}. {load_line}".strip()
    except Exception as e:
        return f"CPU check failed: {e}"


def get_resource_summary() -> str:
    """CPU + memory + storage in one spoken-friendly summary."""
    parts = [get_cpu_usage(), get_system_info(), get_storage()]
    return " ".join(parts)


def run_command(command: str, cwd: str = "") -> str:
    """Run a shell command. Destructive ops blocked unless FULL_CONTROL."""
    blocked = [
        "rm -rf /", "rm -rf ~", "mkfs", "dd if=", ":(){:|:&};:",
        "format", "> /dev/sda", "chmod -R 777 /",
    ]
    if not FULL_CONTROL:
        blocked.extend([
            "rm ", "rmdir", "sudo rm", "shutdown", "reboot",
            "halt", "poweroff", "kill -9", "shred",
        ])
    cmd_lower = command.lower()
    for b in blocked:
        if b in cmd_lower:
            return f"Blocked command containing '{b.strip()}'."
    work_dir = os.path.expanduser(cwd) if cwd else None
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=SHELL_TIMEOUT, cwd=work_dir,
        )
        out = (result.stdout + result.stderr).strip()
        status = f"exit {result.returncode}"
        if not out:
            return f"Command completed ({status}), no output."
        return f"({status})\n{out[:4000]}"
    except subprocess.TimeoutExpired:
        return f"Command timed out after {SHELL_TIMEOUT}s."
    except Exception as e:
        return f"Command error: {e}"


def list_processes() -> str:
    try:
        r = subprocess.run(
            ["ps", "aux"], capture_output=True, text=True, timeout=10,
        )
        lines = r.stdout.strip().split("\n")[:30]
        return "Top processes:\n" + "\n".join(lines)
    except Exception as e:
        return f"Could not list processes: {e}"
