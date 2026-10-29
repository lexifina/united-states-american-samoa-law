"""Cabo Verde fetcher: curl into .cache/ (sha256 of the URL), resumable, polite, every request logged.

    python -X utf8 scripts/cabo-verde-law/fetch.py URL [URL ...]   # fetch (or reuse) and print the cache path
    python -X utf8 scripts/cabo-verde-law/fetch.py --all            # every URL listed in sources.json

Rates: 1 request per second per host. archive.org goes only through scripts/gitlaw_common/wayback.py (one adaptive
rate for the whole machine), and Common Crawl through wayback.cc_get.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'gitlaw_common'))
import wayback  # noqa: E402

CACHE = HERE / '.cache'
LOG = CACHE / 'requests.jsonl'
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
_last: dict[str, float] = {}


def key(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def path_for(url: str) -> Path:
    return CACHE / key(url)


def _wait(host: str) -> None:
    gap = time.time() - _last.get(host, 0.0)
    if gap < 1.0:
        time.sleep(1.0 - gap)
    _last[host] = time.time()


def get(url: str, refresh: bool = False, timeout: int = 120) -> Path | None:
    """Return the cache path of url's body, fetching it once. None if the fetch failed (non-2xx)."""
    CACHE.mkdir(exist_ok=True)
    p = path_for(url)
    if p.exists() and not refresh:
        return p
    host = urlparse(url).hostname or ''
    if host.endswith('archive.org'):
        body = wayback.fetch(url, cache=CACHE)
        return p if body is not None and p.exists() else None
    tmp = p.with_suffix('.part')
    for attempt in range(3):
        _wait(host)
        r = subprocess.run(['curl', '-s', '-L', '--compressed', '-A', UA, '-m', str(timeout), '-o', str(tmp),
                            '-w', '%{http_code}\t%{content_type}\t%{size_download}\t%{url_effective}', url],
                           capture_output=True, text=True)
        code, ctype, size, eff = (r.stdout.split('\t') + ['', '', '', ''])[:4]
        with LOG.open('a', encoding='utf-8') as f:
            f.write(json.dumps({'t': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'url': url, 'status': code,
                                'type': ctype, 'bytes': size, 'effective': eff, 'curl_exit': r.returncode,
                                'sha256_url': key(url)}) + '\n')
        if code.startswith('2') and tmp.exists():
            os.replace(tmp, p)
            return p
        if code in ('404', '403', '410'):
            break
        time.sleep(5 * (attempt + 1))
    if tmp.exists():
        tmp.unlink()
    return None


def main(argv: list[str]) -> int:
    urls = argv
    if argv == ['--all']:
        src = json.loads((HERE / 'sources.json').read_text(encoding='utf-8'))
        urls = [d['url'] for d in src['documents']]
    bad = 0
    for u in urls:
        p = get(u)
        print(p if p else f'FAILED {u}')
        bad += p is None
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
