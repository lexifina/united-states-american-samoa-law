"""Downloads the law of Benin into scripts/benin-law/.cache/.

    python -X utf8 scripts/benin-law/fetch.py URL [URL...]   # fetch (or re-read) single URLs
    python -X utf8 scripts/benin-law/fetch.py --all          # every URL parse.py needs (sources.json)

Every response is cached under .cache/<sha256 of the URL>, through curl (Python's TLS fails on this machine), with
the User-Agent below, and logged to .cache/requests.jsonl. Re-running only fetches what is missing.

Politeness: sgg.gouv.bj at most 3 requests a second (coordinator speed rule, 2026-10-28); on 429/503 the pause
doubles and the request waits 60 s. assemblee-nationale.bj and documentation-anbenin.org state
Crawl-delay: 10 in robots.txt, so they get 10.5 s.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
PAUSES: dict[str, float] = {'assemblee-nationale.bj': 10.5, 'documentation-anbenin.org': 10.5}  # robots.txt Crawl-delay: 10
PAUSE = 0.34
_last: dict[str, float] = {}


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
    host = urlsplit(url).netloc
    code = ''
    for attempt in range(4):
        pause = PAUSES.get(host, PAUSE)
        wait = _last.get(host, 0) + pause - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last[host] = time.monotonic()
        out = subprocess.run(['curl', '-sS', '-L', '--max-redirs', '5', '--compressed', '-A', UA, '-m', '300',
                              '-w', '\n%{http_code}', url], capture_output=True)
        body, _, code = out.stdout.rpartition(b'\n')
        code = code.decode().strip()
        with open(CACHE / 'requests.jsonl', 'a', encoding='utf-8') as log:
            log.write(json.dumps({'url': url, 'status': code, 'bytes': len(body),
                                  'at': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                                  'sha256': hashlib.sha256(body).hexdigest()}) + '\n')
        if code == '200':
            path.write_bytes(body)
            return body
        if code in ('429', '503'):
            PAUSES[host] = PAUSES.get(host, PAUSE) * 2
            time.sleep(60)
            continue
        break
    raise RuntimeError(f'HTTP {code} for {url}')


def main(argv: list[str]) -> None:
    if argv and argv[0] == '--all':
        urls = [s['url'] for s in json.loads((HERE / 'sources.json').read_text(encoding='utf-8'))['documents']]
    else:
        urls = argv
    for url in urls:
        body = fetch(url)
        print(len(body), cache_path(url).name[:12], url)


if __name__ == '__main__':
    main(sys.argv[1:])
