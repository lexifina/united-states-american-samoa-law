"""Locate the Registro Oficial editions that carry the COIP's amending acts and test whether each has a text layer.

For each target (product, date, number) it lists that month's editions, downloads every edition of that number and
day, and prints the title, page count, the share of pages with no text layer and the first page's sumario.

    python -X utf8 coip/find_editions.py [TARGET ...]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import fetch  # noqa: E402
import ro_index  # noqa: E402

# from the reading-only index (coip/index_notes.py) and the RO site search; product per ro_index.PRODUCTS
TARGETS = {
    "s180-2014": ("suplemento", "2014-02-10", 180),
    "s224-2014": ("suplemento", "2014-04-11", 224),
    "s246-2014": ("suplemento", "2014-05-15", 246),
    "s332-2014": ("suplemento", "2014-09-12", 332),
    "s506-2015": ("suplemento", "2015-05-22", 506),
    "s598-2015": ("suplemento", "2015-09-30", 598),
    "s615-2015": ("suplemento", "2015-10-26", 615),
    "s711-2016": ("suplemento", "2016-03-14", 711),
    "s802-2016": ("suplemento", "2016-07-21", 802),
    "s175-2018": ("suplemento", "2018-02-05", 175),
    "s181-2018": ("suplemento", "2018-02-15", 181),
    "s478-2019": ("suplemento", "2019-04-30", 478),
    "s481-2019": ("suplemento", "2019-05-06", 481),
    "ec6-2019": ("constitucional", "2019-08-15", 6),
    "s107-2019": ("suplemento", "2019-12-24", 107),
    "ec95-2020": ("constitucional", "2020-11-18", 95),
    "s386-2021": ("suplemento", "2021-02-05", 386),
    "s392-2021": ("suplemento", "2021-02-17", 392),
    "s452-2021": ("suplemento", "2021-05-14", 452),
    "ec194-2021": ("constitucional", "2021-06-29", 194),
    "s512-2021": ("suplemento", "2021-08-10", 512),
    "s525-2021": ("suplemento", "2021-08-27", 525),
    "s526-2021": ("suplemento", "2021-08-30", 526),
    "ec222-2021": ("constitucional", "2021-10-13", 222),
    "s150-2017": ("suplemento", "2017-12-29", 150),
    "s7-2017": ("suplemento", "2017-07-04", 7),
    "s90-2019": ("suplemento", "2019-06-03", 90),
    "ec90-2019": ("constitucional", "2019-06-03", 90),
    "s21-2019": ("suplemento", "2019-11-13", 21),
    "ec21-2019": ("constitucional", "2019-11-13", 21),
    "s95-2020": ("suplemento", "2020-11-18", 95),
    "ec95-2020b": ("constitucional", "2020-11-18", 95),
    "s386-2021b": ("suplemento", "2021-02-05", 386),
    "s261-2022": ("suplemento", "2022-01-14", 261),
    "s267-2022": ("suplemento", "2022-01-25", 267),
    "s268-2022": ("suplemento", "2022-01-28", 268),
    "s20-2022": ("suplemento", "2022-03-16", 20),
    "ec20-2022": ("constitucional", "2022-03-16", 20),
    "s131-2022": ("suplemento", "2022-08-22", 131),
    "s222-2023": ("suplemento", "2023-01-04", 222),
    "s191-2023": ("suplemento", "2023-03-08", 191),
    "ec191-2023": ("constitucional", "2023-03-08", 191),
    "ec261-2022": ("constitucional", "2022-01-14", 261),
    "ec267-2022": ("constitucional", "2022-01-25", 267),
    "ec268-2022": ("constitucional", "2022-01-28", 268),
    "s899-2016": ("suplemento", "2016-12-09", 899),
    # 2023-2026 (coip/index_el2026.py, coip/index_asamblea.py); a fourth item keeps only the edition of that title
    "s279-2023": ("suplemento", "2023-03-29", 279, "Primer Suplemento"),
    "s471-2024": ("suplemento", "2024-01-05", 471, "Primer Suplemento"),
    "s496-2024": ("suplemento", "2024-02-09", 496, "Segundo Suplemento"),
    "s516-2024": ("suplemento", "2024-03-12", 516, "Primer Suplemento"),
    "ec319-2024": ("constitucional", "2024-02-26", 319, "Ediciones Constitucionales"),
    "s588-2024": ("suplemento", "2024-06-27", 588, "Tercer Suplemento"),
    "s599-2024": ("suplemento", "2024-07-12", 599, "Primer Suplemento"),
    "s610-2024": ("suplemento", "2024-07-29", 610, "Cuarto Suplemento"),
    "s700-2024": ("suplemento", "2024-12-10", 700, "Quinto Suplemento"),
    "ec8-2025": ("constitucional", "2025-03-27", 8, "Ediciones Constitucionales"),
    "ec15-2025": ("constitucional", "2025-04-02", 15, "Ediciones Constitucionales"),
    "s38-2025": ("suplemento", "2025-05-14", 38, "Quinto Suplemento"),
    "s56-2025": ("suplemento", "2025-06-10", 56, "Sexto Suplemento"),
    "s68-2025": ("suplemento", "2025-06-26", 68, "Tercer Suplemento"),
    "ec78-2025": ("constitucional", "2025-09-19", 78, "Ediciones Constitucionales"),
    "ec96-2025": ("constitucional", "2025-10-03", 96, "Ediciones Constitucionales"),
    "s151-2025": ("suplemento", "2025-10-24", 151, "Séptimo Suplemento"),
    "s275-2026": ("suplemento", "2026-04-29", 275, "Cuarto Suplemento"),
    "s316-2026": ("suplemento", "2026-07-01", 316, "Quinto Suplemento"),
    "s343-2026": ("suplemento", "2026-08-07", 343, "Quinto Suplemento"),
    "s290-2026": ("suplemento", "2026-05-22", 290, "Quinto Suplemento"),
}
OUT = HERE / "editions.json"


def main(argv: list[str]) -> None:
    import fitz
    names = argv or list(TARGETS)
    found = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    for name in names:
        prod, day, num, *only = TARGETS[name]
        y, m = int(day[:4]), int(day[5:7])
        # the portal's listing date can be a day or two off the masthead (RO 386 of 2021: listed 6-II, printed 5-II),
        # so the number decides, within three days of the date the indexes give
        import datetime as _dt
        d0 = _dt.date.fromisoformat(day)
        eds = [e for e in ro_index.editions(prod, y, m) if e["number"] == num and e["date"]
               and abs((_dt.date.fromisoformat(e["date"]) - d0).days) <= 3 and (not only or e["title"] == only[0])]
        if not eds:
            print(f"== {name}: no {prod} {num} on {day}")
            continue
        rows = []
        for e in eds:
            p = fetch.get(e["pdf"], timeout=900)
            if p is None:
                print(f"== {name} {e['title']}: download failed {e['pdf']}")
                continue
            d = fitz.open(p)
            sizes = [len(d[i].get_text().strip()) for i in range(len(d))]
            empty = sum(1 for s in sizes if s < 200)
            head = re.sub(r"\s+", " ", d[0].get_text())[:500]
            rows.append({"title": e["title"], "listed": e["date"], "pdf": e["pdf"], "pages": len(d), "no_text_pages": empty,
                         "bytes": p.stat().st_size, "head": head})
            print(f"== {name} | {e['title']} | {len(d)} p | no-text pages {empty} | {p.stat().st_size} B\n   {head[:300]}")
        found[name] = rows
        tmp = OUT.with_suffix(".tmp")
        tmp.write_text(json.dumps(found, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
        tmp.replace(OUT)


if __name__ == "__main__":
    main(sys.argv[1:])
