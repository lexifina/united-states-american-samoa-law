"""Downloads San Marino law from the Consiglio Grande e Generale site into scripts/san-marino-law/.cache/.

    python -X utf8 scripts/san-marino-law/fetch.py URL [URL...]     # fetch (or read from cache) and print the path

Every response is cached under .cache/<sha256 of the URL>, through curl (Python's TLS fails on this machine), at
most 3 requests a second per host, with the User-Agent below, and logged to .cache/requests.jsonl. Re-running only
fetches what is missing.
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
PAUSE = 0.4
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
    for attempt in range(4):
        wait = _last.get(host, 0) + PAUSE - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last[host] = time.monotonic()
        tmp = path.with_suffix('.part')
        out = subprocess.run(['curl', '-sS', '--compressed', '-L', '--max-redirs', '4', '-A', UA, '-o', str(tmp),
                              '-w', '%{http_code}', '--max-time', '180', url], capture_output=True, text=True)
        code = out.stdout.strip()
        with open(CACHE / 'requests.jsonl', 'a', encoding='utf-8') as log:
            log.write(json.dumps({'url': url, 'status': code, 'at': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
                                  'sha256': hashlib.sha256(tmp.read_bytes()).hexdigest() if tmp.exists() else None}) + '\n')
        if code == '200':
            tmp.replace(path)
            return path.read_bytes()
        if tmp.exists():
            tmp.unlink()
        if code in ('429', '503'):
            time.sleep(60)
            continue
        if code.startswith('5') or code == '000':
            time.sleep(5)
            continue
        raise RuntimeError(f'{code} {url} {out.stderr}')
    raise RuntimeError(f'gave up: {url}')


if __name__ == '__main__':
    for u in sys.argv[1:]:
        fetch(u)
        print(cache_path(u))
