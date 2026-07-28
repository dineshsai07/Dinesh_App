# D.I.N.E.S.H

### Device-Integrated Neural Engine for System Handling

**A local, on-device AI control system for macOS (Apple Silicon)**

D.I.N.E.S.H is a personal neural engine that runs entirely on your Mac. It listens, understands imperfect speech and typing, reasons with a local language model, and **acts on the machine**—opening applications, managing files, searching the web, controlling the interface, and improving from your corrections over time.

| | |
|---|---|
| **Product** | D.I.N.E.S.H (Device-Integrated Neural Engine for System Handling) |
| **Author** | Dinesh Sai |
| **Built with** | [Cursor](https://cursor.com) and modern AI-assisted development |
| **Runtime** | macOS · Apple Silicon · Python · Ollama |
| **License** | MIT |

---

## 1. Executive summary

Most assistants answer questions in a browser tab. D.I.N.E.S.H is designed as a **system-handling engine**: neural models provide perception and reasoning; a tool runtime turns that into concrete actions on the device.

It was conceived, designed, and implemented as a **Cursor-native engineering project**—iterating from a local assistant prototype into a packaged product with:

- A cinematic **HUD** (heads-up display) for live control and telemetry  
- A **CLI** for terminal workflows  
- **Voice** (wake word, speech-to-text, neural TTS)  
- **Vision control** (hand gestures and gaze)  
- **Long-term memory** and optional **local model improvement**  
- A **portable installer** so any Apple Silicon Mac can set itself up without hardcoded personal paths  

Privacy is foundational: chat, memory, and model inference stay on-device by default. Nothing is required to leave the machine for core operation.

---

## 2. How D.I.N.E.S.H was created

### 2.1 Origin

D.I.N.E.S.H began as a personal initiative by **Dinesh Sai** to build a capable Mac assistant that felt intentional—not a thin wrapper around a cloud chat API. The goal was a system that could:

1. Run **locally** on Apple Silicon  
2. **Control the Mac** through real tools (not only text replies)  
3. Tolerate **messy human input** (typos, voice noise)  
4. **Remember** preferences and corrections across restarts  
5. Be **shareable**: cloneable, installable, and usable on other Macs  

### 2.2 Development method

The product was developed primarily inside **Cursor**, using AI pair-programming as an engineering accelerator—architecture drafts, implementation, debugging, UI iteration, test coverage, and packaging—while product decisions, naming, and acceptance criteria remained human-directed.

The build path roughly followed:

| Phase | Focus | Outcome |
|---|---|---|
| **Foundation** | Local LLM + tool calling | Agent that can open apps, run commands, use files/web |
| **Voice & presence** | Whisper, TTS, wake word | Hands-free “Hey Dinesh” interaction |
| **Interface** | FastAPI WebSocket HUD | Live status, telemetry, streaming replies |
| **Robustness** | NLU + intent routing | Typos and short commands resolve without “I don’t understand” |
| **Memory** | SQLite + train pipeline | Persistent facts; optional `dinesh-learned` model |
| **Perception** | MediaPipe camera stack | Gesture and gaze actions (“Eyes” mode) |
| **Distribution** | `main.py` portable setup | Any Mac: setup → start, no author machine paths |

### 2.3 Naming

**D.I.N.E.S.H** expands to **Device-Integrated Neural Engine for System Handling**.

- **Device-integrated** — built for *this* Mac (paths, apps, mic, camera, accessibility).  
- **Neural** — local neural models for language, speech, vision, and gesture.  
- **Engine** — not chat-only; it executes tools and drives system actions.  
- **System Handling** — the product job: operate and assist across the OS surface.

Informally, it may be described as a **neural engine**. Formally, the product name remains **D.I.N.E.S.H**.

---

## 3. What it does

| Domain | Capability |
|---|---|
| **Reasoning** | Local LLM via Ollama (`qwen2.5:7b` recommended; prefers `dinesh-learned` after training) |
| **Understanding** | Typo-tolerant NLU; fast intent path for common one-shot commands |
| **Voice** | Wake word, Whisper STT, Edge-TTS speech |
| **Action** | Apps, folders, URLs, files, shell, web search, screenshots, GUI automation |
| **Sight** | Screen vision tools; optional camera gestures and gaze (“Eyes”) |
| **Memory** | SQLite long-term facts, corrections, preferences |
| **Improvement** | `train` rebuilds a local Ollama model; optional MLX LoRA on Apple Silicon |
| **Operations** | HUD with live CPU/RAM/disk/battery; LaunchAgent background service |

---

## 4. Architecture (high level)

```
┌─────────────────────────────────────────────────────────────┐
│                     Interfaces                              │
│   HUD (browser)  ·  CLI  ·  Wake word  ·  Eyes (camera)     │
└─────────────┬───────────────────────────────┬───────────────┘
              │ WebSocket / events            │
┌─────────────▼───────────────────────────────▼───────────────┐
│                   server.py  (FastAPI)                      │
│         status · telemetry · streaming · permissions        │
└─────────────┬───────────────────────────────────────────────┘
              │
┌─────────────▼───────────────────────────────────────────────┐
│                      agent.py                               │
│     NLU normalize → intent fast-path → LLM + tools          │
└──────┬───────────────┬──────────────────┬───────────────────┘
       │               │                  │
┌──────▼──────┐ ┌──────▼──────┐   ┌───────▼────────┐
│  Ollama LLM │ │ Tool layer  │   │ memory/ (SQLite│
│  + optional │ │ mac/files/  │   │ learn + train) │
│  learned    │ │ web/gui/…   │   └────────────────┘
└─────────────┘ └─────────────┘
```

**Request flow (simplified)**

1. User input arrives (text, voice transcript, or gesture-mapped action).  
2. **NLU** repairs common typos and resolves apps/folders when possible.  
3. **Intent router** handles unambiguous commands without an LLM round-trip.  
4. Otherwise the **agent** calls the local model with tools, streams tokens to the HUD, and speaks the reply.  
5. **Memory** may store facts/corrections; `train` can bake them into `dinesh-learned`.

---

## 5. Repository layout

```
.
├── main.py                  # Enterprise entry: setup | start | stop | hud | cli | status
├── install.sh               # Alias → main.py setup
├── start_dinesh.command     # Double-click start (setup on first run)
├── stop_dinesh.command      # Stop background HUD
├── requirements.txt
├── LICENSE                  # MIT
├── ROADMAP.md               # Forward plan
└── dinesh/                  # Application package
    ├── agent.py             # Multi-step agent + streaming
    ├── nlu.py               # Typo / fuzzy understanding
    ├── intent.py            # Fast path for simple commands
    ├── server.py            # HUD WebSocket server
    ├── cli.py               # Terminal assistant
    ├── audio.py             # Mic, wake word, TTS
    ├── config.py            # Prompt, limits, env (DINESH_*)
    ├── models.py            # Auto model selection by RAM / Ollama
    ├── permissions.py       # Mic / camera / accessibility checks
    ├── memory/              # SQLite store, learning, trainer
    ├── tools/               # System capabilities
    ├── vision/              # Gesture + gaze controller
    ├── hud/                 # Frontend (HTML / CSS / JS)
    └── tests/               # Regression tests (NLU, intent, vision)
```

Personal artefacts (memory databases, training exports, LoRA adapters, vision `.task` models) are **gitignored** and created on each machine during setup or use.

---

## 6. Getting started

### 6.1 Prerequisites

- macOS on **Apple Silicon** (M1–M4 recommended)  
- Approximately **16 GB RAM** for comfortable `qwen2.5:7b` use  
- Network access for **first-time** setup only (Homebrew, Ollama models, Python packages, MediaPipe models)

### 6.2 Install and run

```bash
git clone https://github.com/YOUR_USER/dinesh.git
cd dinesh
python3 main.py setup
python3 main.py start
```

Open: [http://127.0.0.1:8742](http://127.0.0.1:8742)

Alternatively, double-click **`start_dinesh.command`**.

### 6.3 Operator commands

| Command | Purpose |
|---|---|
| `python3 main.py setup` | Install system deps, Ollama models, project `.venv`, vision models |
| `python3 main.py start` | Start HUD as a background LaunchAgent (survives terminal close) |
| `python3 main.py stop` | Stop the background HUD |
| `python3 main.py hud` | Run HUD in the foreground (debugging) |
| `python3 main.py cli` | Terminal assistant |
| `python3 main.py status` | Health and install path |

### 6.4 Permissions (one-time)

In **System Settings → Privacy & Security**, enable for **Terminal** (or the app that launches D.I.N.E.S.H):

| Permission | Used for |
|---|---|
| Microphone | Voice, wake word |
| Camera | Eyes mode (gestures / gaze) |
| Accessibility | Mouse / keyboard automation |
| Screen Recording | Screenshots / screen vision |

---

## 7. Everyday use

```
open safari
open my downloads folder
what’s the battery
cpu and memory usage
remember my name is …
memory
train
```

Typing noise is expected. Examples that should still work: `opne chorme`, `wat is the time`, `take a screenshto`.

| Control | How |
|---|---|
| **Wake** | HUD **Wake** → say **“Hey Dinesh”** |
| **Eyes** | HUD **Eyes** → allow Camera; wave, fist, pinch, blink, etc. |
| **Speak** | Space / Speak button / center core |
| **Cancel** | Esc |

---

## 8. Why this qualifies as a “neural engine”

| Term | Justification in this product |
|---|---|
| **Neural** | Local neural models: LLM (Ollama), speech (Whisper), TTS, MediaPipe hands/face, optional screen vision |
| **Engine** | Deterministic tool runtime that **executes** on the OS—not answers alone |
| **Device-integrated** | Bound to the host Mac’s apps, filesystem, audio, camera, and accessibility stack |

Honest positioning: D.I.N.E.S.H does **not** claim a custom silicon neural processor. It claims a **software neural engine**—neural models plus an action engine—integrated with the device.

---

## 9. Privacy, safety, and portability

### Privacy

- Inference and memory are **local by default**.  
- Long-term memory and training data remain on disk and are excluded from git.  
- Camera and microphone are used only when those features are enabled.

### Safety

- Default mode is **SAFE** (destructive operations restricted).  
- Full control (unrestricted shell/GUI risk): `DINESH_FULL_CONTROL=1`  
- Legacy `JARVIS_*` environment variables are accepted as fallbacks where applicable.

### Portability

- No author-machine absolute paths are committed.  
- LaunchAgent plists are **generated per install** from the clone location.  
- Python dependencies install into a project **`.venv`**.

---

## 10. Technology stack

| Layer | Choices |
|---|---|
| Language | Python 3.11+ |
| Local LLM | Ollama (`qwen2.5:7b`, `dinesh-learned`, …) |
| HUD API | FastAPI · WebSockets · Uvicorn |
| Frontend | HTML / CSS / Canvas JS |
| Speech | openai-whisper · edge-tts · sounddevice |
| Vision / Eyes | MediaPipe · OpenCV |
| Memory | SQLite |
| Optional fine-tune | mlx-lm (Apple Silicon LoRA) |
| Packaging | `main.py` + macOS LaunchAgent |

---

## 11. Testing

```bash
python3 main.py setup          # once
source .venv/bin/activate
cd dinesh && python -m pytest tests/ -q
```

Current automated coverage focuses on **NLU / intent routing** and **gesture / gaze classifiers** (camera-free unit tests).

---

## 12. Configuration (selected)

| Variable | Effect |
|---|---|
| `DINESH_MODEL` | Force LLM name |
| `DINESH_VISION_MODEL` | Force vision model |
| `DINESH_WHISPER` | Whisper size (`tiny` / `base` / `small`) |
| `DINESH_FULL_CONTROL` | `1` enables higher-risk tools |
| `DINESH_TTS_VOICE` | Edge-TTS voice id |
| `DINESH_MAX_STEPS` | Agent step budget |

---

## 13. Roadmap

Near-term product priorities (detail in [`ROADMAP.md`](ROADMAP.md)):

- Non-blocking speech so new commands are not held while TTS plays  
- Model warm-start to reduce cold first-token latency  
- Stronger planning / verification for multi-step and risky actions  
- Plugin surface for community tools  

---

## 14. Attribution

D.I.N.E.S.H was created by **Dinesh Sai**, engineered with **Cursor** and AI-assisted development, and released under the **MIT License** for study, use, and extension.

> Built to demonstrate that a serious local assistant—perception, reasoning, memory, and system control—can be designed and shipped as a coherent product, not only as a chat demo.

---

## 15. License

Copyright © 2026 Dinesh Sai  

Released under the [MIT License](LICENSE).
