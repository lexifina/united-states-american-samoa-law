"""Goal tracker for lexifina/global-law: a snapshot every 20 minutes of how much law we hold, how fast it grows,
what it costs in requests, and whether the repo still works; plus the steps taken between snapshots.

  python goal_tracker.py              take a snapshot and re-render the page
  python goal_tracker.py step "text" [--by who] [--expect "..."]   log a step taken (shown on the next snapshot)

Writes goal-snapshots.jsonl and goal-steps.jsonl here, and ~/Documents/html-reports/global-law-goal.html.
"""
import datetime as dt
import html
import json
import random
import subprocess
import sys
import urllib.request
from pathlib import Path

import speedwatch as sw

HOME = Path(__file__).resolve().parent
SNAPS = HOME / 'goal-snapshots.jsonl'
STEPS = HOME / 'goal-steps.jsonl'
OUT = Path.home() / 'Documents' / 'html-reports' / 'global-law-goal.html'
WINDOW = dt.timedelta(minutes=20)


def now():
    return dt.datetime.now(dt.timezone.utc)


def jl(path):
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding='utf-8').splitlines():
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out


def api(tok, path):
    req = urllib.request.Request(f'https://api.github.com/{path}',
                                 headers={'Authorization': f'Bearer {tok}', 'Accept': 'application/vnd.github+json'})
    return json.load(urllib.request.urlopen(req, timeout=60))


def data_held(t):
    """Census of every lexifina/*-law repo (fresh each snapshot): size and how many hold real law."""
    cov = sw.coverage_census(t, every_h=0.3)
    files = sorted(sw.CENSUS_DIR.glob('census-*.tsv'))
    sizes = [int(l.split('\t')[0]) for l in files[-1].read_text(encoding='utf-8').splitlines() if l.strip()] if files else []
    cov['data_mb'] = round(sum(sizes) / 1024)
    cov['with_law'] = cov.get('small', 0) + cov.get('substantial', 0)
    return cov


def commits(t, since):
    hist = [r for r in jl(sw.HISTORY) if sw.parse(r['at']) > since]
    latest = json.loads(sw.LATEST.read_text(encoding='utf-8')) if sw.LATEST.exists() else {}
    span = max((t - since).total_seconds() / 3600, 1 / 60)
    added = sum(r.get('commits_added') or 0 for r in hist)
    eff = (latest.get('effect') or {})
    return {'total': latest.get('total_commits'), 'added': added, 'per_hour': round(added / span),
            'cpu5': latest.get('cpu5'), 'law_cpu_share': eff.get('law_share'),
            'gl_pushes': sum(r.get('gl_pushes') or 0 for r in hist)}


def requests_made(since):
    """Requests through the shared fetch scheduler since `since` (lanes that use it), with cache hits and errors."""
    gets = cached = errs = stops = 0
    by_session, nbytes = {}, 0
    for day in {since.strftime('%Y-%m-%d'), now().strftime('%Y-%m-%d')}:
        f = sw.FEED / f'{day}.jsonl'
        if not f.exists():
            continue
        for line in f.read_text(encoding='utf-8', errors='replace').splitlines():
            try:
                ev = json.loads(line)
                if sw.parse(ev['at']) < since:
                    continue
            except Exception:
                continue
            e, st = ev.get('event', ''), ev.get('status')
            if e == 'get':
                gets += 1
                nbytes += ev.get('bytes') or 0
                s = ev.get('session') or '?'
                by_session[s] = by_session.get(s, 0) + 1
            if e in ('cache', 'hit') or st == 304:
                cached += 1
            if isinstance(st, int) and st >= 400:
                errs += 1
            if e in ('stop', 'stopped', 'challenge'):
                stops += 1
    served = gets + cached
    return {'gets': gets, 'cached': cached, 'cache_share': round(100 * cached / served) if served else 0,
            'errors': errs, 'error_share': round(100 * errs / gets) if gets else 0, 'stops': stops,
            'mb': round(nbytes / 1e6), 'by_session': by_session}


