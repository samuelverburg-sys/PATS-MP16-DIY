#!/usr/bin/env bash
# Install KiCad (kicad-cli and the pcbnew Python module) for hardware/build.py. Ubuntu/Debian only;
# on Windows or macOS install KiCad 7 or newer from kicad.org instead. Safe to run again.
set -euo pipefail

if ! command -v kicad-cli >/dev/null || ! python3 -c "import pcbnew" 2>/dev/null; then
  echo "Installing KiCad"
  SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"
  $SUDO apt-get update -qq
  DEBIAN_FRONTEND=noninteractive $SUDO apt-get install -y -qq --no-install-recommends \
    kicad kicad-footprints kicad-symbols >/dev/null
fi
echo "KiCad ready: $(kicad-cli version)"
