"""Downloads the law of Mali into scripts/mali-law/.cache/.

    python -X utf8 scripts/mali-law/fetch.py URL [URL...]   # fetch (or re-read) single URLs
    python -X utf8 scripts/mali-law/fetch.py --all          # every URL parse.py needs (sources.json)

Every response is cached under .cache/<sha256 of the URL>, through curl (Python's TLS fails on this machine), with
the User-Agent below, and logged to .cache/requests.jsonl. Re-running only fetches what is missing.

Politeness: at most 3 requests a second to sgg-mali.ml (the coordinator's speed rule for official sources), up to 3 in
parallel; on a 429 or 503 the pause doubles and the request waits 60 s.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
PAUSE = {'default': 0.34}
_last: dict[str, float] = {}
_lock = threading.Lock()
_log_lock = threading.Lock()


def cache_path(url: str) -> Path:
    return CACHE / hashlib.sha256(url.encode()).hexdigest()


def _slot(host: str) -> None:
    while True:
        with _lock:
            pause = PAUSE.get(host, PAUSE['default'])
            wait = _last.get(host, 0) + pause - time.monotonic()
            if wait <= 0:
                _last[host] = time.monotonic()
                return
        time.sleep(wait)


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
        _slot(host)
        out = subprocess.run(['curl', '-sS', '-L', '--max-redirs', '5', '--compressed', '-A', UA, '-m', '300',
                              '-w', '\n%{http_code}', url], capture_output=True)
        body, _, code = out.stdout.rpartition(b'\n')
        code = code.decode().strip()
        with _log_lock, open(CACHE / 'requests.jsonl', 'a', encoding='utf-8') as log:
            log.write(json.dumps({'url': url, 'status': code, 'bytes': len(body),
                                  'at': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                                  'sha256': hashlib.sha256(body).hexdigest()}) + '\n')
        if code == '200':
            tmp = path.with_suffix('.part')
            tmp.write_bytes(body)
            tmp.replace(path)
            return body
        if code in ('429', '503'):
            with _lock:
                PAUSE[host] = PAUSE.get(host, PAUSE['default']) * 2
            time.sleep(60)
            continue
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f'{url}: HTTP {code}')


def fetch_many(urls: list[str], threads: int = 3) -> dict[str, bytes | Exception]:
    def one(u):
        try:
            return u, fetch(u)
        except Exception as e:  # noqa: BLE001
            return u, e
    with ThreadPoolExecutor(threads) as ex:
        return dict(ex.map(one, urls))


def main(argv: list[str]) -> None:
    if argv and argv[0] == '--all':
        urls = [s['url'] for s in json.loads((HERE / 'sources.json').read_text(encoding='utf-8'))['files']]
    else:
        urls = argv
    for u, r in fetch_many(urls).items():
        print(('ERR ' + str(r)) if isinstance(r, Exception) else f'{len(r):>10}', u)


if __name__ == '__main__':
    main(sys.argv[1:])
