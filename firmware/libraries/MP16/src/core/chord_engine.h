// The Chordmaker's model and note logic: settings, pads, chords, and which MIDI notes a pad plays.
// Platform-free (no Arduino.h): tested on the host. MIDI goes out through the MidiOut interface.
#pragma once

#include <stdint.h>

namespace mp16 {

constexpr int kPadCount = 16;
constexpr int kChordNotes = 8;  // 1, 3, 5, 7, 9, 11, 13 and a bass note
constexpr int kOutputs = 4;     // chord notes go to output A, B, C or D, each on its own MIDI channel
constexpr int kSlots = 4;       // save/load slots in flash

// The structs below are written to flash byte for byte (slot files). Their field order and types
// are those of the rev-1 firmware, so presets saved on an existing kit still load: do not reorder,
// resize or insert fields. New settings go in a new struct and file.
struct Settings {
  int rootNote = 48;
  int scaleType = 0;
  int midiRecChannel = 0;
  int midiTrigChannel = 1;
  int midiOutputAChannel = 0;
  int midiOutputBChannel = 2;
  int midiOutputCChannel = 3;
  int midiOutputDChannel = 15;
  bool midiThru = false;
  bool tempoSync = true;
  float tempo = 120;
  float velocityScaling = 1.0;
  int defaultVelocity = 65;
  uint32_t shiftColor = 0xFF0000;
  int ledBrightness = 100;
};

struct Chord {
  int degree = 0;                    // scale step of the chord root, 0-6
  int intervals[8] = { 0 };          // semitones from the root note, from the scale
  int octaveModifiers[8] = { 0 };    // -3..3 octaves per note
  int semitoneModifiers[8] = { 0 };  // -7..7 semitones per note
  bool isActive[8] = { false };      // which of the 8 notes play
  int velocityModifiers[8] = { 0 };  // added to the pad velocity per note
  unsigned long timing[8] = { 0 };   // reserved (strum delay)
  int channel[8] = { 0 };            // output 0-3 = A-D
};

struct Pad {
  uint32_t color = 0xFFAA00;
  int triggerNote = 0;  // incoming MIDI note that plays this pad
  int chokeGroup = 0;   // reserved
  bool hold = false;    // reserved
  int arpType = 0;      // reserved: 0 = off, 1 = up, 2 = down, 3 = up & down, 4 = random, 5 = brownian
  int arpSpeed = 1;
  float arpGate = 1.0;
  int arpOctaves = 1;
  int padVelocity = 65;
  int velocityVariation = 0;  // +- random velocity, 0-99
  unsigned long timingVariation = 0;
  Chord chord;
};

#if defined(__arm__)
// Sizes on the RP2040 (32-bit), as written by the rev-1 firmware. A change here breaks saved slots.
static_assert(sizeof(Settings) == 56, "Settings layout changed: saved slots would no longer load");
static_assert(sizeof(Pad) == 248, "Pad layout changed: saved slots would no longer load");
#endif

// Where MIDI messages go. The sketch implements it (USB + the MIDI Out jack); tests record them.
class MidiOut {
 public:
  virtual void send(uint8_t status, uint8_t data1, uint8_t data2) = 0;
};

// The 16 built-in chords (degrees I-VII and more), used when flash holds no saved slot.
extern const Chord kPresetChords[kPadCount];

int clampInt(int v, int lo, int hi);

class ChordEngine {
 public:
  Settings settings;
  Pad pads[kPadCount];

  explicit ChordEngine(MidiOut& out) : out_(out) {}

  // Pads from the built-in presets, trigger notes root + 0..15.
  void loadPresets();

  // Recompute a pad's intervals from its degree and the current scale (after a scale or degree change).
  void setChordIntervals(int pad);
  void setAllChordIntervals();

  // The MIDI note of one chord note, before range checks (can be < 0 or > 127 with large modifiers).
  int noteNumber(int pad, int note) const;

  // The velocity shown on screen for one chord note (no randomness), 1-127.
  int displayVelocity(int pad, int note) const;

  // Start or stop every active note of a pad. Notes shared by several pads keep sounding until the
  // last pad using them stops (reference counted per output and note).
  void playChord(int pad);
  void stopChord(int pad);

  // Note-off for everything sounding; clears the reference counts.
  void killAllNotes();

  void copyChord(int target, int source);

  // MIDI channel (0-15) of output 0-3.
  int outputChannel(int output) const;

  // Seed for the velocity randomness (the sketch passes something that varies, tests a constant).
  void seedRandom(uint32_t seed) { rng_ = seed ? seed : 1; }

  // How many pads hold this note on this output (for tests and the display).
  int noteCount(int output, int note) const;

 private:
  void playNote(int pad, int note);
  void stopNote(int pad, int note);
  int randomInRange(int lo, int hi);  // like Arduino random(lo, hi): lo <= r < hi

  MidiOut& out_;
  uint8_t noteCount_[kOutputs][128] = {};
  uint32_t rng_ = 0x2545F491;
};

}  // namespace mp16
