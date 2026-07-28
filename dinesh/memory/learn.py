"""Extract facts and corrections from live conversation."""

from __future__ import annotations

import re

from memory.store import remember_correction, remember_fact, remember_preference, add_episode

_CORRECTION_CUES = (
    "no,", "no ", "wrong", "that's wrong", "that is wrong", "incorrect",
    "i meant", "i mean", "actually", "don't do that", "do not", "never do",
    "stop saying", "not what i", "you misunderstood", "fix:",
)

_FACT_CUES = (
    "remember that", "remember this", "my name is", "i am ", "i'm ",
    "i prefer", "always ", "never call me", "call me ",
)


def maybe_learn_from_user(user_text: str, last_assistant: str = "") -> list[str]:
    """Detect corrections / explicit memories in user speech. Returns notes."""
    notes: list[str] = []
    low = user_text.lower().strip()
    if not low:
        return notes

    # Explicit remember
    m = re.search(r"remember(?:\s+that|\s+this)?[:\s]+(.+)$", user_text, re.I)
    if m:
        notes.append(remember_fact(m.group(1).strip(), source="explicit"))

    # Name / preference
    m = re.search(r"(?:my name is|call me)\s+([A-Za-z0-9 .'\-]{2,40})", user_text, re.I)
    if m:
        name = m.group(1).strip().rstrip(".")
        notes.append(remember_preference("user_name", name))
        notes.append(remember_fact(f"User's name is {name}", key="name", source="explicit"))

    m = re.search(r"i prefer\s+(.+)$", user_text, re.I)
    if m:
        notes.append(remember_preference("general", m.group(1).strip().rstrip(".")))

    # Correction against last reply
    if last_assistant and any(c in low for c in _CORRECTION_CUES):
        # Strip leading cue for the "right" version
        right = re.sub(
            r"^(no[,.]?\s*|wrong[,.]?\s*|actually[,.]?\s*|i meant\s+|i mean\s+)",
            "",
            user_text,
            flags=re.I,
        ).strip()
        if len(right) > 3:
            notes.append(remember_correction(last_assistant[:400], right[:400], context=user_text[:200]))

    return notes


def summarize_episode(user: str, assistant: str):
    if len(user) < 8 or len(assistant) < 8:
        return
    add_episode(f"User asked about '{user[:80]}' → Dinesh: '{assistant[:120]}'")
