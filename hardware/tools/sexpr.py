"""Minimal S-expression reader/writer for KiCad files (no dependencies)."""
import re

_TOKEN = re.compile(r'\s*(?:(\()|(\))|("(?:[^"\\]|\\.)*")|([^\s()"]+))')


class Sym(str):
    """An unquoted atom (keyword or number), as opposed to a quoted string."""


def parse(text):
    stack, cur = [], []
    pos = 0
    while True:
        m = _TOKEN.match(text, pos)
        if not m or m.end() == pos:
            break
        pos = m.end()
        op, cl, s, atom = m.groups()
        if op:
            stack.append(cur)
            cur = []
        elif cl:
            done, cur = cur, stack.pop()
            cur.append(done)
        elif s is not None:
            cur.append(bytes(s[1:-1], 'utf-8').decode('unicode_escape') if '\\' in s else s[1:-1])
        else:
            cur.append(Sym(atom))
    assert not stack, 'unbalanced parentheses'
    return cur[0]


def quote(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'


def dump(node, indent=0):
    if isinstance(node, list):
        if not node:
            return '()'
        simple = all(not isinstance(x, list) for x in node)
        if simple:
            return '(' + ' '.join(dump(x) for x in node) + ')'
        pad = '\t' * (indent + 1)
        head = []
        rest = list(node)
        while rest and not isinstance(rest[0], list):
            head.append(dump(rest.pop(0)))
        return '(' + ' '.join(head) + ''.join('\n' + pad + dump(x, indent + 1) for x in rest) + '\n' + '\t' * indent + ')'
    if isinstance(node, Sym):
        return str(node)
    if isinstance(node, (int, float)):
        return fmt_num(node)
    return quote(node)


def fmt_num(v):
    if isinstance(v, int):
        return str(v)
    s = f'{v:.6f}'.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


def find(node, key):
    return [x for x in node if isinstance(x, list) and x and x[0] == key]


def first(node, key):
    r = find(node, key)
    return r[0] if r else None
