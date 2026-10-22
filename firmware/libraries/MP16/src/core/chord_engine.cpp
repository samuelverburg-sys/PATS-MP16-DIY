#include "chord_engine.h"

#include "music_theory.h"

namespace mp16 {

int clampInt(int v, int lo, int hi) {
  return v < lo ? lo : (v > hi ? hi : v);
}

void ChordEngine::loadPresets() {
  for (int i = 0; i < kPadCount; i++) {
    pads[i].chord = kPresetChords[i];
    pads[i].triggerNote = settings.rootNote + i;
  }
}

void ChordEngine::setChordIntervals(int pad) {
  Chord& c = pads[pad].chord;
  const int* scale = kScaleIntervals[clampInt(settings.scaleType, 0, kScaleCount - 1)];
  for (int j = 0; j < 7; j++) {
    c.intervals[j] = degreeToScaleInterval(c.degree + kChordDegrees[j], scale);
  }
  c.intervals[7] = c.intervals[0];  // the bass note doubles the chord root
}

void ChordEngine::setAllChordIntervals() {
  for (int i = 0; i < kPadCount; i++) setChordIntervals(i);
}

int ChordEngine::noteNumber(int pad, int note) const {
  const Chord& c = pads[pad].chord;
  return settings.rootNote + c.intervals[note] + c.octaveModifiers[note] * 12 + c.semitoneModifiers[note];
}

int ChordEngine::displayVelocity(int pad, int note) const {
  int raw = (int)(settings.velocityScaling * (pads[pad].padVelocity + pads[pad].chord.velocityModifiers[note]));
  return clampInt(raw, 1, 127);
}

int ChordEngine::outputChannel(int output) const {
  switch (output) {
    case 0: return settings.midiOutputAChannel;
    case 1: return settings.midiOutputBChannel;
    case 2: return settings.midiOutputCChannel;
    default: return settings.midiOutputDChannel;
  }
}

int ChordEngine::noteCount(int output, int note) const {
  if (output < 0 || output >= kOutputs || note < 0 || note > 127) return 0;
  return noteCount_[output][note];
}

void ChordEngine::playChord(int pad) {
  for (int j = 0; j < kChordNotes; j++) {
    if (pads[pad].chord.isActive[j]) playNote(pad, j);
  }
}

void ChordEngine::stopChord(int pad) {
  for (int j = 0; j < kChordNotes; j++) {
    if (pads[pad].chord.isActive[j]) stopNote(pad, j);
  }
}

void ChordEngine::playNote(int pad, int j) {
  const Pad& p = pads[pad];
  int note = noteNumber(pad, j);
  int output = p.chord.channel[j];
  // Notes pushed outside MIDI's 0-127 by the octave/semitone modifiers are not played.
  if (note < 0 || note > 127 || output < 0 || output >= kOutputs) return;

  int variation = randomInRange(-p.velocityVariation, p.velocityVariation);
  int velocity = clampInt((int)(settings.velocityScaling * (p.padVelocity + p.chord.velocityModifiers[j] + variation)), 1, 127);
  uint8_t channel = (uint8_t)(outputChannel(output) & 0x0F);

  // Already sounding from another pad: retrigger it, and count one more pad holding it.
  if (noteCount_[output][note] > 0) out_.send(0x80 | channel, (uint8_t)note, (uint8_t)velocity);
  noteCount_[output][note]++;
  out_.send(0x90 | channel, (uint8_t)note, (uint8_t)velocity);
}

void ChordEngine::stopNote(int pad, int j) {
  int note = noteNumber(pad, j);
  int output = pads[pad].chord.channel[j];
  if (note < 0 || note > 127 || output < 0 || output >= kOutputs) return;

  // Note-off only when the last pad holding this note lets go.
  if (noteCount_[output][note] > 0) {
    noteCount_[output][note]--;
    if (noteCount_[output][note] == 0) out_.send(0x80 | (outputChannel(output) & 0x0F), (uint8_t)note, 0);
  }
}

void ChordEngine::killAllNotes() {
  for (int note = 0; note < 128; note++) {
    for (int output = 0; output < kOutputs; output++) {
      if (noteCount_[output][note] > 0) out_.send(0x80 | (outputChannel(output) & 0x0F), (uint8_t)note, 0);
      noteCount_[output][note] = 0;
    }
  }
}

void ChordEngine::copyChord(int target, int source) {
  pads[target].chord = pads[source].chord;
}

int ChordEngine::randomInRange(int lo, int hi) {
  if (lo >= hi) return lo;
  // xorshift32: small, fast and good enough for velocity humanisation.
  rng_ ^= rng_ << 13;
  rng_ ^= rng_ >> 17;
  rng_ ^= rng_ << 5;
  return lo + (int)(rng_ % (uint32_t)(hi - lo));
}

}  // namespace mp16
