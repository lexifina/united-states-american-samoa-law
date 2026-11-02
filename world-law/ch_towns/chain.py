"""Swiss towns on LexWork, one after another (gitlaw-scraper-dell, municipal tier wave 2, 2026-11-01). Private.

    python -u -X utf8 scripts/world-law/ch_towns/chain.py <docs-date> [--after-pids 1,2] town [town ...]

Strictly sequential: ONE fetcher and ONE publish driver at a time. Per town (its claim already taken by the gate
step): wait for CPU/RAM; start ch_cities.py fetch (BelowNormal); once the Gemeindeordnung is cached, parse and
verify part 10-verfassung; only then create the repo (one API call); start ch_cities_drive.py; wait for both; wait for
autopush_dell to push main; record the remote main sha, the PDF-only acts, PROGRESS.md and the triage/log lines;
delete the claim. Stop: create scripts/world-law/ch_towns/STOP (checked between steps; it also writes the town's
own STOP file, which ch_cities fetch and the driver obey).
"""
from __future__ import annotations

import contextlib
import datetime as dt
import io
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
WL = HERE.parent
SCRIPTS = WL.parent
REPO_ROOT = SCRIPTS.parent
sys.path.insert(0, str(WL))
import ch_cities as K  # noqa: E402
import ch_cities_drive as D  # noqa: E402

