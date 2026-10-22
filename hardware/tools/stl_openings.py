"""Find the openings in an enclosure wall by slicing an STL (no dependencies).

  python3 stl_openings.py PART.stl            # bounding box, then wall gaps per height
  python3 stl_openings.py PART.stl --wall ymax --z 2,4,6

Slices the mesh with horizontal planes (z) and reports, along the chosen outer wall, the intervals
where no material is: the cut-outs for jacks, USB and switches. Coordinates are the STL's own (mm).
"""
import struct
import sys


def load(path):
    data = open(path, 'rb').read()
    if data[:5] == b'solid' and b'facet' in data[:300]:
        tris, cur = [], []
        for line in data.decode(errors='ignore').splitlines():
            w = line.split()
            if w and w[0] == 'vertex':
                cur.append(tuple(map(float, w[1:4])))
                if len(cur) == 3:
                    tris.append(cur)
                    cur = []
        return tris
    n = struct.unpack_from('<I', data, 80)[0]
    return [[struct.unpack_from('<3f', data, 84 + 50 * i + 12 + 12 * k) for k in range(3)] for i in range(n)]


def slice_segments(tris, z):
    segs = []
    for t in tris:
        pts = []
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            if (a[2] - z) * (b[2] - z) < 0:
                f = (z - a[2]) / (b[2] - a[2])
                pts.append((a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1])))
        if len(pts) == 2:
            segs.append(pts)
    return segs


def main():
    path = sys.argv[1]
    wall = 'ymax'
    zs = None
    if '--wall' in sys.argv:
        wall = sys.argv[sys.argv.index('--wall') + 1]
    if '--z' in sys.argv:
        zs = [float(v) for v in sys.argv[sys.argv.index('--z') + 1].split(',')]
    tris = load(path)
    xs = [v[0] for t in tris for v in t]
    ys = [v[1] for t in tris for v in t]
    zz = [v[2] for t in tris for v in t]
    print(f'{path}: {len(tris)} triangles, x {min(xs):.2f}..{max(xs):.2f}, y {min(ys):.2f}..{max(ys):.2f}, '
          f'z {min(zz):.2f}..{max(zz):.2f}')
    if zs is None:
        zs = [round(min(zz) + (max(zz) - min(zz)) * k / 10, 2) for k in range(1, 10)]
    axis = 1 if wall[0] == 'y' else 0
    along = 1 - axis
    lim = max(ys if axis else xs) if wall.endswith('max') else min(ys if axis else xs)
    span = (min(xs if axis else ys), max(xs if axis else ys))
    for z in zs:
        segs = slice_segments(tris, z)
        # material within 3 mm of the wall: covered intervals along the wall
        cov = sorted((min(p[along] for p in s), max(p[along] for p in s)) for s in segs
                     if all(abs(p[axis] - lim) < 3.0 for p in s))
        gaps, end = [], span[0]
        for a, b in cov:
            if a > end + 0.3:
                gaps.append((end, a))
            end = max(end, b)
        if span[1] > end + 0.3:
            gaps.append((end, span[1]))
        g = ', '.join(f'{a:.2f}-{b:.2f} (w {b - a:.2f}, c {(a + b) / 2:.2f})' for a, b in gaps)
        print(f'  z {z:6.2f}: {"no wall here" if not cov else "gaps " + (g or "none")}')


if __name__ == '__main__':
    main()
