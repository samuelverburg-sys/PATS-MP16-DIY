#!/usr/bin/env python3
"""Write the PATS symbols and footprints that KiCad 7's libraries lack, from datasheet tables.

  python3 tools/make_lib.py     # writes lib/PATS.kicad_sym and lib/PATS.pretty/QFN-24-...

Symbols are plain boxes (pins left and right); the schematic writer ties every pin to its net
with a label, so only pin numbers, names and types matter. Sources are in THIRD_PARTY.md.
"""
import os

LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lib')

# name -> (footprint, description, left pins, right pins); pin = (number, name, type)
SYMBOLS = {
    'ES8389': ('PATS:QFN-24-1EP_3x3mm_P0.35mm_EP1.7x1.7mm',
               'Everest ES8389 stereo audio codec, QFN-24 3x3 mm 0.35 mm pitch (datasheet rev 1.0)', [
                   ('17', 'AVDD', 'power_in'), ('5', 'DVDD', 'power_in'), ('6', 'PVDD', 'power_in'),
                   ('4', 'MCLK', 'input'), ('8', 'SCLK', 'bidirectional'), ('10', 'LRCK', 'bidirectional'),
                   ('9', 'DSDIN', 'input'), ('11', 'ASDOUT/AD1', 'output'), ('3', 'CCLK', 'input'),
                   ('2', 'CDATA', 'bidirectional'), ('1', 'AD0', 'input'), ('7', 'DGND', 'power_in'),
                   ('18', 'AGND', 'power_in'), ('25', 'PGND', 'power_in'),
               ], [
                   ('24', 'MIC1P', 'input'), ('23', 'MIC1N', 'input'), ('22', 'MIC2P', 'input'),
                   ('21', 'MIC2N', 'input'), ('16', 'LOUTP', 'output'), ('15', 'LOUTN', 'output'),
                   ('12', 'ROUTP', 'output'), ('13', 'ROUTN', 'output'), ('19', 'VMID', 'passive'),
                   ('20', 'ADCVREF', 'passive'), ('14', 'DACVREF', 'passive'),
               ]),
    'MAX17048': ('Package_DFN_QFN:TDFN-8-1EP_2x2mm_P0.5mm_EP0.8x1.2mm',
                 'Analog Devices MAX17048 1-cell fuel gauge, I2C 0x36, TDFN-8 2x2 mm (T822+3)', [
                     ('3', 'VDD', 'power_in'), ('2', 'CELL', 'input'), ('1', 'CTG', 'input'),
                     ('6', 'QSTRT', 'input'), ('4', 'GND', 'power_in'), ('9', 'EP', 'passive'),
                 ], [
                     ('7', 'SCL', 'input'), ('8', 'SDA', 'bidirectional'), ('5', 'ALRT', 'open_collector'),
                 ]),
    # MIDI In opto-coupler of the MP-16 (rev 1 board, LCSC C406798). 5-pin SO6: no pin 2. Pinout as wired
    # on the rev 1 board (pad nets in hardware/reference/rev1-pcb.easyeda.json) and the Toshiba datasheet.
    'TLP109': ('PATS:Toshiba_SO6-5P_TLP109',
               'Toshiba TLP109 high-speed transistor-output photocoupler, 5-pin SO6 (MIDI In)', [
                   ('1', 'A', 'passive'), ('3', 'K', 'passive'),
               ], [
                   ('6', 'VCC', 'power_in'), ('5', 'VO', 'open_collector'), ('4', 'GND', 'power_in'),
               ]),
}


def font():
    return '(effects (font (size 1.27 1.27)))'


