"""Reading-only index of the COIP's amending acts, from the editorial notes of an unofficial consolidation.

The consolidation (repositorio.consejodecomunicacion.gob.ec, "Última Reforma: Edición Constitucional del Registro
Oficial 222, 13-X-2021", Ediciones Legales style) is never a source of wording: only its inline notes
"(Sustituido por el Art. 12 de la Ley s/n, R.O. 107-S, 24-XII-2019)" are read, to learn which Registro Oficial
editions amended which articles. Prints one line per edition with the articles it names.

    python -X utf8 coip/index_notes.py [--full]
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

CONSOLIDATION = "https://repositorio.consejodecomunicacion.gob.ec/bitstream/CONSEJO_REP/250/1/COIP.pdf"
NOTE = re.compile(r"\(((?:Reformad|Sustituid|Agregad|Derogad|Suprimid|Eliminad|Incorporad|Declarad|Inclu[ií]d|"
                  r"Renumerad|Interpretad|Modificad)[^()]{0,400}?(?:R\.\s*O\.|Registro Oficial|E\.\s*C\.)[^()]{0,120})\)",
                  re.S)
REF = re.compile(r"((?:R\.\s*O\.|E\.\s*C\.)\s*(?:E\.\s*C\.\s*)?\d+(?:\s*-\s*\d?[A-Z]+)?\s*,\s*\d{1,2}\s*-\s*[IVX]+\s*-\s*\d{4})")
ART = re.compile(r"^\s*Art\.\s*([\d.]+(?:\s*(?:bis|ter|\.\d+))?)\s*\.?-", re.M)


def notes() -> list[tuple[str, str, str]]:
    """(article label, Registro Oficial reference, note text) in document order."""
    d = fitz.open(fetch.cached(CONSOLIDATION))
    text = "\n".join(p.get_text() for p in d)
    pos = [(m.start(), m.group(1).rstrip(".")) for m in ART.finditer(text)]
    out = []
    for m in NOTE.finditer(text):
        art = next((a for s, a in reversed(pos) if s < m.start()), "?")
        body = re.sub(r"\s+", " ", re.sub(r"Página \d+ de \d+", " ", m.group(1)))
        refs = REF.findall(body) or ["?"]
        for r in refs:
            out.append((art, re.sub(r"\s+", "", r), body))
    return out


def main() -> None:
    by_ro: dict[str, list[str]] = collections.defaultdict(list)
    for art, ro, _ in notes():
        if art not in by_ro[ro]:
            by_ro[ro].append(art)

    def when(ro: str) -> tuple:
        m = re.search(r"(\d{1,2})-([IVX]+)-(\d{4})", ro)
        rom = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]
        return (int(m.group(3)), rom.index(m.group(2)) + 1, int(m.group(1))) if m else (0, 0, 0)

    for ro, arts in sorted(by_ro.items(), key=lambda x: when(x[0])):
        cut = arts if "--full" in sys.argv else arts[:30]
        print(f"{len(arts):4d}  {ro}  :: {', '.join(cut)}{' ...' if len(cut) < len(arts) else ''}")


if __name__ == "__main__":
    main()
