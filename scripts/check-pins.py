#!/usr/bin/env python3
"""Check that the firmware's rev-2 pins (firmware/libraries/MP16/src/board_pins.h) match the board
(hardware/mp16/design.py): every GPIO, and every 74HC165 bit worked out from the chain as wired.

  python3 scripts/check-pins.py      # exit 1 and a list of differences if they disagree
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, 'hardware', 'tools'), os.path.join(ROOT, 'hardware', 'mp16')]
import design  # noqa: E402

# board_pins.h constant -> the net design.py puts on that GPIO
GPIO_CONSTANTS = {
    'kMidiTx': 'MIDI_TX', 'kMidiRx': 'MIDI_RX', 'kLedData': 'LED_DATA', 'kI2cSda': 'I2C_SDA', 'kI2cScl': 'I2C_SCL',
    'kEncoderA': 'ENC_A', 'kEncoderB': 'ENC_B', 'kShiftRegData': 'SR_DATA', 'kShiftRegLoad': 'SR_LOAD',
    'kShiftRegClock': 'SR_CLK', 'kExpansionData': 'EXP_MOSI', 'kExpansionLatch': 'EXP_LATCH',
    'kPowerGoodN': 'PGOOD_N',
}


def rev2_block(text):
    shared = text[text.index('namespace pins {'):text.index('#if MP16_BOARD_REV == 1')]
    rev2 = text[text.index('#elif MP16_BOARD_REV == 2'):text.index('#else\n#error')]
    return shared + rev2


def ints(text, name):
    m = re.search(r'constexpr int ' + name + r'(\[\d+\])?\s*=\s*([^;]+);', text)
    if not m:
        return None
    nums = [int(v) for v in re.findall(r'-?\d+', re.sub(r'//[^\n]*', '', m.group(2)))]
    return nums if m.group(1) else nums[0]


def sr_bits():
    """Bit of each KEY_ net in the 24 bits read: walk the chain back from SR_DATA."""
    chips = {p.ref: p for p in design.parts if p.symbol == '74xx:74HC165'}
    d_pin = {'11': 0, '12': 1, '13': 2, '14': 3, '3': 4, '4': 5, '5': 6, '6': 7}
    bits, net, base = {}, 'SR_DATA', 23
    while net != 'GND':
        chip = next(c for c in chips.values() if c.pins['9'] == net)  # its Q7 drives this net
        for pin, n in d_pin.items():
            bits[chip.pins[pin]] = base - 7 + n  # D7 comes out first
        base -= 8
        net = chip.pins['10']  # DS: from the next chip
    return bits


def main():
    text = rev2_block(open(os.path.join(ROOT, 'firmware', 'libraries', 'MP16', 'src', 'board_pins.h')).read())
    errors = []
    gpio_of = {net: g for g, net in design.GPIO.items() if net}
    for const, net in GPIO_CONSTANTS.items():
        got = ints(text, const)
        if got != gpio_of.get(net):
            errors.append(f'{const} = {got}, design.py has {net} on GPIO{gpio_of.get(net)}')
    ain = ints(text, 'kAnalogIn')
    want_ain = [gpio_of.get(f'AIN{k}') for k in range(1, 5)]
    if ain != want_ain:
        errors.append(f'kAnalogIn = {ain}, design.py has {want_ain}')
    bits = sr_bits()
    pad_bits = ints(text, 'kSrPadBit')
    want_pads = [bits[f'KEY_P{n}'] for n in range(1, 17)]
    if pad_bits != want_pads:
        errors.append(f'kSrPadBit = {pad_bits}, the chain gives {want_pads}')
    for const, net in (('kSrShiftBit', 'KEY_SHIFT'), ('kSrEncoderSwitchBit', 'KEY_ENC')):
        if ints(text, const) != bits[net]:
            errors.append(f'{const} = {ints(text, const)}, the chain gives {bits[net]}')
    for e in errors:
        print('MISMATCH:', e)
    print(f'check-pins: {len(GPIO_CONSTANTS) + 4} items, {len(errors)} mismatches')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
