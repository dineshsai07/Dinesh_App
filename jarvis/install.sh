#!/bin/bash
# ============================================================
#   Dinesh v3 — Optimized for Mac M4 (16GB)
#   Built with Cursor
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RAM_GB=$(sysctl -n hw.memsize 2>/dev/null | awk '{printf "%d", $1/1024/1024/1024}')
RAM_GB=${RAM_GB:-16}

echo ""
echo "  ╔══════════════════════════════════════════════════════╗"
echo "  ║   Dinesh Setup  ·  Mac M4  ·  Built with Cursor       ║"
echo "  ╚══════════════════════════════════════════════════════╝"
echo ""
echo "  Detected: ${RAM_GB}GB RAM"

# ── Homebrew ─────────────────────────────────────────────────
if ! command -v brew &>/dev/null; then
    echo "  📦 Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    eval "$(/opt/homebrew/bin/brew shellenv)"
    echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
else
    echo "  ✓  Homebrew"
    eval "$(/opt/homebrew/bin/brew shellenv)" 2>/dev/null || true
fi

# ── System deps ──────────────────────────────────────────────
echo "  📦 System libraries..."
brew install portaudio ffmpeg libsndfile 2>/dev/null || brew install portaudio ffmpeg libsndfile

# ── Ollama ───────────────────────────────────────────────────
if ! command -v ollama &>/dev/null; then
    echo "  📦 Installing Ollama..."
    brew install ollama
else
    echo "  ✓  Ollama"
fi

pkill ollama 2>/dev/null || true
sleep 1
ollama serve &>/dev/null &
sleep 3

# ── Models tuned for RAM ─────────────────────────────────────
echo ""
echo "  📥 AI models (optimized for ${RAM_GB}GB)..."

pull_model() {
    if ollama list 2>/dev/null | grep -q "$1"; then
        echo "  ✓  $1 (already installed)"
    else
        echo "  ↓  Pulling $1..."
        ollama pull "$1"
    fi
}

# Proven defaults: qwen2.5:7b for tool calling
echo "  ℹ  Brain: qwen2.5:7b"
pull_model "qwen2.5:7b"

if [ "$RAM_GB" -le 16 ]; then
    echo "  ℹ  Vision: moondream (optional, for see_screen)"
    pull_model "moondream" || true
else
    pull_model "moondream" || true
    pull_model "llama3.2-vision" || true
fi

# ── Python ───────────────────────────────────────────────────
echo ""
echo "  📦 Python packages..."

install_packages() {
    pip3 install \
        openai-whisper sounddevice soundfile numpy ollama \
        "duckduckgo-search>=6.0" pyautogui pillow playwright \
        fastapi "uvicorn[standard]" websockets edge-tts \
        mediapipe "opencv-python>=4.8" \
        "$@"
}

install_packages 2>/dev/null || install_packages --break-system-packages

# Optional: MLX LoRA weight fine-tuning (permanent qwen2.5 learning)
echo "  📦 Optional MLX LoRA (weight fine-tune)…"
pip3 install mlx-lm --break-system-packages 2>/dev/null || \
  pip3 install mlx-lm 2>/dev/null || \
  echo "  ○  mlx-lm skipped — memory + dinesh-learned still work without it"

echo "  🌐 Playwright Chromium..."
python3 -m playwright install chromium 2>/dev/null || true

# MediaPipe hand + face models for Eyes mode
echo "  👁  Vision models (hands + face)…"
VM_DIR="$SCRIPT_DIR/vision_models"
mkdir -p "$VM_DIR"
download_model() {
  local name="$1" url="$2"
  if [ -f "$VM_DIR/$name" ]; then
    echo "  ✓  $name"
  else
    echo "  ↓  $name"
    curl -fsSL -o "$VM_DIR/$name" "$url" || echo "  ○  failed to fetch $name"
  fi
}
download_model hand_landmarker.task \
  "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
download_model face_landmarker.task \
  "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"

# Seed empty memory DB
python3 -c "from memory.store import init_db; init_db(); print('  ✓  Long-term memory DB ready')" 2>/dev/null || true

# ── Done ─────────────────────────────────────────────────────
echo ""
echo "  ╔══════════════════════════════════════════════════════╗"
echo "  ║  ✅  Setup complete                                   ║"
echo "  ╠══════════════════════════════════════════════════════╣"
echo "  ║  Grant permissions (one-time):                        ║"
echo "  ║   • Microphone        → Terminal / Cursor             ║"
echo "  ║   • Camera            → Terminal / Cursor  (Eyes)     ║"
echo "  ║   • Accessibility     → Terminal / Cursor             ║"
echo "  ║   • Screen Recording  → Terminal / Cursor             ║"
echo "  ╠══════════════════════════════════════════════════════╣"
echo "  ║  Terminal:  python3 jarvis.py                        ║"
echo "  ║  HUD UI:    python3 server.py                        ║"
echo "  ║             → open http://127.0.0.1:8742             ║"
echo "  ║  Eyes:      click Eyes in HUD  (wave / blink / …)    ║"
echo "  ║  Learn:     remember … / memory / train              ║"
echo "  ╚══════════════════════════════════════════════════════╝"
echo ""
