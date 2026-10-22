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
| Power | **Battery kept, improved**: 1S LiPo on JST-PH, BQ24074 charger with power path (runs from USB while charging), **reverse-polarity protection** on the battery, slide switch + TPS22917 load switch, MAX17048 fuel gauge, AP2112K 3.3 V, MT3608 5 V boost for the LEDs. Reused from the PATS audio board |
| MIDI | **3.5 mm TRS Type A**, two jacks as now: In (opto-isolated) and Out. **Thru is a firmware option** (Out echoes In), no third jack, no enclosure change |
| Analog expansion | **Header only**: the RP2040's 4 ADC inputs, 74HC595 select lines (shared clock with the 74HC165 chain), I2C and power, for a future pot/fader board. Replaces the old 3-pin H1 |
| Tooling | KiCad, generated from Python with a **copy of the PATS hardware pipeline** (`build.py`, `tools/`, `lib/`), PATS commit recorded |
| Firmware | **Platform-free C++ core with host tests**, wrapped by Arduino (arduino-pico) sketches. One hardware layer, two board configs: the original kit (rev 1, RP2040-Zero, key matrix) and this board (rev 2) |
| Claude | CLAUDE.md, docs, pinned arduino-cli build, SessionStart hook so cloud sessions can build and test |
| Repo | New repo `PATS-MP16-DIY`, fresh history |

## RP2040 pin allocation (proposal)

Rev 1 pins are kept wherever the function still exists, so the rev-1 and rev-2 board configs differ only where the hardware does.

| GPIO | Net | Function | Rev 1 (RP2040-Zero) |
|---|---|---|---|
| GP0 | MIDI_TX | UART0 TX -> MIDI Out (and soft Thru) | same |
| GP1 | MIDI_RX | UART0 RX <- MIDI In opto | same |
| GP2 | LED_DATA | SK6812 chain, via 74AHCT1G125 | same (no shifter) |
| GP4 | I2C_SDA | I2C0: OLED 0x3C, MAX17048 0x36, expansion | same (Wire default) |
| GP5 | I2C_SCL | I2C0 | same |
| GP6 | ENC_A | encoder A | GP7 on rev 1 (rev 1 GP6 = encoder switch) |
| GP7 | ENC_B | encoder B | GP8 on rev 1 |
| GP16 | SR_DATA | SPI0 RX <- 74HC165 Q7 | rev 1: matrix |
| GP17 | SR_LOAD | 74HC165 /PL | rev 1: matrix |
| GP18 | SR_CLK | SPI0 SCK -> 74HC165 CP and expansion 74HC595 SRCLK | rev 1: matrix |
| GP19 | EXP_MOSI | SPI0 TX -> expansion 74HC595 SER | new |
| GP20 | EXP_LATCH | expansion 74HC595 RCLK | new |
| GP21 | CHG_N | BQ24074 /CHG (charging) | new |
| GP22 | PGOOD_N | BQ24074 /PGOOD (USB power present) | new |
| GP26-29 | AIN1-4 | ADC0-3 -> expansion header | GP26 was matrix row 3 |
| GP3, 8-15, 23-25 | spare | test pads | |

The encoder push and Shift go through the 74HC165 chain, as on the UI board.

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
