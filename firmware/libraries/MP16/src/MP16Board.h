// The MP-16 hardware, the same for every sketch and both board revisions: 16 pads + Shift, the
// encoder (turn and push), 17 RGB LEDs, the OLED and the MIDI jacks. USB is left to the sketch
// (USB MIDI and USB keyboard need different USB stacks).
//
//   #include <MP16.h>
//   mp16::Board board;
//   void setup() { board.begin(); }
//   void loop()  { board.scan(); if (board.pad(0).pressed()) ...; board.pixels.show(); }
#pragma once

#include <Arduino.h>
#include <Adafruit_NeoPixel.h>
#include <Adafruit_SSD1306.h>

#include "board_pins.h"
#include "core/input.h"

namespace mp16 {

constexpr int kPixelCount = 17;  // pixel 0 = Shift, pixel 1 + n = pad n
constexpr int kScreenWidth = 128;
constexpr int kScreenHeight = 64;
constexpr uint8_t kOledAddress = 0x3C;
constexpr uint32_t kMidiBaud = 31250;

inline int padPixel(int pad) { return pad + 1; }

class Board {
 public:
  Adafruit_NeoPixel pixels{ kPixelCount, pins::kLedData, NEO_GRB + NEO_KHZ800 };
  Adafruit_SSD1306 display{ kScreenWidth, kScreenHeight, &Wire, -1 };
  SerialUART& midi = Serial1;  // the MIDI In and Out jacks (UART0), 31250 baud

  // Pins, LEDs (off), OLED (blank, upside down as mounted), MIDI UART, encoder interrupts.
  // Returns false if the OLED does not answer (the rest still works).
  bool begin();

  // Read all keys and the encoder push once; call at the start of every loop().
  void scan();

  const Button& pad(int i) const { return pads_[i]; }  // pads 0-15 (labelled 1-16)
  const Button& shift() const { return shift_; }
  const Button& encoderButton() const { return encoderButton_; }

  // Encoder turns since the last call: detents (one click = 1), or quarter steps (4 per click,
  // for fine adjustments). Positive = clockwise. Taking one also clears the other.
  int takeEncoderDetents();
  int takeEncoderQuarterSteps();

  // Battery and charger (rev 2 only; rev 1 reports no USB power information).
  bool hasChargerStatus() const { return MP16_BOARD_REV >= 2; }
  bool isCharging() const;
  bool isUsbPowered() const;

  static constexpr int revision() { return MP16_BOARD_REV; }

  // Called from the encoder pin interrupt.
  void onEncoderEdge();

 private:
  bool readKeys(bool padsDown[16], bool& shiftDown, bool& encoderDown);

  Button pads_[16];
  Button shift_;
  Button encoderButton_;
  QuadratureDecoder decoder_;
  volatile int detents_ = 0;
};

// The board the sketch uses (defined in MP16Board.cpp), for the encoder interrupt.
extern Board* activeBoard;

// Scale a 0xRRGGBB colour, e.g. dimColor(c, 0.3) for an unselected pad.
uint32_t dimColor(uint32_t color, float factor);

}  // namespace mp16
