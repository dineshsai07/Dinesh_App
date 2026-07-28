#!/bin/bash
# ============================================================
#   JARVIS AI - One-Click Setup for Mac M4
#   Installs: Homebrew, Ollama, Whisper, Python deps
# ============================================================

set -e

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║        🤖 JARVIS AI - Mac M4 Setup       ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── 1. Homebrew ──────────────────────────────────────────────
if ! command -v brew &>/dev/null; then
    echo "📦 Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Add brew to PATH for Apple Silicon
    eval "$(/opt/homebrew/bin/brew shellenv)"
    echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
else
    echo "✅ Homebrew already installed"
fi

# ── 2. System Dependencies ───────────────────────────────────
echo ""
echo "📦 Installing system dependencies (portaudio, ffmpeg)..."
brew install portaudio ffmpeg

# ── 3. Ollama (local AI engine) ──────────────────────────────
echo ""
if ! command -v ollama &>/dev/null; then
    echo "📦 Installing Ollama..."
    brew install ollama
else
    echo "✅ Ollama already installed"
fi

# Start Ollama in the background
echo "🚀 Starting Ollama service..."
pkill ollama 2>/dev/null || true
sleep 1
ollama serve &>/dev/null &
OLLAMA_PID=$!
echo "   Ollama started (PID: $OLLAMA_PID)"
sleep 3

# ── 4. Pull AI Model ─────────────────────────────────────────
echo ""
echo "📥 Downloading AI brain: llama3.2 (~2GB)"
echo "   This may take a few minutes on first run..."
ollama pull llama3.2

# ── 5. Python Packages ───────────────────────────────────────
echo ""
echo "📦 Installing Python packages..."

# Use pip3 with fallback strategies
install_packages() {
    pip3 install \
        openai-whisper \
        sounddevice \
        soundfile \
        numpy \
        ollama \
        "duckduckgo-search>=6.0" \
        "$@"
}

# Try system pip first, then with --break-system-packages
if ! install_packages 2>/dev/null; then
    echo "   Retrying with --break-system-packages..."
    install_packages --break-system-packages
fi

# ── 6. Microphone Permission Hint ───────────────────────────
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║        ✅ Setup Complete!                ║"
echo "╠══════════════════════════════════════════╣"
echo "║                                          ║"
echo "║  IMPORTANT: Grant mic permission         ║"
echo "║  System Settings → Privacy → Microphone ║"
echo "║  → Enable for Terminal                   ║"
echo "║                                          ║"
echo "║  Then run:  python3 jarvis.py            ║"
echo "║                                          ║"
echo "╚══════════════════════════════════════════╝"
echo ""
