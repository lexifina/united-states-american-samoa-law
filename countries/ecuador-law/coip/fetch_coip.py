"""Fetch (or reuse from the cache) every source the COIP part needs: the gazette editions in coip/editions.json that
coip_replay.py uses, the Decreto 229 annexes (Supl. 133, 2017), the 2018 referendum results (Supl. 180), and the
four editorial consolidations read only as indexes
(coip/screen_laws.py fetches the Asamblea list and the 2023-2026 laws it screens).

Uses the country's fetch.py: curl --compressed, sha256-named cache, at most 1 request per second per host, every
request logged to .cache/requests.jsonl. coip/find_editions.py (which also downloads) found the editions.

    python -X utf8 coip/fetch_coip.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "civil"))
import fetch  # noqa: E402


def urls() -> list[str]:
    import coip_base
    import coip_replay as R
    import index_lexis
    import index_notes
    import index_el2026
    out = [coip_base.S180_2014, index_notes.CONSOLIDATION, index_lexis.LEXIS, index_el2026.EL2026,
           index_el2026.ANDINA2026]
    out += sorted({law["url"] for law in R.LAWS.values()} | {R.S133_2017, R.S180_2018})
    return list(dict.fromkeys(out))


def main() -> int:
    bad = 0
    for u in urls():
        p = fetch.get(u, timeout=900)
        print("ok " if p else "FAILED", u)
        bad += p is None
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
