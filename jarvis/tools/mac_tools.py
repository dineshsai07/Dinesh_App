"""macOS app control, AppleScript, clipboard, reminders."""

import subprocess
from datetime import datetime
from pathlib import Path

from nlu import resolve_app, resolve_folder


def open_app(app_name: str) -> str:
    """Open an application, tolerating misspellings and nicknames."""
    candidates = [app_name, app_name.title(), app_name.capitalize()]
    resolved = resolve_app(app_name)
    if resolved:
        candidates.insert(0, resolved)

    for name in candidates:
        try:
            subprocess.run(["open", "-a", name], check=True, capture_output=True)
            return f"Opened {name}."
        except subprocess.CalledProcessError:
            continue

    # It may have been a folder rather than an app.
    folder = resolve_folder(app_name)
    if folder:
        return open_path(str(folder))
    return f"I could not find an app or folder named '{app_name}'."


def open_path(path: str) -> str:
    """Open a file or folder in Finder / its default application."""
    target = Path(path).expanduser()
    if not target.exists():
        return f"Nothing exists at {target}."
    try:
        subprocess.run(["open", str(target)], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        return f"Could not open {target}: {e}"
    kind = "folder" if target.is_dir() else "file"
    return f"Opened {kind} {target}."


def open_url(url: str) -> str:
    if not url.startswith(("http://", "https://", "file://")):
        url = "https://" + url
    subprocess.run(["open", url], check=True)
    return f"Opened URL in default browser: {url}"


def set_reminder(title: str, minutes_from_now: int = 10) -> str:
    safe = title.replace('"', "'")
    script = f'''
    tell application "Reminders"
        set d to (current date) + {int(minutes_from_now) * 60}
        make new reminder with properties {{name:"{safe}", due date:d, remind me date:d}}
    end tell
    '''
    try:
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
        return f"Reminder set: '{title}' in {minutes_from_now} minutes."
    except Exception as e:
        return f"Could not set reminder: {e}"


def set_volume(level: int) -> str:
    level = max(0, min(100, int(level)))
    subprocess.run(["osascript", "-e", f"set volume output volume {level}"])
    return f"Volume set to {level}%."


def get_clipboard() -> str:
    try:
        result = subprocess.run(["pbpaste"], capture_output=True, text=True)
        content = result.stdout.strip()
        return content[:2000] if content else "Clipboard is empty."
    except Exception:
        return "Could not access clipboard."


def set_clipboard(text: str) -> str:
    subprocess.run(["pbcopy"], input=text.encode())
    return f"Copied to clipboard: {text[:80]}{'...' if len(text) > 80 else ''}"


def run_applescript(script: str) -> str:
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=30,
        )
        out = (r.stdout + r.stderr).strip()
        if r.returncode != 0:
            return f"AppleScript error: {out}"
        return out[:2000] if out else "AppleScript executed successfully."
    except Exception as e:
        return f"AppleScript failed: {e}"


def send_email(to: str, subject: str, body: str) -> str:
    safe_to = to.replace('"', "")
    safe_sub = subject.replace('"', "'")
    safe_body = body.replace('"', "'")
    script = f'''
    tell application "Mail"
        set newMessage to make new outgoing message with properties {{subject:"{safe_sub}", content:"{safe_body}", visible:true}}
        tell newMessage
            make new to recipient at end of to recipients with properties {{address:"{safe_to}"}}
        end tell
        activate
    end tell
    '''
    return run_applescript(script) + " Email draft opened in Mail."


def create_calendar_event(title: str, minutes_from_now: int = 60, duration_minutes: int = 30) -> str:
    safe = title.replace('"', "'")
    start_secs = int(minutes_from_now) * 60
    dur_secs = int(duration_minutes) * 60
    script = f'''
    tell application "Calendar"
        tell calendar "Home"
            set startDate to (current date) + {start_secs}
            set endDate to startDate + {dur_secs}
            make new event with properties {{summary:"{safe}", start date:startDate, end date:endDate}}
        end tell
    end tell
    '''
    try:
        return run_applescript(script) + f" Event '{title}' created."
    except Exception:
        return run_applescript(script.replace('"Home"', 'first calendar')) + f" Event '{title}' created."


def take_screenshot(filename: str = "") -> str:
    name = filename or f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    path = f"~/Desktop/{name}"
    full = __import__("os").path.expanduser(path)
    subprocess.run(["screencapture", "-x", full])
    return full
