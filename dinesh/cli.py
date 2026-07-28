#!/usr/bin/env python3
"""
Dinesh v3 — Autonomous Mac Intelligence
Optimized for Apple M4
"""

import sys
import time
import subprocess
import logging
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

try:
    import ollama
    import numpy  # noqa: F401
    import sounddevice  # noqa: F401
    import pyautogui  # noqa: F401
except ImportError as e:
    print(f"\n  ✗  Missing dependency: {e}")
    print("     Run:  python3 main.py setup\n")
    sys.exit(1)

from config import FULL_CONTROL, LLM_MODEL, PROFILE, VISION_MODEL, WHISPER_MODEL
from models import warm_models, warn_if_weak
from permissions import startup_checks
from audio import (
    pick_voice, preload_whisper_background, get_whisper_model,
    record_until_silence, transcribe, speak, listen_for_wake_word,
)
from agent import DineshAgent
from ui import print_banner, print_system_status, print_help, print_agent_header, boot_sequence
from memory.store import list_memory, remember_fact, stats as memory_stats
from memory.trainer import full_train_cycle


def ensure_ollama() -> bool:
    try:
        ollama.list()
        return True
    except Exception:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(6):
            time.sleep(1)
            try:
                ollama.list()
                return True
            except Exception:
                continue
        return False


def main():
    print_banner()
    voice = pick_voice()

    if not ensure_ollama():
        print("  ✗  Ollama not running. Run: bash install.sh\n")
        sys.exit(1)

    # Parallel warm-up while showing status
    threading.Thread(target=lambda: warm_models(PROFILE), daemon=True).start()
    preload_whisper_background()

    boot_sequence([
        ("🧠", "Neural engine", LLM_MODEL),
        ("👁", "Vision system", VISION_MODEL),
        ("🎤", "Voice pipeline", f"Whisper {WHISPER_MODEL}"),
        ("🖥", "Control surface", "45 tools loaded"),
        ("🔒", "Permissions", "awaiting your grant"),
    ])

    print_system_status(PROFILE, voice, FULL_CONTROL)
    warn_if_weak(PROFILE)
    startup_checks()
    print_help()

    speak("All systems online. Dinesh at your service, sir.", voice, wait=True)
    agent = DineshAgent()

    while True:
        try:
            cmd = input("  dinesh › ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Shutting down.\n")
            speak("Goodbye, sir.", voice, wait=True)
            break

        low = cmd.lower()
        if low in ("quit", "exit", "shutdown", "bye", "q"):
            speak("Goodbye, sir.", voice, wait=True)
            break

        if low == "clear":
            agent.clear_memory()
            print("  ✓  Short-term chat cleared (long-term memory kept).\n")
            continue

        if low == "memory" or low == "mem":
            print(f"\n  {list_memory()}\n")
            continue

        if low.startswith("remember "):
            fact = cmd[9:].strip()
            if not fact:
                print("  Usage: remember <fact>\n")
                continue
            msg = remember_fact(fact, source="cli")
            agent.refresh_memory_prompt()
            print(f"  🧠  {msg}\n")
            speak("Committed to long-term memory, sir.", voice)
            continue

        if low == "train":
            print("  🧠  Training cycle — exporting chats, baking dinesh-learned, optional LoRA…\n")
            speak("Beginning permanent training cycle.", voice)
            result = full_train_cycle()
            agent.refresh_memory_prompt()
            print(f"  ✓  {result}\n")
            speak("Training complete. I will remember.", voice)
            continue

        if low == "status":
            print_system_status(PROFILE, voice, FULL_CONTROL)
            s = memory_stats()
            print(
                f"  Memory   {s['facts']} facts · {s['corrections']} corrections · "
                f"{s['turns']} turns\n"
            )
            continue

        if low.startswith("agent "):
            task = cmd[6:].strip()
            if not task:
                print("  Usage: agent <task>\n")
                continue
            print_agent_header(task)
            speak("Understood, sir.", voice)
            response = agent.chat(task)
            print(f"\n  🤖  {response}\n")
            speak(response, voice)
            continue

        if low == "live":
            print("  🟢  Live mode — talk freely. Ctrl+C or say 'goodbye' to stop.\n")
            speak("I'm here, sir. Go ahead.", voice)
            while True:
                try:
                    print("  🎤  Listening...", end="", flush=True)
                    audio = record_until_silence()
                    user_input = transcribe(audio, get_whisper_model())
                    print(f"\r  You: {user_input:<58}")
                    if len(user_input) < 2:
                        print("  (didn't catch that — try again)\n")
                        continue
                    if any(w in user_input.lower() for w in ["goodbye", "stop listening", "go to sleep", "shut down"]):
                        speak("Standing by. Goodbye, sir.", voice)
                        break
                    response = agent.chat(user_input)
                    print(f"  🤖  {response}\n")
                    speak(response, voice, wait=True)
                except KeyboardInterrupt:
                    print("\n  Live mode paused.\n")
                    speak("Standing by.", voice)
                    break
            continue

        if low == "wake":
            print("  🟢  Wake word active — say 'Hey Dinesh'\n")
            speak("Wake word activated. Call me when you need me.", voice)
            while True:
                try:
                    user_input = listen_for_wake_word(voice)
                    if not user_input:
                        continue
                    print(f"  You: {user_input}")
                    if any(w in user_input.lower() for w in ["goodbye", "stop listening", "exit"]):
                        speak("Wake word deactivated.", voice)
                        break
                    response = agent.chat(user_input)
                    print(f"  🤖  {response}\n")
                    speak(response, voice, wait=True)
                except KeyboardInterrupt:
                    break
            continue

        if cmd == "":
            print("  🎤  Listening...", end="", flush=True)
            audio = record_until_silence()
            user_input = transcribe(audio, get_whisper_model())
            print(f"\r  You: {user_input:<58}")
            if len(user_input) < 2:
                print("  (no speech detected)\n")
                continue
        else:
            user_input = cmd

        response = agent.chat(user_input)
        print(f"  🤖  {response}\n")
        speak(response, voice)


if __name__ == "__main__":
    main()
