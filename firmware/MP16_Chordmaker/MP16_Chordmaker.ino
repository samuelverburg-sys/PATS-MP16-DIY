// PATS MP-16 Chordmaker: each pad plays a chord from the current key and scale over USB MIDI and the
// MIDI Out jack. Hold Shift and press a pad to edit (labels on the layout: enclosure/layout.png).
//
// Board: "Waveshare RP2040 Zero" (rev 1 kit) or "Generic RP2040" (rev 2), USB Stack: Adafruit TinyUSB.
// Build and upload: README.md, "Firmware". Chord logic: libraries/MP16/src/core/chord_engine.*
#include <Adafruit_TinyUSB.h>
#include <LittleFS.h>
#include <MP16.h>

using namespace mp16;

// ----------------------------------------------------------------------------------------------
// MIDI out: every message goes to USB and to the MIDI Out jack.
// ----------------------------------------------------------------------------------------------
Adafruit_USBD_MIDI usbMidi;
Board board;

struct UsbAndJack : MidiOut {
  void send(uint8_t status, uint8_t data1, uint8_t data2) override {
    uint8_t packet[] = { status, data1, data2 };
    usbMidi.write(packet, 3);
    board.midi.write(packet, 3);
  }
} midiOut;

ChordEngine engine(midiOut);
Settings& settings = engine.settings;
Pad* const pads = engine.pads;
MidiParser jackParser;

// ----------------------------------------------------------------------------------------------
// Screens: Shift + pad n opens screen n (the labels under the pads); -1 is the main screen.
// ----------------------------------------------------------------------------------------------
enum Screen {
  kScreenLoad = -2,
  kScreenMain = -1,
  kScreenRoot = 0,
  kScreenScale = 1,
  kScreenDegree = 2,
  kScreenNotes = 3,
  kScreenVelocityRandom = 4,
  kScreenVelocity = 5,
  kScreenIntervals = 6,
  kScreenOctaves = 7,
  kScreenCopy = 13,
  kScreenMidi = 14,
  kScreenSave = 15,
};

int screenIndex = kScreenMain;
int selectIndex = 0;  // 0 = choosing a note (or MIDI row), n = editing note n - 1
int noteIndex = 0;    // which of the 8 chord notes is highlighted
int selectedPad = 0;
int slotSelect = 0;
int copyIndex = -1;

bool shiftPressedAtKeyDown[16] = { false };
bool padStates[16] = { false };          // pad is sounding (from a key or from MIDI In)
bool previousPadStates[16] = { false };
bool midiStates[16] = { false };         // pad held by an incoming MIDI note
bool previousMidiStates[16] = { false };

const float kDimFactor = 0.3;
const int kMidiMenuRows = 7;

// Turns since the last loop, read once per loop so every menu sees the same value.
int encoderDetents = 0;
int encoderQuarterSteps = 0;

void setup() {
  board.begin();
  usbMidi.begin();
  engine.seedRandom(micros() ^ (uint32_t)rp2040.hwrand32());

  if (!LittleFS.begin()) {
    showMessage("LittleFS failed");
  }
  if (!loadFromFlash(0)) engine.loadPresets();
}

void loop() {
  board.scan();
  readEncoder();
  updateMenu();
  updateMIDI();
  updatePixels();
  updateDisplay();
}

// The main screen adjusts velocity scaling in fine steps; everything else moves one per click.
void readEncoder() {
  if (screenIndex == kScreenMain) {
    encoderQuarterSteps = board.takeEncoderQuarterSteps();
    encoderDetents = 0;
  } else {
    encoderDetents = board.takeEncoderDetents();
    encoderQuarterSteps = 0;
  }
}

bool encoderPushed() { return board.encoderButton().pressed(); }

// ----------------------------------------------------------------------------------------------
// Flash slots: /slot0.txt ... /slot3.txt hold Settings + 16 Pads, byte for byte (rev-1 format).
// ----------------------------------------------------------------------------------------------
bool loadFromFlash(int slot) {
  String path = "/slot" + String(slot) + ".txt";
  File file = LittleFS.open(path, "r");
  if (!file) return false;
  Settings loaded;
  static Pad loadedPads[kPadCount];
  bool ok = file.read((uint8_t*)&loaded, sizeof loaded) == sizeof loaded &&
            file.read((uint8_t*)loadedPads, sizeof loadedPads) == sizeof loadedPads;
  file.close();
  if (!ok) return false;  // short or damaged file: keep what is loaded now
  settings = loaded;
  memcpy(pads, loadedPads, sizeof loadedPads);
  return true;
}

