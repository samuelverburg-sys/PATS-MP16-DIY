#!/usr/bin/env bash
# Compile the MP-16 sketches with arduino-cli (pinned versions: scripts/setup-arduino.sh).
#   scripts/build-firmware.sh                 # every sketch for both boards
#   scripts/build-firmware.sh rev2 MP16_Chordmaker
# UF2 files land in build/<board>/<sketch>/<sketch>.ino.uf2.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FW="$ROOT/firmware"
CTAGS_DIR="${ARDUINO_DATA:-$HOME/.arduino15}/packages/builtin/tools/ctags/5.8-arduino11"

# Board options. Rev 1: the original kit's Waveshare RP2040-Zero (2 MB flash).
# Rev 2: bare RP2040 with a W25Q128JV (16 MB; the W25Q080 boot stage works for the whole W25Q family).
declare -A FQBN=(
  [rev1]="rp2040:rp2040:waveshare_rp2040_zero:flash=2097152_524288"
  [rev2]="rp2040:rp2040:generic:flash=16777216_14680064,boot2=boot2_w25q080_2_padded_checksum"
)
# USB stack per sketch: USB MIDI needs Adafruit TinyUSB, the Keyboard library needs the Pico SDK stack.
declare -A USBSTACK=(
  [MP16_Chordmaker]=tinyusb
  [MP16_Boilerplate]=tinyusb
  [MP16_YoutubeKeyboard]=picosdk
)

[[ $# -ge 1 ]] && boards=("$1") || boards=(rev1 rev2)
sketches=("${@:2}")
[[ ${#sketches[@]} -eq 0 ]] && sketches=("${!USBSTACK[@]}")

status=0
for board in "${boards[@]}"; do
  for sketch in "${sketches[@]}"; do
    out="$ROOT/build/$board/$sketch"
    mkdir -p "$out"
    printf '== %-22s %s\n' "$sketch" "$board"
    if arduino-cli compile --fqbn "${FQBN[$board]},usbstack=${USBSTACK[$sketch]}" \
        --libraries "$FW/libraries" --output-dir "$out" --warnings default \
        --build-property "runtime.tools.ctags.path=$CTAGS_DIR" \
        "$FW/$sketch" 2> "$out/compile.log" | grep -E "Sketch uses|Global variables"; then
      :
    else
      status=1
      grep -vE "discovery|Error initializing instance|index" "$out/compile.log" | tail -30
    fi
  done
done
exit $status
