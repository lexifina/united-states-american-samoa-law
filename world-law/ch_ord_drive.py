"""Ordinance parts of the LexWork cantons (gitlaw-scraper-dell, coverage wave 2026-10-30): parse what the ordinance
fetch has cached, verify the new parts together, and write their PUBLISH files in batches (5 or more parts, or all
that are left once a canton's ordinance fetch is done), so the autopush rebuilds once per batch, not per part.

    python -X utf8 scripts/world-law/ch_ord_drive.py 2026-10-30 bern lucerne ...

Waits while cpu5 > 92 or RAM > 85. Runs at BelowNormal; the builds it starts inherit that.
"""
import datetime as dt
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ch_cantons as C  # noqa: E402

day, slugs = sys.argv[1], sys.argv[2:]
BATCH = 5
LOG = Path(__file__).resolve().parent / 'logs' / 'ch-ord-drive.log'
failed: set[tuple[str, str]] = set()
finished: set[str] = set()


def log(msg: str):
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(f'{dt.datetime.now(dt.timezone.utc).strftime("%H:%M:%S")} {msg}\n')


def load() -> tuple[int, int]:
    p = Path(os.environ.get('LOCALAPPDATA', '')) / 'gitlaw-cpu.log'
    try:
        last = p.read_text(encoding='utf-8').strip().splitlines()[-1]
        return int(last.split('cpu5=')[1].split()[0]), int(last.split('ram=')[1].split()[0])
    except Exception:
        return 0, 0


def wait_load():
    while True:
        c, r = load()
        if c <= 92 and r <= 85:
            return
        time.sleep(60)


def parse(s: str) -> bool:
    r = subprocess.run([sys.executable, '-X', 'utf8', str(Path(C.__file__)), 'parse', s, day], capture_output=True,
                       text=True, encoding='utf-8', creationflags=0x4000)
    if r.returncode:
        log(f'{s} parse failed: {r.stderr[-300:]}')
    return r.returncode == 0


def mark(s: str, names: list[str]):
    wait_load()
    res = C.verify_parts(s, names, day)
    if any(not ok for ok, _ in res.values()) and len(names) > 1:
        res = {n: C.verify_part(s, n, day) for n in names}
    passed = sorted(n for n, (ok, _) in res.items() if ok)
    f = C.folder(s)
    C.write_docs(s, day, extra=passed)
    for n, (ok, line) in sorted(res.items()):
        pub = f / 'corpus.d' / f'{n}.PUBLISH'
        if ok:
            pub.write_text(line + chr(10), encoding='utf-8', newline=chr(10))
            log(f'{s} {n} PUBLISH {line[:200]}')
        else:
            failed.add((s, n))
            log(f'{s} {n} NOT VERIFIED {line[:400]}')
    C.write_docs(s, day)


def batch_ready(s: str) -> bool:
    """True when the fetch has cached enough ordinances (in order) for BATCH more full parts, so new parts reach
    corpus.d (and the autopush) a batch at a time."""
    h = C.Host(s)
    n = 0
    for sn in C.ordinance_candidates(h):
        if not h.path(h.url('texts_of_law/' + C.urllib.parse.quote(sn, safe=''))).exists():
            break
        n += 1
    have = len(list((C.folder(s) / 'corpus.d').glob('*verordnungen*.json')))
    return n >= (have + BATCH + 1) * C.PART_SIZE


while True:
    for s in slugs:
        if s in finished:
            continue
        wait_load()
        f = C.folder(s)
        done = (f / '.cache' / 'fetch-ord-done.txt').exists()
        if not done and not batch_ready(s):
            continue
        if not parse(s):
            continue
        new = [p.stem for p in sorted((f / 'corpus.d').glob('*verordnungen*.json'))
               if not p.with_suffix('.PUBLISH').exists() and (s, p.stem) not in failed]
        if new and (len(new) >= BATCH or done):
            mark(s, new)
            continue
        if done and not new:
            finished.add(s)
            n = len(list((f / 'corpus.d').glob('*verordnungen*.PUBLISH')))
            log(f'{s} all ordinance parts decided ({n} published, '
                f'{len([x for x in failed if x[0] == s])} not verified)')
    if len(finished) == len(slugs):
        log('all fetched and decided; exiting')
        break
    time.sleep(180)
