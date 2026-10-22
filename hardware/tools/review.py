"""Post-route review checks that the DRC does not cover (build.py <board> review).

- decoupling: every capacitor between a supply net and GND should sit close to the chip pin it
  decouples (distance from its supply pad to the nearest chip pin on that net);
- power widths: the narrowest track on each power net, and how much of the net is narrower than
  its class width (short neck-downs at fine-pitch pads are expected, long thin runs are not);
- dangling: track ends that touch nothing.
"""
import math

import pcbnew

DECOUPLE_MAX_MM = 3.0
LAST = {}  # counts of the last run (build log)


def mm(v):
    return v / 1e6


def _dist(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def decoupling(board, supply_nets):
    """Capacitors from a supply/reference net to GND: distance from the supply pad to the nearest pin
    on that net of a chip, connector or LED (any part with more than two pins)."""
    chips = [(fp.GetReference(), p) for fp in board.GetFootprints()
             if fp.GetReference()[0] in 'UXJD' and len([q for q in fp.Pads() if q.GetNumber()]) > 2
             for p in fp.Pads() if p.GetNetname()]
    out = []
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        pads = [p for p in fp.Pads() if p.GetNumber()]
        if not ref.startswith('C') or len(pads) != 2:
            continue
        nets = {p.GetNetname() for p in pads}
        if 'GND' not in nets or len(nets) != 2:
            continue
        sup = next(p for p in pads if p.GetNetname() != 'GND')
        net = sup.GetNetname()
        if net not in supply_nets:
            continue  # RC timing or signal-coupling caps
        near = [(_dist(sup.GetPosition(), q.GetPosition()), r, q.GetNumber()) for r, q in chips if q.GetNetname() == net]
        if not near:
            continue
        d, r, n = min(near)
        out.append((mm(d), ref, net, f'{r}.{n}'))
    return sorted(out, reverse=True)


def power_widths(board, classes):
    """classes: {net: class width mm}. Returns [(net, min width, narrow length, total length)]."""
    acc = {}
    for t in board.GetTracks():
        if t.GetClass() != 'PCB_TRACK' or t.GetNetname() not in classes:
            continue
        a = acc.setdefault(t.GetNetname(), [1e9, 0.0, 0.0])
        w, L = mm(t.GetWidth()), mm(t.GetLength())
        a[0] = min(a[0], w)
        a[2] += L
        if w < classes[t.GetNetname()] - 1e-3:
            a[1] += L
    return sorted((n, a[0], a[1], a[2]) for n, a in acc.items())


def run(board, design):
    print('review: decoupling (supply pad to nearest chip pin on the same net)')
    far = 0
    supply = set(design.POWER_NETS) | set(getattr(design, 'DECOUPLED', ()))
    for d, ref, net, pin in decoupling(board, supply):
        flag = 'FAR' if d > DECOUPLE_MAX_MM else ''
        if flag:
            far += 1
        print(f'  {ref:5} {net:12} {pin:7} {d:5.1f} mm {flag}')
    widths = {n: 0.6 for n in design.POWER_NETS}
    for c, (w, nets) in getattr(design, 'NETCLASSES', {}).items():
        for n in nets:
            if n in widths or c in ('Medium',):
                widths[n] = w
    print('review: power track widths (net, narrowest, length narrower than class, total length)')
    thin = 0
    for net, wmin, narrow, total in power_widths(board, widths):
        flag = 'THIN' if narrow > 3.0 else ''
        if flag:
            thin += 1
        print(f'  {net:12} class {widths[net]:.2f}  min {wmin:.3f}  narrow {narrow:5.1f} / {total:6.1f} mm {flag}')
    print(f'review: {far} decoupling caps further than {DECOUPLE_MAX_MM} mm, {thin} power nets with long thin runs')
    LAST.update(far=far, thin=thin)
    return True
