"""Common Crawl lookups straight from the CDN (data.commoncrawl.org), for when index.commoncrawl.org is unreachable.

Each crawl's CDX index is published as cdx-00000.gz .. cdx-00299.gz (gzip members of about 3,000 lines each) plus
cluster.idx, a sorted list of the first SURT key of every member with its file, offset and length. This bisects
cluster.idx with HTTP range requests, reads only the members that can hold the prefix, and returns the same records
index.commoncrawl.org would ({'urlkey','timestamp','url','status','mime','digest','filename','offset','length',
'crawl'}), so wayback.cc_get() reads the page bytes. Every response is cached by the sha256 of its URL + range.

    python -X utf8 ccindex.py nz,govt,legislation)/act/public/1990/0109/ CC-MAIN-2024-10 CC-MAIN-2023-50
"""
from __future__ import annotations

import gzip
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

DATA = 'https://data.commoncrawl.org/'
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
CHUNK = 1 << 16


def _get(url: str, rng: tuple[int, int] | None, cache: Path) -> bytes:
    key = url + (f' bytes={rng[0]}-{rng[1]}' if rng else '')
    p = cache / hashlib.sha256(key.encode()).hexdigest()
    if p.exists():
        return p.read_bytes()
    cmd = ['curl', '-gsS', '--max-time', '120', '-A', UA, url]
    if rng:
        cmd[1:1] = ['-r', f'{rng[0]}-{rng[1]}']
    for i in range(4):
        out = subprocess.run(cmd, capture_output=True)
        if out.returncode == 0 and out.stdout and not out.stdout.startswith(b'<?xml'):
            break
        time.sleep(2 * (i + 1))
    else:
        raise RuntimeError(f'failed {key}')
    tmp = p.with_suffix('.part')
    tmp.write_bytes(out.stdout)
    tmp.replace(p)
    with open(cache / 'requests.jsonl', 'a', encoding='utf-8') as f:
        f.write(json.dumps({'url': key, 'status': 206 if rng else 200, 'bytes': len(out.stdout),
                            'sha256': p.name}) + '\n')
    return out.stdout


def _size(url: str, cache: Path) -> int:
    p = cache / (hashlib.sha256(('HEAD ' + url).encode()).hexdigest())
    if p.exists():
        return int(p.read_text())
    out = subprocess.run(['curl', '-gsSI', '--max-time', '60', '-A', UA, url], capture_output=True, text=True)
    n = [int(l.split(':')[1]) for l in out.stdout.splitlines() if l.lower().startswith('content-length:')]
    if not n:
        raise RuntimeError(f'no size for {url}')
    p.write_text(str(n[-1]))
    return n[-1]


def _lines_at(url: str, off: int, cache: Path) -> list[str]:
    """Whole lines that start inside the 64 KiB chunk at off."""
    b = _get(url, (off, off + CHUNK - 1), cache)
    s = b.decode('utf-8', 'replace').split('\n')
    if off > 0:
        s = s[1:]
    return [l for l in s[:-1] if l]


def captures(prefix: str, crawl: str, cache: Path | str) -> list[dict]:
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    idx = f'{DATA}cc-index/collections/{crawl}/indexes/cluster.idx'
    size = _size(idx, cache)
    lo, hi = 0, size  # find the last block whose first key < prefix
    while hi - lo > CHUNK:
        mid = (lo + hi) // 2
        ls = _lines_at(idx, mid, cache)
        if not ls or ls[0].split('\t')[0] >= prefix:
            hi = mid
        else:
            lo = mid
    ls = _lines_at(idx, lo, cache)
    if hi < size:
        ls += _lines_at(idx, hi, cache)
    rows = [l.split('\t') for l in ls]
    start = 0
    for i, r in enumerate(rows):
        if r[0] < prefix:
            start = i
    blocks = []
    for r in rows[start:]:
        if r[0] < prefix or r[0].startswith(prefix) or not blocks:
            blocks.append(r)
        else:
            break
    out = []
    for r in blocks:
        f, o, n = r[1], int(r[2]), int(r[3])
        raw = _get(f'{DATA}cc-index/collections/{crawl}/indexes/{f}', (o, o + n - 1), cache)
        for line in gzip.decompress(raw).decode('utf-8', 'replace').splitlines():
            k, ts, js = line.split(' ', 2)
            if k.startswith(prefix):
                rec = json.loads(js)
                rec.update(urlkey=k, timestamp=ts, crawl=crawl)
                out.append(rec)
    return out


if __name__ == '__main__':
    c = Path(__file__).parent / '.cache' / 'ccindex'
    for crawl in sys.argv[2:]:
        for r in captures(sys.argv[1], crawl, c):
            print(crawl, r['timestamp'], r.get('status'), r['url'])