bool saveToFlash(int slot) {
  String path = "/slot" + String(slot) + ".txt";
  File file = LittleFS.open(path, "w");
  if (!file) return false;
  file.write((const uint8_t*)&settings, sizeof(Settings));
  file.write((const uint8_t*)pads, sizeof(Pad) * kPadCount);
  file.close();
  return true;
}

// ----------------------------------------------------------------------------------------------
// Menus
// ----------------------------------------------------------------------------------------------

// Add the encoder's turn to `value`, wrapping within 0..count-1.
bool turnWrap(int& value, int count) {
  if (encoderDetents == 0) return false;
  value = ((value + encoderDetents) % count + count) % count;
  return true;
}

// Add the encoder's turn to `value`, limited to lo..hi. Notes stop first: the change alters them.
bool turnClamp(int& value, int lo, int hi) {
  if (encoderDetents == 0) return false;
  engine.killAllNotes();
  value = clampInt(value + encoderDetents, lo, hi);
  return true;
}

void updateMenu() {
  switch (screenIndex) {
    case kScreenLoad: menuLoad(); break;
    case kScreenMain: menuMain(); break;
    case kScreenRoot: turnClamp(settings.rootNote, 12, 107); break;
    case kScreenScale:
      if (encoderDetents != 0) {
        engine.killAllNotes();
        turnWrap(settings.scaleType, kScaleCount);
        engine.setAllChordIntervals();
      }
      break;
    case kScreenDegree:
      if (turnClamp(pads[selectedPad].chord.degree, 0, 6)) engine.setChordIntervals(selectedPad);
      break;
    case kScreenNotes:
      turnWrap(noteIndex, kChordNotes);
      if (encoderPushed()) {
        engine.killAllNotes();
        pads[selectedPad].chord.isActive[noteIndex] = !pads[selectedPad].chord.isActive[noteIndex];
      }
      break;
    case kScreenVelocityRandom:
      if (encoderDetents != 0) {
        pads[selectedPad].velocityVariation = clampInt(pads[selectedPad].velocityVariation + encoderDetents, 0, 99);
      }
      break;
    case kScreenVelocity: menuPerNote(pads[selectedPad].chord.velocityModifiers, 1, 128); break;
    case kScreenIntervals: menuPerNote(pads[selectedPad].chord.semitoneModifiers, -7, 7); break;
    case kScreenOctaves: menuPerNote(pads[selectedPad].chord.octaveModifiers, -3, 3); break;
    case kScreenMidi: menuMidi(); break;
    case kScreenSave: menuSave(); break;
  }
}

void menuMain() {
  if (encoderQuarterSteps > 0) {
    settings.velocityScaling = constrain(settings.velocityScaling + 0.01, 0.05, 2.0);
  } else if (encoderQuarterSteps < 0) {
    settings.velocityScaling = constrain(settings.velocityScaling - 0.01, 0.05, 2.0);
  }
  if (encoderPushed()) screenIndex = kScreenLoad;
}

void menuLoad() {
  turnWrap(slotSelect, kSlots);
  if (encoderPushed()) {
    engine.killAllNotes();
    screenIndex = kScreenMain;
    if (loadFromFlash(slotSelect)) {
      showMessage(("Loaded Slot " + String(slotSelect + 1)).c_str());
    } else {
      showMessage("Loading Failed");
    }
  }
}

// Velocity, Intervals and Octaves: turn to pick a note, push to edit it, turn to change, push to go back.
void menuPerNote(int values[8], int lo, int hi) {
  if (selectIndex == 0) {
    turnWrap(noteIndex, kChordNotes);
    if (encoderPushed()) selectIndex = noteIndex + 1;
  } else {
    turnClamp(values[selectIndex - 1], lo, hi);
    if (encoderPushed()) selectIndex = 0;
  }
}

