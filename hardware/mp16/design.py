"""PATS MP-16 DIY kit, rev 2: one board, everything on it. Source of truth for parts, nets and placement.

The PATS UI board's front-end (keys, per-key LEDs, 74HC165 chain, encoder, OLED socket; PATS repo
pats-core/hardware/ui/design.py) on the same MP-16 outline, plus what used to be on the RP2040-Zero
module and the rev-1 board: a bare RP2040 with QSPI flash and crystal, USB-C, TRS MIDI In/Out, a LiPo
with charger, power path, reverse-polarity protection, fuel gauge, 3.3 V and a 5 V LED supply.
Decisions: docs/SPEC.md. Pins: must match firmware/libraries/MP16/src/board_pins.h (rev 2).

Coordinates: mm, MP-16 frame seen from above (KLE origin: x right, y down, (0, 0) = top-left of the
board, y = 0 is the edge with the jacks). The enclosure STLs use the same x; y_stl = 104.775 - y.

Sides: every machine-placed part is on the bottom (B), as on the rev-1 board, so JLCPCB assembles one
side. Hand-soldered on top: encoder, OLED header, expansion header.

FIXED POSITIONS (Samuel, 2026-10-22): the key switches with their sockets and LEDs, the encoder, the
OLED module, the TRS jacks, the power switch, USB-C and the side-view charge LED never move (enclosure and
plate). Everything else may be moved to make the board work, the battery plug included. The jacks, USB-C, power switch,
charge LED and battery plug sit exactly where rev 1 had them (pin_targets from the rev-1 board), so the
existing enclosure fits.
"""
from parts import Design, MP16_HOLES, MP16_OUTLINE, PITCH

NAME = 'mp16'
TITLE = 'PATS MP-16 DIY kit rev 2'
BOARD = MP16_OUTLINE
# JLCPCB 2-layer limits with a little margin: the RP2040's 0.4 mm-pitch QFN needs 0.15 mm tracks.
CLEARANCE = 0.13
MIN_TRACK = 0.127
LED_OFFSET = (0.0, 5.08)  # MX LED window: south of the switch centre (contacts are north)

d = Design(side='B')
parts = d.parts
add, res, cap = d.add, d.res, d.cap


# 0402 parts in the crowded top band (RP2040, charger, MIDI). LCSC numbers: JLCPCB basic parts, listed in
# hardware/PARTS.md with how sure each one is; check them all against the JLCPCB preview before ordering.
C0402 = {'100n': 'C1525', '1u': 'C52923', '10n': 'C15195', '15p': 'C1548', '100p': 'C1546', '1n': 'C1523'}
R0402 = {'0': 'C17168', '10': 'C25077', '27': 'C25100', '33': 'C25105', '220': 'C25091', '1k': 'C11702',
         '1.5k': 'C25867', '2.2k': 'C25879', '4.7k': 'C25900', '5.1k': 'C25905', '10k': 'C25744', '100k': 'C25741'}


def cap0402(ref, value, a, b, at, rot=0, block='', **kw):
    return add(ref, 'Device:C', 'Capacitor_SMD:C_0402_1005Metric', value, {'1': a, '2': b}, at, rot, 'B',
               block=block, lcsc=C0402.get(value, ''), **kw)


def res0402(ref, value, a, b, at, rot=0, block='', **kw):
    return add(ref, 'Device:R', 'Resistor_SMD:R_0402_1005Metric', value, {'1': a, '2': b}, at, rot, 'B',
               block=block, lcsc=R0402.get(value, ''), **kw)


# ---------------------------------------------------------------------------
# Rev-1 positions of the parts that must meet the enclosure's openings: pad centres on the rev-1
# board (hardware/reference/rev1-pcb.easyeda.json, converted to this frame). The footprints are the
# ones converted from that board, so the build solves their rotation and lands every pad on its target.
# Jack pads: A/B/C on rev 1 = S/R/T here.
# ---------------------------------------------------------------------------
REV1 = {
    'MIDI_IN_JACK': {'S': (23.0579, 2.2901), 'R': (16.058, 4.0401), 'T': (23.0579, 9.1399)},
    'MIDI_OUT_JACK': {'S': (57.3479, 2.2901), 'R': (50.3479, 4.0401), 'T': (57.3479, 9.1399)},
    'POWER_SWITCH': {'1': (66.0758, 3.6497), '2': (69.0758, 3.6497), '3': (70.5757, 3.6497)},
    'BATTERY': {'1': (66.421, 27.67), '2': (66.421, 25.67)},
    'CHARGE_LED': {'1': (62.0606, 0.762), '2': (60.3674, 0.762)},
}

