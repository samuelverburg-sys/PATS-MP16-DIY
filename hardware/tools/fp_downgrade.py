"""Convert a KiCad 8/9/10 footprint file to the KiCad 7 format (20221018).

Only the constructs used by the footprints in lib/PATS.pretty are handled; anything
unknown that KiCad 7 would reject is dropped. Usage: fp_downgrade.py IN OUT
"""
import sys
from sexpr import parse, dump, Sym, find

DROP = {'uuid', 'generator_version', 'embedded_fonts', 'embedded_files', 'tenting',
        'duplicate_pad_numbers_are_jumpers', 'model', 'unlocked', 'locked', 'teardrops',
        'zone_layer_connections', 'component_classes', 'net_tie_pad_groups'}


def fix_effects(eff):
    out = [Sym('effects')]
    hide = False
    for x in eff[1:]:
        if isinstance(x, list) and x[0] == 'font':
            font = [Sym('font')] + [y for y in x[1:] if not (isinstance(y, list) and y[0] in ('bold', 'italic') and y[1] == 'no')]
            out.append(font)
        elif isinstance(x, list) and x[0] == 'hide':
            hide = x[1] == 'yes'
        else:
            out.append(x)
    return out, hide


def fix_text(node, kind, text):
    out = [Sym('fp_text'), Sym(kind), text]
    hide = False
    for x in node[3 if node[0] == 'property' else 3:]:
        if not isinstance(x, list):
            continue
        if x[0] in DROP:
            continue
        if x[0] == 'hide':
            hide = hide or x[1] == 'yes'
            continue
        if x[0] == 'effects':
            eff, h = fix_effects(x)
            hide = hide or h
            out.append(eff)
            continue
        out.append(x)
    if hide:
        # KiCad 7: bare 'hide' after layer
        idx = next(i for i, y in enumerate(out) if isinstance(y, list) and y[0] == 'layer')
        out.insert(idx + 1, Sym('hide'))
    return out


def fix(node):
    if not isinstance(node, list):
        return node
    out = []
    for x in node:
        if isinstance(x, list) and x and x[0] in DROP:
            continue
        if isinstance(x, list) and x and x[0] in ('remove_unused_layers', 'keep_end_layers') and len(x) == 2:
            if x[1] == 'yes':
                out.append([Sym(x[0])])  # KiCad 7: bare flag means yes
            continue
        if isinstance(x, list) and x and x[0] == 'fill' and len(x) == 2 and x[1] in ('yes', 'no'):
            out.append([Sym('fill'), Sym('solid' if x[1] == 'yes' else 'none')])
            continue
        if isinstance(x, list) and x and x[0] == 'property':
            if x[1] in ('Reference', 'Value'):
                out.append(fix_text(x, x[1].lower(), x[2]))
            continue  # other properties: not needed
        if isinstance(x, list) and x and x[0] == 'fp_text':
            out.append(fix_text(x, str(x[1]), x[2]))
            continue
        if isinstance(x, list) and x and x[0] == 'effects':
            out.append(fix_effects(x)[0])
            continue
        out.append(fix(x))
    return out


def main(src, dst):
    fp = parse(open(src).read())
    fp = fix(fp)
    for i, x in enumerate(fp):
        if isinstance(x, list) and x[0] == 'version':
            fp[i] = [Sym('version'), Sym('20221018')]
        if isinstance(x, list) and x[0] == 'generator':
            fp[i] = [Sym('generator'), Sym('pcbnew')]
    open(dst, 'w').write(dump(fp) + '\n')


if __name__ == '__main__':
    main(*sys.argv[1:3])
