"""Reading-only index of the COIP's amending acts from 2023 on, from the editorial notes of the Ediciones Legales
consolidation of 2026 (copy on aduana.gob.ec, "Última Reforma: Cuarto Suplemento del Registro Oficial 275,
29-IV-2026"), and of the Andina Ediciones compilation "Actualizado: 24/08/2026" (legalcloud.ec copy) for the months
after it.

Never a source of wording: only the notes "(Reformado por el Art. 12 de la Ley s/n, R.O. 279-S, 29-III-2023)" are
read (same patterns as coip/index_notes.py), to learn which Registro Oficial editions amended which articles.

    python -X utf8 coip/index_el2026.py [--since YYYY] [--full] [--notes REGEX] [--andina]
"""
from __future__ import annotations

import collections
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import fetch  # noqa: E402
from index_notes import NOTE, REF  # noqa: E402

import fitz  # noqa: E402

EL2026 = "https://www.aduana.gob.ec/wp-content/uploads/2026/05/CODIGO-ORGANICO-INTEGRAL-PENAL-COIP.pdf"
ANDINA2026 = ("https://legalcloud.ec/wp-content/uploads/2026/08/"
              "Codigo-Organico-Integral-Penal-COIP-24-08-2026-Normativa-Ecuatoriana-1.pdf")
# an article heading "Art. 61.- Expulsión ..." or "Art. 678-A. Clasificación ..." anywhere in a line: the notes sit
# inside the heading, so the heading need not start the line
ART = re.compile(r"\bArt\.\s*(\d+(?:\.\d+)*(?:-[A-Z])?)\s*\.\s*-?\s*[A-ZÁÉÍÓÚ(]")
JUNK = re.compile(r"https://edicioneslegales\.com\.ec/|Pág\. \d+ de \d+|Todos los derechos reservados\. Prohibida su "
                  r"reproducción parcial o total\.|Piense en el medio ambiente\. Imprima solo de ser necesario\.")
ROM = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]


def text(url: str) -> str:
    d = fitz.open(fetch.cached(url))
    return JUNK.sub(" ", "\n".join(p.get_text() for p in d))


def notes(url: str = EL2026) -> list[tuple[str, str, str]]:
    """(article label, Registro Oficial reference, note text) in document order."""
    t = text(url)
    pos = [(m.start(), re.sub(r"\s+", "", m.group(1)).rstrip(".")) for m in ART.finditer(t)]
    out = []
    for m in NOTE.finditer(t):
        art = next((a for s, a in reversed(pos) if s < m.start()), "?")
        body = re.sub(r"\s+", " ", m.group(1))
        for r in REF.findall(body) or ["?"]:
            out.append((art, re.sub(r"\s+", "", r), body))
    return out


def when(ro: str) -> tuple:
    m = re.search(r"(\d{1,2})-([IVX]+)-(\d{4})", ro)
    return (int(m.group(3)), ROM.index(m.group(2)) + 1, int(m.group(1))) if m else (0, 0, 0)


def main(argv: list[str]) -> None:
    since = int(argv[argv.index("--since") + 1]) if "--since" in argv else 2023
    pat = argv[argv.index("--notes") + 1] if "--notes" in argv else None
    url = ANDINA2026 if "--andina" in argv else EL2026
    by_ro: dict[str, list[str]] = collections.defaultdict(list)
    for art, ro, body in notes(url):
        if when(ro)[0] < since:
            continue
        if pat and re.search(pat, body, re.I):
            print(art, "|", body)
        if art not in by_ro[ro]:
            by_ro[ro].append(art)
    if pat:
        return
    for ro, arts in sorted(by_ro.items(), key=lambda x: when(x[0])):
        cut = arts if "--full" in argv else arts[:40]
        print(f"{len(arts):4d}  {ro}  :: {', '.join(cut)}{' ...' if len(cut) < len(arts) else ''}")


if __name__ == "__main__":
    main(sys.argv[1:])
