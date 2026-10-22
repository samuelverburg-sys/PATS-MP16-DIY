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
constexpr int kMidiTx = 0;   // UART0 TX -> MIDI Out jack
constexpr int kMidiRx = 1;   // UART0 RX <- MIDI In opto-coupler
constexpr int kLedData = 2;  // SK6812MINI-E chain: Shift, then pads 1-16
constexpr int kI2cSda = 4;   // OLED (0x3C); rev 2 also the MAX17048 fuel gauge (0x36)
constexpr int kI2cScl = 5;

#if MP16_BOARD_REV == 1
// Original kit, hardware/reference/rev1-schematic.easyeda.json
constexpr int kShift = 3;
constexpr int kEncoderSwitch = 6;
constexpr int kEncoderA = 7;
constexpr int kEncoderB = 8;
constexpr int kMatrixCols[4] = { 9, 10, 11, 12 };   // inputs with pull-up
constexpr int kMatrixRows[4] = { 13, 14, 15, 26 };  // driven low one at a time

#elif MP16_BOARD_REV == 2
// hardware/mp16/design.py (docs/SPEC.md, "RP2040 pin allocation")
constexpr int kEncoderA = 6;
constexpr int kEncoderB = 7;
constexpr int kShiftRegData = 16;  // 74HC165 Q7 (last chip in the chain)
constexpr int kShiftRegLoad = 17;  // 74HC165 /PL, all chips
constexpr int kShiftRegClock = 18; // 74HC165 CP, all chips; also clocks the expansion 74HC595
constexpr int kExpansionData = 19; // expansion header: 74HC595 SER (analog mux select)
constexpr int kExpansionLatch = 20;// expansion header: 74HC595 RCLK
constexpr int kPowerGoodN = 22;    // BQ24074 /PGOOD: low while USB power is present
constexpr int kAnalogIn[4] = { 26, 27, 28, 29 };  // expansion header AIN1-4 (ADC0-3)
// Charging state comes from the MAX17048 fuel gauge (I2C 0x36), not a pin: the charger's /CHG drives
// the charge LED from USB power and must not reach the RP2040 (it would feed it while switched off).
constexpr uint8_t kFuelGaugeAddress = 0x36;

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