# ---------------------------------------------------------------------------
# Keys and LEDs: Shift + 4x4 pads, Kailh hot-swap sockets and SK6812MINI-E on the back (as the UI board).
# ---------------------------------------------------------------------------
keys = [('SHIFT', (3.5 * PITCH, 0.75 * PITCH))]
keys += [(f'P{n + 1}', ((n % 4 + 0.5) * PITCH, (n // 4 + 2) * PITCH)) for n in range(16)]

for i, (name, (x, y)) in enumerate(keys):
    add(f'SW{i + 1}', 'Switch:SW_Push', 'PATS:MX-Hotswap-1U', name,
        {'1': f'KEY_{name}', '2': 'GND'}, (x, y), 0, 'B', block='keys',
        mpn='Kailh CPG151101S11-16', lcsc='C41430893')
    lx, ly = x + LED_OFFSET[0], y + LED_OFFSET[1]
    add(f'D{i + 1}', 'LED:SK6812', 'PATS:LED_SK6812MINI-E_3.2x2.8mm_P1.5mm_ReverseMount', 'SK6812MINI-E',
        {'1': 'GND', '2': f'LED_D{i}', '3': 'VLED', '4': f'LED_D{i + 1}' if i < len(keys) - 1 else None},
        (lx, ly), 0, 'B', block='leds', mpn='SK6812MINI-E', lcsc='C9900001298')
    cap(f'C{i + 1}', '100n', 'VLED', 'GND', (lx - 5.0, ly), 90, block='leds', lcsc='C14663')

# LED data: 3.3 V from GPIO2 -> 74AHCT1G125 powered from VLED (5 V) -> 33 R -> Shift's LED.
add('U4', '74xGxx:74AHCT1G125', 'Package_TO_SOT_SMD:SOT-23-5', '74AHCT1G125',
    {'1': 'GND', '2': 'LED_DATA', '3': 'GND', '4': 'LED_DRV', '5': 'VLED'}, (59.0, 19.2), 90, 'B',
    block='leds', mpn='74AHCT1G125GV', lcsc='C12494', note='3.3 V -> 5 V level shifter for the LED data line')
res0402('R1', '33', 'LED_DRV', 'LED_D0', (59.6, 22.4), 0, block='leds')
cap0402('C18', '100n', 'VLED', 'GND', (57.5, 22.4), 0, block='leds')

# ---------------------------------------------------------------------------
# Encoder (Bourns PEC11R, top side, rev-1 position), pull-ups and RC filters; push switch -> U3.
# ---------------------------------------------------------------------------
add('ENC1', 'Device:RotaryEncoder_Switch', 'PATS:RotaryEncoder_Bourns_PEC11R-4215F-S0024',
    'PEC11R 24 PPR + switch', {'A': 'ENC_A', 'B': 'ENC_B', 'C': 'GND', 'S1': 'KEY_ENC', 'S2': 'GND'},
    (9.525, 14.288), 0, 'F', block='input', mpn='Bourns PEC11R-4215F-S0024', lcsc='C143790',
    extra_pads={'MP': 'GND'}, note='footprint and position from the rev-1 board; hand-soldered')
res0402('R2', '10k', 'ENC_A', '+3V3', (5.0, 24.0), 0, block='input')
res0402('R3', '10k', 'ENC_B', '+3V3', (14.0, 24.0), 180, block='input')
cap0402('C19', '10n', 'ENC_A', 'GND', (7.4, 24.0), 0, block='input')
cap0402('C20', '10n', 'ENC_B', 'GND', (11.6, 24.0), 0, block='input')

# ---------------------------------------------------------------------------
# Switch inputs: 3x 74HC165 (TSSOP-16), each next to the keys it reads.
#   U1: pads 1-8, between key rows 1 and 2.   U2: pads 9-16, between rows 3 and 4.
#   U3: Shift, encoder push, 6 spares; between key rows 1 and 2 left of U1. (It started next to the
#   RP2040; there it walled in the RP2040's GPIO16-29 side: route 2 left SR_*, EXP_*, ENC_*, RUN open.)
# Chain: U2 Q7 -> U1 DS, U1 Q7 -> U3 DS, U3 Q7 -> SR_DATA (GPIO16). U2 DS = GND.
# Bits read (first = bit 23): U3 D7..D0, U1 D7..D0, U2 D7..D0 (board_pins.h, kSrPadBit).
# ---------------------------------------------------------------------------
sr_inputs = {
    'U1': [f'KEY_P{n}' for n in range(1, 9)],
    'U2': [f'KEY_P{n}' for n in range(9, 17)],
    'U3': ['KEY_SHIFT', 'KEY_ENC'] + [f'SR_SPARE{k}' for k in range(1, 7)],
}
chain = {'U3': ('SR_DATA', 'SR_C13'), 'U1': ('SR_C13', 'SR_C21'), 'U2': ('SR_C21', 'GND')}  # (Q7, DS)
d_pins = {'D0': '11', 'D1': '12', 'D2': '13', 'D3': '14', 'D4': '3', 'D5': '4', 'D6': '5', 'D7': '6'}
SR_PLACE = {  # chip centre, rotation; decoupling cap; the two pull-up packs (D0-D3, D4-D7), their rotation
    'U1': ((37.9, 47.0), 0, (38.1, 43.5), [(34.6, 41.0), (39.4, 41.0)], 90),
    'U2': ((37.9, 85.1), 0, (38.1, 81.6), [(34.6, 79.1), (39.4, 79.1)], 90),
    'U3': ((18.0, 47.0), 0, (18.0, 43.5), [(15.6, 41.0), (20.0, 41.0)], 90),
}
rn = 1
for k, (ref, ((ux, uy), urot, cxy, rn_xy, rn_rot)) in enumerate(SR_PLACE.items()):
    q7, ds = chain[ref]
    pins = {'1': 'SR_LOAD', '2': 'SR_CLK', '7': None, '8': 'GND', '9': q7, '10': ds, '15': 'GND', '16': '+3V3'}
    for i, net in enumerate(sr_inputs[ref]):
        pins[d_pins[f'D{i}']] = net
    add(ref, '74xx:74HC165', 'Package_SO:TSSOP-16_4.4x5mm_P0.65mm', '74HC165', pins, (ux, uy), urot, 'B',
        block='input', mpn='74HC165PW', lcsc='C80696')
    cap(f'C{21 + k}', '100n', '+3V3', 'GND', cxy, 0, block='input', lcsc='C14663')
    for j in range(2):
        nets = sr_inputs[ref][4 * j:4 * j + 4]
        add(f'RN{rn}', 'Device:R_Pack04', 'Resistor_SMD:R_Array_Convex_4x0603', '4x10k',
            {'1': nets[0], '2': nets[1], '3': nets[2], '4': nets[3], '5': '+3V3', '6': '+3V3', '7': '+3V3', '8': '+3V3'},
            rn_xy[j], rn_rot, 'B', block='input', mpn='4D03WGJ0103T5E', lcsc='C29718')
        rn += 1

# ---------------------------------------------------------------------------
# OLED socket (top, rev-1 position) and the I2C pull-ups (OLED 0x3C, fuel gauge 0x36).
# ---------------------------------------------------------------------------
add('J2', 'Connector_Generic:Conn_01x04', 'Connector_PinSocket_2.54mm:PinSocket_1x04_P2.54mm_Vertical',
    'OLED SSD1306 I2C', {'1': 'GND', '2': '+3V3', '3': 'I2C_SCL', '4': 'I2C_SDA'},
    (41.91, 25.653), 270, 'F', block='connectors',
    note='as the rev-1 board: pins at y 25.653, left to right SDA SCL VCC GND, module (HS96L03W2C03) above')
res0402('R4', '4.7k', 'I2C_SDA', '+3V3', (45.6, 21.6), 90, block='connectors')
res0402('R5', '4.7k', 'I2C_SCL', '+3V3', (46.6, 21.6), 270, block='connectors')

# ---------------------------------------------------------------------------
# RP2040 (QFN-56, 0.4 mm), W25Q128JV flash, 12 MHz crystal: the Raspberry Pi minimal design
# ("Hardware design with RP2040", Raspberry Pi Ltd). On the bottom the footprint is mirrored: seen from
# above, GPIO0-11 face right, GPIO18-29 left, USB and QSPI up (towards USB-C), crystal and SWD down.
# GPIO allocation: docs/SPEC.md "RP2040 pin allocation" = board_pins.h.
# ---------------------------------------------------------------------------
GPIO = {
    0: 'MIDI_TX', 1: 'MIDI_RX', 2: 'LED_DATA', 3: None, 4: 'I2C_SDA', 5: 'I2C_SCL', 6: 'ENC_A', 7: 'ENC_B',
    8: None, 9: None, 10: None, 11: None, 12: None, 13: None, 14: None, 15: None,
    16: 'SR_DATA', 17: 'SR_LOAD', 18: 'SR_CLK', 19: 'EXP_MOSI', 20: 'EXP_LATCH', 21: None, 22: 'PGOOD_N',
    23: None, 24: None, 25: None, 26: 'AIN1', 27: 'AIN2', 28: 'AIN3', 29: 'AIN4',
}
RP2040_GPIO_PIN = {g: p for g, p in zip(range(30), [2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18,
                                                     27, 28, 29, 30, 31, 32, 34, 35, 36, 37, 38, 39, 40, 41])}
rp = {str(RP2040_GPIO_PIN[g]): net for g, net in GPIO.items()}
rp.update({
    '1': '+3V3', '10': '+3V3', '22': '+3V3', '33': '+3V3', '42': '+3V3', '49': '+3V3',  # IOVDD
    '43': '+3V3',            # ADC_AVDD
    '44': '+3V3',            # VREG_IN: the internal 1.1 V regulator
    '45': 'VDD_CORE', '23': 'VDD_CORE', '50': 'VDD_CORE',  # VREG_VOUT -> DVDD
    '48': '+3V3',            # USB_VDD
    '46': 'RP_USB_DN', '47': 'RP_USB_DP',
    '19': 'GND',             # TESTEN
    '20': 'XIN', '21': 'XOUT',
    '24': 'SWCLK', '25': 'SWDIO', '26': 'RUN',
    '51': 'QSPI_SD3', '52': 'QSPI_SCLK', '53': 'QSPI_SD0', '54': 'QSPI_SD2', '55': 'QSPI_SD1', '56': 'QSPI_SS',
    '57': 'GND',
})
RP = (34.6, 15.6)


def rp_pin(n):
    """Centre of RP2040 pin n seen from above (the part is on the bottom, so its footprint is mirrored):
    pins 1-14 down the right side, 15-28 right to left along the bottom, 29-42 up the left side,
    43-56 left to right along the top; 0.4 mm pitch, pin rows 3.4 mm from the centre."""
    x, y = RP
    if n <= 14:
        return (round(x + 3.4, 3), round(y - 2.6 + (n - 1) * 0.4, 3))
    if n <= 28:
        return (round(x + 2.6 - (n - 15) * 0.4, 3), round(y + 3.4, 3))
    if n <= 42:
        return (round(x - 3.4, 3), round(y + 2.6 - (n - 29) * 0.4, 3))
    return (round(x - 2.6 + (n - 43) * 0.4, 3), round(y - 3.4, 3))


add('U10', 'MCU_RaspberryPi:RP2040', 'Package_DFN_QFN:QFN-56-1EP_7x7mm_P0.4mm_EP3.2x3.2mm', 'RP2040', rp,
    RP, 0, 'B', block='mcu', mpn='RP2040', lcsc='C2040')
# Decoupling: one 100 nF per IOVDD pin, 1 uF on VREG_IN and VREG_VOUT. Each capacitor sits 1.9 mm out from
# its pin row, opposite its pin, so the signal pins between them keep a free way out (route 3 walled pins
# in with capacitors touching the pin rows). Upright (rot 90) on the sides, a 1.2 mm-pitch row on top.
TOP_Y = 10.15  # the row between USB-C (its body ends at y 9.2) and the RP2040
cap0402('C30', '100n', '+3V3', 'GND', (rp_pin(1)[0] + 1.9, rp_pin(1)[1]), 90, block='mcu', note='IOVDD pin 1')
cap0402('C31', '100n', '+3V3', 'GND', (rp_pin(10)[0] + 1.9, rp_pin(10)[1]), 90, block='mcu', note='IOVDD pin 10')
cap0402('C33', '100n', '+3V3', 'GND', (rp_pin(33)[0] - 1.9, rp_pin(33)[1]), 90, block='mcu', note='IOVDD pin 33')
cap0402('C34', '100n', '+3V3', 'GND', (rp_pin(42)[0] - 1.9, rp_pin(42)[1]), 90, block='mcu', note='IOVDD pin 42, ADC_AVDD')
cap0402('C37', '1u', 'VDD_CORE', 'GND', (31.4, TOP_Y), 90, block='mcu', note='VREG_VOUT')
cap0402('C36', '1u', '+3V3', 'GND', (32.6, TOP_Y), 90, block='mcu', note='VREG_IN')
cap0402('C35', '100n', '+3V3', 'GND', (34.2, TOP_Y), 90, block='mcu', note='IOVDD pin 49, USB_VDD')
cap0402('C39', '100n', 'VDD_CORE', 'GND', (35.4, TOP_Y), 90, block='mcu', note='DVDD pin 50')
cap0402('C32', '100n', '+3V3', 'GND', (rp_pin(22)[0], rp_pin(22)[1] + 2.2), 90, block='mcu', note='IOVDD pin 22')
cap0402('C38', '100n', 'VDD_CORE', 'GND', (rp_pin(23)[0] - 1.2, rp_pin(23)[1] + 2.2), 90, block='mcu', note='DVDD pin 23')

# Flash right of the RP2040's QSPI corner (pins 51-56, top right), pins facing it.
add('U11', 'Memory_Flash:W25Q128JVS', 'Package_SO:SOIC-8_5.23x5.23mm_P1.27mm', 'W25Q128JV',
    {'1': 'QSPI_SS', '2': 'QSPI_SD1', '3': 'QSPI_SD2', '4': 'GND', '5': 'QSPI_SD0', '6': 'QSPI_SCLK',
     '7': 'QSPI_SD3', '8': '+3V3'}, (44.0, 15.6), 90, 'B', block='mcu', mpn='W25Q128JVSIQ', lcsc='C97521',
    note='16 MB; Arduino: Generic RP2040, boot2 W25Q080 QSPI /2')
cap0402('C40', '100n', '+3V3', 'GND', (45.0, 10.1), 0, block='mcu')
# BOOT: hold while plugging in or pressing RESET -> USB mass-storage bootloader (pulls QSPI_SS low).
res0402('R10', '1k', 'QSPI_SS', 'BOOT_BTN', (38.8, TOP_Y), 90, block='mcu')
add('SW18', 'Switch:SW_Push', 'Button_Switch_SMD:SW_Push_1P1T_NO_CK_KMR2', 'BOOT', {'1': 'BOOT_BTN', '2': 'GND'},
    (28.6, 26.5), 90, 'B', block='mcu', mpn='C&K KMR221GLFS', lcsc='C72443',
    note='reachable through the window of the open bottom shell')
add('SW19', 'Switch:SW_Push', 'Button_Switch_SMD:SW_Push_1P1T_NO_CK_KMR2', 'RESET', {'1': 'RUN', '2': 'GND'},
    (23.4, 26.5), 90, 'B', block='mcu', mpn='C&K KMR221GLFS', lcsc='C72443')
res0402('R11', '10k', 'RUN', '+3V3', (31.8, rp_pin(26)[1] + 2.2), 90, block='mcu')

# 12 MHz crystal, as the Raspberry Pi design: 1 k series on XOUT, 15 pF loads (ABM8-272-T3, CL 10 pF).
# Under the RP2040's right half, below XIN/XOUT (pins 20, 21).
add('Y1', 'Device:Crystal_GND24', 'Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm', '12MHz',
    {'1': 'XIN', '2': 'GND', '3': 'XTAL_OUT', '4': 'GND'}, (38.6, 21.6), 0, 'B', block='mcu',
    mpn='Abracon ABM8-272-T3', lcsc='C20625731', note='12 MHz, CL 10 pF, approved by Abracon for the RP2040')
res0402('R12', '1k', 'XOUT', 'XTAL_OUT', (35.8, rp_pin(21)[1] + 2.2), 90, block='mcu')
cap0402('C41', '15p', 'XIN', 'GND', (42.2, 21.0), 0, block='mcu')
cap0402('C42', '15p', 'XTAL_OUT', 'GND', (42.2, 22.4), 0, block='mcu')

# SWD test pads (debug probe), next to RESET.
for k, (net, x) in enumerate([('SWCLK', 25.8), ('SWDIO', 28.0), ('GND', 30.2)]):
    add(f'TP{k + 1}', 'Connector:TestPoint', 'TestPoint:TestPoint_Pad_D1.0mm', net, {'1': net},
        (x, 22.6), 0, 'B', block='mcu', note='SWD')

# ---------------------------------------------------------------------------
# USB-C (data + charging), centred on the top edge where the RP2040-Zero's socket was.
# ---------------------------------------------------------------------------
add('J3', 'Connector:USB_C_Receptacle_USB2.0_16P', 'Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12',
    'USB-C', {'A4': 'VBUS_IN', 'A9': 'VBUS_IN', 'B4': 'VBUS_IN', 'B9': 'VBUS_IN', 'A1': 'GND', 'A12': 'GND',
              'B1': 'GND', 'B12': 'GND', 'S1': 'GND', 'A5': 'CC1', 'B5': 'CC2', 'A6': 'USB_DP', 'B6': 'USB_DP',
              'A7': 'USB_DN', 'B7': 'USB_DN', 'A8': None, 'B8': None},
    (38.1, 3.9), 180, 'B', block='power', mpn='HRO TYPE-C-31-M-12', lcsc='C165948')
res0402('R13', '5.1k', 'CC1', 'GND', (27.6, 1.2), 0, block='power')
res0402('R14', '5.1k', 'CC2', 'GND', (27.6, 2.6), 0, block='power')
add('F1', 'Device:Polyfuse', 'Fuse:Fuse_1206_3216Metric', '1.5A hold', {'1': 'VBUS_IN', '2': 'VBUS'},
    (30.4, 5.4), 90, 'B', block='power', mpn='1206 PTC, 1.5 A hold, 6 V',
    note='short-circuit protection for the USB port; the charger limits normal input current to 1.3 A')
add('U12', 'Power_Protection:USBLC6-2SC6', 'Package_TO_SOT_SMD:SOT-23-6', 'USBLC6-2SC6',
    {'1': 'USB_DP', '6': 'USB_DP', '3': 'USB_DN', '4': 'USB_DN', '2': 'GND', '5': 'VBUS'},
    (46.0, 7.2), 0, 'B', block='power', mpn='USBLC6-2SC6', lcsc='C7519')
res0402('R15', '27', 'USB_DP', 'RP_USB_DP', (37.6, TOP_Y), 90, block='mcu', note='USB series, RP2040 design guide')
res0402('R16', '27', 'USB_DN', 'RP_USB_DN', (36.6, TOP_Y), 90, block='mcu')

# ---------------------------------------------------------------------------
# Charger + power path: BQ24074 (as the PATS audio board), USB in, VSYS out, 1S LiPo.
# Charge current 0.3 A (ISET 3.0 k): safe at 1C for the small generic packs from 300 mAh.
# Charge LED on /CHG, powered from VBUS (lit while charging, even with the power switch off), at the
# rev-1 position on the edge. /CHG goes to the LED only: wired to a GPIO too, it would feed the
# switched-off RP2040 through the LED. Firmware reads charging from the fuel gauge, USB from /PGOOD.
# ---------------------------------------------------------------------------
add('U13', 'Battery_Management:BQ24074RGT', 'Package_DFN_QFN:VQFN-16-1EP_3x3mm_P0.5mm_EP1.6x1.6mm',
    'BQ24074', {'13': 'VBUS', '10': 'VSYS', '11': 'VSYS', '2': 'VBAT', '3': 'VBAT', '1': 'TS', '4': 'GND',
                '5': 'VSYS', '6': 'GND', '7': 'PGOOD_N', '9': 'CHG_N', '8': 'GND', '17': 'GND',
                '12': 'ILIM', '14': None, '15': 'ITERM', '16': 'ISET'},
    (53.8, 27.4), 0, 'B', block='power', mpn='BQ24074RGTR', lcsc='C54313',
    note='EN2=1, EN1=0: input limit set by ILIM; /CE=0: charging on; TMR open: default safety timers')
cap0402('C50', '1u', 'VBUS', 'GND', (50.4, 24.6), 0, block='power')
cap('C51', '10u', 'VSYS', 'GND', (57.6, 25.6), 90, block='power')
cap('C52', '10u', 'VBAT', 'GND', (53.8, 30.35), 0, block='power')
res0402('R20', '3k', 'ISET', 'GND', (50.4, 26.4), 0, block='power', note='charge current 890/R = 0.30 A')
res0402('R21', '1k', 'ILIM', 'ILIM_R', (50.4, 27.8), 0, block='power',
    note='input current limit: R21 + R22 = 1.18k, 1550/R = 1.3 A')
res0402('R22', '180', 'ILIM_R', 'GND', (50.4, 29.2), 0, block='power')
res0402('R23', '4.12k', 'ITERM', 'GND', (50.4, 30.4), 0, block='power', note='as TI typical application')
res0402('R24', '10k', 'TS', 'GND', (57.6, 29.2), 90, block='power',
    note='fixed 10k: no temperature sensing (generic packs have no NTC)')
add('D20', 'Device:LED', 'PATS:LED_SideView_XL-1606_RD', 'charge', {'1': 'LED_CHG', '2': 'VBUS'},
    side='B', block='power', pin_targets=REV1['CHARGE_LED'], mpn='XINGLIGHT XL-1606SURC', lcsc='C965860',
    note='side-view red LED at the rev-1 position; on while charging')
res0402('R25', '1.5k', 'LED_CHG', 'CHG_N', (64.8, 6.1), 0, block='power')

# ---------------------------------------------------------------------------
# Battery: JST-PH at the rev-1 position and pinout (pin 1 = GND), for generic 1S LiPo packs.
# Reverse polarity: Q1 (P-MOSFET) passes the battery when it is the right way round. A gate simply
# tied to GND would also turn on for a reversed pack while USB powers the charger (the charger's VBAT
# then sits above the gate) and charge the cell backwards; Q2 turns Q1 off whenever the battery pin is
# below VBAT, so a reversed pack is blocked with or without USB. docs/decisions/0001-battery-reverse-protection.md
# ---------------------------------------------------------------------------
add('J7', 'Connector_Generic:Conn_01x02', 'PATS:JST_PH_S2B-PH-K-S_Horizontal',
    'LiPo 1S (pin 1 = GND, pin 2 = +)', {'1': 'GND', '2': 'BATT_P'}, side='B', block='power',
    pin_targets=REV1['BATTERY'], mpn='JST S2B-PH-K-S(LF)(SN)', lcsc='C173752',
    note='rev-1 part, position and pinout; through-hole')
add('Q1', 'Device:Q_PMOS_GSD', 'Package_TO_SOT_SMD:SOT-23', 'DMG2305UX', {'1': 'Q1_G', '2': 'VBAT', '3': 'BATT_P'},
    (70.4, 25.0), 90, 'B', block='power', mpn='DMG2305UX-7', lcsc='C150470',
    note='-20 V, 4.2 A, 52 mOhm at -4.5 V; body diode from the battery to VBAT')
res0402('R26', '100k', 'Q1_G', 'GND', (70.9, 22.4), 0, block='power')
add('Q2', 'Transistor_BJT:MMBT3906', 'Package_TO_SOT_SMD:SOT-23', 'MMBT3906', {'1': 'Q2_B', '2': 'VBAT', '3': 'Q1_G'},
    (70.4, 28.9), 90, 'B', block='power', mpn='MMBT3906', lcsc='C2940',
    note='pulls Q1 gate to VBAT (off) while the battery pin is below VBAT')
res0402('R27', '100k', 'Q2_B', 'BATT_P', (73.0, 22.4), 0, block='power')

# Fuel gauge on VBAT (after the protection, before the switch): keeps tracking while switched off.
add('U15', 'PATS:MAX17048', 'Package_DFN_QFN:TDFN-8-1EP_2x2mm_P0.5mm_EP0.8x1.2mm', 'MAX17048',
    {'1': 'GND', '2': 'VBAT_GAUGE', '3': 'VBAT_GAUGE', '4': 'GND', '5': 'GAUGE_ALRT', '6': 'GND', '7': 'I2C_SCL',
     '8': 'I2C_SDA', '9': 'GND'},
    (73.0, 17.0), 0, 'B', block='power', mpn='MAX17048G+T10', lcsc='C2682616',
    note='I2C 0x36: battery %, charge rate (charging = positive rate)')
cap0402('C53', '100n', 'VBAT_GAUGE', 'GND', (73.0, 19.4), 0, block='power')
res0402('R28', '0', 'VBAT', 'VBAT_GAUGE', (73.0, 20.6), 0, block='power',
    note='gauge supply/sense link; remove to isolate the gauge')
add('TP4', 'Connector:TestPoint', 'TestPoint:TestPoint_Pad_D1.0mm', 'GAUGE_ALRT', {'1': 'GAUGE_ALRT'},
    (75.0, 22.4), 0, 'B', block='power')

# On/off: slide switch at the rev-1 position -> TPS22917 load switch -> VSW. Charging works with the
# switch off; everything after the load switch (RP2040, LEDs, OLED) is off with it.
add('SW20', 'Switch:SW_SPDT', 'PATS:SW_SPDT_MK-12C02-G015', 'Power',
    {'1': 'VSYS', '2': 'PWR_ON', '3': None}, side='B', block='power', pin_targets=REV1['POWER_SWITCH'],
    mpn='G-Switch MK-12C02-G015', lcsc='C2911519', extra_pads={'SH': 'GND'},
    note='rev-1 part and position (enclosure slot at x 66.8)')
res0402('R29', '100k', 'PWR_ON', 'GND', (68.6, 6.1), 0, block='power')
add('U16', 'Power_Management:TPS22917DBV', 'Package_TO_SOT_SMD:SOT-23-6', 'TPS22917',
    {'1': 'VSYS', '6': 'VSW', '3': 'PWR_ON', '4': 'CT', '5': None, '2': 'GND'},
    (46.6, 26.2), 0, 'B', block='power', mpn='TPS22917DBVR', lcsc='C2681320', note='2 A load switch')
cap0402('C54', '1n', 'CT', 'GND', (46.4, 29.0), 0, block='power', note='soft start')
cap('C55', '10u', 'VSYS', 'GND', (44.4, 29.55), 90, block='power')
cap('C56', '10u', 'VSW', 'GND', (48.5, 29.55), 90, block='power')

# 3.3 V: LDO from VSW (RP2040, flash, 74HC165s, OLED, MIDI opto; < 100 mA).
add('U17', 'Regulator_Linear:AP2112K-3.3', 'Package_TO_SOT_SMD:SOT-23-5', 'AP2112K-3.3',
    {'1': 'VSW', '2': 'GND', '3': 'VSW', '4': None, '5': '+3V3'}, (54.0, 20.4), 90, 'B', block='power',
    mpn='AP2112K-3.3TRG1', lcsc='C51118')
cap0402('C57', '1u', 'VSW', 'GND', (54.0, 23.1), 0, block='power')
cap('C58', '10u', '+3V3', 'GND', (56.5, 19.2), 90, block='power')

# 5 V for the LEDs: MT3608 boost from VSW (as the PATS audio board): Vout = 0.6 V x (1 + 75k/10k) = 5.1 V.
# In the key area between rows 1 and 2, right of pad 4's LED, where the LED supply is used.
add('U18', 'Regulator_Switching:MT3608', 'Package_TO_SOT_SMD:SOT-23-6', 'MT3608',
    {'5': 'VSW', '4': 'VSW', '1': 'SW_LED', '2': 'GND', '3': 'FB_LED', '6': None}, (73.2, 47.6), 90, 'B',
    block='power', mpn='MT3608', lcsc='C84817')
cap('C60', '22u', 'VSW', 'GND', (73.4, 42.0), 90, block='power', big=True, lcsc='C45783')
add('L1', 'Device:L', 'Inductor_SMD:L_Coilcraft_XAL4040-XXX', '10uH', {'1': 'VSW', '2': 'SW_LED'},
    (66.0, 47.6), 0, 'B', block='power', mpn='XAL4040-103MEC', lcsc='C5144883',
    note='as the PATS audio board: 10 uH, Isat 3.0 A')
add('D21', 'Device:D_Schottky', 'Diode_SMD:D_SMA', 'SS34', {'2': 'SW_LED', '1': 'VLED'}, (59.0, 47.6), 0, 'B',
    block='power', mpn='SS34', lcsc='C8678')
cap('C61', '22u', 'VLED', 'GND', (54.0, 47.6), 90, block='power', big=True, lcsc='C45783')
cap('C62', '22u', 'VLED', 'GND', (51.8, 47.6), 90, block='power', big=True, lcsc='C45783')
res0402('R30', '75k', 'VLED', 'FB_LED', (75.4, 45.6), 90, block='power')
res0402('R31', '10k', 'FB_LED', 'GND', (75.4, 49.0), 90, block='power')
cap('C24', '22u', 'VLED', 'GND', (62.6, 22.4), 0, block='leds', big=True, lcsc='C45783',
    note='bulk at the start of the LED chain')

# ---------------------------------------------------------------------------
# MIDI In (TRS Type A, rev-1 jack and circuit): ring -> 220 R -> TLP109 LED -> tip; 1N4148 across the
# LED against reverse voltage; sleeve to ground through 100 pF (no ground loop through the cable).
# The TLP109's open-collector output gets a real 2.2 k pull-up (rev 1 relied on the RP2040's ~50 k).
# ---------------------------------------------------------------------------
add('J4', 'Connector_Audio:AudioJack3', 'PATS:Jack_3.5mm_PJ-320-3P-SMT', 'MIDI IN',
    {'S': 'MIDI_IN_S', 'R': 'MIDI_IN_R', 'T': 'MIDI_IN_T'}, side='B', block='midi',
    pin_targets=REV1['MIDI_IN_JACK'], mpn='PJ-320-3P SMT', lcsc='C17701688', note='rev-1 part and position')
cap0402('C70', '100p', 'MIDI_IN_S', 'GND', (25.6, 2.3), 90, block='midi')
res0402('R40', '220', 'MIDI_IN_R', 'MIDI_IN_A', (17.6, 13.5), 90, block='midi')
add('D22', 'Device:D', 'Diode_SMD:D_SOD-123', '1N4148W', {'1': 'MIDI_IN_A', '2': 'MIDI_IN_T'},
    (20.8, 13.4), 180, 'B', block='midi', mpn='1N4148W', lcsc='C81598')
add('U19', 'PATS:TLP109', 'PATS:Toshiba_SO6-5P_TLP109', 'TLP109',
    {'1': 'MIDI_IN_A', '3': 'MIDI_IN_T', '4': 'GND', '5': 'MIDI_RX', '6': '+3V3'}, (21.0, 19.0), 0, 'B',
    block='midi', mpn='TLP109(TPL,E', lcsc='C406798', note='rev-1 part and position')
res0402('R41', '2.2k', 'MIDI_RX', '+3V3', (17.8, 21.0), 90, block='midi')
cap0402('C71', '100n', '+3V3', 'GND', (17.8, 18.0), 90, block='midi')

# MIDI Out (TRS Type A, 3.3 V): ring <- 33 R <- +3V3, tip <- 10 R <- TX (MIDI 1.0 3.3 V values),
# sleeve to ground. ESD: a USBLC6 clamps both lines at the jack.
add('J5', 'Connector_Audio:AudioJack3', 'PATS:Jack_3.5mm_PJ-320-3P-SMT', 'MIDI OUT',
    {'S': 'GND', 'R': 'MIDI_OUT_R', 'T': 'MIDI_OUT_T'}, side='B', block='midi',
    pin_targets=REV1['MIDI_OUT_JACK'], mpn='PJ-320-3P SMT', lcsc='C17701688', note='rev-1 part and position')
res0402('R42', '33', '+3V3', 'MIDI_OUT_R', (46.0, 3.2), 0, block='midi')
res0402('R43', '10', 'MIDI_TX', 'MIDI_OUT_T', (54.6, 12.6), 0, block='midi')
add('U20', 'Power_Protection:USBLC6-2SC6', 'Package_TO_SOT_SMD:SOT-23-6', 'USBLC6-2SC6',
    {'1': 'MIDI_OUT_R', '6': 'MIDI_OUT_R', '3': 'MIDI_OUT_T', '4': 'MIDI_OUT_T', '2': 'GND', '5': '+3V3'},
    (61.4, 4.4), 90, 'B', block='midi', mpn='USBLC6-2SC6', lcsc='C7519', note='ESD on the MIDI Out jack')

# ---------------------------------------------------------------------------
# Expansion header (2x6, 2.54 mm, through-hole; fit it on the side the add-on needs): 4 analog inputs,
# the 74HC595 lines for an analog-mux board (data, clock = the 74HC165 clock, latch), I2C and power.
# Replaces rev 1's 3-pin analog header.
# ---------------------------------------------------------------------------
EXP_PINS = {1: '+3V3', 2: 'GND', 3: 'AIN1', 4: 'AIN2', 5: 'AIN3', 6: 'AIN4', 7: 'EXP_MOSI', 8: 'SR_CLK',
            9: 'EXP_LATCH', 10: 'GND', 11: 'I2C_SDA', 12: 'I2C_SCL'}
J6_PIN1 = (5.6, 29.24)  # odd pins in the lower row, even pins 2.54 mm above; clear of H3 and the row-1 sockets
add('J6', 'Connector_Generic:Conn_02x06_Odd_Even', 'Connector_PinHeader_2.54mm:PinHeader_2x06_P2.54mm_Vertical',
    'EXPANSION', {str(k): v for k, v in EXP_PINS.items()}, side='F', block='connectors',
    pin_targets={str(n): (J6_PIN1[0] + 2.54 * ((n - 1) // 2), J6_PIN1[1] - 2.54 * ((n - 1) % 2)) for n in EXP_PINS},
    mpn='2x6 2.54 mm pin header (optional, hand-soldered)')

# ---------------------------------------------------------------------------
# Mounting holes: the six of the MP-16 board.
# ---------------------------------------------------------------------------
for i, (x, y) in enumerate(MP16_HOLES):
    add(f'H{i + 1}', 'Mechanical:MountingHole', 'PATS:MountingHole_2.5mm', '2.5 mm', {}, (x, y), 0, 'F', block='mech')

# Wide (0.6 mm) power nets. +3V3 and VDD_CORE are not among them: they carry < 100 mA and must reach the
# RP2040's 0.2 mm pads (0.4 mm pitch), the 74HC165s' 0.65 mm pitch and 0402 parts; they are 'Supply' below.
POWER_NETS = {'VBUS_IN', 'VBUS', 'VSYS', 'VBAT', 'BATT_P', 'VSW', 'VLED', 'SW_LED'}
NETCLASSES = {
    # The RP2040's 0.4 mm-pitch pins: 0.15 mm tracks.
    'Fine': (0.15, sorted({n for n in rp.values() if n} - {'GND', '+3V3', 'VDD_CORE'})),
    'Medium': (0.4, ['VBUS', 'VSYS', 'VBAT']),  # the BQ24074's 0.5 mm-pitch power pins
    'Usb': (0.2, ['USB_DP', 'USB_DN']),
    'Supply': (0.2, ['+3V3', 'VDD_CORE']),  # into fine-pitch pins; 0.2 mm carries far more than they need
    'Ground': (0.3, ['GND']),
}
# Freerouting does not honour the class split on this board (the power stage got every net), so power and
# the rest route together after the escapes; tools/finish.py joins what is left.
ROUTE_STAGES = [
    ('escape', ['Fine', 'Medium', 'Usb', 'Supply']),
    ('rest', ['Power', 'Default']),
]
ROUTE_PASSES = 10  # passes per Freerouting run: it returns to its best result by pass 8 and then repeats
ROUTE_PROMOTE = {'escape': 1, '*': 0}
GND_FANOUT = True
GND_FANOUT_SIDE = 'B'  # every SMD part is on the bottom: vias from their ground pads to the top pour
GND_STITCH = 4.0
DECOUPLED = {'VDD_CORE', 'VBAT_GAUGE'}
ESCAPE = ['U10']  # locked escape stubs out of the RP2040's 0.4 mm pin field before routing (tools/fanout.py)
SILK = []
# Silkscreen labels (tools/silk.py): (text or alternatives, near (x, y), sides, height mm, rotation, may move
# along[, how far]). The two buttons sit side by side in the open bottom shell's window, each named on the
# bottom beside it; the SWD pads above them.
LABELS = [
    ('RESET', (25.95, 26.5), 'B', 0.9, 90, 'y', 0.5),
    ('BOOT', (31.15, 26.5), 'B', 0.9, 90, 'y', 0.5),
    ('SWD', (28.4, 22.6), 'B', 0.7, 0, 'xy', 2.5),  # pads TP1-TP3 = SWCLK, SWDIO, GND (README)
    (('PATS MP-16 rev 2', 'MP-16 rev 2'), (38.1, 102.0), 'B', 1.0, 0, 'xy', 6.0),
]
HIDE_REFS = ['SW18', 'SW19', 'TP1', 'TP2', 'TP3']  # named by the labels above

# DRC findings accepted on purpose:
# - mounting holes at the MP-16 positions sit inside switch outlines (as on the rev-1 and UI boards);
# - reverse-mount LED pads are 0.25 mm from their own cut-out corners (KiCad's footprint).
# - the MIDI Out jack's courtyard reaches into the Shift key's hot-swap socket outline: both at their rev-1
#   positions (the enclosure needs them there); the nearest pads are 0.6 mm apart, as on the rev-1 board.
DRC_ACCEPTED = [('courtyards_overlap', r'Footprint H\d+', r'Footprint SW\d+'),
                ('courtyards_overlap', r'Footprint J5\b', r'Footprint SW1\b'),
                # power switch: rev-1 part and position (fixed); its shield pads sit 0.2 mm from the edge, as on
                # the rev-1 board JLCPCB built (JLCPCB's minimum; 0.3 mm elsewhere on this board)
                ('copper_edge_clearance', r'Edge\.Cuts', r'Pad SH \[GND\] of SW20\b'),
                ('copper_edge_clearance', r'Arc on Edge\.Cuts', r'Pad \d \[[^\]]*\] of D(1[0-7]|[1-9]) ')]
