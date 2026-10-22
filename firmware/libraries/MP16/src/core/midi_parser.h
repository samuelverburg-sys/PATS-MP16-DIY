// Turns the byte stream from the MIDI In jack into whole messages. Platform-free: tested on the host.
// Handles running status, real-time bytes (clock, start, stop) in the middle of a message, and skips
// SysEx. Feed it every byte from Serial1 in loop(); it never blocks.
#pragma once

#include <stdint.h>

namespace mp16 {

struct MidiMessage {
  uint8_t status = 0;
  uint8_t data1 = 0;
  uint8_t data2 = 0;
  uint8_t length = 0;  // 1, 2 or 3 bytes on the wire (status included)

  uint8_t command() const { return status & 0xF0; }
  uint8_t channel() const { return status & 0x0F; }
  bool isNoteOn() const { return command() == 0x90 && data2 > 0; }
  // Note-on with velocity 0 is a note-off too.
  bool isNoteOff() const { return command() == 0x80 || (command() == 0x90 && data2 == 0); }
};

class MidiParser {
 public:
  // Returns true when `byte` completes a message, which is then in `out`.
  bool feed(uint8_t byte, MidiMessage& out);

 private:
  uint8_t status_ = 0;   // running status (0 = none)
  uint8_t data_[2] = {};
  uint8_t count_ = 0;    // data bytes received for the current message
  bool inSysex_ = false;
};

// Number of data bytes that follow a status byte (0, 1 or 2).
int midiDataLength(uint8_t status);

}  // namespace mp16