def symbol(name, fp, descr, left, right):
    rows = max(len(left), len(right))
    h = 2.54 * (rows + 1)
    top = round(h / 2 / 2.54) * 2.54
    w = 10.16
    out = [f'  (symbol "{name}" (in_bom yes) (on_board yes)',
           f'    (property "Reference" "U" (at 0 {top + 1.27:.2f} 0) {font()})',
           f'    (property "Value" "{name}" (at 0 {-top - 1.27:.2f} 0) {font()})',
           f'    (property "Footprint" "{fp}" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))',
           f'    (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))',
           f'    (property "ki_description" "{descr}" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))',
           f'    (symbol "{name}_0_1" (rectangle (start {-w:.2f} {top:.2f}) (end {w:.2f} {-top:.2f}) '
           f'(stroke (width 0.254) (type default)) (fill (type background))))',
           f'    (symbol "{name}_1_1"']
    for side, pins in ((-1, left), (1, right)):
        for i, (num, pname, ptype) in enumerate(pins):
            y = top - 2.54 * (i + 1)
            x = side * (w + 2.54)
            angle = 0 if side < 0 else 180
            out.append(f'      (pin {ptype} line (at {x:.2f} {y:.2f} {angle}) (length 2.54) '
                       f'(name "{pname}" {font()}) (number "{num}" {font()}))')
    out.append('    )\n  )')
    return '\n'.join(out)


def write_symbols():
    body = '\n'.join(symbol(n, *v) for n, v in SYMBOLS.items())
    with open(os.path.join(LIB, 'PATS.kicad_sym'), 'w') as f:
        f.write(f'(kicad_symbol_lib (version 20220914) (generator pats_make_lib)\n{body}\n)\n')


def qfn24_035():
    """ES8389 package (datasheet rev 1.0): 3x3 mm body, 24 leads at 0.35 mm, lead width 0.17 mm,
    exposed pad 1.7 x 1.7 mm (pin 25). Pads: 0.19 x 0.75 mm, centred 1.475 mm from the middle
    (0.35 mm beyond the body edge for the solder fillet), leaving 0.16 mm between pads."""
    name = 'QFN-24-1EP_3x3mm_P0.35mm_EP1.7x1.7mm'
    pw, pl, pc = 0.19, 0.75, 1.475
    lines = [f'(footprint "{name}" (version 20221018) (generator pats_make_lib)', '  (layer "F.Cu")',
             '  (descr "QFN-24 3x3 mm, 0.35 mm pitch, EP 1.7 mm (Everest ES8389 datasheet rev 1.0); tools/make_lib.py")',
             '  (attr smd)',
             '  (fp_text reference "REF**" (at 0 -2.6) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.12))))',
             f'  (fp_text value "{name}" (at 0 2.6) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.12))))']
    c = 2.1
    for a, b in (((-c, -c), (c, -c)), ((c, -c), (c, c)), ((c, c), (-c, c)), ((-c, c), (-c, -c))):
        lines.append(f'  (fp_line (start {a[0]} {a[1]}) (end {b[0]} {b[1]}) (stroke (width 0.05) (type solid)) (layer "F.CrtYd"))')
    for a, b in (((-1.5, -1.5), (1.5, -1.5)), ((1.5, -1.5), (1.5, 1.5)), ((1.5, 1.5), (-1.5, 1.5)), ((-1.5, 1.5), (-1.5, -1.5))):
        lines.append(f'  (fp_line (start {a[0]} {a[1]}) (end {b[0]} {b[1]}) (stroke (width 0.1) (type solid)) (layer "F.Fab"))')
    # Silk: corner marks outside the pads, pin-1 dot.
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        x, y = 1.6 * sx, 1.6 * sy
        lines.append(f'  (fp_line (start {x} {y}) (end {x - 0.3 * sx} {y}) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))')
        lines.append(f'  (fp_line (start {x} {y}) (end {x} {y - 0.3 * sy}) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))')
    lines.append('  (fp_circle (center -2.0 -1.3) (end -1.9 -1.3) (stroke (width 0.2) (type solid)) (fill solid) (layer "F.SilkS"))')
    offs = [(-0.875 + 0.35 * i) for i in range(6)]
    pads = []
    for i, o in enumerate(offs):  # counter-clockwise from the top of the left side
        pads.append((1 + i, -pc, o, pl, pw))        # left, top to bottom
        pads.append((7 + i, o, pc, pw, pl))         # bottom, left to right
        pads.append((13 + i, pc, -o, pl, pw))       # right, bottom to top
        pads.append((19 + i, -o, -pc, pw, pl))      # top, right to left
    for n, x, y, w, h in sorted(pads):
        lines.append(f'  (pad "{n}" smd roundrect (at {x:.4f} {y:.4f}) (size {w} {h}) (layers "F.Cu" "F.Paste" "F.Mask") '
                     f'(roundrect_rratio 0.25))')
    # Exposed pad: copper 1.7 mm, paste reduced to four windows (~60 % coverage).
    lines.append('  (pad "25" smd rect (at 0 0) (size 1.7 1.7) (layers "F.Cu" "F.Mask"))')
    for x in (-0.42, 0.42):
        for y in (-0.42, 0.42):
            lines.append(f'  (pad "" smd rect (at {x} {y}) (size 0.66 0.66) (layers "F.Paste"))')
    lines.append(')')
    with open(os.path.join(LIB, 'PATS.pretty', name + '.kicad_mod'), 'w') as f:
        f.write('\n'.join(lines) + '\n')


