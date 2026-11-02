"""Why did the machine-wide fetch rate fall? Read-only analysis of every requests.jsonl under scripts/ and of the
per-host rate state in %TEMP%/gitlaw-host-rate. Writes bench/rate_drop.json and prints a summary.

    python bench/rate_drop.py [--scripts C:/Users/alany/Documents/lexifina/scripts] [--now 2026-10-29T23:10:00Z]

Agent = the scripts/<slug>-law folder. Host = URL host ('cc:' byte ranges count as data.commoncrawl.org; web.archive.org
and arquivo.pt keep their own names). Idle gap = time between two consecutive logged requests of one agent; gaps over
60 s are counted as "idle" (the agent was parsing, thinking or waiting, not fetching).
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import tempfile
import time
from pathlib import Path


def host_of(url: str) -> str:
    if url.startswith('cc:'):
        return 'data.commoncrawl.org'
    return url.split('://', 1)[-1].split('/', 1)[0].lower()


def ts(s: str) -> float | None:
    try:
        return dt.datetime.strptime(s[:19], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=dt.timezone.utc).timestamp()
    except (TypeError, ValueError):
        return None


def load(scripts: Path):
    rows = []
    for f in scripts.rglob('requests.jsonl'):
        rel = f.relative_to(scripts).parts
        agent = rel[0]
        try:
            with open(f, encoding='utf-8', errors='replace') as fh:
                for line in fh:
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    t = ts(r.get('at') or '')
                    if t is None:
                        continue
                    rows.append((t, agent, host_of(r.get('url') or ''), int(r.get('bytes') or 0), str(r.get('status'))))
        except OSError:
            pass
    rows.sort()
    return rows


def window(rows, a, b):
    return [r for r in rows if a <= r[0] < b]


def per(rows, idx, minutes):
    c = collections.Counter(r[idx] for r in rows)
    return [(k, n, round(n / minutes, 1)) for k, n in c.most_common()]


def idle(rows, a, b):
    """Per agent: active minutes (any request), longest gap, total time in gaps > 60 s, inside [a, b)."""
    by = collections.defaultdict(list)
    for r in rows:
        if a <= r[0] < b:
            by[r[1]].append(r[0])
    out = {}
    for ag, tt in by.items():
        gaps = [y - x for x, y in zip(tt, tt[1:])]
        big = [g for g in gaps if g > 60]
        mins = {int(t // 60) for t in tt}
        out[ag] = {'requests': len(tt), 'active_minutes': len(mins), 'first': time.strftime('%H:%M', time.gmtime(tt[0])),
                   'last': time.strftime('%H:%M', time.gmtime(tt[-1])), 'gaps_over_60s': len(big),
                   'idle_s': round(sum(big)), 'longest_gap_s': round(max(gaps)) if gaps else 0}
    return out


def host_state():
    d = Path(tempfile.gettempdir()) / 'gitlaw-host-rate'
    now = time.time()
    out = {}
    for f in d.glob('*.json'):
        try:
            st = json.loads(f.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        out[f.stem] = {'rate': round(st.get('rate', 0), 2), 'ok': st.get('ok'), 'throttled': st.get('throttled'),
                       'paused_s': round(max(0, st.get('pause_until', 0) - now)),
                       'updated_s_ago': round(now - f.stat().st_mtime)}
    wb = Path(tempfile.gettempdir()) / 'gitlaw-wayback-rate.json'
    try:
        st = json.loads(wb.read_text(encoding='utf-8'))
        out['web.archive.org (shared wayback limiter)'] = {'rate': round(st['rate'], 2), 'ok': st['ok'],
                                                          'throttled': st['throttled'],
                                                          'paused_s': round(max(0, st['pause_until'] - now)),
                                                          'updated_s_ago': round(now - wb.stat().st_mtime)}
    except (OSError, ValueError, KeyError):
        pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scripts', default='C:/Users/alany/Documents/lexifina/scripts')
    ap.add_argument('--now', default=None)
    ap.add_argument('--out', default=str(Path(__file__).with_name('rate_drop.json')))
    a = ap.parse_args()
    now = ts(a.now) if a.now else time.time()
    rows = load(Path(a.scripts))
    day0 = now - 14 * 3600
    # 30-minute buckets, machine-wide
    buckets = collections.Counter(int(r[0] // 1800) for r in rows if r[0] >= day0)
    series = [(time.strftime('%H:%M', time.gmtime(k * 1800)), n, round(n / 30, 1)) for k, n in sorted(buckets.items())]
    peak_k = max(buckets, key=buckets.get)
    pa, pb = peak_k * 1800, peak_k * 1800 + 1800
    la, lb = now - 1800, now
    res = {
        'generated_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(now)),
        'requests_total': len(rows),
        'per_30min_machine': series,
        'peak_window': [time.strftime('%H:%M', time.gmtime(pa)), time.strftime('%H:%M', time.gmtime(pb))],
        'peak_per_host': per(window(rows, pa, pb), 2, 30)[:25],
        'peak_per_agent': per(window(rows, pa, pb), 1, 30)[:25],
        'last30_per_host': per(window(rows, la, lb), 2, 30)[:25],
        'last30_per_agent': per(window(rows, la, lb), 1, 30)[:40],
        'last60_idle_per_agent': idle(rows, now - 3600, now),
        'host_state_now': host_state(),
    }
    Path(a.out).write_text(json.dumps(res, indent=1), encoding='utf-8', newline='\n')
    print('per 30 min (machine):', ' '.join(f'{t}={r}/m' for t, n, r in series))
    print('peak', res['peak_window'])
    for k in ('peak_per_host', 'peak_per_agent', 'last30_per_host', 'last30_per_agent'):
        print(f'\n{k}:')
        for name, n, r in res[k][:18]:
            print(f'  {name:48s} {n:6d}  {r:6.1f}/min')


if __name__ == '__main__':
    main()
