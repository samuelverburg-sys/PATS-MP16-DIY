// Host tests for firmware/libraries/MP16/src/core (no Arduino, no hardware): `make -C firmware/test`.
#include <cstdio>
#include <cstring>
#include <vector>

#include "../libraries/MP16/src/core/chord_engine.h"
#include "../libraries/MP16/src/core/input.h"
#include "../libraries/MP16/src/core/midi_parser.h"
#include "../libraries/MP16/src/core/music_theory.h"

using namespace mp16;

static int failures = 0;
static int checks = 0;
#define CHECK(cond)                                                    \
  do {                                                                 \
    checks++;                                                          \
    if (!(cond)) {                                                     \
      failures++;                                                      \
      std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);      \
    }                                                                  \
  } while (0)

struct Recorder : MidiOut {
  struct Msg { uint8_t s, d1, d2; };
  std::vector<Msg> sent;
  void send(uint8_t s, uint8_t d1, uint8_t d2) override { sent.push_back({ s, d1, d2 }); }
  int count(uint8_t status) const {
    int n = 0;
    for (auto& m : sent) n += m.s == status;
    return n;
  }
};

static void testMusicTheory() {
  CHECK(std::strcmp(midiNoteName(60), "C4") == 0);
  CHECK(std::strcmp(midiNoteName(0), "C-1") == 0);
  CHECK(std::strcmp(midiNoteName(127), "G9") == 0);
  CHECK(std::strcmp(midiNoteName(-1), "--") == 0);
  CHECK(std::strcmp(midiNoteName(128), "--") == 0);
  const int* major = kScaleIntervals[0];
  CHECK(degreeToScaleInterval(0, major) == 0);
  CHECK(degreeToScaleInterval(2, major) == 4);
  CHECK(degreeToScaleInterval(7, major) == 12);
  CHECK(degreeToScaleInterval(9, major) == 16);
}

static void testPresetsMatchScale() {
  // The built-in chords are the diatonic chords of the major scale: recomputing a preset's intervals
  // from its degree must give back what preset.h stored.
  Recorder r;
  ChordEngine e(r);
  e.loadPresets();
  for (int p = 0; p < kPadCount; p++) {
    int stored[8];
    std::memcpy(stored, e.pads[p].chord.intervals, sizeof stored);
    e.setChordIntervals(p);
    CHECK(std::memcmp(stored, e.pads[p].chord.intervals, sizeof stored) == 0);
    CHECK(e.pads[p].triggerNote == 48 + p);
  }
}

static void testPlayStop() {
  Recorder r;
  ChordEngine e(r);
  e.loadPresets();
  // Pad 1: C major 7 (C E G B) on output A (channel 1), bass C one octave down on output B (channel 3).
  e.playChord(0);
  CHECK(r.count(0x90) == 4);  // 4 active notes in preset 1 (1, 3, 5, 7)
  CHECK(r.sent[0].d1 == 48);  // C3
  CHECK(r.sent[1].d1 == 64);  // E4 (octave +1)
  CHECK(r.sent[2].d1 == 55);  // G3
  CHECK(r.sent[3].d1 == 59);  // B3
  e.stopChord(0);
  CHECK(r.count(0x80) == 4);
  for (int n = 0; n < 128; n++) CHECK(e.noteCount(0, n) == 0);
}

static void testSharedNotesAreReferenceCounted() {
  Recorder r;
  ChordEngine e(r);
  e.loadPresets();
  // Pads 1 and 8 are both C major 7 voicings sharing C3, G3 and B3.
  e.playChord(0);
  e.playChord(7);
  CHECK(e.noteCount(0, 48) == 2);
  r.sent.clear();
  e.stopChord(0);
  // C3 is still held by pad 8: no note-off for it yet.
  for (auto& m : r.sent) CHECK(!(m.s == 0x80 && m.d1 == 48));
  e.stopChord(7);
  CHECK(e.noteCount(0, 48) == 0);
}

static void testOutOfRangeNotesAreSkipped() {
  Recorder r;
  ChordEngine e(r);
  e.loadPresets();
  e.settings.rootNote = 107;
  for (int j = 0; j < 8; j++) {
    e.pads[0].chord.octaveModifiers[j] = 3;  // far above 127
    e.pads[0].chord.isActive[j] = true;
  }
  e.playChord(0);
  for (auto& m : r.sent) CHECK(m.d1 <= 127);
  CHECK(r.sent.empty());
  e.stopChord(0);  // must not underflow or write out of bounds
  CHECK(r.sent.empty());
}

