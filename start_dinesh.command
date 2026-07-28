#!/bin/bash
# Double-click or run from Terminal — starts D.I.N.E.S.H on THIS Mac.
cd "$(cd "$(dirname "$0")" && pwd)"
# First-time? run setup automatically if no venv yet.
if [ ! -x ".venv/bin/python" ]; then
  echo "  First run — setting up (this may take a while)…"
  python3 main.py setup || exit 1
fi
exec python3 main.py start
