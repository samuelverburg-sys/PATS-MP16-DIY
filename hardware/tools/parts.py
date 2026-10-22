"""Part model shared by all PATS board designs (ui/design.py, audio/design.py)."""
from dataclasses import dataclass, field


@dataclass
class Part:
    ref: str
    symbol: str            # KiCad lib id
    footprint: str         # KiCad lib id (PATS:... = hardware/lib/PATS.pretty)
    value: str
    pins: dict             # pin number -> net name; None = intentionally unconnected
    at: tuple = (0.0, 0.0)  # mm, MP-16 layout frame (x right, y down, origin top-left of the board)
    rot: float = 0.0       # degrees, counter-clockwise as in KiCad
    side: str = 'B'        # 'F' top, 'B' bottom
    anchor: str = 'origin'  # 'origin' = footprint origin at `at`; 'center' = pad bbox centre at `at`
    mpn: str = ''
    lcsc: str = ''         # JLCPCB/LCSC part number, where known
    dnp: bool = False
    block: str = ''
    note: str = ''
    extra_pads: dict = field(default_factory=dict)  # footprint-only pads (e.g. MP) -> net
    pin_targets: dict = field(default_factory=dict)  # pin -> (x, y): solve rotation/position to land pads here


class Design:
    def __init__(self, side='B'):
        self.parts = []
        self.side = side  # side for res() and cap()

    def add(self, *args, **kw):
        p = Part(*args, **kw)
        self.parts.append(p)
        return p

    def res(self, ref, value, a, b, at, rot=0, block='', **kw):
        return self.add(ref, 'Device:R', 'Resistor_SMD:R_0603_1608Metric', value, {'1': a, '2': b}, at, rot, self.side,
                        block=block, **kw)

    def cap(self, ref, value, a, b, at, rot=0, block='', big=False, **kw):
        if value == '10u':  # the MP-16 BOM part: Samsung CL10A106MP8NNNC, 0603
            kw.setdefault('mpn', 'CL10A106MP8NNNC')
            kw.setdefault('lcsc', 'C85713')
            big = False
        fp = 'Capacitor_SMD:C_0805_2012Metric' if big else 'Capacitor_SMD:C_0603_1608Metric'
        return self.add(ref, 'Device:C', fp, value, {'1': a, '2': b}, at, rot, self.side, block=block, **kw)


# The six 2.5 mm holes of the MP-16 board; both PATS boards use them.
MP16_HOLES = [(2.0, 2.0), (74.2, 2.0), (2.0, 26.575), (74.2, 26.575), (2.0, 102.775), (74.2, 102.775)]
MP16_OUTLINE = (0.0, 0.0, 76.2, 104.775)
PITCH = 19.05
