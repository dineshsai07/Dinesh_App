#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║           J.A.R.V.I.S  —  Just A Rather Very               ║
║               Intelligent System  v2.0                      ║
║                                                              ║
║   Built for Mac M4  ·  Fully local  ·  No cloud needed      ║
╠══════════════════════════════════════════════════════════════╣
║  🎤  Whisper      — on-device voice recognition             ║
║  🧠  Ollama       — local LLM (llama3.2)                    ║
║  🔊  Daniel       — commanding British voice                 ║
║  🌐  DuckDuckGo   — web search (needs internet)             ║
║  🖥️   AppleScript  — full Mac control                        ║
╚══════════════════════════════════════════════════════════════╝

OFFLINE MODE:  Voice input, Q&A, Mac control → all work offline
               Web search → requires internet
"""

import os, sys, json, subprocess, tempfile, time, shutil, threading
from datetime import datetime
from pathlib import Path

# ── Third-party ────────────────────────────────────────────────
try:
    import numpy as np
    import sounddevice as sd
    import soundfile as sf
    import whisper
    import ollama
    from duckduckgo_search import DDGS
except ImportError as e:
    print(f"\n❌  Missing dependency: {e}")
    print("    Run:  bash install.sh  first!\n")
    sys.exit(1)

# ══════════════════════════════════════════════════════════════
#  CONFIGURATION
# ══════════════════════════════════════════════════════════════

LLM_MODEL     = "llama3.2"
WHISPER_MODEL = "base"          # tiny | base | small | medium
SAMPLE_RATE   = 16000
CHANNELS      = 1
SILENCE_DB    = 0.008           # mic sensitivity (lower = more sensitive)
SILENCE_SECS  = 1.8            # pause duration to stop recording
MAX_RECORD    = 15              # max seconds per recording

# ── Voice settings ─────────────────────────────────────────────
# Daniel = British English male — closest to Jarvis
# Fallback chain: Daniel → Oliver → Alex → default
PREFERRED_VOICES = ["Daniel", "Oliver", "Alex"]
SPEECH_RATE      = 185          # words per minute (commanding pace)

# ── Personality ────────────────────────────────────────────────
SYSTEM_PROMPT = """You are J.A.R.V.I.S — Just A Rather Very Intelligent System.
You are the personal AI of the user — precise, calm, and efficient like the Jarvis from Iron Man.
Personality rules:
- Address the user as "sir" occasionally but not every sentence
- Be concise. Responses will be spoken aloud — no bullet points, no markdown, no asterisks
- Sound confident and capable, never uncertain
- When completing a task say what you did, not what you're going to do
- If you don't know something, say so briefly and offer to search
- Occasionally add a dry, witty remark — sparingly
You have tools for web search, Mac control, file creation, system info and more.
Never delete files or folders under any circumstances."""

# ══════════════════════════════════════════════════════════════
#  STARTUP UTILITIES
# ══════════════════════════════════════════════════════════════

def pick_voice() -> str:
    """Pick best available voice from preference list."""
    try:
        result = subprocess.run(["say", "-v", "?"], capture_output=True, text=True)
        available = result.stdout.lower()
        for v in PREFERRED_VOICES:
            if v.lower() in available:
                return v
    except Exception:
        pass
    return "Alex"

def ensure_ollama() -> bool:
    """Start Ollama if not running."""
    try:
        ollama.list()
        return True
    except Exception:
        print("  🚀  Starting Ollama service...")
        subprocess.Popen(["ollama", "serve"],
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
        time.sleep(3)
        try:
            ollama.list()
            return True
        except Exception:
            return False

def load_whisper_model():
    print(f"  🧠  Loading Whisper ({WHISPER_MODEL}) on Neural Engine...")
    m = whisper.load_model(WHISPER_MODEL)
    print("  ✅  Whisper ready")
    return m

# ══════════════════════════════════════════════════════════════
#  AUDIO  —  Record & Transcribe
# ══════════════════════════════════════════════════════════════

def record_until_silence() -> np.ndarray:
    """Record audio, auto-stop after SILENCE_SECS of silence."""
    chunk_ms   = 100
    chunk_size = int(SAMPLE_RATE * chunk_ms / 1000)
    max_chunks = int(MAX_RECORD * 1000 / chunk_ms)
    frames, started, silent_n = [], False, 0

    with sd.InputStream(samplerate=SAMPLE_RATE,
                        channels=CHANNELS,
                        dtype="float32") as stream:
        for _ in range(max_chunks):
            chunk, _ = stream.read(chunk_size)
            frames.append(chunk.copy())
            energy = float(np.sqrt(np.mean(chunk ** 2)))
            if energy > SILENCE_DB:
                started  = True
                silent_n = 0
            elif started:
                silent_n += 1
                if silent_n >= int(SILENCE_SECS * 1000 / chunk_ms):
                    break

    return np.concatenate(frames, axis=0)


def transcribe(audio: np.ndarray, model) -> str:
    """Transcribe audio → text using local Whisper."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp = f.name
    try:
        sf.write(tmp, audio, SAMPLE_RATE)
        result = model.transcribe(tmp, language="en", fp16=False)
        return result["text"].strip()
    finally:
        os.unlink(tmp)


