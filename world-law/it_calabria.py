"""Calabria (italy-calabria-law) for git-for-law, gitlaw-scraper-dell, 2026-10-30. Private (world-law-ops).

www.consiglioregionale.calabria.it robots.txt (read 2026-10-30 12:37 UTC):
    Request-rate: 1/30      Visit-time: 0600-0845      (the comments beside them say "5 s" and "2:00-5:45 UT"; the
                                                         directives are the stricter rule and are the ones obeyed)
So this fetcher sends at most one request every 30 s (it_fetch GAP file), and only between 06:00 and 08:44 UTC; outside
that window it waits (or exits with --once). It resumes from its saved queue, so it can run on several mornings.

Order, as REGION-TRIAGE-BRIEF.md "Order of requests on a new host" asks:
 1. robots.txt alone, re-read at the start of every window; obey any change (Disallow: / or a new window stops here).
 2. the home page, then the legal-notes / copyright page (gate 3: a person reads it before any build).
 3. the Statuto (page and its document): built first, once gate 3 passes.
 4. the regional-laws database pages (index first).
Nothing here builds or publishes; no repo is created until every gate passes.

    python -X utf8 scripts/world-law/it_calabria.py crawl [--once]   # waits for the window; --once: exit after it
    python -X utf8 scripts/world-law/it_calabria.py status
"""
from __future__ import annotations

import ctypes
import datetime as dt
import html as htmlmod
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import it_fetch  # noqa: E402
import it_regions as R  # noqa: E402

SLUG = 'calabria'
HOST = 'www.consiglioregionale.calabria.it'
BASE = f'https://{HOST}/'
FOLDER = R.folder(SLUG)
STATE = FOLDER / '.cache' / 'crawl.json'
LOG = FOLDER / 'fetch.log'
GAP = 31.0                  # Request-rate 1/30, plus a second
WIN = (6 * 60, 8 * 60 + 44)  # minutes UTC: 06:00 .. 08:44 (the last request starts before 08:45)
MAX_REQUESTS = 300           # in all, across mornings, before a person looks at what was found

KEYS = [  # (priority, pattern on the URL or link text); lower = sooner
    (1, r'note[-_ ]?legali|notelegali|copyright|condizioni|termini|disclaimer'),
    (2, r'statut'),
    (3, r'legg[ei][-_ ]?regional|leggiregionali|banca[-_ ]?dati|normativa|legislazione|raccolta'),
]
BINARY = re.compile(r'(?i)\.(jpe?g|png|gif|svg|ico|css|js|zip|mp4|mp3|woff2?|ttf|xlsx?|pptx?)(\?|$)')


def log(*a):
    line = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()) + ' ' + ' '.join(str(x) for x in a)
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, 'a', encoding='utf-8', newline='\n') as f:
        f.write(line + '\n')


def keep_awake(on: bool):
    """Hold a system-required power request while the window runs (the laptop sleeps when idle)."""
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | (0x00000001 if on else 0))
    except Exception:
        pass


def minute_utc() -> int:
    t = dt.datetime.now(dt.timezone.utc)
    return t.hour * 60 + t.minute


def in_window() -> bool:
    return WIN[0] <= minute_utc() <= WIN[1]


def load() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding='utf-8'))
    return {'queue': [[0, BASE]], 'seen': [], 'done': [], 'disallow': [], 'found': {}, 'requests': 0}


def save(st: dict):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix('.tmp')
    tmp.write_text(json.dumps(st, ensure_ascii=False, indent=0), encoding='utf-8', newline='\n')
    tmp.replace(STATE)


