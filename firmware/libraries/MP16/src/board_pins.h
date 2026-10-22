// Every pin of both MP-16 boards. This is the only place a pin number may appear in the firmware.
//
// The board revision is picked from the Arduino board you compile for:
//   Tools > Board > "Waveshare RP2040 Zero"  -> rev 1 (the original kit: RP2040-Zero, 4x4 key matrix)
//   Tools > Board > "Generic RP2040"         -> rev 2 (bare RP2040, 74HC165 key chain, battery)
// or forced with -DMP16_BOARD_REV=1 / 2 (arduino-cli --build-property "build.extra_flags=...").
#pragma once

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
constexpr int kChargingN = 21;     // BQ24074 /CHG: low while the battery charges
constexpr int kPowerGoodN = 22;    // BQ24074 /PGOOD: low while USB power is present
constexpr int kAnalogIn[4] = { 26, 27, 28, 29 };  // expansion header AIN1-4 (ADC0-3)

// Bit positions in the 24 bits read from the 74HC165 chain, first bit read = bit 23.
// U1 (pads 1-8) is nearest the RP2040, so its D7 comes out first; then U2 (pads 9-16), then U3.
// Input Dn of a chip comes out as bit (base + n). All inputs are low while pressed.
constexpr int kShiftRegBits = 24;
constexpr int kSrPadBit[16] = { 16, 17, 18, 19, 20, 21, 22, 23,   // U1 D0-D7: pads 1-8
                                8, 9, 10, 11, 12, 13, 14, 15 };   // U2 D0-D7: pads 9-16
constexpr int kSrShiftBit = 0;          // U3 D0
constexpr int kSrEncoderSwitchBit = 1;  // U3 D1
#else
#error "MP16_BOARD_REV must be 1 or 2"
#endif

}  // namespace pins
}  // namespace mp16
