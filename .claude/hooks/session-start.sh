#!/bin/bash
# Claude Code cloud sessions: install what the firmware build, the host tests and the hardware build
# need (CLAUDE.md, "Commands"). Local sessions are left alone: install with the same scripts yourself.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

# Firmware: pinned arduino-cli, RP2040 core and libraries (all from GitHub).
scripts/setup-arduino.sh
echo "export PATH=\"$HOME/.local/bin:\$PATH\"" >> "$CLAUDE_ENV_FILE"

# Hardware: KiCad (kicad-cli + the pcbnew Python module) and Freerouting.
scripts/setup-kicad.sh
