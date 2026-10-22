#include "midi_parser.h"

namespace mp16 {

int midiDataLength(uint8_t status) {
  if (status < 0xF0) {
    uint8_t command = status & 0xF0;
    return (command == 0xC0 || command == 0xD0) ? 1 : 2;  // program change, channel pressure: 1
  }
  switch (status) {
    case 0xF1: return 1;  // MTC quarter frame
    case 0xF2: return 2;  // song position
    case 0xF3: return 1;  // song select
    default: return 0;    // tune request, real-time
  }
}

bool MidiParser::feed(uint8_t byte, MidiMessage& out) {
  if (byte >= 0xF8) {  // real-time: one byte, may arrive inside any other message
    out = MidiMessage{ byte, 0, 0, 1 };
    return true;
  }
  if (byte == 0xF0) {  // SysEx start: skip until any status byte
    inSysex_ = true;
    status_ = 0;
    return false;
  }
  if (byte & 0x80) {  // status byte
    inSysex_ = false;
    if (byte == 0xF7) return false;  // SysEx end
    count_ = 0;
    if (midiDataLength(byte) == 0) {  // tune request
      status_ = 0;
      out = MidiMessage{ byte, 0, 0, 1 };
      return true;
    }
    // Channel messages set running status; system common messages cancel it.
    status_ = byte;
    return false;
  }
  // Data byte
  if (inSysex_ || status_ == 0) return false;  // SysEx payload, or data with no status: ignore
  data_[count_++] = byte;
  int needed = midiDataLength(status_);
  if (count_ < needed) return false;
  out = MidiMessage{ status_, data_[0], needed == 2 ? data_[1] : (uint8_t)0, (uint8_t)(needed + 1) };
  count_ = 0;
  if (status_ >= 0xF0) status_ = 0;  // no running status for system common
  return true;
}

}  // namespace mp16
