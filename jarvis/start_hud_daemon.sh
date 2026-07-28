#!/bin/bash
# Keep D.I.N.E.S.H HUD alive independently of Cursor / Terminal sessions.
cd /Users/dineshsai/jarvis_app/jarvis
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
exec /opt/homebrew/bin/python3 server.py
