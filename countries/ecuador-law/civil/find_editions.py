"""Locate the Registro Oficial editions that carry the Civil Code's amending acts (research helper).

For each target (product, date, number) it lists that month's editions, downloads every edition of that number and
day, and prints the first page's sumario lines and the text-layer size per page, so the right edition can be pinned
in civil/sources_civil.json.

    python -X utf8 civil/find_editions.py [TARGET ...]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import fetch  # noqa: E402
import ro_index  # noqa: E402

TARGETS = {
    "ro79-2005": ("ro", "2005-08-10", 79),
    "ro169-2005": ("ro", "2005-12-20", 169),
    "s274-2006": ("suplemento", "2006-05-19", 274),
    "s285-2010": ("suplemento", "2010-09-23", 285),
    "s452-2011": ("suplemento", "2011-05-19", 452),
    "s732-2012": ("suplemento", "2012-06-26", 732),
    "s796-2012": ("suplemento", "2012-09-25", 796),
    "s797-2012": ("suplemento", "2012-09-26", 797),
    "s843-2012": ("suplemento", "2012-12-03", 843),
    "s332-2014": ("suplemento", "2014-09-12", 332),
    "s506-2015": ("suplemento", "2015-05-22", 506),
    "s526-2015": ("suplemento", "2015-06-19", 526),
    "s983-2017": ("suplemento", "2017-04-12", 983),
    "ec96-2019": ("constitucional", "2019-07-08", 96),
    "s452-2021": ("suplemento", "2021-05-14", 452),
    "s561-2021": ("suplemento", "2021-10-19", 561),
    "ec15-2022": ("constitucional", "2022-03-14", 15),
    "s471-2024": ("suplemento", "2024-01-05", 471),
    "s496-2024": ("suplemento", "2024-02-09", 496),
    "s517-2024": ("suplemento", "2024-03-13", 517),
    "s588-2024": ("suplemento", "2024-06-27", 588),
    "s61-2025": ("suplemento", "2025-06-17", 61),
}


def main(argv: list[str]) -> None:
    import fitz
    names = argv or list(TARGETS)
    for name in names:
        prod, day, num = TARGETS[name]
        y, m = int(day[:4]), int(day[5:7])
        eds = [e for e in ro_index.editions(prod, y, m) if e["date"] == day and e["number"] == num]
        if not eds:
            print(f"== {name}: no {prod} {num} on {day}")
            continue
        for e in eds:
            p = fetch.get(e["pdf"], timeout=600)
            if p is None:
                print(f"== {name} {e['title']}: download failed {e['pdf']}")
                continue
            d = fitz.open(p)
            sizes = [len(d[i].get_text().strip()) for i in range(len(d))]
            head = re.sub(r"\s+", " ", d[0].get_text())[:900]
            print(f"== {name} | {e['title']} | {len(d)} pages | text chars p1-5 {sizes[:5]} | zero-text pages "
                  f"{sum(1 for s in sizes if s < 50)} | {p.stat().st_size} bytes\n   {e['pdf']}\n   {head}")


if __name__ == "__main__":
    main(sys.argv[1:])
