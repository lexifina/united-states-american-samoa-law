"""Git for Global Law speed report: measures throughput every run and renders an HTML page with what limits it.

    python -X utf8 speedwatch.py          # one measurement (speedwatch.sh runs it every 5 minutes)

Each run:
- reads the global-law clone the repoint loop keeps fresh (%LOCALAPPDATA%\\gl-repoint) for pushes and submodules;
- diffs every country repo's main tip (from the repoint loop's gl-repoint-tips.json) against the previous run and asks
  GitHub how many commits each changed tip added (compare API; a non-fast-forward is flagged as a rewrite);
- reads both scrapers' autopush logs, REWRITE-PENDING.json, STALLED.txt and the CPU log;
- appends a row to speed-history.jsonl, writes speed-latest.json and renders
  %USERPROFILE%\\Documents\\html-reports\\global-law-speed.html;
- writes an "ADVICE" line to alerts.log when a bottleneck starts (once per bottleneck, not every run).
"""
import datetime as dt
import html
import json
import os
import re
import subprocess
import urllib.request
from pathlib import Path

LAD = Path(os.environ.get('LOCALAPPDATA', str(Path.home())))
HOME = Path(__file__).resolve().parent
GL = LAD / 'gl-repoint'
TIPS = LAD / 'gl-repoint-tips.json'
CPU_LOG = LAD / 'gitlaw-cpu.log'
SCRIPTS = Path.home() / 'Documents' / 'lexifina' / 'scripts'
LOGS = {'hp-omen': SCRIPTS / 'south-america-law' / 'logs' / 'autopush.log',
        'dell': SCRIPTS / 'world-law' / 'logs' / 'autopush_dell.log'}
PENDING = SCRIPTS / 'world-law' / 'REWRITE-PENDING.json'
STALLED = SCRIPTS / 'world-law' / 'logs' / 'STALLED.txt'
HISTORY = HOME / 'speed-history.jsonl'
STATE = HOME / 'speed-state.json'
LATEST = HOME / 'speed-latest.json'
ALERTS = HOME / 'alerts.log'
OUT = Path.home() / 'Documents' / 'html-reports' / 'global-law-speed.html'
CENSUS = LAD / 'gl-commit-census.json'  # full per-repo commit count, the baseline for the running total
MAX_COMPARES = 120  # GitHub API calls per run at most (the quota is shared by every session on the account)


def now():
    return dt.datetime.now(dt.timezone.utc)


def iso(t):
    return t.strftime('%Y-%m-%dT%H:%M:%SZ')


def parse(s):
    return dt.datetime.fromisoformat(s.replace('Z', '+00:00'))


def git(*a):
    return subprocess.run(['git', *a], cwd=GL, capture_output=True, text=True, encoding='utf-8').stdout


def read_text(p):
    """Logs come in UTF-8 or UTF-16 (PowerShell redirection); read either, keeping only the tail."""
    try:
        b = p.read_bytes()[-3_000_000:]
    except OSError:
        return ''
    # A log can hold UTF-16 stretches (PowerShell redirection) between UTF-8 ones; the log text is ASCII, so dropping
    # the NUL bytes reads both.
    return b.replace(b'\xff\xfe', b'').replace(b'\x00', b'').decode('utf-8', 'replace')


def token():
    # gh's keyring token first: `git credential fill` can block forever on a hidden credential-manager prompt
    # (it did after a Claude relaunch on 2026-11-03, stalling every snapshot for 90 min).
    try:
        t = subprocess.run(['gh', 'auth', 'token'], capture_output=True, text=True, timeout=30).stdout.strip()
        if t:
            return t
    except (OSError, subprocess.TimeoutExpired):
        pass
    try:
        out = subprocess.run(['git', 'credential', 'fill'], input='protocol=https\nhost=github.com\n\n',
                             capture_output=True, text=True, timeout=30,
                             env={**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'GCM_INTERACTIVE': 'never'}).stdout
    except subprocess.TimeoutExpired:
        return ''
    return next((l.split('=', 1)[1] for l in out.splitlines() if l.startswith('password=')), '')