def listen_for_wake_word(model, voice: str) -> str:
    """
    Continuous listening mode.
    Waits until 'jarvis' is detected, then records the full command.
    Returns the command text.
    """
    chunk_secs = 3
    chunk_size = int(SAMPLE_RATE * chunk_secs)
    print("  👂  Listening for 'Hey Jarvis'...")

    with sd.InputStream(samplerate=SAMPLE_RATE,
                        channels=CHANNELS,
                        dtype="float32") as stream:
        while True:
            chunk, _ = stream.read(chunk_size)
            energy = float(np.sqrt(np.mean(chunk ** 2)))
            if energy < 0.003:
                continue                          # too quiet — skip transcription
            text = transcribe(chunk, model).lower()
            if "jarvis" in text:
                # Pull out command from the same utterance
                command = text.split("jarvis", 1)[-1].strip(" ,.")
                if len(command) > 3:
                    return command
                # "Hey Jarvis" alone — listen for follow-up command
                _speak("Yes, sir?", voice)
                print("  🎤  Listening...", end="", flush=True)
                audio = record_until_silence()
                return transcribe(audio, model)

# ══════════════════════════════════════════════════════════════
#  SPEECH  —  Text to Speech
# ══════════════════════════════════════════════════════════════

_speak_proc = None

def _speak(text: str, voice: str, wait: bool = False):
    """Speak using macOS say with commanding voice."""
    global _speak_proc
    if _speak_proc and _speak_proc.poll() is None:
        _speak_proc.terminate()
    clean = text.replace('"', "'").replace("*", "").replace("#", "")
    _speak_proc = subprocess.Popen(
        ["say", "-v", voice, "-r", str(SPEECH_RATE), clean]
    )
    if wait:
        _speak_proc.wait()

# ══════════════════════════════════════════════════════════════
#  TOOLS
# ══════════════════════════════════════════════════════════════

# ── System Info ────────────────────────────────────────────────

def get_storage() -> str:
    """Get available storage on the Mac."""
    try:
        usage = shutil.disk_usage("/")
        total = usage.total  / (1024**3)
        used  = usage.used   / (1024**3)
        free  = usage.free   / (1024**3)
        pct   = (usage.used / usage.total) * 100
        return (f"Storage: {free:.1f} GB available out of {total:.1f} GB total. "
                f"{pct:.0f}% used ({used:.1f} GB).")
    except Exception as e:
        return f"Could not get storage info: {e}"

def get_battery() -> str:
    """Get Mac battery level."""
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
    """Get CPU, memory, and uptime overview."""
    try:
        mem   = subprocess.run(["vm_stat"], capture_output=True, text=True).stdout
        uptime= subprocess.run(["uptime"], capture_output=True, text=True).stdout.strip()
        pages_free = 0
        for line in mem.split("\n"):
            if "Pages free" in line:
                pages_free = int(line.split(":")[1].strip().rstrip(".")) * 4096
        free_mb = pages_free / (1024**2)
        return f"System: {uptime}. Approximately {free_mb:.0f} MB RAM free."
    except Exception as e:
        return f"System info error: {e}"

