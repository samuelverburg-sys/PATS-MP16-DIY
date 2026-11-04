#!/usr/bin/env python3
"""Generate and check a PATS board from <board>/design.py.

  python3 build.py ui check     # netlist sanity checks only (fast)
  python3 build.py ui sch       # write ui/ui.kicad_sch (+ KiCad netlist round trip)
  python3 build.py ui pcb       # write ui/ui.kicad_pcb (placed, unrouted) + placement checks
  python3 build.py ui route     # autoroute with Freerouting, fill zones
  python3 build.py ui drc       # design rule check
  python3 build.py ui fab       # gerbers, drill, BOM and CPL for JLCPCB
  python3 build.py ui all       # everything in order

Needs KiCad 7+ (kicad-cli and the pcbnew Python module) and, for routing, Java 25 and
Freerouting 2.5 (JAVA=..., FREEROUTING_JAR=...).
"""
import collections
import importlib
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, ROOT)

import symlib  # noqa: E402

symlib.SYM_DIRS.append(os.path.join(ROOT, 'lib'))  # PATS.kicad_sym (tools/make_lib.py)

BOARD_NAME = sys.argv[1] if len(sys.argv) > 1 else 'ui'
HERE = os.path.join(ROOT, BOARD_NAME)
sys.path.insert(0, HERE)
design = importlib.import_module('design')

FP_DIRS = {'PATS': os.path.join(ROOT, 'lib', 'PATS.pretty')}
KICAD_FP = os.environ.get('KICAD_FOOTPRINT_DIR', '/usr/share/kicad/footprints')
NAME = design.NAME
PCB = os.path.join(HERE, NAME + '.kicad_pcb')
BUILD = os.path.join(HERE, 'build')


def fp_path(lib_id):
    lib, name = lib_id.split(':')
    return FP_DIRS.get(lib, os.path.join(KICAD_FP, lib + '.pretty')), name


def netlist():
    """net -> [(ref, pin)] for all connected pins (incl. footprint-only pads)."""
    nets = collections.defaultdict(list)
    for p in design.parts:
        for pin, net in list(p.pins.items()) + list(p.extra_pads.items()):
            if net:
                nets[net].append((p.ref, pin))
    return nets


def check():
    import pcbnew
    errors, warnings = [], []
    refs = collections.Counter(p.ref for p in design.parts)
    errors += [f'duplicate reference {r}' for r, n in refs.items() if n > 1]

    for p in design.parts:
        sym = symlib.load(p.symbol)
        sym_pins = {n for n, *_ in symlib.pins(sym)}
        given = set(p.pins)
        if given - sym_pins:
            errors.append(f'{p.ref}: pins not in symbol {p.symbol}: {sorted(given - sym_pins)}')
        if sym_pins - given:
            errors.append(f'{p.ref}: symbol pins not assigned (use None for no-connect): {sorted(sym_pins - given)}')
        d, name = fp_path(p.footprint)
        fp = pcbnew.FootprintLoad(d, name)
        if fp is None:
            errors.append(f'{p.ref}: footprint {p.footprint} not found')
            continue
        pads = {pad.GetNumber() for pad in fp.Pads() if pad.GetNumber()}
        missing = (sym_pins | set(p.extra_pads)) - pads
        if missing:
            errors.append(f'{p.ref}: symbol pins without pads in {p.footprint}: {sorted(missing)}')
        unused = pads - sym_pins - set(p.extra_pads)
        if unused:
            warnings.append(f'{p.ref}: pads with no net: {sorted(unused)}')

    for net, conns in sorted(netlist().items()):
        if len(conns) < 2:
            errors.append(f'net {net} has only one connection: {conns}')

    # Every switch input must be pulled up and reach a shift register.
    nets = netlist()
    for net in nets:
        if net.startswith('KEY_'):
            refs_on = {r for r, _ in nets[net]}
            if not any(r.startswith('RN') for r in refs_on) or not any(r in ('U1', 'U2', 'U3') for r in refs_on):
                errors.append(f'{net}: needs a pull-up pack and a 74HC165 input')

    for w in warnings:
        print('warning:', w)
    for e in errors:
        print('ERROR:', e)
    print(f'check: {len(design.parts)} parts, {len(nets)} nets, {len(errors)} errors, {len(warnings)} warnings')
    return not errors


def sch():
    import sch as schw
    import subprocess
    import xml.etree.ElementTree as ET
    path = os.path.join(HERE, NAME + '.kicad_sch')
    schw.write(design.parts, path, NAME, design.TITLE)
    # Round trip: let KiCad parse it and compare its netlist with design.py.
    xml = os.path.join(BUILD, NAME + '.net.xml')
    os.makedirs(os.path.dirname(xml), exist_ok=True)
    r = subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', xml, path],
                       capture_output=True, text=True)
    if r.returncode:
        print(r.stdout, r.stderr)
        return False
    got = {}
    for net in ET.parse(xml).getroot().iter('net'):
        name = net.get('name').lstrip('/')
        nodes = {(n.get('ref'), n.get('pin')) for n in net.iter('node')}
        if name.startswith('unconnected-') or name.startswith('Net-('):
            continue
        got[name] = nodes
    fp_only = {(p.ref, pad) for p in design.parts for pad in p.extra_pads}  # pads with no symbol pin
    want = {n: {c for c in conns if c not in fp_only} for n, conns in netlist().items()}
    want = {n: c for n, c in want.items() if c}
    bad = [n for n in set(want) | set(got) if want.get(n) != got.get(n)]
    for n in sorted(bad)[:20]:
        print('netlist mismatch', n, 'design:', sorted(want.get(n, [])), 'schematic:', sorted(got.get(n, [])))
    print(f'sch: wrote {os.path.relpath(path)}; KiCad netlist {"matches" if not bad else "DIFFERS from"} design.py '
          f'({len(got)} nets)')
    return not bad


def pcb():
    import pcb as pcbw
    import project
    pcbw.build(design, fp_path, PCB)
    from stable_ids import stabilize_board
    stabilize_board(PCB)  # same design -> same board, item order included (the router depends on it)
    # after SaveBoard, which writes a default project file
    project_rewrite()
    lib_table = os.path.join(HERE, 'fp-lib-table')
    shutil.copy(os.path.join(ROOT, 'fp-lib-table.template'), lib_table)
    print(f'pcb: wrote {os.path.relpath(PCB)} ({len(design.parts)} footprints, unrouted)')
    return courtyards() and bodies() and facing()


