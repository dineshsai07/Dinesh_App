"""Smart model selection — tuned for Mac M4 16GB."""

import os
import subprocess
from dataclasses import dataclass

import ollama

# Priority lists (first match wins).
# Ordered by function-calling reliability, not raw size — small models that
# cannot emit proper tool_calls make the agent useless.
LLM_PRIORITY = [
    "dinesh-learned",     # permanently improved local model
    "jarvis-learned",     # legacy name (if already trained)
    "qwen2.5:7b",
    "llama3.1:8b",
    "qwen2.5:3b",
    "qwen3:4b",
    "llama3.2",
    "gemma3:4b",
    "mistral",
    "phi3",
]

# Shown at startup when a weak tool-calling model is selected
RECOMMENDED_LLM = "qwen2.5:7b"
WEAK_TOOL_MODELS = {"llama3.2", "gemma3", "phi3", "moondream"}

VISION_PRIORITY = [
    "moondream",          # ~1.8GB — best for 16GB Macs
    "gemma3:4b",          # already installed, multimodal
    "llava:7b",
    "llama3.2-vision",
    "bakllava",
]

WHISPER_BY_RAM = {
    8: "tiny",
    16: "base",
    32: "small",
}


@dataclass
class ModelProfile:
    llm: str
    vision: str
    whisper: str
    ram_gb: int
    tier: str  # lite | standard | pro


def _ram_gb() -> int:
    try:
        out = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True)
        return max(8, int(out.stdout.strip()) // (1024 ** 3))
    except Exception:
        return 16


def _installed_models() -> set[str]:
    try:
        resp = ollama.list()
        models = getattr(resp, "models", None)
        if models is None and isinstance(resp, dict):
            models = resp.get("models", [])
        names: set[str] = set()
        for m in models or []:
            name = getattr(m, "model", None) or getattr(m, "name", None)
            if not name and isinstance(m, dict):
                name = m.get("model") or m.get("name") or ""
            if not name:
                continue
            names.add(name)
            if ":" in name:
                names.add(name.split(":")[0])
        return names
    except Exception:
        return set()


def _pick(candidates: list[str], installed: set[str]) -> str | None:
    for c in candidates:
        if c in installed:
            return c
        base = c.split(":")[0]
        # Prefer exact tag match first (qwen2.5:7b over bare qwen2.5)
        for inst in installed:
            if inst == c:
                return inst
        for inst in installed:
            if inst == base or inst.startswith(base + ":"):
                return inst
    return None


def _env_first(*keys: str) -> str | None:
    for key in keys:
        if key in os.environ and os.environ[key]:
            return os.environ[key]
    return None


def detect_profile() -> ModelProfile:
    ram = _ram_gb()
    installed = _installed_models()

    llm = (
        _env_first("DINESH_MODEL", "JARVIS_MODEL")
        or _pick(LLM_PRIORITY, installed)
        or RECOMMENDED_LLM
    )
    vision = (
        _env_first("DINESH_VISION_MODEL", "JARVIS_VISION_MODEL")
        or _pick(VISION_PRIORITY, installed)
        or "moondream"
    )
    whisper = (
        _env_first("DINESH_WHISPER", "JARVIS_WHISPER")
        or WHISPER_BY_RAM.get(ram, "base")
    )

    if ram <= 16:
        tier = "lite"
    elif ram <= 24:
        tier = "standard"
    else:
        tier = "pro"

    return ModelProfile(llm=llm, vision=vision, whisper=whisper, ram_gb=ram, tier=tier)



def is_weak_tool_model(name: str) -> bool:
    base = name.split(":")[0]
    return base in WEAK_TOOL_MODELS


def warn_if_weak(profile: ModelProfile):
    if not is_weak_tool_model(profile.llm):
        return
    print(f"  ⚠  '{profile.llm}' is unreliable at tool calling.")
    print(f"     For a much smarter Dinesh:  ollama pull {RECOMMENDED_LLM}\n")


def warm_models(profile: ModelProfile):
    """Pre-load LLM into memory for faster first response."""
    try:
        ollama.chat(
            model=profile.llm,
            messages=[{"role": "user", "content": "ping"}],
            options={"num_predict": 1},
        )
    except Exception:
        pass
