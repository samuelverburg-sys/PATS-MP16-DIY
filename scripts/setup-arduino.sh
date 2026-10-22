#!/usr/bin/env bash
# Install the pinned Arduino toolchain for scripts/build-firmware.sh. Safe to run again (skips what is
# installed). Everything comes from GitHub, so it also works where downloads.arduino.cc is blocked
# (Claude Code cloud sessions): libraries are installed from their git tags instead of the index.
set -euo pipefail

ARDUINO_CLI_VERSION=1.3.1
RP2040_CORE_VERSION=6.3.0  # earlephilhower/arduino-pico
CTAGS_VERSION=5.8-arduino11
LIBS=(
  "adafruit/Adafruit_NeoPixel#1.15.5"
  "adafruit/Adafruit_SSD1306#2.5.17"
  "adafruit/Adafruit-GFX-Library#1.13.0"
  "adafruit/Adafruit_BusIO#1.17.4"
)

BIN="${ARDUINO_BIN:-$HOME/.local/bin}"
DATA="${ARDUINO_DATA:-$HOME/.arduino15}"
mkdir -p "$BIN"
export PATH="$BIN:$PATH"

if ! arduino-cli version 2>/dev/null | grep -q "Version: $ARDUINO_CLI_VERSION"; then
  echo "Installing arduino-cli $ARDUINO_CLI_VERSION"
  curl -fsSL "https://github.com/arduino/arduino-cli/releases/download/v${ARDUINO_CLI_VERSION}/arduino-cli_${ARDUINO_CLI_VERSION}_Linux_64bit.tar.gz" \
    | tar xz -C "$BIN" arduino-cli
fi

arduino-cli config init --overwrite >/dev/null
arduino-cli config set board_manager.additional_urls \
  https://github.com/earlephilhower/arduino-pico/releases/download/global/package_rp2040_index.json
arduino-cli config set library.enable_unsafe_install true  # needed for --git-url installs

if ! arduino-cli core list 2>/dev/null | grep -q "rp2040:rp2040 *$RP2040_CORE_VERSION"; then
  echo "Installing rp2040:rp2040@$RP2040_CORE_VERSION"
  arduino-cli core update-index 2>/dev/null || true  # the Arduino index may be unreachable; the RP2040 one is enough
  arduino-cli core install "rp2040:rp2040@$RP2040_CORE_VERSION"
fi

installed="$(arduino-cli lib list 2>/dev/null || true)"
for spec in "${LIBS[@]}"; do
  repo="${spec%#*}" tag="${spec#*#}"
  name="$(echo "$repo" | cut -d/ -f2 | sed 's/-Library$/ Library/; s/_/ /g; s/-/ /g')"
  if ! echo "$installed" | grep -q "^$name *$tag "; then
    echo "Installing $repo $tag"
    arduino-cli lib install --git-url "https://github.com/$repo#$tag" >/dev/null
  fi
done

# ctags is normally fetched from downloads.arduino.cc; take Arduino's GitHub release instead.
CTAGS_DIR="$DATA/packages/builtin/tools/ctags/$CTAGS_VERSION"
if [[ ! -x "$CTAGS_DIR/ctags" ]]; then
  echo "Installing ctags $CTAGS_VERSION"
  mkdir -p "$CTAGS_DIR"
  tmp="$(mktemp -d)"
  curl -fsSL "https://github.com/arduino/ctags/releases/download/$CTAGS_VERSION/ctags-$CTAGS_VERSION-x86_64-pc-linux-gnu.tar.bz2" \
    | tar xj -C "$tmp"
  cp "$(find "$tmp" -name ctags -type f | head -1)" "$CTAGS_DIR/ctags"
  rm -rf "$tmp"
fi

echo "Arduino toolchain ready: arduino-cli $ARDUINO_CLI_VERSION, rp2040 $RP2040_CORE_VERSION"
