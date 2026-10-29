"""Angola git-for-law: polite, cached, resumable fetcher.

Every download goes through curl (Python TLS fails on this machine), is cached under .cache/ by the sha256 of the URL,
and is logged to .cache/requests.jsonl. At most 1 request per second per government host. archive.org, if ever
needed, goes only through scripts/gitlaw_common/wayback.py (one adaptive machine-wide rate).

    python -X utf8 scripts/angola-law/fetch.py            # fetch everything in sources.json
    python -X utf8 scripts/angola-law/fetch.py URL ...     # fetch (or show the cached path of) single URLs
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'gitlaw_common'))
import wayback  # noqa: E402

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
_last: dict[str, float] = {}


def cache_path(url: str) -> Path:
    return CACHE / hashlib.sha256(url.encode('utf-8')).hexdigest()


def _wait(host: str) -> None:
    gap = time.time() - _last.get(host, 0)
    if gap < 1.0:
        time.sleep(1.0 - gap)
    _last[host] = time.time()


def get(url: str, refresh: bool = False) -> Path:
    CACHE.mkdir(exist_ok=True)
    gi = CACHE / '.gitignore'
    if not gi.exists():
        gi.write_text('*\n', encoding='utf-8')
    out = cache_path(url)
    if out.exists() and not refresh:
        return out
    host = urlparse(url).netloc
    if 'archive.org' in host:
        # archive.org only through the shared client: one adaptive machine-wide rate (coordinator, 2026-10-28).
        body = wayback.fetch(url, cache=CACHE)
        if body is None:
            raise RuntimeError(f'404 {url}')
        out.write_bytes(body)
        return out
    _wait(host)
    tmp = out.with_suffix('.part')
    t0 = time.time()
    r = subprocess.run(['curl', '-s', '-L', '--compressed', '-m', '180', '-A', UA, '-o', str(tmp),
                        '-w', '%{http_code} %{content_type}', url], capture_output=True, text=True)
    status, _, ctype = (r.stdout or '000 ').partition(' ')
    size = tmp.stat().st_size if tmp.exists() else 0
    with open(CACHE / 'requests.jsonl', 'a', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps({'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(t0)), 'url': url,
                            'status': status, 'type': ctype, 'bytes': size,
                            'sha256': hashlib.sha256(tmp.read_bytes()).hexdigest() if size else None}) + '\n')
    if status != '200' or not size:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f'{status} {url}')
    os.replace(tmp, out)
    return out


def main(argv: list[str]) -> None:
    src = json.loads((HERE / 'sources.json').read_text(encoding='utf-8'))
    urls = argv or list(dict.fromkeys([v['url'] for k, v in src.items() if k != 'checks']
                                      + [v['url'] for v in src.get('checks', {}).values()]))
    for u in urls:
        try:
            print(get(u), u)
        except RuntimeError as e:
            print('FAILED', e)


if __name__ == '__main__':
    main(sys.argv[1:])