def facing():
    """Pre-routing checks. Facing: a two-pad part (R, C, L, D) next to a chip pin should turn the pad on
    that pin's net towards the pin. Otherwise its other pad (often ground) sits in the way and the
    track has to go around its own part: the main cause of unroutable connections on the audio board."""
    import math
    import pcbnew
    board = pcbnew.LoadBoard(PCB)
    chip_pads = [(fp.GetReference(), p) for fp in board.GetFootprints() if fp.GetReference()[0] in 'UX'
                 for p in fp.Pads() if p.GetNetname()]
    warn = []
    for fp in board.GetFootprints():
        pads = [p for p in fp.Pads() if p.GetNumber()]
        if fp.GetReference()[0] not in 'RCLD' or len(pads) != 2:
            continue
        for p, other in ((pads[0], pads[1]), (pads[1], pads[0])):
            net = p.GetNetname()
            if not net or net == 'GND' or net == other.GetNetname():
                continue
            d = lambda a, b: math.hypot(a.GetPosition().x - b.GetPosition().x, a.GetPosition().y - b.GetPosition().y)
            near = [(d(p, q), ref, q) for ref, q in chip_pads if q.GetNetname() == net and d(p, q) < pcbnew.FromMM(8)]
            if len(near) != 1:
                continue
            _, ref, q = near[0]
            if any(r.GetNetname() == other.GetNetname() and d(other, r) < pcbnew.FromMM(8) for _, r in chip_pads):
                continue  # in series between two chips: one end always faces away
            if d(other, q) + pcbnew.FromMM(0.3) < d(p, q):
                warn.append(f'{fp.GetReference()}: pad {p.GetNumber()} ({net}) faces away from {ref}.{q.GetNumber()}; '
                            f'rotate it 180 deg')
    # Order: parts serving neighbouring pins on one side of a chip should sit in the same order as
    # those pins along that side; when two are swapped their tracks have to cross.
    order = []
    for fp in board.GetFootprints():
        if fp.GetReference()[0] != 'U':
            continue
        c = fp.GetPosition()
        served = []  # (pin, side axis, pin coordinate along the side, part coordinate along the side)
        for q in fp.Pads():
            net = q.GetNetname()
            if not net or net == 'GND' or not q.GetNumber():
                continue
            parts_on = [(p, f) for f in board.GetFootprints() if f.GetReference()[0] in 'RC'
                        for p in f.Pads() if p.GetNetname() == net and
                        math.hypot(p.GetPosition().x - q.GetPosition().x, p.GetPosition().y - q.GetPosition().y)
                        < pcbnew.FromMM(8)]
            if len(parts_on) != 1:
                continue
            p, f = parts_on[0]
            dx, dy = q.GetPosition().x - c.x, q.GetPosition().y - c.y
            side = ('x', 1 if dx > 0 else -1) if abs(dx) > abs(dy) else ('y', 1 if dy > 0 else -1)
            along = (lambda v: v.y) if side[0] == 'x' else (lambda v: v.x)
            served.append((q.GetNumber(), side, along(q.GetPosition()), along(f.GetPosition()), f.GetReference()))
        for i, a in enumerate(served):
            for b in served[i + 1:]:
                if a[1] == b[1] and a[4] != b[4] and (a[2] - b[2]) * (a[3] - b[3]) < 0:
                    order.append(f'{fp.GetReference()}: {a[4]} (pin {a[0]}) and {b[4]} (pin {b[0]}) are in the '
                                 f'opposite order to their pins; swap them')
    # Crossing to connectors: two neighbouring pins on one side of a chip whose nets end on a connector,
    # test pad or encoder in the opposite order along that side must cross (MP-16: AIN1-4 to the
    # expansion header, ENC_A/B to the encoder, SWCLK/SWDIO to their test pads each left a net open).
    ends = {}
    for f in board.GetFootprints():
        if f.GetReference().startswith(('J', 'TP', 'ENC')):
            for p in f.Pads():
                if p.GetNetname() and p.GetNetname() != 'GND' and not p.GetNetname().startswith('+'):
                    # a pad's position along the part's long axis, on the line through its centre: tracks
                    # enter a two-row header between its rows, so which row a pin is in does not order them
                    bb, pos = f.GetBoundingBox(False, False), p.GetPosition()
                    at = (pos.x, pos.y) if not f.GetReference().startswith('J') else \
                        (pos.x, bb.Centre().y) if bb.GetWidth() >= bb.GetHeight() else (bb.Centre().x, pos.y)
                    ends.setdefault(p.GetNetname(), []).append((p, f.GetReference(), at))
    for fp in board.GetFootprints():
        if fp.GetReference()[0] != 'U':
            continue
        c = fp.GetPosition()
        served = []
        for q in fp.Pads():
            e = ends.get(q.GetNetname(), [])
            if len(e) != 1 or math.hypot(e[0][0].GetPosition().x - q.GetPosition().x,
                                         e[0][0].GetPosition().y - q.GetPosition().y) > pcbnew.FromMM(30):
                continue
            dx, dy = q.GetPosition().x - c.x, q.GetPosition().y - c.y
            side = ('x', 1 if dx > 0 else -1) if abs(dx) > abs(dy) else ('y', 1 if dy > 0 else -1)
            # how far along the side, and where the far end lies across the side's direction of travel
            along = (lambda v: v.y) if side[0] == 'x' else (lambda v: v.x)
            served.append((q.GetNumber(), q.GetNetname(), side, along(q.GetPosition()), e[0]))
        def cross(p1, p2, p3, p4):  # do segments p1-p2 and p3-p4 cross (proper intersection)
            d = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
            return d(p3, p4, p1) * d(p3, p4, p2) < 0 and d(p1, p2, p3) * d(p1, p2, p4) < 0
        xy = lambda p: (p.GetPosition().x, p.GetPosition().y)
        for i, a in enumerate(served):
            for b in served[i + 1:]:
                if a[2] != b[2] or abs(a[3] - b[3]) > pcbnew.FromMM(1.3):
                    continue  # neighbouring pins on one side only
                pa = next(q for q in fp.Pads() if q.GetNumber() == a[0])
                pb = next(q for q in fp.Pads() if q.GetNumber() == b[0])
                if cross(xy(pa), a[4][2], xy(pb), b[4][2]):
                    order.append(f'{fp.GetReference()}: pins {a[0]} ({a[1]}) and {b[0]} ({b[1]}) reach '
                                 f'{a[4][1]}/{b[4][1]} '
                                 f'crossed; swap the pins or the ends')
    # Side: a part whose only chip pin on that net is on the chip's far side from it has to route around the
    # chip (MP-16 run 9: R21 left of U13, ILIM on its right; left open, and neither check above saw it).
    side_warn = []
    fps = {f.GetReference(): f for f in board.GetFootprints()}
    for fp in board.GetFootprints():
        pads = [p for p in fp.Pads() if p.GetNumber()]
        if fp.GetReference()[0] not in 'RCLD' or len(pads) != 2:
            continue
        for p in pads:
            net = p.GetNetname()
            if not net or net in ('GND',) or net.startswith('+') or net in getattr(design, 'POWER_NETS', set()) or \
                    net in getattr(design, 'PLANES', {}).values():
                continue
            pins = [(ref, q) for ref, q in chip_pads if q.GetNetname() == net]
            if len(pins) != 1:
                continue
            ref, q = pins[0]
            c = fps[ref].GetPosition()
            to_pin = (q.GetPosition().x - c.x, q.GetPosition().y - c.y)
            to_part = (p.GetPosition().x - c.x, p.GetPosition().y - c.y)
            dist = math.hypot(*to_part) * math.hypot(*to_pin)
            if (math.hypot(*to_part) < pcbnew.FromMM(12) and dist and
                    (to_pin[0] * to_part[0] + to_pin[1] * to_part[1]) / dist < -0.5):  # more than 120 deg apart
                side_warn.append(f'{fp.GetReference()}: on the far side of {ref} from pin {q.GetNumber()} ({net}); '
                                 f'move it to that pin\'s side')
    for w in warn + order + side_warn:
        print('facing:', w)
    print(f'facing: {len(warn)} parts turned away from the pin they serve, {len(order)} pairs in crossing order, '
          f'{len(side_warn)} on the far side of their chip')
    return True


def bodies():
    """Part drawings (fab layer: body plus what sticks out of it in use, e.g. an inserted microSD card) may
    not overlap another part on the same side: the courtyard check misses a card's or plug's path."""
    import pcbnew
    import silk
    board = pcbnew.LoadBoard(PCB)
    fps = [(f, silk._body(f)) for f in board.GetFootprints()]
    fps = [(f, bb) for f, bb in fps if bb]
    m = pcbnew.FromMM(0.05)
    hits = [f'{a.GetReference()}/{c.GetReference()}' for i, (a, A) in enumerate(fps) for c, C in fps[i + 1:]
            if a.GetLayer() == c.GetLayer() and A.GetLeft() + m < C.GetRight() and C.GetLeft() + m < A.GetRight()
            and A.GetTop() + m < C.GetBottom() and C.GetTop() + m < A.GetBottom()]
    print(f'bodies: {len(hits)} part drawings overlapping' + (f': {", ".join(hits)}' if hits else ''))
    return not hits