// Push moves to the next row; turn changes the row's value.
void menuMidi() {
  switch (selectIndex) {
    case 0: turnWrap(settings.midiRecChannel, 16); break;
    case 1: if (encoderDetents) { engine.killAllNotes(); turnWrap(settings.midiTrigChannel, 16); } break;
    case 2: if (encoderDetents) { engine.killAllNotes(); turnWrap(settings.midiOutputAChannel, 16); } break;
    case 3: if (encoderDetents) { engine.killAllNotes(); turnWrap(settings.midiOutputBChannel, 16); } break;
    case 4: if (encoderDetents) { engine.killAllNotes(); turnWrap(settings.midiOutputCChannel, 16); } break;
    case 5: if (encoderDetents) { engine.killAllNotes(); turnWrap(settings.midiOutputDChannel, 16); } break;
    case 6: if (encoderDetents) settings.midiThru = !settings.midiThru; break;
  }
  if (encoderPushed()) selectIndex = (selectIndex + 1) % kMidiMenuRows;
}

void menuSave() {
  turnWrap(slotSelect, kSlots);
  if (encoderPushed()) {
    bool ok = saveToFlash(slotSelect);
    screenIndex = kScreenMain;
    selectIndex = 0;
    showMessage(ok ? "Settings Saved" : "Saving Failed");
  }
}

// ----------------------------------------------------------------------------------------------
// MIDI
// ----------------------------------------------------------------------------------------------
void updateMIDI() {
  for (int i = 0; i < 16; i++) {
    previousMidiStates[i] = midiStates[i];
    previousPadStates[i] = padStates[i];
  }

  // MIDI In jack: every byte that is waiting (the UART buffers them while the loop draws the screen).
  MidiMessage msg;
  while (board.midi.available()) {
    uint8_t byte = board.midi.read();
    if (jackParser.feed(byte, msg)) {
      // Thru: the jack's messages go out of the MIDI Out jack and to USB (the MP-16 as a MIDI interface).
      if (settings.midiThru) forwardFromJack(msg);
      processIncomingMIDI(msg);
    }
  }

  // USB MIDI: on Thru, out of the MIDI Out jack only (sending it back to USB would loop).
  while (usbMidi.available()) {
    uint8_t packet[4];
    if (!usbMidi.readPacket(packet)) break;
    MidiMessage m;
    m.status = packet[1];
    m.data1 = packet[2];
    m.data2 = packet[3];
    m.length = (uint8_t)(1 + midiDataLength(m.status));
    if (m.status < 0x80) continue;  // SysEx continuation packets
    if (settings.midiThru) board.midi.write(packet + 1, m.length);
    processIncomingMIDI(m);
  }

  if (board.shift().pressed()) screenIndex = kScreenMain;  // Shift cancels any screen

  for (int i = 0; i < 16; i++) {
    const Button& key = board.pad(i);
    if (key.pressed()) {
      if (board.shift().down) {  // Shift + pad: open that pad's screen
        shiftPressedAtKeyDown[i] = true;
        screenIndex = i;
        if (i == kScreenCopy) copyIndex = selectedPad;
        selectIndex = 0;
      } else if (screenIndex == kScreenCopy) {  // copy screen: this pad is the destination
        engine.killAllNotes();
        if (copyIndex != -1 && copyIndex != i) {
          engine.copyChord(i, copyIndex);
          showMessage(("Copied " + String(copyIndex + 1) + " to " + String(i + 1)).c_str());
          copyIndex = -1;
        }
        screenIndex = kScreenMain;
      } else {
        shiftPressedAtKeyDown[i] = false;
        padStates[i] = true;
        selectedPad = i;
      }
    } else if (key.released()) {
      if (!shiftPressedAtKeyDown[i] && !midiStates[i]) padStates[i] = false;
    }

    if (midiStates[i] && !previousMidiStates[i]) {
      padStates[i] = true;
    } else if (!midiStates[i] && previousMidiStates[i] && !key.down) {
      padStates[i] = false;
    }

    if (padStates[i] && !previousPadStates[i]) {
      engine.playChord(i);
    } else if (!padStates[i] && previousPadStates[i]) {
      engine.stopChord(i);
    }
  }
}

void forwardFromJack(const MidiMessage& m) {
  uint8_t bytes[3] = { m.status, m.data1, m.data2 };
  board.midi.write(bytes, m.length);
  usbMidi.write(bytes, m.length);
}