def compare(tok, repo, old, new):
    """Commits new adds over old, and whether new is a fast-forward of old."""
    req = urllib.request.Request(f'https://api.github.com/repos/lexifina/{repo}/compare/{old}...{new}',
                                 headers={'Authorization': f'Bearer {tok}', 'Accept': 'application/vnd.github+json'})
    d = json.load(urllib.request.urlopen(req, timeout=60))
    return d.get('ahead_by', 0), d.get('status') in ('ahead', 'identical')


CENSUS_DIR = HOME / 'census'


def coverage_census(t, every_h=6):
    """Size bands of every lexifina/*-law repo, refreshed every 6 h (about 8 API calls); else the last result.
    Coverage, not commits, is the goal: this is how the strategy log measures each wave."""
    CENSUS_DIR.mkdir(exist_ok=True)
    files = sorted(CENSUS_DIR.glob('census-*.tsv'))
    if files and (t - dt.datetime.fromtimestamp(files[-1].stat().st_mtime, dt.timezone.utc)) < dt.timedelta(hours=every_h):
        lines = files[-1].read_text(encoding='utf-8').splitlines()
    else:
        tok, lines, page = token(), [], 1
        try:
            while True:
                req = urllib.request.Request(f'https://api.github.com/orgs/lexifina/repos?per_page=100&type=all&page={page}',
                                             headers={'Authorization': f'Bearer {tok}', 'Accept': 'application/vnd.github+json'})
                batch = json.load(urllib.request.urlopen(req, timeout=60))
                lines += [f"{r['size']}\t{r['private']}\t{(r['pushed_at'] or '')[:16]}\t{r['name']}"
                          for r in batch if r['name'].endswith('-law')]
                if len(batch) < 100:
                    break
                page += 1
        except Exception:
            return {}
        (CENSUS_DIR / f"census-{t.strftime('%Y-%m-%d-%H%M')}.tsv").write_text('\n'.join(lines) + '\n', encoding='utf-8')
    sizes = [int(l.split('\t')[0]) for l in lines if l.strip()]
    return {'repos': len(sizes), 'empty': sum(s < 500 for s in sizes),
            'small': sum(500 <= s < 5000 for s in sizes), 'substantial': sum(s >= 5000 for s in sizes)}


def count_commits(tok, repo):
    req = urllib.request.Request(f'https://api.github.com/repos/lexifina/{repo}/commits?sha=main&per_page=1',
                                 headers={'Authorization': f'Bearer {tok}'})
    r = urllib.request.urlopen(req, timeout=60)
    m = re.search(r'page=(\d+)>; rel="last"', r.headers.get('Link', ''))
    return int(m.group(1)) if m else 1


def cpu_window(since):
    vals = []
    for line in read_text(CPU_LOG).splitlines()[-200:]:
        m = re.search(r'cpu5=(\d+)\s+ram=(\d+)', line)
        if m:
            vals.append((int(m.group(1)), int(m.group(2))))
    recent = vals[-5:] or [(0, 0)]
    return round(sum(v[0] for v in recent) / len(recent)), recent[-1][1]


def scraper_window(name, since):
    """Pushes, holds and loop counts from one autopush log since `since`."""
    text = read_text(LOGS[name])
    passes = [(m.start(), parse(m.group(1)), int(m.group(2))) for m in
              re.finditer(r'--- pass at (\S+Z) \(scheduler: (\d+) country loops alive\)', text)]
    loops = passes[-1][2] if passes else 0
    last_pass = iso(passes[-1][1]) if passes else None
    start = next((pos for pos, t, _ in passes if t >= since), len(text))
    chunk = text[start:]
    pushed = len(re.findall(r'\| pushed \(main', chunk))
    appended = len(re.findall(r'\| pushed \(main append-only', chunk))
    held = len(re.findall(r'NOT pushed|refused|HELD', chunk)) - len(re.findall(r'unchanged since[^\n]*NOT pushed', chunk))
    waiting = len(re.findall(r'waiting for its builder', chunk))
    # real failures only: crashes and failed public pushes. A refused check ("check failed, not pushed") is a hold,
    # and a private wip snapshot that can't fast-forward doesn't affect publishing.
    failed = len(re.findall(r'Traceback|main[^\n|]*push[^\n|]*failed|public[^\n|]*FAILED', chunk))
    return {'loops': loops, 'last_pass': last_pass, 'pushed': pushed, 'appended': appended, 'held': held,
            'waiting': waiting, 'failed': failed}


