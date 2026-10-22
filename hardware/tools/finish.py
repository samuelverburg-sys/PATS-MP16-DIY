"""Finish routing: connect what the autorouter left unconnected, one connection at a time.

Freerouting sometimes stalls on the last few escapes from fine-pitch parts. This router finds,
per net, the groups of copper (pads, tracks, vias) that do not touch yet, and joins them with a
grid A* search (0.05 mm grid, both layers, vias where the layer changes) around all copper of
other nets at the board's clearance. The bottom layer costs more, to keep the ground plane
whole. Ground (poured) is skipped. Usage: build.py <board> finish.
"""
import heapq
import math

import numpy as np
import pcbnew

MM = pcbnew.FromMM
G = 0.05            # grid, mm
TRACK_W = 0.15      # mm
VIA_D, VIA_DRILL = 0.6, 0.3
B_COST = 2.0        # bottom layer step cost factor (keep the ground plane whole)
VIA_COST = 40       # in grid steps (2 mm)
SKIP_NETS = {'GND', ''}


class Shape:
    """Copper primitive in mm: rect (cx, cy, hw, hh), seg (x0, y0, x1, y1, r) or circle (cx, cy, r)."""

    def __init__(self, kind, args, layers, net, item=None):
        self.kind, self.args, self.layers, self.net, self.item = kind, args, layers, net, item

    def bbox(self):
        k, a = self.kind, self.args
        if k == 'rect':
            return a[0] - a[2], a[1] - a[3], a[0] + a[2], a[1] + a[3]
        if k == 'seg':
            return min(a[0], a[2]) - a[4], min(a[1], a[3]) - a[4], max(a[0], a[2]) + a[4], max(a[1], a[3]) + a[4]
        return a[0] - a[2], a[1] - a[2], a[0] + a[2], a[1] + a[2]

    def dist(self, X, Y):
        """Distance from points (arrays, mm) to the copper (0 inside)."""
        k, a = self.kind, self.args
        if k == 'rect':
            return np.hypot(np.maximum(np.abs(X - a[0]) - a[2], 0), np.maximum(np.abs(Y - a[1]) - a[3], 0))
        if k == 'circle':
            return np.maximum(np.hypot(X - a[0], Y - a[1]) - a[2], 0)
        x0, y0, x1, y1, r = a
        dx, dy = x1 - x0, y1 - y0
        L2 = dx * dx + dy * dy
        t = np.clip(((X - x0) * dx + (Y - y0) * dy) / L2, 0, 1) if L2 > 0 else 0
        return np.maximum(np.hypot(X - (x0 + t * dx), Y - (y0 + t * dy)) - r, 0)


def nm(v):
    return v / 1e6


NPTH = '<npth>'  # net name given to bare (non-plated) holes


def shapes(board):
    out, holes = [], []
    F, B = pcbnew.F_Cu, pcbnew.B_Cu
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            layers = [l for l in (F, B) if pad.IsOnLayer(l)]
            b = pad.GetBoundingBox()
            c = b.Centre()
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                holes.append(Shape('circle', (nm(c.x), nm(c.y), nm(pad.GetDrillSize().x) / 2), [F, B], NPTH))
                continue
            if layers:
                w, h = nm(b.GetWidth()), nm(b.GetHeight())
                if pad.GetShape() == pcbnew.PAD_SHAPE_CIRCLE or (pad.GetShape() == pcbnew.PAD_SHAPE_OVAL and
                                                                  abs(w - h) < 1e-3):
                    s = Shape('circle', (nm(c.x), nm(c.y), w / 2), layers, pad.GetNetname(), pad)
                elif pad.GetShape() == pcbnew.PAD_SHAPE_OVAL:  # capsule along its long side
                    r = min(w, h) / 2
                    dx, dy = (w / 2 - r, 0) if w > h else (0, h / 2 - r)
                    s = Shape('seg', (nm(c.x) - dx, nm(c.y) - dy, nm(c.x) + dx, nm(c.y) + dy, r), layers,
                              pad.GetNetname(), pad)
                else:
                    s = Shape('rect', (nm(c.x), nm(c.y), nm(b.GetWidth()) / 2, nm(b.GetHeight()) / 2), layers,
                              pad.GetNetname(), pad)
                out.append(s)
            if pad.GetDrillSize().x > 0:
                holes.append(Shape('circle', (nm(c.x), nm(c.y), nm(pad.GetDrillSize().x) / 2), [F, B], ''))
    for t in board.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            p = t.GetPosition()
            out.append(Shape('circle', (nm(p.x), nm(p.y), nm(t.GetWidth()) / 2), [F, B], t.GetNetname(), t))
            holes.append(Shape('circle', (nm(p.x), nm(p.y), nm(t.GetDrillValue()) / 2), [F, B], ''))
        else:
            s, e = t.GetStart(), t.GetEnd()
            out.append(Shape('seg', (nm(s.x), nm(s.y), nm(e.x), nm(e.y), nm(t.GetWidth()) / 2), [t.GetLayer()],
                             t.GetNetname(), t))
    return out, holes


