"""Load symbols from KiCad symbol libraries, flatten 'extends', list pins."""
import copy
import os
from sexpr import parse, Sym, find, first

SYM_DIRS = [os.environ.get('KICAD_SYMBOL_DIR', '/usr/share/kicad/symbols')]
_cache = {}


def _lib(name):
    if name not in _cache:
        for d in SYM_DIRS:
            p = os.path.join(d, name + '.kicad_sym')
            if os.path.exists(p):
                _cache[name] = parse(open(p).read())
                break
        else:
            raise FileNotFoundError(name)
    return _cache[name]


def _raw(lib, name):
    for s in find(_lib(lib), 'symbol'):
        if s[1] == name:
            return s
    raise KeyError(f'{lib}:{name}')


def load(lib_id):
    """Return a flattened symbol definition named 'lib:name' (as used in lib_symbols)."""
    lib, name = lib_id.split(':')
    s = copy.deepcopy(_raw(lib, name))
    ext = first(s, 'extends')
    if ext:
        parent = copy.deepcopy(_raw(lib, ext[1]))
        props = {p[1]: p for p in find(s, 'property')}
        out = [Sym('symbol'), lib_id]
        for x in parent[2:]:
            if isinstance(x, list) and x[0] == 'property' and x[1] in props:
                out.append(props.pop(x[1]))
            elif isinstance(x, list) and x[0] == 'symbol':
                out.append([Sym('symbol'), x[1].replace(ext[1], name, 1)] + x[2:])
            else:
                out.append(x)
        out[2:2] = []  # keep order
        out += list(props.values())
        s = out
    else:
        s[1] = lib_id
    return s


def pins(sym):
    """[(number, name, x, y, type)] in symbol coordinates (y up), all units merged."""
    out = []
    for unit in find(sym, 'symbol'):
        for p in find(unit, 'pin'):
            at = first(p, 'at')
            out.append((first(p, 'number')[1], first(p, 'name')[1], float(at[1]), float(at[2]), str(p[1])))
    return out
