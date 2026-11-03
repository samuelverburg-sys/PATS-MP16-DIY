# 0002: 4 layers, a Qwiic connector, a battery divider (2026-11-03)

Decided by Samuel after a data review of 13 routing runs (`hardware/mp16/ROUTING-LOG.md`).

## 4 layers, one assembly side (was: 2 layers preferred)

- On 2 layers the board only routed with 14 parts on the top side (the RP2040's capacitors, flash, crystal,
  the encoder's pull-ups and filters), which needs double-sided assembly at JLCPCB: Standard PCBA at $50
  setup for two sides against $8 for Economic PCBA on one side (JLCPCB price page, Sept. 2025).
- After 12 runs the 2-layer board still had 2-3 open connections and ground-pour islands (up to 10).
  4 layers with every part on the bottom reached 1 open connection on the first full run, with a solid
  ground plane under the RP2040, USB and the boost converter.
- The 2-layer variant stays buildable: `MP16_LAYERS=2` (parts on top follow `MP16_MCU_SIDE`).

## A 4-pin I2C connector instead of the 2x6 expansion header

- The header's analog lines failed in 4 of 9 routes; it took 16 x 6 mm of through-hole space where the
  encoder, MIDI In and RP2040 lines meet, and no add-on exists yet.
- J6 is now a JST SH 1.0 mm (Qwiic / STEMMA QT pinout: GND, 3V3, SDA, SCL), SMD on the bottom and assembled.
  Add-ons put an ADC or multiplexer on the I2C bus. GPIO19, 20 and 26-28 are free.

## A voltage divider instead of the MAX17048 fuel gauge

- VBAT / 2 (1M + 1M, 100 nF) into ADC3 (GPIO29). Percent from the voltage (`core/battery.h`, host-tested):
  roughly 5 % steps instead of the gauge's model. Charging is estimated (USB present, cell below 4.15 V);
  the charge LED still shows the charger's real state. 2 uA drain from the pack, also when switched off.
- Removed: U15 (MAX17048), its capacitor, link resistor and alert test pad.

## Kept after review

- **5 V LED boost**: the SK6812MINI-E is specified for 3.7-5.5 V (OPSCO datasheet); a LiPo spends about
  half its charge below 3.7 V, so the LEDs need the boost.
- Bare RP2040 (Samuel: disagreed with a module), fixed positions, the 74HC165 chain, 3.3 V MIDI, 16 MB flash.
