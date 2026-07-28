"""Persistent long-term memory — survives restarts."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from config import APP_DIR

DB_PATH = APP_DIR / "memory" / "dinesh_memory.db"
TRAIN_DIR = APP_DIR / "memory" / "training"

# Migrate legacy DB name if present
_LEGACY_DB = APP_DIR / "memory" / "jarvis_memory.db"
if not DB_PATH.exists() and _LEGACY_DB.exists():
    try:
        _LEGACY_DB.rename(DB_PATH)
        for suffix in ("-wal", "-shm"):
            old = Path(str(_LEGACY_DB) + suffix)
            new = Path(str(DB_PATH) + suffix)
            if old.exists() and not new.exists():
                old.rename(new)
    except OSError:
        pass


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRAIN_DIR.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c


def init_db():
    with _conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY,
                key TEXT,
                value TEXT NOT NULL,
                source TEXT DEFAULT 'chat',
                created_at REAL,
                updated_at REAL
            );
            CREATE TABLE IF NOT EXISTS corrections (
                id INTEGER PRIMARY KEY,
                wrong TEXT NOT NULL,
                right TEXT NOT NULL,
                context TEXT,
                created_at REAL
            );
            CREATE TABLE IF NOT EXISTS preferences (
                id INTEGER PRIMARY KEY,
                key TEXT UNIQUE,
                value TEXT NOT NULL,
                created_at REAL,
                updated_at REAL
            );
            CREATE TABLE IF NOT EXISTS turns (
                id INTEGER PRIMARY KEY,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                meta TEXT,
                created_at REAL
            );
            CREATE TABLE IF NOT EXISTS episodes (
                id INTEGER PRIMARY KEY,
                summary TEXT NOT NULL,
                created_at REAL
            );
            """
        )


def remember_fact(value: str, key: str = "", source: str = "chat") -> str:
    init_db()
    now = time.time()
    with _conn() as c:
        c.execute(
            "INSERT INTO facts(key, value, source, created_at, updated_at) VALUES (?,?,?,?,?)",
            (key or "note", value.strip(), source, now, now),
        )
    return f"Committed to long-term memory: {value.strip()[:120]}"


def remember_preference(key: str, value: str) -> str:
    init_db()
    now = time.time()
    with _conn() as c:
        c.execute(
            """
            INSERT INTO preferences(key, value, created_at, updated_at) VALUES (?,?,?,?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
            """,
            (key.strip(), value.strip(), now, now),
        )
    return f"Preference saved: {key} = {value}"


def remember_correction(wrong: str, right: str, context: str = "") -> str:
    init_db()
    with _conn() as c:
        c.execute(
            "INSERT INTO corrections(wrong, right, context, created_at) VALUES (?,?,?,?)",
            (wrong.strip(), right.strip(), context.strip(), time.time()),
        )
    return "Correction stored. I will not repeat that mistake."


def log_turn(role: str, content: str, meta: dict | None = None):
    init_db()
    with _conn() as c:
        c.execute(
            "INSERT INTO turns(role, content, meta, created_at) VALUES (?,?,?,?)",
            (role, content, json.dumps(meta or {}), time.time()),
        )


def add_episode(summary: str):
    init_db()
    with _conn() as c:
        c.execute(
            "INSERT INTO episodes(summary, created_at) VALUES (?,?)",
            (summary.strip(), time.time()),
        )


def stats() -> dict[str, Any]:
    init_db()
    with _conn() as c:
        return {
            "facts": c.execute("SELECT COUNT(*) FROM facts").fetchone()[0],
            "corrections": c.execute("SELECT COUNT(*) FROM corrections").fetchone()[0],
            "preferences": c.execute("SELECT COUNT(*) FROM preferences").fetchone()[0],
            "turns": c.execute("SELECT COUNT(*) FROM turns").fetchone()[0],
            "episodes": c.execute("SELECT COUNT(*) FROM episodes").fetchone()[0],
            "db": str(DB_PATH),
        }


def memory_block(max_chars: int = 2500) -> str:
    """Text injected into the system prompt every session."""
    init_db()
    parts: list[str] = ["LONG-TERM MEMORY (permanent — obey these):"]
    with _conn() as c:
        prefs = c.execute(
            "SELECT key, value FROM preferences ORDER BY updated_at DESC LIMIT 20"
        ).fetchall()
        if prefs:
            parts.append("Preferences:")
            for r in prefs:
                parts.append(f"- {r['key']}: {r['value']}")

        corr = c.execute(
            "SELECT wrong, right FROM corrections ORDER BY id DESC LIMIT 15"
        ).fetchall()
        if corr:
            parts.append("Corrections (never repeat the wrong behaviour):")
            for r in corr:
                parts.append(f"- Wrong: {r['wrong'][:120]} → Right: {r['right'][:160]}")

        facts = c.execute(
            "SELECT value FROM facts ORDER BY id DESC LIMIT 25"
        ).fetchall()
        if facts:
            parts.append("Known facts:")
            for r in facts:
                parts.append(f"- {r['value'][:200]}")

        eps = c.execute(
            "SELECT summary FROM episodes ORDER BY id DESC LIMIT 8"
        ).fetchall()
        if eps:
            parts.append("Recent episode summaries:")
            for r in eps:
                parts.append(f"- {r['summary'][:200]}")

    if len(parts) == 1:
        return "LONG-TERM MEMORY: empty so far. Learn from this user over time."

    text = "\n".join(parts)
    return text[:max_chars]


def export_training_jsonl(path: Path | None = None) -> Path:
    """Export chat turns as supervised fine-tune JSONL (sharegpt-style)."""
    init_db()
    out = path or (TRAIN_DIR / "dataset.jsonl")
    with _conn() as c:
        rows = c.execute(
            "SELECT role, content FROM turns ORDER BY id ASC"
        ).fetchall()

    pairs: list[dict] = []
    buf: list[dict] = []
    for r in rows:
        buf.append({"role": r["role"], "content": r["content"]})
        if r["role"] == "assistant" and len(buf) >= 2:
            # keep last user+assistant (+ optional prior context)
            window = buf[-6:]
            pairs.append({"messages": window})

    # Also bake corrections as explicit training pairs
    with _conn() as c:
        for r in c.execute("SELECT wrong, right, context FROM corrections").fetchall():
            pairs.append({
                "messages": [
                    {"role": "user", "content": r["context"] or "Continue."},
                    {"role": "assistant", "content": r["wrong"]},
                    {"role": "user", "content": f"That was wrong. Correct approach: {r['right']}"},
                    {"role": "assistant", "content": r["right"]},
                ]
            })

    with out.open("w") as f:
        for p in pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    return out


def list_memory(limit: int = 20) -> str:
    init_db()
    s = stats()
    lines = [
        f"Memory DB: {s['facts']} facts, {s['corrections']} corrections, "
        f"{s['preferences']} prefs, {s['turns']} turns, {s['episodes']} episodes."
    ]
    with _conn() as c:
        for r in c.execute("SELECT value FROM facts ORDER BY id DESC LIMIT ?", (limit,)):
            lines.append(f"• {r['value'][:140]}")
        for r in c.execute(
            "SELECT wrong, right FROM corrections ORDER BY id DESC LIMIT 8"
        ):
            lines.append(f"✗→✓ {r['wrong'][:60]} ⇒ {r['right'][:80]}")
    return "\n".join(lines)
