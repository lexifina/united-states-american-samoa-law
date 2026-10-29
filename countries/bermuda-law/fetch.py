"""Bermuda: fetch every dated consolidation of the Phase 1 acts into .cache/.

Sources, in order:
1. Bermuda Laws Online (bermudalaws.bm), today's consolidated PDF of each act, fetched directly (1 request/second).
2. Internet Archive `id_` captures of the same consolidated PDFs under both URL layouts the site has used
   (`/Laws/Consolidated Laws/<title>.pdf` until 2024, `/Laws/Consolidated Law/<year>/<title>` since), through the
   shared machine-wide client gitlaw_common/wayback.py. One capture per distinct content digest.
3. Common Crawl captures of the same URLs, through the same client (byte ranges from the CDN).
4. The annual (as enacted / as made) PDFs of the amending instruments that parse.py needs, fetched directly.

Writes snapshots.json (the manifest parse.py reads) beside this file. Resumable: everything is cached by the sha256
of its URL, and every request is logged to .cache/requests.jsonl.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
sys.path.insert(0, str(HERE.parent / 'gitlaw_common'))
import wayback  # noqa: E402

UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
SITE = 'https://www.bermudalaws.bm'

ACTS = {
    'constitution': ('1968', 'Bermuda Constitution Order 1968'),
    'criminal-code': ('1907', 'Criminal Code Act 1907'),
    'pipa': ('2016', 'Personal Information Protection Act 2016'),
}

# Annual laws (as enacted / as made) fetched directly: (key, path under /Laws/Annual Law/)
ANNUAL: list[tuple[str, str]] = []
if (HERE / 'annual.json').exists():
    ANNUAL = [tuple(x) for x in json.loads((HERE / 'annual.json').read_text(encoding='utf-8'))]

_last = [0.0]


def cache_path(url: str) -> Path:
    return CACHE / hashlib.sha256(url.encode('utf-8')).hexdigest()


def log(url: str, code: int, size: int) -> None:
    with open(CACHE / 'requests.jsonl', 'a', encoding='utf-8') as f:
        f.write(json.dumps({'url': url, 'status': code, 'bytes': size,
                            'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'via': 'fetch.py'}) + '\n')


def direct(url: str) -> bytes | None:
    """GET an official page with curl, 1 request a second, cached by sha256(url)."""
    p = cache_path(url)
    if p.exists():
        return p.read_bytes()
    wait = _last[0] + 1.0 - time.time()
    if wait > 0:
        time.sleep(wait)
    tmp = p.with_suffix('.part')
    out = subprocess.run(['curl', '-sS', '-L', '--compressed', '-A', UA, '--max-time', '180', '-o', str(tmp),
                          '-w', '%{http_code}', url], capture_output=True, text=True)
    _last[0] = time.time()
    code = int(out.stdout.strip() or 0)
    size = tmp.stat().st_size if tmp.exists() else 0
    log(url, code, size)
    if code != 200:
        tmp.unlink(missing_ok=True)
        return None
    tmp.replace(p)
    return p.read_bytes()


def live_url(year: str, title: str) -> str:
    return f'{SITE}/Laws/Consolidated%20Law/{year}/{quote(title)}'


def old_url(title: str) -> str:
    return f'http://www.bermudalaws.bm/Laws/Consolidated%20Laws/{quote(title)}.pdf'


def main() -> None:
    CACHE.mkdir(exist_ok=True)
    (CACHE / '.gitignore').write_text('*\n')
    retrieved = time.strftime('%Y-%m-%d', time.gmtime())
    prev = {}
    if (HERE / 'snapshots.json').exists():
        prev = json.loads((HERE / 'snapshots.json').read_text(encoding='utf-8'))
    manifest: dict = {'acts': {}, 'annual': {}}
    crawls = wayback.cc_crawls(CACHE)
    for slug, (year, title) in ACTS.items():
        snaps = []
        # 1. live
        url = live_url(year, title)
        body = direct(url)
        if body and body[:4] == b'%PDF':
            old = {s['url']: s for s in prev.get('acts', {}).get(slug, []) if s['via'] == 'live'}
            snaps.append({'via': 'live', 'url': url, 'date': old.get(url, {}).get('date', retrieved),
                          'sha256': hashlib.sha256(body).hexdigest(), 'file': cache_path(url).name})
        # 2. Internet Archive
        seen = set()
        for orig in (old_url(title), live_url(year, title)):
            for c in wayback.captures(orig.split('://', 1)[1], cache=CACHE):
                if 'pdf' not in c['mimetype'] or c['digest'] in seen:
                    continue
                seen.add(c['digest'])
                raw = wayback.get(c['original'], ts=c['timestamp'], cache=CACHE)
                if not raw or raw[:4] != b'%PDF':
                    continue
                aurl = f'https://web.archive.org/web/{c["timestamp"]}id_/{c["original"]}'
                ts = c['timestamp']
                snaps.append({'via': 'archive.org', 'url': aurl, 'original': c['original'],
                              'date': f'{ts[:4]}-{ts[4:6]}-{ts[6:8]}', 'timestamp': ts,
                              'sha256': hashlib.sha256(raw).hexdigest(), 'file': cache_path(aurl).name})
        # 3. Common Crawl
        recs = []
        def idx(crawl, orig):
            return wayback.cc_captures(orig.split('://', 1)[1], crawls=[crawl], cache=CACHE)
        with ThreadPoolExecutor(8) as ex:
            futs = [ex.submit(idx, cr, o) for cr in crawls for o in (old_url(title), live_url(year, title))]
            for f in futs:
                recs.extend(f.result() or [])
        for r in recs:
            if str(r.get('status')) != '200' or r.get('digest') in seen:
                continue
            seen.add(r['digest'])
            raw = wayback.cc_get(r, cache=CACHE)
            if not raw or raw[:4] != b'%PDF':
                continue
            key = f'cc:{r["filename"]}:{r["offset"]}:{r["length"]}'
            ts = r['timestamp']
            snaps.append({'via': 'commoncrawl', 'url': r['url'], 'crawl': r['crawl'], 'warc': r['filename'],
                          'offset': r['offset'], 'length': r['length'], 'date': f'{ts[:4]}-{ts[4:6]}-{ts[6:8]}',
                          'timestamp': ts, 'sha256': hashlib.sha256(raw).hexdigest(),
                          'file': cache_path(key).name})
        snaps.sort(key=lambda s: (s['date'], s['via'], s['url']))
        manifest['acts'][slug] = snaps
        print(slug, len(snaps), [s['date'] for s in snaps], flush=True)
    for key, path in ANNUAL:
        url = f'{SITE}/Laws/Annual%20Law/{quote(path)}'
        body = direct(url)
        if body and body[:4] == b'%PDF':
            manifest['annual'][key] = {'url': url, 'sha256': hashlib.sha256(body).hexdigest(),
                                       'file': cache_path(url).name}
        else:
            print('annual missing', key, url)
    tmp = HERE / 'snapshots.json.tmp'
    tmp.write_text(json.dumps(manifest, indent=1, sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8')
    tmp.replace(HERE / 'snapshots.json')


if __name__ == '__main__':
    main()
