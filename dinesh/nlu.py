"""
Natural-language pre-processing for D.I.N.E.S.H.

Speech-to-text and fast typing both produce noisy input. Rather than failing
with "I didn't understand", we normalise the text first:

  1. Fix common misspellings via a curated map (fast, exact).
  2. Fuzzy-correct remaining unknown words against a domain vocabulary.
  3. Resolve app / folder names against what actually exists on this Mac.

Everything here is best-effort: if we cannot confidently correct a token we
leave it untouched rather than guessing wildly.
"""

from __future__ import annotations

import functools
import os
import re
from difflib import SequenceMatcher, get_close_matches
from pathlib import Path

HOME = Path.home()

# ── Curated corrections ────────────────────────────────────────
# Short words are unsafe for fuzzy matching, so handle them explicitly.
COMMON_TYPOS: dict[str, str] = {
    # verbs
    "opne": "open", "oepn": "open", "opn": "open", "pen": "open",
    "clsoe": "close", "colse": "close",
    "creat": "create", "crate": "create", "craete": "create", "creaet": "create",
    "mak": "make", "amke": "make",
    "delet": "delete", "delte": "delete", "remvoe": "remove",
    "srch": "search", "serach": "search", "seach": "search", "saerch": "search",
    "tel": "tell", "shwo": "show", "shw": "show",
    "lauch": "launch", "launc": "launch", "laucnh": "launch",
    "tkae": "take", "taek": "take",
    "wirte": "write", "writ": "write",
    "chekc": "check", "chck": "check", "cehck": "check",
    "runn": "run", "exectue": "execute", "exeucte": "execute",
    # question words
    "wat": "what", "waht": "what", "wht": "what", "whta": "what",
    "hwo": "how", "hwat": "what", "wich": "which", "wehre": "where",
    "wher": "where", "whn": "when", "wehn": "when", "wy": "why",
    "hows": "how is", "whats": "what is", "wats": "what is",
    "yuo": "you", "yuor": "your", "youre": "you are",
    "abt": "about", "abut": "about", "abuot": "about",
    "mch": "much", "muhc": "much", "mucht": "much",
    "hav": "have", "haev": "have", "ahve": "have",
    "lft": "left", "lef": "left",
    "jok": "joke", "joek": "joke",
    "canu": "can you", "canyou": "can you",
    # nouns
    "downlaods": "downloads", "downlods": "downloads", "donwloads": "downloads",
    "dowloads": "downloads", "donloads": "downloads",
    "desktp": "desktop", "deskotp": "desktop", "dekstop": "desktop",
    "documnets": "documents", "documets": "documents", "docuemnts": "documents",
    "flder": "folder", "foldr": "folder", "fodler": "folder", "folde": "folder",
    "fiel": "file", "fle": "file", "flie": "file",
    "screenshto": "screenshot", "screenshoot": "screenshot",
    "screnshot": "screenshot", "screeshot": "screenshot",
    "batery": "battery", "battry": "battery", "baterry": "battery",
    "memry": "memory", "memmory": "memory", "meomry": "memory",
    "storag": "storage", "stroage": "storage",
    "spac": "space", "spce": "space", "sapce": "space",
    "volme": "volume", "voluem": "volume", "volum": "volume",
    "brwoser": "browser", "browsr": "browser",
    "wifi": "wi-fi", "internt": "internet", "internte": "internet",
    "systm": "system", "sytem": "system", "sysetm": "system",
    "tiem": "time", "tmie": "time",
    "wheather": "weather", "wether": "weather", "weathr": "weather",
    "usag": "usage", "usge": "usage", "usege": "usage", "usaeg": "usage",
    "chorme": "chrome", "chrom": "chrome", "safri": "safari",
    "terminl": "terminal", "termnal": "terminal", "finde": "finder",
    "computrs": "computers", "compuers": "computers", "computor": "computer",
    "compter": "computer", "machne": "machine",
    # misc
    "teh": "the", "adn": "and", "nad": "and", "ot": "to", "fo": "of",
    "pls": "please", "plz": "please", "thnx": "thanks", "ty": "thanks",
    "u": "you", "ur": "your", "r": "are",
    "dooing": "doing", "somthing": "something", "anythign": "anything",
}