# ── Web ────────────────────────────────────────────────────────

def web_search(query: str) -> str:
    """Search the web via DuckDuckGo (requires internet)."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=4))
        if not results:
            return "No results found."
        return "\n".join(f"- {r['title']}: {r['body']}" for r in results)
    except Exception as e:
        return f"Search failed — check internet connection. Error: {e}"

# ── Mac Control ────────────────────────────────────────────────

def open_app(app_name: str) -> str:
    """Open a macOS application."""
    for name in [app_name, app_name.title(), app_name.upper()]:
        try:
            subprocess.run(["open", "-a", name], check=True, capture_output=True)
            return f"Opened {app_name}."
        except subprocess.CalledProcessError:
            continue
    return f"Application not found: {app_name}."

def set_reminder(title: str, minutes_from_now: int = 10) -> str:
    """Add a reminder to macOS Reminders."""
    script = f'''
    tell application "Reminders"
        set d to (current date) + {int(minutes_from_now) * 60}
        make new reminder with properties {{name:"{title}", due date:d, remind me date:d}}
    end tell
    '''
    try:
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
        return f"Reminder set: '{title}' in {minutes_from_now} minutes."
    except Exception as e:
        return f"Could not set reminder: {e}"

def set_volume(level: int) -> str:
    """Set Mac system volume (0-100)."""
    level = max(0, min(100, int(level)))
    subprocess.run(["osascript", "-e", f"set volume output volume {level}"])
    return f"Volume set to {level}%."

def take_screenshot(filename: str = "") -> str:
    """Take a screenshot and save to Desktop."""
    name = filename if filename else f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    path = os.path.expanduser(f"~/Desktop/{name}")
    subprocess.run(["screencapture", "-x", path])
    return f"Screenshot saved to Desktop as {name}."

def get_clipboard() -> str:
    """Get current clipboard content."""
    try:
        result = subprocess.run(["pbpaste"], capture_output=True, text=True)
        content = result.stdout.strip()
        return content[:500] if content else "Clipboard is empty."
    except Exception:
        return "Could not access clipboard."

def set_clipboard(text: str) -> str:
    """Copy text to clipboard."""
    subprocess.run(["pbcopy"], input=text.encode())
    return f"Copied to clipboard: {text[:80]}{'...' if len(text) > 80 else ''}"

# ── File & Folder CREATION (no delete) ────────────────────────

def create_file(path: str, content: str = "") -> str:
    """Create a new file with optional content."""
    full = os.path.expanduser(path)
    try:
        os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
        with open(full, "w") as f:
            f.write(content)
        return f"File created: {full}"
    except Exception as e:
        return f"Could not create file: {e}"

def create_folder(path: str) -> str:
    """Create a new folder."""
    full = os.path.expanduser(path)
    try:
        os.makedirs(full, exist_ok=True)
        return f"Folder created: {full}"
    except Exception as e:
        return f"Could not create folder: {e}"

def list_files(folder: str = "~/Desktop") -> str:
    """List files in a folder."""
    full = os.path.expanduser(folder)
    try:
        items = sorted(os.listdir(full))
        if not items:
            return f"{folder} is empty."
        visible = [i for i in items if not i.startswith(".")]
        sample = visible[:25]
        out = f"Contents of {folder} ({len(visible)} items):\n"
        out += "\n".join(f"  • {i}" for i in sample)
        if len(visible) > 25:
            out += f"\n  ... and {len(visible) - 25} more."
        return out
    except Exception as e:
        return f"Could not list files: {e}"

def run_safe_command(command: str) -> str:
    """
    Run a safe read-only or creation shell command.
    All destructive operations are blocked.
    """
    BLOCKED = [
        "rm ", "rmdir", "rm -", "sudo rm",
        "mv /", "dd ", "mkfs", "format",
        "shutdown", "reboot", "halt", "poweroff",
        "chmod 777", "chown", "> /dev/",
        "truncate", ":(){:|:&};:", "kill -9",
        "unlink", "shred"
    ]
    cmd_lower = command.lower()
    for b in BLOCKED:
        if b in cmd_lower:
            return f"Blocked: I am not permitted to run destructive commands like '{b.strip()}'."
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True,
            text=True, timeout=10
        )
        out = (result.stdout + result.stderr).strip()
        return out[:600] if out else "Command completed with no output."
    except subprocess.TimeoutExpired:
        return "Command timed out after 10 seconds."
    except Exception as e:
        return f"Command error: {e}"

# ── Tool registry ───────────────────────────────────────────────

TOOL_MAP = {
    "web_search":       web_search,
    "open_app":         open_app,
    "set_reminder":     set_reminder,
    "get_storage":      get_storage,
    "get_battery":      get_battery,
    "get_time_and_date":get_time_and_date,
    "get_system_info":  get_system_info,
    "set_volume":       set_volume,
    "take_screenshot":  take_screenshot,
    "get_clipboard":    get_clipboard,
    "set_clipboard":    set_clipboard,
    "create_file":      create_file,
    "create_folder":    create_folder,
    "list_files":       list_files,
    "run_safe_command": run_safe_command,
}

TOOLS_SCHEMA = [
    {"type":"function","function":{"name":"web_search","description":"Search the internet for current info, news, weather, prices, sports, anything.","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}},
    {"type":"function","function":{"name":"open_app","description":"Open any macOS app by name. Examples: Safari, Spotify, Terminal, Finder, Calendar, Notes, Mail, VS Code.","parameters":{"type":"object","properties":{"app_name":{"type":"string"}},"required":["app_name"]}}},
    {"type":"function","function":{"name":"set_reminder","description":"Set a reminder in macOS Reminders app.","parameters":{"type":"object","properties":{"title":{"type":"string"},"minutes_from_now":{"type":"integer","description":"Minutes until reminder fires. Default 10."}},"required":["title"]}}},
    {"type":"function","function":{"name":"get_storage","description":"Check how much storage space is available on the Mac.","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"get_battery","description":"Check the Mac battery level and charging status.","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"get_time_and_date","description":"Get the current time and date.","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"get_system_info","description":"Get CPU, memory, and uptime info.","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"set_volume","description":"Set Mac system volume from 0 to 100.","parameters":{"type":"object","properties":{"level":{"type":"integer","description":"Volume level 0-100"}},"required":["level"]}}},
    {"type":"function","function":{"name":"take_screenshot","description":"Take a screenshot and save it to the Desktop.","parameters":{"type":"object","properties":{"filename":{"type":"string","description":"Optional filename"}}}}},
    {"type":"function","function":{"name":"get_clipboard","description":"Read current clipboard content.","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"set_clipboard","description":"Copy text to clipboard.","parameters":{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}}},
    {"type":"function","function":{"name":"create_file","description":"Create a new file with optional text content. Path can include ~/Desktop, ~/Documents, etc.","parameters":{"type":"object","properties":{"path":{"type":"string","description":"File path e.g. ~/Desktop/notes.txt"},"content":{"type":"string","description":"File content"}},"required":["path"]}}},
    {"type":"function","function":{"name":"create_folder","description":"Create a new folder on the Mac.","parameters":{"type":"object","properties":{"path":{"type":"string","description":"Folder path e.g. ~/Desktop/Projects"}},"required":["path"]}}},
    {"type":"function","function":{"name":"list_files","description":"List files in a folder. Default is Desktop.","parameters":{"type":"object","properties":{"folder":{"type":"string","description":"Folder path e.g. ~/Desktop, ~/Downloads"}}}}},
    {"type":"function","function":{"name":"run_safe_command","description":"Run a safe terminal command for read-only or creation tasks. No delete/destructive commands allowed.","parameters":{"type":"object","properties":{"command":{"type":"string"}},"required":["command"]}}},
]

# ══════════════════════════════════════════════════════════════
#  LLM CHAT
# ══════════════════════════════════════════════════════════════

conversation_history = [{"role": "system", "content": SYSTEM_PROMPT}]

def chat(user_message: str) -> str:
    """Send message to Ollama, handle tool calls, return reply."""
    conversation_history.append({"role": "user", "content": user_message})

    response = ollama.chat(
        model=LLM_MODEL,
        messages=conversation_history,
        tools=TOOLS_SCHEMA,
    )
    msg = response["message"]

    if msg.get("tool_calls"):
        conversation_history.append(msg)
        for tc in msg["tool_calls"]:
            fname = tc["function"]["name"]
            args  = tc["function"].get("arguments", {})
            print(f"  🔧  [{fname}]  {json.dumps(args)}")
            result = TOOL_MAP[fname](**args) if fname in TOOL_MAP else f"Unknown tool: {fname}"
            conversation_history.append({"role": "tool", "content": str(result)})

        final = ollama.chat(model=LLM_MODEL, messages=conversation_history)
        reply = final["message"]["content"]
    else:
        reply = msg["content"]

    conversation_history.append({"role": "assistant", "content": reply})
    return reply

# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════

BANNER = r"""
     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
     ██║███████║██████╔╝██║   ██║██║███████╗
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
       Just A Rather Very Intelligent System
