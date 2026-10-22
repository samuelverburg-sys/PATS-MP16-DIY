# PATS MP-16 DIY kit

A 16-pad MIDI chord controller: RP2040, 16 MX pads + Shift with RGB LEDs, encoder, 128x64 OLED, USB
MIDI and TRS MIDI In/Out. Two board revisions share one firmware:

- **Rev 1**: the original kit (Waveshare RP2040-Zero module, 4x4 key matrix). Hardware only as
  reference: `hardware/reference/rev1-*.easyeda.json`.
- **Rev 2**: this repo's board (bare RP2040, 74HC165 key chain, LiPo + charger). Spec and decisions:
  `docs/SPEC.md`. Generated from `hardware/mp16/design.py`.

## Layout

| Path | What |
|---|---|
| `firmware/MP16_*/` | Arduino sketches (Chordmaker = the main firmware, Boilerplate = template, YoutubeKeyboard) |
| `firmware/libraries/MP16/src/core/` | Plain C++ logic, **no `Arduino.h`**: chord engine, music theory, MIDI parser, key/encoder input. Host-tested |
| `firmware/libraries/MP16/src/board_pins.h` | **Every pin**, per board revision. The only place a pin number may appear |
| `firmware/libraries/MP16/src/MP16Board.*` | Hardware layer: keys (matrix or 74HC165), encoder, LEDs, OLED, MIDI UART, charger pins |
| `firmware/test/` | Host tests for `core/` (g++, ASan/UBSan) |
| `hardware/` | KiCad generator copied from PATS (`hardware/PATS-PIPELINE.md`); `mp16/design.py` is the source of truth |
| `enclosure/` | 3D-print STLs (Top, Midplate, Bottom, Switch, OLED standoff) and the KLE key layout |
| `scripts/` | Toolchain setup and firmware build |

## Commands

```sh
scripts/setup-arduino.sh                      # pinned arduino-cli 1.3.1 + arduino-pico 6.3.0 + libraries
scripts/build-firmware.sh                     # all sketches, both boards -> build/<rev>/<sketch>/*.uf2
scripts/build-firmware.sh rev2 MP16_Chordmaker
make -C firmware/test                         # host tests for core/ (run after any core change)

scripts/setup-kicad.sh                        # KiCad 7 (kicad-cli + pcbnew) and Freerouting
python3 hardware/build.py mp16 check          # netlist checks (seconds)
python3 hardware/build.py mp16 all            # check, sch, pcb, route, drc, review, fab
```

Cloud sessions run `.claude/hooks/session-start.sh`, which calls both setup scripts.
`downloads.arduino.cc` is blocked there; the setup script takes everything from GitHub instead.

## Rules

- **Pins live only in `board_pins.h`.** Rev 2 pins must match `hardware/mp16/design.py` (the
  `RP2040 pin allocation` table in `docs/SPEC.md` is the agreement between them). Never guess a pin.
- **`core/` stays platform-free**: no `Arduino.h`, no pins, no `delay`/`millis`. Hardware goes in
  `MP16Board`, UI in the sketch. Every change to `core/` ships with a test in `firmware/test/`.
- **Saved slots are raw structs** (`Settings`, `Pad` in `core/chord_engine.h`, rev-1 layout, guarded
  by `static_assert` on the RP2040). Never reorder, resize or insert fields; new data goes in a new file.
- MIDI data bytes are 0-127: clamp before sending. Notes outside 0-127 are skipped, not wrapped.
- USB stacks differ per sketch: USB MIDI needs Adafruit TinyUSB, `Keyboard` needs Pico SDK
  (`USBSTACK` in `scripts/build-firmware.sh`).
- Keep both revisions building: `scripts/build-firmware.sh` with no arguments before committing firmware.
- **Fixed positions (Samuel, 2026-10-22): never move** the key switches with their hot-swap sockets and
  LEDs, the encoder, the OLED module (J2), the TRS jacks (J4, J5), the power switch (SW20) or USB-C (J3):
  they must meet the enclosure and the plate. Everything else may be moved to make the board work.
- Hardware: change `design.py`, regenerate with `build.py`, never hand-edit the generated KiCad files.
  Ordering waits for the user's review; flashing a board is the user's step.
- Arduino-IDE users must keep working without the CLI: sketches compile with the IDE when the
  sketchbook location is set to `firmware/` (README.md).