# Vocabulary used for fuzzy correction of longer unknown words.
DOMAIN_VOCAB: set[str] = {
    # actions
    "open", "close", "launch", "start", "stop", "quit", "create", "make",
    "delete", "remove", "move", "copy", "rename", "search", "google", "find",
    "show", "tell", "read", "write", "append", "run", "execute", "take",
    "capture", "screenshot", "click", "type", "scroll", "press", "set",
    "increase", "decrease", "mute", "play", "pause", "download", "install",
    "check", "list", "summarise", "summarize", "explain", "remember", "train",
    # objects
    "file", "files", "folder", "folders", "directory", "app", "application",
    "window", "tab", "browser", "terminal", "editor", "document", "documents",
    "desktop", "downloads", "pictures", "music", "movies", "library", "home",
    "screen", "volume", "brightness", "battery", "storage", "disk", "memory",
    "cpu", "ram", "network", "internet", "system", "process", "processes",
    "clipboard", "reminder", "calendar", "email", "note", "notes",
    # question words / fillers
    "what", "when", "where", "which", "why", "how", "who", "is", "are",
    "the", "time", "date", "today", "tomorrow", "weather", "news", "usage",
    "space", "much", "have", "left", "joke", "about", "you", "your",
    "computer", "computers", "machine", "something", "anything",
    "can", "do", "me", "my", "a", "an", "i", "to", "of", "in", "on",
}


@functools.lru_cache(maxsize=1)
def installed_apps() -> list[str]:
    """Application names available on this Mac, including nested Utilities."""
    names: set[str] = set()
    roots = ("/Applications", "/System/Applications", str(HOME / "Applications"))
    for base in roots:
        try:
            entries = os.listdir(base)
        except OSError:
            continue
        for entry in entries:
            if entry.endswith(".app"):
                names.add(entry[:-4])
                continue
            # One level deeper, e.g. /System/Applications/Utilities
            nested = os.path.join(base, entry)
            if os.path.isdir(nested):
                try:
                    for sub in os.listdir(nested):
                        if sub.endswith(".app"):
                            names.add(sub[:-4])
                except OSError:
                    continue
    return sorted(names)


@functools.lru_cache(maxsize=1)
def _app_lookup() -> dict[str, str]:
    return {a.lower(): a for a in installed_apps()}


@functools.lru_cache(maxsize=1)
def _app_word_index() -> dict[str, str]:
    """Map each significant word of an app name to the full name.

    Lets "chrome" resolve to "Google Chrome" and "photoshop" to
    "Adobe Photoshop 2024".
    """
    index: dict[str, str] = {}
    skip = {"app", "the", "for", "and", "adobe", "microsoft", "google", "apple"}
    for app in installed_apps():
        for word in re.split(r"[\s\-_]+", app.lower()):
            word = word.strip("().")
            if len(word) < 3 or word in skip or word.isdigit():
                continue
            # Prefer the shortest app name for an ambiguous word.
            if word not in index or len(app) < len(index[word]):
                index[word] = app
    return index


# Common folders users refer to by name.
def known_folders() -> dict[str, Path]:
    candidates = {
        "desktop": HOME / "Desktop",
        "downloads": HOME / "Downloads",
        "documents": HOME / "Documents",
        "pictures": HOME / "Pictures",
        "music": HOME / "Music",
        "movies": HOME / "Movies",
        "home": HOME,
        "applications": Path("/Applications"),
    }
    return {name: path for name, path in candidates.items() if path.exists()}


def _correct_token(token: str, vocab: list[str]) -> str:
    """Correct a single lowercase word, or return it unchanged."""
    if token in COMMON_TYPOS:
        return COMMON_TYPOS[token]
    # Too short to fuzzy-match safely ("cat" vs "car" etc).
    if len(token) < 5 or token in DOMAIN_VOCAB or not token.isalpha():
        return token
    match = get_close_matches(token, vocab, n=1, cutoff=0.84)
    return match[0] if match else token


