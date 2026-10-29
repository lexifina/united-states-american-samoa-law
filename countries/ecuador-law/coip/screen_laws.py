"""Screen the laws published since 2023 (coip/index_asamblea.py) for reforms of the COIP: download each law's
Registro Oficial PDF (the Asamblea's copy), test its text layer, and list every mention of the Code with the article
numbers named near it. Writes coip/screen.json. Reading only: nothing here becomes legal text.

    python -X utf8 coip/screen_laws.py [--since YYYY]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import fetch  # noqa: E402
import index_asamblea  # noqa: E402

OUT = HERE / "screen.json"
CODE = re.compile(r"C[oó]digo\s+Org[aá]nico\s+Integral\s+Penal|\bCOIP\b", re.I)


def screen(path: Path) -> dict:
    import fitz
    d = fitz.open(path)
    texts = [d[i].get_text() for i in range(len(d))]
    empty = sum(1 for t in texts if len(t.strip()) < 200)
    flat = re.sub(r"\s+", " ", "\n".join(texts))
    hits = []
    for m in CODE.finditer(flat):
        hits.append(flat[max(0, m.start() - 220):m.end() + 60])
    return {"pages": len(d), "no_text_pages": empty, "mentions": len(hits), "snippets": hits[:80]}


def main(argv: list[str]) -> None:
    since = int(argv[argv.index("--since") + 1]) if "--since" in argv else 2023
    found = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    for r in index_asamblea.all_rows(since):
        if r["date"][:4] < str(since) or not r["pdf"]:
            continue
        key = r["pdf"]
        if key in found:
            continue
        p = fetch.get(r["pdf"], timeout=900)
        if p is None:
            print("FAILED", r["pdf"], flush=True)
            continue
        try:
            s = screen(p)
        except Exception as e:  # noqa: BLE001
            s = {"error": str(e)}
        found[key] = {**r, **s, "bytes": p.stat().st_size}
        print(f"{r['date']} {s.get('pages')}p empty={s.get('no_text_pages')} coip={s.get('mentions')} "
              f"{r['title'][:90]}", flush=True)
        tmp = OUT.with_suffix(".tmp")
        tmp.write_text(json.dumps(found, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
        tmp.replace(OUT)


if __name__ == "__main__":
    main(sys.argv[1:])
