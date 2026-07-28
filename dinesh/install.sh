#!/bin/bash
# Thin wrapper — full setup lives in ../main.py (portable for any Mac).
cd "$(cd "$(dirname "$0")/.." && pwd)"
exec python3 main.py setup
