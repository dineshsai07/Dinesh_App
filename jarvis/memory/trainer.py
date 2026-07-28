"""
Self-improvement / fine-tune pipeline for qwen2.5:7b on Apple Silicon.

Two layers of permanent learning:
1) Instant: rebuild Ollama model `dinesh-learned` with SYSTEM = prompt + memory
2) Deep: LoRA fine-tune via MLX when mlx-lm is installed (optional, heavier)
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from config import SYSTEM_PROMPT
from models import RECOMMENDED_LLM
from memory.store import TRAIN_DIR, export_training_jsonl, memory_block, stats


def _base_model() -> str:
    """Always bake from the stock base — never FROM a learned model (avoids nesting)."""
    return os.environ.get("JARVIS_BASE_MODEL") or RECOMMENDED_LLM


def rebuild_ollama_learned_model() -> str:
    """
    Create/update Ollama model `dinesh-learned` from base + long-term memory.
    This permanently changes behaviour across restarts without GPU fine-tuning.
    """
    TRAIN_DIR.mkdir(parents=True, exist_ok=True)
    mem = memory_block(3500)
    system = SYSTEM_PROMPT + "\n\n" + mem
    safe = system.replace('"""', "'''")
    base = _base_model()
    modelfile = TRAIN_DIR / "Modelfile.dinesh-learned"
    modelfile.write_text(
        f'FROM {base}\n'
        f'PARAMETER temperature 0.55\n'
        f'PARAMETER num_ctx 4096\n'
        f'SYSTEM """{safe}"""\n',
        encoding="utf-8",
    )
    try:
        r = subprocess.run(
            ["ollama", "create", "dinesh-learned", "-f", str(modelfile)],
            capture_output=True, text=True, timeout=600,
        )
        if r.returncode != 0:
            return f"Failed to create dinesh-learned: {r.stderr or r.stdout}"
        return (
            "Permanent model updated: dinesh-learned. "
            "Dinesh will prefer it on next launch (or immediately after train). "
            f"Memory baked in ({stats()['facts']} facts, {stats()['corrections']} corrections)."
        )
    except Exception as e:
        return f"Could not create dinesh-learned: {e}"


def export_dataset() -> str:
    path = export_training_jsonl()
    n = sum(1 for _ in path.open())
    return f"Training dataset exported: {path} ({n} examples)."


def run_lora_finetune(iters: int = 200) -> str:
    """
    Fine-tune with MLX LoRA on Apple Silicon.
    Requires: pip install mlx-lm
    Uses a 4-bit Qwen2.5-7B Instruct suitable for 16GB unified memory.
    """
    try:
        import mlx_lm  # noqa: F401
    except ImportError:
        return (
            "MLX not installed. Long-term memory + dinesh-learned still work. "
            "For weight fine-tuning run: pip3 install mlx-lm --break-system-packages"
        )

    dataset = export_training_jsonl()
    n = sum(1 for _ in dataset.open())
    if n < 8:
        return (
            f"Need more conversation data to fine-tune (have {n} examples, want ≥8). "
            "Keep chatting, correcting me, and saying 'remember that…', then run train again."
        )

    mlx_data = TRAIN_DIR / "mlx_train.jsonl"
    with dataset.open() as src, mlx_data.open("w") as dst:
        for line in src:
            obj = json.loads(line)
            msgs = obj.get("messages") or []
            text_parts = []
            for m in msgs:
                role = m.get("role", "")
                content = m.get("content", "")
                text_parts.append(f"<|{role}|>\n{content}")
            dst.write(json.dumps({"text": "\n".join(text_parts)}) + "\n")

    adapter_dir = TRAIN_DIR / "lora_adapters"
    adapter_dir.mkdir(exist_ok=True)
    base = "mlx-community/Qwen2.5-7B-Instruct-4bit"
    train_split = TRAIN_DIR / "train.jsonl"
    valid_split = TRAIN_DIR / "valid.jsonl"
    lines = mlx_data.read_text().strip().splitlines()
    split = max(1, int(len(lines) * 0.9))
    train_split.write_text("\n".join(lines[:split]) + "\n")
    valid_split.write_text("\n".join(lines[split:] or lines[:1]) + "\n")

    cmd = [
        "python3", "-m", "mlx_lm", "lora",
        "--model", base,
        "--train",
        "--data", str(TRAIN_DIR),
        "--adapter-path", str(adapter_dir),
        "--fine-tune-type", "lora",
        "--batch-size", "1",
        "--num-layers", "8",
        "--iters", str(iters),
        "--learning-rate", "1e-5",
        "--max-seq-length", "1024",
        "--grad-checkpoint",
    ]

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
        log = TRAIN_DIR / "lora_last.log"
        log.write_text((r.stdout or "") + "\n" + (r.stderr or ""))
        if r.returncode != 0:
            return (
                f"LoRA training failed (see {log}). "
                "Memory model dinesh-learned is still updated. "
                f"Error tail: {(r.stderr or r.stdout)[-400:]}"
            )
        return (
            f"LoRA fine-tune complete. Adapters at {adapter_dir}. "
            "Daily use stays on dinesh-learned via Ollama; adapters are for MLX experiments."
        )
    except subprocess.TimeoutExpired:
        return "LoRA training timed out. Try fewer iters or keep using dinesh-learned."
    except Exception as e:
        return f"LoRA training error: {e}"


def activate_learned_model() -> None:
    """Switch this process to dinesh-learned immediately after training."""
    import config as cfg
    cfg.LLM_MODEL = "dinesh-learned"


def full_train_cycle() -> str:
    """Export data → rebuild Ollama learned model → attempt LoRA."""
    parts = [export_dataset(), rebuild_ollama_learned_model()]
    activate_learned_model()
    parts.append(run_lora_finetune(iters=100))
    return " | ".join(parts)