def courtyards():
    """Report footprints whose courtyards overlap (placement problems), per side."""
    import pcbnew
    board = pcbnew.LoadBoard(PCB)
    fps = list(board.GetFootprints())
    clashes = []
    for i, a in enumerate(fps):
        for b in fps[i + 1:]:
            ra, rb = sorted((a.GetReference(), b.GetReference()))
            # An MX switch outline always covers its own LED and LED capacitor: expected.
            if ra[0] in 'CD' and rb.startswith('SW') and ra[1:] == rb[2:]:
                continue
            # The MP-16 board has its mounting holes inside the outer switch outlines too.
            if ra.startswith('H') and rb.startswith('SW'):
                continue
            for layer in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
                ca, cb = a.GetCourtyard(layer), b.GetCourtyard(layer)
                if ca.OutlineCount() and cb.OutlineCount() and ca.Collide(cb) and \
                        (ra, rb) not in {tuple(sorted(p)) for p in getattr(design, 'COURTYARD_OK', [])}:
                    clashes.append((a.GetReference(), b.GetReference(), board.GetLayerName(layer)))
            # A through-hole part occupies both sides: its pins are soldered on the far side, by hand on the
            # MP-16 (headers), so parts there need room (MP-16 run 11: J6's pins 0.3 mm from R2, C19, C20,
            # R3 on the bottom passed the same-side check). Key switches carry their own sockets and LEDs.
            if not (ra.startswith('SW') and rb.startswith('SW')):
                for th, other in ((a, b), (b, a)):
                    # mounting holes count too (MP-16: a connector on H4 passed); holes inside switch
                    # outlines are skipped above
                    is_hole = th.GetReference().startswith('H') and th.GetReference()[1:].isdigit()
                    if not (th.HasThroughHolePads() or is_hole) or th.GetReference().startswith('SW') or \
                            other.GetLayer() == th.GetLayer():
                        continue
                    ct = th.GetCourtyard(pcbnew.F_CrtYd if th.GetLayer() == pcbnew.F_Cu else pcbnew.B_CrtYd)
                    co = other.GetCourtyard(pcbnew.B_CrtYd if th.GetLayer() == pcbnew.F_Cu else pcbnew.F_CrtYd)
                    pair = tuple(sorted((th.GetReference(), other.GetReference())))
                    if ct.OutlineCount() and co.OutlineCount() and ct.Collide(co) and pair not in THROUGH_OK() and \
                            (pair[0], pair[1], 'through-hole over the other side') not in clashes:
                        clashes.append((pair[0], pair[1], 'through-hole over the other side'))
    for c in clashes:
        print('courtyard overlap:', *c)
    print(f'placement: {len(clashes)} courtyard overlaps')
    return True


def THROUGH_OK():
    """(through-hole part, part on the other side) pairs that may overlap: design.THROUGH_HOLE_OVERLAP_OK."""
    return {tuple(sorted(p)) for p in getattr(design, 'THROUGH_HOLE_OVERLAP_OK', [])}


JAVA = os.environ.get('JAVA', 'java')
FREEROUTING = os.environ.get('FREEROUTING_JAR', 'freerouting.jar')


def net_width(net):
    """Track width of a net's class (mm)."""
    c = net_class(net)
    return {'Power': 0.6, 'Default': 0.25}.get(c) or getattr(design, 'NETCLASSES', {})[c][0]


def net_class(net):
    """Net class of a net as design.py assigns it (Default when not listed)."""
    for c, (_, nets) in getattr(design, 'NETCLASSES', {}).items():
        if net in nets:
            return c
    return 'Power' if net in design.POWER_NETS else 'Default'


def NO_RIPUP():
    """Nets the finishing router never rips up and reroutes: power (stays wide) and USB data (a pair)."""
    return set(design.POWER_NETS) | set(getattr(design, 'NETCLASSES', {}).get('Usb', (0, []))[1])


def promote(text, nets, prefix='P_'):
    """Move `nets` out of their DSN net classes into classes of their own ('P_<class>', same width
    and clearance), so a Freerouting run can route just them (or, with another prefix, skip them)."""
    import re
    pat = re.compile(r'\(class (\S+)([^()]*)(\(circuit\s*\(use_via [^)]*\)\s*\)\s*\(rule\s*(?:\([^()]*\)\s*)*\))\s*\)')
    extra = []

    def sub(m):
        name, members, body = m.group(1), m.group(2).split(), m.group(3)
        moved = [n for n in members if n.strip('"') in nets]
        if not moved:
            return m.group(0)
        extra.append(f'(class {prefix}{name} {" ".join(moved)} {body})')
        kept = [n for n in members if n not in moved]
        return f'(class {name} {" ".join(kept)} {body})'
    text = pat.sub(sub, text)
    i = text.index('(class ')
    return text[:i] + ' '.join(extra) + '\n    ' + text[i:]


MARGIN_OVERRIDE = None  # clearance margin (mm) for the current routing attempt (design.ROUTE_MARGINS)


def snapshot(board):
    """The board's tracks and vias as plain values (restore() puts them back)."""
    out = []
    for t in board.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            p = t.GetPosition()
            out.append(('via', p.x, p.y, t.GetWidth(), t.GetDrillValue(), t.GetNetCode(), t.IsLocked()))
        else:
            s, e = t.GetStart(), t.GetEnd()
            out.append(('track', s.x, s.y, e.x, e.y, t.GetWidth(), t.GetLayer(), t.GetNetCode(), t.IsLocked()))
    return out


def restore(board, snap):
    import pcbnew
    for t in list(board.GetTracks()):
        board.Remove(t)
    for item in snap:
        if item[0] == 'via':
            _, x, y, w, drill, net, locked = item
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pcbnew.VECTOR2I(x, y))
            v.SetWidth(w)
            v.SetDrill(drill)
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        else:
            _, x0, y0, x1, y1, w, layer, net, locked = item
            v = pcbnew.PCB_TRACK(board)
            v.SetStart(pcbnew.VECTOR2I(x0, y0))
            v.SetEnd(pcbnew.VECTOR2I(x1, y1))
            v.SetWidth(w)
            v.SetLayer(layer)
        v.SetNetCode(net)
        v.SetLocked(locked)
        board.Add(v)


def open_nets_report(board, nets=None, skip=None):
    """What KiCad itself sees as unconnected (Freerouting's log lists open nets only some of the time):
    {net: [pieces]}, each piece a list of (item, x, y) in the design frame (mm), from KiCad's DRC
    (under a second on this board). `nets` limits the report; ground is skipped (pours carry it)."""
    import re
    import pcbnew
    if skip is None:  # ground and the plane nets: their pours and planes are only filled at the end
        skip = {'GND'} | set(getattr(design, 'PLANES', {}).values())
    rpt = os.path.join(BUILD, 'open.rpt')
    pcbnew.WriteDRCReport(board, rpt, pcbnew.EDA_UNITS_MILLIMETRES, False)
    out = collections.defaultdict(list)
    for item in re.split(r'\n(?=\[)', open(rpt).read()):
        if not item.startswith('[unconnected_items]'):
            continue
        ends = [(re.sub(r' on [BF]\.Cu.*| of ', lambda m: ' of ' if m.group(0) == ' of ' else '', d.strip())[:40],
                 round(float(x) - 40.0, 2), round(float(y) - 30.0, 2))
                for x, y, d in re.findall(r'@\(([-\d.]+) mm, ([-\d.]+) mm\): (.*)', item)]
        names = set(re.findall(r'\[([^\]]+)\] (?:of|on)', item))
        if len(names) != 1:
            continue
        n = names.pop()
        if n in skip or (nets is not None and n not in nets):
            continue
        out[n].append(ends)
    return dict(out)


