"""Downloads Normattiva Open Data "multivigente" exports (every version of an act) into .cache/zips/.

    python -X utf8 scripts/italy-law/fetch.py [source id ...]

Normattiva Open Data (dati.normattiva.it, Istituto Poligrafico e Zecca dello Stato, CC BY 4.0) documents an API
(`/assets/come_fare_per/API_Normattiva_OpenData.pdf`). For one act we use its asynchronous export:

    POST ricerca-asincrona/nuova-ricerca  {"formato": "AKN"|"JSON", "tipoRicerca": "A", "richiestaExport": "M", ...}
    GET  ricerca-asincrona/check-status/<token>       (polled every 10 s; PUT conferma-ricerca if it waits)
    GET  collections/download/collection-asincrona/<token>  -> zip, one file per version of the act

and for the constitutional laws the prepared collection "Leggi costituzionali". Every request goes through curl with
our User-Agent and is logged to .cache/requests.jsonl. A source already in the cache is never fetched again.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
ZIPS = CACHE / 'zips'
API = 'https://api.normattiva.it/t/normattiva.api/bff-opendata/v1/api/v1'
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
LOCK = threading.Lock()
_last = [0.0]


def _q(den, num=None, year=None):
    p = {'denominazioneAtto': den, 'titoloContainsType': 'ALL_WORDS', 'testoContainsType': 'ALL_WORDS',
         'limitaAnniVigenza': False}
    if num:
        p['numeroProvvedimento'] = str(num)
        p['annoProvvedimento'] = year
    return p


# id -> what to export. The order is the order of the acts in the repository.
SOURCES = {
    'costituzione': {'kind': 'async', 'params': _q('COSTITUZIONE')},
    'codice-civile': {'kind': 'async', 'params': _q('REGIO DECRETO', 262, 1942)},
    'codice-penale': {'kind': 'async', 'params': _q('REGIO DECRETO', 1398, 1930)},
    'codice-privacy': {'kind': 'async', 'params': _q('DECRETO LEGISLATIVO', 196, 2003)},
}


def curl(args: list[str]) -> tuple[int, dict, bytes]:
    """One HTTP request, at most 3 a second across threads; logged."""
    with LOCK:
        wait = _last[0] + 0.34 - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.monotonic()
    out = subprocess.run(['curl', '-sS', '--compressed', '--max-time', '1800', '-A', UA, '-D', '-', *args],
                         capture_output=True)
    if out.returncode:
        raise RuntimeError(f'curl {args[-1]}: {out.stderr.decode(errors="replace")}')
    raw = out.stdout
    status, headers = 0, {}
    while raw.startswith(b'HTTP/'):
        head, _, raw = raw.partition(b'\r\n\r\n')
        lines = head.decode('latin-1').split('\r\n')
        status = int(lines[0].split()[1])
        headers = {l.split(':', 1)[0].lower(): l.split(':', 1)[1].strip() for l in lines[1:] if ':' in l}
    method = 'POST' if '-X' in args and args[args.index('-X') + 1] == 'POST' else (
        'PUT' if '-X' in args and args[args.index('-X') + 1] == 'PUT' else 'GET')
    with LOCK:
        with (CACHE / 'requests.jsonl').open('a', encoding='utf-8', newline='\n') as f:
            f.write(json.dumps({'at': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'method': method,
                                'url': args[-1], 'status': status, 'bytes': len(raw),
                                'sha256': hashlib.sha256(raw).hexdigest()}) + '\n')
    return status, headers, raw


def fetch(sid: str, fmt: str) -> Path:
    src = SOURCES[sid]
    path = ZIPS / f'{sid}{"" if fmt == "AKN" else "-json"}.zip'
    if path.exists():
        return path
    ZIPS.mkdir(parents=True, exist_ok=True)
    meta: dict = {}
    if src['kind'] == 'collection':
        url = f'{API}/collections/download/collection-preconfezionata?nome={src["nome"].replace(" ", "%20")}' \
              f'&formato={fmt}&formatoRichiesta=M'
        status, _, body = curl(['-L', url])
        meta['request'] = {'GET': url}
    else:
        req = {'formato': fmt, 'tipoRicerca': 'A', 'richiestaExport': 'M', 'parametriRicerca': src['params']}
        status, _, token = curl(['-H', 'Content-Type: application/json', '-X', 'POST', '--data', json.dumps(req),
                                 f'{API}/ricerca-asincrona/nuova-ricerca'])
        token = token.decode().strip()
        if status not in (200, 202) or not re.fullmatch(r'[0-9a-f-]{36}', token):
            raise SystemExit(f'nuova-ricerca {sid} {fmt}: {status} {token[:300]}')
        meta['request'] = {'POST': f'{API}/ricerca-asincrona/nuova-ricerca', 'body': req, 'token': token}
        deadline = time.monotonic() + 3 * 3600
        while True:
            status, _, st = curl([f'{API}/ricerca-asincrona/check-status/{token}'])
            state = json.loads(st or b'{}').get('stato')
            if state == 0:
                curl(['-H', 'Content-Type: application/json', '-X', 'PUT', '--data', json.dumps({'token': token}),
                      f'{API}/ricerca-asincrona/conferma-ricerca'])
            elif state == 3 or status == 303:
                break
            elif state in (4, 5):
                raise SystemExit(f'export {sid} {fmt}: {st[:300]}')
            if time.monotonic() > deadline:
                raise SystemExit(f'export {sid} {fmt}: still waiting after 3 hours')
            print(f'{sid} {fmt}: state {state}', flush=True)
            time.sleep(10)
        status, _, body = curl(['-L', f'{API}/collections/download/collection-asincrona/{token}'])
    if status != 200 or not body.startswith(b'PK'):
        raise SystemExit(f'download {sid} {fmt}: HTTP {status} {body[:200]!r}')
    tmp = path.with_suffix('.part')
    tmp.write_bytes(body)
    tmp.replace(path)
    meta.update(retrieved=dt.date.today().isoformat(), sha256=hashlib.sha256(body).hexdigest(), bytes=len(body))
    path.with_suffix('.json').write_text(json.dumps(meta, indent=1) + '\n', encoding='utf-8')
    print(f'{sid} {fmt}: {len(body)} bytes', flush=True)
    return path


def main():
    ids = sys.argv[1:] or list(SOURCES)
    jobs = [(s, f) for s in ids for f in ('AKN', 'JSON')]
    with ThreadPoolExecutor(4) as ex:
        for f in [ex.submit(fetch, s, fmt) for s, fmt in jobs]:
            f.result()


if __name__ == '__main__':
    main()
