#include "music_theory.h"

namespace mp16 {

const char* const kScaleNames[kScaleCount] = {
  "Major",      // Major (Ionian)
  "MinNatur",   // Natural Minor (Aeolian)
  "Dorian",     // Dorian
  "Phrygian",   // Phrygian
  "Lydian",     // Lydian
  "Mixolydi",   // Mixolydian
  "Locrian",    // Locrian
  "WholeTon",   // Whole Tone
  "HarmonMin",  // Harmonic Minor
  "PhrygDom"    // Phrygian Dominant
};

const int kScaleIntervals[kScaleCount][kScaleLength] = {
  { 0, 2, 4, 5, 7, 9, 11 },   // Major scale (Ionian)
  { 0, 2, 3, 5, 7, 8, 10 },   // Natural Minor (Aeolian)
  { 0, 2, 3, 5, 7, 9, 10 },   // Dorian
  { 0, 1, 3, 5, 7, 8, 10 },   // Phrygian
  { 0, 2, 4, 6, 7, 9, 11 },   // Lydian
  { 0, 2, 4, 5, 7, 9, 10 },   // Mixolydian
  { 0, 1, 3, 5, 6, 8, 10 },   // Locrian
  { 0, 2, 4, 6, 8, 10, 12 },  // Whole Tone (6 notes; the 7th step is the octave)
  { 0, 2, 4, 5, 7, 8, 11 },   // Harmonic Minor
  { 0, 1, 4, 5, 7, 8, 11 }    // Phrygian Dominant
};

const int kChordDegrees[7] = { 0, 2, 4, 6, 8, 10, 12 };

static const char* const kNoteNames[128] = {
  "C-1", "C#-1", "D-1", "D#-1", "E-1", "F-1", "F#-1", "G-1", "G#-1", "A-1", "A#-1", "B-1",  // 0-11
  "C0", "C#0", "D0", "D#0", "E0", "F0", "F#0", "G0", "G#0", "A0", "A#0", "B0",              // 12-23
  "C1", "C#1", "D1", "D#1", "E1", "F1", "F#1", "G1", "G#1", "A1", "A#1", "B1",              // 24-35
  "C2", "C#2", "D2", "D#2", "E2", "F2", "F#2", "G2", "G#2", "A2", "A#2", "B2",              // 36-47
  "C3", "C#3", "D3", "D#3", "E3", "F3", "F#3", "G3", "G#3", "A3", "A#3", "B3",              // 48-59
  "C4", "C#4", "D4", "D#4", "E4", "F4", "F#4", "G4", "G#4", "A4", "A#4", "B4",              // 60-71
  "C5", "C#5", "D5", "D#5", "E5", "F5", "F#5", "G5", "G#5", "A5", "A#5", "B5",              // 72-83
  "C6", "C#6", "D6", "D#6", "E6", "F6", "F#6", "G6", "G#6", "A6", "A#6", "B6",              // 84-95
  "C7", "C#7", "D7", "D#7", "E7", "F7", "F#7", "G7", "G#7", "A7", "A#7", "B7",              // 96-107
  "C8", "C#8", "D8", "D#8", "E8", "F8", "F#8", "G8", "G#8", "A8", "A#8", "B8",              // 108-119
  "C9", "C#9", "D9", "D#9", "E9", "F9", "F#9", "G9"                                         // 120-127
};

const char* midiNoteName(int note) {
  if (note < 0 || note > 127) return "--";
  return kNoteNames[note];
}

int degreeToScaleInterval(int degree, const int scale[], int scaleLength) {
  if (degree < 0) degree = 0;
  int baseDegree = degree % scaleLength;
  int octaveShift = (degree / scaleLength) * 12;
  return scale[baseDegree] + octaveShift;
}

}  // namespace mp16