def print_open(report, prefix='route'):
    for n, gaps in sorted(report.items()):
        print(f'{prefix}: OPEN {n}: ' + '; '.join(' <-> '.join(f'{d} ({x:.1f},{y:.1f})' for d, x, y in g)
                                                  for g in gaps[:3]) + (' ...' if len(gaps) > 3 else ''))


def freerouting(board, ignore, tag, edit=None, margin=None, run=True):
    """Export `board` (pours already removed), run Freerouting skipping the `ignore` classes,
    return the session path, or None. `edit` may rewrite the DSN text first. run=False: export only and
    return the job for fr_run() (exports must be sequential, pcbnew is not thread-safe; runs need not)."""
    import re
    import subprocess
    import pcbnew
    dsn = os.path.join(BUILD, f'{NAME}{tag}.dsn')
    ses = os.path.join(BUILD, f'{NAME}{tag}.ses')
    if os.path.exists(ses):
        os.remove(ses)
    if not pcbnew.ExportSpecctraDSN(board, dsn):
        print('route: DSN export failed')
        return None
    # Route with a little more clearance than DRC requires: Freerouting's polygon pad shapes and
    # rounding otherwise leave gaps a few um under the rule.
    margin = margin if margin is not None else MARGIN_OVERRIDE if MARGIN_OVERRIDE is not None else \
        float(os.environ.get('ROUTE_CLEARANCE_MARGIN', getattr(design, 'ROUTE_CLEARANCE_MARGIN', 0.02)))
    margin *= 1000
    text = open(dsn).read()
    text = re.sub(r'\(clearance ([0-9.]+)\)', lambda m: f'(clearance {float(m.group(1)) + margin:g})', text)
    # The router keeps only the track clearance from the board outline, so a track or via can land closer
    # to the edge than the board's edge clearance (0.3 mm). A rectangular outline is pulled in by the
    # difference (design.ROUTE_EDGE_INSET = False turns it off).
    edge = board.GetDesignSettings().m_CopperEdgeClearance / 1e3 if getattr(design, 'ROUTE_EDGE_INSET', True) else 0
    m = re.search(r'\(boundary\s*\(path pcb 0\s+([-0-9.\s]+)\)', text)
    pts = [float(v) for v in m.group(1).split()] if m else []
    xs, ys = sorted(set(pts[0::2])), sorted(set(pts[1::2]))
    clear = float(re.search(r'\(clearance ([0-9.]+)\)', text).group(1))
    if len(xs) == 2 and len(ys) == 2 and edge > clear:
        # Freerouting lets copper come within about (clearance - 0.07 mm) of the boundary, not `clearance`:
        # with the inset edge - clear tracks ended 0.235 mm from the edge (rule 0.3). The DSN is in um, so
        # the inset is the whole edge clearance + 20 um (an earlier '+ 0.08' meant 0.08 um and did nothing).
        d = edge + 20
        box = [xs[0] + d, ys[0] + d, xs[1] - d, ys[1] - d]
        path = f'{box[2]:g} {box[1]:g}  {box[0]:g} {box[1]:g}  {box[0]:g} {box[3]:g}  {box[2]:g} {box[3]:g}  {box[2]:g} {box[1]:g}'
        text = text[:m.start(1)] + path + text[m.end(1):]
    # Cut-outs inside the board (the MP-16's 17 LED windows) are exported as keep-outs on every signal layer
    # with no edge clearance: inner-layer tracks ran 0.16-0.30 mm from their edges (MP-16 run 16B, rule
    # 0.3; the outer layers are kept off by the LED pads). Each is grown outward by the same inset as the
    # outline, per axis about its centre (the windows are rounded rectangles).
    if edge > clear:
        d = edge + 20

        def grow(km):
            vals = [float(v) for v in km.group(3).split()]
            xs_, ys_ = vals[0::2], vals[1::2]
            cx, cy = (min(xs_) + max(xs_)) / 2, (min(ys_) + max(ys_)) / 2
            out = []
            for x, y in zip(xs_, ys_):
                out += [x + d * ((x > cx) - (x < cx)), y + d * ((y > cy) - (y < cy))]
            return f'(keepout "" (polygon signal {km.group(2)}  ' + '  '.join(
                f'{out[i]:g} {out[i + 1]:g}' for i in range(0, len(out), 2)) + ')'
        text = re.sub(r'\(keepout "" \(polygon (signal) ([0-9.]+)\s+([-0-9.\s]+)\)', grow, text)
    if edit:
        text = edit(text)
    open(dsn, 'w').write(text)
    # No post-route optimisation: '-mt 0' alone does not turn it off (it still ran with 3 threads on a
    # fully routed stage). Multi-threaded, it made results differ from run to run, and on the UI board
    # it ran past the time limit, losing a complete routing.
    cmd = [JAVA, '-jar', FREEROUTING, '-de', dsn, '-do', ses, '-mp', os.environ.get('ROUTE_PASSES', str(getattr(design, 'ROUTE_PASSES', 30))),
           '-mt', '0', '--router.optimizer.enabled=false',
           '--gui.enabled=false', '--usage_and_diagnostic_data.disable_analytics=true']
    if ignore:
        # Freerouting's own fan-out stage would stub every SMD pin of every net, ignored classes
        # included; those stubs would then be locked into the stage.
        cmd += ['--router.autorouter.ignore_net_classes=' + ','.join(ignore), '--router.fanout.enabled=false']
    log = os.path.join(BUILD, f'freerouting{tag}.log')
    job = (cmd, ses, log)
    return fr_run(job) if run else job


def fr_run(job):
    """Run one prepared Freerouting job: (session path, log text), or None."""
    import subprocess
    cmd, ses, log = job
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=int(os.environ.get('ROUTE_TIMEOUT', getattr(design, 'ROUTE_TIMEOUT', 900))))
        out = r.stdout + r.stderr
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b'').decode() if isinstance(e.stdout, bytes) else (e.stdout or '')
        print('route: Freerouting timed out')
    open(log, 'w').write(out)
    if not os.path.exists(ses):
        print(f'route: Freerouting failed, see {os.path.relpath(log)}')
        return None
    return ses, out


def route():
    """Autoroute (see _route) and append the run to the build log (tools/buildlog.py)."""
    import time
    import buildlog
    rec = {'type': 'route', 'board': NAME, 'time': buildlog.now(), 'commit': buildlog.git_rev(),
           'note': os.environ.get('ROUTE_NOTE', ''),  # what this run tests: ROUTE_NOTE="..." build.py ...
           'design': buildlog.sha(os.path.join(HERE, 'design.py')), 'stages': [],
           'settings': buildlog.settings(
               design, float(os.environ.get('ROUTE_CLEARANCE_MARGIN', getattr(design, 'ROUTE_CLEARANCE_MARGIN', 0.02))),
               int(os.environ.get('ROUTE_PASSES', str(getattr(design, 'ROUTE_PASSES', 30)))), int(os.environ.get('ROUTE_TIMEOUT', getattr(design, 'ROUTE_TIMEOUT', 900))), FREEROUTING)}
    if not rec['note'] and not QUICK and not os.environ.get('ROUTE_CONTINUE'):
        print('route: set ROUTE_NOTE="what this run tests" (and run build.py <board> preflight first)')
        return False
    try:
        from congestion import analyse
        rec['congestion'] = analyse(PCB)['score']  # the placement's score before routing (tools/congestion.py)
    except Exception as e:  # never stop a route over the estimate
        print(f'route: congestion estimate failed: {e}')
    t0, ok = time.time(), False
    import signal

    def stopped(sig, frame):  # a run stopped by hand (kill) still gets its record, marked stopped
        rec['stopped'] = True
        raise SystemExit(1)
    signal.signal(signal.SIGTERM, stopped)
    try:
        ok = _route(rec)
    finally:
        rec['ok'] = bool(ok)
        rec['s'] = round(time.time() - t0)
        if ok:
            rec['pcb'] = buildlog.sha(PCB)
        buildlog.append(rec)
        parts = [('prep', rec.get('prep_s'))] + [(f'stage {st["name"]}', st['s']) for st in rec['stages']] + \
            sorted((rec.get('phases') or {}).items(), key=lambda kv: list((rec.get('phases') or {})).index(kv[0]))
        print('route: time ' + ', '.join(f'{k} {v} s' for k, v in parts if v is not None)
              + f'; total {rec["s"] / 60:.1f} min; logged to {os.path.relpath(buildlog.LOG)}')
    return ok


