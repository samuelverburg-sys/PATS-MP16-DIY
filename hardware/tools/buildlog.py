"""Build log: every route, drc and review run appends one JSON line to hardware/build-log.jsonl
(committed), so build time, settings and results can be compared across runs (build.py <board> log).

A route record carries the settings it ran with, per-stage results and times, and a hash of the board it
saved; drc and review records carry the same hash, which ties them to that routing.
"""
import datetime
import hashlib
import json
import os
import subprocess

LOG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'build-log.jsonl')


def sha(path):
    return hashlib.sha1(open(path, 'rb').read()).hexdigest()[:10]


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def git_rev():
    """Short commit, '+' when the hardware tree has uncommitted changes besides generated files."""
    try:
        here = os.path.dirname(LOG)
        rev = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=here, capture_output=True,
                             text=True).stdout.strip()
        dirty = subprocess.run(['git', 'status', '--porcelain', '--', '*.py', 'lib'], cwd=here,
                               capture_output=True, text=True).stdout.strip()
        return rev + ('+' if dirty else '')
    except OSError:
        return '?'


def settings(design, margin, passes, timeout, jar):
    """The routing settings a run used (design.py values, defaults filled in)."""
    stages = []
    for name, classes, *extra in (getattr(design, 'ROUTE_STAGES', None) or [('all', None)]):
        s = {'name': name, 'classes': classes or []}
        if extra and extra[0]:
            s['nets'] = list(extra[0])
        if len(extra) > 1:
            s['skip'] = list(extra[1])
        stages.append(s)
    return {
        'stages': stages,
        'promote': getattr(design, 'ROUTE_PROMOTE', 2),
        'margins': getattr(design, 'ROUTE_MARGINS', None),
        'clearance_margin': margin,
        'edge_inset': getattr(design, 'ROUTE_EDGE_INSET', True),
        'escape': getattr(design, 'ESCAPE', None),
        'gnd_fanout': getattr(design, 'GND_FANOUT', False),
        'gnd_fanout_via': getattr(design, 'GND_FANOUT_VIA', {}),
        'solid_ground_below': getattr(design, 'SOLID_GROUND_BELOW', []),
        'gnd_stitch': getattr(design, 'GND_STITCH', 0),
        'clearance': getattr(design, 'CLEARANCE', 0.2),
        'min_track': getattr(design, 'MIN_TRACK', 0.15),
        'netclasses': {c: w for c, (w, _) in getattr(design, 'NETCLASSES', {}).items()},
        'passes': passes,
        'timeout': timeout,
        'router': os.path.basename(jar),
        'optimizer': False,
    }


def append(rec):
    with open(LOG, 'a') as f:
        f.write(json.dumps(rec, sort_keys=True) + '\n')


def records(board=None):
    if not os.path.exists(LOG):
        return []
    out = [json.loads(line) for line in open(LOG) if line.strip()]
    return [r for r in out if board is None or r.get('board') == board]


def table(board, last=15):
    """Route runs of `board`, newest last, with the DRC and review results of the board each one saved."""
    recs = records(board)
    checks = {}
    for r in recs:
        if r['type'] in ('drc', 'review') and r.get('pcb'):
            checks.setdefault(r['pcb'], {})[r['type']] = r
    routes = [r for r in recs if r['type'] == 'route'][-last:]
    if not routes:
        print(f'log: no route runs of {board} yet ({os.path.relpath(LOG)})')
        return
    print(f'{"when (UTC)":17} {"commit":9} {"time":>6}  {"stages (open nets after each)":44} {"unrouted":>8}  drc / review')
    for r in routes:
        st = ' '.join(f'{s["name"]}:{len(s["open"]) or "ok"}' for s in r.get('stages', [])) or '-'
        c = checks.get(r.get('pcb'), {})
        d = c.get('drc')
        rv = c.get('review')
        res = (f'{d["errors"]} err, {d["unconnected"]} unc' if d else 'no drc') + \
              (f' / {rv["far"]} far, {rv["thin"]} thin' if rv else '')
        status = '' if r.get('ok') else ' FAILED'
        print(f'{r["time"][:16]:17} {r.get("commit", "?"):9} {r.get("s", 0) / 60:5.1f}m  {st[:44]:44} '
              f'{str(r.get("unrouted", "-")):>8}  {res}{status}')