static void testVelocityStaysValid() {
  Recorder r;
  ChordEngine e(r);
  e.loadPresets();
  e.settings.velocityScaling = 2.0f;
  e.pads[0].padVelocity = 127;
  e.pads[0].velocityVariation = 99;
  for (int i = 0; i < 50; i++) {
    e.playChord(0);
    e.stopChord(0);
  }
  for (auto& m : r.sent) CHECK(m.d2 <= 127);
  CHECK(e.displayVelocity(0, 0) == 127);
  e.settings.velocityScaling = 0.05f;
  e.pads[0].padVelocity = 1;
  CHECK(e.displayVelocity(0, 0) == 1);
}

static void testKillAll() {
  Recorder r;
  ChordEngine e(r);
  e.loadPresets();
  e.playChord(0);
  e.playChord(1);
  r.sent.clear();
  e.killAllNotes();
  CHECK(!r.sent.empty());
  for (auto& m : r.sent) CHECK((m.s & 0xF0) == 0x80);
  for (int o = 0; o < kOutputs; o++)
    for (int n = 0; n < 128; n++) CHECK(e.noteCount(o, n) == 0);
}

static std::vector<MidiMessage> parse(const std::vector<uint8_t>& bytes) {
  MidiParser p;
  std::vector<MidiMessage> out;
  MidiMessage m;
  for (uint8_t b : bytes)
    if (p.feed(b, m)) out.push_back(m);
  return out;
}

static void testMidiParser() {
  auto m = parse({ 0x91, 60, 100 });
  CHECK(m.size() == 1 && m[0].isNoteOn() && m[0].channel() == 1 && m[0].data1 == 60 && m[0].length == 3);

  // Running status: a second note-on without its status byte, then a note-off as velocity 0.
  m = parse({ 0x90, 60, 100, 62, 0 });
  CHECK(m.size() == 2 && m[1].data1 == 62 && m[1].isNoteOff());

  // Clock in the middle of a note-on arrives on its own and does not break the note.
  m = parse({ 0x90, 60, 0xF8, 100 });
  CHECK(m.size() == 2 && m[0].status == 0xF8 && m[1].data1 == 60 && m[1].data2 == 100);

  // Program change has one data byte.
  m = parse({ 0xC0, 5 });
  CHECK(m.size() == 1 && m[0].length == 2 && m[0].data1 == 5);

  // SysEx is skipped; the next message parses normally.
  m = parse({ 0xF0, 0x7E, 0x01, 0x02, 0xF7, 0x80, 60, 0 });
  CHECK(m.size() == 1 && m[0].isNoteOff());

  // Data bytes without a status (cable plugged in mid-message) are ignored.
  m = parse({ 60, 100, 0x90, 61, 1 });
  CHECK(m.size() == 1 && m[0].data1 == 61);
}

static void testQuadrature() {
  QuadratureDecoder d;
  // Clockwise gray sequence from rest (A=1, B=1 with pull-ups): 11 -> 10 -> 00 -> 01 -> 11.
  // The table counts 01->00 etc.; drive one full cycle each way and expect one detent.
  const bool cw[4][2] = { { 1, 0 }, { 0, 0 }, { 0, 1 }, { 1, 1 } };
  d.step(1, 1);
  int sum = 0;
  for (auto& s : cw) sum += d.step(s[0], s[1]);
  int ccwSum = 0;
  const bool ccw[4][2] = { { 0, 1 }, { 0, 0 }, { 1, 0 }, { 1, 1 } };
  for (auto& s : ccw) ccwSum += d.step(s[0], s[1]);
  CHECK(sum == -ccwSum);
  CHECK(sum == 1 || sum == -1);
  // Contact bounce (back and forth across one edge) cancels out.
  int bounce = d.step(1, 0) + d.step(1, 1) + d.step(1, 0) + d.step(1, 1);
  CHECK(bounce == 0);
}

static void testButtonEdges() {
  Button b;
  b.update(true);
  CHECK(b.pressed() && !b.released());
  b.update(true);
  CHECK(!b.pressed() && !b.released());
  b.update(false);
  CHECK(b.released());
}

int main() {
  testMusicTheory();
  testPresetsMatchScale();
  testPlayStop();
  testSharedNotesAreReferenceCounted();
  testOutOfRangeNotesAreSkipped();
  testVelocityStaysValid();
  testKillAll();
  testMidiParser();
  testQuadrature();
  testButtonEdges();
  std::printf("%d checks, %d failed\n", checks, failures);
  return failures ? 1 : 0;
}