def _route(rec):
    """Autoroute. With design.ROUTE_STAGES the nets are routed in priority order, one group of net
    classes at a time; each stage's tracks are locked (exported as fixed wiring, never ripped up)
    before the next, so the most constrained nets get the free board and later stages cannot undo
    them. Ground is fanned out to the bottom plane first (design.GND_FANOUT). Anything still open
    at the end goes to tools/finish.py. Without stages: one Freerouting run over all nets."""
    global MARGIN_OVERRIDE
    import time
    t_route = time.time()
    import re
    import pcbnew
    from ses_import import import_ses
    os.makedirs(BUILD, exist_ok=True)
    board = pcbnew.LoadBoard(PCB)
    min_w = int(getattr(design, 'MIN_TRACK', 0.15) * 1e6)
    if os.environ.get('ROUTE_REUSE_SES'):
        ses = os.path.join(BUILD, NAME + '.ses')
        print('route: re-using', os.path.relpath(ses), import_ses(board, ses, min_w))
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        pcbnew.SaveBoard(PCB, board)
        project_rewrite()
        return True
    tracks = list(board.GetTracks())
    # Export without the GND pours: otherwise GND is treated as a plane and never routed, and a
    # fragmented pour leaves pads unconnected. Pours are refilled at the end.
    # Pour-only keep-outs (POUR_KEEPOUT) go too: the DSN export would turn them into full keep-outs.
    # Inner-layer planes (design.PLANES) stay: exported as Specctra planes, they keep Freerouting off
    # those layers (a power-type layer without its plane was routed on) and connect their nets' vias.
    inner = {board.GetLayerID(n) for n in getattr(design, 'PLANES', {})}
    pours = [z for z in board.Zones() if (not z.GetIsRuleArea() and not (set(z.GetLayerSet().Seq()) & inner)) or
             (z.GetDoNotAllowCopperPour() and not z.GetDoNotAllowTracks())]
    for z in pours:
        board.Remove(z)
    fan = getattr(design, 'GND_FANOUT', False)
    stubs = []
    # ROUTE_CONTINUE=1: keep the board's current tracks (a previous run) and route what is left.
    if not os.environ.get('ROUTE_CONTINUE'):
        for t in tracks:
            board.Remove(t)
        if fan:  # ground via beside every top-side ground pad; the Ground class is then not routed
            from fanout import fanout
            for fnet in ['GND'] + [n for n in getattr(design, 'PLANES', {}).values() if n != 'GND']:
                items, failed = [], []
                for fside in getattr(design, 'GND_FANOUT_SIDE', 'F'):  # 'F', 'B' or 'BF': both sides
                    it, fl = fanout(board, net=fnet, at=getattr(design, 'GND_FANOUT_VIA', {}), side=fside)
                    items += it
                    failed += fl
                for t in items:
                    t.SetLocked(True)
                print(f'route: {fnet} fan-out {len(items)} items' + (f'; no room at {", ".join(failed)}' if failed else ''),
                      flush=True)
        if getattr(design, 'PREROUTE_MM', 0):  # short hops first, deterministic and locked (tools/finish.py)
            from finish import prejoin_short
            t_pj = time.time()
            # the clearance of the widest Freerouting margin (+0.04), plus 0.01: locked tracks closer than the
            # router's clearance are 'unfixable violations' to it (run 14: 58-139, ground vias vs pre-routed tracks)
            pj_joined, pj_stuck = prejoin_short(board, getattr(design, 'CLEARANCE', 0.2) + 0.05,
                          {n: net_width(n) for n in {x for p in design.parts for x in p.pins.values() if x}},
                          design.PREROUTE_MM, skip=set(getattr(design, 'PLANES', {}).values()),
                          first=getattr(design, 'PREROUTE_FIRST', ()), first_mm=getattr(design, 'PREROUTE_FIRST_MM', 12.0))
            rec['prejoin'] = {'joined': pj_joined, 'stuck': pj_stuck, 's': round(time.time() - t_pj)}
        if getattr(design, 'ESCAPE', None):  # locked escape stubs from the fine-pitch parts' signal pins
            from fanout import escapes
            stubs = escapes(board, design.ESCAPE)
            for t in stubs:
                t.SetLocked(True)
            print(f'route: escape stubs on {", ".join(design.ESCAPE)}: {len(stubs)}')
    stub_keys = {(t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y) for t in stubs}
    stages = getattr(design, 'ROUTE_STAGES', None) or [('all', None)]
    rec['prep_s'] = round(time.time() - t_route)  # export, fan-out, escape stubs
    nets = {n for p in design.parts for n in list(p.pins.values()) + list(p.extra_pads.values()) if n}
    dsn_class = lambda n: 'kicad_default' if net_class(n) == 'Default' else net_class(n)
    claimed = set()  # nets an earlier named-net stage routed: later stages neither count nor rip them up
    for i, (name, classes, *extra) in enumerate(stages):
        t_stage = time.time()
        # A stage is (name, [classes]), (name, [], [nets]): just those nets, moved into classes of their
        # own in the DSN, so the other stages' DSN files stay exactly as they were, or
        # (name, [classes], None, [nets]): the classes without those nets (left for a later stage).
        only = set(extra[0]) if extra and extra[0] else set()
        skip = set(extra[1]) if len(extra) > 1 else set()
        dsn_classes = {'kicad_default' if c == 'Default' else c for c in
                       {net_class(n) for n in nets} | {'Default'}}
        want = {'kicad_default' if c == 'Default' else c for c in classes} if classes or only else dsn_classes - {'Ground'}
        skipped = sorted({'S_' + dsn_class(n) for n in skip})
        ignore = sorted(dsn_classes - want) + skipped
        stage_nets = only or {n for n in nets if dsn_class(n) in want} - skip - claimed
        claimed |= only
        base = (lambda t: promote(t, only)) if only else (lambda t: promote(t, skip, 'S_')) if skip else None
        staged = bool(classes or only)
        tag = f'-{i + 1}-{name}' if staged else ''
        # A stage that leaves nets open can be ripped up and run again with those nets routed first,
        # on their own (design.ROUTE_PROMOTE rounds, default 2): the hardest nets get the free board.
        # design.ROUTE_MARGINS: clearance margins to try the whole stage with, from the board as it was
        # before the stage, while nets stay open (Freerouting gives a different, as valid, result for
        # any change of its input). The attempt with the fewest unrouted connections is kept.
        # ROUTE_PROMOTE: rounds for every stage, or {stage name: rounds, '*': default}.
        promote_cfg = os.environ.get('ROUTE_PROMOTE', getattr(design, 'ROUTE_PROMOTE', 2))
        if isinstance(promote_cfg, dict):
            promote_cfg = promote_cfg.get(name, promote_cfg.get('*', 2))
        rounds = 1 + int(promote_cfg) if staged else 1
        attempts = []
        margins = getattr(design, 'ROUTE_MARGINS', None) or [None]
        before, best, attempt = snapshot(board), None, 0
        par = int(os.environ.get('ROUTE_PARALLEL', getattr(design, 'ROUTE_PARALLEL', 0)))
        if par > 1:
            # N Freerouting runs at once with different clearance margins (Freerouting uses one core): its
            # result swings from run to run, so the best of N by KiCad's count beats one more pass.
            from concurrent.futures import ThreadPoolExecutor
            pmargins = (list(margins) if margins != [None] else [0.02, 0.03, 0.04, 0.05])[:par]  # never 0: Freerouting's rounding then lands under the rule
            jobs = [freerouting(board, ignore, f'{tag}-par{k}', base, margin=m, run=False) for k, m in enumerate(pmargins)]
            jobs = [j for j in jobs if j]
            t_par = time.time()
            with ThreadPoolExecutor(len(jobs)) as ex:
                results = list(ex.map(fr_run, jobs))
            for m, res in zip(pmargins, results):
                restore(board, before)
                if not res:
                    continue
                for t in list(board.GetTracks()):
                    if not t.IsLocked():
                        board.Remove(t)
                import_ses(board, res[0], min_w)
                report = open_nets_report(board, stage_nets)
                score = sum(len(v) for v in report.values())
                attempt += 1
                attempts.append({'margin': m, 'round': 0, 'first': [], 'open': sorted(report),
                                 's': round(time.time() - t_par)})
                print(f'route: parallel attempt margin {m}: {score} open', flush=True)
                if best is None or score < best[0]:
                    best = (score, snapshot(board), sorted(report), [], attempt)
            if best is None:
                return False
            # Promote round (design.ROUTE_PROMOTE_PARALLEL): the nets the best attempt left open are routed
            # first, alone, on the pre-routed board, locked, and the parallel attempts run again around them
            # (MP-16 2026-11-04: the finish closed 60-90 % of what Freerouting left, never all).
            for pround in range(int(os.environ.get('ROUTE_PROMOTE_PARALLEL', getattr(design, 'ROUTE_PROMOTE_PARALLEL', 0)))):
                if not best[0]:
                    break
                promoted = sorted(set(best[3]) | set(best[2]))
                restore(board, before)
                for t in list(board.GetTracks()):
                    if not t.IsLocked():
                        board.Remove(t)
                res = freerouting(board, sorted(dsn_classes) + skipped, f'{tag}-promote{pround}',
                                  lambda t: promote(promote(t, skip, 'S_') if skip else t, set(promoted)))
                if not res:
                    break
                import_ses(board, res[0], min_w)
                for t in board.GetTracks():
                    t.SetLocked(True)
                first_open = sorted(open_nets_report(board, set(promoted)))
                print(f'route: promote round {pround + 1}: {", ".join(promoted)} routed first'
                      + (f'; still open: {", ".join(first_open)}' if first_open else ''), flush=True)
                promoted_base = snapshot(board)
                jobs = [freerouting(board, ignore, f'{tag}-pr{pround}-par{k}', base, margin=m, run=False)
                        for k, m in enumerate(pmargins)]
                jobs = [j for j in jobs if j]
                t_par = time.time()
                with ThreadPoolExecutor(len(jobs)) as ex:
                    results = list(ex.map(fr_run, jobs))
                for m, res in zip(pmargins, results):
                    restore(board, promoted_base)
                    if not res:
                        continue
                    for t in list(board.GetTracks()):
                        if not t.IsLocked():
                            board.Remove(t)
                    import_ses(board, res[0], min_w)
                    report = open_nets_report(board, stage_nets)
                    score = sum(len(v) for v in report.values())
                    attempt += 1
                    attempts.append({'margin': m, 'round': pround + 1, 'first': promoted, 'open': sorted(report),
                                     's': round(time.time() - t_par)})
                    print(f'route: promote round {pround + 1}, margin {m}: {score} open', flush=True)
                    if score < best[0]:
                        best = (score, snapshot(board), sorted(report), promoted, attempt)
            margins = []  # done: skip the sequential attempts
        for k, margin in enumerate(margins):
            MARGIN_OVERRIDE = margin
            vtag = tag + (f'-m{k}' if k else '')
            if k:
                restore(board, before)
            promoted, open_nets = [], []
            for round_ in range(rounds):
                t_attempt = time.time()
                if promoted:
                    res = freerouting(board, sorted(dsn_classes) + skipped, f'{vtag}-p{round_}',
                                      lambda t: promote(promote(t, skip, 'S_') if skip else t, set(promoted)))
                    if not res:
                        break
                    for t in list(board.GetTracks()):
                        if not t.IsLocked():
                            board.Remove(t)
                    import_ses(board, res[0], min_w)
                    for t in board.GetTracks():
                        t.SetLocked(True)
                res = freerouting(board, ignore, vtag + (f'-r{round_}' if round_ else ''), base)
                if not res:
                    break
                ses, log = res
                for t in list(board.GetTracks()):  # the session repeats unlocked wiring; locked (fixed) wiring stays out
                    if not t.IsLocked():
                        board.Remove(t)
                import_ses(board, ses, min_w)
                # KiCad's own connectivity, not Freerouting's log (which lists open nets only sometimes:
                # every stage here printed "all routed" while 10-39 pads stayed unconnected)
                report = open_nets_report(board, stage_nets)
                open_nets = sorted(report)
                score = sum(len(v) for v in report.values())
                attempt += 1
                attempts.append({'margin': margin, 'round': round_, 'first': list(promoted), 'open': open_nets,
                                 's': round(time.time() - t_attempt)})
                if best is None or score <= best[0]:  # ties: the later attempt
                    best = (score, snapshot(board), open_nets, list(promoted), attempt)
                if not open_nets or round_ == rounds - 1:
                    break
                # rip up this stage (its tracks are the unlocked ones, plus the promoted nets' ones)
                for t in list(board.GetTracks()):
                    if t.GetClass() == 'PCB_TRACK' and (t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y) in stub_keys:
                        continue  # escape stubs stay
                    if not t.IsLocked() or t.GetNetname() in promoted:
                        board.Remove(t)
                promoted = sorted(set(promoted) | set(open_nets))
            if not res:  # timed out or failed: this attempt is dropped, the best one so far stays
                attempt += 1
                if best is None:
                    return False
            if not best[0]:
                break
        MARGIN_OVERRIDE = None
        if best[4] != attempt:  # an earlier attempt was better
            restore(board, best[1])
        open_nets, promoted = best[2], best[3]
        for t in board.GetTracks():
            t.SetLocked(staged)
        rec['stages'].append({'name': name, 'nets': len(stage_nets), 'attempts': attempt, 'first': promoted,
                              'open': open_nets, 's': round(time.time() - t_stage), 'tries': attempts})
        print(f'route: stage {i + 1} {name} ({", ".join(sorted(want or only))}): {len(stage_nets)} nets'
              + (f'; first: {", ".join(promoted)}' if promoted else '')
              + (f'; open: {", ".join(open_nets)}' if open_nets else '; all routed')
              + f' ({round(time.time() - t_stage)} s)', flush=True)
    for t in board.GetTracks():
        t.SetLocked(False)
    tiny = [t for t in board.GetTracks() if t.GetClass() == 'PCB_TRACK' and t.GetLength() < pcbnew.FromMM(0.005)]
    for t in tiny:  # zero-length fragments the router sometimes leaves at pads
        board.Remove(t)
    if stubs:
        from fanout import trim_escapes
        live = [t for t in board.GetTracks() if t.GetClass() == 'PCB_TRACK' and
                (t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y) in stub_keys]
        print(f'route: {trim_escapes(board, live)} unused escape stubs removed')
    for z in pours:
        board.Add(z)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.BuildConnectivity()
    rec['phases'] = phases = {}
    t_phase = time.time()
    report = open_nets_report(board)
    rec['open_after_router'] = {n: len(v) for n, v in report.items()}
    rec['open_gaps_after_router'] = report  # where: {net: [[(item, x, y), ...], ...]}, design frame
    print(f'route: after Freerouting {sum(len(v) for v in report.values())} connections open in '
          f'{len(report)} nets ({round(time.time() - t_route)} s so far)', flush=True)
    print_open(report)
    if QUICK:  # placement iteration: the router's answer is all that is needed (build.py <board> quick)
        pcbnew.SaveBoard(PCB, board)
        rec['quick'] = True
        return not report
    if report:
        from finish import finish as run
        done, failed = run(board, getattr(design, 'CLEARANCE', 0.2) + 0.02, sorted(report),
                           {n: net_width(n) for n in {x for p in design.parts for x in p.pins.values() if x}},
                           keep=NO_RIPUP())
        rec['finish'] = {'joined': done, 'failed': failed}
        print(f'route: finish joined {done or "nothing"}' + (f'; failed {failed}' if failed else ''))
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    phases['finish'], t_phase = round(time.time() - t_phase), time.time()
    if getattr(design, 'GND_STITCH', 0):
        from finish import stitch
        n = stitch(board, getattr(design, 'CLEARANCE', 0.2) + 0.02, design.GND_STITCH)
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        rec['stitch_vias'] = n
        phases['stitch'], t_phase = round(time.time() - t_phase), time.time()
        print(f'route: {n} ground stitching vias ({design.GND_STITCH} mm grid)')
        from finish import join_ground
        if 'GND' in getattr(design, 'PLANES', {}).values():
            # A ground plane: every ground pad has a via to it (fan-out), and join_ground sees only the
            # outer pours, so it would 'join' areas the plane already joins (90 s each). DRC checks it.
            joined, cut_off = 0, 0
            print('route: ground joining skipped (ground plane)', flush=True)
        else:
            joined, cut_off = join_ground(board, getattr(design, 'CLEARANCE', 0.2) + 0.02, keep=NO_RIPUP(),
                                          widths={n: net_width(n) for n in {x for p in design.parts for x in p.pins.values() if x}})
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        rec['ground_joined'], rec['ground_cut_off'] = joined, cut_off
        phases['join_ground'] = round(time.time() - t_phase)
        print(f'route: {joined} cut-off ground areas joined to the plane' + (f'; {cut_off} still cut off' if cut_off else ''))
    board.BuildConnectivity()
    tracks = [t for t in board.GetTracks() if t.GetClass() == 'PCB_TRACK']
    vias = [t for t in board.GetTracks() if t.GetClass() == 'PCB_VIA']
    rec.update(tracks=len(tracks), vias=len(vias), unrouted=board.GetConnectivity().GetUnconnectedCount(False))
    rec['open_final'] = open_nets_report(board, skip=set())  # every net, ground included, with positions
    print(f'route: {len(tracks)} track segments, {len(vias)} vias; unrouted: {rec["unrouted"]}')
    pcbnew.SaveBoard(PCB, board)
    # content-derived IDs and order (tools/stable_ids.py), in a fresh process: reloading the board here,
    # after the route's many track edits, is what crashed pcbnew before
    import subprocess
    subprocess.run([sys.executable, '-c', 'import sys; sys.path.insert(0, sys.argv[1]); '
                    'from stable_ids import stabilize_board; stabilize_board(sys.argv[2])',
                    os.path.join(ROOT, 'tools'), PCB], check=True, capture_output=True)
    project_rewrite()
    return True