C = K.C
STOP = HERE / 'STOP'
BELOW = 0x00004000
LOG = HERE / 'chain.log'


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def say(*a):
    line = ' '.join(str(x) for x in a)
    print(now(), line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(f'{now()} {line}\n')


def alive(pid: int) -> bool:
    r = subprocess.run(['tasklist', '/FI', f'PID eq {pid}', '/NH'], capture_output=True, text=True)
    return str(pid) in r.stdout


def stopping(town: str | None = None) -> bool:
    if STOP.exists():
        if town:
            (C.folder(K.key(town)) / 'STOP').write_text('stop\n')
        return True
    return False


def claim(town: str) -> Path:
    return WL / 'claims' / f'switzerland-{town}-city-law.txt'


def start(args: list[str], folder: Path, name: str) -> subprocess.Popen:
    out = open(folder / f'{name}.log', 'a', encoding='utf-8')
    err = open(folder / f'{name}.err', 'a', encoding='utf-8')
    p = subprocess.Popen([sys.executable, '-u', '-X', 'utf8'] + args, cwd=str(REPO_ROOT), stdout=out, stderr=err,
                         creationflags=BELOW)
    with open(folder / 'my-pids.txt', 'a', encoding='utf-8') as f:
        f.write(f'{p.pid} {name}\n')
    say(f'started {name} pid {p.pid}')
    return p


def triage(line: str):
    with open(SCRIPTS / 'REGION-TRIAGE.md', 'a', encoding='utf-8', newline='\n') as f:
        f.write(f'  - {line}\n')


def scrapelog(line: str):
    with open(SCRIPTS / 'SCRAPING-LOG.md', 'a', encoding='utf-8', newline='\n') as f:
        f.write(f'- {line}\n')


def left_out(town: str) -> tuple[int, int, list[str]]:
    """(acts published, versions, acts in force of an ordinance type with no XHTML, i.e. PDF-only)."""
    slug = K.key(town)
    h = K.host(town)
    inparts = {}
    for p in sorted((C.folder(slug) / 'corpus.d').glob('*.json')):
        if not p.with_suffix('.PUBLISH').exists():
            continue
        for a in json.loads(p.read_text(encoding='utf-8'))['acts']:
            inparts[a['systematic_number']] = len(a['versions'])
    out = []
    for sn in [C.constitution_sn(h)] + K.ordinance_candidates(h):
        if sn in inparts:
            continue
        d = h.cached(h.url('texts_of_law/' + K.urllib.parse.quote(sn, safe='')))
        if not d or not C.ord_type_ok(h, d):
            continue
        out.append(f'{sn} {d["text_of_law"].get("title", "")}'.strip())
    return len(inparts), sum(inparts.values()), out


def remote_main(repo: str) -> str:
    r = subprocess.run(['git', 'ls-remote', f'https://github.com/lexifina/{repo}.git', 'refs/heads/main'],
                       capture_output=True, text=True)
    return (r.stdout.split() or [''])[0]


def finish(town: str, docs_date: str):
    """Wait for autopush to publish the last part's main; record; release the claim."""
    slug = K.key(town)
    fold = C.folder(slug)
    repo = f'switzerland-{slug}-law'
    pubs = sorted(fold.glob('corpus.d/*.PUBLISH'))
    if not pubs:
        say(f'{town}: nothing published')
        return
    logs = sorted((x for x in fold.glob('drive*.log')), key=lambda x: x.stat().st_mtime)   # a retry driver's log is newer
    drive = ''.join(x.read_text(encoding='utf-8', errors='replace') for x in logs)
    fin = [l for l in drive.splitlines() if l.startswith('drive: finished')]
    if not fin or not fin[-1].endswith('failed: []') or list(fold.glob('corpus.d/*.json'))[:0] or \
            any(not p.with_suffix('.PUBLISH').exists() for p in fold.glob('corpus.d/*.json')):
        say(f'{town}: PENDING, a part is unpublished ({fin[-1] if fin else "driver did not finish"}); claim kept')
        triage(f'{town}: PENDING. {fin[-1] if fin else "driver did not finish"}; parts published so far: '
               f'{", ".join(p.stem for p in pubs)}. Claim kept (autopush pushes main only once every part verifies).')
        return
    last = max(p.stat().st_mtime for p in pubs)
    ok, m = False, ''
    for _ in range(90):  # up to ~45 min
        if stopping():
            return
        bs = fold / 'BUILD_STATUS.json'
        if bs.exists() and bs.stat().st_mtime > last + 1:
            st = json.loads(bs.read_text(encoding='utf-8'))
            m = st.get('main', '')
            if 'fail' not in m and 'NOT' not in m and (m.startswith('pushed') or m.startswith('unchanged since')):
                ok = True
                break
        time.sleep(30)
    if not ok:
        say(f'{town}: PENDING, autopush has not pushed main ({m or 'no BUILD_STATUS'}); claim kept')
        triage(f'{town}: PENDING, autopush has not pushed main yet; claim kept.')
        return
    sha = remote_main(repo)
    n, nv, pdf = left_out(town)
    parts = [p.stem for p in pubs]
    (fold / 'PROGRESS.md').write_text(
        f'# {repo} (gitlaw-scraper-dell, {now()})\n\nState: done. Remote main {sha[:10]}.\n\n'
        f'Parts published: {", ".join(parts)} ({n} acts, {nv} versions).\n\n'
        f'Left out: in force and of an included type, but in no published part (no XHTML text, only a PDF, '
        f'or the text did not parse) ({len(pdf)}):\n\n' + ''.join(f'- {x}\n' for x in pdf),
        encoding='utf-8', newline='\n')
    triage(f'{town}: BUILT. lexifina/{repo}: Gemeindeordnung + {n - 1} Erlasse, {nv} dated versions, parts '
           f'{", ".join(parts)}; main {sha[:10]}; {len(pdf)} acts left out (PDF-only or unparsed) (listed in {fold.name}/PROGRESS.md). '
           'Claim released.')
    scrapelog(f'{now()} {town}: done, main {sha[:10]} ({repo}); fetch requests in {fold.name}/.cache/requests.jsonl; '
              'no 403/429/challenge unless noted. Claim deleted.')
    claim(town).unlink(missing_ok=True)
    say(f'{town}: done main {sha[:10]} parts {parts} acts {n} versions {nv} pdf-only {len(pdf)}')


def one(town: str, docs_date: str):
    slug = K.key(town)
    fold = C.folder(slug)
    fold.mkdir(parents=True, exist_ok=True)
    repo = f'switzerland-{slug}-law'
    if not claim(town).exists():
        say(f'{town}: no claim held, skipped')
        return
    while D.busy():
        if stopping():
            return
        time.sleep(60)
    off = len((fold / 'fetch.log').read_text(encoding='utf-8', errors='replace')) if (fold / 'fetch.log').exists() else 0
    f = start([str(WL / 'ch_cities.py'), 'fetch', town], fold, 'fetch')
    while f.poll() is None:   # read only what this fetch wrote (an earlier run's STOPPED line must not count)
        log = (fold / 'fetch.log').read_text(encoding='utf-8', errors='replace')[off:] if (fold / 'fetch.log').exists() else ''
        if 'Gemeindeordnung fetched' in log or 'STOPPED' in log:
            break
        time.sleep(10)
    log = (fold / 'fetch.log').read_text(encoding='utf-8', errors='replace')[off:]
    if 'Gemeindeordnung fetched' not in log:
        f.wait()
        say(f'{town}: fetch stopped before the Gemeindeordnung: {log.strip()[-300:]}')
        triage(f'{town}: FAIL at the first request wave: {log.strip()[-200:]}. No repo; claim released.')
        claim(town).unlink(missing_ok=True)
        return
    with contextlib.redirect_stdout(io.StringIO()):
        C.parse_canton(slug, docs_date)
    ok, line = C.verify_part(slug, '10-verfassung', docs_date)
    if not ok:
        (fold / 'STOP').write_text('first part did not verify\n')
        f.wait()
        say(f'{town}: Gemeindeordnung did not verify: {line[:300]}')
        triage(f'{town}: NOT BUILT, the Gemeindeordnung part did not verify ({line[:200]}). No repo; claim released.')
        claim(town).unlink(missing_ok=True)
        return
    say(f'{town}: 10-verfassung verifies: {line[:160]}')
    if stopping(town):
        f.wait()
        return
    say(f'{town}: create repo: {K.create_repo(town)}')
    time.sleep(20)
    dr = start([str(WL / 'ch_cities_drive.py'), town, docs_date], fold, 'drive')
    while f.poll() is None or dr.poll() is None:
        if stopping(town):
            say(f'{town}: STOP seen; waiting for fetch/driver to exit')
        time.sleep(30)
    say(f'{town}: fetch rc {f.returncode}, driver rc {dr.returncode}')
    if stopping():
        return
    finish(town, docs_date)


def main():
    a = sys.argv[1:]
    docs_date = a.pop(0)
    after = []
    if a and a[0] == '--after-pids':
        after = [int(x) for x in a[1].split(',')]
        a = a[2:]
    while any(alive(p) for p in after):
        if stopping():
            return
        time.sleep(30)
    for town in a:
        if stopping():
            say('STOP file: chain stopped')
            return
        if town.startswith('finish:'):
            finish(town[7:], docs_date)
            continue
        try:
            one(town, docs_date)
        except Exception as e:  # report, keep the claim (a person decides), go on
            say(f'{town}: ERROR {e!r}')
            triage(f'{town}: ERROR in the chain ({e!r}); claim kept for review.')
    say('chain: done')


if __name__ == '__main__':
    main()