def cpu_by_lane(seconds=3.0):
    """Which work is using the CPU right now: cores per lane over a short sample, from each process's command line
    (python script or git subcommand), so the report can say where build CPU goes."""
    try:
        import psutil, time
    except Exception:
        return []
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            p.cpu_percent(None)
            procs.append(p)
        except Exception:
            pass
    time.sleep(seconds)
    lanes = {}
    for p in procs:
        try:
            pct = p.cpu_percent(None)
            if pct < 1:
                continue
            name = (p.info['name'] or '').lower()
            cmd = ' '.join(p.info['cmdline'] or [])
            if 'python' in name:
                m = re.search(r'([\w.-]+)\.py\b', cmd.replace('\\', '/').rsplit('/', 1)[-1] if '.py' in cmd else cmd)
                m = re.findall(r'([\w-]+)\.py', cmd.replace('\\', '/'))
                lane = f'python {m[-1] if m else "?"}'
            elif name.startswith('git'):
                sub = next((a for a in (p.info['cmdline'] or [])[1:] if not a.startswith('-')), '?')
                lane = f'git {sub}'
            else:
                lane = name.removesuffix('.exe')
            lanes[lane] = lanes.get(lane, 0) + pct / 100
        except Exception:
            pass
    return sorted(((k, round(v, 2)) for k, v in lanes.items()), key=lambda kv: -kv[1])[:15]


FEED = LAD / 'gitlaw' / 'fetch-scheduler' / 'feed'


def fetch_window(since):
    """Requests through the shared fetch scheduler since `since`: per host, cache hits, stops and errors, from its
    JSONL feed (only lanes that have adopted the scheduler appear here)."""
    hosts, total, stops, errs, cached = {}, 0, set(), 0, 0
    for day in {since.strftime('%Y-%m-%d'), now().strftime('%Y-%m-%d')}:
        f = FEED / f'{day}.jsonl'
        if not f.exists():
            continue
        for line in f.read_text(encoding='utf-8', errors='replace').splitlines():
            try:
                ev = json.loads(line)
                if parse(ev['at']) < since:
                    continue
            except Exception:
                continue
            h = ev.get('host', '?')
            e = ev.get('event', '')
            if e in ('stop', 'stopped', 'challenge'):
                stops.add(h)
            if e in ('cache', 'hit') or ev.get('status') == 304:
                cached += 1
            if isinstance(ev.get('status'), int) and ev['status'] >= 400:
                errs += 1
            if e == 'get':
                total += 1
                hosts[h] = hosts.get(h, 0) + 1
    return {'requests': total, 'hosts': len(hosts), 'cached': cached, 'errors': errs, 'stops': sorted(stops),
            'top_hosts': sorted(hosts.items(), key=lambda kv: -kv[1])[:8]}


OVERHEAD = ('msmpeng', 'searchindexer', 'grep', 'find', 'wmiprvse', 'dllhost', 'tail', 'svchost')
# vmmemwsl is the WSL VM: since 2026-11-03 the builds, checks and pushes of every lane run there, so it counts as law work
LAW_VM = ('vmmemwsl', 'vmmem')


def cpu_effectiveness(lanes, commits, window_min):
    """How much of the sampled CPU is law work (python and git) vs overhead (antivirus, indexing, watchers),
    and law commits per busy core-hour for this window."""
    law = sum(v for k, v in lanes if k.startswith(('python', 'git')) or k.split()[0] in LAW_VM)
    over = sum(v for k, v in lanes if k.split()[0] in OVERHEAD)
    total = sum(v for k, v in lanes if k not in ('system idle process',))
    per_core_h = round(commits / max(0.1, law) / max(0.1, window_min / 60)) if law else 0
    return {'law_cores': round(law, 1), 'overhead_cores': round(over, 1), 'busy_cores': round(total, 1),
            'law_share': round(100 * law / total) if total else 0, 'commits_per_law_core_h': per_core_h}