// Notes on the trigger channel play the pad whose trigger note they match.
void processIncomingMIDI(const MidiMessage& m) {
  if (m.channel() != settings.midiTrigChannel || m.status >= 0xF0) return;
  if (!m.isNoteOn() && !m.isNoteOff()) return;
  for (int i = 0; i < 16; i++) {
    if (m.data1 == pads[i].triggerNote) midiStates[i] = m.isNoteOn();
  }
}

// ----------------------------------------------------------------------------------------------
// LEDs
// ----------------------------------------------------------------------------------------------
void updatePixels() {
  Adafruit_NeoPixel& pixels = board.pixels;
  pixels.clear();

  if (board.shift().down) {
    pixels.setPixelColor(0, settings.shiftColor);
  } else if (screenIndex != kScreenMain) {
    pixels.setPixelColor(0, dimColor(settings.shiftColor, kDimFactor));  // a screen is open
  }

  for (int i = 0; i < 16; i++) {
    bool bright = i == selectedPad && !board.shift().down;
    pixels.setPixelColor(padPixel(i), bright ? pads[i].color : dimColor(pads[i].color, kDimFactor));
    if (board.pad(i).down || midiStates[i]) pixels.setPixelColor(padPixel(i), 0xFFFFFF);
  }
  pixels.show();
}

// ----------------------------------------------------------------------------------------------
// OLED
// ----------------------------------------------------------------------------------------------
Adafruit_SSD1306& display = board.display;

// A message in the middle of the screen for one second.
void showMessage(const char* text) {
  display.clearDisplay();
  display.setCursor(22, 28);
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.print(text);
  display.display();
  delay(1000);
}

void updateDisplay() {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  switch (screenIndex) {
    case kScreenLoad: drawSlotScreen("Load:"); break;
    case kScreenMain: drawPadHeader("Degree: ", pads[selectedPad].chord.degree + 1, 66); drawChordNotes(selectedPad); drawNoteVelocities(selectedPad); break;
    case kScreenRoot: drawCentered(37, "Root: ", midiNoteName(settings.rootNote)); break;
    case kScreenScale: drawCentered(18, "Scale: ", kScaleNames[settings.scaleType]); break;
    case kScreenDegree:
      drawPadHeader("Degree: ", pads[selectedPad].chord.degree + 1, 66);
      display.drawLine(66, 14, 120, 14, SSD1306_WHITE);
      drawChordNotes(selectedPad);
      drawNoteVelocities(selectedPad);
      break;
    case kScreenNotes: drawPadTitle("Edit Notes", 62); drawChordNotes(selectedPad); drawNoteVelocities(selectedPad); drawNoteSelect(false); break;
    case kScreenVelocityRandom:
      drawPadTitle(nullptr, 0);
      display.setCursor(4, 28);
      display.print("Velocity Random: ");
      display.print(pads[selectedPad].velocityVariation);
      break;
    case kScreenVelocity: drawPadTitle("Edit Velocity", 50); drawChordNotes(selectedPad); drawNoteVelocities(selectedPad); drawNoteSelect(true); break;
    case kScreenIntervals: drawPadTitle("Edit Intervals", 44); drawChordNotes(selectedPad); drawModSelect(); break;
    case kScreenOctaves:
      drawPadTitle("Edit Octaves", 50);
      drawChordNotes(selectedPad);
      drawNoteOctaves(selectedPad);
      drawNoteSelect(true);
      break;
    case kScreenCopy:
      display.setCursor(31, 20);
      display.print("Copy pad ");
      display.print(selectedPad + 1);
      display.setCursor(10, 40);
      display.print("Select destination");
      break;
    case kScreenMidi: drawMidiMenu(); break;
    case kScreenSave: drawSlotScreen("Save to:"); break;
  }
  display.display();
}

void drawCentered(int x, const char* label, const char* value) {
  display.setCursor(x, 28);
  display.print(label);
  display.print(value);
}

void drawPadTitle(const char* title, int x) {
  display.setCursor(2, 5);
  display.print("Pad ");
  display.print(selectedPad + 1);
  if (title) {
    display.setCursor(x, 5);
    display.print(title);
  }
}

void drawPadHeader(const char* label, int value, int x) {
  drawPadTitle(label, x);
  display.print(value);
}

void drawSlotScreen(const char* title) {
  display.setCursor(40, 6);
  display.print(title);
  for (int i = 0; i < kSlots; i++) {
    display.setCursor(44, 17 + 11 * i);
    display.print("Slot ");
    display.print(i + 1);
    if (i == slotSelect) display.drawRect(42, 15 + 11 * i, 40, 11, SSD1306_WHITE);
  }
}

