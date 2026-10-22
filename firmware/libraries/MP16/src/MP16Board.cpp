#include "MP16Board.h"

#include <Wire.h>

namespace mp16 {

Board* activeBoard = nullptr;

static void encoderIsr() {
  if (activeBoard) activeBoard->onEncoderEdge();
}

bool Board::begin() {
  activeBoard = this;

#if MP16_BOARD_REV == 1
  for (int row : pins::kMatrixRows) {
    pinMode(row, OUTPUT);
    digitalWrite(row, HIGH);
  }
  for (int col : pins::kMatrixCols) pinMode(col, INPUT_PULLUP);
  pinMode(pins::kShift, INPUT_PULLUP);
  pinMode(pins::kEncoderSwitch, INPUT_PULLUP);
#else
  pinMode(pins::kShiftRegData, INPUT);
  pinMode(pins::kShiftRegLoad, OUTPUT);
  pinMode(pins::kShiftRegClock, OUTPUT);
  digitalWrite(pins::kShiftRegLoad, HIGH);
  digitalWrite(pins::kShiftRegClock, LOW);
  // Expansion 74HC595 lines: idle low so nothing is latched by accident.
  pinMode(pins::kExpansionData, OUTPUT);
  pinMode(pins::kExpansionLatch, OUTPUT);
  digitalWrite(pins::kExpansionData, LOW);
  digitalWrite(pins::kExpansionLatch, LOW);
  pinMode(pins::kChargingN, INPUT_PULLUP);  // open-drain outputs of the BQ24074
  pinMode(pins::kPowerGoodN, INPUT_PULLUP);
#endif

  // Rev 2 has 10k pull-ups and RC filters on the board; rev 1 relies on the internal pull-ups.
  pinMode(pins::kEncoderA, INPUT_PULLUP);
  pinMode(pins::kEncoderB, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(pins::kEncoderA), encoderIsr, CHANGE);
  attachInterrupt(digitalPinToInterrupt(pins::kEncoderB), encoderIsr, CHANGE);

  pixels.begin();
  pixels.setBrightness(100);
  pixels.clear();
  pixels.show();

  pinMode(pins::kMidiRx, INPUT_PULLUP);  // idle high when no cable is plugged in
  midi.setTX(pins::kMidiTx);
  midi.setRX(pins::kMidiRx);
  midi.begin(kMidiBaud);

  Wire.setSDA(pins::kI2cSda);
  Wire.setSCL(pins::kI2cScl);
  display.setRotation(2);  // the OLED is mounted upside down
  if (!display.begin(SSD1306_SWITCHCAPVCC, kOledAddress)) return false;
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.display();
  return true;
}

bool Board::readKeys(bool padsDown[16], bool& shiftDown, bool& encoderDown) {
#if MP16_BOARD_REV == 1
  shiftDown = !digitalRead(pins::kShift);
  encoderDown = !digitalRead(pins::kEncoderSwitch);
  for (int row = 0; row < 4; row++) {
    for (int r = 0; r < 4; r++) digitalWrite(pins::kMatrixRows[r], r == row ? LOW : HIGH);
    for (int col = 0; col < 4; col++) padsDown[row * 4 + col] = !digitalRead(pins::kMatrixCols[col]);
  }
  digitalWrite(pins::kMatrixRows[3], HIGH);
#else
  // Parallel load (/PL low), then shift 24 bits out of the chain, MSB (U1 D7) first.
  digitalWrite(pins::kShiftRegLoad, LOW);
  delayMicroseconds(1);
  digitalWrite(pins::kShiftRegLoad, HIGH);
  uint32_t bits = 0;
  for (int i = 0; i < pins::kShiftRegBits; i++) {
    bits = (bits << 1) | (digitalRead(pins::kShiftRegData) ? 1u : 0u);
    digitalWrite(pins::kShiftRegClock, HIGH);
    delayMicroseconds(1);
    digitalWrite(pins::kShiftRegClock, LOW);
  }
  auto down = [bits](int bit) { return ((bits >> bit) & 1u) == 0; };  // pressed = pulled low
  for (int p = 0; p < 16; p++) padsDown[p] = down(pins::kSrPadBit[p]);
  shiftDown = down(pins::kSrShiftBit);
  encoderDown = down(pins::kSrEncoderSwitchBit);
#endif
  return true;
}

void Board::scan() {
  bool padsDown[16];
  bool shiftDown = false;
  bool encoderDown = false;
  readKeys(padsDown, shiftDown, encoderDown);
  for (int i = 0; i < 16; i++) pads_[i].update(padsDown[i]);
  shift_.update(shiftDown);
  encoderButton_.update(encoderDown);
}

void Board::onEncoderEdge() {
  detents_ += decoder_.step(digitalRead(pins::kEncoderA), digitalRead(pins::kEncoderB));
}

int Board::takeEncoderDetents() {
  noInterrupts();
  int d = detents_;
  detents_ = 0;
  decoder_.takeQuarterSteps();
  interrupts();
  return d;
}

int Board::takeEncoderQuarterSteps() {
  noInterrupts();
  int q = decoder_.takeQuarterSteps();
  detents_ = 0;
  interrupts();
  return q;
}

bool Board::isCharging() const {
#if MP16_BOARD_REV >= 2
  return digitalRead(pins::kChargingN) == LOW;
#else
  return false;
#endif
}

bool Board::isUsbPowered() const {
#if MP16_BOARD_REV >= 2
  return digitalRead(pins::kPowerGoodN) == LOW;
#else
  return false;
#endif
}

uint32_t dimColor(uint32_t color, float factor) {
  uint8_t r = (uint8_t)(((color >> 16) & 0xFF) * factor);
  uint8_t g = (uint8_t)(((color >> 8) & 0xFF) * factor);
  uint8_t b = (uint8_t)((color & 0xFF) * factor);
  return ((uint32_t)r << 16) | ((uint32_t)g << 8) | b;
}

}  // namespace mp16