def finish():
    """Connect what the router left unconnected (nets from the last DRC report), see tools/finish.py."""
    import re
    import pcbnew
    from finish import finish as run
    rpt = os.path.join(BUILD, 'drc.rpt')
    text = open(rpt).read() if os.path.exists(rpt) else ''
    items = [i for i in re.split(r'\n(?=\[)', text) if i.startswith('[unconnected_items]')]
    nets = sorted({n for i in items for n in re.findall(r'\[([^\]]+)\] (?:of|on)', i)} - {'GND'})
    board = pcbnew.LoadBoard(PCB)
    done, failed = run(board, getattr(design, 'CLEARANCE', 0.2) + 0.02, nets, {n: net_width(n) for n in nets},
                       keep=NO_RIPUP())
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(PCB, board)
    project_rewrite()
    print(f'finish: nets {nets}; joined {done}; failed {failed}')
    return True


def project_rewrite():
    import project
    project.write(os.path.join(HERE, NAME + '.kicad_pro'), design.POWER_NETS, NAME,
                  getattr(design, 'CLEARANCE', 0.2), getattr(design, 'NETCLASSES', {}),
                  getattr(design, 'MIN_TRACK', 0.15))


def drc():
    import re
    import pcbnew
    board = pcbnew.LoadBoard(PCB)
    report = os.path.join(BUILD, 'drc.rpt')
    pcbnew.WriteDRCReport(board, report, pcbnew.EDA_UNITS_MILLIMETRES, True)
    text = open(report).read()
    items = [i for i in re.split(r'\n(?=\[)', text) if i.startswith('[')]
    errors, warnings, accepted, unconnected = [], collections.Counter(), 0, 0
    for i in items:
        kind = re.match(r'\[(\w+)\]', i).group(1)
        if kind == 'unconnected_items':
            unconnected += 1
            continue
        if 'Severity: error' not in i:
            warnings[kind] += 1
            continue
        if any(kind == k and re.search(a, i) and re.search(b, i) for k, a, b in design.DRC_ACCEPTED):
            accepted += 1
            continue
        errors.append(i.strip())
    for e in errors[:15]:
        print(e, '\n--')
    print(f'drc: {len(errors)} errors, {unconnected} unconnected, {accepted} accepted, warnings {dict(warnings)}; '
          f'report {os.path.relpath(report)}')
    import buildlog
    buildlog.append({'type': 'drc', 'board': NAME, 'time': buildlog.now(), 'pcb': buildlog.sha(PCB),
                     'errors': len(errors), 'unconnected': unconnected, 'accepted': accepted,
                     'warnings': dict(warnings)})
    return not errors and not unconnected


