"""gitlaw-scraper-dell (2026-10-30): streams belgium-flanders-law parts. Every INTERVAL s: parse the cache into
corpus.d parts (be_flanders.py parse), then verify + PUBLISH each part that has none, one at a time (one build process).
autopush_dell.py publishes main from the PUBLISH files. Stops when the fetch is done and every part is published, or
when scripts/belgium-flanders-law/.cache/loop-stop exists. Log: .cache/loop.log.
"""
from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent / 'belgium-flanders-law'
INTERVAL = 600
DOCS_DATE = sys.argv[1] if len(sys.argv) > 1 else '2026-10-30'
LOG = FOLDER / '.cache' / 'loop.log'


def log(msg: str):
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(f'{dt.datetime.now(dt.timezone.utc):%Y-%m-%dT%H:%M:%SZ} {msg}\n')


def run(*args) -> str:
    p = subprocess.run([sys.executable, '-X', 'utf8', str(HERE / 'be_flanders.py'), *args], capture_output=True,
                       text=True, encoding='utf-8', errors='replace', creationflags=0x4000 if os.name == 'nt' else 0)
    return (p.stdout + p.stderr).strip()


def main():
    try:
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception:
        pass
    while not (FOLDER / '.cache' / 'loop-stop').exists():
        log('parse: ' + run('parse', DOCS_DATE)[-300:])
        pending = [p.stem for p in sorted((FOLDER / 'corpus.d').glob('*.json')) if not p.with_suffix('.PUBLISH').exists()]
        for part in pending:
            log(f'{part}: ' + run('publish', part, DOCS_DATE)[-400:])
        done = all((FOLDER / '.cache' / f'fetch-{w}-done.txt').exists() for w in ('core', 'decrees'))
        if done and not [p for p in (FOLDER / 'corpus.d').glob('*.json') if not p.with_suffix('.PUBLISH').exists()]:
            log('fetch done and every part published; waiting for autopush to push main, then releasing the claim')
            last = max(p.stat().st_mtime for p in (FOLDER / 'corpus.d').glob('*.PUBLISH'))
            claim = HERE / 'claims' / 'belgium-flanders-law.txt'
            for _ in range(144):   # up to a day
                st = FOLDER / 'BUILD_STATUS.json'
                try:
                    s = st.read_text(encoding='utf-8')
                except OSError:
                    s = ''
                if st.exists() and st.stat().st_mtime > last + 5 and 'left out until verified' not in s \
                        and ('pushed' in s or 'unchanged' in s) and 'fail' not in s:
                    if claim.exists() and claim.read_text(encoding='utf-8').startswith('gitlaw-scraper-dell'):
                        claim.unlink()
                    log('main pushed with every part; claim released; loop ends')
                    return
                time.sleep(INTERVAL)
            log('autopush did not confirm within a day; claim kept; loop ends')
            return
        time.sleep(INTERVAL)


if __name__ == '__main__':
    main()
