"""Downloads Albanian law from Qendra e Botimeve Zyrtare (qbz.gov.al) into scripts/albania-law/.cache/.

    python -X utf8 scripts/albania-law/fetch.py            # everything parse.py needs
    python -X utf8 scripts/albania-law/fetch.py URL ...    # one-off URLs into the same cache

qbz.gov.al is an Angular app over an open JSON API (https://qbz.gov.al/api/v1, no login):

  /acts/{id}                    one act: gazette year and number, dates, pdf.url and word.url (a free .docx)
  /publications?type=kushtetuta the consolidated Constitution (PDF, with a text layer)
  /gazettes/{year}/{number}     one issue of the Fletorja Zyrtare

and, from the Internet Archive (parse.ARCHIVE), the Assembly's 1998 text and QBZ's 2008-2016 editions.

Every response is cached under .cache/<sha256 of the URL>, through curl (Python's TLS fails on this machine), at most
3 requests a second, with the User-Agent below, and logged to .cache/requests.jsonl. Re-running only fetches what is
missing.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
API = 'https://qbz.gov.al/api/v1'
SITE = 'https://qbz.gov.al'
PAUSE = 0.34
_last = [0.0]

# qbz act ids of the laws parse.py replays (see sources.json for what each is).
ACT_IDS = [5051, 6511, 8604, 12702, 15530, 22000, 24124]
PUBLICATIONS = ['kushtetuta']


def cache_path(url: str) -> Path:
    return CACHE / hashlib.sha256(url.encode()).hexdigest()


def fetch(url: str, offline: bool = False) -> bytes:
    path = cache_path(url)
    if path.exists():
        return path.read_bytes()
    if offline:
        raise FileNotFoundError(f'not cached: {url}')
    CACHE.mkdir(exist_ok=True)
    gi = CACHE / '.gitignore'
    if not gi.exists():
        gi.write_text('*\n')
    for attempt in range(4):
        wait = _last[0] + PAUSE - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.monotonic()
        out = subprocess.run(['curl', '-sS', '-L', '--max-redirs', '4', '--compressed', '-A', UA, '-m', '300',
                              '-w', '\n%{http_code}', url], capture_output=True)
        body, _, code = out.stdout.rpartition(b'\n')
        code = code.decode().strip()
        with open(CACHE / 'requests.jsonl', 'a', encoding='utf-8') as log:
            log.write(json.dumps({'url': url, 'status': code, 'bytes': len(body),
                                  'at': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                                  'sha256': hashlib.sha256(body).hexdigest()}) + '\n')
        if out.returncode == 0 and code == '200' and body.strip():
            tmp = path.with_suffix('.tmp')
            tmp.write_bytes(body)
            tmp.replace(path)
            return body
        if code in ('429', '503'):
            time.sleep(60)
        else:
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f'fetch failed ({code}): {url}')


def fetch_json(url: str, offline: bool = False):
    return json.loads(fetch(url, offline))


def act(act_id: int, offline: bool = False) -> dict:
    return fetch_json(f'{API}/acts/{act_id}', offline)


def act_docx(act_id: int, offline: bool = False) -> bytes:
    return fetch(SITE + act(act_id, offline)['word']['url'], offline)


def gazette(year: int, number: str, offline: bool = False) -> dict:
    """One issue of the Fletorja Zyrtare: publishDate and the issue's PDF (whose masthead parse.py checks)."""
    return fetch_json(f'{API}/gazettes/{year}/{number}', offline)['gazette']


def publication(kind: str, offline: bool = False) -> tuple[dict, bytes]:
    meta = fetch_json(f'{API}/publications?type={kind}', offline)[0]
    return meta, fetch(SITE + meta['pdf']['url'], offline)


def main(argv: list[str]) -> None:
    if argv:
        for url in argv:
            print(len(fetch(url)), url)
        return
    for i in ACT_IDS:
        a = act(i)
        g = gazette(a['gazette']['year'], a['gazette']['number'])
        print(i, a.get('number'), a.get('title', '')[:70], len(act_docx(i)), len(fetch(SITE + g['pdf']['url'])))
    for kind in PUBLICATIONS:
        meta, pdf = publication(kind)
        print(kind, meta['id'], len(pdf))
    # Internet Archive captures (the 1998 text and QBZ's older editions), through the shared, rate-limited client
    sys.path.insert(0, str(HERE.parent / 'gitlaw_common'))
    try:
        import wayback
    except ImportError:
        sys.exit('The Internet Archive captures need scripts/gitlaw_common/wayback.py from the Lexifina repository '
                 '(run this script from scripts/albania-law/ there).')
    from parse import ARCHIVE
    for name, (ts, url) in ARCHIVE.items():
        body = wayback.get(url, ts=ts, cache=CACHE)
        print(name, ts, None if body is None else len(body))


if __name__ == '__main__':
    main(sys.argv[1:])
