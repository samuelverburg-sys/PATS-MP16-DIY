# MP-16 rev 2 hardware

One board, generated from Python and checked by script: `mp16/design.py` is the source of truth for
every part, value, LCSC number, connection and position. The KiCad files in `mp16/` are generated from
it; never edit them by hand (the next build overwrites them).

| | |
|---|---|
| Outline | 76.2 x 104.775 mm, six 2.5 mm holes: the rev-1 board, so the enclosure (`../enclosure/stl/`) fits |
| Layers | 2, JLCPCB standard rules (0.127 mm tracks, 0.13 mm clearance) |
| Assembly | every SMD part on the bottom (one JLCPCB assembly side, as rev 1); hand-soldered on top: encoder, OLED header, optional expansion header |
| Spec and decisions | `../docs/SPEC.md`, `../docs/decisions/` |

## Build

```sh
../scripts/setup-kicad.sh          # KiCad 7, Java 25, Freerouting 2.5.0 (once)
python3 build.py mp16 check        # netlist checks (seconds)
python3 build.py mp16 sch          # schematic + KiCad netlist round trip
python3 build.py mp16 pcb          # placed board + placement checks (courtyards, part drawings, facing, crossing order)
python3 build.py mp16 all          # check, sch, pcb, route, drc, review, fab (about 10 minutes)
python3 tools/where.py mp16 [x0 y0 x1 y1]   # part boxes in the design frame, for placing parts
BOARD=mp16 tools/xray.sh build/xray.png 250 [x0 y0 w h]   # bottom parts seen from above (design frame)
BOARD=mp16 tools/render.sh build   # top and bottom renders
python3 ../scripts/check-pins.py   # firmware pins (board_pins.h) == this board
```

Outputs: `mp16/mp16.kicad_sch`, `mp16/mp16.kicad_pcb`, `mp16/fab/` (Gerbers zip, BOM and CPL for
JLCPCB). Every `route`, `drc` and `review` run adds a line to `build-log.jsonl`.

## Where things are and why

Frame: mm seen from above, (0, 0) = top-left corner, y = 0 is the edge with the jacks (the KLE layout's
frame; the enclosure STLs use the same x and y_stl = 104.775 - y).

- **Fixed by the enclosure** (rev-1 positions, placed by `pin_targets` onto the rev-1 pad centres from
  `reference/rev1-pcb.easyeda.json`, with footprints converted from that board): MIDI In jack (x 19.6),
  USB-C (x 38.1, where the RP2040-Zero's socket was), MIDI Out jack (x 53.9), power switch (x 68.3),
  side-view charge LED, encoder, OLED header. These never move (Samuel, 2026-10-22). The battery plug
  (66.4, 26.7) is at its rev-1 position too, but may move.
  Checked against the STL openings with `tools/stl_openings.py`.
- **Top band (y 0-31)**: RP2040 and its flash and crystal in the middle (inside the window of the "Bottom
  (Open)" shell, with BOOT, RESET and the SWD pads), MIDI In circuit under its jack, charger, load switch,
  LDO and LED level shifter on the right, fuel gauge and battery protection beside the battery plug.
  0402 passives here; 0603 elsewhere.
- **Buttons and debug**: BOOT (SW18) and RESET (SW19) side by side in the lower left of the open bottom
  shell's window, named on the bottom silkscreen; above them three SWD pads, TP1 SWCLK, TP2 SWDIO,
  TP3 GND (left to right seen from above, right to left seen from below). Flashing a blank or stuck
  board: hold BOOT, press RESET, release BOOT; the RPI-RP2 drive appears.
- **Key area**: hot-swap sockets, LEDs and their capacitors as the PATS UI board; U1 (pads 1-8) between key
  rows 1 and 2 and U2 (pads 9-16) between rows 3 and 4, next to the keys they read; the 5 V LED boost
  between pads 3 and 4 and along row 1's LEDs.

## Fit checks still open (before ordering)

1. USB-C height: the RP2040-Zero's socket sat 1 mm lower (on the module's own board); this socket is on
   the main board. The enclosure opening (about 16 x 10 mm) leaves ~0.5 mm above a standard plug. Check
   with the printed Top/Bottom and a real cable.
2. The optional expansion header is through-hole: fit it from the bottom and trim the pins on top, or
   they may touch the switch plate.
3. 3D check of the stack (PCB, plate, OLED, battery between board and bottom shell).

## Pipeline

`build.py`, `tools/` and `lib/` are copied from the PATS repository (github.com/samuelverburg-sys/PATS,
`pats-core/hardware/`, commit 3d1c7dc, 2026-10-22); `PATS-PIPELINE.md` lists the changes made here.
The routing approach (Freerouting in stages, then a local finish router and ground stitching) is
described in the PATS hardware README; this board routes the RP2040's 0.4 mm pins and the charger's
power pins first, then power, then everything else.
