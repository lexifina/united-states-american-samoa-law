"""Fetch everything more/parse_cpdc.py reads (more/sources.json) into the shared cache ../.cache.

Direct URLs go through ../fetch.py (curl, sha256(URL) names, 1 request per second per host, requests.jsonl);
web.archive.org captures go through scripts/gitlaw_common/wayback.py (shared machine-wide archive.org rate).

    python -X utf8 more/mfetch.py --plan
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent / 'gitlaw_common'))
import fetch  # noqa: E402
import wayback  # noqa: E402


def main() -> int:
    plan = json.loads((HERE / 'sources.json').read_text(encoding='utf-8'))
    bad = 0
    for part in plan.values():
        for u in part['urls']:
            if u.startswith('https://web.archive.org/'):
                ok = wayback.fetch(u, cache=fetch.CACHE) is not None
            else:
                ok = fetch.get(u) is not None
            print('ok ' if ok else 'FAILED', u)
            bad += not ok
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
