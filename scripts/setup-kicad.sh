#!/usr/bin/env bash
# Install what hardware/build.py needs: KiCad 7+ (kicad-cli and the pcbnew Python module), poppler
# (renders), Java 25 and Freerouting 2.5.0 (routing). Ubuntu/Debian only; elsewhere install KiCad from
# kicad.org, a Java 25 runtime and the Freerouting jar, and set JAVA and FREEROUTING_JAR. Safe to rerun.
set -euo pipefail

FREEROUTING_VERSION=2.5.0
FREEROUTING_SHA256=f6f51bb02245e8e717f9359bd260cc9c5c0b1bc0acc8b7cb2cd5b8ffeb5de3c7
FR_DIR="${FREEROUTING_DIR:-$HOME/.local/share/freerouting}"
JAVA25=/usr/lib/jvm/java-25-openjdk-amd64/bin/java

SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"
need=()
{ command -v kicad-cli >/dev/null && python3 -c "import pcbnew" 2>/dev/null; } || need+=(kicad kicad-footprints kicad-symbols)
command -v pdftoppm >/dev/null || need+=(poppler-utils)
[ -x "$JAVA25" ] || need+=(openjdk-25-jre-headless)
if [ ${#need[@]} -gt 0 ]; then
  echo "Installing ${need[*]}"
  $SUDO apt-get update -qq
  DEBIAN_FRONTEND=noninteractive $SUDO apt-get install -y -qq --no-install-recommends "${need[@]}" >/dev/null
fi

JAR="$FR_DIR/freerouting-$FREEROUTING_VERSION.jar"
if [ ! -f "$JAR" ]; then
  echo "Installing Freerouting $FREEROUTING_VERSION"
  mkdir -p "$FR_DIR"
  curl -fsSL -o "$JAR.part" \
    "https://github.com/freerouting/freerouting/releases/download/v$FREEROUTING_VERSION/freerouting-$FREEROUTING_VERSION.jar"
  echo "$FREEROUTING_SHA256  $JAR.part" | sha256sum -c --quiet
  mv "$JAR.part" "$JAR"
fi

# For build.py (cloud sessions: written to the session environment by the SessionStart hook).
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo "export JAVA=$JAVA25 FREEROUTING_JAR=$JAR" >> "$CLAUDE_ENV_FILE"
fi
echo "KiCad ready: $(kicad-cli version); Freerouting: JAVA=$JAVA25 FREEROUTING_JAR=$JAR"