def health(tok):
    """Does global-law still work? Remote main = the pointer loop's tip, gitlinks count, and 6 random pointers
    resolve to real commits in their repos."""
    g = lambda *a: subprocess.run(['git', *a], cwd=sw.GL, capture_output=True, text=True, encoding='utf-8').stdout
    # the pointer loop commits with commit-tree and pushes; origin/main is its view of the published tip
    local = g('rev-parse', 'origin/main').strip()
    remote = (g('ls-remote', 'origin', 'refs/heads/main').split() or [''])[0]
    links = [l.split(None, 3) for l in g('ls-tree', '-r', local).splitlines() if l.startswith('160000')]
    gm = HOME / '.gitmodules-snapshot'
    gm.write_text(g('cat-file', '-p', f'{local}:.gitmodules'), encoding='utf-8')
    urls = {}
    for line in subprocess.run(['git', 'config', '-f', str(gm), '--get-regexp', r'submodule\..*\.(path|url)'],
                               capture_output=True, text=True, encoding='utf-8').stdout.splitlines():
        k, v = line.split(' ', 1)
        name = k[len('submodule.'):].rsplit('.', 1)[0]
        urls.setdefault(name, {})[k.rsplit('.', 1)[1]] = v
    path_to_repo = {d['path']: d['url'].rstrip('/').removesuffix('.git').rsplit('/', 1)[-1]
                    for d in urls.values() if 'path' in d and 'url' in d}
    sample, ok, bad = random.sample(links, min(6, len(links))), 0, []
    for _, _, sha, path in sample:
        repo = path_to_repo.get(path)
        try:
            api(tok, f'repos/lexifina/{repo}/commits/{sha}')
            ok += 1
        except Exception:
            bad.append(path)
    loop_age = (now() - dt.datetime.fromtimestamp((HOME / 'repoint_loop.log').stat().st_mtime, dt.timezone.utc)).total_seconds() / 60
    # the loop may have pushed since its last fetch: then the remote is ahead, which is fine
    ahead = subprocess.run(['git', 'merge-base', '--is-ancestor', local, remote], cwd=sw.GL).returncode in (0, 128)
    checks = {'pushed': bool(remote) and (remote == local or ahead), 'pointers_resolve': not bad, 'loop_fresh': loop_age < 20}
    return {'ok': all(checks.values()), **checks, 'gitlinks': len(links), 'sampled': len(sample),
            'unresolved': bad, 'loop_age_min': round(loop_age), 'tip': remote[:9]}


def snapshot():
    t = now()
    snaps = jl(SNAPS)
    since = sw.parse(snaps[-1]['at']) if snaps else t - WINDOW
    tok = sw.token()
    snap = {'at': sw.iso(t), 'held': data_held(t), 'commits': commits(t, since), 'requests': requests_made(since),
            'health': health(tok),
            'steps': [s for s in jl(STEPS) if sw.parse(s['at']) > since]}
    with SNAPS.open('a', encoding='utf-8') as f:
        f.write(json.dumps(snap) + '\n')
    render(jl(SNAPS))
    return snap


# ---------- page ----------

SERIES = [  # (label, getter, unit, higher_is_better)
    ('Law repos holding law', lambda s: s['held'].get('with_law'), '', True),
    ('Law data held', lambda s: s['held'].get('data_mb'), ' MB', True),
    ('Law commits, all repos', lambda s: s['commits'].get('total'), '', True),
    ('Commits per hour', lambda s: s['commits'].get('per_hour'), '/h', True),
    ('Requests per snapshot', lambda s: s['requests'].get('gets'), '', None),
    ('Cache and 304 share', lambda s: s['requests'].get('cache_share'), '%', True),
    ('CPU spent on law work', lambda s: s['commits'].get('law_cpu_share'), '%', True),
    ('Nearly empty repos', lambda s: s['held'].get('empty'), '', False),
]


def fmt(v, unit=''):
    if v is None:
        return '–'
    return f'{v:,}{unit}' if isinstance(v, int) else f'{v}{unit}'


def spark(snaps, get, unit):
    pts = [(i, get(s)) for i, s in enumerate(snaps) if isinstance(get(s), (int, float))]
    W, H, P = 320, 120, 14
    if len(pts) < 2:
        return f'<svg viewBox="0 0 {W} {H}" class="chart" role="img"><text x="{P}" y="{H/2}" class="muted">a line appears after the second snapshot</text></svg>'
    ys = [v for _, v in pts]
    lo, hi = min(ys), max(ys)
    hi = hi if hi > lo else lo + 1
    n = max(len(snaps) - 1, 1)
    X = lambda i: P + (W - 2 * P) * i / n
    Y = lambda v: H - P - (H - 2 * P) * (v - lo) / (hi - lo)
    d = ' '.join(f'{"M" if k == 0 else "L"}{X(i):.1f},{Y(v):.1f}' for k, (i, v) in enumerate(pts))
    dots = ''.join(f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="4" class="pt"><title>{html.escape(snaps[i]["at"][11:16])}Z: {fmt(v, unit)}</title></circle>'
                   for i, v in pts)
    return (f'<svg viewBox="0 0 {W} {H}" class="chart" role="img">'
            f'<line x1="{P}" y1="{H-P}" x2="{W-P}" y2="{H-P}" class="axis"/>'
            f'<text x="{P}" y="{P-3}" class="muted">{fmt(hi if isinstance(hi, int) else round(hi), unit)}</text>'
            f'<text x="{P}" y="{H-2}" class="muted">{fmt(lo, unit)}</text>'
            f'<path d="{d}" class="line"/>{dots}</svg>')


