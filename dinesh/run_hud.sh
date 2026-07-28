#!/bin/bash
# Launch D.I.N.E.S.H HUD in the foreground (dev / debug).
# Prefer:  python3 main.py start   (background, stays alive)
cd "$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd .. && pwd)"
export PYTHONPATH="$(pwd)"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

PORT=8742
if lsof -tiTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1; then
  echo "  ↻  Port $PORT busy — stopping the old instance…"
  lsof -tiTCP:$PORT -sTCP:LISTEN | xargs kill 2>/dev/null || true
  sleep 1
fi

echo ""
echo "  D.I.N.E.S.H HUD (foreground)"
echo "  Open → http://127.0.0.1:$PORT"
echo "  Tip: use  python3 main.py start  for a background service."
echo ""

PY="$ROOT/.venv/bin/python"
if [ ! -x "$PY" ]; then
  PY="$(command -v python3)"
fi

( sleep 2; open "http://127.0.0.1:$PORT" >/dev/null 2>&1 ) &
exec "$PY" server.py