def jack_pj320b():
    """PJ-320B 3.5 mm TRS jack, SMD (vendor drawing "PJ-320B", P.C.B layout top view). Plug axis along y,
    opening towards -y; origin at the body centre. Drawing, from the open end of the 3 mm nose: body
    3-14 mm (6 wide, 5 high), pads 1.5 x 3.5 mm at 5.1 (pin 1), 7.1 (pin 2), 12.1 (pin 3) along the
    axis, 3.75 mm either side of it (pin 2 on one side, 1 and 3 on the other), pegs 1.2 mm at 5 and 11.
    Pins (drawing): 1 sleeve, 2 ring, 3 tip."""
    name = 'Jack_3.5mm_PJ-320B_SMD'
    y = lambda d: round(d - 8.5, 3)  # distance from the open end -> y
    lines = [f'(footprint "{name}" (version 20221018) (generator pats_make_lib)', '  (layer "F.Cu")',
             '  (descr "PJ-320B 3.5 mm TRS jack, SMD, opening towards -y (vendor drawing PJ-320B); tools/make_lib.py")',
             '  (attr smd)',
             '  (fp_text reference "REF**" (at 0 7) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.12))))',
             f'  (fp_text value "{name}" (at 0 8.2) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.12))))']

    def rect(x0, y0, x1, y1, layer, w):
        for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
            lines.append(f'  (fp_line (start {a[0]} {a[1]}) (end {b[0]} {b[1]}) (stroke (width {w}) (type solid)) (layer "{layer}"))')
    rect(-3, y(3), 3, y(14), 'F.Fab', 0.1)            # body
    rect(-2.5, y(0), 2.5, y(3), 'F.Fab', 0.1)         # nose
    rect(-5.75, y(0) - 0.25, 5.75, y(14) + 0.25, 'F.CrtYd', 0.05)
    # Silk: body sides between the pads, the nose
    for x in (-3.1, 3.1):
        lines.append(f'  (fp_line (start {x} {y(3)}) (end {x} {y(3.9)}) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))')
    lines.append(f'  (fp_line (start -2.6 {y(0)}) (end 2.6 {y(0)}) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))')
    for x in (-2.6, 2.6):
        lines.append(f'  (fp_line (start {x} {y(0)}) (end {x} {y(3)}) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))')
    lines.append(f'  (fp_line (start -3.1 {y(14)}) (end 3.1 {y(14)}) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))')
    for n, d, x in (('S', 5.1, -3.75), ('R', 7.1, 3.75), ('T', 12.1, -3.75)):
        lines.append(f'  (pad "{n}" smd rect (at {x} {y(d)}) (size 3.5 1.5) (layers "F.Cu" "F.Paste" "F.Mask"))')
    for d in (5, 11):
        lines.append(f'  (pad "" np_thru_hole circle (at 0 {y(d)}) (size 1.2 1.2) (drill 1.2) (layers "*.Cu" "*.Mask"))')
    lines.append(')')
    with open(os.path.join(LIB, 'PATS.pretty', name + '.kicad_mod'), 'w') as f:
        f.write('\n'.join(lines) + '\n')


if __name__ == '__main__':
    write_symbols()
    qfn24_035()
    jack_pj320b()
    print('wrote lib/PATS.kicad_sym and the ES8389 and PJ-320B footprints')
