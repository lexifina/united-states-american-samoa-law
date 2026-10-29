"""The Código Orgánico Integral Penal as enacted (Registro Oficial Suplemento 180, 10-II-2014).

Reads only the cached gazette PDF (text layer). Units, in the Code's own order:
  art-001 .. art-730                     the articles ("Artículo 1.- Finalidad.- ...")
  disp-general-01 .. 04, disp-transitoria-01 .., disp-reformatoria-01 .., disp-derogatoria-01 .., disp-final
  titulos                                the Libro / Título / Capítulo / Sección / Parágrafo headings, one per line
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import fetch  # noqa: E402
import rotext  # noqa: E402

S180_2014 = ("http://esacc.corteconstitucional.gob.ec/storage/api/v1/10_DWL_FL/"
             "eyJjYXJwZXRhIjoicm8iLCJ1dWlkIjoiMjkwYzMxODUtNTY0OC00MzNjLTk1ZDEtZDg0NjY1NDc5NWI0LnBkZiJ9")
HEAD = re.compile(r"^(LIBRO|T[IÍ]TULO|CAP[IÍ]TULO|SECCI[OÓ]N|PAR[AÁ]GRAFO)\s", re.I)
ART = re.compile(r"^Art[ií]culo\s+(\d+)\s*\.-")
ORDINALS = ["PRIMERA", "SEGUNDA", "TERCERA", "CUARTA", "QUINTA", "SEXTA", "SÉPTIMA", "OCTAVA", "NOVENA", "DÉCIMA"]
TENS = {"DÉCIMO": 10, "VIGÉSIMO": 20, "TRIGÉSIMO": 30, "CUADRAGÉSIMO": 40}
UNIT_WORDS = {"PRIMERA": 1, "SEGUNDA": 2, "TERCERA": 3, "CUARTA": 4, "QUINTA": 5, "SEXTA": 6, "SÉPTIMA": 7,
              "OCTAVA": 8, "NOVENA": 9}
DISP = {"DISPOSICIONES GENERALES": ("disp-general", "Disposición general", "general"),
        "DISPOSICIONES TRANSITORIAS": ("disp-transitoria", "Disposición transitoria", "transitional"),
        "DISPOSICIONES REFORMATORIAS": ("disp-reformatoria", "Disposición reformatoria", "amending"),
        "DISPOSICIONES DEROGATORIAS": ("disp-derogatoria", "Disposición derogatoria", "repeal")}


def ordinal(word: str) -> int | None:
    """'PRIMERA' -> 1, 'DÉCIMA' -> 10, 'DÉCIMO PRIMERA' -> 11, 'VIGÉSIMA' -> 20, 'VIGÉSIMO SEXTA' -> 26."""
    w = word.strip().upper()
    if w in UNIT_WORDS:
        return UNIT_WORDS[w]
    if w == "DÉCIMA":
        return 10
    if w in ("VIGÉSIMA", "TRIGÉSIMA", "CUADRAGÉSIMA"):
        return TENS[w[:-1] + "O"]
    parts = w.split()
    if len(parts) == 2 and parts[0] in TENS and parts[1] in UNIT_WORDS:
        return TENS[parts[0]] + UNIT_WORDS[parts[1]]
    return None


ORD_RE = re.compile(r"^((?:D[EÉ]CIMO|VIG[EÉ]SIMO|TRIG[EÉ]SIMO)\s+\w+|\w+):\s")


def art_key(n: int, extra: str = "") -> str:
    return f"art-{n:03d}" + (f"-{extra}" if extra else "")


_WORD = r"[a-záéíóúñü]+"
_BROKEN = re.compile(rf"\b({_WORD})-({_WORD})\b")


def vocabulary(ps: list[str]) -> set[str]:
    """Every lower-case word that occurs unbroken (not joined to another by a hyphen)."""
    out: set[str] = set()
    for p in ps:
        for m in re.finditer(rf"(?<![-\w])({_WORD})(?![-\w])", p.lower()):
            out.add(m.group(1))
    return out


def join_broken(ps: list[str], vocab: set[str]) -> list[str]:
    """The Registro Oficial hyphenates words at line ends; the text layer keeps the hyphen ('in-definidas',
    'abste-nerse'). A hyphenated pair is joined when the joined word occurs unbroken in the Code's text (or in the
    same edition); otherwise the printed hyphen stays (compounds like 'político-administrativo')."""
    def fix(m: re.Match) -> str:
        w = m.group(1) + m.group(2)
        return w if w.lower() in vocab else m.group(0)
    return [_BROKEN.sub(fix, p) for p in ps]


_BASE_VOCAB: set[str] = set()


def base_vocab() -> set[str]:
    if not _BASE_VOCAB:
        _BASE_VOCAB.update(vocabulary(rotext.paragraphs(fetch.cached(S180_2014))))
    return _BASE_VOCAB


def paragraphs(url: str = S180_2014) -> list[str]:
    return join_broken(rotext.paragraphs(fetch.cached(url)), base_vocab())


HEAD_NEXT: list[list[str]] = []  # [heading line, key of the first unit after it], filled by units_from_paragraphs


def units_from_paragraphs(ps: list[str]) -> dict:
    HEAD_NEXT.clear()
    start = ps.index("LIBRO PRELIMINAR NORMAS RECTORAS")
    units: dict[str, dict] = {}
    heads: list[str] = []
    cur: str | None = None
    expect = 1
    section: tuple | None = None
    expect_ord = 1
    for p in ps[start:]:
        m = ART.match(p)
        if section is None and m:
            n = int(m.group(1))
            if n != expect:
                raise SystemExit(f"Artículo {n} where {expect} was expected")
            expect += 1
            cur = art_key(n)
            for h in HEAD_NEXT:
                if h[1] == "":
                    h[1] = cur
            units[cur] = {"label": f"Art. {n}", "kind": "art", "lines": [p]}
            continue
        if p in DISP:
            section = DISP[p]
            expect_ord = 1
            cur = None
            continue
        if p == "DISPOSICIÓN FINAL":
            section = ("disp-final", "Disposición final", "final")
            cur = "disp-final"
            units[cur] = {"label": "Disposición final", "kind": "final", "lines": []}
            continue
        if cur == "disp-final" and p.startswith("Dado y suscrito"):
            break
        if section is None and HEAD.match(p):
            heads.append(p)
            HEAD_NEXT.append([p, ""])
            cur = None
            continue
        if section is not None and section[0] != "disp-final":
            mo = ORD_RE.match(p)
            n = ordinal(mo.group(1)) if mo else None
            if n == expect_ord:
                expect_ord += 1
                cur = f"{section[0]}-{n:02d}"
                units[cur] = {"label": f"{section[1]} {mo.group(1).lower()}", "kind": section[2], "lines": [p]}
                continue
        if cur is None:
            raise SystemExit(f"text outside any unit: {p[:80]!r}")
        units[cur]["lines"].append(p)
    if expect != 731:
        raise SystemExit(f"articles end at {expect - 1}")
    out = {k: {"label": u["label"], "kind": u["kind"], "text": "\n".join(u["lines"]) + "\n"} for k, u in units.items()}
    out["titulos"] = {"label": "Títulos y capítulos", "kind": "headings", "text": "\n".join(heads) + "\n"}
    return out


def first_version() -> dict:
    return units_from_paragraphs(paragraphs())


if __name__ == "__main__":
    u = first_version()
    kinds: dict[str, int] = {}
    for v in u.values():
        kinds[v["kind"]] = kinds.get(v["kind"], 0) + 1
    print(len(u), kinds)
    for k in ("art-001", "disp-general-04", "disp-transitoria-23", "disp-reformatoria-01", "disp-derogatoria-26",
              "disp-final"):
        print(k, "|", u[k]["text"][:200].replace("\n", " / "))
