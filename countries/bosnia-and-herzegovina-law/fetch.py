"""Downloads the law of Bosnia and Herzegovina (state level) into scripts/bosnia-and-herzegovina-law/.cache/.

    python -X utf8 scripts/bosnia-and-herzegovina-law/fetch.py            # every source in SOURCES below
    python -X utf8 scripts/bosnia-and-herzegovina-law/fetch.py URL ...    # one URL (probe); prints the cache path

Every response is cached under .cache/<sha256 of the URL>, through curl (Python's TLS fails on this machine), at most
3 requests a second per host (the wave's speed rule for official sites), with the User-Agent below, and logged to
.cache/requests.jsonl. Re-running only fetches what is missing.
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
PAUSE = 0.34
_last: dict[str, float] = {}

SOURCES_FILE = HERE / 'sources.json'


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
    wait = _last.get(host, 0) + PAUSE - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    last = None
    for attempt in range(3):
        _last[host] = time.monotonic()
        out = subprocess.run(['curl', '-sS', '-L', '--max-redirs', '4', '--compressed', '-A', UA, '-m', '120',
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
        last = f'{code} {out.stderr.decode(errors="replace").strip()}'
        if code in ('404', '410', '403'):
            break
        time.sleep(60 if code in ('429', '503') else 3)
    raise RuntimeError(f'fetch failed: {url}: {last}')


def main() -> None:
    urls = sys.argv[1:]
    if not urls:
        urls = [s['url'] for s in json.loads(SOURCES_FILE.read_text(encoding='utf-8'))]
    for url in urls:
        try:
            body = fetch(url)
            print(f'{cache_path(url)}  {len(body)}  {url}')
        except Exception as e:  # noqa: BLE001
            print(f'FAILED {url}: {e}')


if __name__ == '__main__':
    main()
