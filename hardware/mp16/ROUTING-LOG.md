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
| 13 | run 12 + the encoder's R2, C19, C20, R3 on the top side (same place): on the bottom they sat in the gap the AIN tracks need past the encoder | | | | |
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
- Recurring trouble spot: the charger group (U13 and its resistors) in the channel between key rows 2 and 3:
  ISET, ITERM, VSYS, PGOOD_N and a ground area have each failed there.
