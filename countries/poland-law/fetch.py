"""Downloads everything the Polish corpus needs from the Sejm's ELI API (https://api.sejm.gov.pl/eli) into .cache/.

    python -X utf8 scripts/poland-law/fetch.py

For each act in acts.json: its metadata, its text (text.html, else the PDF), the metadata and text of every unified
text (tekst jednolity) the API lists for it, and the metadata and text of every amending act and Constitutional
Tribunal announcement it lists (their own words are replayed where they quote the new wording).

The cache is keyed by the sha256 of the URL; every request goes through curl (Python's TLS fails on this machine) and
is logged to .cache/requests.jsonl. At most 3 requests a second, 3 at a time; resumable (cached answers are reused).
"""
from __future__ import annotations

import concurrent.futures as cf
import hashlib
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
API = 'https://api.sejm.gov.pl/eli'
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
RATE = 1 / 3
_lock = threading.Lock()
_last = [0.0]
OFFLINE = [False]


def path_of(url: str) -> Path:
    return CACHE / hashlib.sha256(url.encode()).hexdigest()


def _log(rec: dict):
    with _lock, open(CACHE / 'requests.jsonl', 'a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')


def get(url: str) -> bytes | None:
    """The answer's bytes (cached), or None for a 404 / empty answer (cached as a single 0x00 byte)."""
    p = path_of(url)
    if p.exists():
        b = p.read_bytes()
        return None if b == b'\x00' else b
    if OFFLINE[0]:
        raise SystemExit(f'not cached: {url}')
    CACHE.mkdir(exist_ok=True)
    for attempt in range(5):
        with _lock:
            wait = _last[0] + RATE - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            _last[0] = time.monotonic()
        tmp = p.with_suffix('.part')
        out = subprocess.run(['curl', '-sS', '--compressed', '-L', '--max-time', '180', '-A', UA, '-o', str(tmp),
                              '-w', '%{http_code}', url], capture_output=True, text=True)
        code = int(out.stdout.strip() or 0)
        body = tmp.read_bytes() if tmp.exists() else b''
        _log({'url': url, 'status': code, 'bytes': len(body), 'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
              'sha256': hashlib.sha256(body).hexdigest() if code == 200 else None})
        if code == 200 and b'Request Rejected' in body[:600]:
            tmp.unlink(missing_ok=True)
            raise SystemExit('WAF rejected ' + url)
        if code in (404, 204) or (code == 200 and not body):
            tmp.unlink(missing_ok=True)
            p.write_bytes(b'\x00')
            return None
        if code == 200:
            tmp.replace(p)
            return body
        tmp.unlink(missing_ok=True)
        if code in (429, 503):
            time.sleep(60)
        else:
            time.sleep(3 * (attempt + 1))
    raise SystemExit(f'HTTP {code} for {url}')


def meta(eli: str) -> dict:
    return json.loads(get(f'{API}/acts/{eli}'))


def text_html(eli: str) -> bytes | None:
    return get(f'{API}/acts/{eli}/text.html')


def text_file(eli: str, kind: str) -> bytes | None:
    m = meta(eli)
    for t in m.get('texts', []):
        if t['type'] == kind:
            return get(f'{API}/acts/{eli}/text/{kind}/{t["fileName"]}')
    return None


def pmap(fn, items):
    with cf.ThreadPoolExecutor(3) as ex:
        return list(ex.map(fn, items))


def fetch_act(conf: dict):
    m = meta(conf['eli'])
    refs = m['references']
    if m['textHTML']:
        text_html(conf['eli'])
    for k in conf.get('pdf', []):
        text_file(conf['eli'], k)
    tjs = [r['id'] for r in refs.get('Inf. o tekście jednolitym', [])]
    others = [r['id'] for k in ('Akty zmieniające', 'Orzeczenie TK', 'Sprostowanie') for r in refs.get(k, [])]
    metas = dict(zip(tjs + others, pmap(meta, tjs + others)))
    need = [e for e in tjs + others if metas[e]['textHTML']]
    pmap(text_html, need)
    # Unified texts without HTML: the PDF as published (O).
    pmap(lambda e: text_file(e, 'O'), [e for e in tjs if not metas[e]['textHTML']])
    print(f'{conf["slug"]}: {len(tjs)} unified texts, {len(others)} amending acts/rulings, {len(need)} HTML texts',
          flush=True)


def main():
    acts = json.loads((HERE / 'acts.json').read_text(encoding='utf-8'))
    only = set(sys.argv[1:])
    for a in acts:
        if not only or a['slug'] in only:
            fetch_act(a)


if __name__ == '__main__':
    main()
