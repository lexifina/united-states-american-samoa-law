"""Fetch every source the Philippines build reads, into .cache/ (resumable, cached, logged).

The Official Gazette (officialgazette.gov.ph) answers every request from this machine with a Cloudflare
challenge, and the Supreme Court E-Library sits behind a Radware WAF, so the official pages are read through
pinned Internet Archive `id_` captures (raw bytes, no banner), via the shared machine-wide client
scripts/gitlaw_common/wayback.py. It caches by sha256 of the archive URL and logs to .cache/requests.jsonl.

    python -X utf8 fetch.py            fetch every pinned capture in PLAN
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
sys.path.insert(0, str(HERE.parent / 'gitlaw_common'))

OG = 'https://www.officialgazette.gov.ph'

# (capture timestamp, original URL): each is the newest HTTP 200 capture listed by the CDX API on 2026-10-28.
PLAN = {
    'constitution': ('20231009121845', 'http://www.officialgazette.gov.ph/constitutions/1987-constitution/'),
    'ra-10173': ('20230930155155', 'http://www.officialgazette.gov.ph/2012/08/15/republic-act-no-10173/'),
    'act-3815': ('20230608093131', 'https://www.officialgazette.gov.ph/1930/12/08/act-no-3815-s-1930/'),
    'eo-200': ('20230717000612', 'https://www.officialgazette.gov.ph/1987/06/18/executive-order-no-200-s-1987/'),
}


def archive_url(ts: str, url: str) -> str:
    return f'https://web.archive.org/web/{ts}id_/{url}'


def cache_path(url: str) -> Path:
    return CACHE / hashlib.sha256(url.encode('utf-8')).hexdigest()


def read(name: str) -> tuple[str, bytes]:
    """(archive URL, cached bytes) for a PLAN entry; parse.py uses this and never the network."""
    ts, url = PLAN[name]
    au = archive_url(ts, url)
    return au, cache_path(au).read_bytes()


def main() -> None:
    import wayback
    CACHE.mkdir(exist_ok=True)
    (CACHE / '.gitignore').write_text('*\n')
    for name, (ts, url) in PLAN.items():
        body = wayback.get(url, ts=ts, cache=CACHE)
        print(name, None if body is None else len(body), archive_url(ts, url))


if __name__ == '__main__':
    main()
