#!/bin/bash
# ============================================================
#   Launch D.I.N.E.S.H HUD
#   Run this from YOUR OWN Terminal so macOS attaches
#   Microphone + Camera permission to Terminal (needed for
#   wake word and Eyes / gesture mode).
# ============================================================
cd "$(dirname "$0")"

PORT=8742

# Free the port if a previous instance is stuck
if lsof -tiTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1; then
  echo "  ↻  Port $PORT busy — stopping the old instance…"
  lsof -tiTCP:$PORT -sTCP:LISTEN | xargs kill 2>/dev/null || true
  sleep 1
fi

echo ""
echo "  ╔══════════════════════════════════════════════════════╗"
echo "  ║   D.I.N.E.S.H  HUD                                    ║"
echo "  ║   → http://127.0.0.1:$PORT                            ║"
echo "  ╠══════════════════════════════════════════════════════╣"
echo "  ║   Wake word:  click Wake, then say “Hey Dinesh”       ║"
echo "  ║   Eyes:       click Eyes (allow Camera when asked)    ║"
echo "  ╚══════════════════════════════════════════════════════╝"
echo ""
echo "  First run may ask for Microphone / Camera — click Allow."
echo "  If it doesn't ask: System Settings → Privacy & Security"
echo "  → Microphone & Camera → enable Terminal, then rerun."
echo ""

# Open the browser shortly after the server comes up
( sleep 3; open "http://127.0.0.1:$PORT" >/dev/null 2>&1 ) &

exec python3 server.py
