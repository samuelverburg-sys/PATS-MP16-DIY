// Scales, note names and scale-degree arithmetic. Platform-free (no Arduino.h): tested on the host.
#pragma once

#include <stdint.h>

namespace mp16 {

constexpr int kScaleCount = 10;
constexpr int kScaleLength = 7;

// Scale names, each at most 9 characters so they fit the OLED next to "Scale: ".
extern const char* const kScaleNames[kScaleCount];

// Semitones from the root for each step of the scale.
extern const int kScaleIntervals[kScaleCount][kScaleLength];

// Scale steps of the chord tones 1, 3, 5, 7, 9, 11, 13 counted from the chord's degree.
extern const int kChordDegrees[7];

// "C-1" ... "G9". Out-of-range notes (below 0 or above 127) return "--".
const char* midiNoteName(int note);

// Semitones from the root of scale step `degree`, continuing into higher octaves past the 7th step.
// Example: Major, degree 9 (the 3rd one octave up) -> 16.
int degreeToScaleInterval(int degree, const int scale[], int scaleLength = kScaleLength);

}  // namespace mp16
