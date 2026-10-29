"""Downloads the sources for the law of the Democratic Republic of the Congo into scripts/dr-congo-law/.cache/.

    python -X utf8 scripts/dr-congo-law/fetch.py URL [URL...]   # fetch (or re-read) single URLs
    python -X utf8 scripts/dr-congo-law/fetch.py --all          # every URL in sources.json

Every response is cached under .cache/<sha256 of the URL>, through curl (Python's TLS fails on this machine), with
the User-Agent below, and logged to .cache/requests.jsonl. Re-running fetches only what is missing.

Politeness (coordinator SPEED RULE, 2026-10-28): direct sources at most 3 requests a second per host; on a 429 or
503 the pause doubles and the fetcher waits 60 s. archive.org goes only through gitlaw_common/wayback.py.
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
_pause: dict[str, float] = {}
_last: dict[str, float] = {}


def cache_path(url: str) -> Path:
    return CACHE / hashlib.sha256(url.encode('utf-8')).hexdigest()


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
        pause = _pause.setdefault(host, 0.34)
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
        if out.returncode == 0 and code == '200' and body.strip():
            tmp = path.with_suffix('.tmp')
            tmp.write_bytes(body)
            tmp.replace(path)
            return body
        if code in ('404', '403', '410'):
            break
        if code in ('429', '503'):
            _pause[host] = pause * 2
            time.sleep(60)
        else:
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f'{url}: http {code}')


def main(argv: list[str]) -> None:
    if argv == ['--all']:
        urls = [s['url'] for s in json.loads((HERE / 'sources.json').read_text(encoding='utf-8'))['files']]
    else:
        urls = argv
    for u in urls:
        try:
            b = fetch(u)
            print(len(b), hashlib.sha256(b).hexdigest()[:12], u)
        except Exception as e:  # noqa: BLE001
            print('FAIL', u, e)


if __name__ == '__main__':
    main(sys.argv[1:])
