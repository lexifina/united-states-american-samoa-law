"""Download the Légifrance LEGI open-data dumps (DILA, Licence Ouverte / Etalab 2.0) into .cache/.

One full dump (Freemium_legi_global_<stamp>.tar.gz) plus every daily increment (LEGI_<stamp>.tar.gz) published
after it, from https://echanges.dila.gouv.fr/OPENDATA/LEGI/. Each file is cached under .cache/<sha256(url)>.bin,
written atomically, skipped if already present (resumable). Every request is logged to .cache/requests.jsonl.

    python -X utf8 fetch.py            # listing + global + increments
    python -X utf8 fetch.py --listing  # refresh the listing only
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
BASE = 'https://echanges.dila.gouv.fr/OPENDATA/LEGI/'
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
MIN_GAP = 0.4  # seconds between requests (SPEED RULE: up to 3 a second on official sites)
_last = [0.0]


def cache_path(url: str) -> Path:
    return CACHE / (hashlib.sha256(url.encode()).hexdigest() + '.bin')


def fetch(url: str, refresh: bool = False) -> Path:
    out = cache_path(url)
    if out.exists() and not refresh:
        return out
    wait = MIN_GAP - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    tmp = out.with_suffix('.part')
    t0 = time.time()
    r = subprocess.run(['curl', '-sS', '--compressed', '-L', '--retry', '4', '--retry-delay', '20', '-A', UA,
                        '-o', str(tmp), '-w', '%{http_code}', url], capture_output=True, text=True)
    _last[0] = time.time()
    code = r.stdout.strip()
    with open(CACHE / 'requests.jsonl', 'a', encoding='utf-8') as f:
        f.write(json.dumps({'url': url, 'status': code, 'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                            'seconds': round(time.time() - t0, 1),
                            'bytes': tmp.stat().st_size if tmp.exists() else 0}) + '\n')
    if code != '200':
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f'{url}: HTTP {code} {r.stderr.strip()}')
    if url.endswith('.gz') and subprocess.run(['gzip', '-t', str(tmp)], capture_output=True).returncode:
        tmp.unlink(missing_ok=True)  # two archives once arrived truncated with a 200 after a 600 s stall
        raise RuntimeError(f'{url}: truncated archive')
    tmp.replace(out)
    return out


def listing(refresh: bool = True) -> list[str]:
    p = fetch(BASE, refresh=refresh)
    names = sorted(set(re.findall(r'href="((?:Freemium_legi_global|LEGI)_\d{8}-\d{6}\.tar\.gz)"', p.read_text('utf-8'))))
    return names


def plan(names: list[str]) -> list[str]:
    """The newest global dump, then every increment stamped after it."""
    glob = sorted(n for n in names if n.startswith('Freemium'))[-1]
    stamp = re.search(r'(\d{8}-\d{6})', glob).group(1)
    incs = [n for n in names if n.startswith('LEGI_') and re.search(r'(\d{8}-\d{6})', n).group(1) > stamp]
    return [glob] + incs


def main() -> None:
    CACHE.mkdir(exist_ok=True)
    names = listing(refresh=True)
    files = plan(names)
    (CACHE / 'plan.json').write_text(json.dumps({'base': BASE, 'files': files,
                                                  'listing_sha256': hashlib.sha256(cache_path(BASE).read_bytes()).hexdigest()},
                                                 indent=1), 'utf-8')
    if '--listing' in sys.argv:
        print(len(files), 'files planned')
        return
    if '--incs' in sys.argv:  # increments only, newest first: a second, parallel fetcher while the global downloads
        files = files[1:][::-1]
    for i, n in enumerate(files):
        p = fetch(BASE + n)
        print(f'{i + 1}/{len(files)} {n} {p.stat().st_size}', flush=True)


if __name__ == '__main__':
    main()
