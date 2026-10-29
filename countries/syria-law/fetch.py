"""Fetch the Syrian sources into .cache/ (sha256-of-URL names, requests.jsonl), through the shared archive client.

The People's Assembly site (parliament.gov.sy) no longer answers from here, so its pages are read from pinned
Internet Archive `id_` captures. Everything goes through scripts/gitlaw_common/wayback.py, which keeps one polite
machine-wide rate and caches by URL, so a rerun fetches nothing twice.

    python -X utf8 scripts/syria-law/fetch.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'gitlaw_common'))
import wayback  # noqa: E402

CACHE = HERE / '.cache'
SOURCES = json.loads((HERE / 'sources.json').read_text(encoding='utf-8'))


def main() -> None:
    CACHE.mkdir(exist_ok=True)
    for doc in SOURCES['documents']:
        if doc.get('via') == 'wayback':
            raw = wayback.get(doc['page'], ts=doc['ts'], cache=CACHE)
        else:
            raw = wayback.fetch_direct(doc['url'], cache=CACHE)
        print(doc['id'], 'ok' if raw else 'MISSING', len(raw or b''))


if __name__ == '__main__':
    main()
