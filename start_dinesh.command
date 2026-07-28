#!/bin/bash
# Double-click this (or run from Terminal) to start D.I.N.E.S.H and keep it alive.
set -e
PLIST_SRC="/Users/dineshsai/jarvis_app/jarvis/com.dinesh.hud.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.dinesh.hud.plist"
SCRIPT="/Users/dineshsai/jarvis_app/jarvis/start_hud_daemon.sh"

chmod +x "$SCRIPT" /Users/dineshsai/jarvis_app/jarvis/run_hud.sh 2>/dev/null || true
mkdir -p "$HOME/Library/LaunchAgents"
cp "$PLIST_SRC" "$PLIST_DST"

# Unload old, load fresh
launchctl bootout "gui/$(id -u)/com.dinesh.hud" 2>/dev/null || true
launchctl unload "$PLIST_DST" 2>/dev/null || true
sleep 1
# Free port if something else holds it
lsof -tiTCP:8742 -sTCP:LISTEN 2>/dev/null | xargs kill 2>/dev/null || true
sleep 1

launchctl bootstrap "gui/$(id -u)" "$PLIST_DST" 2>/dev/null || launchctl load "$PLIST_DST"
launchctl enable "gui/$(id -u)/com.dinesh.hud" 2>/dev/null || true
launchctl kickstart -k "gui/$(id -u)/com.dinesh.hud" 2>/dev/null || true

echo "Starting D.I.N.E.S.H…"
for i in $(seq 1 20); do
  if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8742/ | grep -q 200; then
    echo "Ready → http://127.0.0.1:8742"
    open "http://127.0.0.1:8742"
    exit 0
  fi
  sleep 1
done
echo "Still starting — check /tmp/dinesh_hud.log"
open "http://127.0.0.1:8742" 2>/dev/null || true
