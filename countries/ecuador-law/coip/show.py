"""Research helper: print the paragraphs of a cached gazette edition (as civil/replay.Src reads them) from an anchor.

    python -X utf8 coip/show.py <edition name in coip/editions.json> <title substring> <anchor regex> [count]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "civil"))
from replay import Src  # noqa: E402  (civil/replay.py)


def main(name: str, title: str, anchor: str, count: int = 40) -> None:
    eds = json.loads((HERE / "editions.json").read_text(encoding="utf-8"))[name]
    ed = next(e for e in eds if title in e["title"])
    s = Src(ed["pdf"])
    hits = [i for i, p in enumerate(s.paras) if re.search(anchor, p)]
    print(ed["title"], ed["pdf"], "hits", hits[:10])
    if hits:
        i = hits[0]
        for j in range(max(0, i - 2), min(len(s.paras), i + count)):
            print(f"{j}\t{s.paras[j]}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 40)
