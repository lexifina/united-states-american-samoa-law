"""Fetch the official Turkmen texts for the Turkmenistan law history into .cache/.

Direct official source: the Mejlis of Turkmenistan (mejlis.gov.tm), which serves the full text of laws and codes
as HTML. Archived copies (Common Crawl first, archive.org second) go through the shared client
scripts/gitlaw_common/wayback.py and land in the same cache.

Every response is cached under .cache/<sha256(url)> and logged to .cache/requests.jsonl. Resumable: cached URLs
are never fetched again. At most 3 requests a second to the Mejlis (coordinator SPEED RULE).

    python -X utf8 scripts/turkmenistan-law/fetch.py
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
sys.path.insert(0, str(HERE.parent / 'gitlaw_common'))
import wayback  # noqa: E402

# Direct official pages (Turkmen, the official language).
MEJLIS = [
    'https://mejlis.gov.tm/single-law/107?lang=tm',   # Constitution, 2016 revision, consolidated to 2023
    'https://mejlis.gov.tm/single-code/6?lang=tm',    # Civil Code (Raýat kodeksi) 2025
    'https://mejlis.gov.tm/single-code/27?lang=tm',   # Criminal Code (Jenaýat kodeksi), revised edition 2022
    'https://mejlis.gov.tm/codes?lang=tm&ajax=true',  # list of codes
    'https://mejlis.gov.tm/laws?lang=tm&ajax=true',   # list of laws
]

# Archived captures pinned by Common Crawl record (crawl, WARC file, offset, length): see sources.json.
SOURCES = HERE / 'sources.json'

_last = [0.0]


def cache_path(url: str) -> Path:
    return CACHE / hashlib.sha256(url.encode('utf-8')).hexdigest()


def log(url: str, code: int, size: int) -> None:
    with open(CACHE / 'requests.jsonl', 'a', encoding='utf-8') as f:
        f.write(json.dumps({'url': url, 'status': code, 'bytes': size,
                            'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'via': 'fetch.py'}) + '\n')


def get(url: str) -> bytes | None:
    hit = cache_path(url)
    if hit.exists():
        return hit.read_bytes()
    wait = _last[0] + 0.34 - time.time()
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()
    with tempfile.NamedTemporaryFile(delete=False) as f:
        tmp = f.name
    try:
        out = subprocess.run(['curl', '-sS', '-L', '--compressed', '-A', UA, '--max-time', '120', '-o', tmp,
                              '-w', '%{http_code}', url], capture_output=True, text=True)
        code = int(out.stdout.strip() or 0) if out.returncode == 0 else 0
        body = Path(tmp).read_bytes() if code else b''
    finally:
        Path(tmp).unlink(missing_ok=True)
    log(url, code, len(body))
    if code != 200:
        print('FAIL', code, url)
        return None
    part = hit.with_suffix('.part')
    part.write_bytes(body)
    os.replace(part, hit)
    return body


def main() -> None:
    CACHE.mkdir(exist_ok=True)
    (CACHE / '.gitignore').write_text('*\n', encoding='utf-8')
    for u in MEJLIS:
        b = get(u)
        print(len(b or b''), u)
    if SOURCES.exists():
        for s in json.loads(SOURCES.read_text(encoding='utf-8')):
            if 'cc' in s:
                b = wayback.cc_get(s['cc'], cache=CACHE)
            elif 'wayback' in s:
                b = wayback.get(s['url'], ts=s['wayback'], cache=CACHE)
            else:
                b = get(s['url'])
            print(len(b or b''), s['key'])


if __name__ == '__main__':
    main()
