# 0001: Reverse-polarity protection for the battery

Decided 2026-10-22 (Samuel asked for reverse-polarity protection; generic JST-PH LiPo packs are the reference).

## The problem

Cheap 1S LiPo packs with a JST-PH plug come wired both ways round: there is no standard. A pack the
wrong way round must not damage the board, and above all must never be charged backwards (a LiPo
charged in reverse can vent or burn).

## Why one MOSFET is not enough

The usual protection is a P-MOSFET in the battery's + lead with its gate tied to ground. With the
battery the right way round, the body diode conducts first, the gate is then well below the source and
the MOSFET turns fully on, in both directions (discharge and charge). With a reversed pack and **no USB**
the gate is not below the source and the body diode is reverse-biased: blocked. But with a reversed pack
**and USB plugged in**, the charger holds its battery pin at ~4.2 V: the gate (0 V) is now far below the
source, the MOSFET turns on, and the charger pushes current into the reversed cell. The same happens with
any single-MOSFET variant whose gate is referred to the board's ground.

## What the board does

Q1 (DMG2305UX P-MOSFET) in the + lead as above, plus Q2 (MMBT3906 PNP): emitter on VBAT (the
charger's battery pin, Q1's source), collector on Q1's gate, base on the battery connector's + pin
through 100 k. R26 (100 k) pulls Q1's gate to ground.

| Case | Q2 | Q1 | Result |
|---|---|---|---|
| Battery right way round (USB or not) | base ~ emitter: off | gate at 0 V: on | normal use and charging |
| Reversed, no USB | base below emitter: on, gate pulled to VBAT (~0 V) | gate = source: off, body diode reverse-biased | nothing flows (< 40 uA through Q2's base resistor) |
| Reversed, USB present | base far below emitter: on, gate pulled to VBAT | off, body diode reverse-biased | charger isolated from the cell |
| No battery, USB present | off | on | VBAT appears on the connector (harmless) |

Q2's base current with a reversed pack is under 0.1 mA through the 100 k. Charging (0.3 A) drops ~15 mV
across Q1, far below Q2's turn-on.

## To check on the first boards

- With a bench supply in place of the battery (current limit 50 mA): reversed, with and without USB:
  no current, VBAT stays at the charger's level, the supply sees no reverse current.
- Right way round: the board runs from the supply, and charges into it with USB.