def main():
    t = now()
    state = json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {}
    prev_t = parse(state['at']) if 'at' in state else t - dt.timedelta(minutes=5)
    window_min = max(1.0, (t - prev_t).total_seconds() / 60)

    # global-law: pushes in the window, submodules now
    gl_pushes = int(git('rev-list', '--count', f'--since={iso(prev_t)}', 'refs/remotes/origin/main').strip() or 0)
    subs = sum(1 for l in git('ls-tree', '-r', 'refs/remotes/origin/main').splitlines() if ' commit ' in l)

    # country tips: what moved since the last run, and by how many commits
    tips = {u.rstrip('/').removesuffix('.git').rsplit('/', 1)[1]: v.get('tips', {}).get('main')
            for u, v in json.loads(TIPS.read_text(encoding='utf-8')).items()} if TIPS.exists() else {}
    old_tips = state.get('tips', {})
    total = state.get('total')
    tok = token()
    added, moved, rewrites, new_repos, skipped = 0, [], [], [], 0
    if total is None and CENSUS.exists():  # first run: start from the full census, keyed to the current tips
        total = sum(n or 0 for _, _, n in json.loads(CENSUS.read_text(encoding='utf-8')))
        old_tips = dict(tips)
    calls = 0
    for repo, sha in sorted(tips.items()):
        if not sha:
            continue
        before = old_tips.get(repo)
        if before == sha:
            continue
        if calls >= MAX_COMPARES:
            skipped += 1
            continue
        calls += 1
        try:
            if before is None:
                n = count_commits(tok, repo)
                new_repos.append((repo, n))
                added += n
            else:
                n, ff = compare(tok, repo, before, sha)
                if not ff:
                    rewrites.append(repo)
                moved.append((repo, n))
                added += n
        except Exception:
            skipped += 1
            sha = before  # retry next run
        if sha:
            old_tips[repo] = sha
    total = (total or 0) + added

    cpu5, ram = cpu_window(prev_t)
    scr = {n: scraper_window(n, prev_t) for n in LOGS}
    try:
        pending = json.loads(PENDING.read_text(encoding='utf-8'))
    except Exception:
        pending = {}
    stalled = [l for l in read_text(STALLED).splitlines() if l[:19] and l[:4].isdigit()
               and parse(l.split()[0]) > t - dt.timedelta(hours=2)]

    row = {'at': iso(t), 'window_min': round(window_min, 1), 'commits_added': added, 'repos_moved': len(moved),
           'new_repos': len(new_repos), 'gl_pushes': gl_pushes, 'submodules': subs, 'total_commits': total,
           'cpu5': cpu5, 'ram': ram, 'rewrites_seen': rewrites, 'pending': len(pending), 'stalled_2h': len(stalled),
           'skipped_compares': skipped, 'scrapers': scr, 'cpu_lanes': cpu_by_lane(), 'fetch': fetch_window(prev_t),
           'top': sorted(moved + new_repos, key=lambda x: -x[1])[:12]}
    # repos whose claim file names a GPT-6 worker (hp-omen's Azure lanes): their commits, tracked separately
    claims = Path(r'C:\Users\alany\Documents\lexifina\scripts\world-law\claims')
    wl = {c.stem for c in claims.glob('*.txt') if 'gpt-worker' in read_text(c)}
    row['worker_repos'] = len(wl)
    row['worker_commits'] = sum(n for r, n in moved + new_repos if r in wl or f'{r}-law' in wl)
    # effect and coverage go into the history row too, so the strategy log can chart them over time
    row['effect'] = cpu_effectiveness(row.get('cpu_lanes', []), added, window_min)
    row['coverage'] = coverage_census(t)
    with HISTORY.open('a', encoding='utf-8') as f:
        f.write(json.dumps(row) + '\n')
    hist = [json.loads(l) for l in HISTORY.read_text(encoding='utf-8').splitlines() if l.strip()][-300:]
    advice = diagnose(row, hist, pending, stalled)
    row['advice'] = advice
    LATEST.write_text(json.dumps(row, indent=1), encoding='utf-8')

    # alert once per bottleneck when it starts, and not again for the same key within 2 h (CPU near the 75% line
    # flapped the headroom advice every other run)
    keys = sorted(a['key'] for a in advice if a['level'] == 'act')
    seen = set(state.get('advice_keys', []))
    last = dict(state.get('advice_last', {}))
    with ALERTS.open('a', encoding='utf-8') as f:
        for a in advice:
            k = a['key']
            recent = k in last and t - parse(last[k]) < dt.timedelta(hours=2)
            if a['level'] == 'act' and k not in seen and not recent:
                f.write(f"{iso(t)} ADVICE {a['title']}: {a['do']}\n")
                last[k] = iso(t)
    STATE.write_text(json.dumps({'at': iso(t), 'tips': old_tips, 'total': total, 'advice_keys': keys,
                                 'advice_last': last}), encoding='utf-8')
    render(row, hist, pending, stalled, advice)


