#!/usr/bin/env python3
"""Launcher — runs D.I.N.E.S.H from the jarvis/ package."""
import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().parent / "jarvis" / "jarvis.py"), run_name="__main__")
