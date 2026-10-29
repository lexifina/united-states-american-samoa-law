"""Build corpus.d/98-batch7.json for Colombia: national laws the basedoc carries with their history. Ley 1150 de 2007
(contratación), Ley 1474 de 2011 (Estatuto Anticorrupción), Ley 1712 de 2014 (transparencia y acceso a la información),
Ley 789 de 2002 (protección social), Ley 1429 de 2010 (formalización y generación de empleo), Ley 1523 de 2012 (gestión
del riesgo de desastres), Ley 99 de 1993 (Ley General Ambiental), Ley 388 de 1997 (desarrollo territorial) and the
Código Nacional de Recursos Naturales Renovables (Decreto Ley 2811 de 1974).

Reads only ../.cache/ (batch7/fetch_batch7.py); no network; deterministic. Imports the batch 6 driver (its generic page
repairs), which imports the batch 5, 4, 3 and Phase 2 drivers and the engine (phase2/engine.py): the same per-provision
reconstruction from the Senado basedoc, rulings as `court` laws, in-force days from each act's own vigencia clause, and
the placeholder line '[La fuente no da el texto vigente en esta fecha.]' where the source gives no earlier wording.

Usage:  python -X utf8 batch7/parse_batch7.py [--report] [--out-dir DIR] [--only slug,...] [--show page:art,...]
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COUNTRY = os.path.dirname(HERE)
for _d in ("batch6", "batch5", "batch4", "batch3", "phase2"):
    sys.path.insert(0, os.path.join(COUNTRY, _d))
import parse_batch6 as B6  # noqa: E402

B5 = B6.B5
B4 = B6.B4
B3 = B6.B3
P = B6.P
E = B6.E
OUT_DIR = os.path.join(COUNTRY, "corpus.d")
PART = "98-batch7.json"
DECISIONS = P.DECISIONS
E.RETRIEVED = "2026-10-29"  # this batch's fetch day (the part's `retrieved`)
PRE_START = B4.PRE_START
cut_signers = B6.cut_signers


def _clause(units, art, must, key, enacted, pub):
    a = cut_signers(B3.article_text(units, art))
    if not a.startswith(must) or not pub:
        raise SystemExit(f"{key} art. {art}: {a[:300]!r} {enacted} {pub}")
    return a


def on_publication(page, key, label, art, must, what="promulgation"):
    """A start function for an act in force from its publication (or promulgation, or issue) under its own article."""
    def start(units, enacted, pub):
        a = _clause(units, art, must, key, enacted, pub)
        day = enacted if what == "issue" else pub
        return (day, f"{label}, art. {art}: '{a[:600]}' (sanctioned {enacted}, Diario Oficial of {pub})",
                f"The act as promulgated ({label}, sanctioned {enacted}, Diario Oficial of {pub}), in force from {day} "
                f"under its art. {art}: '{a[:600]}'")
    return start


def start_1150(units, enacted, pub):
    a = _clause(units, "33", "La presente ley empieza a regir seis (6) meses después de su promulgación, con excepción del "
                "artículo 6o que entrará a regir a los dieciocho (18) meses", "Ley 1150", enacted, pub)
    six, eighteen = E.add_months(pub, 6), E.add_months(pub, 18)
    return (pub, f"Ley 1150 de 2007, art. 33: '{a}' The first version is dated from promulgation ({pub}), when arts. 9 and "
                 f"17 took effect; the rest six months later ({six}), art. 6 eighteen months later ({eighteen}).",
            f"The act as promulgated (Ley 1150 de 2007, Diario Oficial No. 46.691 of {pub}). Its arts. 9 and 17 took effect "
            f"on promulgation; the rest six months later ({six}), and art. 6 eighteen months later ({eighteen}) (art. 33). "
            f"The history dates the whole act from promulgation. Art. 33: '{a}'")


def start_1712(units, enacted, pub):
    a = _clause(units, "33", "La presente ley rige a los seis (6) meses de la fecha de su promulgación para todos los "
                "sujetos obligados del orden nacional. Para los entes territoriales la ley entrará en vigencia un año "
                "después de su promulgación.", "Ley 1712", enacted, pub)
    six, year = E.add_months(pub, 6), E.add_months(pub, 12)
    return (six, f"Ley 1712 de 2014, art. 33: '{a}' The first version is dated six months after promulgation ({six}), when "
                 f"it took effect for national bodies; for territorial bodies a year after ({year}).",
            f"The act as promulgated (Ley 1712 de 2014, Diario Oficial No. 49.084 of {pub}), in force from {six} for the "
            f"national bodies it binds and from {year} for territorial bodies (art. 33). The history dates it from {six}. "
            f"Art. 33: '{a}'")


ACTS = [
    # slug, page, first law, short, title, law title, start function
    ("ley-1150-2007", "ley_1150_2007", "ley-1150-2007", "L1150",
     "Ley 1150 de 2007, eficiencia y transparencia en la contratación pública",
     "Por medio de la cual se introducen medidas para la eficiencia y la transparencia en la Ley 80 de 1993 y se dictan "
     "otras disposiciones generales sobre la contratación con Recursos Públicos", start_1150),
    ("estatuto-anticorrupcion", "ley_1474_2011", "ley-1474-2011", "EAC", "Estatuto Anticorrupción (Ley 1474 de 2011)",
     "Por la cual se dictan normas orientadas a fortalecer los mecanismos de prevención, investigación y sanción de actos "
     "de corrupción y la efectividad del control de la gestión pública",
     on_publication("ley_1474_2011", "Ley 1474", "Ley 1474 de 2011", "135",
                    "La presente ley rige a partir de su promulgación")),
    ("ley-de-transparencia", "ley_1712_2014", "ley-1712-2014", "LTAIP",
     "Ley de Transparencia y del Derecho de Acceso a la Información Pública Nacional (Ley 1712 de 2014)",
     "Por medio de la cual se crea la Ley de Transparencia y del Derecho de Acceso a la Información Pública Nacional y se "
     "dictan otras disposiciones", start_1712),
    ("ley-789-2002", "ley_0789_2002", "ley-789-2002", "L789",
     "Ley 789 de 2002, sistema de protección social y reforma laboral",
     "Por la cual se dictan normas para apoyar el empleo y ampliar la protección social y se modifican algunos artículos "
     "del Código Sustantivo de Trabajo",
     on_publication("ley_0789_2002", "Ley 789", "Ley 789 de 2002", "52",
                    "La presente ley rige a partir de la fecha de su publicación")),
    ("ley-de-formalizacion-y-generacion-de-empleo", "ley_1429_2010", "ley-1429-2010", "L1429",
     "Ley de Formalización y Generación de Empleo (Ley 1429 de 2010)",
     "Por la cual se expide la Ley de Formalización y Generación de Empleo",
     on_publication("ley_1429_2010", "Ley 1429", "Ley 1429 de 2010", "65",
                    "La presente ley rige a partir de la fecha de su publicación y promulgación")),
    ("gestion-del-riesgo-de-desastres", "ley_1523_2012", "ley-1523-2012", "GRD",
     "Política Nacional de Gestión del Riesgo de Desastres (Ley 1523 de 2012)",
     "Por la cual se adopta la política nacional de gestión del riesgo de desastres y se establece el Sistema Nacional de "
     "Gestión del Riesgo de Desastres y se dictan otras disposiciones",
     on_publication("ley_1523_2012", "Ley 1523", "Ley 1523 de 2012", "96",
                    "La presente ley rige a partir de la fecha de su publicación")),
    ("ley-general-ambiental", "ley_0099_1993", "ley-99-1993", "LGA", "Ley General Ambiental (Ley 99 de 1993)",
     "Por la cual se crea el Ministerio del Medio Ambiente, se reordena el Sector Público encargado de la gestión y "
     "conservación del medio ambiente y los recursos naturales renovables, se organiza el Sistema Nacional Ambiental, SINA "
     "y se dictan otras disposiciones",
     on_publication("ley_0099_1993", "Ley 99", "Ley 99 de 1993", "118",
                    "La presente Ley rige a partir de la fecha de su promulgación")),
    ("ley-de-desarrollo-territorial", "ley_0388_1997", "ley-388-1997", "LDT", "Ley de Desarrollo Territorial (Ley 388 de 1997)",
     "Por la cual se modifica la Ley 9a. de 1989, y la Ley 2a. de 1991 y se dictan otras disposiciones",
     on_publication("ley_0388_1997", "Ley 388", "Ley 388 de 1997", "138",
                    "Las disposiciones de la presente ley rigen a partir de su publicación")),
    ("codigo-de-recursos-naturales", "decreto_2811_1974", "dec-2811-1974", "CRN",
     "Código Nacional de Recursos Naturales Renovables y de Protección al Medio Ambiente (Decreto Ley 2811 de 1974)",
     "Por el cual se dicta el Código Nacional de Recursos Naturales Renovables y de Protección al Medio Ambiente",
     on_publication("decreto_2811_1974", "Decreto 2811", "Decreto Ley 2811 de 1974", "340",
                    "El presente Código rige a partir de la fecha de su expedición", what="issue")),
]
BUILDERS: dict = {}
for _slug, _page, _key, _short, _title, _ltitle, _start in ACTS:
    BUILDERS[_slug] = (lambda pg=_page, k=_key, s=_slug, sh=_short, t=_title, lt=_ltitle, st=_start:
                       B3.build(pg, k, s, sh, t, lt, st))
    P.PREFIX[_slug] = (_page, _short)
NAMES = tuple(t for _, _, _, _, t, _, _ in ACTS)


def finish_part(path: str) -> None:
    with open(path, encoding="utf-8") as f:
        part = json.load(f)
    part["ai_use"] = ["None at data-build time: batch7/fetch_batch7.py and batch7/parse_batch7.py (with batch6/, batch5/, "
                      "batch4/, batch3/ and phase2/, which they import) are deterministic code, written with Claude Code "
                      "(claude-opus-5-5); no model reads, writes or summarises legal text."]
    part["sources"][0]["notes"] += (" Terms checked 2026-10-28: robots.txt disallows only the Joomla system folders, not "
                                    "/senado/basedoc/; each page's footer reserves Avance Jurídico's notes, concordances "
                                    "and arrangement, so only the official text and the facts the notes state are used. "
                                    "Pages retrieved on 2026-10-29 through gitlaw_common/wayback.py host_get (some amending "
                                    "acts' pages earlier, for the other parts, from the same cache).")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(part, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    os.replace(tmp, path)


def main(argv: list[str]) -> None:
    if "--show" in argv:
        for x in argv[argv.index("--show") + 1].split(","):
            page, art = x.split(":")
            print(page, art, B3.article_text(P.doc_units(page), art)[:1500])
        return
    only = argv[argv.index("--only") + 1].split(",") if "--only" in argv else list(BUILDERS)
    acts = [BUILDERS[s]() for s in BUILDERS if s in only]
    for a in acts:
        B6.drop_epigraph_only(a)
        B6.credit_titulos(a)
    names = tuple(n for n in NAMES if any(a["title"] == n for a in acts))
    if B6.TITULOS_CREDITED:
        DECISIONS.append(names[0] + " and the other acts of batch 7: a change of titulos.md (the headings shown while an "
                         "article under them is in force) on a day whose other changes are all credited to one law is "
                         "credited to that law: " + "; ".join(B6.TITULOS_CREDITED) + ".")
    if B6.EPIGRAPH_ONLY:
        DECISIONS.append(names[0] + " and the other acts of batch 7: an article whose words were all struck or repealed but "
                         "whose epigraph the page still prints is absent, not kept as its epigraph alone: "
                         + ", ".join(sorted(set(x.split(" (")[0] for x in B6.EPIGRAPH_ONLY))) + ".")
    if B6.MONTH_FIRST_DO:
        DECISIONS.append(names[0] + " and the other acts of batch 7: amending acts whose page writes the Diario Oficial day "
                         "month first are read from that line: " + "; ".join(sorted(B6.MONTH_FIRST_DO)) + ".")
    if B6.STRUCK_NO_RULING:
        DECISIONS.append(names[0] + " and the other acts of batch 7: words the page shows struck, with no ruling or act the "
                         "source dates, are left out of every version (the engine's rule): "
                         + "; ".join(sorted(set(B6.STRUCK_NO_RULING))) + ".")
    problems = B3.anachronisms(acts)
    for p in problems:
        E.note("anachronism " + p)
    for p in PRE_START:
        E.note("pre-start " + p)
    d = argv[argv.index("--out-dir") + 1] if "--out-dir" in argv else OUT_DIR
    out = os.path.join(d, PART)
    P.write_part(acts, out, names)
    finish_part(out)
    print(f"  {len(problems)} anachronisms, {len(PRE_START)} pre-start events")
    if "--report" in argv:
        for r in E.REPORT:
            print("  ", r)


if __name__ == "__main__":
    main(sys.argv[1:])
