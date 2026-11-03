// Every pin of both MP-16 boards. This is the only place a pin number may appear in the firmware.
//
// The board revision is picked from the Arduino board you compile for:
//   Tools > Board > "Waveshare RP2040 Zero"  -> rev 1 (the original kit: RP2040-Zero, 4x4 key matrix)
//   Tools > Board > "Generic RP2040"         -> rev 2 (bare RP2040, 74HC165 key chain, battery)
// or forced with -DMP16_BOARD_REV=1 / 2 (arduino-cli --build-property "build.extra_flags=...").
#pragma once

#include <stdint.h>

#ifndef MP16_BOARD_REV
#if defined(ARDUINO_WAVESHARE_RP2040_ZERO)
#define MP16_BOARD_REV 1
#else
#define MP16_BOARD_REV 2
#endif
#endif

namespace mp16 {
namespace pins {

// Shared by both revisions
constexpr int kLedData = 2;  // SK6812MINI-E chain: Shift, then pads 1-16

#if MP16_BOARD_REV == 1
// Original kit, hardware/reference/rev1-schematic.easyeda.json
constexpr int kMidiUart = 0;  // UART0 (Serial1)
constexpr int kMidiTx = 0;    // UART0 TX -> MIDI Out jack
constexpr int kMidiRx = 1;    // UART0 RX <- MIDI In opto-coupler
constexpr int kI2cSda = 4;    // I2C0: OLED (0x3C)
constexpr int kI2cScl = 5;
constexpr int kShift = 3;
constexpr int kEncoderSwitch = 6;
constexpr int kEncoderA = 7;
constexpr int kEncoderB = 8;
constexpr int kMatrixCols[4] = { 9, 10, 11, 12 };   // inputs with pull-up
constexpr int kMatrixRows[4] = { 13, 14, 15, 26 };  // driven low one at a time

#elif MP16_BOARD_REV == 2
// hardware/mp16/design.py (docs/SPEC.md, "RP2040 pin allocation"). The RP2040 sits on the bottom, so seen
// from above GPIO0-11 face right and GPIO18-29 left: each signal is on the side it leaves towards.
constexpr int kMidiUart = 1;  // UART1 (Serial2)
constexpr int kMidiTx = 8;    // UART1 TX -> MIDI Out jack (right)
constexpr int kMidiRx = 21;   // UART1 RX <- MIDI In opto-coupler (left)
constexpr int kI2cSda = 12;   // I2C0: OLED (0x3C) and the Qwiic connector J6; bottom edge, towards the OLED
constexpr int kI2cScl = 13;
constexpr int kEncoderA = 23;  // left, towards the encoder; A on the upper pin of the two, as the encoder's
constexpr int kEncoderB = 22;  // A is the farther pin (their tracks would cross the other way round)
constexpr int kShiftRegData = 16;  // 74HC165 Q7 (last chip in the chain)
constexpr int kShiftRegLoad = 17;  // 74HC165 /PL, all chips
constexpr int kShiftRegClock = 18; // 74HC165 CP, all chips
constexpr int kPowerGoodN = 3;     // BQ24074 /PGOOD: low while USB power is present
constexpr int kBatterySense = 29;  // ADC3: VBAT / 2 (1M + 1M divider, 100 nF), as the Pico's VSYS sense
constexpr int kBatteryDivider = 2;
// Charging is estimated from /PGOOD and the voltage (core/battery.h): the charger's /CHG drives the charge
// LED from USB power and must not reach the RP2040 (it would feed it while switched off).
// GPIO19, 20, 26-28 are free (the 2x6 expansion header became a 4-pin I2C connector, 2026-11-03).

// Bit positions in the 24 bits read from the 74HC165 chain, first bit read = bit 23.
// Chain (hardware/mp16/design.py): U3 (Shift, encoder push, spares) is nearest the RP2040, then U1
// (pads 1-8, between key rows 1 and 2), then U2 (pads 9-16, between rows 3 and 4).
// Input Dn of U3 comes out as bit 16 + n, of U1 as 8 + n, of U2 as n. All inputs are low while pressed.
constexpr int kShiftRegBits = 24;
constexpr int kSrPadBit[16] = { 8, 9, 10, 11, 12, 13, 14, 15,   // U1 D0-D7: pads 1-8
                                0, 1, 2, 3, 4, 5, 6, 7 };       // U2 D0-D7: pads 9-16
constexpr int kSrShiftBit = 16;          // U3 D0
constexpr int kSrEncoderSwitchBit = 17;  // U3 D1
#else
#error "MP16_BOARD_REV must be 1 or 2"
#endif

}  // namespace pins
}  // namespace mp16
