"""
Intent router — handles unambiguous one-shot commands without an LLM round-trip.

Input is normalised first (see `nlu.py`), so misspelled commands such as
"opne chorme" or "whats the batery" still route correctly. Anything ambiguous,
multi-step, or web-related returns None and falls through to the LLM agent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from nlu import normalize, resolve_app, resolve_folder
from tools import file_tools as files
from tools import mac_tools as mac
from tools import shell_tools as shell
from tools import web_tools as web

HOME = Path.home()
DESKTOP = HOME / "Desktop"

# Markers that mean the request needs planning, web access, or several steps.
_NEEDS_AGENT = (
    " and ", " then ", " also ", " after ", " before ",
    "scrap", "fetch", "website", "http", "www.", ".com", ".in", ".org",
    "news", "headline", "latest", "summarise", "summarize", "explain",
    "why", "compare", "write me", "draft", "translate",
)

# Tightly-scoped rules; their regexes are specific enough that we can run them
# even when the text contains words like "and" or ".com".
_PRECISE_RULES = (
    "_time_and_date", "_battery", "_resources", "_storage",
    "_volume", "_screenshot", "_open_something",
)

# Looser rules that could misfire on multi-step requests.
_LOOSE_RULES = ("_create_folder", "_list_files", "_web_search")


def _needs_agent(low: str) -> bool:
    return any(marker in low for marker in _NEEDS_AGENT)


def handle_intent(text: str) -> str | None:
    """Return a response string for simple commands, or None to defer to the LLM."""
    raw = (text or "").strip()
    if not raw:
        return None

    clean = normalize(raw)
    low = clean.lower().strip(" .!?")

    for name in _PRECISE_RULES:
        result = globals()[name](low, clean)
        if result is not None:
            return result

    if _needs_agent(low):
        return None

    for name in _LOOSE_RULES:
        result = globals()[name](low, clean)
        if result is not None:
            return result
    return None


# ── Individual rules ───────────────────────────────────────────
# Each takes (normalised_lowercase, normalised_original) and returns str | None.

def _time_and_date(low: str, _raw: str) -> str | None:
    if re.search(r"\b(time|date|day)\b", low) and re.search(
        r"\b(what|whats|tell|current|now|today|give)\b", low
    ):
        return shell.get_time_and_date()
    return None


def _battery(low: str, _raw: str) -> str | None:
    if re.search(r"\b(battery|charge|charging|power level)\b", low) and len(low.split()) <= 9:
        return shell.get_battery()
    return None


def _resources(low: str, _raw: str) -> str | None:
    topics = sum(
        1 for pattern in (r"\bcpu\b", r"\b(ram|memory)\b", r"\b(disk|storage|space)\b")
        if re.search(pattern, low)
    )
    if topics >= 2:
        return shell.get_resource_summary()
    if re.search(r"\bcpu\b", low) and re.search(r"\b(usage|load|how much|whats|status)\b", low):
        return shell.get_cpu_usage()
    return None


def _storage(low: str, _raw: str) -> str | None:
    if re.search(r"\b(disk|storage|space)\b", low) and re.search(
        r"\b(how much|how is|free|left|available|whats|what is|check|show|remaining)\b", low
    ):
        return shell.get_storage()
    return None


def _volume(low: str, _raw: str) -> str | None:
    m = re.search(r"\b(?:set|change|turn|put)\s+(?:the\s+)?volume\s+(?:to\s+)?(\d{1,3})", low)
    if m:
        return mac.set_volume(int(m.group(1)))
    if re.search(r"\b(mute|silence)\b.*\bvolume\b|\bmute\b$", low):
        return mac.set_volume(0)
    return None


def _screenshot(low: str, _raw: str) -> str | None:
    if re.fullmatch(r"(take\s+|grab\s+|capture\s+)?(a\s+|the\s+)?screenshot(\s+now)?", low):
        return f"Screenshot saved to {mac.take_screenshot()}."
    return None


def _open_something(low: str, raw: str) -> str | None:
    """Open an app, a folder, or a URL — deciding which from the target."""
    m = re.match(r"^(?:open|launch|start|show|go to)\s+(?:up\s+)?(.{2,60})$", raw.strip(), re.I)
    if not m:
        return None
    target = m.group(1).strip(" .?")
    target_low = target.lower()

    # "open safari and search for news" is a multi-step request, not an open.
    if any(joiner in f" {target_low} " for joiner in (" and ", " then ", " also ")):
        return None

    if re.match(r"^(https?://|www\.)", target_low) or re.search(r"\.(com|org|net|io|in|dev)\b", target_low):
        return mac.open_url(target)

    # Explicit folder wording, or an actual path.
    wants_folder = bool(re.search(r"\b(folder|directory|dir)\b", target_low))
    if target.startswith(("~", "/")):
        return mac.open_path(target)

    if wants_folder:
        folder = resolve_folder(target)
        return mac.open_path(str(folder)) if folder else f"I could not find a folder called '{target}'."

    # Prefer an app; fall back to a folder of the same name.
    if resolve_app(target):
        return mac.open_app(target)
    folder = resolve_folder(target)
    if folder:
        return mac.open_path(str(folder))
    return mac.open_app(target)


def _create_folder(low: str, raw: str) -> str | None:
    m = re.match(
        r"^(?:create|make|add)\s+(?:a\s+|new\s+)*folder\s+(?:called|named)?\s*"
        r"[\"']?([A-Za-z0-9_\- ]{1,40}?)[\"']?"
        r"(?:\s+(?:on|in)\s+(?:my\s+|the\s+)?(desktop|documents|downloads|home))?\.?$",
        raw.strip(), re.I,
    )
    if not m:
        return None
    name = re.sub(r"[^\w\- ]", "", m.group(1)).strip() or "NewFolder"
    where = resolve_folder(m.group(2) or "desktop") or DESKTOP
    return files.create_folder(str(where / name))


def _list_files(low: str, raw: str) -> str | None:
    m = re.match(
        r"^(?:list|show|whats?(?:\s+is)?)\s+(?:me\s+)?(?:the\s+)?"
        r"(?:files|contents?)\s+(?:in|of|inside)\s+(?:my\s+|the\s+)?(.{2,40})$",
        raw.strip(), re.I,
    )
    if not m:
        return None
    folder = resolve_folder(m.group(1)) or DESKTOP
    return files.list_files(str(folder))


def _web_search(low: str, raw: str) -> str | None:
    m = re.match(r"^(?:search(?:\s+for)?|google|look up)\s+(.+)$", raw.strip(), re.I)
    if not m:
        return None
    query = m.group(1).strip(" .?")
    return web.web_search(query) if 2 < len(query) < 80 else None


def _about_me_html(title: str) -> str:
    user = os.environ.get("USER", "Creator")
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"/><title>About {user}</title>
<style>body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#0a0e17;color:#e8f4ff;font-family:system-ui}}
main{{max-width:640px;padding:2.5rem;border:1px solid rgba(0,229,255,.25);border-radius:20px}}
h1{{margin:0 0 1rem}}p{{color:#8aa4b8;line-height:1.7}}</style></head>
<body><main><h1>About {user}</h1>
<p>Built with Dinesh on Apple Silicon — local, private, on-device.</p>
<p>Project: {title}</p></main></body></html>"""
