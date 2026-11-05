# Routing journal (MP-16 rev 2)

What each routing experiment tested and what it showed. The numbers come from the build log
(`hardware/build-log.jsonl`); read it with:

```sh
python3 hardware/build.py mp16 log                 # last 15 route runs: attempts, open after router/finish, DRC, what changed
LOG_WIDE=1 python3 hardware/build.py mp16 log      # plus the open nets and where their gaps are
ROUTE_NOTE="what this run tests" python3 hardware/build.py mp16 route drc   # the note is stored with the run
```

Before a run: `python3 hardware/build.py mp16 preflight` (seconds): placement checks, the congestion score
(`tools/congestion.py`: routing demand against room, averaged over shifted grids) against the last run's, the
worst windows and the nets in them, and what the last run left open. Score candidate placements this way
while a route runs, and start the next route with the best one already chosen. Scores so far: run 8 78.5,
run 9 76.5, run 10 75.1 (lower is better; the order matches the results).

How to use it: one change per run, a `ROUTE_NOTE` naming it, and a row below when the result is in. Compare
like with like: a `quick` run (3 Freerouting passes) is only comparable to another quick run; a full run's
"router" column (open after Freerouting, best of the parallel attempts) is the placement's score, "finish"
is what the grid router could not close afterwards.

Freerouting is not deterministic: the same placement swings by about ±3 open connections between attempts
(see the attempts column), so a difference of 1-2 between two runs is noise. What is deterministic: the
pre-route (`tools/finish.py prejoin_short`), the finish, and everything in `design.py`.

## Experiments, 2026-11-03 (2 layers, JLCPCB rules)