def rate(hist, minutes, key):
    t = parse(hist[-1]['at'])
    rows = [h for h in hist if parse(h['at']) > t - dt.timedelta(minutes=minutes)]
    span = sum(h['window_min'] for h in rows) or 1
    return sum(h.get(key, 0) for h in rows), span


def stuck_pushes(push_min=5, prompt_min=2):
    """git push processes older than push_min minutes and credential-manager prompts older than prompt_min (reported only)."""
    import time
    try:
        import psutil
    except ImportError:
        return []
    out, t = [], time.time()
    for p in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
        try:
            name = (p.info['name'] or '').lower()
            cmd = ' '.join(p.info['cmdline'] or [])
            age = (t - p.info['create_time']) / 60
            if 'credential-manager' in name and age > prompt_min:
                out.append(f'pid {p.info["pid"]} credential prompt {age:.0f} min')
            elif name.startswith('git') and ' push' in cmd and age > push_min:
                out.append(f'pid {p.info["pid"]} git push {age:.0f} min')
        except (psutil.Error, TypeError):
            continue
    return out


def runaway_searches(min_age_min=10):
    """Recursive grep/find/rg left running for more than min_age_min: tree-wide searches over the scripts tree
    cost a core each for hours (and feed Defender). Reported with PID and command so the owner can stop it."""
    import psutil, time
    out = []
    for p in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
        try:
            n, cmd = (p.info['name'] or '').lower(), p.info['cmdline'] or []
            if n not in ('grep.exe', 'rg.exe', 'find.exe') or '--line-buffered' in cmd:
                continue
            recursive = n in ('rg.exe', 'find.exe') or any(a.startswith('-') and not a.startswith('--') and 'r' in a for a in cmd[1:])
            age = (time.time() - p.info['create_time']) / 60
            if recursive and age > min_age_min:
                out.append({'pid': p.info['pid'], 'age_min': round(age), 'cmd': ' '.join(cmd[1:])[:140]})
        except Exception:
            continue
    return out


