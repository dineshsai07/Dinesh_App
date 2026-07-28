#!/bin/bash
# Stop the always-on D.I.N.E.S.H HUD LaunchAgent.
PLIST_DST="$HOME/Library/LaunchAgents/com.dinesh.hud.plist"
launchctl bootout "gui/$(id -u)/com.dinesh.hud" 2>/dev/null || true
launchctl unload "$PLIST_DST" 2>/dev/null || true
lsof -tiTCP:8742 -sTCP:LISTEN 2>/dev/null | xargs kill 2>/dev/null || true
echo "D.I.N.E.S.H stopped."
