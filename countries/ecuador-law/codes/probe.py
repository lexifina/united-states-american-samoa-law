"""Find a Registro Oficial edition by product, date and number, download it (cached) and report its text layer.

    python -X utf8 codes/probe.py suplemento 2019-05-29 497 [title-substring]
"""
from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import fetch  # noqa: E402
import ro_index  # noqa: E402


def main(argv: list[str]) -> None:
    import fitz
    prod, day, num = argv[0], argv[1], int(argv[2])
    only = argv[3] if len(argv) > 3 else None
    d0 = dt.date.fromisoformat(day)
    eds = [e for e in ro_index.editions(prod, d0.year, d0.month) if e["number"] == num and e["date"]
           and abs((dt.date.fromisoformat(e["date"]) - d0).days) <= 3 and (not only or only in e["title"])]
    if not eds:
        print(f"no {prod} {num} near {day}")
    for e in eds:
        p = fetch.get(e["pdf"], timeout=900)
        if p is None:
            print("download failed", e["pdf"])
            continue
        d = fitz.open(p)
        sizes = [len(d[i].get_text().strip()) for i in range(len(d))]
        empty = sum(1 for s in sizes if s < 200)
        head = re.sub(r"\s+", " ", d[0].get_text())[:400]
        print(f"== {e['title']} | {e['date']} | {len(d)} p | no-text {empty} | {p.stat().st_size} B\n   {e['pdf']}\n   {head}")


if __name__ == "__main__":
    main(sys.argv[1:])
