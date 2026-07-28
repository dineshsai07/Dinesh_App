#!/bin/bash
# Stop the background D.I.N.E.S.H HUD on THIS Mac.
cd "$(cd "$(dirname "$0")" && pwd)"
exec python3 main.py stop
