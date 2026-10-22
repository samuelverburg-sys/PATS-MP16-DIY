"""Write a KiCad 7 schematic: every part grouped by block, every pin tied to its net by a label.

Labels instead of drawn wires keep the generated sheet correct by construction; the
netlist check in build.py compares kicad-cli's netlist of this file with design.py.
"""
import uuid as _uuid
from sexpr import Sym, dump, find, first
import symlib

GRID = 2.54
BLOCK_TITLES = {
    'keys': 'Keys (Kailh hot-swap, MX)', 'leds': 'Per-key RGB (SK6812MINI-E chain)',
    'input': 'Switch inputs (3x 74HC165), encoder', 'modules': 'Dev board, DAC, microSD, OLED, expansion',
    'power': 'Power: USB-C, BQ24074, on/off, 5 V boosts, fuel gauge', 'mech': 'Mechanical',
    'connectors': 'Connectors', 'mcu': 'ESP32-S3 dev board (YD-ESP32-S3) sockets',
    'audio': 'Audio: ES8389 codec, TPA6132A2 headphone amp, jacks', 'storage': 'microSD (4-bit SDMMC)',
}
BLOCK_ORDER = ['power', 'mcu', 'audio', 'storage', 'modules', 'input', 'keys', 'leds', 'connectors', 'mech']


def U():
    return str(_uuid.uuid4())


def snap(v):
    return round(v / GRID) * GRID


def eff(size=1.27, justify=None, hide=False):
    e = [Sym('effects'), [Sym('font'), [Sym('size'), size, size]]]
    if justify:
        e.append([Sym('justify')] + [Sym(j) for j in justify])
    if hide:
        e.append(Sym('hide'))
    return e


def prop(name, value, x, y, hide=False, justify=None):
    return [Sym('property'), name, value, [Sym('at'), x, y, 0], eff(justify=justify, hide=hide)]


def bbox(pins):
    xs = [x for _, _, x, _, _ in pins] or [0]
    ys = [y for _, _, _, y, _ in pins] or [0]
    return min(xs), max(xs), min(ys), max(ys)


def write(parts, path, project, title):
    root = U()
    lib_syms = {}
    body = []
    by_block = {}
    for p in parts:
        by_block.setdefault(p.block or 'misc', []).append(p)

    cursor_y = 30.0
    page_w = 800.0  # A1 landscape is 841 mm
    for block in BLOCK_ORDER + sorted(set(by_block) - set(BLOCK_ORDER)):
        items = by_block.get(block)
        if not items:
            continue
        body.append([Sym('text'), BLOCK_TITLES.get(block, block), [Sym('at'), 20.0, cursor_y, 0],
                     eff(size=3.0, justify=['left', 'bottom']), [Sym('uuid'), U()]])
        cursor_y += 8.0
        x, row_h = 20.0, 0.0
        for p in items:
            sym = symlib.load(p.symbol)
            lib_syms[p.symbol] = sym
            pins = symlib.pins(sym)
            x0, x1, y0, y1 = bbox(pins)
            longest = max([len(n or '') for n in p.pins.values()] + [4])
            margin = snap(longest * 1.1 + 6)
            w = snap(x1 - x0 + 2 * margin + 10)
            h = snap(y1 - y0 + 14)
            if x + w > page_w:
                x, cursor_y, row_h = 20.0, cursor_y + row_h, 0.0
            sx, sy = snap(x + margin - x0), snap(cursor_y + y1 + 6)
            body.append(place_symbol(p, sym, pins, sx, sy, project, root))
            for num, name, px, py, ptype in pins:
                net = p.pins.get(num)
                ax, ay = sx + px, sy - py
                if net is None:
                    body.append([Sym('no_connect'), [Sym('at'), ax, ay], [Sym('uuid'), U()]])
                else:
                    angle = (pin_angle(sym, num) + 180) % 360
                    just = ['right', 'bottom'] if angle in (180, 270) else ['left', 'bottom']
                    body.append([Sym('label'), net, [Sym('at'), ax, ay, angle], [Sym('fields_autoplaced')],
                                 eff(justify=just), [Sym('uuid'), U()]])
            x += w
            row_h = max(row_h, h)
        cursor_y += row_h + 12.0

    doc = [Sym('kicad_sch'), [Sym('version'), Sym('20230121')], [Sym('generator'), Sym('eeschema')],
           [Sym('uuid'), root], [Sym('paper'), 'A1'],
           [Sym('title_block'), [Sym('title'), title], [Sym('company'), 'PATS'],
            [Sym('comment'), 1, 'Generated from design.py by build.py. Edit design.py, not this file.']],
           [Sym('lib_symbols')] + list(lib_syms.values())]
    doc += body
    doc.append([Sym('sheet_instances'), [Sym('path'), '/', [Sym('page'), '1']]])
    open(path, 'w').write(dump(doc) + '\n')


def pin_angle(sym, number):
    for unit in find(sym, 'symbol'):
        for pin in find(unit, 'pin'):
            if first(pin, 'number')[1] == number:
                return int(float(first(pin, 'at')[3])) if len(first(pin, 'at')) > 3 else 0
    return 0


def place_symbol(p, sym, pins, sx, sy, project, root):
    x0, x1, y0, y1 = bbox(pins)
    s = [Sym('symbol'), [Sym('lib_id'), p.symbol], [Sym('at'), sx, sy, 0], [Sym('unit'), 1],
         [Sym('in_bom'), Sym('yes')], [Sym('on_board'), Sym('yes')], [Sym('dnp'), Sym('yes' if p.dnp else 'no')],
         [Sym('uuid'), U()],
         prop('Reference', p.ref, sx, sy - y1 - 3.0),
         prop('Value', p.value, sx, sy - y0 + 3.0),
         prop('Footprint', p.footprint, sx, sy, hide=True),
         prop('Datasheet', '', sx, sy, hide=True),
         prop('MPN', p.mpn, sx, sy, hide=True)]
    if p.note:
        s.append(prop('Note', p.note, sx, sy, hide=True))
    for num in sorted({n for n, *_ in pins}):
        s.append([Sym('pin'), num, [Sym('uuid'), U()]])
    s.append([Sym('instances'), [Sym('project'), project,
                                 [Sym('path'), '/' + root, [Sym('reference'), p.ref], [Sym('unit'), 1]]]])
    return s
