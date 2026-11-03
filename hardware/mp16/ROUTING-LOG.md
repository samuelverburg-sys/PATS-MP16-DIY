# Routing journal (MP-16 rev 2)

What each routing experiment tested and what it showed. The numbers come from the build log
(`hardware/build-log.jsonl`); read it with:

```sh
python3 hardware/build.py mp16 log                 # last 15 route runs: attempts, open after router/finish, DRC, what changed
LOG_WIDE=1 python3 hardware/build.py mp16 log      # plus the open nets and where their gaps are
ROUTE_NOTE="what this run tests" python3 hardware/build.py mp16 route drc   # the note is stored with the run
```

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
| 1 | 4 layers (GND + VLED planes), all parts on the bottom | 11 | 1 (RP_USB_DN) | 0 err | 4 layers nearly closes; Samuel prefers 2 |
| 2 | 2 layers, GPIO map: every signal on the RP2040 side it leaves towards | 10 / 7 / 11 | 3 (ISET, USB pair) | 8 err | the GPIO remap helped; 8 errors from margin 0.0 and edge insets (generator fixed) |
| 3 | RP2040 1 mm left (USB lane past the USB-C shell leg), ISET/ITERM swapped | 13 / 14 / 15 | 8 (USB pair, QSPI_SD3, RUN, VDD_CORE, ISET, AIN2, VSW) | not run | bottom-only is too crowded around the RP2040 on 2 layers |
| 4 | **RP2040's capacitors, flash and crystal on the top side** (`MP16_MCU_SIDE=F`), under the OLED | 6 / 6 / 7 | 3 (ITERM, XOUT, a top GND pad) | **0 err** | big step: the bottom around the RP2040 is free for its signals; needs double-sided assembly |
| 5 | as 4 + priority pre-route (USB, crystal, QSPI, VDD_CORE, ISET/ITERM up to 15 mm, then shortest first), R12 back on the bottom, ground fan-out on both sides | 10 / 13 / 9 | 6 (ENC_A, MIDI_RX/TX, PGOOD_N, SWCLK, VBUS_IN) | stopped | long priority routes (QSPI, VDD_CORE) wall in the GPIO pins: priority only for nets that failed repeatedly |
| 6 | as 5 with priority only for USB, crystal, ISET/ITERM (up to 10 mm) | 6 / 7 / 7 | 1 (PGOOD_N) + 2 ground islands | 3 err (VBUS 0.235 mm from the top edge) | best so far; the edge inset was in um, not mm (fixed); ground joining ran 865 s (budget added) |
| 7 | as 6 + PGOOD_N pre-routed last (own reach 60 mm), edge inset = 0.3 mm + 20 um | 13 / 12 / 18 | stopped | - | worse; two changes at once (breaking the one-change rule). Open at the USB-C edge (CC2, VBUS, VBUS_IN): the inset; KEY_P2, AIN4, I2C_SDA, SWCLK: likely the long PGOOD_N route |
| 8 | run 6 + the edge inset only (needed for JLCPCB anyway): the new baseline | 43 / 8 / 7 connections (9 / 7 / 6 nets) | 4 (AIN4, PGOOD_N, VBUS_IN, VSYS) + 7 ground areas | **0 err**, 11 unc | the inset fixes the edge errors and costs little; one attempt fell to 43 open on the same board (Freerouting's spread). Ground areas cut off around U1/U2 and under the charger; the charger group (U13, between key rows 2 and 3) blocks the channel the key and LED lines use |

## What has been learnt

- Placement decides most of it: moving parts (GPIO map, top-side passives) changed the open count by 5-10;
  router settings changed it by 1-3.
- Pre-routing a net locks the shortest path the grid router finds; that path ignores the pins around it.
  Pre-route only short, critical nets (USB, crystal, charger resistors), not buses that fan out (QSPI).
- Freerouting's result varies between attempts on the same board (run 8: 43, 8 and 7 open); three parallel
  attempts with different margins and keeping the best is a lottery, so it is a last step, never the fix.
- Recurring trouble spot: the charger group (U13 and its resistors) in the channel between key rows 2 and 3:
  ISET, ITERM, VSYS, PGOOD_N and a ground area have each failed there.