def normalize(text: str) -> str:
    """
    Return a cleaned version of the user's text with typos corrected.

    Punctuation and casing of unmatched words are preserved so that names
    like file paths survive untouched.
    """
    if not text or not text.strip():
        return ""

    vocab = sorted(DOMAIN_VOCAB | set(_app_word_index()) | {a.lower() for a in installed_apps()})
    out: list[str] = []

    for raw in text.split():
        prefix = re.match(r"^\W*", raw).group(0)
        suffix = re.search(r"\W*$", raw).group(0)
        core = raw[len(prefix):len(raw) - len(suffix) or None]

        # Never touch paths, URLs, or anything with digits/slashes.
        if not core or "/" in core or "\\" in core or any(c.isdigit() for c in core):
            out.append(raw)
            continue

        fixed = _correct_token(core.lower(), vocab)
        if fixed != core.lower() and core.isupper():
            fixed = fixed.upper()
        elif fixed != core.lower() and core[:1].isupper():
            fixed = fixed.capitalize()
        elif fixed == core.lower():
            fixed = core

        out.append(prefix + fixed + suffix)

    return " ".join(out)


def resolve_app(name: str) -> str | None:
    """Best-effort match of a spoken/typed app name to an installed app."""
    if not name:
        return None
    query = name.strip().lower()
    lookup = _app_lookup()

    if query in lookup:
        return lookup[query]

    aliases = {
        "chrome": "Google Chrome",
        "vscode": "Visual Studio Code",
        "vs code": "Visual Studio Code",
        "code": "Visual Studio Code",
        "terminal": "Terminal",
        "browser": "Safari",
        "settings": "System Settings",
        "preferences": "System Settings",
        "activity monitor": "Activity Monitor",
        "text editor": "TextEdit",
    }
    if query in aliases and aliases[query].lower() in lookup:
        return lookup[aliases[query].lower()]

    words = _app_word_index()
    if query in words:
        return words[query]

    # Fuzzy match, but only against candidates sharing the first letter —
    # without this guard "chorme" happily matches "Home".
    def _best(pool: list[str]) -> str | None:
        same_initial = [c for c in pool if c[:1] == query[:1]]
        for candidates, cutoff in ((same_initial, 0.72), (pool, 0.88)):
            hit = get_close_matches(query, candidates, n=1, cutoff=cutoff)
            if hit:
                return hit[0]
        return None

    hit = _best(list(words))
    if hit:
        return words[hit]
    hit = _best(list(lookup))
    if hit:
        return lookup[hit]

    # Substring fallback: "photoshop" → "Adobe Photoshop 2024"
    for key, original in lookup.items():
        if query in key:
            return original
    return None


def resolve_folder(name: str) -> Path | None:
    """Match a folder reference to a real directory."""
    if not name:
        return None
    query = re.sub(r"\b(my|the|folder|directory)\b", " ", name.lower()).strip()
    query = re.sub(r"\s+", " ", query)
    if not query:
        return None

    folders = known_folders()
    if query in folders:
        return folders[query]

    match = get_close_matches(query, list(folders), n=1, cutoff=0.75)
    if match:
        return folders[match[0]]

    # Search one level under Home and Desktop for a matching directory.
    for base in (HOME, HOME / "Desktop", HOME / "Documents"):
        try:
            entries = [e for e in base.iterdir() if e.is_dir() and not e.name.startswith(".")]
        except OSError:
            continue
        names = {e.name.lower(): e for e in entries}
        if query in names:
            return names[query]
        near = get_close_matches(query, list(names), n=1, cutoff=0.8)
        if near:
            return names[near[0]]
    return None


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def fuzzy_contains(text: str, phrase: str, cutoff: float = 0.85) -> bool:
    """True if `phrase` appears in `text`, tolerating small typos."""
    words = text.lower().split()
    target = phrase.lower().split()
    if not target or len(words) < len(target):
        return False
    span = len(target)
    for i in range(len(words) - span + 1):
        window = " ".join(words[i:i + span])
        if similarity(window, phrase) >= cutoff:
            return True
    return False