def read_robots(st: dict) -> bool:
    """Re-read robots.txt alone (fresh). False = stop for good."""
    url = BASE + 'robots.txt'
    p = it_fetch.path_for(url)
    if p.exists():
        p.rename(p.with_name(p.name + '.' + time.strftime('%Y%m%d%H%M%S')))   # keep the earlier copy
    b = it_fetch.get(url)
    st['requests'] += 1
    t = (b or b'').decode('utf-8', 'replace')
    rules, cur = [], False
    rate = window = None
    for ln in t.splitlines():
        ln = ln.split('#', 1)[0].strip()
        if not ln or ':' not in ln:
            continue
        k, v = (x.strip() for x in ln.split(':', 1))
        k = k.lower()
        if k == 'user-agent':
            cur = v == '*'
        elif k == 'disallow' and cur and v:
            rules.append(v)
        elif k == 'request-rate':
            rate = v
        elif k == 'visit-time':
            window = v
    st['disallow'] = rules
    log('robots.txt', len(t), 'bytes; Disallow', len(rules), 'rules; Request-rate', rate, '; Visit-time', window)
    if '/' in rules:
        log('robots now disallows everything: stop')
        return False
    if rate != '1/30' or window != '0600-0845':
        log('robots rate/window changed from 1/30 0600-0845: stop for a person to re-read')
        return False
    return True


def allowed(st: dict, url: str) -> bool:
    s = urlsplit(url)
    if s.netloc.lower() != HOST:
        return False
    path = s.path + (('?' + s.query) if s.query else '')
    return not any(path.startswith(r) for r in st['disallow'])


def prio(url: str, text: str) -> int | None:
    hay = (url + ' ' + text).lower()
    for p, pat in KEYS:
        if re.search(pat, hay):
            return p
    return None


def links(url: str, b: bytes) -> list[tuple[str, str]]:
    t = b.decode('utf-8', 'replace')
    out = []
    for m in re.finditer(r'(?is)<a\b[^>]*href\s*=\s*["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', t):
        href = htmlmod.unescape(m.group(1)).strip()
        if href.lower().startswith(('mailto:', 'javascript:', 'tel:')):
            continue
        txt = ' '.join(htmlmod.unescape(re.sub(r'<[^>]+>', ' ', m.group(2))).split())
        out.append((urljoin(url, href), txt))
    return out


def crawl(once: bool):
    R.below_normal()
    it_fetch.set_gap(HOST, GAP)
    st = load()
    if st.get('finished'):
        log('crawl already finished: nothing to do')
        return
    today = lambda: dt.datetime.now(dt.timezone.utc).date().isoformat()  # noqa: E731
    while True:
        if not in_window():
            if once and st.get('ran_on') == today():
                log('window over: exit (resume tomorrow)')
                save(st)
                return
            time.sleep(30)
            continue
        keep_awake(True)
        try:
            st['ran_on'] = today()
            if not read_robots(st):
                save(st)
                return
            while in_window() and st['queue'] and st['requests'] < MAX_REQUESTS:
                st['queue'].sort(key=lambda x: x[0])
                pr, url = st['queue'].pop(0)
                if url in st['done'] or not allowed(st, url):
                    continue
                R.wait_cpu()
                try:
                    b = it_fetch.get(url, timeout=120)
                except it_fetch.Stopped as e:
                    log('STOPPED', e)
                    save(st)
                    return
                st['requests'] += 1
                st['done'].append(url)
                log('GET', pr, url, len(b or b''), 'bytes')
                if b and not url.lower().endswith('.pdf') and not b.startswith(b'%PDF'):
                    for u, txt in links(url, b):
                        if u in st['seen'] or BINARY.search(u) or not allowed(st, u):
                            continue
                        p = prio(u, txt)
                        if p is None:
                            continue
                        st['seen'].append(u)
                        st['queue'].append([p, u])
                        st['found'].setdefault(str(p), []).append([u, txt[:120]])
                save(st)
            if not st['queue'] or st['requests'] >= MAX_REQUESTS:
                log('crawl finished:', st['requests'], 'requests; queue', len(st['queue']))
                st['finished'] = True
                save(st)
                R.progress(SLUG, f'window crawl finished: {st["requests"]} requests; a person reads the legal-notes '
                                 f'page (gate 3) before the Statuto is built')
                return
        finally:
            keep_awake(False)
        log('window closed:', st['requests'], 'requests so far; queue', len(st['queue']))
        save(st)
        if once:
            return


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    if sys.argv[1] == 'crawl':
        crawl('--once' in sys.argv)
    elif sys.argv[1] == 'status':
        st = load()
        print(json.dumps({'requests': st['requests'], 'queue': len(st['queue']),
                          'found': {k: v[:15] for k, v in st['found'].items()}}, ensure_ascii=False, indent=1))
