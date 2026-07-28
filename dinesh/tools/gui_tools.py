"""GUI automation — mouse, keyboard, screen capture."""

import subprocess
import time
from datetime import datetime

import pyautogui

from config import PYAUTOGUI_PAUSE, TYPE_INTERVAL, ensure_screenshot_dir

pyautogui.FAILSAFE = True  # move mouse to top-left corner to abort
pyautogui.PAUSE = PYAUTOGUI_PAUSE


def get_screen_size() -> str:
    w, h = pyautogui.size()
    return f"Screen resolution: {w}x{h} pixels."


def get_mouse_position() -> str:
    x, y = pyautogui.position()
    return f"Mouse at ({x}, {y})."


def move_mouse(x: int, y: int) -> str:
    pyautogui.moveTo(int(x), int(y), duration=0.3)
    return f"Moved mouse to ({x}, {y})."


def click_at(x: int, y: int, button: str = "left", clicks: int = 1) -> str:
    pyautogui.click(int(x), int(y), clicks=int(clicks), button=button)
    return f"Clicked {button} button {clicks}x at ({x}, {y})."


def double_click_at(x: int, y: int) -> str:
    pyautogui.doubleClick(int(x), int(y))
    return f"Double-clicked at ({x}, {y})."


def right_click_at(x: int, y: int) -> str:
    pyautogui.rightClick(int(x), int(y))
    return f"Right-clicked at ({x}, {y})."


def scroll(amount: int, x: int = 0, y: int = 0) -> str:
    if x or y:
        pyautogui.moveTo(int(x) or None, int(y) or None)
    pyautogui.scroll(int(amount))
    direction = "up" if amount > 0 else "down"
    return f"Scrolled {direction} {abs(amount)} units."


def type_text(text: str, interval: float = TYPE_INTERVAL) -> str:
    if text.isascii() and all(c.isprintable() for c in text):
        pyautogui.write(text, interval=interval)
    else:
        subprocess.run(["pbcopy"], input=text.encode())
        pyautogui.hotkey("command", "v")
        time.sleep(0.2)
    return f"Typed {len(text)} characters."


def press_key(key: str) -> str:
    pyautogui.press(key)
    return f"Pressed key: {key}."


def hotkey(*keys: str) -> str:
    pyautogui.hotkey(*keys)
    return f"Pressed hotkey: {'+'.join(keys)}."


def capture_screen(filename: str = "") -> str:
    name = filename or f"screen_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    path = ensure_screenshot_dir() / name
    img = pyautogui.screenshot()
    img.save(str(path))
    return str(path)


def drag(from_x: int, from_y: int, to_x: int, to_y: int, duration: float = 0.5) -> str:
    pyautogui.moveTo(from_x, from_y)
    pyautogui.drag(to_x - from_x, to_y - from_y, duration=duration)
    return f"Dragged from ({from_x},{from_y}) to ({to_x},{to_y})."


def list_windows() -> str:
    script = '''
    tell application "System Events"
        set out to ""
        repeat with p in (every process whose background only is false)
            try
                set out to out & (name of p) & linefeed
            end try
        end repeat
        return out
    end tell
    '''
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=10)
        apps = [a.strip() for a in r.stdout.strip().split("\n") if a.strip()]
        if not apps:
            return "No visible windows found."
        return "Visible apps:\n" + "\n".join(f"  • {a}" for a in sorted(set(apps)))
    except Exception as e:
        return f"Could not list windows: {e}"


def focus_app(app_name: str) -> str:
    script = f'''
    tell application "{app_name}"
        activate
    end tell
    '''
    try:
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True, timeout=10)
        time.sleep(0.5)
        return f"Focused app: {app_name}."
    except Exception:
        try:
            subprocess.run(["open", "-a", app_name], check=True, capture_output=True)
            time.sleep(0.5)
            return f"Opened and focused: {app_name}."
        except Exception as e:
            return f"Could not focus {app_name}: {e}"


def minimize_front_window() -> str:
    pyautogui.hotkey("command", "m")
    return "Minimized front window."


def close_front_window() -> str:
    pyautogui.hotkey("command", "w")
    return "Closed front window."


def show_notification(title: str, message: str) -> str:
    safe_title = title.replace('"', "'")
    safe_msg = message.replace('"', "'")
    script = f'display notification "{safe_msg}" with title "{safe_title}"'
    subprocess.run(["osascript", "-e", script], capture_output=True)
    return f"Notification shown: {title}."
