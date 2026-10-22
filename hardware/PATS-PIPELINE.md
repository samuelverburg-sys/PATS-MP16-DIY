# The board generator, copied from PATS

Source: github.com/samuelverburg-sys/PATS, `pats-core/hardware/` at commit
3d1c7dc1f4c6a81745e27514db4d8bda24fe8e49 (2026-10-22): `build.py`, `tools/`, `lib/`, `.gitignore`,
`fp-lib-table.template`, `THIRD_PARTY.md`, `ORDERING-CHECKLIST.md`. Copied, not linked (decided with
Samuel 2026-10-22): this repository builds on its own.

When the PATS pipeline improves, bring changes over file by file and note them below.

## Changes made here

| File | Change | Why |
|---|---|---|
| `tools/silk.py` | `import connector` moved into `connector_labels()` | the PATS board-to-board connector module does not exist here |
| `tools/render.sh` | bottom render includes `B.Fab` | part outlines help when placing |
| `tools/make_lib.py` | `TLP109` symbol added | MIDI In opto-coupler of rev 1, not in KiCad's library |
| `tools/fanout.py`, `build.py` | ground fan-out works on either side (`design.GND_FANOUT_SIDE`, default `F`) | all of this board's SMD parts are on the bottom; the fan-out handled only top-side parts |
| `tools/pcb.py` | `design.HIDE_REFS`: references to hide outright | parts a label names in words (BOOT, RESET) |
| `build.py` | `design.ROUTE_PASSES` (default 30) | Freerouting stops after that many passes and returns its best result instead of timing out |
| `tools/xray.sh` | new | bottom parts seen from above, in the design frame |
| `tools/where.py` | new | courtyard boxes and overlaps in the design frame |
| `tools/stl_openings.py` | new | finds the enclosure's wall openings from the STLs |
| `lib/PATS.pretty/Toshiba_SO6-5P_TLP109` | new, converted from the rev-1 board (`tools/easyeda_fp.py`) | |
| `lib/PATS.pretty/LED_SideView_XL-1606_RD` | new, converted from the rev-1 board | side-view charge LED |
