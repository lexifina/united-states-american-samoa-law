"""Equatorial Guinea: cached curl fetcher for the Boletín Oficial del Estado (boe.gob.gq).

    python -X utf8 scripts/equatorial-guinea-law/fetch.py            # the files parse.py reads
    python -X utf8 scripts/equatorial-guinea-law/fetch.py URL ...    # any other file

Files are cached in .cache/ under the sha256 of their URL; every request is logged to .cache/requests.jsonl.
curl only (Python's TLS fails on this machine), --compressed, at most one request per second per host.
"""
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
_last: dict[str, float] = {}

# What parse.py reads. With no arguments, fetch.py downloads exactly these.
BUILD_SOURCES = [
    # Ley 1/2012, de 16 de febrero (Ley Fundamental), the BOE's file uploaded October 2026, linked from its home page
    'https://boe.gob.gq/sites/default/files/2026-10/LEY%20FUNDAMENTAL_0.pdf',
    # Ley 1/2025, de 16 de julio, reforming arts. 56.1, 80 and 84.1 and 2 of the Ley Fundamental
    'https://boe.gob.gq/files/MODIFICACI%C3%93N%20DE%20LA%20LEY%20FUNDAMENTAL.pdf',
]


def path(url: str) -> Path:
    return CACHE / hashlib.sha256(url.encode()).hexdigest()


def get(url: str, refresh: bool = False) -> bytes | None:
    p = path(url)
    if p.exists() and not refresh:
        return p.read_bytes()
    CACHE.mkdir(exist_ok=True)
    host = url.split('/')[2]
    wait = 1.0 - (time.time() - _last.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    _last[host] = time.time()
    tmp = p.with_suffix('.part')
    r = subprocess.run(['curl', '-s', '--compressed', '-L', '-m', '120', '-A', UA, '-o', str(tmp), '-w', '%{http_code}',
                        url], capture_output=True, text=True)
    code = int(r.stdout.strip() or 0)
    size = tmp.stat().st_size if tmp.exists() else 0
    with open(CACHE / 'requests.jsonl', 'a', encoding='utf8') as f:
        f.write(json.dumps({'t': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'url': url, 'code': code,
                            'bytes': size}) + '\n')
    if code != 200:
        tmp.unlink(missing_ok=True)
        return None
    tmp.replace(p)
    return p.read_bytes()


if __name__ == '__main__':
    for u in sys.argv[1:] or BUILD_SOURCES:
        b = get(u)
        print(u, None if b is None else len(b), path(u).name, hashlib.sha256(b).hexdigest() if b else '')
