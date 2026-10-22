"""Write <board>/PARTS.md: the BOM from design.py, grouped by part, with where each LCSC number comes from.

  python3 tools/parts_table.py mp16

Sources, most trusted first: the rev-1 board's BOM (ordered and built at JLCPCB), the PATS repository's
checked list (pats-core/hardware/LCSC-CANDIDATES.md), a web check of the LCSC listing (date given),
or unverified (from memory: check it in the JLCPCB BOM preview before ordering).
"""
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE]

REV1 = {'C41430893', 'C9900001298', 'C143790', 'C5248080', 'C17701688', 'C2911519', 'C173752', 'C965860',
        'C406798', 'C85713'}
PATS = {'C14663', 'C1589', 'C45783', 'C23140', 'C25804', 'C29718', 'C80696', 'C12494', 'C15849', 'C1588',
        'C8678', 'C5144883', 'C23162', 'C23186', 'C4177', 'C859051', 'C22843', 'C25803', 'C21189', 'C23242',
        'C7519', 'C54313', 'C2682616', 'C2681320', 'C84817', 'C72443', 'C51118', 'C165948'}
WEB = {'C97521': '2026-10-22', 'C150470': '2026-10-22', 'C20625731': '2026-10-22'}


def source(lcsc):
    if not lcsc:
        return 'none: choose a part'
    if lcsc in REV1:
        return 'rev-1 BOM'
    if lcsc in PATS:
        return 'PATS checked list'
    if lcsc in WEB:
        return f'LCSC listing seen {WEB[lcsc]}'
    return '**unverified**'


def main():
    name = sys.argv[1]
    sys.path.insert(0, os.path.join(HERE, '..', name))
    import design
    groups = collections.OrderedDict()
    for p in design.parts:
        if p.footprint.startswith(('PATS:MountingHole', 'TestPoint:')):
            continue
        fp = p.footprint.split(':')[1]
        key = (p.value, fp, p.lcsc, p.mpn)
        groups.setdefault(key, []).append(p.ref)
    lines = [f'# {design.TITLE}: parts', '',
             f'Generated from `{name}/design.py` by `tools/parts_table.py`; do not edit by hand.',
             'Check every **unverified** LCSC number in the JLCPCB BOM preview (description, value, package) '
             'before ordering.', '',
             '| Qty | References | Value | Footprint | LCSC | Part | Source of the LCSC number |',
             '|---|---|---|---|---|---|---|']
    for (value, fp, lcsc, mpn), refs in groups.items():
        refs = sorted(refs, key=lambda r: (r.rstrip('0123456789'), int(''.join(c for c in r if c.isdigit()) or 0)))
        lines.append(f'| {len(refs)} | {", ".join(refs)} | {value} | {fp} | {lcsc or "-"} | {mpn or ""} | {source(lcsc)} |')
    out = os.path.join(HERE, '..', name, 'PARTS.md')
    open(out, 'w').write('\n'.join(lines) + '\n')
    counts = collections.Counter(source(k[2]).strip('*') for k in groups)
    print(f'wrote {os.path.relpath(out)}: {len(groups)} lines;', dict(counts))


if __name__ == '__main__':
    main()