def diagnose(row, hist, pending, stalled):
    """Rules that turn the numbers into the next thing to do. level 'act' = do something now; 'note' = watch."""
    out = []
    c60, span60 = rate(hist, 60, 'commits_added')
    p60, _ = rate(hist, 60, 'gl_pushes')
    s = row['scrapers']
    ef = row.get('effect') or {}
    if ef.get('busy_cores') and ef.get('law_share', 100) < 60:
        out.append({'key': 'cpu-ineffective', 'level': 'act', 'title': f"Only {ef['law_share']}% of busy CPU is law work",
                    'why': f"{ef['overhead_cores']} cores go to overhead (antivirus, indexing, watchers); law work has {ef['law_cores']}.",
                    'do': 'Cut the overhead (Defender exclusions, stray watchers, idle containers) before adding agents.'})
    import shutil
    free_gb = shutil.disk_usage('C:/').free / 1e9
    if free_gb < 40:
        out.append({'key': 'disk-low', 'level': 'act', 'title': f"Only {free_gb:.0f} GB free on C:",
                    'why': 'A full C: crashes WSL and Docker and stops every lane (it hit 0 B at 10:00Z on 2026-11-03).',
                    'do': 'Pause writers and clear caches of finished lanes before it reaches 0.'})
    stuck = stuck_pushes()
    if stuck:
        out.append({'key': 'push-stuck', 'level': 'act', 'title': f'{len(stuck)} git push or credential prompt stuck over 5 min',
                    'why': 'A hung git-credential-manager prompt blocks every push behind it (it did twice on 2026-11-03).',
                    'do': 'Give that clone the per-repo gh helper (ensure_gh_helper.sh) and stop only your own stuck PID: '
                          + '; '.join(stuck[:6])})
    rs = runaway_searches()
    if rs:
        out.append({'key': 'runaway-search', 'level': 'act', 'title': f"{len(rs)} tree-wide search(es) running over 10 min",
                    'why': '; '.join(f"PID {r['pid']} ({r['age_min']} min): {r['cmd']}" for r in rs[:4]),
                    'do': 'The owning session should stop it and search one folder or one repo instead.'})
    if row['cpu5'] < 75:
        out.append({'key': 'cpu-headroom', 'level': 'act', 'title': f"CPU at {row['cpu5']}%",
                    'why': 'Below the 80-92% target, so there is room for more agents.',
                    'do': 'Ask both scrapers to add 2 agents now, on hosts with idle slots.'
                          + (' Cut overhead first: most busy CPU is not law work.' if ef.get('law_share', 100) < 60 else '')})
    if row['cpu5'] > 95:
        out.append({'key': 'cpu-over', 'level': 'act', 'title': f"CPU at {row['cpu5']}%",
                    'why': 'Above the back-off line: builds slow each other down.',
                    'do': 'Ask the scrapers to stop starting work until cpu5 < 92.'})
    if len(pending) >= 5:
        out.append({'key': 'held-rewrites', 'level': 'act', 'title': f'{len(pending)} repos held as rewrites',
                    'why': 'Verified work that cannot publish without changing published history.',
                    'do': 'Ship the labelled correction commit and append older acts at the end (D12).'})
    for name, v in s.items():
        if v['last_pass'] and parse(v['last_pass']) < parse(row['at']) - dt.timedelta(minutes=15):
            out.append({'key': f'{name}-loop-stale', 'level': 'act', 'title': f'{name} autopush loop quiet',
                        'why': f"No pass logged since {v['last_pass']}.",
                        'do': f'Ask {name} whether its autopush loop is alive and restart it.'})
        if v['failed'] >= 3:
            out.append({'key': f'{name}-failures', 'level': 'act', 'title': f"{name}: {v['failed']} failures",
                        'why': 'Failed or erroring passes in the last window.',
                        'do': f'Ask {name} to look at its autopush log.'})
        if v['held'] > 2 * max(1, v['pushed']):
            out.append({'key': f'{name}-mostly-held', 'level': 'note', 'title': f'{name}: mostly held',
                        'why': f"{v['held']} held/refused vs {v['pushed']} pushed this window.",
                        'do': 'Check REWRITE-PENDING for that lane; most holds clear once corrections exist.'})
    if span60 >= 50 and c60 < 200:
        out.append({'key': 'low-yield', 'level': 'act', 'title': f'Only {c60} commits in the last hour',
                    'why': 'Throughput is low for the size of the fleet.',
                    'do': 'Start the bulk routes (Italy, Japan, Canada federal, South Australia XML) and add hosts.'})
    if stalled:
        out.append({'key': 'stalled', 'level': 'note', 'title': f'{len(stalled)} stalled producer(s) in 2 h',
                    'why': 'A claimed repo whose folder has not changed for 2 hours.',
                    'do': 'Ask the owning scraper to restart or release it.'})
    if row['rewrites_seen']:
        out.append({'key': 'rewrite-seen', 'level': 'act', 'title': 'Non-fast-forward main seen',
                    'why': ', '.join(row['rewrites_seen'][:8]) + ' moved without a fast-forward.',
                    'do': 'Find which loop pushed it; force-pushes are banned (2026-11-02).'})
    if row['skipped_compares']:
        out.append({'key': 'compare-backlog', 'level': 'note', 'title': f"{row['skipped_compares']} tips not yet measured",
                    'why': 'More repos moved than one run measures; they are counted on the next run.', 'do': '-'})
    if not out:
        out.append({'key': 'ok', 'level': 'note', 'title': 'No bottleneck flagged', 'why': '', 'do': '-'})
    return out


