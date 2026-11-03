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
| `tools/finish.py` | the grid search tries a 4 mm, then 12 mm window around the two pieces before the whole board | 80-90 s per stuck net, even for 1.5 mm hops |
| `tools/finish.py`, `build.py` | `prejoin_short()` / `design.PREROUTE_MM`: pieces of a net within N mm routed and locked before Freerouting | Freerouting failed 1-3 mm hops (a part's own pins, a part and its capacitor) in crowded corners |
| `build.py` | `design.ROUTE_PARALLEL`: N Freerouting runs at once (different margins), best kept by KiCad's count | its result swings from run to run (10 to 19 open on near-identical boards); it uses one core |
| `build.py` | ground joining skipped when GND is a plane | it sees only the outer pours and 'joined' areas the plane already joins |
| `tools/xray.sh` | new | bottom parts seen from above, in the design frame |
| `tools/where.py` | new | courtyard boxes and overlaps in the design frame |
| `tools/stl_openings.py` | new | finds the enclosure's wall openings from the STLs |
| `lib/PATS.pretty/Toshiba_SO6-5P_TLP109` | new, converted from the rev-1 board (`tools/easyeda_fp.py`) | |
| `lib/PATS.pretty/LED_SideView_XL-1606_RD` | new, converted from the rev-1 board | side-view charge LED |
| `build.py` | facing check: a part on the far side of its chip from the only pin it serves (more than 120 deg) | MP-16 run 9: R21 left of U13 with ILIM on the right stayed open; the order and turn checks could not see it |
| `tools/finish.py`, `build.py` | pre-route order: `design.PREROUTE_FIRST` nets first (an entry may be `(net, mm)`), then every net by its shortest hop | alphabetical order let long hops block short ones; Samuel: route the critical nets first |
| `build.py`, `tools/buildlog.py` | route log: `ROUTE_NOTE`, pre-route result, gap positions, settings changed since the previous run, stopped runs; `LOG_WIDE=1 build.py <board> log` | to learn from each run instead of re-running |
| `tools/finish.py` | `join_ground` time budget (`GROUND_SECONDS`, 300) with the positions of areas left cut off | it ran 865 s on one MP-16 run |
| `build.py` | DSN boundary inset = edge clearance + 20 um (the DSN is in um; the old `+ 0.08` was 0.08 um) | tracks ended 0.235 mm from the edge (rule 0.3) |
| `build.py` | ground fan-out on several sides (`GND_FANOUT_SIDE = 'BF'`) | the MP-16's RP2040 capacitors are on the top, the rest on the bottom |
