"""Reading-only index of the COIP's amending acts from the Lexis consolidation on FAOLEX (last change 2023-03-08).

Only its "Nota:" lines are read, to learn which Registro Oficial editions amended (or ruled on) which articles. No
wording is taken from it. Prints one line per edition, oldest first, with the articles named.

    python -X utf8 coip/index_lexis.py [--full] [--notes REGEX]
"""
from __future__ import annotations

import collections
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import fetch  # noqa: E402

import fitz  # noqa: E402

LEXIS = "https://faolex.fao.org/docs/pdf/ecu204126.pdf"
MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
          "noviembre", "diciembre"]
REF = re.compile(r"((?:Registro Oficial|Edici[oó]n Constitucional)[^.]{0,90}?\s(\d{1,3})\s+de\s+(\d{1,2})\s+de\s+(\w+)\s+del?\s+(\d{4}))",
                 re.I)
ART = re.compile(r"^\s*Art\.\s*([\d.]+(?:\s*\.\d+)?)\s*\.?-?\s*$|^\s*Art\.\s*([\d.]+)\s*\.-", re.M)


def text() -> str:
    d = fitz.open(fetch.cached(LEXIS))
    t = "\n".join(p.get_text() for p in d)
    return re.sub(r"CÓDIGO ORGÁNICO INTEGRAL PENAL, COIP - Página \d+\s*LEXIS FINDER - www\.lexis\.com\.ec", " ", t)


def notes() -> list[tuple[str, str, str, str]]:
    """(article, ISO date, edition reference, note text)."""
    t = text()
    pos = [(m.start(), (m.group(1) or m.group(2)).rstrip(".")) for m in ART.finditer(t)]
    out = []
    for m in re.finditer(r"Nota:", t):
        art = next((a for s, a in reversed(pos) if s < m.start()), "general")
        # Lexis prints the note's first line before the word "Nota:" (layout order), so read around it
        body = re.sub(r"\s+", " ", t[max(0, m.start() - 160):m.start()] + " " + t[m.end():m.end() + 600])
        for r in REF.finditer(body[:400]):
            mon = r.group(4).lower()
            if mon not in MONTHS:
                continue
            day = f"{int(r.group(5)):04d}-{MONTHS.index(mon) + 1:02d}-{int(r.group(3)):02d}"
            ref = re.sub(r"\s+", " ", r.group(1))
            out.append((art, day, ref, body[:260]))
            break
    return out


def main() -> None:
    pat = sys.argv[sys.argv.index("--notes") + 1] if "--notes" in sys.argv else None
    by: dict[tuple[str, str], list[str]] = collections.defaultdict(list)
    for art, day, ref, body in notes():
        num = re.search(r"(\d{1,3}) de \d", ref)
        kind = re.search(r"(Edici[oó]n Constitucional|Primer|Segundo|Tercer|Cuarto|Quinto|Sexto|Suplemento|Registro Oficial)", ref, re.I)
        key = (day, f"{kind.group(1) if kind else '?'} {num.group(1) if num else '?'}")
        if pat and re.search(pat, body, re.I):
            print(art, day, "|", body)
        if art not in by[key]:
            by[key].append(art)
    if pat:
        return
    for (day, ref), arts in sorted(by.items()):
        cut = arts if "--full" in sys.argv else arts[:25]
        print(f"{day}  {ref:28s} {len(arts):4d} :: {', '.join(cut)}{' ...' if len(cut) < len(arts) else ''}")


if __name__ == "__main__":
    main()
