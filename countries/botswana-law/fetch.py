"""Downloads Botswana law into scripts/botswana-law/.cache/.

    python -X utf8 scripts/botswana-law/fetch.py URL [URL...]   # fetch (or re-read) single URLs
    python -X utf8 scripts/botswana-law/fetch.py --all          # every URL parse.py needs (sources.json)

Every response is cached under .cache/<sha256 of the URL> and logged to .cache/requests.jsonl.
- archive.org (Wayback `id_` captures, CDX) goes through the shared machine-wide adaptive client
  scripts/gitlaw_common/wayback.py (coordinator, 2026-10-28: no per-agent archive.org delays);
- Common Crawl captures go through wayback.cc_get (cache key `cc:<file>:<offset>:<length>`);
- any other host: curl, at most one request per second per host, with the User-Agent below.
Re-running only fetches what is missing.
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
sys.path.insert(0, str(HERE.parent / 'gitlaw_common'))
import wayback  # noqa: E402

UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
PAUSE = 1.1
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
    if host.endswith('archive.org'):
        body = wayback.fetch(url, CACHE)
        if body is None:
            raise RuntimeError(f'{url}: not available')
        return body
    code = ''
    for attempt in range(4):
        wait = _last.get(host, 0) + PAUSE - time.monotonic()
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
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f'{url}: http {code}')


def cdx(url: str, offline: bool = False, extra: str = '') -> list[list[str]]:
    """Wayback captures of url (timestamp, original, statuscode, digest), one per distinct digest."""
    q = (f'https://web.archive.org/cdx/search/cdx?url={url}&output=json'
         f'&fl=timestamp,original,statuscode,digest&collapse=digest{extra}')
    rows = json.loads(fetch(q, offline) or b'[]')
    return rows[1:]


def wayback_raw(ts: str, original: str, offline: bool = False) -> bytes:
    """The raw bytes of one Wayback capture (the id_ form, without the Wayback toolbar)."""
    return fetch(f'https://web.archive.org/web/{ts}id_/{original}', offline)


def all_urls() -> list[str]:
    src = json.loads((HERE / 'sources.json').read_text(encoding='utf-8'))
    return [u for u in src.get('urls', [])]


def main(argv: list[str]) -> None:
    urls = all_urls() if argv == ['--all'] else argv
    for u in urls:
        try:
            b = fetch(u)
            print(f'ok {len(b):>9} {u}', flush=True)
        except Exception as e:  # noqa: BLE001
            print(f'FAIL {u}: {e}', flush=True)


if __name__ == '__main__':
    main(sys.argv[1:])
