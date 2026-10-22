# Ordering checklist: MP-16 rev 2 (manual checks)

Everything the build can check (netlist, DRC, placement, decoupling and power-track review, firmware
pins) is done by `python3 build.py mp16 all` (expect `drc: 0 errors, 0 unconnected`) and
`python3 ../scripts/check-pins.py`. What still needs a person, per order:

## Before uploading

- [ ] **Hardware review**: walk through `mp16/mp16.kicad_sch` and `docs/SPEC.md` together; the open fit checks
      in `README.md` (USB-C height in the enclosure opening, expansion header vs. plate).
- [ ] **LCSC numbers**: `mp16/PARTS.md` lists every part with the source of its LCSC number. Check each
      **unverified** line and choose a part for each "none" line (odd values: 3k ISET, 180 R + 1k ILIM,
      4.12k ITERM need 1 % parts, not the nearest basic value; 10 uF 0603 at 6.3 V or more; the polyfuse
      1206, 1.5 A hold, 6 V or more; 75k 0402). Prefer JLCPCB basic parts for the passives.
- [ ] **Battery plug**: J7 (JST PH) has **pin 1 = GND**, as rev 1. The board survives a reversed pack
      (`docs/decisions/0001-battery-reverse-protection.md`) but will not run from it.

## At JLCPCB, after uploading

- [ ] **Board options**: 2 layers, 1.6 mm, 1 oz, ENIG recommended (0.4 mm-pitch RP2040); assembly side
      **bottom** (every assembled part is on the bottom).
- [ ] **Gerber viewer**: outline and the six holes; the LED cut-outs under the reverse-mount SK6812MINI-E.
- [ ] **Placement preview, every part's rotation** (KiCad and JLCPCB disagree on some packages). Pin 1 above
      all on: RP2040 (U10), W25Q128 (U11), BQ24074 (U13), MAX17048 (U15), TPS22917 (U16), AP2112K (U17),
      MT3608 (U18), TLP109 (U19), USBLC6 (U12, U20), 74HC165 (U1-U3), 74AHCT1G125 (U4), crystal (Y1),
      Q1 and Q2; polarity on D21 (SS34), D22 (1N4148W), the charge LED D20 and the 17 SK6812MINI-E;
      USB-C (J3), both jacks (J4, J5) and the power switch (SW20) opening towards the top edge; the 17
      hot-swap sockets (SW1-SW17, C41430893) each under its key, right way round.
- [ ] **BOM matching**: every line matched, quantities right, nothing left unplaced except the hand-solder list.

## Hand-solder (not in the assembly files)

Encoder (ENC1), OLED header (J2, 1x4 socket), battery plug (J7, JST S2B-PH-K-S, C173752, through-hole),
optional expansion header (J6, 2x6 2.54 mm), the MX switches into the hot-swap sockets.

## When the boards arrive

- [ ] Battery pack polarity with a meter before plugging it in (red = pin 2, +).
- [ ] First power from USB without battery and with the switch off: the charge LED stays off without a
      battery or flickers (charger probing), nothing gets warm. Switch on: 3.3 V and VLED (5.1 V) present.
- [ ] Hold BOOT, press RESET: the RP2 drive appears. Flash `MP16_Boilerplate` (rev 2 build) and check
      every key, the encoder, the LEDs and the OLED.
- [ ] Reverse-polarity test with a bench supply instead of the battery (decision 0001, last section).
- [ ] OLED module pin order before plugging it in: the socket is SDA, SCL, VCC, GND left to right (as rev 1,
      for the HS96L03W2C03); other modules swap VCC and GND.
- [ ] MIDI: Out into a synth (Type A TRS adapter), In from a keyboard with Thru on in the MIDI menu.
