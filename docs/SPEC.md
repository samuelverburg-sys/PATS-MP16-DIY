# PATS MP-16 DIY: rev 2 hardware and firmware spec

Status: **agreed 2026-10-22** (interview with Samuel; open points settled the same day).

Sources: the original kit (github.com/samuelverburg/MP16-DIY-Kit, EasyEDA project "PATS MP-16 Waveshare"),
and the PATS UI and audio boards (github.com/samuelverburg-sys/PATS, `pats-core/hardware/`).

## Decisions from the interview

| Topic | Decision |
|---|---|
| Board count | **One board**, MP-16 outline (76.2 x 104.775 mm), six 2.5 mm holes at the MP-16 positions, fits the existing enclosure |
| Front-end | **Copied from the PATS UI board**: 3x 74HC165 (16 pads + Shift + encoder push + 6 spare, no matrix, no ghosting), 74AHCT1G125 LED level shifter, PEC11R encoder with RC filters, OLED socket |
| Keys and LEDs | Kailh CPG151101S11 MX hot-swap sockets, SK6812MINI-E reverse-mount (as both boards today) |
| MCU | **Bare RP2040** on the board (replaces the RP2040-Zero), QSPI flash, 12 MHz crystal, BOOT + RESET buttons, SWD pads |
| USB | USB-C (data + charging), USBLC6-2SC6 ESD, polyfuse |
| Power | **Battery kept, improved**: 1S LiPo on JST-PH, BQ24074 charger with power path (runs from USB while charging), **reverse-polarity protection** on the battery, slide switch + TPS22917 load switch, battery voltage divider into ADC3 (Samuel 2026-11-03: instead of the MAX17048 gauge), AP2112K 3.3 V, MT3608 5 V boost for the LEDs. Reused from the PATS audio board |
| MIDI | **3.5 mm TRS Type A**, two jacks as now: In (opto-isolated) and Out. **Thru is a firmware option** (Out echoes In), no third jack, no enclosure change |
| Expansion | **4-pin I2C connector** (JST SH 1.0 mm, Qwiic / STEMMA QT: GND, 3V3, SDA, SCL), SMD on the bottom (Samuel 2026-11-03, instead of the 2x6 header with analog inputs and mux lines, whose tracks failed in 4 of 9 routes). Add-ons (ADC, multiplexer, pots) sit on the I2C bus. Replaces the old 3-pin H1 |
| Tooling | KiCad, generated from Python with a **copy of the PATS hardware pipeline** (`build.py`, `tools/`, `lib/`), PATS commit recorded |
| Firmware | **Platform-free C++ core with host tests**, wrapped by Arduino (arduino-pico) sketches. One hardware layer, two board configs: the original kit (rev 1, RP2040-Zero, key matrix) and this board (rev 2) |
| Claude | CLAUDE.md, docs, pinned arduino-cli build, SessionStart hook so cloud sessions can build and test |
| Repo | New repo `PATS-MP16-DIY`, fresh history |

## RP2040 pin allocation (proposal)

The board layer picks the pins (and the UART) per revision from `board_pins.h`.

| GPIO | Net | Function | Rev 1 (RP2040-Zero) |
|---|---|---|---|
| GP2 | LED_DATA | SK6812 chain, via 74AHCT1G125 | same (no shifter) |
| GP3 | PGOOD_N | BQ24074 /PGOOD (USB power present) | new |
| GP8 | MIDI_TX | UART1 TX -> MIDI Out (and soft Thru) | GP0, UART0 |
| GP12 | I2C_SDA | I2C0: OLED 0x3C, Qwiic connector J6 | GP4 |
| GP13 | I2C_SCL | I2C0 | GP5 |
| GP16 | SR_DATA | 74HC165 Q7 (U3, nearest the RP2040) | rev 1: matrix |
| GP17 | SR_LOAD | 74HC165 /PL | rev 1: matrix |
| GP18 | SR_CLK | 74HC165 CP | rev 1: matrix |
| GP19 | - | free | |
| GP20 | - | free | |
| GP21 | MIDI_RX | UART1 RX <- MIDI In opto | GP1, UART0 |
| GP22 | ENC_B | encoder B | GP8 |
| GP23 | ENC_A | encoder A (the upper pin of the two: the tracks to the encoder do not cross) | GP7 |
| GP26-28 | - | free (ADC0-2) | GP26 was matrix row 3 |
| GP29 | BAT_SENSE | ADC3: VBAT / 2 (1M + 1M, 100 nF), as the Pico's VSYS sense | new |
| GP0, 1, 4-7, 9-11, 14, 15, 24, 25 | spare | not connected | |

Why these pins (2026-11-03): the RP2040 sits on the bottom, so seen from above GPIO0-11 face right, 12-17 down
and 18-29 left. Each signal leaves on the side it goes to (MIDI In and the encoder on the left, MIDI Out and the
LEDs on the right, the OLED below); with the first allocation the router left the wrapped-around lines open.

The encoder push and Shift go through the 74HC165 chain, as on the UI board. Chain order (nearest the
RP2040 first): U3 (Shift, encoder push, 6 spares; top band), U1 (pads 1-8; between key rows 1 and 2),
U2 (pads 9-16; between rows 3 and 4). `scripts/check-pins.py` checks `board_pins.h` against `design.py`.

Charging is estimated from /PGOOD and the battery voltage (`core/battery.h`), not read from the charger's /CHG pin: /CHG drives the
charge LED from USB power, and a wire from it to a GPIO would feed the switched-off RP2040 through the
LED.

## Board layout constraints

- The key area (y > ~30 mm) is unchanged from the UI board: keys, LEDs, decoupling, all on the bottom.
- The top band (y 0-30 mm) gets the RP2040, flash, crystal, power, USB-C and MIDI. It is where the RP2040-Zero, charger and jacks sat on rev 1, and where the UI board had its 26-pin connector.
- **USB-C, both TRS jacks and the power switch must land on the enclosure's existing openings.** Their positions are taken from the rev-1 EasyEDA PCB and checked against `STLs/` by script.
- Single-sided assembly (all SMD on the bottom for JLCPCB); encoder, OLED header and switches hand-soldered on top, as the UI board.

## Settled points (2026-10-22)

1. **Flash: W25Q128JV, 16 MB** (rev 1 had 2 MB). Arduino: "Generic RP2040", 16MB (Sketch: 2MB, FS: 14MB),
   boot stage 2 "W25Q080 QSPI /2" (the W25Q080 stage works for the whole W25Q family).
2. **MIDI Out stays 3.3 V**: 2x 33 R from the RP2040's 3.3 V, as rev 1 and the MIDI 1.0 3.3 V
   recommendation.
3. **Battery: cheap generic 1S LiPo packs with a JST-PH 2.0 plug** are the reference. There is no
   official polarity standard for these plugs and generic packs vary, so: the rev-1 pinout is kept (the
   packs used with rev 1 fit unchanged), polarity is printed on both sides of the board, and the
   reverse-polarity protection makes a pack wired the other way harmless (it simply does not power or
   charge; swap its two crimp contacts). The manual says to check a new pack with a meter first.
4. **Firmware structure**: Arduino stays the way to build and flash (the IDE opens the sketches as
   before). The logic that is not about pins (chords, scales, MIDI parsing, key and encoder events) is
   plain C++ in `firmware/libraries/MP16/src/core/`, which Arduino compiles like any other file and
   which is also tested on a PC (`make -C firmware/test`).
