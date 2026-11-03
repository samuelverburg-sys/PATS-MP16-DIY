// Battery state from its voltage (rev 2: VBAT / 2 into ADC3, board_pins.h kBatterySense). Platform-free.
//
// A 1S LiPo's resting voltage maps to its charge only roughly (the curve is flat around 3.8 V and the
// voltage sags under load), so treat the percentage as a gauge with 5 % steps, not a measurement.
#pragma once

#include <stdint.h>

namespace mp16 {

// Battery millivolts from a raw ADC reading: `bits` resolution, `vrefMv` full scale, `ratio` divider
// (VBAT / ratio at the pin).
int batteryMillivoltsFromAdc(uint32_t raw, int bits, int vrefMv, int ratio);

// 0-100 from millivolts: linear between the points of a typical 1S LiPo discharge curve; 100 at 4.20 V and
// above, 0 at 3.30 V and below.
int lipoPercent(int millivolts);

// Charging, as far as the voltage can tell: USB present and the cell not yet near full (the charger
// holds 4.2 V at the end; above 4.15 V it is finishing or done).
bool likelyCharging(bool usbPresent, int millivolts);

// Smooths readings (exponential, 1/8 per sample) so the shown percentage does not flicker with load.
class BatteryFilter {
 public:
  int update(int millivolts);  // returns the smoothed value; the first sample is taken as is
  int value() const { return mv_; }

 private:
  int mv_ = -1;
};

}  // namespace mp16