void drawMidiMenu() {
  static const char* const labels[kMidiMenuRows] = {
    "MIDI In Rec:  ", "MIDI In Trig: ", "MIDI Out A:   ", "MIDI Out B:   ",
    "MIDI Out C:   ", "MIDI Out D:   ", "MIDI Thru:    ",
  };
  const int values[kMidiMenuRows - 1] = {
    settings.midiRecChannel, settings.midiTrigChannel, settings.midiOutputAChannel,
    settings.midiOutputBChannel, settings.midiOutputCChannel, settings.midiOutputDChannel,
  };
  // 7 rows of 9 px: 8 px text and the selection line right under it.
  for (int row = 0; row < kMidiMenuRows; row++) {
    display.setCursor(5, row * 9);
    display.print(labels[row]);
    if (row < kMidiMenuRows - 1) {
      display.print(values[row] + 1);
    } else {
      display.print(settings.midiThru ? "On" : "Off");
    }
  }
  display.drawLine(5, selectIndex * 9 + 8, 124, selectIndex * 9 + 8, SSD1306_WHITE);
}

// The 8 chord notes in two rows of four boxes: interval label (1, 3, ... B), note name, value below.
void noteBox(int i, int& x, int& y) {
  x = (i % 4) * 32;
  y = i < 4 ? 20 : 42;
}

void drawChordNotes(int pad) {
  static const char* const labels[kChordNotes] = { "1", "3", "5", "7", "9", "11", "13", "B" };
  const Chord& chord = pads[pad].chord;
  for (int i = 0; i < kChordNotes; i++) {
    int x, y;
    noteBox(i, x, y);
    display.fillRect(x, y, 13, 17, SSD1306_WHITE);
    display.setTextColor(SSD1306_BLACK);
    display.setCursor(x + (strlen(labels[i]) == 1 ? 4 : 1), y + 1);
    display.print(labels[i]);

    display.setCursor(x + 1, y + 9);
    int semis = chord.semitoneModifiers[i];
    if (semis > 0) display.print("+");
    if (semis != 0) display.print(semis);

    display.setTextColor(SSD1306_WHITE);
    display.setCursor(x + 14, y + 1);
    display.print(chord.isActive[i] ? midiNoteName(engine.noteNumber(pad, i)) : "-");
  }
}

void drawNoteVelocities(int pad) {
  for (int i = 0; i < kChordNotes; i++) {
    if (!pads[pad].chord.isActive[i]) continue;
    int x, y;
    noteBox(i, x, y);
    display.setCursor(x + 14, y + 9);
    display.print(engine.displayVelocity(pad, i));
  }
}

void drawNoteOctaves(int pad) {
  for (int i = 0; i < kChordNotes; i++) {
    int x, y;
    noteBox(i, x, y);
    display.setCursor(x + 14, y + 9);
    int octaves = pads[pad].chord.octaveModifiers[i];
    if (octaves > 0) display.print("+");
    display.print(octaves);
  }
}

// Line above and below the highlighted note; while editing, a double line under its value.
void drawNoteSelect(bool editable) {
  int x, y;
  noteBox(noteIndex, x, y);
  display.drawLine(x, y - 2, x + 31, y - 2, SSD1306_WHITE);
  if (editable && selectIndex - 1 == noteIndex) {
    display.drawLine(x + 13, y + 18, x + 31, y + 18, SSD1306_WHITE);
    display.drawLine(x, y + 20, x + 31, y + 20, SSD1306_WHITE);
  } else {
    display.drawLine(x, y + 18, x + 31, y + 18, SSD1306_WHITE);
  }
}

// As drawNoteSelect, but the interval offset sits under the label box on the left.
void drawModSelect() {
  int x, y;
  noteBox(noteIndex, x, y);
  display.drawLine(x, y - 2, x + 31, y - 2, SSD1306_WHITE);
  if (selectIndex - 1 == noteIndex) {
    display.drawLine(x, y + 18, x + 12, y + 18, SSD1306_WHITE);
    display.drawLine(x, y + 20, x + 31, y + 20, SSD1306_WHITE);
  } else {
    display.drawLine(x, y + 18, x + 31, y + 18, SSD1306_WHITE);
  }
}
