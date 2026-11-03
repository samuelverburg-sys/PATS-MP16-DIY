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
| `tools/finish.py` | prints each net it joins or cannot join; rip-up time budget per net (`FINISH_RIPUP_SECONDS`, default 90) | on this board a stuck net kept the finish searching for over 40 minutes, silently |
| `tools/finish.py` | vias (stitching, joins) keep the hole clearance from bare NPTH holes with their copper ring, not only their drill | stitching vias landed 0.1-0.23 mm from key-socket holes (rule 0.25) |
| `build.py` | `open_nets_report()`: what is open comes from KiCad's DRC (0.7 s), not Freerouting's log; used for each stage's result, rip-up rounds and the best-attempt choice | Freerouting's log lists open nets only some of the time: every stage printed "all routed" while 10-49 connections were open |
| `build.py` | `quick` step: Freerouting only (3 passes), no finish/stitch/ground joining; prints every open connection with positions | a placement test in minutes instead of 40-60 |
| `build.py` | a timing line per run (prep, each stage, finish, stitch, ground join) | to see where the time goes |
| `build.py` | the finish router gets only the nets KiCad reports open | it walked every net, rebuilding the board geometry for each (25-40 min a run) |
| `build.py`, `tools/pcb.py` | 4 layers: `design.LAYERS`, `design.PLANES` (inner layer -> net); planes typed as power layers and kept in the router's input as Specctra planes; their nets fanned out to vias; Gerbers include the inner layers | this board on 2 layers left 49 connections open after Freerouting |
| `build.py`, `tools/sch.py` | from PATS after 3d1c7dc (to a8de241): JLCPCB CPL offset for the MX-Hotswap-1U sockets (`CPL_OFFSETS`), byte-identical schematics and Gerber zips, fab keeps the board views | PATS commits 45b45e8, fa79d13, 3be9aac |
| `tools/xray.sh` | new | bottom parts seen from above, in the design frame |
| `tools/where.py` | new | courtyard boxes and overlaps in the design frame |
| `tools/stl_openings.py` | new | finds the enclosure's wall openings from the STLs |
| `lib/PATS.pretty/Toshiba_SO6-5P_TLP109` | new, converted from the rev-1 board (`tools/easyeda_fp.py`) | |
| `lib/PATS.pretty/LED_SideView_XL-1606_RD` | new, converted from the rev-1 board | side-view charge LED |
