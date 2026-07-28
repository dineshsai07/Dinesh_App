#!/bin/bash
# Portable installer — works from any clone location on any Mac.
cd "$(cd "$(dirname "$0")" && pwd)"
exec python3 main.py setup
