"""Ground fan-out before autorouting: a via next to every top-side SMD ground pad (and in the
middle of each grounded exposed pad), joined to it by a short track. The via reaches the bottom
ground pour, so ground needs no autorouted tracks; build.py then leaves GND out of the router's
netlist, which frees the router for the signals. Used where the bottom layer is a near-solid
ground plane (audio board: design.GND_FANOUT = True)."""
import math
import pcbnew

MM = pcbnew.FromMM
VIA_D, VIA_DRILL, TRACK_W = 0.6, 0.3, 0.3
# Copper side of the parts being fanned out (design.GND_FANOUT_SIDE): 'F' on the PATS boards, 'B' on a
# board whose parts are all on the bottom (MP-16 rev 2). Set by fanout().
LAYER = pcbnew.F_Cu
GAP = 0.2  # copper clearance kept around the new via (> the board's 0.15 mm rule)
TRACK_GAP = 0.155  # for the short fan-out tracks
HOLE_GAP = 0.3  # via copper to a bare (NPTH) hole: the board's hole clearance is 0.25 mm
SIBLING_W = 0.13  # track from a fine-pitch ground pin into the part's exposed pad


def keepouts(board):
    """Rule areas (board and footprint ones, e.g. an antenna keep-out) that forbid vias or tracks:
    [(bbox, no_vias, no_tracks, copper layers)]."""
    zones = list(board.Zones()) + [z for fp in board.GetFootprints() for z in fp.Zones()]
    return [(z.GetBoundingBox(), z.GetDoNotAllowVias(), z.GetDoNotAllowTracks(),
             [l for l in (pcbnew.F_Cu, pcbnew.B_Cu) if z.GetLayerSet().Contains(l)]) for z in zones
            if z.GetIsRuleArea() and (z.GetDoNotAllowVias() or z.GetDoNotAllowTracks())]


def _obstacles(board, net):
    """(x, y, half-width, half-height) of every copper pad not on `net`, and of every keep-out, in nm."""
    # keep-outs that forbid vias, or tracks on the top layer (fan-out tracks are on F.Cu)
    out = [(b.Centre().x, b.Centre().y, b.GetWidth() / 2, b.GetHeight() / 2) for b, no_vias, no_tracks, layers
           in keepouts(board) if no_vias or (no_tracks and LAYER in layers)]
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname() == net and pad.GetNetname():
                continue
            b = pad.GetBoundingBox()
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:  # bare holes (key sockets' pegs): hole clearance
                grow = MM(HOLE_GAP - GAP)
                out.append((b.Centre().x, b.Centre().y, b.GetWidth() / 2 + grow, b.GetHeight() / 2 + grow))
                continue
            if not (pad.IsOnLayer(pcbnew.F_Cu) or pad.IsOnLayer(pcbnew.B_Cu)):
                continue  # paste-only windows (exposed pads) are not copper
            out.append((b.Centre().x, b.Centre().y, b.GetWidth() / 2, b.GetHeight() / 2))
    return out


def _free(x, y, obstacles, vias, edge):
    r = MM(VIA_D / 2 + GAP)
    x0, y0, x1, y1 = edge
    if not (x0 + MM(0.3 + VIA_D / 2) < x < x1 - MM(0.3 + VIA_D / 2) and
            y0 + MM(0.3 + VIA_D / 2) < y < y1 - MM(0.3 + VIA_D / 2)):
        return False
    for cx, cy, hw, hh in obstacles:
        if abs(x - cx) < hw + r and abs(y - cy) < hh + r:
            return False
    return all(math.hypot(x - vx, y - vy) >= MM(VIA_D + GAP) for vx, vy in vias)


def _track_free(a, b, half_w, obstacles, own=None):
    """No obstacle pad closer than TRACK_GAP to the straight track a-b (sampled every 0.02 mm),
    ignoring the part of the track inside its own pad `own` (x, y, half-w, half-h)."""
    n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / MM(0.02)))
    for i in range(n + 1):
        x, y = a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n
        if own and abs(x - own[0]) <= own[2] and abs(y - own[1]) <= own[3]:
            continue
        for cx, cy, hw, hh in obstacles:
            if math.hypot(max(abs(x - cx) - hw, 0), max(abs(y - cy) - hh, 0)) < half_w + MM(TRACK_GAP):
                return False
    return True


