# D.I.N.E.S.H

**Device-Integrated Neural Engine for System Handling**

A local, on-device AI assistant for macOS (Apple Silicon). It opens apps, manages files, searches the web, watches your system, listens for **“Hey Dinesh”**, and gets better over time from your corrections — without sending your chat history to a cloud LLM.

Built with [Cursor](https://cursor.com).

---

## What it does

| Capability | Detail |
|---|---|
| **Local LLM** | Ollama + `qwen2.5:7b` (auto-picks `dinesh-learned` after training) |
| **Voice** | Whisper STT · Edge-TTS British neural voice · wake word |
| **Tools** | Open apps/folders/URLs, files, shell, web search, screenshots, GUI |
| **Typo-tolerant NLU** | `opne chorme` → opens Chrome · never “I didn’t understand” |
| **Long-term memory** | SQLite facts, corrections, preferences across restarts |
| **Self-improvement** | `train` rebuilds `dinesh-learned`; optional MLX LoRA |
| **HUD** | Live CPU/RAM/disk/battery console at `http://127.0.0.1:8742` |
| **Eyes mode** | MediaPipe hands + face — wave, fist, pinch, blink, gaze scroll |

---

## Requirements

- macOS on Apple Silicon (M1–M4)
- ~16 GB RAM recommended for `qwen2.5:7b`
- [Homebrew](https://brew.sh) · Python 3.11+ · [Ollama](https://ollama.com)

Grant once in **System Settings → Privacy & Security**:
Microphone, Accessibility, Screen Recording (for the app that runs Dinesh).

---

## Quick start

```bash
git clone https://github.com/YOUR_USER/dinesh.git
cd dinesh
./install.sh
```

**Terminal assistant**

```bash
python3 jarvis.py
# or:  cd jarvis && python3 jarvis.py
```

**HUD (recommended)**

```bash
cd jarvis && python3 server.py
# open http://127.0.0.1:8742
```

---

## Everyday commands

```
open safari
open my downloads folder
what’s the battery
cpu and memory usage
create a folder called Notes on desktop
search for python asyncio
remember my name is Dinesh
memory
train
```

Typos are fine: `opne chorme`, `wat is the time`, `take a screenshto`.

Wake word (HUD **Wake** button or CLI): **Hey Dinesh**.

### Eyes mode (hands + gaze)

Click **Eyes** in the HUD (requires Camera permission). All processing is on-device via MediaPipe.

| Signal | Action |
|---|---|
| Wave / open palm | Start listening |
| Fist | Cancel |
| Thumbs up | Confirm |
| Peace ✌️ | Screenshot |
| Pinch | Mouse click |
| Point | Move cursor |
| Swipe L/R/U/D | Scroll |
| Double blink | Click |
| Look left/right/up/down | Scroll |

Grant **Camera** to Terminal / Cursor in System Settings → Privacy & Security.

---

## How learning works

1. **Immediate** — corrections like “no, call me …” are stored and injected into the system prompt.
2. **Permanent model** — `train` exports chats + memory → rebuilds the local Ollama model `dinesh-learned`.
3. **Optional LoRA** — with `mlx-lm` installed, `train` can fine-tune weights on Apple Silicon.

Your `jarvis_memory.db` and training exports stay on disk and are gitignored.

---

## Project layout

```
jarvis_app/
├── jarvis.py          # launcher
├── install.sh
├── requirements.txt
└── jarvis/
    ├── agent.py       # LLM + tools + memory
    ├── nlu.py         # typo / fuzzy matching
    ├── intent.py      # fast path for simple commands
    ├── server.py      # HUD WebSocket server
    ├── audio.py       # mic, wake word, TTS
    ├── memory/        # SQLite + train pipeline
    ├── tools/         # mac / files / web / vision / …
    ├── hud/           # frontend
    └── tests/         # NLU + intent regressions
```

---

## Tests

```bash
cd jarvis && python3 -m pytest tests/ -q
```

---

## Safety

Default mode is **SAFE** (no unrestricted shell abuse). Set `JARVIS_FULL_CONTROL=1` only if you understand the risk — the model can run shell commands and drive the GUI.

---

## License

MIT — see [LICENSE](LICENSE).

---

## Roadmap ideas (contributions welcome)

- Streaming token replies in the HUD
- Per-app permission prompts before GUI/shell actions
- Plugin folder for community tools
- Optional cloud LLM fallback with a hard local-only switch
- Better multi-turn planning for long workflows
