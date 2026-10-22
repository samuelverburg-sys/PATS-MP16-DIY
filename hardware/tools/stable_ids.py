"""Deterministic item IDs in a .kicad_pcb: the same design gives a byte-identical board.

pcbnew gives every item a random UUID and saves footprints in UUID order, so each freshly generated
board listed its parts in a different order; Freerouting, which gets them in that order, then returned
a different routing for the same design. Here every UUID in a top-level item is replaced by one derived
from that item's content (UUIDs removed), so a load and save in pcbnew puts them in a fixed order.
"""
import re
import uuid

NS = uuid.UUID('5d0c7c0e-6a49-4a1b-9e0b-2f1f6f0a7a11')
ID = re.compile(r'\((tstamp|uuid) [0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\)')


def stabilize(path):
    """Rewrite `path` in place with content-derived UUIDs; returns how many were replaced."""
    lines = open(path).read().split('\n')
    starts = [i for i, line in enumerate(lines) if line.startswith('  (')]  # top-level items
    ends = starts[1:] + [max(i for i, line in enumerate(lines) if line.strip() == ')')]
    seen, n = {}, 0
    for a, b in zip(starts, ends):
        body = '\n'.join(lines[a:b])
        key = ID.sub('', body)
        dup = seen.get(key, 0)
        seen[key] = dup + 1
        count = [0]

        def sub(m):
            count[0] += 1
            return f'({m.group(1)} {uuid.uuid5(NS, f"{key}|{dup}|{count[0]}")})'
        lines[a:b] = ID.sub(sub, body).split('\n')  # same number of lines
        n += count[0]
    open(path, 'w').write('\n'.join(lines))
    return n


def stabilize_board(path):
    """stabilize(), then load and save once in pcbnew so it orders the items by their new IDs."""
    import pcbnew
    n = stabilize(path)
    board = pcbnew.LoadBoard(path)
    pcbnew.SaveBoard(path, board)
    stabilize(path)  # pcbnew may add IDs of its own on save (e.g. for the board itself)
    return n
