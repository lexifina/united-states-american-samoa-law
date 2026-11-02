"""Drives the LexWork cantons (gitlaw-scraper-dell, 2026-10-30): parse what the fetch has cached, verify each full part,
write its PUBLISH. One pass after another, a pause between passes; exits when every canton's fetch is done and every
part is decided. Runs at BelowNormal; the builds it starts inherit that.

    python -X utf8 scripts/world-law/ch_drive.py 2026-10-30 bern lucerne ...
"""
import datetime as dt
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ch_cantons as C  # noqa: E402

day, slugs = sys.argv[1], sys.argv[2:]
LOG = Path(__file__).resolve().parent / 'logs' / 'ch-drive.log'
failed: set[tuple[str, str]] = set()


def log(msg: str):
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(f'{dt.datetime.now(dt.timezone.utc).strftime("%H:%M:%S")} {msg}\n')


def cpu5() -> int:
    import os
    p = Path(os.environ.get('LOCALAPPDATA', '')) / 'gitlaw-cpu.log'
    try:
        last = p.read_text(encoding='utf-8').strip().splitlines()[-1]
        return int(last.split('cpu5=')[1].split()[0])
    except Exception:
        return 0


def mark(s: str, names: list[str], tag: str):
    """Verify `names` together; write PUBLISH for those that pass (docs first), drop it for those that fail."""
    if not names:
        return
    res = C.verify_parts(s, names, day)
    if any(not ok for ok, _ in res.values()) and len(names) > 1:
        res = {n: C.verify_part(s, n, day) for n in names}  # find the failing part on its own
    passed = [n for n, (ok, _) in res.items() if ok]
    C.write_docs(s, day, extra=passed)
    f = C.folder(s)
    for n, (ok, line) in sorted(res.items()):
        pub = f / 'corpus.d' / f'{n}.PUBLISH'
        if ok:
            pub.write_text(line + chr(10), encoding='utf-8', newline=chr(10))
            log(f'{s} {n} {tag} PUBLISH {line[:200]}')
        else:
            if pub.exists():
                pub.unlink()
            failed.add((s, n))
            log(f'{s} {n} {tag} NOT VERIFIED {line[:300]}')
    if passed and not (f / 'PUBLISH').exists():
        (f / 'PUBLISH').write_text('corpus.d parts are published one by one, each once its own <part>.PUBLISH is '
                                   'written.' + chr(10), encoding='utf-8', newline=chr(10))
    C.write_docs(s, day)


def parse(s: str, cmd: str) -> bool:
    r = subprocess.run([sys.executable, '-X', 'utf8', str(Path(C.__file__)), cmd, s, day], capture_output=True,
                       text=True, encoding='utf-8', creationflags=0x4000)
    if r.returncode:
        log(f'{s} {cmd} failed: {r.stderr[-300:]}')
    return r.returncode == 0


redo = []
for a in list(slugs):
    if a.startswith('--reparse'):
        slugs.remove(a)
        redo = a.split('=', 1)[1].split(',') if '=' in a else list(slugs)
if redo:
    for s in redo:
        if parse(s, 'reparse'):
            mark(s, [p.stem for p in sorted((C.folder(s) / 'corpus.d').glob('*.json'))
                     if p.with_suffix('.PUBLISH').exists()], 'REVERIFIED')

while True:
    pending = False
    for s in slugs:
        while cpu5() > 92:
            time.sleep(60)
        f = C.folder(s)
        done = (f / '.cache' / 'fetch-done.txt').exists()
        if not parse(s, 'parse'):
            pending = True
            continue
        mark(s, [p.stem for p in sorted((f / 'corpus.d').glob('*.json'))
                 if not p.with_suffix('.PUBLISH').exists() and (s, p.stem) not in failed], 'NEW')
        if not done:
            pending = True
    if not pending:
        log('all fetched and decided; exiting')
        break
    time.sleep(120)
