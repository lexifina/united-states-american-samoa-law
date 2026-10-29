"""Reading-only list of the laws the Asamblea Nacional reports as published in the Registro Oficial ('Leyes
aprobadas', asambleanacional.gob.ec), with their RO references, to find the COIP's amending acts after 2023.

Every page goes through fetch.py (curl --compressed, cached, 1 request per second per host).

    python -X utf8 coip/index_asamblea.py [--since YYYY] [REGEX]
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import fetch  # noqa: E402

BASE = "https://www.asambleanacional.gob.ec/es/leyes-aprobadas"


def page(n: int) -> str:
    url = BASE if n == 0 else f"{BASE}?page={n}"
    p = fetch.get(url)
    if p is None:
        raise SystemExit(f"failed: {url}")
    return p.read_text("utf-8", "replace")


def rows(t: str) -> list[dict]:
    out = []
    for tr in re.findall(r"<tr class=\"(?:odd|even)[^\"]*\">(.*?)</tr>", t, re.S):
        cells = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", c))).strip()
                 for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        pdf = re.findall(r'href="([^"]+\.pdf)"', tr)
        if len(cells) >= 3:
            m = re.search(r"(\d{2})-(\d{2})-(\d{4})", cells[2])
            out.append({"n": cells[0], "title": cells[1], "ro": cells[2],
                        "date": f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else "",
                        "pdf": pdf[0] if pdf else ""})
    return out


def all_rows(since: int = 0) -> list[dict]:
    out: list[dict] = []
    n = 0
    while True:
        rs = rows(page(n))
        if not rs:
            break
        out += rs
        if since and all(r["date"] and r["date"][:4] < str(since) for r in rs):
            break
        n += 1
        if n > 60:
            break
    return out


def main(argv: list[str]) -> None:
    since = 0
    if "--since" in argv:
        i = argv.index("--since")
        since = int(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    pat = argv[0] if argv else "."
    for r in all_rows(since):
        if since and r["date"][:4] < str(since):
            continue
        if re.search(pat, r["title"], re.I):
            print(f"{r['date']} | {r['ro']} | {r['title']} | {r['pdf']}")


if __name__ == "__main__":
    main(sys.argv[1:])