# Where JLCPCB's part sits relative to our footprint's origin, in the footprint's own frame (mm, y down,
# as in the .kicad_mod), for footprints whose origin is not the middle of the part JLCPCB places.
# MX-Hotswap-1U: the origin is the key switch's centre; the Kailh socket's body is centred between its
# two 3 mm holes, (-2.54, -5.08) and (3.81, -2.54). Found in JLCPCB's placement preview, 2026-10-27:
# the sockets lined up after moving them by exactly this (-0.635, +3.81 mm in the CPL on the bottom).
CPL_OFFSETS = {'MX-Hotswap-1U': (0.635, -3.81)}


def cpl_position(footprint, x, y, rot, bottom):
    """KiCad's position export (y up) moved by the footprint's CPL offset. KiCad flips a bottom-side
    footprint about its X axis, then rotates it by `rot` (counter-clockwise)."""
    import math
    lx, ly = CPL_OFFSETS.get(footprint, (0.0, 0.0))
    if bottom:
        ly = -ly
    a = math.radians(rot)
    dx = lx * math.cos(a) + ly * math.sin(a)          # board frame, y down
    dy = -lx * math.sin(a) + ly * math.cos(a)
    return round(x + dx, 6), round(y - dy, 6)          # the export's y points up


def fab():
    import csv
    import json
    import re
    import shutil
    import subprocess
    import zipfile
    out = os.path.join(HERE, 'fab')
    gerb = os.path.join(out, 'gerbers')
    # Only what this step writes: the board views (top/bottom .png/.pdf, tools/render.sh) stay.
    shutil.rmtree(gerb, ignore_errors=True)
    for f in (NAME + '-gerbers.zip', NAME + '-bom.csv', NAME + '-cpl.csv', 'pos.csv'):
        if os.path.exists(os.path.join(out, f)):
            os.remove(os.path.join(out, f))
    os.makedirs(gerb)
    inner = ''.join(f'In{k}.Cu,' for k in range(1, getattr(design, 'LAYERS', 2) - 1))
    layers = f'F.Cu,{inner}B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts'
    run = lambda *a: subprocess.run(['kicad-cli', 'pcb', 'export', *a], check=True, capture_output=True)
    run('gerbers', '--layers', layers, '--subtract-soldermask', '-o', gerb + '/', PCB)
    run('drill', '--format', 'excellon', '--excellon-separate-th', '--generate-map', '--map-format', 'gerberx2',
        '-o', gerb + '/', PCB)
    # Same board, same files: drop the export time KiCad writes into every file (the optional X2
    # CreationDate attribute and the date in the header comments), and give the zip entries a fixed
    # time, so a rebuild of an unchanged board leaves the order files byte-identical.
    for f in sorted(os.listdir(gerb)):
        fp = os.path.join(gerb, f)
        if f.endswith('.gbrjob'):
            job = json.load(open(fp))
            job.get('Header', {}).pop('CreationDate', None)
            open(fp, 'w').write(json.dumps(job, indent=2) + '\n')
            continue
        lines = open(fp, newline='').read().split('\n')
        lines = [l for l in lines if 'TF.CreationDate' not in l]
        lines = [re.sub(r' date .*?(\*?)$', r'\1', l) if l.startswith(('G04 Created by KiCad', '; DRILL file')) else l
                 for l in lines]
        open(fp, 'w', newline='').write('\n'.join(lines))
    zpath = os.path.join(out, NAME + '-gerbers.zip')
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(gerb)):
            info = zipfile.ZipInfo(f, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, open(os.path.join(gerb, f), 'rb').read())
    pos = os.path.join(out, 'pos.csv')
    run('pos', '--side', 'both', '--format', 'csv', '--units', 'mm', '--smd-only', '-o', pos, PCB)
    parts = {p.ref: p for p in design.parts}
    # JLCPCB pick-and-place (CPL) and BOM. THT parts (headers, encoder, battery) are left for hand soldering.
    with open(pos) as f, open(os.path.join(out, NAME + '-cpl.csv'), 'w', newline='') as g:
        w = csv.writer(g)
        w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
        placed = []
        for row in csv.DictReader(f):
            ref = row['Ref']
            p = parts.get(ref)
            if not p or p.dnp or ref.startswith(('H', 'TP')):
                continue
            x, y = cpl_position(p.footprint.split(':')[1], float(row['PosX']), float(row['PosY']), float(row['Rot']),
                                row['Side'] != 'top')
            w.writerow([ref, f'{x:.6f}mm', f'{y:.6f}mm', 'Top' if row['Side'] == 'top' else 'Bottom', row['Rot']])
            placed.append(ref)
    groups = collections.OrderedDict()
    for ref in placed:
        p = parts[ref]
        # identical parts on one line: by LCSC/MPN when known (keys carry their name as value)
        comment = p.mpn if p.lcsc and p.mpn else p.value
        groups.setdefault((comment, p.footprint.split(':')[1], p.lcsc, p.mpn), []).append(ref)
    with open(os.path.join(out, NAME + '-bom.csv'), 'w', newline='') as g:
        w = csv.writer(g)
        w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #', 'Manufacturer Part'])
        for (value, fp, lcsc, mpn), refs in groups.items():
            w.writerow([value, ','.join(refs), fp, lcsc, mpn])
    hand = sorted(r for r, p in parts.items() if not p.dnp and r not in placed and not r.startswith('H'))
    print(f'fab: {os.path.relpath(zpath)}, {NAME}-bom.csv ({len(groups)} lines), {NAME}-cpl.csv '
          f'({len(placed)} parts); hand-solder: {", ".join(hand)}')
    return True


