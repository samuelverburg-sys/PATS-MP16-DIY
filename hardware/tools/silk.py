"""Silkscreen labels placed where they stay readable (pcb step).

design.LABELS: [(text or (alternatives, longest first), (x, y), sides, size, rot, search[, reach mm])] in layout mm: sides 'F', 'B' or 'FB' (both;
the bottom copy mirrored), size = text height in mm (0.8 for labels, 0.65 for passive references:
below JLCPCB's 1.0 mm recommendation, at their 0.15 mm minimum stroke), rot in
degrees, search 'xy' / 'x' / 'y' / '' = the directions a label may move from (x, y) to clear pads,
holes, part outlines (courtyards) and other labels on its side. Labels that find no free spot are
reported (and not placed), so a layout change cannot silently bury one.
"""
import pcbnew


MM = pcbnew.FromMM
STROKE = 0.15

# Board-to-board connector: short names for the pins (silk room is one 2.54 mm column per pin).
SHORT = {'VLED': 'VLED', 'GND': 'GND', '+3V3': '3V3', 'SR_LOAD': 'LOAD', 'SR_CLK': 'CLK', 'SR_DATA': 'DATA',
         'ENC_A': 'ENCA', 'ENC_B': 'ENCB', 'I2C_SCL': 'SCL', 'I2C_SDA': 'SDA', 'LED_DATA': 'LED',
         'AIN1': 'AIN1', 'AIN2': 'AIN2', 'AIN3': 'AIN3', 'AIN4': 'AIN4', 'EXP_MOSI': 'MOSI', 'EXP_LATCH': 'LTCH'}


def length(text, size):
    """Printed length of `text` at height `size` (mm), measured with pcbnew's stroke font."""
    t = pcbnew.PCB_TEXT(pcbnew.BOARD())
    t.SetText(text)
    t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
    t.SetTextThickness(MM(STROKE))
    return t.GetBoundingBox().GetWidth() / 1e6


def beside(text, pin, side, size=0.8, pad=0.85, gap=0.25):
    """Centre for an upright (90 degree) label of `text` whose near end sits `gap` mm past a round pad of
    radius `pad` at `pin`, on its 'above' or 'below' side."""
    d = pad + gap + length(text, size) / 2
    return (pin[0], pin[1] - d if side == 'above' else pin[1] + d)


def connector_labels(sides='FB', size=0.8, skip=()):
    import connector  # PATS UI/audio boards only (their board-to-board connector)
    """A label right beside every board-to-board pin (except `skip`): odd pins above the upper row, even
    pins below the lower row, reading upwards, plus the pin-1 corner."""
    out = []
    for n, net in connector.PINS.items():
        if n in skip:
            continue
        at = beside(SHORT[net], connector.pin_xy(n), 'above' if n % 2 else 'below', size)
        out.append((SHORT[net], at, sides, size, 90, 'y', 0.5))
    x, y = connector.pin_xy(1)
    out.append(('1', (x - 1.6, y), sides, size, 0, 'x', 0.5))
    return out


def _boxes(board, layer, refs=True):
    """Keep-clear rectangles on one side: copper pads, holes, part bodies (fab outline; courtyard when a
    footprint has none). Silk may run between a body and its courtyard line."""
    cu = pcbnew.F_Cu if layer == pcbnew.F_SilkS else pcbnew.B_Cu
    cy = pcbnew.F_CrtYd if layer == pcbnew.F_SilkS else pcbnew.B_CrtYd
    fab = pcbnew.F_Fab if layer == pcbnew.F_SilkS else pcbnew.B_Fab
    out = []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.IsOnLayer(cu) or p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                out.append(p.GetBoundingBox())
        if fp.GetLayer() == cu:
            body = [g.GetBoundingBox() for g in fp.GraphicalItems()
                    if g.GetLayer() == fab and g.GetClass() != 'PCB_TEXT' and g.GetClass() != 'FP_TEXT']
            if body:
                bb = body[0]
                for g in body[1:]:
                    bb.Merge(g)
                out.append(bb)
            elif fp.GetCourtyard(cy).OutlineCount():
                out.append(fp.GetCourtyard(cy).BBox())
        # the part's own silkscreen: outline, pin-1 marks, reference text
        for g in list(fp.GraphicalItems()) + ([fp.Reference(), fp.Value()] if refs else []):
            if g.GetLayer() == layer and (g.GetClass() not in ('PCB_TEXT', 'FP_TEXT') or g.IsVisible()):
                out.append(g.GetBoundingBox())
    for d in board.GetDrawings():  # board texts already on this side
        if d.GetLayer() == layer:
            out.append(d.GetBoundingBox())
    return out


def _near(bb, boxes, reach):
    """The boxes within `reach` mm of `bb` (the only ones a nearby move can touch)."""
    r = MM(reach)
    return [b for b in boxes if bb.GetLeft() - r < b.GetRight() and b.GetLeft() < bb.GetRight() + r and
            bb.GetTop() - r < b.GetBottom() and b.GetTop() < bb.GetBottom() + r]


def _hit(bb, boxes, margin):
    m = MM(margin)
    return any(bb.GetLeft() - m < b.GetRight() and b.GetLeft() < bb.GetRight() + m and
               bb.GetTop() - m < b.GetBottom() and b.GetTop() < bb.GetBottom() + m for b in boxes)