"""

def print_help():
    print("""
  Commands:
    ENTER         →  voice input
    type message  →  text input
    wake          →  activate continuous 'Hey Jarvis' mode
    clear         →  reset conversation memory
    quit          →  shutdown
    """)

def main():
    voice = pick_voice()
    print(BANNER)
    print(f"  Voice  : {voice} (British commanding)")
    print(f"  Model  : {LLM_MODEL}  |  Whisper: {WHISPER_MODEL}")
    print(f"  Offline: voice + Q&A + Mac control")
    print(f"  Online : web search")
    print()

    if not ensure_ollama():
        print("  ⚠️   Could not start Ollama — make sure it's installed.")
        sys.exit(1)

    wm = load_whisper_model()
    print_help()

    _speak("All systems online. J.A.R.V.I.S. at your service, sir.", voice, wait=True)

    speak = lambda text, wait=False: _speak(text, voice, wait)

    while True:
        try:
            cmd = input("  ▶   [ENTER=voice | type | wake | clear | quit]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            speak("Shutting down. Goodbye, sir.", wait=True)
            break

        if cmd.lower() in ("quit", "exit", "shutdown", "bye"):
            speak("Shutting down. Goodbye, sir.", wait=True)
            break

        if cmd.lower() == "clear":
            conversation_history.clear()
            conversation_history.append({"role": "system", "content": SYSTEM_PROMPT})
            print("  🗑️   Memory cleared.\n")
            continue

        if cmd.lower() == "wake":
            print("  🟢  Wake word mode active. Say 'Hey Jarvis' anytime.")
            speak("Wake word mode activated. Say Hey Jarvis whenever you need me.")
            while True:
                try:
                    user_input = listen_for_wake_word(wm, voice)
                    if not user_input:
                        continue
                    print(f"  🗣   You: {user_input}")
                    if any(w in user_input.lower() for w in ["shutdown", "exit", "goodbye", "stop listening"]):
                        speak("Deactivating wake word mode.")
                        break
                    print("  💭  Processing...", end="", flush=True)
                    response = chat(user_input)
                    print(f"\r  🤖  Jarvis: {response}\n")
                    speak(response)
                except KeyboardInterrupt:
                    speak("Wake word mode deactivated.")
                    break
            continue

        if cmd == "":
            # ── Voice input ───────────────────────────────────
            print("  🎤  Listening...", end="", flush=True)
            audio = record_until_silence()
            print(" transcribing...", end="", flush=True)
            user_input = transcribe(audio, wm)
            print(f"\r  🗣   You: {user_input:<60}")
            if not user_input or len(user_input) < 2:
                print("  ⚠️   Didn't catch that — try again.\n")
                continue
        else:
            user_input = cmd

        print("  💭  Processing...", end="", flush=True)
        response = chat(user_input)
        print(f"\r  🤖  Jarvis: {response}\n")
        speak(response)


if __name__ == "__main__":
    main()
