"""Research helper: print the paragraphs of a cached gazette edition (strict.paragraphs, as codes/cogep.py reads them)
from an anchor.

    python -X utf8 codes/show.py <edition name in codes/ or coip/editions.json> <title substring> <anchor regex> [count]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import fetch  # noqa: E402
import strict  # noqa: E402


def edition(name: str, title: str) -> str:
    for f in (HERE / "editions.json", HERE.parent / "coip" / "editions.json"):
        eds = json.loads(f.read_text(encoding="utf-8")).get(name)
        if eds:
            return next(e for e in eds if title in e["title"])["pdf"]
    raise SystemExit(f"no edition {name} {title}")


def main(name: str, title: str, anchor: str, count: int = 40) -> None:
    url = edition(name, title)
    ps = strict.paragraphs(fetch.cached(url))
    hits = [i for i, p in enumerate(ps) if re.search(anchor, p)]
    print(url, "hits", hits[:10])
    if hits:
        i = hits[0]
        for j in range(max(0, i - 2), min(len(ps), i + count)):
            print(f"{j}\t{ps[j]}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 40)
