"""Import a Freerouting/Specctra session (.ses) into a pcbnew BOARD (KiCad 7's own importer
needs the GUI's current board). Handles wires (paths) and through vias, which is all
Freerouting writes for a 2-layer board."""
import re
import pcbnew

MIN_WIDTH_NM = 150000  # default: 0.15 mm, the board's minimum track width (JLCPCB allows 0.127 mm)
from sexpr import parse, find, first


def import_ses(board, path, min_width_nm=MIN_WIDTH_NM):
    ses = parse(open(path).read())
    routes = first(ses, 'routes')
    res = first(routes, 'resolution')
    scale = {'um': 1000, 'mm': 1000000, 'mil': 25400}[str(res[1])] / float(res[2])  # nm per SES unit
    pt = lambda x, y: pcbnew.VECTOR2I(int(round(float(x) * scale)), int(round(-float(y) * scale)))
    layers = {'F.Cu': pcbnew.F_Cu, 'B.Cu': pcbnew.B_Cu}
    nets = board.GetNetsByName()
    n_tracks = n_vias = 0
    for net in find(first(routes, 'network_out'), 'net'):
        ni = nets[net[1]] if net[1] in nets else None
        if ni is None:
            raise KeyError(f'net {net[1]} not on board')
        for wire in find(net, 'wire'):
            p = first(wire, 'path')
            layer, width, coords = layers[str(p[1])], float(p[2]) * scale, p[3:]
            pts = [pt(coords[i], coords[i + 1]) for i in range(0, len(coords), 2)]
            for a, b in zip(pts, pts[1:]):
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(a)
                t.SetEnd(b)
                t.SetWidth(int(max(width, min_width_nm)))  # router neck-downs below the board minimum
                t.SetLayer(layer)
                t.SetNet(ni)
                board.Add(t)
                n_tracks += 1
        for via in find(net, 'via'):
            m = re.search(r'_(\d+):(\d+)_um', via[1])
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pt(via[2], via[3]))
            v.SetWidth(int(m.group(1)) * 1000)
            v.SetDrill(int(m.group(2)) * 1000)
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            v.SetNet(ni)
            board.Add(v)
            n_vias += 1
    return n_tracks, n_vias