| # | Change tested | Attempts (open after Freerouting) | After finish | DRC | Conclusion |
|---|---|---|---|---|---|
| 1 | 4 layers (GND + VLED planes), all parts on the bottom | 11 | run 10 + J6 pin 1 -> (6.4, 28.0) (congestion 75.1 -> 62.6 on a 0.5 mm grid) | stopped at once | - | - | wrong on two counts: J6's pins came 0.3 mm from R2, C19, C20, R3 on the bottom (hand-soldered: bridges; the courtyard check compared one side only, now it checks through-hole parts against the other side), and on a 0.25 mm grid the gain vanished (all J6 positions 39-42): the coarse score was aliasing |
| 12 | run 10 + uncrossed ends found by the new crossing check: ENC_A on GPIO23 / ENC_B on GPIO22 (the encoder's A is the farther pin), SWD pads SWDIO, SWCLK, GND left to right, header pins 7-9 EXP_LATCH, EXP_MOSI, SR_CLK; J6 back at (5.6, 29.24); congestion 39.1 (0.25 mm grid) | 9 / 11 / 12 connections | **2 (AIN2, AIN4)**, as the crossing check predicted | **0 err, 3 unc** (AIN2, AIN4, 1 ground) | ENC_A and SWCLK routed; ground nearly whole |
| 13 | run 12 + the encoder's R2, C19, C20, R3 on the top side (same place): on the bottom they sat in the gap the AIN tracks need past the encoder | 10 / 9 / 11 connections | stopped in the finish (ENC_A, MIDI_RX, RUN stuck at that point) | - | AIN2 and AIN4 routed. Stopped: Samuel chose 4 layers after the data review (docs/decisions/0002) |
| 14 | **4 layers** (In1 GND plane, In2 VLED plane), every SMD part on the bottom; Qwiic J6 at the bottom edge; battery divider; congestion 39.2 | all 3 timed out (900 s) at pass 6-9: 39-92 unrouted, 58-139 violations | - | - | two faults: (1) with both inner layers planes only the outer two carried signals, as on 2 layers, now with the RP2040's parts back on the bottom; (2) Freerouting saw 58-139 'unfixable' violations before routing: pre-routed tracks 0.15 mm from ground vias, under its clearance + margin (0.17-0.19) |
| 15 | run 14 with In2 a **signal layer** (VLED routed as a 0.6 mm power track; In1 stays the ground plane); pre-route keeps the router's widest clearance (+0.05); SES import takes inner-layer tracks; Freerouting timeout 1500 s; congestion 35.8 | 10 / 13 / 13 connections; **5 nets** (+3V3, MIDI_OUT_R, TS, VBAT, VDD_CORE) | crashed | - | the fewest open nets after Freerouting so far, and no pre-existing violations. The finish crashed (`tools/finish.py` build_blocks, KeyError 2): its grid router knows only F.Cu and B.Cu and met a track on In2. **Next:** teach finish.py (shapes, build_blocks, A*) the inner signal layer, or let it treat In2 tracks as obstacles on both outer layers' via cells; then rerun 15 |
| 2 | 2 layers, GPIO map: every signal on the RP2040 side it leaves towards | 10 / 7 / 11 | 3 (ISET, USB pair) | 8 err | the GPIO remap helped; 8 errors from margin 0.0 and edge insets (generator fixed) |
| 3 | RP2040 1 mm left (USB lane past the USB-C shell leg), ISET/ITERM swapped | 13 / 14 / 15 | 8 (USB pair, QSPI_SD3, RUN, VDD_CORE, ISET, AIN2, VSW) | not run | bottom-only is too crowded around the RP2040 on 2 layers |
| 4 | **RP2040's capacitors, flash and crystal on the top side** (`MP16_MCU_SIDE=F`), under the OLED | 6 / 6 / 7 | 3 (ITERM, XOUT, a top GND pad) | **0 err** | big step: the bottom around the RP2040 is free for its signals; needs double-sided assembly |
| 5 | as 4 + priority pre-route (USB, crystal, QSPI, VDD_CORE, ISET/ITERM up to 15 mm, then shortest first), R12 back on the bottom, ground fan-out on both sides | 10 / 13 / 9 | 6 (ENC_A, MIDI_RX/TX, PGOOD_N, SWCLK, VBUS_IN) | stopped | long priority routes (QSPI, VDD_CORE) wall in the GPIO pins: priority only for nets that failed repeatedly |
| 6 | as 5 with priority only for USB, crystal, ISET/ITERM (up to 10 mm) | 6 / 7 / 7 | 1 (PGOOD_N) + 2 ground islands | 3 err (VBUS 0.235 mm from the top edge) | best so far; the edge inset was in um, not mm (fixed); ground joining ran 865 s (budget added) |
| 7 | as 6 + PGOOD_N pre-routed last (own reach 60 mm), edge inset = 0.3 mm + 20 um | 13 / 12 / 18 | stopped | - | worse; two changes at once (breaking the one-change rule). Open at the USB-C edge (CC2, VBUS, VBUS_IN): the inset; KEY_P2, AIN4, I2C_SDA, SWCLK: likely the long PGOOD_N route |
| 8 | run 6 + the edge inset only (needed for JLCPCB anyway): the new baseline | 43 / 8 / 7 connections (9 / 7 / 6 nets) | 4 (AIN4, PGOOD_N, VBUS_IN, VSYS) + 7 ground areas | **0 err**, 11 unc | the inset fixes the edge errors and costs little; one attempt fell to 43 open on the same board (Freerouting's spread). Ground areas cut off around U1/U2 and under the charger; the charger group (U13, between key rows 2 and 3) blocks the channel the key and LED lines use |
| 9 | run 8 + the charger group (U13, C50-C52, R20-R24) moved from the channel between key rows 2-3 to the free band under the OLED (x 47-71, y 24-30) | 13 / 13 / 14 connections | **2 (AIN4, ILIM)** + 10 ground areas | 0 err, 12 unc | worse after Freerouting, better after the finish: the finish's result is what counts. ILIM: R21 sat left of U13, its pin is on the right (the facing check missed it: no partner part to compare with) |
| 10 | run 9 + R21/R22 beside ILIM (pin 12, right of U13) + expansion header AIN4..AIN1 left to right (uncrossed); congestion 75.1 | 25 / 12 / 11 connections | **2 (ENC_A, SWCLK)** | stopped before ground joining | both fixes worked (ILIM and AIN4 routed); what is left is on the left, between the encoder, the SWD pads and J6 |
| 11 | run 10 + expansion header J6 up and right, pin 1 (5.6, 29.24) -> (6.4, 28.0): its lower row sat on the busy bus at y 30 above key row 1; congestion 75.1 -> 62.6 (best of 9 positions scored) | | | | |
| 16A | qualifying (A/B, 2 attempts each, side by side): run 15 + finish router knows inner layers, fan-out keeps vias off same-net plated holes, Qwiic J6 on the right edge between key rows 3 and 4; charger in the band under the OLED (`MP16_CHARGER=band`); congestion 37.7 | 10 / 43 connections | 3 (QSPI_SD1, SWCLK, TS) | 40 err (38 inner-layer tracks 0.16-0.30 mm from LED windows, 2 finish tracks 0.1293 mm), 3 unc | finish router ran on 4 layers without crashing; loses the A/B |
| 16B | as 16A with the charger between key rows 2 and 3 (`MP16_CHARGER=keys`, pins' sides checked); congestion 39.0 | 40 / 13 connections | **1 (VDD_CORE)** | 25 err (23 inner-layer tracks by LED windows, 2 J6 courtyards), 2 unc | **wins the A/B**: charger between key rows 2 and 3 is the default; 10.2 min in all |
| 17 | final: 16B + LED window keep-outs grown by the edge clearance, finish clearance +0.03, three parallel attempts and one promote round (`ROUTE_PROMOTE_PARALLEL = 1`), ground budget 900 s | 5 / 44 / 28; promote round 29 / 29 / 33 (kept the first) | **1 (VDD_CORE)** | **0 err**, 2 unc (both VDD_CORE) | every other net routed, ground whole. Promote round: VDD_CORE could not be routed even alone, so it was walled in before routing: C36 (pin 44) and C37 (pin 45) sat in swapped order, boxing pin 45 in (the order check skips nets with several capacitors) |
| 18 | run 17 + C36/C37 swapped to their pins' order; VDD_CORE pre-routed first with a 12 mm reach (pre-route check: VDD_CORE whole before Freerouting) | 42 / 44 / 17; promote: QSPI_SD0, QSPI_SD1, +3V3 open even routed first | stopped | - | the VDD_CORE pre-route (A*, 12 mm) wound over the top layer above the RP2040's top row, vias inside the pin ring, walling the QSPI escapes in. Pre-route only nets that stay local |
| 19 | run 17 + C36/C37 swapped only (no VDD_CORE pre-route; pin 45 to C37 is a short hop the normal pre-route joins) | 18 / 49 / 50; promote 31-33 | 3 (QSPI_SCLK, QSPI_SD0, SWDIO) | **0 err**, 3 unc | VDD_CORE now joined (the swap was right). **Root cause of the RP2040 failures since the pre-route came in:** short hops between neighbouring same-net RP2040 pins ran through the pin ring: before routing, 29 +3V3 and 24 VDD_CORE tracks and 6 vias (+3V3, USB_DP, BAT_SENSE, VDD_CORE, XOUT) sat inside the ring, where the other pins escape. Each run the ring's leftovers decided which RP2040 nets failed |
| 20 | run 19 + `PREROUTE_KEEP_INSIDE = ['U10', 'U13']`: no pre-routed tracks or vias inside the RP2040's and the charger's pin rings (pre-route test: 3 items inside instead of 37 tracks and 6 vias; RP_USB_DN, VDD_CORE, XOUT left to Freerouting) | 38 / 45 / 43; promote 13 / 12 / 15 | **1 (RP_USB_DN)** | **0 err**, 1 unc | ties run 17. Freerouting alone did much worse without the ring hops (it had to join neighbouring same-net pins itself; one attempt took 22 min), but the promote round and finish recovered to 1. RP_USB_DN: R15/R16's RP2040 pads faced away from pins 46/47, so the USB pair crossed back through a 0.88 mm gap between C37 and C35 |
| 22 (prepared, not run) | run 20 + R15/R16 turned (RP2040 pads above pins 46/47), C39/C36/C37 0.2 mm left: the USB lane is clear | | | | |
| 21G (record) | grid mode: the grid router routes every net it can (any length), one Freerouting attempt, finish. Pre-route alone: 256 hops in 858 s, 22 connections in 21 nets left | 1 attempt: 9 connections in 9 nets | 6 (KEY_SHIFT, LED_D2, RP_USB_DN, SR_C21, SR_DATA, SR_LOAD) | 0 err, 6 unc | 39.4 min (pre-route 14.4, Freerouting 13.6, finish 11.2). Deterministic and repeatable (the pre-route gave the same 256 hops twice), but the grid router's long paths take room the shift-register and key lines need |
| 21F (record) | freerouting mode: no fan-out, no pre-route, Freerouting routes everything incl. ground, 20 passes, 3 attempts + promote, finish | 39 / 49 / 38; promote 12 / 13 / 13 | 2 signal nets (RUN, SWCLK) + 14 ground islands | 4 err (ground tracks at the edge), 16 unc | 27.1 min, the fastest, but without the fan-out the outer ground pours fall apart into islands no step joins (plane boards skip ground joining). Every net could be routed when routed first: without pre-route nothing is walled in |

## What has been learnt

- Placement decides most of it: moving parts (GPIO map, top-side passives) changed the open count by 5-10;
  router settings changed it by 1-3.
- Pre-routing a net locks the shortest path the grid router finds; that path ignores the pins around it.
  Pre-route only short, critical nets (USB, crystal, charger resistors), not buses that fan out (QSPI).
- Freerouting's result varies between attempts on the same board (run 8: 43, 8 and 7 open); three parallel
  attempts with different margins and keeping the best is a lottery, so it is a last step, never the fix.
- Judge a placement by what is open after the finish, not after Freerouting (run 9: worse after Freerouting,
  better after the finish). Ground areas depend on the ground-joining budget (GROUND_SECONDS); judge signal
  nets in experiments and give the final build the long budget.
- What predicts a failure before routing: geometry checks per net (a part on the far side of its chip, two
  neighbouring pins whose connections cross). The congestion score does not separate small moves (runs 8, 9,
  10 score 40.4, 40.0, 39.2 on the fine grid while leaving 4, 2, 2 nets open); use it for big moves and to
  find crowded windows. On run 10's placement the crossing check names exactly the two nets left open.
- A 4-layer board with two inner planes has the signal room of a 2-layer board. Give it at least one inner
  signal layer.
- Locked items must keep the router's clearance including its margin, or the router starts with violations
  it cannot fix and routes around them badly.
- A net that stays open when routed first, alone, is blocked by placement or locked items, not by
  traffic: look at its pins' neighbours before rerunning.
- The pre-route must not use a fine-pitch chip's pin ring: neighbouring same-net pins are 0.4 mm apart, so
  the grid router joins them through the ring and drops vias there, where every other pin escapes.
- Record runs (2026-11-05), same board: balanced (run 20) 1 open, 0 errors, 35 min; Freerouting-heavy (21F)
  2 open + 14 ground islands, 4 errors, 27 min; grid-heavy (21G) 6 open, 0 errors, 39 min. Each side does
  what the other cannot: the fan-out and short pre-routed hops make the ground and the dense pin joins
  certain; Freerouting with a promote round handles the board-wide routing; the finish closes the rest.
- Recurring trouble spot: the charger group (U13 and its resistors) in the channel between key rows 2 and 3:
  ISET, ITERM, VSYS, PGOOD_N and a ground area have each failed there.
