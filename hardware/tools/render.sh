#!/bin/sh
# Render top and bottom views of "${BOARD:-ui}.kicad_pcb" to PNG (needs kicad-cli and pdftoppm).
set -e
cd "$(dirname "$0")/../${BOARD:-ui}"
OUT=${1:-build}
DPI=${2:-110}
mkdir -p "$OUT"
kicad-cli pcb export pdf --exclude-value -l F.Cu,F.Silkscreen,F.Courtyard,Edge.Cuts -o "$OUT/top.pdf" "${BOARD:-ui}.kicad_pcb" >/dev/null
kicad-cli pcb export pdf --exclude-value -m -l B.Cu,B.Silkscreen,B.Courtyard,B.Fab,Edge.Cuts -o "$OUT/bottom.pdf" "${BOARD:-ui}.kicad_pcb" >/dev/null
# crop to the board: layout frame 0..76.2 x 0..176 mm, sheet origin at (40, 30) mm
PX=$(python3 -c "print($DPI/25.4)")
X=$(python3 -c "print(int(38*$PX))"); Y=$(python3 -c "print(int(27*$PX))")
W=$(python3 -c "print(int(80*$PX))"); H=$(python3 -c "print(int(110*$PX))")
XB=$(python3 -c "print(int((297-38-80)*$PX))")  # bottom view is mirrored on the A4 sheet
pdftoppm -r "$DPI" -png -singlefile -x $X -y $Y -W $W -H $H "$OUT/top.pdf" "$OUT/top"
pdftoppm -r "$DPI" -png -singlefile -x $XB -y $Y -W $W -H $H "$OUT/bottom.pdf" "$OUT/bottom"
echo "$OUT/top.png $OUT/bottom.png"
