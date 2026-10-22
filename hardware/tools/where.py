"""Courtyard boxes of the placed parts in the design.py frame (mm, seen from above), and which overlap.

  python3 tools/where.py mp16 [x0 y0 x1 y1]     # parts inside a window (default: whole board)
"""
import os
import sys

import pcbnew

ORIGIN = (40.0, 30.0)  # tools/pcb.py


def boxes(board_path):
    board = pcbnew.LoadBoard(board_path)
    out = {}
    for fp in board.GetFootprints():
        side = 'B' if fp.IsFlipped() else 'F'
        c = fp.GetCourtyard(pcbnew.B_CrtYd if side == 'B' else pcbnew.F_CrtYd)
        b = c.BBox() if c.OutlineCount() else fp.GetBoundingBox(False, False)
        out[fp.GetReference()] = (side, pcbnew.ToMM(b.GetLeft()) - ORIGIN[0], pcbnew.ToMM(b.GetTop()) - ORIGIN[1],
                                  pcbnew.ToMM(b.GetRight()) - ORIGIN[0], pcbnew.ToMM(b.GetBottom()) - ORIGIN[1],
                                  fp.HasThroughHolePads())
    return out


def main():
    name = sys.argv[1]
    win = [float(v) for v in sys.argv[2:6]] if len(sys.argv) >= 6 else [-1, -1, 80, 110]
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', name, name + '.kicad_pcb')
    bx = boxes(here)
    inside = {r: b for r, b in bx.items() if b[1] < win[2] and b[3] > win[0] and b[2] < win[3] and b[4] > win[1]}
    for r, (s, x0, y0, x1, y1, th) in sorted(inside.items(), key=lambda kv: (kv[1][2], kv[1][1])):
        print(f'{r:6} {s}{" TH" if th else "   "} x {x0:6.2f}..{x1:6.2f}  y {y0:6.2f}..{y1:6.2f}')
    refs = sorted(inside)
    hits = []
    for i, a in enumerate(refs):
        for b in refs[i + 1:]:
            A, B = bx[a], bx[b]
            same = A[0] == B[0] or A[5] or B[5]  # through-hole parts block both sides
            if same and A[1] < B[3] and B[1] < A[3] and A[2] < B[4] and B[2] < A[4]:
                hits.append(f'{a}/{b}')
    print('overlapping boxes:', ', '.join(hits) or 'none')


if __name__ == '__main__':
    main()