def place(board, labels, origin, margin=0.1, reach=4.0, step=0.1):
    """Add the labels; returns the ones that found no free spot."""
    edge = board.GetBoardEdgesBoundingBox()
    boxes = {pcbnew.F_SilkS: _boxes(board, pcbnew.F_SilkS, False), pcbnew.B_SilkS: _boxes(board, pcbnew.B_SilkS, False)}
    failed = []
    for texts, (x, y), sides, size, rot, search, *more in labels:
        far = more[0] if more else reach
        texts = [texts] if isinstance(texts, str) else list(texts)  # alternatives, longest first
        steps = [0.0] + [sg * step * k for k in range(1, int(far / step) + 1) for sg in (1, -1)]
        moves = sorted(((dx, dy) for dx in (steps if 'x' in search else [0.0])
                        for dy in (steps if 'y' in search else [0.0])), key=lambda d: d[0] ** 2 + d[1] ** 2)
        for side in sides:
            layer = pcbnew.F_SilkS if side == 'F' else pcbnew.B_SilkS
            if not any(_put(board, text, layer, size, rot, (origin[0] + x, origin[1] + y), moves, edge,
                            boxes[layer], margin) for text in texts):
                failed.append(f'{texts[-1]}@{side}')
    return failed


def _put(board, text, layer, size, rot, at, moves, edge, boxes, margin):
    """Place one text at the first free spot of `moves` around `at` (mm); False if there is none."""
    t = pcbnew.PCB_TEXT(board)
    t.SetText(text)
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
    t.SetTextThickness(MM(STROKE))
    t.SetTextAngleDegrees(rot)
    t.SetMirrored(layer == pcbnew.B_SilkS)
    t.SetPosition(pcbnew.VECTOR2I(MM(at[0]), MM(at[1])))
    near = _near(t.GetBoundingBox(), boxes, max(abs(c) for m in moves for c in m) + margin)
    for dx, dy in moves:
        t.SetPosition(pcbnew.VECTOR2I(MM(at[0] + dx), MM(at[1] + dy)))
        bb = t.GetBoundingBox()
        inside = (bb.GetLeft() > edge.GetLeft() + MM(0.5) and bb.GetRight() < edge.GetRight() - MM(0.5) and
                  bb.GetTop() > edge.GetTop() + MM(0.5) and bb.GetBottom() < edge.GetBottom() - MM(0.5))
        if inside and not _hit(bb, near, margin):
            board.Add(t)
            boxes.append(bb)
            return True
    return False


SMALL_REF = ('R', 'C', 'L', 'D', 'FB', 'RN', 'TP')  # passives and test points: the smallest references


def place_refs(board, size=0.8, small=0.65, margin=0.08, reach=2.5, step=0.1):
    """After the labels: move every visible reference (R1, C5 ...) to the nearest spot beside its part
    that is clear of pads, bodies, silk and the texts placed so far; hide the ones with no room (rather
    than print them over something). Returns the hidden references."""
    hidden = []
    texts = {pcbnew.F_SilkS: [], pcbnew.B_SilkS: []}
    named = set()  # parts a label already names ("U2 CHARGER"): their own reference is not repeated
    for d in board.GetDrawings():
        if d.GetLayer() in texts:
            texts[d.GetLayer()].append(d.GetBoundingBox())
            if d.GetClass() == 'PCB_TEXT':
                named.add(d.GetText().split(' ')[0])
    base = {L: _boxes(board, L, False) for L in texts}
    steps = [0.0] + [sg * step * k for k in range(1, int(reach / step) + 1) for sg in (1, -1)]
    moves = sorted(((dx, dy) for dx in steps for dy in steps), key=lambda d: d[0] ** 2 + d[1] ** 2)
    for fp in sorted(board.GetFootprints(), key=lambda f: f.GetReference()):
        ref = fp.Reference()
        L = ref.GetLayer()
        if L not in texts or not ref.IsVisible():
            continue
        if fp.GetReference() in named:
            ref.SetVisible(False)
            continue
        c = fp.GetPosition()
        bodies = _body(fp)
        done = False
        ref_name = fp.GetReference()
        h0 = small if ref_name.rstrip('0123456789') in SMALL_REF else size
        for h in (h0, 0.6):  # below ~0.6 mm the 0.15 mm stroke no longer reads
            ref.SetTextSize(pcbnew.VECTOR2I(MM(h), MM(h)))
            ref.SetTextThickness(MM(STROKE))
            start = pcbnew.VECTOR2I(c.x, (bodies.GetTop() if bodies else c.y) - MM(h))
            ref.SetPosition(start)
            near = _near(ref.GetBoundingBox(), base[L] + texts[L], reach + margin)
            for dx, dy in moves:
                ref.SetPosition(pcbnew.VECTOR2I(start.x + MM(dx), start.y + MM(dy)))
                bb = ref.GetBoundingBox()
                if not _hit(bb, near, margin):
                    texts[L].append(bb)
                    done = True
                    break
            if done:
                break
        if not done:
            ref.SetVisible(False)
            hidden.append(fp.GetReference())
    return hidden


def _body(fp):
    """Bounding box of the part's fab-layer drawing (its body, and e.g. an inserted card), or None."""
    fab = pcbnew.F_Fab if fp.GetLayer() == pcbnew.F_Cu else pcbnew.B_Fab
    body = [g.GetBoundingBox() for g in fp.GraphicalItems()
            if g.GetLayer() == fab and g.GetClass() not in ('PCB_TEXT', 'FP_TEXT')]
    if not body:
        return None
    bb = body[0]
    for g in body[1:]:
        bb.Merge(g)
    return bb
