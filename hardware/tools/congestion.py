"""Routing demand against room, before routing (seconds instead of a 25-minute route).

Demand: every net's connections as the router must make them (a minimum spanning tree over its pads,
straight lines), counted where they pass through, not within 1 mm of the pads they join. Room: how many tracks fit through each window on both layers, from the copper already
there (pads, holes). Where demand exceeds room the router has to detour or give up; the sum of that
overflow is the placement's score (lower is better) and the worst windows name the nets that cause them.

  python3 tools/congestion.py BOARD.kicad_pcb [--top N]      # also: build.py <board> preflight
"""
import math
import sys

import numpy as np
import pcbnew

ORIGIN = (40.0, 30.0)  # tools/pcb.py: design frame (0, 0) on the KiCad sheet
CELL = 0.5             # mm
WIN = 4                # cells per window side (2 mm)
PITCH = 0.28           # mm per track: 0.15 track + 0.13 clearance (JLCPCB 2-layer, the fine class)
SKIP = {'GND'}


def _grid(board):
    x0, y0, x1, y1 = 0.0, 0.0, 76.2, 104.775
    bb = board.GetBoardEdgesBoundingBox()
    if bb.GetWidth():
        x0, y0 = pcbnew.ToMM(bb.GetLeft()) - ORIGIN[0], pcbnew.ToMM(bb.GetTop()) - ORIGIN[1]
        x1, y1 = pcbnew.ToMM(bb.GetRight()) - ORIGIN[0], pcbnew.ToMM(bb.GetBottom()) - ORIGIN[1]
    nx, ny = int((x1 - x0) / CELL) + 1, int((y1 - y0) / CELL) + 1
    return x0, y0, nx, ny


def analyse(path, skip=SKIP):
    """The score averaged over four window grids shifted by half a window: a single grid's score jumped
    from 68 to 50 when a pin header moved 1.2 mm across a window border (aliasing, not routability)."""
    board = pcbnew.LoadBoard(path)
    runs = [_analyse(board, skip, off) for off in ((0, 0), (0.5, 0), (0, 0.5), (0.5, 0.5))]
    best = runs[0]
    return {'score': round(sum(r['score'] for r in runs) / len(runs), 1),
            'windows_over': best['windows_over'], 'spots': best['spots']}


def _analyse(board, skip, off):
    x0, y0, nx, ny = _grid(board)
    x0 -= off[0] * WIN * CELL
    y0 -= off[1] * WIN * CELL
    nx, ny = nx + WIN, ny + WIN
    blocked = {pcbnew.F_Cu: np.zeros((ny, nx), bool), pcbnew.B_Cu: np.zeros((ny, nx), bool)}

    def mark(layer, cx, cy, hw, hh):
        i0, i1 = int((cx - hw - x0) / CELL), int((cx + hw - x0) / CELL) + 1
        j0, j1 = int((cy - hh - y0) / CELL), int((cy + hh - y0) / CELL) + 1
        blocked[layer][max(0, j0):max(0, j1), max(0, i0):max(0, i1)] = True

    pads_of = {}
    for fp in board.GetFootprints():
        for p in fp.Pads():
            bb = p.GetBoundingBox()
            cx, cy = pcbnew.ToMM(bb.Centre().x) - ORIGIN[0], pcbnew.ToMM(bb.Centre().y) - ORIGIN[1]
            hw, hh = pcbnew.ToMM(bb.GetWidth()) / 2 + 0.1, pcbnew.ToMM(bb.GetHeight()) / 2 + 0.1
            for layer in blocked:
                if p.IsOnLayer(layer) or p.GetDrillSizeX() > 0:
                    mark(layer, cx, cy, hw, hh)
            n = p.GetNetname()
            if n and n not in skip:
                pos = p.GetPosition()
                pads_of.setdefault(n, []).append((pcbnew.ToMM(pos.x) - ORIGIN[0], pcbnew.ToMM(pos.y) - ORIGIN[1]))

    # demand: minimum spanning tree per net (Prim), each edge drawn into the windows it crosses
    wy, wx = ny // WIN + 1, nx // WIN + 1
    demand = np.zeros((wy, wx))
    nets_in = [[set() for _ in range(wx)] for _ in range(wy)]
    for net, pts in pads_of.items():
        pts = sorted(set((round(x, 2), round(y, 2)) for x, y in pts))
        if len(pts) < 2:
            continue
        inside, edges = {0}, []
        best = {i: (math.dist(pts[0], pts[i]), 0) for i in range(1, len(pts))}
        while best:
            i = min(best, key=lambda k: best[k][0])
            edges.append((pts[best[i][1]], pts[i]))
            inside.add(i)
            del best[i]
            for k in best:
                d = math.dist(pts[i], pts[k])
                if d < best[k][0]:
                    best[k] = (d, i)
        for (ax, ay), (bx, by) in edges:
            steps = max(1, int(math.dist((ax, ay), (bx, by)) / (CELL / 2)))
            seen = set()
            for s in range(steps + 1):
                x, y = ax + (bx - ax) * s / steps, ay + (by - ay) * s / steps
                if min(math.dist((x, y), (ax, ay)), math.dist((x, y), (bx, by))) < 1.0:
                    continue  # where a connection starts or ends it uses the pad, not the room around it
                w = (int((y - y0) / CELL) // WIN, int((x - x0) / CELL) // WIN)
                if w not in seen and 0 <= w[0] < wy and 0 <= w[1] < wx:
                    seen.add(w)
                    demand[w] += 1
                    nets_in[w[0]][w[1]].add(net)

    # room: tracks that fit across a window = free share of its cells on each layer x tracks per side
    room = np.zeros((wy, wx))
    per_side = WIN * CELL / PITCH
    for layer, blk in blocked.items():
        free = 1.0 - blk.astype(float)
        for j in range(wy):
            for i in range(wx):
                cell = free[j * WIN:(j + 1) * WIN, i * WIN:(i + 1) * WIN]
                if cell.size:
                    room[j, i] += cell.mean() * per_side
    over = np.maximum(0.0, demand - room)
    hot = sorted(((over[j, i], demand[j, i], room[j, i], j, i) for j in range(wy) for i in range(wx) if over[j, i] > 0),
                 reverse=True)
    spots = [{'x': round(x0 + (i + 0.5) * WIN * CELL, 1), 'y': round(y0 + (j + 0.5) * WIN * CELL, 1),
              'demand': int(d), 'room': round(r, 1), 'nets': sorted(nets_in[j][i])} for o, d, r, j, i in hot]
    return {'score': round(float(over.sum()), 1), 'windows_over': len(hot), 'spots': spots}


def report(res, top=8):
    print(f'congestion: score {res["score"]} (sum of demand over room, lower is better), '
          f'{res["windows_over"]} windows of {WIN * CELL:g} mm over')
    for s in res['spots'][:top]:
        nets = ', '.join(s['nets'][:8]) + (' ...' if len(s['nets']) > 8 else '')
        print(f'congestion:   ({s["x"]:5.1f}, {s["y"]:5.1f}) {s["demand"]} connections, room {s["room"]}: {nets}')


if __name__ == '__main__':
    top = int(sys.argv[sys.argv.index('--top') + 1]) if '--top' in sys.argv else 8
    report(analyse(sys.argv[1]), top)
