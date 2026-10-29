"""Fetch Sudan's sources into .cache/ (sha256 of the URL), logging every request to .cache/requests.jsonl.

    python -X utf8 scripts/sudan-law/fetch.py            # everything parse.py needs
    python -X utf8 scripts/sudan-law/fetch.py URL ...    # probe single URLs into the cache

Sources:
- the Ministry of Justice "Sudan laws" ebook (Kotobee EPUB, https://www.moj.gov.sd/sudanlaws/), fetched directly:
  its package.xml, the navigation document and the XHTML chapters for the acts in ACTS below;
- archive.org `id_` captures and Common Crawl, through the shared client scripts/gitlaw_common/wayback.py.

curl, --compressed, the lexifina-watch User-Agent, at most 3 requests a second on moj.gov.sd. Resumable: cached
URLs are never fetched again.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
EPUB = 'https://www.moj.gov.sd/sudanlaws/epub/EPUB/'
_last = [0.0]


def path_for(url: str) -> Path:
    return CACHE / hashlib.sha256(url.encode('utf-8')).hexdigest()


def get(url: str, min_gap: float = 0.34, key: str | None = None) -> bytes | None:
    """key: cache under this URL instead (for signed URLs whose query expires, e.g. WIPO Lex)."""
    hit = path_for(key or url)
    if hit.exists():
        return hit.read_bytes()
    CACHE.mkdir(parents=True, exist_ok=True)
    for attempt in range(4):
        wait = _last[0] + min_gap - time.time()
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        with tempfile.NamedTemporaryFile(delete=False) as f:
            tmp = f.name
        try:
            out = subprocess.run(['curl', '-sS', '-L', '--compressed', '-A', UA, '--max-time', '180',
                                  '-o', tmp, '-w', '%{http_code}', url], capture_output=True, text=True)
            code = int(out.stdout.strip() or 0) if out.returncode == 0 else 0
            body = Path(tmp).read_bytes() if code else b''
        finally:
            Path(tmp).unlink(missing_ok=True)
        with open(CACHE / 'requests.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps({'url': url, 'key': key, 'status': code, 'bytes': len(body),
                                'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}) + '\n')
        if code == 200:
            part = hit.with_suffix('.part')
            part.write_bytes(body)
            os.replace(part, hit)
            return body
        if code == 404:
            return None
        if code in (429, 503):
            min_gap *= 2
            time.sleep(60)
        else:
            time.sleep(2 * (attempt + 1))
    return None


def acts() -> list[dict]:
    return json.loads((HERE / 'acts.json').read_text(encoding='utf-8'))


def main(argv: list[str]) -> None:
    if argv:
        for u in argv:
            b = get(u)
            print(u, None if b is None else len(b))
        return
    get(EPUB + 'package.xml')
    get(EPUB + 'xhtml/contents.html')
    for a in acts():
        for u in a.get('fetch', []):
            b = get(u)
            print(a['slug'], u, None if b is None else len(b))


if __name__ == '__main__':
    main(sys.argv[1:])