def review():
    import pcbnew
    import buildlog
    import review as rv
    ok = rv.run(pcbnew.LoadBoard(PCB), design)
    buildlog.append({'type': 'review', 'board': NAME, 'time': buildlog.now(), 'pcb': buildlog.sha(PCB), **rv.LAST})
    return ok


def preflight():
    """Before a route run (seconds): placement checks, the congestion score against the last route run's,
    the windows where demand exceeds room, and what the last run left open, so each run starts from a
    prepared change instead of a guess. Prints a verdict; route refuses to run without ROUTE_NOTE."""
    import buildlog
    from congestion import analyse, report
    ok = courtyards() and bodies() and facing()
    res = analyse(PCB)
    report(res)
    routes = [r for r in buildlog.records(NAME) if r['type'] == 'route' and r.get('congestion') is not None]
    if routes:
        last = routes[-1]
        delta = res['score'] - last['congestion']
        print(f'preflight: congestion {res["score"]} vs {last["congestion"]} in the last route run '
              f'({last["time"][:16]}, {last.get("note") or "no note"}): {"better" if delta < 0 else "worse" if delta > 0 else "same"}'
              f' by {abs(delta):.1f}')
        left = sorted(set((last.get('finish') or {}).get('failed', [])) | set(n for n in (last.get('open_final') or {}) if n != 'GND'))
        if left:
            print(f'preflight: the last run left open {", ".join(left)}: does this change address each?')
    print('preflight: run with ROUTE_NOTE="..." and add a row to the routing journal first')
    return ok


def log():
    """Route runs of this board from the build log, with their DRC and review results."""
    import buildlog
    buildlog.table(NAME, last=int(os.environ.get('LOG_LAST', '15')), wide=bool(os.environ.get('LOG_WIDE')))
    return True


QUICK = False


def quick():
    """Placement iteration in minutes: route with Freerouting only (ROUTE_PASSES, default 3 here), no
    finish router, stitching or ground joining, then list what is open with pad positions (design frame)
    and print where the time went. A board that is open here will not be saved by the finish router."""
    global QUICK
    QUICK = True
    os.environ.setdefault('ROUTE_PASSES', '3')
    ok = route()
    return ok


STEPS = {'quick': quick, 'preflight': preflight, 'check': check, 'sch': sch, 'pcb': pcb, 'route': route, 'finish': finish, 'drc': drc, 'review': review,
         'fab': fab, 'log': log}

if __name__ == '__main__':
    steps = sys.argv[2:] or ['check']
    if steps == ['all']:
        steps = ['check', 'sch', 'pcb', 'route', 'drc', 'review', 'fab']
    os.makedirs(BUILD, exist_ok=True)
    for i, s in enumerate(steps):
        if not STEPS[s]():
            sys.exit(f'{s} failed')
        if s in ('pcb', 'route') and steps[i + 1:]:
            # pcbnew keeps the project it loaded with the board (the default one SaveBoard wrote) for
            # the rest of the process, so the net classes project_rewrite() just wrote would not reach
            # a board loaded later: every net would route and check as Default. After routing, the many
            # tracks removed and re-added from Python leave pcbnew's wrappers unreliable (a crash after
            # the save). Continue in a new process.
            sys.stdout.flush()
            os.execv(sys.executable, [sys.executable, os.path.abspath(__file__), sys.argv[1]] + steps[i + 1:])