def touching(a, b):
    if not set(a.layers) & set(b.layers):
        return False
    ax0, ay0, ax1, ay1 = a.bbox()
    bx0, by0, bx1, by1 = b.bbox()
    if ax1 < bx0 or bx1 < ax0 or ay1 < by0 or by1 < ay0:
        return False
    # sample the smaller shape's area: points along a segment's axis or the shape's centre lines
    pts = sample(a) if a.kind == 'seg' else sample(b) if b.kind == 'seg' else None
    if pts is not None:
        other = b if a.kind == 'seg' else a
        seg = a if a.kind == 'seg' else b
        X, Y = pts
        return bool((other.dist(X, Y) <= seg.args[4] + 1e-4).any())
    if a.kind == 'rect' and b.kind == 'rect':  # bboxes overlap on a shared layer
        return True
    c, o = (a, b) if a.kind == 'circle' else (b, a)
    return bool(o.dist(np.array([c.args[0]]), np.array([c.args[1]]))[0] <= c.args[2] + 1e-4)


def sample(s):
    x0, y0, x1, y1, _ = s.args
    n = max(2, int(math.hypot(x1 - x0, y1 - y0) / 0.02) + 1)
    t = np.linspace(0, 1, n)
    return x0 + t * (x1 - x0), y0 + t * (y1 - y0)


