"""Downloads Mauritian law into scripts/mauritius-law/.cache/.

    python -X utf8 scripts/mauritius-law/fetch.py URL [URL...]   # fetch (or re-read) single URLs
    python -X utf8 scripts/mauritius-law/fetch.py --all          # every URL parse.py needs (sources.json "urls")
    python -X utf8 scripts/mauritius-law/fetch.py --cdx URL      # list Wayback captures of URL

Uses the shared curl cache of scripts/africa-law/peachjam.py (read-only import): one file per URL named by its
sha256, every request logged to .cache/requests.jsonl, archive.org through the shared adaptive rate of
gitlaw_common/wayback.py. Government hosts (*.govmu.org) at most 1 request per second.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'africa-law'))
sys.path.insert(0, str(HERE.parent / 'gitlaw_common'))
import peachjam  # noqa: E402
import wayback  # noqa: E402  (coordinator 2026-10-28: archive.org only through the shared adaptive client)

for host in ('attorneygeneral.govmu.org', 'mauritiusassembly.govmu.org', 'supremecourt.govmu.org',
             'dataprotection.govmu.org', 'www.govmu.org', 'govmu.org', 'gis.govmu.org'):
    peachjam.CRAWL_DELAY.setdefault(host, 1.1)

CACHE = peachjam.Cache(HERE)


def fetch(url: str, offline: bool = False) -> bytes:
    """Government hosts through the curl cache (1 request/s); archive.org through gitlaw_common/wayback.py."""
    if 'archive.org/' in url and not CACHE.has(url):
        if offline:
            raise FileNotFoundError(f'not in cache (run fetch.py): {url}')
        body = wayback.fetch(url, CACHE.dir)
        if body is None:
            raise RuntimeError(f'fetch failed {url}')
        return body
    CACHE.offline = offline
    return CACHE.get(url)


def path(url: str) -> Path:
    return CACHE.path(url)


def cdx(url: str, offline: bool = False, extra: str = '') -> list[list[str]]:
    """Wayback captures of url: [timestamp, original, statuscode, digest, length], one per distinct digest."""
    q = (f'https://web.archive.org/cdx/search/cdx?url={url}&output=json'
         f'&fl=timestamp,original,statuscode,digest,length&collapse=digest{extra}')
    rows = json.loads(fetch(q, offline) or b'[]')
    return rows[1:]


def wayback_url(ts: str, original: str) -> str:
    return f'https://web.archive.org/web/{ts}id_/{original}'


def main(argv: list[str]) -> None:
    if argv[:1] == ['--cdx']:
        for u in argv[1:]:
            for r in cdx(u):
                print(*r)
        return
    urls = json.loads((HERE / 'sources.json').read_text(encoding='utf-8'))['urls'] if argv == ['--all'] else argv
    for u in urls:
        try:
            b = fetch(u)
            print(f'ok {len(b):>9} {path(u).name[:12]} {u}', flush=True)
        except Exception as e:  # noqa: BLE001
            print(f'FAIL {u}: {e}', flush=True)


if __name__ == '__main__':
    main(sys.argv[1:])
