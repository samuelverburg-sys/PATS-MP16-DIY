// Key edges and the rotary encoder's quadrature decoding. Platform-free: tested on the host.
#pragma once

#include <stdint.h>

namespace mp16 {

// One key or button: the current and previous scan, so a sketch can ask for edges.
struct Button {
  bool down = false;
  bool wasDown = false;

  void update(bool nowDown) {
    wasDown = down;
    down = nowDown;
  }
  bool pressed() const { return down && !wasDown; }
  bool released() const { return !down && wasDown; }
};

// Gray-code decoder for the encoder's A and B lines. Call step() on every change of A or B (from
// the pin interrupt). 4 valid transitions make one detent on the PEC11R; bounces cancel out.
class QuadratureDecoder {
 public:
  static constexpr int kStepsPerDetent = 4;

  // a, b: current pin levels. Returns +1 or -1 when a detent completes, else 0.
  int step(bool a, bool b) {
    static const int8_t kTable[16] = { 0, -1, 1, 0, 1, 0, 0, -1, -1, 0, 0, 1, 0, 1, -1, 0 };
    uint8_t encoded = (uint8_t)((a ? 2 : 0) | (b ? 1 : 0));
    int delta = kTable[(last_ << 2) | encoded];
    last_ = encoded;
    steps_ += delta;
    quarterSteps_ += delta;
    if (steps_ >= kStepsPerDetent) { steps_ = 0; return 1; }
    if (steps_ <= -kStepsPerDetent) { steps_ = 0; return -1; }
    return 0;
  }

  // Quarter steps since the last call (fine adjustments: 4 per detent). Resets the detent progress.
  int takeQuarterSteps() {
    int q = quarterSteps_;
    quarterSteps_ = 0;
    steps_ = 0;
    return q;
  }

 private:
  uint8_t last_ = 0;
  int steps_ = 0;
  int quarterSteps_ = 0;
};

}  // namespace mp16