def growth_table(top=20):
    """Which repos grew most since the first census: where the coverage is coming from."""
    files = sorted(sw.CENSUS_DIR.glob('census-*.tsv'))
    if len(files) < 2:
        return ''
    read = lambda f: {l.split('\t')[3]: int(l.split('\t')[0]) for l in f.read_text(encoding='utf-8').splitlines() if l.count('\t') >= 3}
    a, b = read(files[0]), read(files[-1])
    rows = sorted(((b[k] - a.get(k, 0), a.get(k, 0), b[k], k) for k in b), reverse=True)
    rows = [r for r in rows if r[0] > 0][:top]
    if not rows:
        return ''
    body = ''.join(f"<tr><td>{html.escape(k.removesuffix('-law'))}</td><td>{fmt(round(old / 1024, 1), ' MB')}</td>"
                   f"<td>{fmt(round(new / 1024, 1), ' MB')}</td><td>+{fmt(round(d / 1024, 1), ' MB')}</td></tr>"
                   for d, old, new, k in rows)
    return (f"<h2>Biggest gains since {files[0].stem[7:]} UTC</h2><p class='muted'>Repo size on GitHub (it lags "
            f"pushes by a few minutes). {sum(1 for k in b if b[k] > a.get(k, 0))} repos grew in all.</p>"
            f"<div class='tablewrap'><table><thead><tr><th>Jurisdiction</th><th>Then</th><th>Now</th><th>Gain</th></tr></thead>"
            f"<tbody>{body}</tbody></table></div>")


