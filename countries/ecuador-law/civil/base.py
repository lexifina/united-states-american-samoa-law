"""The Código Civil as codified in 2005 (Codificación 2005-010, Registro Oficial Suplemento 46, 24-VI-2005).

Reads only the cached gazette PDF. Units: art-0001 .. art-2424, disp-transitoria, disp-final, and `titulos` (the
Libro / Título / Parágrafo headings in order, one per line).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import fetch  # noqa: E402
import rotext  # noqa: E402

RO46_2005 = ("http://esacc.corteconstitucional.gob.ec/storage/api/v1/10_DWL_FL/"
             "eyJjYXJwZXRhIjoicm8iLCJ1dWlkIjoiYzMwNzA4MTgtYTg5NC00OTA3LWFmNGItZTI3NDZlNmQxODJlLnBkZiJ9")
HEAD = re.compile(r"^(LIBRO|T[IÍ]TULO|Par[aá]grafo|PAR[AÁ]GRAFO|Cap[ií]tulo|CAP[IÍ]TULO|Secci[oó]n|SECCI[OÓ]N)\b"
                  r"|^[IVX]+( [A-ZÁÉÍÓÚ].*)?$")  # also the numbered sub-headings "II", "II Reglas relativas a ..."
ART = re.compile(r"^Art\.\s*(\d+)\s*\.?\s*-")


def art_key(n: int, extra: str = "") -> str:
    return f"art-{n:04d}" + (f"-{extra}" if extra else "")


def units_from_paragraphs(ps: list[str]) -> dict:
    start = ps.index("TITULO PRELIMINAR")
    units: dict[str, dict] = {}
    heads: list[str] = []
    cur: str | None = None
    in_head = False
    expect = 1
    for p in ps[start:]:
        m = ART.match(p)
        if m:
            n = int(m.group(1))
            if n != expect:
                raise SystemExit(f"article {n} where {expect} was expected")
            expect += 1
            cur = art_key(n)
            units[cur] = {"label": f"Art. {n}", "kind": "art", "text": ""}
            in_head = False
        elif p.startswith("DISPOSICION TRANSITORIA.-"):
            cur = "disp-transitoria"
            units[cur] = {"label": "Disposición transitoria", "kind": "transitional", "text": ""}
            in_head = False
        elif p.startswith("DISPOSICION FINAL.-"):
            cur = "disp-final"
            units[cur] = {"label": "Disposición final", "kind": "final", "text": ""}
            in_head = False
        elif cur == "disp-final" and p.startswith("LA COMISION DE LEGISLACION"):
            break
        elif HEAD.match(p) or (in_head and cur is not None):
            in_head = True
            for x in re.split(r"\s+(?=Par[aá]grafo \d+o\.$)|\s+(?=[IVX]+ Reglas )", p):
                # a sub-heading numeral set in the next text block ("Del depósito necesario" + "I")
                m2 = re.fullmatch(r"(?!LIBRO|T[IÍ]TULO)(.+?) ([IVX]+)", x.strip())
                heads.extend([m2.group(1), m2.group(2)] if m2 else [x.strip()])
            continue
        elif cur is None:
            heads.append(p)  # the heading lines before art. 1
            continue
        if re.search(r"\bArts?\.\n$", units[cur]["text"]) and re.match(r"\d", p):
            # a column break right after "Art." (arts. 845 and 907): the number belongs to the same sentence
            units[cur]["text"] = units[cur]["text"][:-1] + " " + p + "\n"
            continue
        units[cur]["text"] += p + "\n"
    if expect != 2425:
        raise SystemExit(f"stopped at article {expect - 1}")
    units["titulos"] = {"label": "Títulos y parágrafos", "kind": "headings", "text": "".join(h + "\n" for h in heads)}
    return units


def base_units() -> tuple[dict, str]:
    path = fetch.cached(RO46_2005)
    if path is None:
        raise SystemExit(f"not in cache: {RO46_2005}")
    return units_from_paragraphs(rotext.paragraphs(path)), RO46_2005


if __name__ == "__main__":
    u, _ = base_units()
    print(len(u), sum(len(x["text"]) for x in u.values()))
    print(u["art-0006"]["text"])
    print(u["disp-final"]["text"])
    print(u["titulos"]["text"][:400])
