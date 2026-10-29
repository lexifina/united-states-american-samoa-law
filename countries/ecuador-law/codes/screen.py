"""Screen laws from the Asamblea 'leyes aprobadas' list (coip/index_asamblea.py) for mentions of one Code in their
Registro Oficial text layer. Reading only: nothing here becomes legal text.

    python -X utf8 codes/screen.py <out.json> <code-regex> <title-regex> [--since YYYY]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "coip"))
sys.path.insert(0, str(HERE.parent))
import fetch  # noqa: E402
import index_asamblea  # noqa: E402


def screen(path: Path, code: re.Pattern) -> dict:
    import fitz
    d = fitz.open(path)
    texts = [d[i].get_text() for i in range(len(d))]
    empty = sum(1 for t in texts if len(t.strip()) < 200)
    flat = re.sub(r"\s+", " ", "\n".join(texts))
    hits = [flat[max(0, m.start() - 200):m.end() + 120] for m in code.finditer(flat)]
    return {"pages": len(d), "no_text_pages": empty, "mentions": len(hits), "snippets": hits[:60]}


def main(argv: list[str]) -> None:
    since = 2019
    if "--since" in argv:
        i = argv.index("--since")
        since = int(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    out, code, title = HERE / argv[0], re.compile(argv[1], re.I), re.compile(argv[2], re.I)
    found = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    for r in index_asamblea.all_rows(since):
        if r["date"][:4] < str(since) or not r["pdf"] or not title.search(r["title"]) or r["pdf"] in found:
            continue
        p = fetch.get(r["pdf"], timeout=900)
        if p is None:
            print("FAILED", r["pdf"], flush=True)
            continue
        try:
            s = screen(p, code)
        except Exception as e:  # noqa: BLE001
            s = {"error": str(e)}
        found[r["pdf"]] = {**r, **s}
        print(f"{r['date']} {s.get('pages')}p empty={s.get('no_text_pages')} hits={s.get('mentions')} {r['title'][:80]}",
              flush=True)
        tmp = out.with_suffix(".tmp")
        tmp.write_text(json.dumps(found, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
        tmp.replace(out)


if __name__ == "__main__":
    main(sys.argv[1:])
