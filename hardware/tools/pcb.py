"""Build <board>.kicad_pcb from <board>/design.py with the pcbnew API (KiCad 7)."""
import pcbnew

ORIGIN = (40.0, 30.0)  # layout frame (0,0) on the KiCad sheet, mm
MM = pcbnew.FromMM


def P(x, y):
    return pcbnew.VECTOR2I(MM(ORIGIN[0] + x), MM(ORIGIN[1] + y))


def pad_center(fp):
    xs, ys = [], []
    for pad in fp.Pads():
        b = pad.GetBoundingBox()
        xs += [b.GetLeft(), b.GetRight()]
        ys += [b.GetTop(), b.GetBottom()]
    return pcbnew.VECTOR2I((min(xs) + max(xs)) // 2, (min(ys) + max(ys)) // 2)


def place_on_targets(fp, p, base):
    """Find the rotation and position that put every listed pad on its target (top view)."""
    for rot in (0, 90, 180, 270):
        fp.SetOrientationDegrees((base + rot) % 360)
        fp.SetPosition(pcbnew.VECTOR2I(0, 0))
        pads = {pad.GetNumber(): pad.GetPosition() for pad in fp.Pads()}
        ref = next(iter(p.pin_targets))
        tx, ty = p.pin_targets[ref]
        off = pcbnew.VECTOR2I(MM(ORIGIN[0] + tx) - pads[ref].x, MM(ORIGIN[1] + ty) - pads[ref].y)
        ok = all(abs(pads[n].x + off.x - MM(ORIGIN[0] + x)) < MM(0.01) and
                 abs(pads[n].y + off.y - MM(ORIGIN[1] + y)) < MM(0.01) for n, (x, y) in p.pin_targets.items())
        if ok:
            fp.SetPosition(off)
            return
    raise ValueError(f'{p.ref}: no rotation puts its pads on the connector targets')


def build(design, fp_path, path):
    board = pcbnew.CreateEmptyBoard()
    board.SetCopperLayerCount(2)
    ds = board.GetDesignSettings()
    # JLCPCB standard 2-layer capabilities are finer than this; these leave margin.
    ds.m_TrackMinWidth = MM(getattr(design, 'MIN_TRACK', 0.15))
    ds.m_ViasMinSize = MM(0.6)
    ds.m_MinThroughDrill = MM(0.3)
    ds.m_CopperEdgeClearance = MM(0.3)
    ns = ds.m_NetSettings
    default = ns.m_DefaultNetClass
    default.SetTrackWidth(MM(0.25))
    default.SetClearance(MM(getattr(design, 'CLEARANCE', 0.2)))
    default.SetViaDiameter(MM(0.6))
    default.SetViaDrill(MM(0.3))
    nets = {}
    for p in design.parts:
        for net in list(p.pins.values()) + list(p.extra_pads.values()):
            if net and net not in nets:
                ni = pcbnew.NETINFO_ITEM(board, net)
                board.Add(ni)
                nets[net] = ni

    for p in design.parts:
        lib, name = fp_path(p.footprint)
        fp = pcbnew.FootprintLoad(lib, name)
        fp.SetFPID(pcbnew.LIB_ID(p.footprint.split(':')[0], name))
        fp.SetReference(p.ref)
        fp.SetValue(p.value)
        if p.mpn:
            fp.SetProperty('MPN', p.mpn)
        fp.SetPosition(pcbnew.VECTOR2I(0, 0))
        board.Add(fp)  # must belong to a board before Flip()
        if p.side == 'B':
            fp.Flip(pcbnew.VECTOR2I(0, 0), True)
        base = fp.GetOrientationDegrees()  # Flip() leaves 180 deg for a bottom-side part
        if p.pin_targets:
            place_on_targets(fp, p, base)
        else:
            fp.SetOrientationDegrees((base + p.rot) % 360)
            target = P(*p.at)
            if p.anchor == 'center':
                c = pad_center(fp)
                target = pcbnew.VECTOR2I(target.x - c.x, target.y - c.y)
            fp.SetPosition(target)
        attrs = fp.GetAttributes()
        if p.dnp or p.ref.startswith('H'):
            attrs |= pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES
        fp.SetAttributes(attrs)
        for pad in fp.Pads():
            net = p.pins.get(pad.GetNumber()) or p.extra_pads.get(pad.GetNumber())
            if net:
                pad.SetNet(nets[net])

    # Outline
    x0, y0, x1, y1 = design.BOARD
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    for a, b in zip(corners, corners[1:] + corners[:1]):
        seg = pcbnew.PCB_SHAPE(board)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetStart(P(*a))
        seg.SetEnd(P(*b))
        seg.SetLayer(pcbnew.Edge_Cuts)
        seg.SetWidth(MM(0.1))
        board.Add(seg)

    # Ground pour on both layers (filled after routing).
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(board)
        ls = pcbnew.LSET()
        ls.AddLayer(layer)
        z.SetLayerSet(ls)  # KiCad 7: SetLayer() alone does not move a zone off F.Cu
        z.SetNetCode(nets['GND'].GetNetCode())
        z.SetLocalClearance(MM(0.3))
        z.SetMinThickness(MM(0.25))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)  # solid: no starved thermal spokes
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)  # drop unconnected pour fragments
        z.SetThermalReliefGap(MM(0.3))
        z.SetThermalReliefSpokeWidth(MM(0.4))
        ol = z.Outline()
        ol.NewOutline()
        for c in corners:
            ol.Append(P(*c))
        board.Add(z)

    # Keep tracks and vias away from the LED cut-outs (cut-out +-1.88 x +-1.68 mm, plus 0.35 mm).
    for p in design.parts:
        if 'SK6812MINI-E' in p.footprint:
            x, y = p.at
            k = pcbnew.ZONE(board)
            k.SetIsRuleArea(True)
            k.SetDoNotAllowTracks(True)
            k.SetDoNotAllowVias(True)
            k.SetDoNotAllowCopperPour(False)
            k.SetDoNotAllowPads(False)
            k.SetDoNotAllowFootprints(False)
            ls = pcbnew.LSET()
            ls.AddLayer(pcbnew.F_Cu)
            ls.AddLayer(pcbnew.B_Cu)
            k.SetLayerSet(ls)
            ol = k.Outline()
            ol.NewOutline()
            for dx, dy in ((-2.23, -2.03), (2.23, -2.03), (2.23, 2.03), (-2.23, 2.03)):
                ol.Append(P(x + dx, y + dy))
            board.Add(k)

    # No ground pour over fine-pitch parts (design.POUR_KEEPOUT): the pour would leave slivers between
    # their pins that touch a pad only at its edge. Their ground pins reach ground through tracks.
    for ref in getattr(design, 'POUR_KEEPOUT', []):
        fp = board.FindFootprintByReference(ref)
        bb = fp.GetCourtyard(pcbnew.F_CrtYd if fp.GetLayer() == pcbnew.F_Cu else pcbnew.B_CrtYd).BBox()
        k = pcbnew.ZONE(board)
        k.SetIsRuleArea(True)
        k.SetDoNotAllowCopperPour(True)
        k.SetDoNotAllowTracks(False)
        k.SetDoNotAllowVias(False)
        k.SetDoNotAllowPads(False)
        k.SetDoNotAllowFootprints(False)
        ls = pcbnew.LSET()
        ls.AddLayer(fp.GetLayer())
        k.SetLayerSet(ls)
        ol = k.Outline()
        ol.NewOutline()
        for x, y in ((bb.GetLeft(), bb.GetTop()), (bb.GetRight(), bb.GetTop()), (bb.GetRight(), bb.GetBottom()),
                     (bb.GetLeft(), bb.GetBottom())):
            ol.Append(pcbnew.VECTOR2I(x, y))
        board.Add(k)

    # Solid ground under noise-sensitive parts (design.SOLID_GROUND_BELOW): no tracks on the opposite layer
    # under the part's courtyard (vias and pour allowed), so the plane there stays whole and joined to
    # the rest; routed tracks underneath had cut off the patch the codec's ground vias land in.
    for ref in getattr(design, 'SOLID_GROUND_BELOW', []):
        fp = board.FindFootprintByReference(ref)
        bb = fp.GetCourtyard(pcbnew.F_CrtYd if fp.GetLayer() == pcbnew.F_Cu else pcbnew.B_CrtYd).BBox()
        k = pcbnew.ZONE(board)
        k.SetIsRuleArea(True)
        k.SetDoNotAllowCopperPour(False)
        k.SetDoNotAllowTracks(True)
        k.SetDoNotAllowVias(False)
        k.SetDoNotAllowPads(False)
        k.SetDoNotAllowFootprints(False)
        ls = pcbnew.LSET()
        ls.AddLayer(pcbnew.B_Cu if fp.GetLayer() == pcbnew.F_Cu else pcbnew.F_Cu)
        k.SetLayerSet(ls)
        ol = k.Outline()
        ol.NewOutline()
        for x, y in ((bb.GetLeft(), bb.GetTop()), (bb.GetRight(), bb.GetTop()), (bb.GetRight(), bb.GetBottom()),
                     (bb.GetLeft(), bb.GetBottom())):
            ol.Append(pcbnew.VECTOR2I(x, y))
        board.Add(k)

    # Silkscreen notes
    for text, (x, y), side, size in getattr(design, 'SILK', []):
        layer = pcbnew.F_SilkS if side == 'F' else pcbnew.B_SilkS
        t = pcbnew.PCB_TEXT(board)
        t.SetText(text)
        t.SetPosition(P(x, y))
        t.SetLayer(layer)
        t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
        t.SetTextThickness(MM(size * 0.15))
        if layer == pcbnew.B_SilkS:
            t.SetMirrored(True)
        board.Add(t)

    # Labels placed clear of pads, holes, part outlines and each other (tools/silk.py)
    import silk
    failed = silk.place(board, getattr(design, 'LABELS', []), ORIGIN)
    for ref in getattr(design, 'HIDE_REFS', []):  # parts a label names in words ("RESET"): no reference
        board.FindFootprintByReference(ref).Reference().SetVisible(False)
    hidden = silk.place_refs(board)
    print(f'silk: {len(getattr(design, "LABELS", []))} labels' + (f'; no free spot for {", ".join(failed)}' if failed else '')
          + f'; {len(hidden)} references hidden for lack of room' + (f' ({", ".join(hidden)})' if hidden else ''))

    pcbnew.SaveBoard(path, board)
    return board
