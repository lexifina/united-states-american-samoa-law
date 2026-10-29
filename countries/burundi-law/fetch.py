"""Burundi (BI): fetch layer.

Direct official hosts (presidence.gov.bi, assemblee.bi) through curl --compressed, at most 3 requests a second per
host (coordinator's speed rule; halved for 60 s on any 429/503), cached under .cache/ by the sha256 of the URL and
logged to .cache/requests.jsonl. Common Crawl and archive.org go through the shared client
scripts/gitlaw_common/wayback.py, which caches and logs into the same folder. Resumable: a cached answer is never
fetched again.

    python -X utf8 fetch.py                 # fetch everything parse.py needs (GETS below)
    python -X utf8 fetch.py URL ...         # fetch (and cache) given URLs, printing size and content type
"""
import datetime as dt
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
sys.path.insert(0, str(HERE.parent / 'gitlaw_common'))
import wayback  # noqa: E402

_last: dict = {}
_delay: dict = {}


def path_of(url: str) -> Path:
    return CACHE / hashlib.sha256(url.encode('utf-8')).hexdigest()


def get(url: str, offline: bool = False) -> bytes | None:
    """One direct GET, cached by the sha256 of the URL. None on 404."""
    f = path_of(url)
    if f.exists():
        return f.read_bytes()
    if (f.with_suffix('.404')).exists():
        return None
    if offline:
        raise SystemExit(f'offline: {url} is not in the cache; run fetch.py')
    CACHE.mkdir(exist_ok=True)
    (CACHE / '.gitignore').write_text('*\n', encoding='utf-8', newline='\n')
    host = urlparse(url).netloc
    for attempt in range(5):
        wait = _delay.get(host, 0.34) - (time.time() - _last.get(host, 0.0))
        if wait > 0:
            time.sleep(wait)
        tmp = f.with_suffix('.tmp')
        r = subprocess.run(['curl', '-sS', '-L', '--compressed', '-m', '300', '-A', UA, '-o', str(tmp),
                            '-w', '%{http_code} %{content_type}', url], capture_output=True)
        _last[host] = time.time()
        code, _, ctype = r.stdout.decode(errors='replace').partition(' ')
        if r.returncode == 0 and code == '200':
            body = tmp.read_bytes()
            tmp.replace(f)
            _log({'url': url, 'status': 200, 'content_type': ctype, 'bytes': len(body),
                  'sha256': hashlib.sha256(body).hexdigest(), 'file': f.name})
            return body
        if code == '404':
            _log({'url': url, 'status': 404})
            f.with_suffix('.404').write_text('', encoding='utf-8')
            tmp.unlink(missing_ok=True)
            return None
        if code in ('429', '503'):
            _delay[host] = min(_delay.get(host, 0.34) * 2, 8)
            time.sleep(60)
        else:
            time.sleep(3 * (attempt + 1))
    _log({'url': url, 'status': code, 'error': r.stderr.decode(errors='replace')[:200]})
    return None


def _log(rec: dict) -> None:
    rec = {'at': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'requests': 1, **rec}
    with (CACHE / 'requests.jsonl').open('a', encoding='utf-8', newline='\n') as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + '\n')


def sha256(url: str) -> str:
    return hashlib.sha256(path_of(url).read_bytes()).hexdigest()


# Every official document parse.py reads (filled in as acts are chosen).
GETS: list = []


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    for u in (sys.argv[1:] or GETS):
        b = get(u)
        print(len(b) if b is not None else None, b[:8] if b else b'', u)