def spark(vals, w=640, h=90, color='var(--accent)'):
    if not vals:
        return ''
    m = max(vals) or 1
    step = w / max(1, len(vals) - 1)
    pts = ' '.join(f'{i * step:.1f},{h - (v / m) * (h - 6) - 3:.1f}' for i, v in enumerate(vals))
    return (f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="none" class="spark" role="img">'
            f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{pts}"/></svg>'
            f'<div class="axis"><span>{len(vals)} runs ago</span><span>max {m:,}</span><span>now</span></div>')


def hourly(hist):
    """Law commits added per clock hour (UTC), oldest first, from the run history."""
    by = {}
    for h in hist:
        k = h['at'][:13]
        by[k] = by.get(k, 0) + h['commits_added']
    return sorted(by.items())[-24:]


def render(row, hist, pending, stalled, advice):
    e = html.escape
    c5 = row['commits_added']
    c60, s60 = rate(hist, 60, 'commits_added')
    c1440, s1440 = rate(hist, 1440, 'commits_added')
    p60, _ = rate(hist, 60, 'gl_pushes')
    per_h = round(c60 * 60 / s60) if s60 else 0
    tiles = [('Commits, last run', f"{c5:,}", f"{row['window_min']} min"),
             ('Commits per hour', f"{per_h:,}", f'last {round(s60)} min'),
             ('Commits, last 24 h', f"{c1440:,}", f'over {round(s1440 / 60, 1)} h measured'),
             ('Total commits', f"{row['total_commits']:,}", 'census + measured'),
             ('global-law pushes, 1 h', f"{p60}", f"{row['submodules']} submodules"),
             ('CPU (5-min avg)', f"{row['cpu5']}%", f"RAM {row['ram']}%"),
             ('Held rewrites', f"{row['pending']}", 'REWRITE-PENDING.json'),
             ('CPU on law work', f"{(row.get('effect') or {}).get('law_share', 0)}%", f"{(row.get('effect') or {}).get('law_cores', 0)} of {(row.get('effect') or {}).get('busy_cores', 0)} busy cores"),
             ('Commits per law core-hour', f"{(row.get('effect') or {}).get('commits_per_law_core_h', 0):,}", 'this run'),
             ('GPT-6 worker-lane commits/h', f"{round(rate(hist, 60, 'worker_commits')[0] * 60 / (s60 or 1)):,}", f"{row.get('worker_repos', 0)} repos with a gpt-worker claim"),
             ('Stalled, 2 h', f"{row['stalled_2h']}", 'STALLED.txt')]
    tile_html = ''.join(f'<div class="tile"><div class="k">{e(a)}</div><div class="v">{e(b)}</div>'
                        f'<div class="s">{e(c)}</div></div>' for a, b, c in tiles)
    adv = ''.join(f'<tr class="{a["level"]}"><td>{"Act" if a["level"] == "act" else "Watch"}</td><td>{e(a["title"])}</td>'
                  f'<td>{e(a["why"])}</td><td>{e(a["do"])}</td></tr>' for a in advice)
    scr = ''.join(f'<tr><td>{e(n)}</td><td>{v["loops"]}</td><td>{e(v["last_pass"] or "-")}</td><td>{v["pushed"]}</td>'
                  f'<td>{v["appended"]}</td><td>{v["held"]}</td><td>{v.get("waiting", 0)}</td><td>{v["failed"]}</td></tr>' for n, v in row['scrapers'].items())
    fw = row.get('fetch') or {}
    fetch_html = (f"<p class='sub'>{fw.get('requests', 0)} requests to {fw.get('hosts', 0)} hosts this run · {fw.get('cached', 0)} cache or 304 · "
                  f"{fw.get('errors', 0)} errors · stops: {e(', '.join(fw.get('stops', [])) or 'none')}</p>"
                  + ''.join(f'<div class=sub>{e(h)}: {n}</div>' for h, n in fw.get('top_hosts', [])))
    lanes = ''.join(f'<tr><td>{e(k)}</td><td>{v}</td></tr>' for k, v in row.get('cpu_lanes', [])) or '<tr><td colspan=2>-</td></tr>'
    top = ''.join(f'<tr><td>{e(r)}</td><td>{n:,}</td></tr>' for r, n in row['top']) or '<tr><td colspan=2>none this run</td></tr>'
    pend = ''.join(f'<tr><td>{e(k)}</td><td>{e(str(v)[:220])}</td></tr>' for k, v in list(pending.items())[:30])
    hours = hourly(hist)
    hour_html = ''.join(f'<tr><td>{e(k[11:13])}:00</td><td>{n:,}</td></tr>' for k, n in reversed(hours))
    totals = [h['total_commits'] for h in hist[-288:]]
    series = [h['commits_added'] for h in hist[-288:]]
    pushes = [h['gl_pushes'] for h in hist[-288:]]
    cpus = [h['cpu5'] for h in hist[-288:]]
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="refresh" content="60">
<title>Global law speed</title><style>
:root{{--bg:#fafaf9;--fg:#1c1917;--muted:#78716c;--line:#e7e5e4;--card:#fff;--accent:#2563eb;--act:#b45309;--ok:#15803d}}
@media (prefers-color-scheme: dark){{:root{{--bg:#0c0a09;--fg:#e7e5e4;--muted:#a8a29e;--line:#292524;--card:#1c1917;--accent:#60a5fa;--act:#f59e0b;--ok:#4ade80}}}}
body{{background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,-apple-system,Segoe UI,sans-serif;margin:0;padding:20px 16px;max-width:1100px;margin:auto}}
h1{{font-size:20px;margin:0 0 2px}}h2{{font-size:15px;margin:26px 0 8px}}.sub{{color:var(--muted)}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:10px;margin-top:16px}}
.tile{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 12px}}
.k{{color:var(--muted);font-size:12px}}.v{{font-size:22px;font-weight:600;margin-top:2px}}.s{{color:var(--muted);font-size:12px}}
table{{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:8px;overflow:hidden}}
td,th{{text-align:left;padding:6px 10px;border-bottom:1px solid var(--line);vertical-align:top}}th{{font-size:12px;color:var(--muted);font-weight:500}}
tr.act td:first-child{{color:var(--act);font-weight:600}}tr.note td:first-child{{color:var(--muted)}}
.spark{{width:100%;height:90px;background:var(--card);border:1px solid var(--line);border-radius:8px}}
.axis{{display:flex;justify-content:space-between;color:var(--muted);font-size:11px;margin-top:2px}}
.wrap{{overflow-x:auto}}</style></head><body>
<h1>Global law speed</h1><div class="sub">Measured {e(row['at'])} · refreshes every 5 minutes (page reloads each minute)</div>
<div class="tiles">{tile_html}</div>
<h2>What to do now</h2><div class="wrap"><table><tr><th></th><th>Signal</th><th>Why</th><th>Do</th></tr>{adv}</table></div>
<h2>Law commits in all repos (running total)</h2>{spark(totals, color='var(--ok)')}
<h2>Law commits added per hour (UTC)</h2><div class="wrap"><table><tr><th>Hour</th><th>Commits</th></tr>{hour_html}</table></div>
<p class="sub">These count law commits in every country, state and city repo. global-law's own commit count no longer tracks law growth: since 30 Oct one repoint commit carries many law changes.</p>
<h2>Commits added per run (last 24 h)</h2>{spark(series)}
<h2>global-law pushes per run</h2>{spark(pushes)}
<h2>CPU, 5-minute average</h2>{spark(cpus, color='var(--act)')}
<h2>Scraper loops (this run)</h2><div class="wrap"><table><tr><th>Scraper</th><th>Country loops</th><th>Last pass</th>
<th>Pushed</th><th>Appended</th><th>Held / refused</th><th>Waiting for builder</th><th>Failures</th></tr>{scr}</table></div>
<h2>Shared fetch scheduler (lanes that have adopted it)</h2>{fetch_html}
<h2>Where the CPU goes (cores, 3-second sample)</h2><div class="wrap"><table><tr><th>Lane</th><th>Cores</th></tr>{lanes}</table></div>
<h2>Most commits added this run</h2><div class="wrap"><table><tr><th>Repo</th><th>Commits</th></tr>{top}</table></div>
<h2>Held rewrites</h2><div class="wrap"><table><tr><th>Repo</th><th>Reason</th></tr>{pend}</table></div>
</body></html>"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding='utf-8')


if __name__ == '__main__':
    main()