def clusters(items):
    parent = list(range(len(items)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if find(i) != find(j) and touching(items[i], items[j]):
                parent[find(i)] = find(j)
    groups = {}
    for i in range(len(items)):
        groups.setdefault(find(i), []).append(items[i])
    return list(groups.values())


class Grid:
    def __init__(self, board, clearance):
        self.board = board
        e = board.GetBoardEdgesBoundingBox()
        self.x0, self.y0 = nm(e.GetLeft()), nm(e.GetTop())
        self.nx = int(nm(e.GetWidth()) / G) + 1
        self.ny = int(nm(e.GetHeight()) / G) + 1
        xs = self.x0 + np.arange(self.nx) * G
        ys = self.y0 + np.arange(self.ny) * G
        self.X, self.Y = np.meshgrid(xs, ys)  # [iy, ix]
        self.cl = clearance
        edge_t = 0.3 + TRACK_W / 2
        edge_v = 0.3 + VIA_D / 2
        inside = lambda m: ((self.X >= self.x0 + m) & (self.X <= self.x0 + nm(e.GetWidth()) - m) &
                            (self.Y >= self.y0 + m) & (self.Y <= self.y0 + nm(e.GetHeight()) - m))
        self.edge_ok_t, self.edge_ok_v = inside(edge_t), inside(edge_v)

    def window(self, s, r):
        x0, y0, x1, y1 = s.bbox()
        i0 = max(0, int((x0 - r - self.x0) / G) - 1)
        i1 = min(self.nx, int((x1 + r - self.x0) / G) + 2)
        j0 = max(0, int((y0 - r - self.y0) / G) - 1)
        j1 = min(self.ny, int((y1 + r - self.y0) / G) + 2)
        return j0, j1, i0, i1

    def mark(self, arr, s, r):
        j0, j1, i0, i1 = self.window(s, r)
        if j0 >= j1 or i0 >= i1:
            return
        d = s.dist(self.X[j0:j1, i0:i1], self.Y[j0:j1, i0:i1])
        arr[j0:j1, i0:i1] |= d < r


def build_blocks(grid, all_shapes, holes, net, width=TRACK_W):
    F, B = pcbnew.F_Cu, pcbnew.B_Cu
    rt = width / 2 + grid.cl
    rv = VIA_D / 2 + grid.cl
    blk = {F: np.zeros(grid.X.shape, bool), B: np.zeros(grid.X.shape, bool)}
    vblk = np.zeros(grid.X.shape, bool)
    for s in all_shapes:
        if s.net == net:
            continue
        for l in s.layers:
            grid.mark(blk[l], s, rt)
        grid.mark(vblk, s, rv)
    for h in holes:
        grid.mark(vblk, h, VIA_DRILL / 2 + 0.25)  # hole to hole
        if h.net == NPTH:  # no copper ring to keep tracks off a bare hole: hole clearance
            grid.mark(vblk, h, VIA_D / 2 + 0.25 + 0.03)  # a via's copper ring too (0.03: grid rounding)
            grid.mark(blk[F], h, width / 2 + 0.25)
            grid.mark(blk[B], h, width / 2 + 0.25)
    from fanout import keepouts
    for bb, no_vias, no_tracks, layers in keepouts(grid.board):
        k = Shape('rect', (nm(bb.Centre().x), nm(bb.Centre().y), nm(bb.GetWidth()) / 2, nm(bb.GetHeight()) / 2), [], '')
        if no_tracks:
            for l in layers:
                grid.mark(blk[l], k, rt)
        if no_vias:
            grid.mark(vblk, k, rv)
    blk[F] |= ~grid.edge_ok_t
    blk[B] |= ~grid.edge_ok_t
    vblk |= ~grid.edge_ok_v
    return blk, vblk


def shrunk(s, d=0.08):
    """The shape d mm smaller all round, so a route starts and ends well inside the copper."""
    a = list(s.args)
    if s.kind == 'rect':
        a[2], a[3] = max(a[2] - d, 0.01), max(a[3] - d, 0.01)
    else:
        a[-1] = max(a[-1] - d, 0.01)
    return Shape(s.kind, tuple(a), s.layers, s.net, s.item)


def in_copper(grid, shapes_, layer):
    m = np.zeros(grid.X.shape, bool)
    for s in shapes_:
        if layer in s.layers:
            k = np.zeros(grid.X.shape, bool)
            grid.mark(k, shrunk(s), 1e-6)
            if not k.any():  # a narrow pad (0.19 mm codec pin) shrunk to less than one grid step: its centre cell
                x0, y0, x1, y1 = s.bbox()
                d = (grid.X - (x0 + x1) / 2) ** 2 + (grid.Y - (y0 + y1) / 2) ** 2
                k[np.unravel_index(np.argmin(d), d.shape)] = True
            m |= k
    return m


def astar(grid, blk, vblk, src, dst, F, B):
    """src/dst: {layer: bool mask}. Returns [(layer, iy, ix), ...] or None."""
    ny, nx = grid.X.shape
    L = [F, B]
    free = [~blk[F], ~blk[B]]
    goal = [dst[F] & free[0], dst[B] & free[1]]
    gy, gx = np.nonzero(goal[0] | goal[1])
    if not len(gy):
        return None
    # heuristic: octile distance to the goal set's bounding box
    ty0, ty1, tx0, tx1 = gy.min(), gy.max(), gx.min(), gx.max()

    def h(iy, ix):
        dy = max(ty0 - iy, 0, iy - ty1)
        dx = max(tx0 - ix, 0, ix - tx1)
        return max(dx, dy) + 0.414 * min(dx, dy)

    gcost = {}
    prev = {}
    heap = []
    for li in (0, 1):
        sy, sx = np.nonzero(src[L[li]] & free[li])
        for iy, ix in zip(sy.tolist(), sx.tolist()):
            k = (li, iy, ix)
            gcost[k] = 0.0
            heapq.heappush(heap, (h(iy, ix), 0.0, k))
    steps = [(-1, 0, 1), (1, 0, 1), (0, -1, 1), (0, 1, 1), (-1, -1, 1.414), (-1, 1, 1.414), (1, -1, 1.414),
             (1, 1, 1.414)]
    n = 0
    while heap:
        f, g, k = heapq.heappop(heap)
        if g > gcost.get(k, 1e18):
            continue
        li, iy, ix = k
        if goal[li][iy, ix]:
            path = [k]
            while k in prev:
                k = prev[k]
                path.append(k)
            return path[::-1]
        n += 1
        if n > 4_000_000:
            return None
        fac = B_COST if li == 1 else 1.0
        for dy, dx, c in steps:
            y2, x2 = iy + dy, ix + dx
            if 0 <= y2 < ny and 0 <= x2 < nx and free[li][y2, x2]:
                if dy and dx and not (free[li][iy, x2] and free[li][y2, ix]):
                    continue  # no corner cutting
                k2 = (li, y2, x2)
                g2 = g + c * fac
                if g2 < gcost.get(k2, 1e18):
                    gcost[k2] = g2
                    prev[k2] = k
                    heapq.heappush(heap, (g2 + h(y2, x2), g2, k2))
        if not vblk[iy, ix] and free[1 - li][iy, ix]:
            k2 = (1 - li, iy, ix)
            g2 = g + VIA_COST
            if g2 < gcost.get(k2, 1e18):
                gcost[k2] = g2
                prev[k2] = k
                heapq.heappush(heap, (g2 + h(iy, ix), g2, k2))
    return None


def add_path(board, grid, path, net, F, B, width=TRACK_W):
    ni = board.GetNetsByName()[net]
    L = [F, B]
    pt = lambda iy, ix: pcbnew.VECTOR2I(MM(grid.x0 + ix * G), MM(grid.y0 + iy * G))
    added = []
    # split into runs per layer, then merge collinear steps
    runs, cur = [], [path[0]]
    for k in path[1:]:
        if k[0] != cur[-1][0]:
            runs.append(cur)
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pt(k[1], k[2]))
            v.SetWidth(MM(VIA_D))
            v.SetDrill(MM(VIA_DRILL))
            v.SetLayerPair(F, B)
            v.SetNet(ni)
            board.Add(v)
            added.append(v)
            cur = [k]
        else:
            cur.append(k)
    runs.append(cur)
    for run in runs:
        if len(run) < 2:
            continue
        corners = [run[0]]
        for a, b, c in zip(run, run[1:], run[2:]):
            if (b[1] - a[1], b[2] - a[2]) != (c[1] - b[1], c[2] - b[2]):
                corners.append(b)
        corners.append(run[-1])
        for a, b in zip(corners, corners[1:]):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(pt(a[1], a[2]))
            t.SetEnd(pt(b[1], b[2]))
            t.SetWidth(MM(width))
            t.SetLayer(L[a[0]])
            t.SetNet(ni)
            board.Add(t)
            added.append(t)
    return added


def _join(board, grid, net, widths, added):
    """Join `net`'s pieces two closest at a time until it is whole. Returns (True, None), or
    (False, shapes of the smaller piece that could not be joined). New items go to `added`."""
    F, B = pcbnew.F_Cu, pcbnew.B_Cu
    while True:
        all_shapes, holes = shapes(board)
        groups = clusters([s for s in all_shapes if s.net == net])
        if len(groups) < 2:
            return True, None
        # join the two closest groups (by bbox centre distance)
        cen = lambda g: np.mean([[(s.bbox()[0] + s.bbox()[2]) / 2, (s.bbox()[1] + s.bbox()[3]) / 2] for s in g], 0)
        best = min(((i, j) for i in range(len(groups)) for j in range(i + 1, len(groups))),
                   key=lambda ij: np.linalg.norm(cen(groups[ij[0]]) - cen(groups[ij[1]])))
        a, b = groups[best[0]], groups[best[1]]
        src = {F: in_copper(grid, a, F), B: in_copper(grid, a, B)}
        dst = {F: in_copper(grid, b, F), B: in_copper(grid, b, B)}
        path = None
        for w in sorted({max((widths or {}).get(net, TRACK_W), TRACK_W), TRACK_W}, reverse=True):
            blk, vblk = build_blocks(grid, all_shapes, holes, net, w)
            path = astar(grid, blk, vblk, src, dst, F, B)
            if path:
                break
        if not path:  # the smaller piece (usually the stuck pin): where a rip-up should look
            return False, min(a, b, key=len)
        added += add_path(board, grid, path, net, F, B, w)


def _save(items):
    out = []
    for t in items:
        if t.GetClass() == 'PCB_VIA':
            out.append(('via', t.GetPosition(), t.GetWidth(), t.GetDrillValue(), t.GetNetCode()))
        else:
            out.append(('track', t.GetStart(), t.GetEnd(), t.GetWidth(), t.GetLayer(), t.GetNetCode()))
    return out


def _put(board, saved):
    for item in saved:
        if item[0] == 'via':
            _, p, w, drill, net = item
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(p)
            v.SetWidth(w)
            v.SetDrill(drill)
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        else:
            _, a, b, w, layer, net = item
            v = pcbnew.PCB_TRACK(board)
            v.SetStart(a)
            v.SetEnd(b)
            v.SetWidth(w)
            v.SetLayer(layer)
        v.SetNetCode(net)
        board.Add(v)


def _ripup(board, grid, net, stuck, widths, keep, tries=4, reach=1.0, join=None):
    """Local rip-up: remove one nearby other net's wiring, join `net` (or call join(added) -> bool), then
    rejoin the removed net. Kept only if the board's unconnected count drops; otherwise everything is
    put back. Returns the ripped net or None."""
    join = join or (lambda added: _join(board, grid, net, widths, added)[0])
    def gap(s, t):
        a, b = s.bbox(), t.bbox()
        return max(0.0, a[0] - b[2], b[0] - a[2]) ** 2 + max(0.0, a[1] - b[3], b[1] - a[3]) ** 2
    all_shapes, _ = shapes(board)
    near = {}
    for s in all_shapes:
        if s.net == net or s.net in SKIP_NETS or s.net in keep or s.net == NPTH or s.item is None:
            continue
        if s.item.GetClass() not in ('PCB_TRACK', 'PCB_VIA'):
            continue
        d = min(gap(s, g) for g in stuck)
        if d <= reach ** 2:
            near[s.net] = min(d, near.get(s.net, d))
    def unconnected():  # whole board, pours refilled: a re-route must not cut a pour apart
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        board.BuildConnectivity()
        return board.GetConnectivity().GetUnconnectedCount(False)
    before = unconnected()
    import os
    import time
    t_end = time.time() + float(os.environ.get('FINISH_RIPUP_SECONDS', '90'))  # per stuck net
    for other in sorted(near, key=near.get)[:tries]:
        if time.time() > t_end:
            print(f'finish: {net}: rip-up budget used up', flush=True)
            break
        old = [t for t in board.GetTracks() if t.GetNetname() == other]
        saved = _save(old)
        for t in old:
            board.Remove(t)
        added = []
        ok = join(added) and _join(board, grid, other, widths, added)[0]
        if ok and unconnected() < before:
            return other
        for t in added:
            board.Remove(t)
        _put(board, saved)
    unconnected()
    return None


def finish(board, clearance, only=None, widths=None, keep=()):
    """widths: {net: track width mm} (the net's class width); each join is tried at that width first and
    at TRACK_W (0.15 mm) only if the wide track does not fit. A join that finds no path tries a local
    rip-up of a nearby net (never one in `keep`, nor ground)."""
    grid = Grid(board, clearance)
    done, failed = [], []
    nets = sorted(({s.net for s in shapes(board)[0]} & set(only or [])) if only else
                  ({s.net for s in shapes(board)[0]}) - SKIP_NETS) if True else []
    nets = [n for n in nets if n not in SKIP_NETS]
    import time
    for net in nets:
        added = []
        t0 = time.time()
        ok, stuck = _join(board, grid, net, widths, added)
        if added or not ok:
            print(f'finish: {net}: {"joined" if ok else "stuck, trying rip-up"} ({time.time() - t0:.0f} s)', flush=True)
        if added:
            done.append(net)
        if ok:
            continue
        other = _ripup(board, grid, net, stuck, widths, keep)
        if other:
            done.append(f'{net} (re-routed {other})')
        else:
            failed.append(net)
    return done, failed


def stitch(board, clearance, pitch=4.0, net='GND'):
    """Ground stitching vias on a `pitch` mm grid wherever a via fits clear of other nets' copper,
    tying the top pour to the bottom plane (no isolated top-pour pieces, shorter return paths)."""
    # The pours keep 0.3 mm from other nets and are at least 0.25 mm wide: a stitching via must sit
    # where the pour can actually surround it on both layers.
    grid = Grid(board, max(clearance, 0.3) + 0.25)
    all_shapes, holes = shapes(board)
    _, vblk = build_blocks(grid, all_shapes, holes, net)
    # keep stitching vias off pads of the net itself too (no vias in pads)
    for s in all_shapes:  # no vias in the net's own pads, and keep spacing to its existing vias
        if s.net == net and s.item is not None and s.item.GetClass() in ('PAD', 'PCB_VIA'):
            grid.mark(vblk, s, VIA_D / 2 + clearance + (0.25 if s.item.GetClass() == 'PCB_VIA' else 0))
    for fp in board.GetFootprints():  # no stitching vias under part bodies (SD socket shell, jacks, ...)
        for layer in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
            c = fp.GetCourtyard(layer)
            if c.OutlineCount():
                bb = c.BBox()
                s = Shape('rect', (nm(bb.Centre().x), nm(bb.Centre().y), nm(bb.GetWidth()) / 2, nm(bb.GetHeight()) / 2),
                          [], '')
                grid.mark(vblk, s, VIA_D / 2)
    ni = board.GetNetsByName()[net]
    step = int(round(pitch / G))
    n, added = 0, []
    for iy in range(step // 2, grid.ny, step):
        for ix in range(step // 2, grid.nx, step):
            if vblk[iy, ix]:
                continue
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pcbnew.VECTOR2I(int(MM(float(grid.x0 + ix * G))), int(MM(float(grid.y0 + iy * G)))))
            v.SetWidth(MM(VIA_D))
            v.SetDrill(MM(VIA_DRILL))
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            v.SetNet(ni)
            board.Add(v)
            added.append(v)
            n += 1
    # Second pass: a top-pour piece the grid missed (boxed in by tracks) gets a via at a free spot inside it.
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    vias = [t.GetPosition() for t in board.GetTracks() if t.GetClass() == 'PCB_VIA' and t.GetNetname() == net]
    free = np.argwhere(~vblk)
    for z in board.Zones():
        if z.GetIsRuleArea() or z.GetNetname() != net or not z.IsOnLayer(pcbnew.F_Cu):
            continue
        polys = z.GetFilledPolysList(pcbnew.F_Cu)
        for k in range(polys.OutlineCount()):
            piece = globals()['piece'](polys, k)
            if any(piece.Contains(p) for p in vias):
                continue
            b = polys.Outline(k).BBox()
            pos = lambda iy, ix: (int(MM(float(grid.x0 + ix * G))), int(MM(float(grid.y0 + iy * G))))
            inside = [(iy, ix) for iy, ix in free
                      if b.GetLeft() < pos(iy, ix)[0] < b.GetRight() and b.GetTop() < pos(iy, ix)[1] < b.GetBottom()]
            for iy, ix in inside:
                p = pcbnew.VECTOR2I(*pos(iy, ix))
                if piece.Contains(p):
                    v = pcbnew.PCB_VIA(board)
                    v.SetPosition(p)
                    v.SetWidth(MM(VIA_D))
                    v.SetDrill(MM(VIA_DRILL))
                    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                    v.SetNet(ni)
                    board.Add(v)
                    added.append(v)
                    n += 1
                    break
    # Drop stitching vias the pour does not reach on both layers (they would only be stubs).
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    fills = {L: [z.GetFilledPolysList(L) for z in board.Zones()
                 if not z.GetIsRuleArea() and z.GetNetname() == net and z.IsOnLayer(L)] for L in (pcbnew.F_Cu, pcbnew.B_Cu)}
    for v in added:
        if not all(any(P.Contains(v.GetPosition()) for P in fills[L]) for L in fills):
            board.Remove(v)
            n -= 1
    return n


def piece(P, k):
    """Fill piece k of a SHAPE_POLY_SET with its holes (an outline alone would also 'contain'
    everything inside its holes)."""
    s = pcbnew.SHAPE_POLY_SET()
    s.AddOutline(P.Outline(k))
    for h in range(P.HoleCount(k)):
        s.AddHole(P.Hole(k, h))
    return s


def ground_groups(board, net='GND'):
    """Groups of the net's pour pieces (both layers) joined by its vias, through-hole pads and tracks.
    Returns [{'pts': [(x_mm, y_mm), ...], 'pieces': [(layer, SHAPE_POLY_SET), ...]}], largest first.
    Every piece is in some group, also one touched by nothing but a pad edge (KiCad counts a pad as
    connected to a piece only when the pad's centre lies in it)."""
    links = [t.GetPosition() for t in board.GetTracks() if t.GetClass() == 'PCB_VIA' and t.GetNetname() == net]
    links += [p.GetPosition() for f in board.GetFootprints() for p in f.Pads()
              if p.GetNetname() == net and p.GetDrillSize().x > 0]
    nodes = []
    for L in (pcbnew.F_Cu, pcbnew.B_Cu):
        for z in board.Zones():
            if z.GetIsRuleArea() or z.GetNetname() != net or not z.IsOnLayer(L):
                continue
            P = z.GetFilledPolysList(L)
            for k in range(P.OutlineCount()):
                s = piece(P, k)
                nodes.append((L, s))
    par = list(range(len(nodes)))

    def root(i):
        while par[i] != i:
            i = par[i]
        return i

    members = {}
    for v in links:
        ins = [i for i, (_, s) in enumerate(nodes) if s.Contains(v)]
        for a in ins[1:]:
            par[root(a)] = root(ins[0])
        if ins:
            members.setdefault(ins[0], []).append((nm(v.x), nm(v.y)))
    smd = [p for f in board.GetFootprints() for p in f.Pads() if p.GetNetname() == net and p.GetDrillSize().x == 0]
    pad_pts = [p.GetPosition() for p in smd]
    pad_boxes = [(p.GetBoundingBox().Centre(), p.GetBoundingBox().GetWidth() / 2, p.GetBoundingBox().GetHeight() / 2)
                 for p in smd]
    # Tracks: each segment is a node too; segments join each other at shared ends, vias and pieces
    # they end in, so a multi-segment track whose corners lie outside the pour still links its ends.
    segs = [t for t in board.GetTracks() if t.GetClass() == 'PCB_TRACK' and t.GetNetname() == net]
    base = len(nodes)
    par.extend(range(base, base + len(segs) + len(pad_pts)))
    ends = {}
    # A pad's area counts as filled by every piece that reaches it, so pad centres (and track ends on
    # pads) say nothing about which piece a pad joins: they only link tracks to each other.
    on_pad = lambda q: any(abs(q.x - c.x) <= hw and abs(q.y - c.y) <= hh for c, hw, hh in pad_boxes)
    for k, t in enumerate(segs):
        for q in (t.GetStart(), t.GetEnd()):
            key = (q.x // 1000, q.y // 1000)  # 1 um
            if key in ends:
                par[root(base + k)] = root(ends[key])
            else:
                ends[key] = base + k
            if on_pad(q):
                continue
            for i, (_, s) in enumerate(nodes):
                if s.Contains(q):
                    par[root(base + k)] = root(i)
    for j, q in enumerate(pad_pts):  # a pad joins the tracks that start on it
        node = base + len(segs) + j
        for k, t in enumerate(segs):
            if t.GetStart() == q or t.GetEnd() == q:
                par[root(node)] = root(base + k)
    groups = {}
    for i, (L, s) in enumerate(nodes):
        g = groups.setdefault(root(i), {'pts': [], 'pieces': []})
        g['pieces'].append((L, s))
        g['pts'].extend(members.get(i, []))
    return sorted(groups.values(), key=lambda g: (len(g['pts']), len(g['pieces'])), reverse=True)


def join_ground(board, clearance, net='GND', keep=(), widths=None):
    """Route a track from each ground group cut off from the main plane to the main plane; where other
    nets' tracks fence a group in on both layers, rip up one of them (never one in `keep`) and reroute
    it. Groups that cannot be joined are skipped, so one hard case does not stop the rest."""
    F, B = pcbnew.F_Cu, pcbnew.B_Cu
    grid = Grid(board, clearance)
    joined, skip = 0, set()
    for _ in range(40):
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        groups = ground_groups(board, net)
        key = lambda g: (round(nm(g['pieces'][0][1].BBox().Centre().x), 2), round(nm(g['pieces'][0][1].BBox().Centre().y), 2))
        todo = [g for g in groups[1:] if key(g) not in skip]
        if not todo:
            break
        main, small = groups[0], todo[-1]
        all_shapes, holes = shapes(board)
        blk, vblk = build_blocks(grid, all_shapes, holes, net)
        circ = lambda pts: [Shape('circle', (x, y, 0.2), [F, B], net) for x, y in pts]
        dst = {L: in_copper(grid, circ(main['pts']), L) for L in (F, B)}
        for L, pc in main['pieces']:  # or anywhere in the main pour (sampled every 0.5 mm: a track ending there joins it)
            bb = pc.BBox()
            j0, j1, i0, i1 = grid.window(Shape('rect', (nm(bb.Centre().x), nm(bb.Centre().y), nm(bb.GetWidth()) / 2,
                                                         nm(bb.GetHeight()) / 2), [], ''), 0)
            for iy in range(j0, j1, 10):
                for ix in range(i0, i1, 10):
                    if pc.Contains(pcbnew.VECTOR2I(int(MM(float(grid.X[iy, ix]))), int(MM(float(grid.Y[iy, ix]))))):
                        dst[L][iy, ix] = True
        src = {L: in_copper(grid, circ(small['pts']), L) for L in (F, B)}
        for L, pc in small['pieces']:  # any cell inside the cut-off piece can start the track
            bb = pc.BBox()
            j0, j1, i0, i1 = grid.window(Shape('rect', (nm(bb.Centre().x), nm(bb.Centre().y), nm(bb.GetWidth()) / 2,
                                                         nm(bb.GetHeight()) / 2), [], ''), 0)
            for iy in range(j0, j1):
                for ix in range(i0, i1):
                    if pc.Contains(pcbnew.VECTOR2I(int(MM(float(grid.X[iy, ix]))), int(MM(float(grid.Y[iy, ix]))))):
                        src[L][iy, ix] = True
        path = astar(grid, blk, vblk, src, dst, F, B)
        if path:
            items = add_path(board, grid, path, net, F, B)
            pcbnew.ZONE_FILLER(board).Fill(board.Zones())
            if len(ground_groups(board, net)) < len(groups):
                joined += 1
                continue
            for t in items:  # no progress: take the track out again
                board.Remove(t)

        def bridge(added):  # the same join, with the blocks recomputed after a rip-up
            sh, ho = shapes(board)
            bl, vb = build_blocks(grid, sh, ho, net)
            p = astar(grid, bl, vb, src, dst, F, B)
            if p:
                added += add_path(board, grid, p, net, F, B)
            return bool(p)
        stuck = []
        for L, pc in small['pieces']:
            bb = pc.BBox()
            stuck.append(Shape('rect', (nm(bb.Centre().x), nm(bb.Centre().y), nm(bb.GetWidth()) / 2,
                                        nm(bb.GetHeight()) / 2), [L], net))
        if _ripup(board, grid, net, stuck, widths, keep, reach=0.5, join=bridge):
            joined += 1
            continue
        skip.add(key(small))
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    return joined, len(ground_groups(board, net)) - 1
