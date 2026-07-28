# Suggested next upgrades for D.I.N.E.S.H
#
# Priority order for making this feel "out of the world" in public demos.

## P0 — ship blockers (done or nearly done)
- [x] Typo / STT noise tolerance (nlu.py)
- [x] Never reply "I didn't understand"
- [x] Live telemetry (CPU/RAM/disk/battery)
- [x] Responsive HUD (no horizontal overflow)
- [x] Long-term memory + train → dinesh-learned
- [x] Open-source pack (README, LICENSE, .gitignore, requirements)
- [x] Eyes mode — MediaPipe hands + face (wave/fist/pinch/blink/gaze)
- [x] Streaming LLM tokens into HUD
- [x] First-run permissions report (mic/camera/accessibility/screen)

## P1 — polish that demo viewers notice in under 30 seconds
- [ ] Confirm spoken wake with a soft chime + reactor pulse
- [ ] Calibrate gesture sensitivity per user
- [ ] Optional always-on Eyes at boot (JARVIS_EYES=1)

## P2 — intelligence leaps
- [ ] Multi-step plan preview before risky shell/GUI actions
- [ ] Self-eval after tasks: did the tool succeed? retry once if not
- [ ] Semantic memory search (embed facts, retrieve top-k) instead of dumping all facts into the prompt
- [ ] Voice barge-in: interrupt TTS by speaking

## P3 — open-source growth
- [ ] Plugin directory: drop a Python file → new tool
- [ ] GitHub Actions: run pytest on PRs
- [ ] Demo GIF / short video in README
- [ ] Optional cloud LLM fallback behind JARVIS_CLOUD=1 with a big local-only banner

## What NOT to add yet
- More models for the sake of it — qwen2.5:7b + dinesh-learned is enough
- Purple glow redesigns — the cyan console identity is already distinctive
- Mobile App Store packaging — keep web HUD + CLI first
