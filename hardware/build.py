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
    for w in warn + order:
        print('facing:', w)
    print(f'facing: {len(warn)} parts turned away from the pin they serve, {len(order)} pairs in crossing order')
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
                if ca.OutlineCount() and cb.OutlineCount() and ca.Collide(cb):
                    clashes.append((a.GetReference(), b.GetReference(), board.GetLayerName(layer)))
    for c in clashes:
        print('courtyard overlap:', *c)
    print(f'placement: {len(clashes)} courtyard overlaps')
    return True


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


def freerouting(board, ignore, tag, edit=None):
    """Export `board` (pours already removed), run Freerouting skipping the `ignore` classes,
    return the session path, or None. `edit` may rewrite the DSN text first."""
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
    margin = MARGIN_OVERRIDE if MARGIN_OVERRIDE is not None else \
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
        d = edge - clear
        box = [xs[0] + d, ys[0] + d, xs[1] - d, ys[1] - d]
        path = f'{box[2]:g} {box[1]:g}  {box[0]:g} {box[1]:g}  {box[0]:g} {box[3]:g}  {box[2]:g} {box[3]:g}  {box[2]:g} {box[1]:g}'
        text = text[:m.start(1)] + path + text[m.end(1):]
    if edit:
        text = edit(text)
    open(dsn, 'w').write(text)
    # No post-route optimisation: '-mt 0' alone does not turn it off (it still ran with 3 threads on a
    # fully routed stage). Multi-threaded, it made results differ from run to run, and on the UI board
    # it ran past the time limit, losing a complete routing.
    cmd = [JAVA, '-jar', FREEROUTING, '-de', dsn, '-do', ses, '-mp', os.environ.get('ROUTE_PASSES', '30'),
           '-mt', '0', '--router.optimizer.enabled=false',
           '--gui.enabled=false', '--usage_and_diagnostic_data.disable_analytics=true']
    if ignore:
        # Freerouting's own fan-out stage would stub every SMD pin of every net, ignored classes
        # included; those stubs would then be locked into the stage.
        cmd += ['--router.autorouter.ignore_net_classes=' + ','.join(ignore), '--router.fanout.enabled=false']
    log = os.path.join(BUILD, f'freerouting{tag}.log')
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=int(os.environ.get('ROUTE_TIMEOUT', '900')))
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
           'design': buildlog.sha(os.path.join(HERE, 'design.py')), 'stages': [],
           'settings': buildlog.settings(
               design, float(os.environ.get('ROUTE_CLEARANCE_MARGIN', getattr(design, 'ROUTE_CLEARANCE_MARGIN', 0.02))),
               int(os.environ.get('ROUTE_PASSES', '30')), int(os.environ.get('ROUTE_TIMEOUT', '900')), FREEROUTING)}
    t0, ok = time.time(), False
    try:
        ok = _route(rec)
    finally:
        rec['ok'] = bool(ok)
        rec['s'] = round(time.time() - t0)
        if ok:
            rec['pcb'] = buildlog.sha(PCB)
        buildlog.append(rec)
        print(f'route: {rec["s"] / 60:.1f} min; logged to {os.path.relpath(buildlog.LOG)}')
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
    pours = [z for z in board.Zones() if not z.GetIsRuleArea() or
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
            items, failed = fanout(board, at=getattr(design, 'GND_FANOUT_VIA', {}), side=getattr(design, 'GND_FANOUT_SIDE', 'F'))
            for t in items:
                t.SetLocked(True)
            print(f'route: ground fan-out {len(items)} items' + (f'; no room at {", ".join(failed)}' if failed else ''))
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
                unrouted = {m: int(c) for m, c in re.findall(r"Net '([^']+)' \((\d+) unrouted", log) if m in stage_nets}
                open_nets = sorted(unrouted)
                score = sum(unrouted.values())
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
              + (f'; open: {", ".join(open_nets)}' if open_nets else '; all routed'))
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
    left = board.GetConnectivity().GetUnconnectedCount(False)
    rec['phases'] = phases = {}
    t_phase = time.time()
    if left:
        from finish import finish as run
        done, failed = run(board, getattr(design, 'CLEARANCE', 0.2) + 0.02, None,
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


def fab():
    import csv
    import shutil
    import subprocess
    import zipfile
    out = os.path.join(HERE, 'fab')
    gerb = os.path.join(out, 'gerbers')
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(gerb)
    layers = 'F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts'
    run = lambda *a: subprocess.run(['kicad-cli', 'pcb', 'export', *a], check=True, capture_output=True)
    run('gerbers', '--layers', layers, '--subtract-soldermask', '-o', gerb + '/', PCB)
    run('drill', '--format', 'excellon', '--excellon-separate-th', '--generate-map', '--map-format', 'gerberx2',
        '-o', gerb + '/', PCB)
    zpath = os.path.join(out, NAME + '-gerbers.zip')
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(gerb)):
            z.write(os.path.join(gerb, f), f)
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
            w.writerow([ref, row['PosX'] + 'mm', row['PosY'] + 'mm', 'Top' if row['Side'] == 'top' else 'Bottom',
                        row['Rot']])
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


def log():
    """Route runs of this board from the build log, with their DRC and review results."""
    import buildlog
    buildlog.table(NAME)
    return True


STEPS = {'check': check, 'sch': sch, 'pcb': pcb, 'route': route, 'finish': finish, 'drc': drc, 'review': review,
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
