"""Convert one footprint (LIB) from an EasyEDA Standard PCB JSON into a KiCad 7 footprint.

Pads, holes and silkscreen are taken as placed on the source board, relative to the LIB
origin. Parts placed on the bottom are mirrored so the KiCad footprint is defined as seen
from its own side (build.py places it on B again). Usage:

  easyeda_fp.py BOARD.json PACKAGE_SUBSTRING NAME OUT.kicad_mod [pad=new ...]
"""
import json
import sys

U = 0.254  # EasyEDA Standard unit = 10 mil


def f(v):
    return f'{v:.4f}'.rstrip('0').rstrip('.')


def convert(board_json, package, name, out, rename=None):
    rename = rename or {}
    d = json.load(open(board_json))
    lib = next(s for s in d['shape'] if s.startswith('LIB~') and package in s.split('#@$')[0])
    subs = lib.split('#@$')
    head = subs[0].split('~')
    ox, oy = float(head[1]), float(head[2])
    attrs = dict(zip(head[3].split('`')[0::2], head[3].split('`')[1::2]))
    pad_layers = {p.split('~')[6] for p in subs if p.startswith('PAD~')}
    silk_layers = {t.split('~')[2] for t in subs if t.startswith('TRACK~')}
    bottom = '2' in pad_layers or ('4' in silk_layers and '3' not in silk_layers)
    sx = -1 if bottom else 1

    def P(x, y):
        return (sx * (float(x) - ox) * U, (float(y) - oy) * U)

    lines, xs, ys = [], [], []
    for t in subs:
        k = t.split('~')
        if k[0] == 'PAD':
            shape, x, y, w, h, layer, _net, num, hole_r = k[1], k[2], k[3], float(k[4]), float(k[5]), k[6], k[7], k[8], float(k[9] or 0)
            cx, cy = P(x, y)
            num = rename.get(num, num)
            tht = layer == '11'
            layers = '"*.Cu" "*.Mask"' if tht else '"F.Cu" "F.Paste" "F.Mask"'
            if shape in ('RECT', 'POLYGON'):
                pts = list(map(float, k[10].split()))
                px = [P(pts[i], pts[i + 1]) for i in range(0, len(pts), 2)]
                w_mm = max(p[0] for p in px) - min(p[0] for p in px)
                h_mm = max(p[1] for p in px) - min(p[1] for p in px)
                cx = (max(p[0] for p in px) + min(p[0] for p in px)) / 2
                cy = (max(p[1] for p in px) + min(p[1] for p in px)) / 2
                kshape = 'rect'
            elif shape == 'ELLIPSE':
                w_mm = h_mm = w * U
                kshape = 'circle'
            elif shape == 'OVAL':
                w_mm, h_mm = w * U, h * U
                kshape = 'oval'
            else:
                raise ValueError(f'pad shape {shape}')
            drill = ''
            if tht:
                slot = float(k[13] or 0) * U
                dia = 2 * hole_r * U
                if slot > dia:
                    drill = f'(drill oval {f(dia)} {f(slot)})' if h_mm > w_mm else f'(drill oval {f(slot)} {f(dia)})'
                else:
                    drill = f'(drill {f(dia)})'
            kind = 'thru_hole' if tht else 'smd'
            lines.append(f'  (pad "{num}" {kind} {kshape} (at {f(cx)} {f(cy)}) (size {f(w_mm)} {f(h_mm)}) {drill} (layers {layers}))')
            xs += [cx - w_mm / 2, cx + w_mm / 2]
            ys += [cy - h_mm / 2, cy + h_mm / 2]
        elif k[0] == 'HOLE':
            cx, cy = P(k[1], k[2])
            dia = 2 * float(k[3]) * U
            lines.append(f'  (pad "" np_thru_hole circle (at {f(cx)} {f(cy)}) (size {f(dia)} {f(dia)}) (drill {f(dia)}) (layers "*.Cu" "*.Mask"))')
            xs += [cx - dia / 2, cx + dia / 2]
            ys += [cy - dia / 2, cy + dia / 2]
        elif k[0] == 'TRACK' and k[2] in ('3', '4'):
            width = float(k[1]) * U
            pts = list(map(float, k[4].split()))
            px = [P(pts[i], pts[i + 1]) for i in range(0, len(pts), 2)]
            for a, b in zip(px, px[1:]):
                lines.append(f'  (fp_line (start {f(a[0])} {f(a[1])}) (end {f(b[0])} {f(b[1])}) (stroke (width {f(max(width, 0.12))}) (type solid)) (layer "F.SilkS"))')
                xs += [a[0], b[0]]
                ys += [a[1], b[1]]
    m = 0.25
    x0, x1, y0, y1 = min(xs) - m, max(xs) + m, min(ys) - m, max(ys) + m
    crt = [f'  (fp_line (start {f(a)} {f(b)}) (end {f(c)} {f(e)}) (stroke (width 0.05) (type solid)) (layer "F.CrtYd"))'
           for (a, b), (c, e) in zip([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], [(x1, y0), (x1, y1), (x0, y1), (x0, y0)])]
    tht_any = any('thru_hole' in l and 'np_' not in l for l in lines)
    src = attrs.get('Manufacturer Part', package)
    with open(out, 'w') as fh:
        fh.write(f'(footprint "{name}" (version 20221018) (generator pcbnew)\n  (layer "F.Cu")\n')
        fh.write(f'  (descr "{src}, LCSC {attrs.get("Supplier Part", "")}; converted from the PATS MP-16 EasyEDA board by tools/easyeda_fp.py")\n')
        fh.write(f'  (attr {"through_hole" if tht_any else "smd"})\n')
        fh.write(f'  (fp_text reference "REF**" (at 0 {f(y0 - 1)}) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))\n')
        fh.write(f'  (fp_text value "{name}" (at 0 {f(y1 + 1)}) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))\n')
        fh.write('\n'.join(crt + lines) + '\n)\n')
    return bottom


if __name__ == '__main__':
    board, package, name, out, *ren = sys.argv[1:]
    print('bottom' if convert(board, package, name, out, dict(r.split('=') for r in ren)) else 'top')
