"""Polished startup UI — demo-ready for screen recording."""

import sys
import time


def _line(icon: str, label: str, value: str = "", ok: bool = True):
    mark = "✓" if ok else "○"
    val = f"  {value}" if value else ""
    print(f"  {mark}  {icon}  {label}{val}")


def print_banner():
    print(r"""
  ╔══════════════════════════════════════════════════════════╗
  ║   D.I.N.E.S.H  ·  Device-Integrated Neural  ·  v3        ║
  ║   Engine for System Handling  ·  Apple Silicon           ║
  ╚══════════════════════════════════════════════════════════╝
""")


def print_system_status(profile, voice: str, full_control: bool):
    mode = "FULL CONTROL" if full_control else "SAFE"
    print(f"  ┌─ System ─────────────────────────────────────────────┐")
    print(f"  │  Voice     {voice:<44}│")
    print(f"  │  Brain     {profile.llm:<44}│")
    print(f"  │  Vision    {profile.vision:<44}│")
    print(f"  │  Whisper   {profile.whisper:<44}│")
    print(f"  │  Hardware  M4 · {profile.ram_gb}GB · {profile.tier} tier{' ' * (28 - len(profile.tier))}│")
    print(f"  │  Mode      {mode:<44}│")
    print(f"  └──────────────────────────────────────────────────────┘")
    print()


def boot_sequence(steps: list[tuple[str, str, str]]):
    """Animated boot lines for reel-friendly startup."""
    for icon, label, detail in steps:
        sys.stdout.write(f"  {icon}  {label}...")
        sys.stdout.flush()
        time.sleep(0.15)
        sys.stdout.write(f"\r  ✓  {label}  {detail}\n")
        sys.stdout.flush()


def print_help():
    print("""
  ┌─ Commands ───────────────────────────────────────────────┐
  │  ENTER              Voice command                        │
  │  live               Always-on conversation (most human)  │
  │  wake               Hey Dinesh wake-word mode            │
  │  agent <task>       Multi-step autonomous mission        │
  │  remember <fact>    Save permanent long-term memory      │
  │  memory             Show what I've learned               │
  │  train              Fine-tune / bake memory into model   │
  │  clear              Reset short-term chat only           │
  │  quit               Shutdown                             │
  └──────────────────────────────────────────────────────────┘

  Try:  live
        remember my name is …
        train
  """)


def print_agent_header(task: str):
    print(f"\n  ╭─ AGENT ──────────────────────────────────────────────╮")
    print(f"  │  {task[:54]:<54}│")
    print(f"  ╰──────────────────────────────────────────────────────╯")


def print_tool_step(step: int, name: str, detail: str):
    d = detail[:70] + "…" if len(detail) > 70 else detail
    print(f"  ⚡ [{step:02d}] {name:<22} {d}")
