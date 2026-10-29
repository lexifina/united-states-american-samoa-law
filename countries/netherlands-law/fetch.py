"""Downloads Dutch national law from the Basiswettenbestand (BWB) into scripts/netherlands-law/.cache/.

    python -X utf8 scripts/netherlands-law/fetch.py [acts...]      # default: every act in ACTS

The BWB is the official consolidated legislation behind wetten.overheid.nl, published by KOOP (Kennis- en
Exploitatiecentrum Officiele Overheidspublicaties) under CC0. Its repository serves, per regulation (BWB id):

  manifest   https://repository.officiele-overheidspublicaties.nl/bwb/<id>/manifest.xml
             every dated version ("toestand", expression label YYYY-MM-DD_N) with its in-force date
             (datum_inwerkingtreding), its end date (einddatum) and its visibility window (zichtdatum).
  version    https://repository.officiele-overheidspublicaties.nl/bwb/<id>/<label>/xml/<id>_<label>.xml
             the BWB toestand XML of the whole act as in force from that day: every article carries the
             source of its current wording (bron="Stb.2022-332", inwerking, effect, ondertekening_bron).
  law       https://zoek.officielebekendmakingen.nl/stb-YYYY-N/metadata.xml
             the Staatsblad issue's own metadata (title, signature and publication dates) for every source named in
             a cached version's bron="Stb.YYYY-N" attribute, from 1995 (the first year officielebekendmakingen.nl
             holds).
  WTI        https://repository.officiele-overheidspublicaties.nl/bwb/<id>/<id>.WTI
             the act's "wetstechnische informatie": its amendment history (wijzigingen) per version.

Every response is cached under .cache/<sha256 of the URL>, through curl (Python's TLS fails on this machine), at
most 3 requests a second to the host (coordinator SPEED RULE), with the User-Agent below, and logged to
.cache/requests.jsonl. Re-running only fetches what is missing; the manifest and WTI are refetched only with
--refresh.
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
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
REPO = 'https://repository.officiele-overheidspublicaties.nl/bwb'
GAP = 1 / 3          # at most 3 requests a second across all threads
_lock = threading.Lock()
_last = [0.0]

ACTS = json.loads((HERE / 'acts.json').read_text(encoding='utf-8'))


def cache_path(url: str) -> Path:
    return CACHE / hashlib.sha256(url.encode()).hexdigest()


def fetch(url: str, refresh: bool = False, offline: bool = False) -> bytes:
    path = cache_path(url)
    if path.exists() and not refresh:
        return path.read_bytes()
    if offline:
        raise FileNotFoundError(url)
    for attempt in range(4):
        with _lock:
            wait = _last[0] + GAP - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            _last[0] = time.monotonic()
        tmp = path.with_suffix('.part')
        r = subprocess.run(['curl', '-s', '--compressed', '-L', '-A', UA, '-o', str(tmp), '-w', '%{http_code}',
                            '--max-time', '180', url], capture_output=True, text=True)
        code = r.stdout.strip()
        size = tmp.stat().st_size if tmp.exists() else 0
        with _lock:
            with open(CACHE / 'requests.jsonl', 'a', encoding='utf-8') as f:
                f.write(json.dumps({'at': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                                    'url': url, 'status': code, 'bytes': size}) + '\n')
        if code == '200' and size:
            tmp.replace(path)
            return path.read_bytes()
        if tmp.exists():
            tmp.unlink()
        if code in ('429', '503'):
            time.sleep(60)
        else:
            time.sleep(2 + attempt * 3)
    raise RuntimeError(f'fetch failed {code}: {url}')


def manifest_url(bwb: str) -> str:
    return f'{REPO}/{bwb}/manifest.xml'


def wti_url(bwb: str) -> str:
    return f'{REPO}/{bwb}/{bwb}.WTI'


def version_url(bwb: str, label: str) -> str:
    return f'{REPO}/{bwb}/{label}/xml/{bwb}_{label}.xml'


def expressions(manifest: bytes) -> list[dict]:
    """Every expression in the manifest: label, in-force date, end date, visibility window."""
    out = []
    for m in re.finditer(rb'<expression label="([^"]+)"><metadata>(.*?)</metadata>', manifest, re.S):
        meta = m.group(2).decode()
        get = lambda tag: (re.search(f'<{tag}>([^<]*)</{tag}>', meta) or [None, None])[1]
        out.append({'label': m.group(1).decode(), 'from': get('datum_inwerkingtreding'), 'until': get('einddatum'),
                    'seen_from': get('zichtdatum_start'), 'seen_until': get('zichtdatum_eind')})
    return out


def law_url(bron: str) -> str:
    kind, year, nr = re.fullmatch(r'(\w+)\.(\d{4})-(\d+)', bron).groups()
    return f'https://zoek.officielebekendmakingen.nl/{kind.lower()}-{year}-{nr}/metadata.xml'


def law_sources(names: list[str]) -> list[str]:
    """Every bron="Stb.YYYY-N" named on any article or heading of any cached version, from 1995."""
    found = set()
    for name in names:
        bwb = ACTS[name]['bwb']
        for e in expressions(fetch(manifest_url(bwb), offline=True)):
            p = cache_path(version_url(bwb, e['label']))
            if p.exists():
                found.update(re.findall(rb' bron="(Stb\.(?:199[5-9]|20\d\d)-\d+)"', p.read_bytes()))
    return sorted(b.decode() for b in found)


def fetch_law(bron: str) -> bytes | None:
    try:
        return fetch(law_url(bron))
    except RuntimeError:
        return None


def main(argv: list[str]) -> None:
    refresh = '--refresh' in argv
    names = [a for a in argv if not a.startswith('--')] or list(ACTS)
    CACHE.mkdir(exist_ok=True)
    for name in names:
        bwb = ACTS[name]['bwb']
        man = fetch(manifest_url(bwb), refresh=refresh)
        fetch(wti_url(bwb), refresh=refresh)
        # Only the expressions still visible today (zichtdatum_eind 9999-12-31): a superseded _0 for a day is
        # replaced by a corrected _1 for the same day, and the source's current view of history is the _1.
        exprs = [e for e in expressions(man) if e['seen_until'] == '9999-12-31']
        todo = [version_url(bwb, e['label']) for e in exprs]
        missing = [u for u in todo if not cache_path(u).exists()]
        print(f'{name} {bwb}: {len(exprs)} expressions, {len(missing)} to fetch', flush=True)
        with ThreadPoolExecutor(3) as pool:
            for i, _ in enumerate(pool.map(fetch, missing), 1):
                if i % 25 == 0:
                    print(f'  {i}/{len(missing)}', flush=True)
    laws = [b for b in law_sources(list(ACTS)) if not cache_path(law_url(b)).exists()]
    print(f'law metadata: {len(laws)} to fetch', flush=True)
    with ThreadPoolExecutor(3) as pool:
        missing = [b for b, body in zip(laws, pool.map(fetch_law, laws)) if body is None]
    if missing:
        print('no metadata for', missing)


if __name__ == '__main__':
    main(sys.argv[1:])
