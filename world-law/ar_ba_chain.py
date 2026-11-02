"""Unattended finish for Buenos Aires (gitlaw-scraper-dell, coordinator 2026-10-31). Private, never published.

1. Waits for the main continuation run (PID given) to exit.
2. If that run was not stopped by a challenge/403/429, re-reads normas.gba.gob.ar/robots.txt once, alone, and stops if
   it changed; otherwise runs the second pass (oldest-first for the 12 capped years) through ar_batch.py with
   AR_BA_PASS2=1 and AR_PART_PREFIX=990 (same rules, checks and batching; laws already published are dropped).
3. Waits for the autopush to push a main that includes every PUBLISHed part, then writes
   argentina-buenos-aires-law/FINAL-REPORT.txt, appends to SCRAPING-LOG.md and releases the claim.

    python -X utf8 scripts/world-law/ar_ba_chain.py <pid>
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent
FOLDER = SCRIPTS / 'argentina-buenos-aires-law'
LOG = HERE / 'logs' / 'ar-deepen-buenos-aires.log'
CLAIM = HERE / 'claims' / 'argentina-buenos-aires-law.txt'
ROBOTS_BEFORE = b'# See http://www.robotstxt.org/robotstxt.html for documentation on how to use the robots.txt file\n\nSitemap: https://normas.gba.gob.ar/sitemap.xml.gz\n'


def now():
    return dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def note(line: str):
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(f'{time.strftime("%H:%M:%S")} chain: {line}\n')


def scraping_log(line: str):
    with open(SCRIPTS / 'SCRAPING-LOG.md', 'a', encoding='utf-8', newline='\n') as f:
        f.write(f'- {now()} gitlaw-scraper-dell (Buenos Aires unattended chain): {line}\n')


def alive(pid: int) -> bool:
    import psutil
    return psutil.pid_exists(pid) and 'python' in psutil.Process(pid).name().lower()


def main():
    import psutil
    psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    pid = int(sys.argv[1])
    start_size = LOG.stat().st_size
    while alive(pid):
        time.sleep(60)
    tail = LOG.read_text(encoding='utf-8', errors='replace')[-4000:]
    if 'STOPPED' in tail or 'Traceback' in tail:
        note('main run ended with STOPPED/Traceback: second pass not started')
        scraping_log('main continuation run ended with a stop or error; second pass not started; claim kept.')
        return
    note('main continuation run finished; second pass (oldest-first, 12 capped years) starting')
    sys.path.insert(0, str(HERE))
    import ar_provinces as E
    time.sleep(10)
    r = E.net().get('https://normas.gba.gob.ar/robots.txt')
    if r.status_code != 200 or r.content.replace(b'\r', b'').strip() != ROBOTS_BEFORE.strip():
        note(f'robots.txt changed or not 200 ({r.status_code}): second pass not started')
        scraping_log(f'robots.txt re-read: HTTP {r.status_code}, changed or unreadable; second pass not started; claim kept.')
        return
    scraping_log('main list exhausted; robots.txt re-read alone (unchanged); second pass started: oldest-first '
                 '(by_publication_date_asc) for 2006 2001 1992 1975 1974 1965 1964 1961 1960 1959 1942 1889, parts '
                 '990-leyes-NNN continued, laws already published dropped.')
    env = dict(os.environ, AR_BA_PASS2='1', AR_PART_PREFIX='990',
               PATH=r'C:\Program Files\Git\mingw64\bin;' + os.environ.get('PATH', ''))
    with open(LOG, 'a', encoding='utf-8') as out:
        p = subprocess.run([sys.executable, '-X', 'utf8', str(HERE / 'ar_batch.py'), 'run', 'buenos-aires',
                            '--laws=100000', '--batch=6', '--replan'], cwd=SCRIPTS.parent, env=env,
                           stdout=out, stderr=subprocess.STDOUT)
    tail = LOG.read_text(encoding='utf-8', errors='replace')[-4000:]
    if p.returncode or 'STOPPED' in tail:
        note(f'second pass ended with code {p.returncode} or a stop; claim kept')
        scraping_log('second pass ended with an error or a stop; claim kept.')
        return
    left = [x.name for x in (FOLDER / 'corpus.d').glob('*.VERIFIED')]
    # wait for the autopush: a BUILD_STATUS written after the last PUBLISH that names no part as left out
    last_pub = max(x.stat().st_mtime for x in (FOLDER / 'corpus.d').glob('*.PUBLISH'))
    for _ in range(24 * 60):
        st = FOLDER / 'BUILD_STATUS.json'
        if st.exists() and st.stat().st_mtime > last_pub + 5:
            d = json.loads(st.read_text(encoding='utf-8'))
            if 'left out until verified' not in d.get('main', '') and ('pushed' in d.get('main', '') or
                                                                        'nothing to push' in d.get('main', '')):
                break
        time.sleep(60)
    sha = subprocess.run(['git', 'ls-remote', 'https://github.com/lexifina/argentina-buenos-aires-law.git',
                          'refs/heads/main'], capture_output=True, text=True).stdout.split()[:1]
    acts = 0
    laws = 0
    for x in sorted((FOLDER / 'corpus.d').glob('*.json')):
        if x.with_suffix('.PUBLISH').exists():
            j = json.loads(x.read_text(encoding='utf-8'))
            acts += len(j['acts'])
            if '-leyes-' in x.stem:
                laws += len(j['acts'])
    rep = (f'{now()} Buenos Aires finished: {laws} laws in law parts ({acts} norms incl. constitution and codes); '
           f'main {sha[0] if sha else "?"}; unpublished verified parts left: {left or "none"}.')
    (FOLDER / 'FINAL-REPORT.txt').write_text(rep + '\n', encoding='utf-8', newline='\n')
    note(rep)
    if not left and sha:
        CLAIM.unlink(missing_ok=True)
        scraping_log(rep + ' Claim released.')
    else:
        scraping_log(rep + ' Claim kept (see FINAL-REPORT.txt).')


if __name__ == '__main__':
    main()
