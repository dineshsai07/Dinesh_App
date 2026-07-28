# Changelog

All notable changes to this project are documented in this file.

## [1.0.0] - 2026-07-28

### Added
- Portable `main.py` lifecycle commands for setup/start/stop/hud/cli/status.
- HUD runtime with live telemetry, wake flow, and vision control integration.
- Long-term memory persistence and local training export pipeline.
- Core regression suite for NLU, intent routing, and vision gesture logic.

### Changed
- Project/package renamed from `jarvis` to `dinesh`.
- Documentation updated for current architecture and operator workflow.

### Security
- SAFE mode defaults maintained for destructive operations.

## [Unreleased]

### Added
- Safety confirmations for risky shell commands in full-control mode.
- Safety confirmations for destructive delete operations.
- Response latency telemetry fields (`first token` and `total response`).
- Audio warm-start helper to reduce first interaction delay.
- New reliability tests for `audio.py`, `server.py`, and `memory/store.py`.
- README sections for known limitations, troubleshooting, and demo onboarding.
