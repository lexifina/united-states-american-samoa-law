"""Compare the replayed Código Civil with two unofficial consolidations, for reading only (never copied).

- Ediciones Legales consolidation on gob.ec (last reform 17-VI-2025): today's text.
- Lexis consolidation of 12-IV-2017 at WIPO Lex: the text before the Código Orgánico del Ambiente took effect.

Writes civil/reconcile_civil.json with, per article, whether the normalised texts agree, and prints the disagreements.

    python -X utf8 civil/reconcile_civil.py
"""
from __future__ import annotations

import difflib
import html
import json
import re
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import fetch  # noqa: E402
import parse_civil  # noqa: E402

EDICIONES_2025 = "https://www.gob.ec/sites/default/files/regulations/2025-09/Documento_C%C3%B3digo-Civil-2025.pdf"
LEXIS_2017 = "https://wipolex-res.wipo.int/edocs/lexdocs/laws/es/ec/ec118es.pdf"
ART = re.compile(r"Art\.\s*(\d+)(?:\s*([A-Z])\b)?\s*\.?\s*-|Art\.\s*(?:…|\.\.\.)\s*\.?\s*-")
HEADS = re.compile(r"\s(Par[aá]grafo \d+o\.\s+[A-ZÁÉÍÓÚ¿]{2,}|T[IÍ]TULO [IVXL]+\b|T[ií]tulo [IVXL]+\s+[A-ZÁÉÍÓÚ]{2,}"
                   r"|Libro [IVX]+\s+[A-ZÁÉÍÓÚ]{2,}|LIBRO [IVX]+|DISPOSICI[OÓ]N|[IVX]+ REGLAS|II$)")
NOTE = re.compile(r"\s(?:Nota|Concordancias|Jurisprudencia):.*?(?:\d{4}\s?\)\s?\.?|\d{4}\s?\.)(?=\s|$)")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    for a in "“”„«»":
        s = s.replace(a, '"')
    s = s.replace("…", "...").replace("º", "o").replace("°", "o")
    s = re.sub(r"\((Reformad|Sustituid|Agregad|Derogad|Eliminad|Suprimid|Incluid)[ao]s?\b[^()]*(\([^()]*\)[^()]*)*\)\s*\.?-?", " ", s)
    s = re.sub(r"\bArt\.\s*(\d+)\s*(\w?)\s*\.?\s*-\s*", r"Art. \1\2.- ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def split_articles(flat: str) -> dict[str, str]:
    out: dict[str, str] = {}
    marks = []
    expect = 1
    for m in ART.finditer(flat):
        if m.group(1):
            n = int(m.group(1))
            letter = (m.group(2) or "").lower()
            if letter and n == expect - 1:
                marks.append((m.start(), f"art-{n:04d}-{letter}"))
            elif n == expect:
                marks.append((m.start(), f"art-{n:04d}"))
                expect += 1
        elif expect - 1 == 36:
            marks.append((m.start(), "art-0036-1"))
    for (i, k), (j, _) in zip(marks, marks[1:] + [(len(flat), None)]):
        t = flat[i:j]
        t = re.split(r"\s(?:Nota|Concordancias|Jurisprudencia):", t)[0]  # notes follow the article text
        h = HEADS.search(t, 10)
        if h:
            t = t[:h.start()]
        out[k] = t
    return out


def ediciones() -> dict[str, str]:
    import fitz
    d = fitz.open(fetch.cached(EDICIONES_2025))
    t = "\n".join(p.get_text() for p in d)
    t = re.sub(r"https://edicioneslegales\.com\.ec/\s*Pág\. \d+ de \d+\s*Todos los derechos reservados\. Prohibida su "
               r"reproducción parcial o total\.\s*Piense en el medio ambiente\. Imprima solo de ser necesario\.", " ", t)
    t = re.sub(r"\s+", " ", t)
    return split_articles(t[t.find("EXPEDIR LA SIGUIENTE CODIFICACIÓN"):])


def lexis() -> dict[str, str]:
    t = fetch.cached(LEXIS_2017).read_text(encoding="utf-8", errors="replace")
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", t, flags=re.S)
    t = re.sub(r"<br\s*/?>|</p>|</div>", "\n", t)
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    t = re.sub(r"\s+", " ", t)
    return split_articles(t[t.find("TITULO PRELIMINAR"):])


def state_on(versions: list[dict], day: str) -> dict:
    units = {}
    for v in versions:
        if v["from"] > day:
            break
        if "units" in v:
            units = dict(v["units"])
        for k, x in (v.get("changes") or {}).items():
            if x is None:
                units.pop(k, None)
            else:
                units[k] = x
    return units


def compare(ours: dict, theirs: dict) -> dict[str, dict]:
    res = {}
    for k in sorted(set(ours) | set(theirs)):
        if not k.startswith("art-"):
            continue
        a = norm(ours[k]["text"].replace("\n", " ")) if k in ours else None
        b = norm(theirs[k]) if k in theirs else None
        if b is not None and re.fullmatch(r"Art\. \d+\w?\.-\s*\.?", b):
            b = None  # a repealed article, left as a bare number with a note
        if a == b:
            continue
        r = difflib.SequenceMatcher(None, a or "", b or "").ratio()
        res[k] = {"ratio": round(r, 3), "ours": a, "theirs": b}
    return res


def main() -> None:
    act = parse_civil.build_act()
    versions = act["versions"]
    out = {}
    for name, theirs, day in [("ediciones_2025", ediciones(), "2026-10-28"), ("lexis_2017", lexis(), "2017-04-12")]:
        res = compare(state_on(versions, day), theirs)
        out[name] = {"day": day, "articles_compared": len(theirs), "disagree": len(res), "rows": res}
        print(f"== {name} (state on {day}): {len(theirs)} articles found in the consolidation, {len(res)} disagree")
        for k, r in res.items():
            print(f"  {k} {r['ratio']}")
    (HERE / "reconcile_civil.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
