#include "battery.h"

namespace mp16 {

namespace {
struct Point {
  int mv;
  int percent;
};
// Typical 1S LiPo resting voltage against remaining charge (generic pack data), highest first.
constexpr Point kCurve[] = {
    {4200, 100}, {4150, 95}, {4110, 90}, {4080, 85}, {4020, 80}, {3980, 75}, {3950, 70},
    {3910, 65},  {3870, 60}, {3850, 55}, {3840, 50}, {3820, 45}, {3800, 40}, {3790, 35},
    {3770, 30},  {3750, 25}, {3730, 20}, {3710, 15}, {3690, 10}, {3610, 5},  {3300, 0},
};
constexpr int kPoints = sizeof(kCurve) / sizeof(kCurve[0]);
}  // namespace

int batteryMillivoltsFromAdc(uint32_t raw, int bits, int vrefMv, int ratio) {
  if (bits <= 0 || bits > 24) return 0;
  const uint32_t full = (1u << bits) - 1;
  if (raw > full) raw = full;
  return (int)((uint64_t)raw * (uint64_t)vrefMv * (uint64_t)ratio / full);
}

int lipoPercent(int millivolts) {
  if (millivolts >= kCurve[0].mv) return 100;
  if (millivolts <= kCurve[kPoints - 1].mv) return 0;
  for (int i = 1; i < kPoints; ++i) {
    const Point& hi = kCurve[i - 1];
    const Point& lo = kCurve[i];
    if (millivolts >= lo.mv) {
      return lo.percent + (millivolts - lo.mv) * (hi.percent - lo.percent) / (hi.mv - lo.mv);
    }
  }
  return 0;
}

bool likelyCharging(bool usbPresent, int millivolts) { return usbPresent && millivolts > 0 && millivolts < 4150; }

int BatteryFilter::update(int millivolts) {
  if (mv_ < 0) {
    mv_ = millivolts;
  } else {
    mv_ += (millivolts - mv_) / 8;
  }
  return mv_;
}

}  // namespace mp16