def render(snaps):
    last, first = snaps[-1], snaps[0]
    tiles = []
    for label, get, unit, better in SERIES:
        v, v0 = get(last), get(first)
        prev = get(snaps[-2]) if len(snaps) > 1 else None
        delta = ''
        if isinstance(v, (int, float)) and isinstance(v0, (int, float)) and len(snaps) > 1:
            dv = v - v0
            good = None if better is None or dv == 0 else ((dv > 0) == better)
            cls = {True: 'up', False: 'down', None: ''}[good]
            delta = f'<span class="delta {cls}">{"+" if dv >= 0 else ""}{fmt(dv if isinstance(dv, int) else round(dv, 1), unit)} since start</span>'
            if isinstance(prev, (int, float)):
                dp = v - prev
                delta += f'<span class="delta">{"+" if dp >= 0 else ""}{fmt(dp if isinstance(dp, int) else round(dp, 1), unit)} last 20 min</span>'
        tiles.append(f'<section class="tile"><h3>{html.escape(label)}</h3><div class="big">{fmt(v, unit)}</div>{delta}'
                     f'{spark(snaps, get, unit)}</section>')
    h = last['health']
    hp = 'ok' if h.get('ok') else 'bad'
    health_txt = (f"{'Working' if h.get('ok') else 'Problem'}: global-law main {html.escape(h.get('tip', ''))}, "
                  f"{fmt(h.get('gitlinks'))} jurisdictions pinned, {h.get('sampled', 0) - len(h.get('unresolved', []))}/{h.get('sampled', 0)} sampled pointers resolve, "
                  f"pointer loop last ran {h.get('loop_age_min')} min ago, remote {'matches' if h.get('pushed') else 'does NOT match'} the loop's tip.")
    rows = []
    for s in reversed(snaps):
        steps = ''.join(f"<li><b>{html.escape(x.get('by', ''))}</b> {html.escape(x['text'])}"
                        + (f" <span class='muted'>Expect: {html.escape(x['expect'])}</span>" if x.get('expect') else '') + '</li>'
                        for x in s.get('steps', [])) or '<li class="muted">No step logged</li>'
        rows.append(f"<tr><td class='nowrap'>{s['at'][5:10]} {s['at'][11:16]}Z</td>"
                    f"<td>{fmt(s['held'].get('with_law'))}</td><td>{fmt(s['held'].get('data_mb'), ' MB')}</td>"
                    f"<td>{fmt(s['commits'].get('total'))}</td><td>{fmt(s['commits'].get('per_hour'))}</td>"
                    f"<td>{fmt(s['requests'].get('gets'))} <span class='muted'>({s['requests'].get('cache_share', 0)}% cached, {s['requests'].get('error_share', 0)}% errors)</span></td>"
                    f"<td>{'✓' if s['health'].get('ok') else '✗ ' + ', '.join(k for k in ('pushed', 'pointers_resolve', 'loop_fresh') if not s['health'].get(k))}</td>"
                    f"<td><ul>{steps}</ul></td></tr>")
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="300"><title>Global law goal</title><style>
:root{{--bg:#f5f5f3;--surface:#fcfcfb;--text:#0b0b0b;--text2:#52514e;--border:#e2e1dc;--series:#2a78d6;--good:#008300;--bad:#e34948}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#111110;--surface:#1a1a19;--text:#f0efec;--text2:#c3c2b7;--border:#33322f;--series:#3987e5;--good:#3fae3f;--bad:#e66767}}}}
:root[data-theme="dark"]{{--bg:#111110;--surface:#1a1a19;--text:#f0efec;--text2:#c3c2b7;--border:#33322f;--series:#3987e5;--good:#3fae3f;--bad:#e66767}}
body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:1180px;margin:0 auto;padding:24px 16px}} h1{{font-size:22px;margin:0 0 4px;font-weight:600}} h2{{font-size:16px;margin:28px 0 10px;font-weight:600}}
h3{{font-size:12px;margin:0;color:var(--text2);font-weight:500}} .muted{{color:var(--text2);font-size:12px;fill:var(--text2)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}}
.tile{{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:12px;min-width:0}}
.big{{font-size:26px;font-weight:600;font-variant-numeric:tabular-nums}} .delta{{display:inline-block;margin-right:8px;font-size:12px;color:var(--text2)}}
.delta.up{{color:var(--good)}} .delta.down{{color:var(--bad)}} .chart{{width:100%;height:auto;margin-top:6px}}
.line{{fill:none;stroke:var(--series);stroke-width:2}} .pt{{fill:var(--series);stroke:var(--surface);stroke-width:2}} .axis{{stroke:var(--border)}}
.health{{padding:10px 12px;border-radius:8px;border:1px solid var(--border);background:var(--surface)}} .health.ok{{border-left:4px solid var(--good)}} .health.bad{{border-left:4px solid var(--bad)}}
.tablewrap{{overflow-x:auto;background:var(--surface);border:1px solid var(--border);border-radius:8px}}
table{{border-collapse:collapse;width:100%;font-size:13px}} th,td{{text-align:left;vertical-align:top;padding:8px 10px;border-bottom:1px solid var(--border)}}
th{{color:var(--text2);font-weight:500;font-size:12px}} td ul{{margin:0;padding-left:16px}} .nowrap{{white-space:nowrap}}
</style></head><body><main>
<h1>Global law: progress to a finished repo</h1>
<p class="muted">A snapshot every 20 minutes, from {first['at'][:16]}Z to {last['at'][:16]}Z ({len(snaps)} snapshots). Green means better since the first snapshot. "Holding law" means a repo over 0.5 MB.</p>
<p class="health {hp}">{html.escape(health_txt)}</p>
<div class="grid">{''.join(tiles)}</div>
{growth_table()}
<h2>Snapshots and the steps taken before each</h2>
<div class="tablewrap"><table><thead><tr><th>Snapshot</th><th>Repos with law</th><th>Data</th><th>Law commits</th><th>Commits/h</th><th>Requests</th><th>Repo works</th><th>Steps taken</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
</main></body></html>"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding='utf-8')


def log_step(text, by='global-law-main-composer', expect=''):
    with STEPS.open('a', encoding='utf-8') as f:
        f.write(json.dumps({'at': sw.iso(now()), 'by': by, 'text': text, 'expect': expect}) + '\n')


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[:1] == ['step']:
        by = a[a.index('--by') + 1] if '--by' in a else 'global-law-main-composer'
        expect = a[a.index('--expect') + 1] if '--expect' in a else ''
        log_step(a[1], by, expect)
    else:
        s = snapshot()
        print(json.dumps({k: s[k] for k in ('at', 'held', 'commits', 'health')})[:600])
