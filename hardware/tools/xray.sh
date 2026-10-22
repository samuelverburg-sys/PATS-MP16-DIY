#!/bin/sh
# X-ray view: bottom-side copper, courtyards and part drawings seen from ABOVE (same frame as design.py,
# not mirrored), with the top-side drawings faint. For placing bottom parts. Optional crop in mm:
#   BOARD=mp16 tools/xray.sh OUT.png [dpi] [x0 y0 w h]
set -e
cd "$(dirname "$0")/../${BOARD:-ui}"
OUT=${1:-build/xray.png}; DPI=${2:-200}
X0=${3:-0}; Y0=${4:-0}; W=${5:-76.2}; H=${6:-104.8}
mkdir -p "$(dirname "$OUT")"
tmp=$(mktemp -d)
kicad-cli pcb export pdf --exclude-value --black-and-white -l B.Cu,B.Courtyard,B.Fab,B.Silkscreen,F.Fab,Edge.Cuts \
  -o "$tmp/x.pdf" "${BOARD:-ui}.kicad_pcb" >/dev/null
PX=$(python3 -c "print($DPI/25.4)")
# layout frame (0, 0) is at (40, 30) mm on the sheet (tools/pcb.py ORIGIN)
pdftoppm -r "$DPI" -png -singlefile -x $(python3 -c "print(int((40+$X0)*$PX))") -y $(python3 -c "print(int((30+$Y0)*$PX))") \
  -W $(python3 -c "print(int($W*$PX))") -H $(python3 -c "print(int($H*$PX))") "$tmp/x.pdf" "${OUT%.png}"
rm -rf "$tmp"
echo "$OUT"
