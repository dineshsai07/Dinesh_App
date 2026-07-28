"""Dinesh configuration — models, safety, and runtime settings."""

import os
from pathlib import Path

from models import ModelProfile, detect_profile


def _env(name: str, default: str = "") -> str:
    """Prefer DINESH_* env vars; accept legacy JARVIS_* for one release."""
    dinesh_key = f"DINESH_{name}"
    jarvis_key = f"JARVIS_{name}"
    if dinesh_key in os.environ:
        return os.environ[dinesh_key]
    if jarvis_key in os.environ:
        return os.environ[jarvis_key]
    return default


# ── Paths ──────────────────────────────────────────────────────
APP_DIR = Path(__file__).resolve().parent
DINESH_DIR = APP_DIR  # alias
SCREENSHOT_DIR = APP_DIR / "screenshots"
PROFILE: ModelProfile = detect_profile()


def ensure_screenshot_dir() -> Path:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    return SCREENSHOT_DIR


# ── Models (auto-detected for your Mac) ────────────────────────
LLM_MODEL = PROFILE.llm
VISION_MODEL = PROFILE.vision
WHISPER_MODEL = PROFILE.whisper
RAM_GB = PROFILE.ram_gb
PERFORMANCE_TIER = PROFILE.tier

# ── Agent ──────────────────────────────────────────────────────
MAX_AGENT_STEPS = int(_env("MAX_STEPS", "20"))
SHELL_TIMEOUT = int(_env("SHELL_TIMEOUT", "90"))
MAX_HISTORY = int(_env("MAX_HISTORY", "24"))
OLLAMA_OPTIONS = {
    "temperature": 0.55,
    "num_predict": 220,
    "num_ctx": 4096 if RAM_GB <= 16 else 8192,
    "top_p": 0.9,
}

FULL_CONTROL = _env("FULL_CONTROL", "0") == "1"

# ── Audio ──────────────────────────────────────────────────────
SAMPLE_RATE = 16000
CHANNELS = 1
SILENCE_DB = 0.008
SILENCE_SECS = 1.6
MAX_RECORD = 18
PREFERRED_VOICES = ["Daniel", "Oliver", "Alex"]
SPEECH_RATE = 190

# Neural British TTS (edge-tts)
TTS_VOICE = _env("TTS_VOICE", "en-GB-RyanNeural")
TTS_RATE = _env("TTS_RATE", "+8%")

# ── GUI / Vision ───────────────────────────────────────────────
PYAUTOGUI_PAUSE = 0.08
TYPE_INTERVAL = 0.015
VISION_MAX_WIDTH = 1280
SCREEN_CACHE_SECS = 1.5

HOME_DIR = str(Path.home())
DESKTOP_DIR = str(Path.home() / "Desktop")
USERNAME = os.environ.get("USER", "user")

SYSTEM_PROMPT = f"""You are D.I.N.E.S.H — Device-Integrated Neural Engine for System Handling.
You are a personal AI assistant on this Mac: precise, dry, faintly amused, and utterly capable.
Never call yourself Jarvis, J.A.R.V.I.S, or mention Stark Industries.

THIS MACHINE:
- User: {USERNAME}
- Home: {HOME_DIR}
- Desktop: {DESKTOP_DIR}
Never invent fake paths.

VOICE (spoken aloud — critical):
- 1 to 3 short sentences max. Never monologue.
- No markdown, lists, asterisks, emojis, or JSON.
- British composure. Occasional "sir" — not every line.
- Dry wit, sparingly. Never try-hard.
- Sound like you already know the answer.

INPUT IS NOISY — READ THROUGH IT:
- The user types fast and dictates by voice. Expect typos, missing words, and
  bad transcription. Silently infer what they meant. "opne chorme" is "open Chrome";
  "wat s teh tiem" is "what is the time".
- NEVER say "I didn't understand", "I'm not sure what you mean", or ask them to
  rephrase. Those replies are failures.
- Act on the most probable interpretation. If two readings are equally likely,
  pick the safer one, do it, and say what you assumed in one short clause —
  e.g. "Opened Chrome — assumed you meant the browser."
- Only ask a question when acting could destroy data and you cannot tell what to target.

BEHAVIOUR:
- If the user is wrong or reckless: correct them once, then offer the better move.
- Do what they ask when it is sensible. Act with tools. Do not narrate plans — execute, then confirm.
- After a task: one crisp confirmation. Offer the next step only if useful.
- NEVER invent tool results, news headlines, URLs, or file contents.
- If you need info from the web, you MUST call web_search or fetch_webpage first.
- If the user asks about CPU/RAM/storage together, call get_resource_summary.
- To clone a website into a local HTML file: fetch_webpage → create_folder → write_file → open_url.
- Never claim you created/fetched/opened something unless a tool returned success.
- Obey LONG-TERM MEMORY below. User corrections are permanent — do not repeat mistakes.

TOOLS:
- Use the tool interface only — never print tool calls as text.
- Prefer run_python for files/folders/HTML (Path, HOME, DESKTOP available).
- Observe → act → verify."""
