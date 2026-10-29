"""Build corpus.json for Ecuador from the cached Registro Oficial PDFs only (no network).

    python -X utf8 parse.py            writes corpus.json (atomically, via corpus.json.tmp)

The Constitution of 2008 is read from Registro Oficial No. 449 (20 October 2008).
Every later version is the previous one with the provisions that an amending act
replaced, taken word for word from that act's own Registro Oficial edition
(amendments.py lists, per act, which provision is replaced and where its new text
sits in the act's PDF).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import fetch  # noqa: E402
import rotext  # noqa: E402

DOCS_DATE = "2026-10-28"
RO449 = ("http://esacc.corteconstitucional.gob.ec/storage/api/v1/10_DWL_FL/"
         "eyJjYXJwZXRhIjoicm8iLCJ1dWlkIjoiMDZmMTE3NmQtMGMxNC00OTNmLWFhZGYtMjQ0ZmQ0OWQ1OTVmLnBkZiJ9")

ORD = ["PRIMERA", "SEGUNDA", "TERCERA", "CUARTA", "QUINTA", "SEXTA", "SÉPTIMA", "OCTAVA", "NOVENA", "DÉCIMA",
       "UNDÉCIMA", "DUODÉCIMA", "DECIMOTERCERA", "DECIMOCUARTA", "DECIMOQUINTA", "DECIMOSEXTA", "DECIMOSÉPTIMA",
       "DECIMOCTAVA", "DECIMONOVENA", "VIGÉSIMA", "VIGESIMOPRIMERA", "VIGESIMOSEGUNDA", "VIGESIMOTERCERA",
       "VIGESIMOCUARTA", "VIGESIMOQUINTA", "VIGESIMOSEXTA", "VIGESIMOSÉPTIMA", "VIGESIMOCTAVA", "VIGESIMONOVENA",
       "TRIGÉSIMA"]
ORD_LABEL = ["primera", "segunda", "tercera", "cuarta", "quinta", "sexta", "séptima", "octava", "novena", "décima",
             "undécima", "duodécima", "decimotercera", "decimocuarta", "decimoquinta", "decimosexta",
             "decimoséptima", "decimoctava", "decimonovena", "vigésima", "vigesimoprimera", "vigesimosegunda",
             "vigesimotercera", "vigesimocuarta", "vigesimoquinta", "vigesimosexta", "vigesimoséptima",
             "vigesimoctava", "vigesimonovena", "trigésima"]
ORD_RE = re.compile(r"^(" + "|".join(sorted(ORD, key=len, reverse=True)) + r")\s*\.?-\s*")
HEAD_RE = re.compile(r"^(T[IÍ]TULO\s+[IVXL]+|Cap[ií]tulo\s+\w+|CAP[IÍ]TULO\s+[IVXL]+|Secci[oó]n\s+\w+)\s*$")
ART_RE = re.compile(r"^Art\.\s*-?\s*(\d+)\s*\.?\s*-")  # RT art. 16 is printed "Art.- 16.-"


def sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def need(url: str) -> Path:
    p = fetch.cached(url)
    if p is None:
        raise SystemExit(f"not in cache: {url} (run fetch.py first)")
    return p


def unit(label: str, kind: str, paras: list[str]) -> dict:
    return {"label": label, "kind": kind, "text": "".join(p + "\n" for p in paras)}


def art_key(n: int, prefix: str = "art") -> str:
    return f"{prefix}-{n:03d}"


def base_constitution() -> tuple[dict, Path]:
    path = need(RO449)
    paras = rotext.paragraphs(path, 7)  # pages 1-7 are the edition's cover and index
    units: dict[str, dict] = {}
    titles: list[str] = []
    order: list[str] = []
    cur: list[str] | None = None
    section = "pre"
    expect_name = False

    def open_unit(key: str, label: str, kind: str) -> list[str]:
        if key in units:
            raise SystemExit(f"duplicate unit {key}")
        units[key] = {"label": label, "kind": kind, "paras": []}
        order.append(key)
        return units[key]["paras"]

    for p in paras:
        if section == "pre":
            if p.endswith("PREÁMBULO") and "preambulo" not in units:
                # the index's last entries run into the heading on page 8
                cur = open_unit("preambulo", "Preámbulo", "preamble")
                cur.append("PREÁMBULO")
                continue
            if p.startswith("CONSTITUCIÓN DE LA REPÚBLICA DEL ECUADOR"):
                titles.append(p)
                section = "body"
                cur = None
                continue
            if cur is not None:
                cur.append(p)
            continue
        if section == "final" and p.startswith("f.)"):
            break
        if expect_name:
            expect_name = False
            if not ART_RE.match(p) and not HEAD_RE.match(p) and not ORD_RE.match(p) and len(p) < 160:
                titles.append(p)
                continue
        if p == "DISPOSICIONES TRANSITORIAS":
            section, cur = "dt", None
            titles.append(p)
            continue
        if p == "DISPOSICIÓN DEROGATORIA":
            section = "dd"
            cur = open_unit("disp-derogatoria", "Disposición derogatoria", "repeal")
            cur.append(p)
            continue
        if p == "RÉGIMEN DE TRANSICIÓN":
            section, cur = "rt", None
            titles.append(p)
            continue
        if p == "DISPOSICIÓN FINAL":
            section = "final"
            cur = open_unit("disp-final", "Disposición final", "final")
            cur.append(p)
            continue
        if HEAD_RE.match(p):
            titles.append(p)
            expect_name = True
            continue
        m = ART_RE.match(p)
        if m and section in ("body", "rt"):
            n = int(m.group(1))
            if section == "body":
                cur = open_unit(art_key(n), f"Art. {n}", "art")
            else:
                cur = open_unit(f"regimen-transicion-art-{n:02d}", f"Régimen de transición, art. {n}", "transitional")
            cur.append(p)
            continue
        m = ORD_RE.match(p)
        if m and section == "dt":
            i = ORD.index(m.group(1)) + 1
            cur = open_unit(f"disp-transitoria-{i:02d}", f"Disposición transitoria {ORD_LABEL[i - 1]}", "transitional")
            cur.append(p)
            continue
        if cur is None:
            raise SystemExit(f"text outside any unit: {p[:80]!r}")
        cur.append(p)

    # sanity: the numbering the source promises
    arts = [k for k in order if k.startswith("art-")]
    assert arts == [art_key(i) for i in range(1, 445)], "articles 1-444 not complete and in order"
    dts = [k for k in order if k.startswith("disp-transitoria-")]
    assert len(dts) == 30, len(dts)
    rts = [k for k in order if k.startswith("regimen-transicion-")]
    assert rts == [f"regimen-transicion-art-{i:02d}" for i in range(1, 31)], rts
    out = {k: unit(units[k]["label"], units[k]["kind"], units[k]["paras"]) for k in order}
    out["titulos"] = unit("Títulos, capítulos y secciones", "heading", titles)
    return out, path


COUNTRY = {
    "code": "EC", "name": "Ecuador", "slug": "ecuador", "lang": "es",
    "tz": "America/Guayaquil",
    "future_branch": "futuro",
    "publisher": {"name": "Registro Oficial del Ecuador", "email": "registro@registroficial.invalid"},
    "default_in_force_rule": {
        "text": ("Código Civil (codificación 2005) art. 6: \"La ley entrará en vigencia a partir de su promulgación en "
                 "el Registro Oficial y por ende será obligatoria y se entenderá conocida de todos desde entonces. "
                 "Podrá sin embargo, en la misma ley, designarse un plazo especial para su vigencia a partir de su "
                 "promulgación.\" The Constitution's own Disposición final puts it in force on its publication in "
                 "the Registro Oficial."),
        "source": ("http://esacc.corteconstitucional.gob.ec/storage/api/v1/10_DWL_FL/"
                   "eyJjYXJwZXRhIjoicm8iLCJ1dWlkIjoiYzMwNzA4MTgtYTg5NC00OTA3LWFmNGItZTI3NDZlNmQxODJlLnBkZiJ9"),
    },
    "licence_note": ("Texto oficial: Registro Oficial del Ecuador (www.registroficial.gob.ec), órgano de la "
                     "Corte Constitucional."),
}


def build() -> dict:
    base, base_path = base_constitution()
    laws = {
        "constitucion-2008": {
            "label": "Constitución de 2008",
            "title": "Constitución de la República del Ecuador (aprobada en el referéndum del 28 de septiembre de 2008)",
            "kind": "referendum",
            "enacted": "2008-09-28",
            "published": "2008-10-20",
            "url": RO449,
            "temporary_until": None,
            "restores": None,
            "note": None,
        }
    }
    versions = [{
        "from": "2008-10-20",
        "source_url": RO449,
        "sha256": sha_file(base_path),
        "units": base,
        "credits": {},
        "note": "Registro Oficial No. 449, lunes 20 de octubre de 2008.",
    }]
    import amendments  # noqa: E402  (applies each amending act to the previous version)
    amendments.apply_all(versions, laws)
    acts = [{
        "slug": "constitucion",
        "short": "CRE",
        "title": "Constitución de la República del Ecuador",
        "url": RO449,
        "first_law": "constitucion-2008",
        "earlier_laws": [],
        "versions": versions,
    }]
    requests = sum(1 for _ in (HERE / ".cache" / "requests.jsonl").open(encoding="utf-8"))
    return {
        "country": COUNTRY,
        "sources": [{
            "name": "Registro Oficial del Ecuador",
            "url": "https://www.registroficial.gob.ec",
            "retrieved": DOCS_DATE,
            "requests": requests,
            "licence": "No licence stated on the site; official gazette text.",
            "notes": ("One PDF per gazette edition, served by esacc.corteconstitucional.gob.ec. Editions were found "
                      "through the site's month listings (admin-ajax) and search. No dated consolidation exists, so "
                      "every version is the 2008 text with each amending act's replacements applied."),
        }],
        "laws": laws,
        "acts": acts,
        "applies": [],
        "decisions": DECISIONS + amendments.DECISIONS,
        "ai_use": [
            "No generative model wrote legal text. Parsing is rule-based (pymupdf text blocks). The amendment map in "
            "amendments.py (which provision each act replaces, and the anchors around its new text in the act's PDF) "
            "was written by an AI agent (Claude) from reading each act; the words themselves are cut from the PDFs.",
            "No OCR output is legal text in this record. OCR (Windows.Media.Ocr) was used, only to read and not as text, on image-only pages of the court ruling 018-18-SIN-CC "
            "and its auto (dates and scope) and of Decreto Ejecutivo 147 of 2025 (which article it concerned).",
        ],
    }


DECISIONS = [
    "Text: the Constitution of 2008 is taken from Registro Oficial No. 449 of 20 October 2008 (pymupdf text blocks, one "
    "per column). Paragraphs follow the printed blank lines; a paragraph cut by a column or page break is re-joined "
    "when the first part has no closing punctuation or the next starts in lower case. Page headers are dropped.",
    "Words broken at a line end with a hyphen ('afectivo-', 'decretos-', 'agro-') keep the printed hyphen and are "
    "joined without a space; the gazette does not say which hyphens are soft.",
    "Typography is normalised once: NBSP to space, curly quotes and guillemets to straight quotes, en and em dashes to "
    "'-', runs of spaces to one. Missing final stops in the gazette (for example art. 333, first paragraph) are kept.",
    "Units: one file per article (art-001 to art-444), per transitional provision (disp-transitoria-01 to -30), per "
    "article of the Régimen de transición (regimen-transicion-art-01 to -30), plus the preamble, the Disposición "
    "derogatoria and the Disposición final. Headings of titles, chapters and sections are kept, in order, in titulos.md. "
    "The signatures, the certification and the electoral tribunal's notice printed after the Disposición final are "
    "not part of the text and are left out.",
    "In force: the Constitution's Disposición final puts it in force on its publication in the Registro Oficial, "
    "20 October 2008. It was approved in the referendum of 28 September 2008, so its law is of kind 'referendum' "
    "with that day as enacted.",
]

if __name__ == "__main__":
    corpus = build()
    tmp = HERE / "corpus.json.tmp"
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(corpus, fh, ensure_ascii=False, indent=1, sort_keys=False)
        fh.write("\n")
    os.replace(tmp, HERE / "corpus.json")
    v = corpus["acts"][0]["versions"]
    print(f"corpus.json: {len(v)} versions, {len(v[-1]['units'])} units in the last")
