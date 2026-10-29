"""Reconcile the replayed Constitution with a commercial consolidation (reading only; nothing is copied).

The Lexis Finder consolidation republished by the Ministerio de Defensa ("Ultima modificación: 25-ene.-2021")
is compared word by word, article by article, with this record's text in force on 25 January 2021. Its notes
("Nota: ...", "Concordancias: ...") and page furniture are skipped. The result is a list of articles whose
words differ, written to reconcile.json, for a person to explain in PROGRESS.md.

    python -X utf8 reconcile.py
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fetch  # noqa: E402
import rotext  # noqa: E402

LEXIS = "https://www.defensa.gob.ec/wp-content/uploads/downloads/2021/02/Constitucion-de-la-Republica-del-Ecuador_act_ene-2021.pdf"
DAY = "2021-01-25"


def words(s: str) -> list[str]:
    s = rotext.norm(s)
    s = unicodedata.normalize("NFC", s).lower()
    return re.findall(r"[a-záéíóúñü0-9]+", s)


def lexis_articles() -> dict[int, str]:
    import fitz
    doc = fitz.open(fetch.cached(LEXIS))
    lines = []
    for p in doc:
        for ln in p.get_text().split("\n"):
            if re.match(r"\s*(CONSTITUCIÓN DE LA REPÚBLICA DEL ECUADOR - Página|LEXIS FINDER)", ln):
                continue
            lines.append(ln)
    out: dict[int, list[str]] = {}
    cur = None
    skip = False
    for ln in lines:
        m = re.match(r"\s*Art\.\s*(\d+)\.?\s*-", ln)
        if re.match(r"\s*(DISPOSICIONES TRANSITORIAS|R[ÉE]GIMEN DE TRANSICI)", ln):
            cur = None
        if m and (cur is None or int(m.group(1)) == cur + 1) and int(m.group(1)) <= 444 and (cur or 0) < 444:
            cur = int(m.group(1))
            out[cur] = []
            skip = False
        if cur is None:
            continue
        if re.match(r"\s*(Nota|Concordancias)\s*:", ln):
            skip = True
            continue
        if skip and re.match(r"\s*(T[IÍ]TULO|Cap[ií]tulo|CAP[IÍ]TULO|Secci[oó]n|Art\.)", ln):
            skip = False
        if skip or re.match(r"\s*(T[IÍ]TULO|Cap[ií]tulo|CAP[IÍ]TULO|Secci[oó]n)\b", ln):
            continue
        out[cur].append(ln)
    return {k: " ".join(v) for k, v in out.items()}


def main() -> None:
    import difflib
    corpus = json.loads((HERE / "corpus.json").read_text(encoding="utf-8"))
    vs = [v for v in corpus["acts"][0]["versions"] if v["from"] <= DAY]
    units = vs[-1]["units"]
    lx = lexis_articles()
    report = []
    # the consolidation's chapter and section names sit between articles; drop them from its trailing words
    heads = sorted((words(h) for h in units["titulos"]["text"].splitlines() if h.strip()), key=len, reverse=True)
    for n in range(1, 445):
        ours = words(units[f"art-{n:03d}"]["text"])
        theirs = words(lx.get(n, ""))
        changed = True
        while changed and len(theirs) > len(ours):
            changed = False
            for h in heads:
                if h and theirs[-len(h):] == h and theirs[:-len(h)][:len(ours)] == theirs[:-len(h)][:len(ours)]:
                    theirs = theirs[:-len(h)]
                    changed = True
                    break
        if ours == theirs:
            continue
        sm = difflib.SequenceMatcher(a=ours, b=theirs, autojunk=False)
        ops = [(t, " ".join(ours[i1:i2]), " ".join(theirs[j1:j2])) for t, i1, i2, j1, j2 in sm.get_opcodes() if t != "equal"]
        report.append({"art": n, "ratio": round(sm.ratio(), 3), "diffs": ops[:8]})
    (HERE / "reconcile.json").write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(report)} of 444 articles differ in words; see reconcile.json")
    for r in report:
        print(r["art"], r["ratio"], r["diffs"][:3])


if __name__ == "__main__":
    main()