def _to_sibling(fp, pad, net, obstacles, w=None):
    """End point of an axis-aligned track from `pad` into another `net` pad of the same footprint."""
    c = pad.GetPosition()
    b = pad.GetBoundingBox()
    w = w or min(MM(TRACK_W), min(b.GetWidth(), b.GetHeight()))
    best = None
    for q in fp.Pads():
        if q.GetNumber() == pad.GetNumber() and q.GetPosition() == pad.GetPosition():  # SWIG: `is` never matches
            continue
        if q.GetNetname() != net:
            continue
        qb = q.GetBoundingBox()
        qc, qhw, qhh = qb.Centre(), qb.GetWidth() / 2, qb.GetHeight() / 2
        for axis in (0, 1):
            perp = abs(c.y - qc.y) if axis == 0 else abs(c.x - qc.x)
            if perp > (qhh if axis == 0 else qhw) + w / 4:
                continue
            a0, q0, qh = (c.x, qc.x, qhw) if axis == 0 else (c.y, qc.y, qhh)
            end = q0 - qh + MM(0.1) if a0 < q0 else q0 + qh - MM(0.1)
            # The pin may sit just beside the pad's side (up to w/4): pull the end inside the pad, or
            # the track overlaps it without connecting (KiCad joins a track end only inside a pad).
            inset = MM(0.02)
            if axis == 0:
                p = (end, min(max(c.y, qc.y - qhh + inset), qc.y + qhh - inset))
            else:
                p = (min(max(c.x, qc.x - qhw + inset), qc.x + qhw - inset), end)
            d = abs(end - a0)
            if (best is None or d < best[0]) and _track_free((c.x, c.y), p, w / 2, obstacles,
                                                             (c.x, c.y, b.GetWidth() / 2, b.GetHeight() / 2)):
                best = (d, p)
    return best[1] if best else None


def _to_neighbour(board, fp, pad, net, obstacles, reach=3.0):
    """End point of an axis-aligned track from `pad` into a `net` pad of another footprint within
    `reach` mm (straight out of the pin, as a short fan-out)."""
    c = pad.GetPosition()
    b = pad.GetBoundingBox()
    w = min(MM(TRACK_W), min(b.GetWidth(), b.GetHeight()))
    best = None
    for other in board.GetFootprints():
        if other.GetReference() == fp.GetReference():
            continue
        for q in other.Pads():
            if q.GetNetname() != net or not q.IsOnLayer(LAYER):
                continue
            qb = q.GetBoundingBox()
            qc, qhw, qhh = qb.Centre(), qb.GetWidth() / 2, qb.GetHeight() / 2
            if math.hypot(qc.x - c.x, qc.y - c.y) > MM(reach):
                continue
            for axis in (0, 1):
                perp = abs(c.y - qc.y) if axis == 0 else abs(c.x - qc.x)
                if perp > (qhh if axis == 0 else qhw) - w / 2:
                    continue  # the track must land fully on the pad
                a0, q0, qh = (c.x, qc.x, qhw) if axis == 0 else (c.y, qc.y, qhh)
                end = q0 - qh + MM(0.15) if a0 < q0 else q0 + qh - MM(0.15)
                p = (end, c.y) if axis == 0 else (c.x, end)
                d = abs(end - a0)
                if (best is None or d < best[0]) and _track_free((c.x, c.y), p, w / 2, obstacles,
                                                                 (c.x, c.y, b.GetWidth() / 2, b.GetHeight() / 2)):
                    best = (d, p)
    return best[1] if best else None


def _track(board, ni, a, b, width):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(pcbnew.VECTOR2I(int(a[0]), int(a[1])))
    t.SetEnd(pcbnew.VECTOR2I(int(b[0]), int(b[1])))
    t.SetWidth(int(width))
    t.SetLayer(LAYER)
    t.SetNet(ni)
    board.Add(t)
    return t


