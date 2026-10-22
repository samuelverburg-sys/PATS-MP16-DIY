// PATS MP-16 boilerplate: the starting point for your own firmware. Reads every control, lights the
// LEDs, draws the screen and has USB + jack MIDI ready. Fill in the places marked "your code".
//
// Board: "Waveshare RP2040 Zero" (rev 1 kit) or "Generic RP2040" (rev 2), USB Stack: Adafruit TinyUSB.
// What the board object offers: libraries/MP16/src/MP16Board.h
#include <Adafruit_TinyUSB.h>
#include <MP16.h>

using namespace mp16;

Adafruit_USBD_MIDI usbMidi;
Board board;
MidiParser jackParser;

const float kDimFactor = 0.1;
int encoderPosition = 0;

void setup() {
  board.begin();
  usbMidi.begin();
}

void loop() {
  board.scan();
  encoderPosition += board.takeEncoderDetents();

  for (int i = 0; i < 16; i++) {
    if (board.pad(i).pressed() && !board.shift().down) {
      sendNoteOn(48 + i, 100, 0);  // your code: what a pad does when pressed
    } else if (board.pad(i).released()) {
      sendNoteOff(48 + i, 0, 0);   // ... and when released
    }
  }
  if (board.encoderButton().pressed()) {
    encoderPosition = 0;  // your code: encoder push
  }

  MidiMessage msg;
  while (board.midi.available()) {
    if (jackParser.feed(board.midi.read(), msg)) {
      // your code: a message from the MIDI In jack (msg.status, msg.data1, msg.data2)
    }
  }

  updatePixels();
  updateDisplay();
}

void sendNoteOn(int note, int velocity, int channel) { sendMidi(0x90 | (channel & 0x0F), note, velocity); }
void sendNoteOff(int note, int velocity, int channel) { sendMidi(0x80 | (channel & 0x0F), note, velocity); }

// To USB and the MIDI Out jack.
void sendMidi(uint8_t status, uint8_t data1, uint8_t data2) {
  uint8_t packet[] = { status, (uint8_t)(data1 & 0x7F), (uint8_t)(data2 & 0x7F) };
  usbMidi.write(packet, 3);
  board.midi.write(packet, 3);
}

void updatePixels() {
  board.pixels.clear();
  board.pixels.setPixelColor(0, board.shift().down ? 0xFFFFFF : dimColor(0xFFFFFF, kDimFactor));
  for (int i = 0; i < 16; i++) {
    board.pixels.setPixelColor(padPixel(i), board.pad(i).down ? 0xFFFFFF : dimColor(0xFFFFFF, kDimFactor));
  }
  board.pixels.show();
}

void updateDisplay() {
  Adafruit_SSD1306& display = board.display;
  display.clearDisplay();
  display.setCursor(0, 0);
  display.print("MP-16 rev ");
  display.println(Board::revision());
  display.print("Encoder: ");
  display.println(encoderPosition);  // your code: draw your own screen
  display.display();
}
