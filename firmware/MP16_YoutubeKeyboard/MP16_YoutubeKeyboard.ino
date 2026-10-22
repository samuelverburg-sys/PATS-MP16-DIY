// PATS MP-16 as a YouTube remote: a USB keyboard that types YouTube's shortcut keys.
//   Shift: play/pause (k)        Pads 1-10: jump to 0%-90% (keys 0-9)
//   Pad 11/12: back/forward 10 s (j/l)    Pad 13/14: slower/faster (< and >)
//   Pad 15: mute (m)             Pad 16: next video (N)
//
// Board: "Waveshare RP2040 Zero" (rev 1 kit) or "Generic RP2040" (rev 2), USB Stack: **Pico SDK**
// (the Keyboard library does not work with Adafruit TinyUSB).
#include <Keyboard.h>
#include <MP16.h>

using namespace mp16;

Board board;

// The key each pad types; Keyboard.press('<') adds Shift by itself, as typing '<' needs it.
const char kPadKeys[16] = { '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'j', 'l', '<', '>', 'm', 'N' };
const char kShiftKey = 'k';
const float kDimFactor = 0.1;

void setup() {
  board.begin();
  Keyboard.begin();
}

void loop() {
  board.scan();

  if (board.shift().pressed()) Keyboard.press(kShiftKey);
  if (board.shift().released()) Keyboard.release(kShiftKey);
  for (int i = 0; i < 16; i++) {
    if (board.pad(i).pressed()) Keyboard.press(kPadKeys[i]);
    if (board.pad(i).released()) Keyboard.release(kPadKeys[i]);
  }

  // LEDs: dim white, full white while held.
  board.pixels.clear();
  board.pixels.setPixelColor(0, board.shift().down ? 0xFFFFFF : dimColor(0xFFFFFF, kDimFactor));
  for (int i = 0; i < 16; i++) {
    board.pixels.setPixelColor(padPixel(i), board.pad(i).down ? 0xFFFFFF : dimColor(0xFFFFFF, kDimFactor));
  }
  board.pixels.show();
}
