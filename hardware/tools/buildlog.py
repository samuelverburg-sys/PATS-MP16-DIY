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
        'layers': getattr(design, 'LAYERS', 2),
        'preroute': {'mm': getattr(design, 'PREROUTE_MM', 0), 'first': [e if isinstance(e, str) else f'{e[0]}:{e[1]}' for e in getattr(design, 'PREROUTE_FIRST', ())],
                     'first_mm': getattr(design, 'PREROUTE_FIRST_MM', None)},
        'parallel': int(os.environ.get('ROUTE_PARALLEL', getattr(design, 'ROUTE_PARALLEL', 0))),
        # the board's own experiment switches (MP-16: which side the RP2040's parts are on, ...)
        'design_vars': dict(getattr(design, 'ROUTE_LOG_VARS', {})),
    }


def append(rec):
    with open(LOG, 'a') as f:
        f.write(json.dumps(rec, sort_keys=True) + '\n')


def records(board=None):
    if not os.path.exists(LOG):
        return []
    out = [json.loads(line) for line in open(LOG) if line.strip()]
    return [r for r in out if board is None or r.get('board') == board]


def _flat(d, pre=''):
    out = {}
    for k, v in (d or {}).items():
        if isinstance(v, dict) and k != 'netclasses':
            out.update(_flat(v, f'{pre}{k}.'))
        else:
            out[pre + k] = v
    return out


def changed(prev, cur):
    """Settings that differ between two route records, as 'key=value' (the new value)."""
    a, b = _flat(prev.get('settings')), _flat(cur.get('settings'))
    out = []
    for k in sorted(set(a) | set(b)):
        if a.get(k) != b.get(k):
            v = b.get(k)
            out.append(f'{k}={",".join(map(str, v)) if isinstance(v, list) else v}')
    if prev.get('design') != cur.get('design'):
        out.append('design.py')
    return out


def table(board, last=15, wide=False):
    """Route runs of `board`, newest last: what the run tested (ROUTE_NOTE), what changed since the run before
    it, the pre-route, each Freerouting attempt's open count, what the finish left open, and the DRC of the
    board it saved. `wide`: also the open nets and where their gaps are."""
    recs = records(board)
    checks = {}
    for r in recs:
        if r['type'] in ('drc', 'review') and r.get('pcb'):
            checks.setdefault(r['pcb'], {})[r['type']] = r
    all_routes = [r for r in recs if r['type'] == 'route']
    routes = all_routes[-last:]
    if not routes:
        print(f'log: no route runs of {board} yet ({os.path.relpath(LOG)})')
        return
    print(f'{"when (UTC)":17} {"commit":9} {"time":>6} {"prejoin":>8} {"attempts":>9} {"router":>6} '
          f'{"finish":>6}  drc')
    for r in routes:
        i = all_routes.index(r)
        tries = [t for s in r.get('stages', []) for t in s.get('tries', [])]
        att = '/'.join(str(len(t['open'])) for t in tries) or '-'
        pj = r.get('prejoin') or {}
        pjs = f'{pj.get("joined", "-")}' + (f'-{len(pj["stuck"])}' if pj.get('stuck') else '') if pj else '-'
        after = sum((r.get('open_after_router') or {}).values()) if 'open_after_router' in r else '-'
        fin = 'quick' if r.get('quick') else r.get('unrouted', '-')
        c = checks.get(r.get('pcb'), {})
        d = c.get('drc')
        res = f'{d["errors"]} err, {d["unconnected"]} unc' if d else '-'
        status = ' (stopped)' if r.get('stopped') or ('unrouted' not in r and not r.get('quick')) else ''
        print(f'{r["time"][:16]:17} {r.get("commit", "?"):9} {r.get("s", 0) / 60:5.1f}m {pjs:>8} {att:>9} '
              f'{str(after):>6} {str(fin):>6}  {res}{status}')
        if r.get('note'):
            print(f'    tested: {r["note"]}')
        ch = changed(all_routes[i - 1], r) if i else []
        if ch:
            print(f'    changed: {"; ".join(ch)}'[:400])
        if wide:
            if pj.get('stuck'):
                print(f'    prejoin could not: {", ".join(pj["stuck"])}')
            fin_d = r.get('finish') or {}
            if fin_d.get('failed'):
                print(f'    finish failed: {", ".join(fin_d["failed"])}')
            for n, pieces in sorted((r.get('open_final') or {}).items()):
                ends = '; '.join(' - '.join(f'{e[0]} ({e[1]}, {e[2]})' for e in p) for p in pieces[:2])
                print(f'    open {n}: {ends}')
