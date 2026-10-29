"""Reading-only index of a Code's amending acts from the 'Nota:' lines of a Lexis-style consolidation in DOCX form
(LegalCloud downloads of the COGEP and the Código del Trabajo, 'Última modificación: 07-02-2023' / '01-02-2023').
Never a source of wording: only the notes are read, to learn which Registro Oficial editions amended which articles.

    python -X utf8 codes/index_docx.py cogep|trabajo [--notes REGEX] [--since YYYY]
"""
from __future__ import annotations

import collections
import html
import re
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import fetch  # noqa: E402

DOCX = {"cogep": "https://legalcloud.ec/download/codigo-organico-general-de-procesos-cogep/?wpdmdl=9478",
        "trabajo": "https://legalcloud.ec/download/codigo-del-trabajo/?wpdmdl=9477"}
MES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
       "noviembre", "diciembre"]
REF = re.compile(r"Registro Oficial\s+((?:\w+\s+)?Suplemento|Edici[oó]n\s+\w+|No\.|)\s*(?:No\.\s*)?(\d+)\s+de\s+(\d{1,2})\s+de\s+"
                 r"(\w+)\s+del?\s+(\d{4})", re.I)


def paras(which: str) -> list[str]:
    z = zipfile.ZipFile(fetch.cached(DOCX[which]))
    x = z.read("word/document.xml").decode("utf-8")
    out = []
    for p in re.findall(r"<w:p[ >].*?</w:p>", x, re.S):
        t = html.unescape(re.sub(r"<[^>]+>", "", re.sub(r"<w:(?:br|tab)[^>]*/>", " ", p)))
        if t.strip():
            out.append(t)
    return out


def notes(which: str) -> list[tuple[str, str, str, str]]:
    """(article, ISO date, RO ref, note) in document order."""
    t = "\n".join(paras(which))
    arts = [(m.start(), m.group(1)) for m in re.finditer(r"Art\.\s*(\d+(?:\.\d+)?(?:\s*\(\d+\))?(?:-[A-Z])?)\s*\.?-", t)]
    out = []
    for m in re.finditer(r"Nota:(.*?)(?=Nota:|Concordancias:|Jurisprudencia:|Art\.\s*\d+|\n[A-ZÁÉÍÓÚ ]{6,}\n|$)", t, re.S):
        art = next((a for s, a in reversed(arts) if s < m.start()), "?")
        body = re.sub(r"\s+", " ", m.group(1)).strip()
        for r in REF.finditer(body):
            mon = r.group(4).lower()
            day = f"{r.group(5)}-{MES.index(mon) + 1:02d}-{int(r.group(3)):02d}" if mon in MES else "?"
            out.append((art, day, f"{r.group(1) or 'RO'} {r.group(2)}".strip(), body))
    return out


def main(argv: list[str]) -> None:
    which = argv[0]
    pat = argv[argv.index("--notes") + 1] if "--notes" in argv else None
    since = argv[argv.index("--since") + 1] if "--since" in argv else "0"
    by: dict[tuple, list[str]] = collections.defaultdict(list)
    for art, day, ro, body in notes(which):
        if day < since:
            continue
        if pat and re.search(pat, body, re.I):
            print(art, "|", body[:300])
        if art not in by[(day, ro)]:
            by[(day, ro)].append(art)
    if pat:
        return
    for (day, ro), arts in sorted(by.items()):
        print(f"{day}  {ro:28s} {len(arts):4d}  {', '.join(arts)}")


if __name__ == "__main__":
    main(sys.argv[1:])