def fanout(board, net='GND', at=None, side='F'):
    """A via (or a short track to a ground pad) for every `net` pad of the parts on `side` ('F' or 'B').
    at: {'U9.10': (dx, dy)} mm, a via position relative to that pad, where the automatic spot right
    beside the pin would block the pin's neighbours."""
    global LAYER
    LAYER = pcbnew.B_Cu if side == 'B' else pcbnew.F_Cu
    at = at or {}
    ni = board.GetNetsByName()[net]
    obstacles = _obstacles(board, net)
    edge = board.GetBoardEdgesBoundingBox()
    edge = (edge.GetLeft(), edge.GetTop(), edge.GetRight(), edge.GetBottom())
    vias, placed, failed, items = [], 0, [], []
    for fp in board.GetFootprints():
        if fp.GetLayer() != LAYER:
            continue
        fc = fp.GetPosition()
        for pad in fp.Pads():
            if pad.GetNetname() != net or pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                continue
            if not pad.IsOnLayer(LAYER):
                continue
            c = pad.GetPosition()
            b = pad.GetBoundingBox()
            hw, hh = b.GetWidth() / 2, b.GetHeight() / 2
            spot = None
            key = f'{fp.GetReference()}.{pad.GetNumber()}'
            if key in at:
                spot = (c.x + MM(at[key][0]), c.y + MM(at[key][1]))
            elif min(hw, hh) < MM(0.15):  # fine-pitch pin: join the part's own ground pad first, keeping
                t = _to_sibling(fp, pad, net, obstacles, MM(SIBLING_W))  # its neighbours' escapes free
                if t:
                    items.append(_track(board, ni, (c.x, c.y), t, MM(SIBLING_W)))
                    placed += 1
                    continue
            if spot:
                pass
            elif hw > MM(0.35) and hh > MM(0.35) and fp.GetReference()[0] == 'U':  # exposed pad: via in the middle
                spot = (c.x, c.y)
            else:
                dx, dy = c.x - fc.x, c.y - fc.y  # prefer away from the part's centre
                dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
                dirs.sort(key=lambda d: -(d[0] * dx + d[1] * dy))
                for step in (0.0, 0.3, 0.6, 1.0):
                    for ux, uy in dirs:
                        reach = (hw if ux else hh) + MM(VIA_D / 2 + GAP + step)
                        x, y = c.x + ux * reach, c.y + uy * reach
                        w = min(MM(TRACK_W), 2 * min(hw, hh))
                        if _free(x, y, obstacles, vias, edge) and _track_free((c.x, c.y), (x, y), w / 2, obstacles, (c.x, c.y, hw, hh)):
                            spot = (x, y)
                            break
                    if spot:
                        break
            if not spot:  # no room for a via: a straight track to a ground pad of the same part (e.g. its EP)
                t = _to_sibling(fp, pad, net, obstacles)
                if not t:  # or to a ground pad of a neighbouring part (e.g. a decoupling cap right above the pin)
                    t = _to_neighbour(board, fp, pad, net, obstacles)
                if t:
                    t = _track(board, ni, (c.x, c.y), t, min(MM(TRACK_W), 2 * min(hw, hh)))
                    items.append(t)
                    placed += 1
                else:
                    failed.append(f'{fp.GetReference()}.{pad.GetNumber()}')
                continue
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pcbnew.VECTOR2I(int(spot[0]), int(spot[1])))
            v.SetWidth(MM(VIA_D))
            v.SetDrill(MM(VIA_DRILL))
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            v.SetNet(ni)
            board.Add(v)
            items.append(v)
            vias.append(spot)
            obstacles.append((spot[0], spot[1], MM(VIA_D / 2), MM(VIA_D / 2)))
            if (spot[0], spot[1]) != (c.x, c.y):
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(c)
                t.SetEnd(pcbnew.VECTOR2I(int(spot[0]), int(spot[1])))
                t.SetWidth(int(min(MM(TRACK_W), 2 * min(hw, hh))))
                t.SetLayer(LAYER)
                t.SetNet(ni)
                board.Add(t)
                items.append(t)
            placed += 1
    return items, failed


def escapes(board, refs, length=0.8, width=0.15):
    """Escape stubs for fine-pitch parts: from every signal pad a straight track out of the pin field,
    `length` mm beyond the pad's outer end. Locked before autorouting, they keep each pin's exit in
    pin order, so the router cannot pass a track under a neighbouring pad's end and wall it in."""
    items = []
    for ref in refs:
        fp = board.FindFootprintByReference(ref)
        c = fp.GetPosition()
        for pad in fp.Pads():
            net = pad.GetNetname()
            if not net or net == 'GND' or not pad.GetNumber():
                continue
            p = pad.GetPosition()
            b = pad.GetBoundingBox()
            dx, dy = p.x - c.x, p.y - c.y
            if abs(dx) > abs(dy):
                ux, uy, half = (1 if dx > 0 else -1), 0, b.GetWidth() / 2
            else:
                ux, uy, half = 0, (1 if dy > 0 else -1), b.GetHeight() / 2
            reach = half + MM(length)
            t = _track(board, pad.GetNet(), (p.x, p.y), (p.x + ux * reach, p.y + uy * reach), MM(width))
            t.SetLayer(fp.GetLayer())  # on the part's side (bottom-mounted parts on B.Cu)
            items.append(t)
    return items


def trim_escapes(board, stubs):
    """Remove escape stubs the router did not use (nothing attached anywhere along them but the pad)."""
    removed = 0
    for s in stubs:
        a, b, net, half = s.GetStart(), s.GetEnd(), s.GetNetname(), s.GetWidth() / 2
        L = math.hypot(b.x - a.x, b.y - a.y)

        def on_stub(q):
            t = max(0.0, min(1.0, ((q.x - a.x) * (b.x - a.x) + (q.y - a.y) * (b.y - a.y)) / (L * L)))
            px, py = a.x + t * (b.x - a.x), a.y + t * (b.y - a.y)
            return math.hypot(q.x - px, q.y - py) <= half and math.hypot(q.x - a.x, q.y - a.y) > MM(0.3)

        used = False
        for t in board.GetTracks():
            if t.GetNetname() != net or (t.GetStart() == a and t.GetEnd() == b):
                continue
            pts = [t.GetPosition()] if t.GetClass() == 'PCB_VIA' else [t.GetStart(), t.GetEnd()]
            if any(on_stub(q) for q in pts):
                used = True
                break
        if not used:
            board.Remove(s)
            removed += 1
    return removed
