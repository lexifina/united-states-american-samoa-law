"""Build corpus.d/80-batch3.json for Colombia: Código de Comercio (Decreto 410 de 1971), CPACA (Ley 1437 de 2011),
Código de Procedimiento Penal (Ley 906 de 2004) and Código de la Infancia y la Adolescencia (Ley 1098 de 2006).

Reads only ../.cache/ (batch3/fetch_batch3.py, ../fetch.py); no network; deterministic. Uses the Phase 2 driver and
engine (phase2/parse_phase2.py, phase2/engine.py): the same per-provision reconstruction, in-force rules and checks.

Usage:  python -X utf8 batch3/parse_batch3.py [--report] [--out-dir DIR] [--only slug,...]
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COUNTRY = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(COUNTRY, "phase2"))
import parse_phase2 as P  # noqa: E402

E = P.E
# Typing slips in these codes' notes, fixed by what the same notes show: "Texto original de la Ley 1437 de 2001" (the
# CPACA's own original, Ley 1437 de 2011); "Texto adicionado por la Ley 1908 de 2019" (its note: "artículo 21 de la Ley
# 1908 de 2018"); "Texto con las modificaciones introducidas por el Decreto 1959 de 2019" (the notes on the same article:
# "modificado por el artículo 3 de la Ley 1959 de 2019").
# Ley 44 de 1981 (art. 13 rewrote art. 159 of the Código de Comercio): neither the basedoc nor Colpensiones holds it,
# no Internet Archive copy exists, and the code's notes give no Diario Oficial. The change is shown on the last day of
# the year in its name, the latest day it can have been sanctioned; it may have taken effect later (stated in decisions).
E.HAND_RULES["ley-44-1981"] = ("1981-12-31", "no source gives its day (the basedoc and Colpensiones do not hold the act, "
                                             "and the Código de Comercio's note gives no Diario Oficial): shown on the "
                                             "last day of 1981, the latest day it can have been sanctioned; it may have "
                                             "taken effect later")
# Vigencia clauses read by hand from the acts' own cached pages where the pattern rules misread them.
E.HAND_RULES.update({
    "ley-1328-2009": ("pub", "Ley 1328 de 2009, art. 101: 'La presente ley rige a partir de su promulgación con excepción de "
                             "las reglas especiales de vigencia en ella contempladas y de los siguientes artículos: 1o a 22 "
                             "... 35 ... y 61 a 66 ...' (its change here, a derogation in Código de Comercio art. 1230 by "
                             "art. 101 itself, is under the general rule)"),
    "ley-2475-2025": ("pub+12m", "Ley 2475 de 2025, art. 8: 'La presente ley rige doce (12) meses a partir de su publicación "
                                 "y deroga las disposiciones que le sean contrarias.'"),
    "ley-2592-2026": ("pub+6m", "Ley 2592 de 2026, art. 12: 'La presente ley rige a partir de los seis (6) meses de su "
                                "publicación, a partir de los cuales se derogan todas las disposiciones que le sean "
                                "contrarias.'"),
    "ley-1760-2015": ("pub", "Ley 1760 de 2015, art. 5: 'La presente ley rige a partir de la fecha de su promulgación, salvo "
                             "el artículo 1o y el numeral 6 del artículo 4o, los cuales entrarán a regir en un (1) año "
                             "contado a partir de la fecha de su promulgación ...' (its arts. 2 to 4 rewrote arts. 308, 310 "
                             "and 317 of the Código de Procedimiento Penal; numeral 6 of art. 317 as rewritten took effect a "
                             "year later, which one commit for the article cannot show)"),
})
E.KEY_FIXES.update({"ley-1437-2001": "ley-1437-2011", "ley-1908-2019": "ley-1908-2018", "dec-1959-2019": "ley-1959-2019"})
# The Código de Comercio ends "Comuníquese y publíquese. Dado en Bogotá, D.E., a 27 de marzo de 1971." and the signers.
P.SIGN_OFF = re.compile(P.SIGN_OFF.pattern + r"|\s*COMUN[ÍI]QUESE Y PUBL[ÍI]QUESE|\s*Comun[íi]quese y publ[íi]quese")
OUT_DIR = os.path.join(COUNTRY, "corpus.d")

HEAD_RE = re.compile(r"\s*(LIBRO|T[ÍI]TULO|CAP[ÍI]TULO|SECCI[ÓO]N|PARTE|DISPOSICIONES)\b[^a-zñáéíóú]{0,60}$")
_units_p2 = P.doc_units


def doc_units(name: str) -> list[dict]:
    """The Phase 2 split, with three repairs for these pages:
    * the Código de Comercio marks in braces the words corrected by the errata note printed at the end of its official
      edition (the same Diario Oficial No. 33.339): the corrected words are the official text, so the braces go;
    * an article whose anchor the publisher named "Nivel001" (art. 508 of the Código de Comercio) is an article;
    * heading paragraphs ("SECCIÓN III.", "REPRESENTANTE LEGAL") left at the end of an article without an anchor of
      their own become a heading of their own, so they are neither in the article nor lost."""
    units = _units_p2(name)
    out = []
    for u in units:
        if name == "codigo_comercio":
            u["items"] = [tuple(x.replace("{", "").replace("}", "") if isinstance(x, str) and k > 0 and (it[0] == "p" or k == 2)
                                else x for k, x in enumerate(it)) for it in u["items"]]
        if u["name"].startswith("Nivel") and re.match(r"ART[IÍ]CULO\s+\d", u["label"] or ""):
            u["name"] = E.label_num(u["label"]) or u["name"]
        # A heading anchor that holds only part of "ARTÍCULO" (label "A", the rest "RTÍCULO 1913. ..." in the
        # paragraph) or nothing (label "", the paragraph starts "ARTÍCULO 1129. ..."): rebuild the heading.
        if u is not units[0] and (u["label"] or "") in ("", "A", "AR", "ART") and u["items"] and u["items"][0][0] == "p":
            whole = E.html.escape(u["label"] or "", quote=False) + u["items"][0][1]
            m = re.match(r"\s*(ART(?:Í|&Iacute;|I)CULO\s+\d+[A-Z]?\.(?:\s*&lt;(?:(?!&gt;).)*&gt;\.?)?)", whole, re.S)
            if m:
                u["label"] = E.plain(m.group(1))
                u["items"] = [("p", whole[m.end():])] + u["items"][1:]
        items = u["items"]
        cut = None
        if u is not units[0] and re.match(r"ART[IÍ]CULO", u["label"] or ""):
            for k, it in enumerate(items):
                if it[0] == "p" and HEAD_RE.match(E.plain(it[1])) and all(x[0] == "p" for x in items[k:]):
                    cut = k
                    break
        if cut is not None:
            head = [E.tidy(E.to_text(x[1])) for x in items[cut:]]
            head = [h for h in head if h]
            u["items"] = items[:cut]
            out.append(u)
            out.append({"name": f"Nivel-{u['name']}-tail", "label": head[0], "page": u["page"],
                        "items": [("p", E.html.escape(h, quote=False)) for h in head[1:]]})
            continue
        out.append(u)
    return out


P.doc_units = doc_units
E.doc_units = doc_units
DECISIONS = P.DECISIONS


def article_text(units: list[dict], number: str) -> str:
    """Plain text of the article numbered `number` (by its heading label)."""
    for u in units:
        if E.label_num(u["label"] or "") == number:
            return " ".join(E.plain(E.strip_markers(it[1])) for it in u["items"] if it[0] == "p")
    raise SystemExit(f"article {number} not found")


def register_first(key: str, page: str, title: str) -> tuple[str | None, str | None]:
    kind, n, y = key.split("-")
    enacted, pub = E.page_header(page, y)
    E.register(key)
    E.LAWS[key].update({"title": title, "enacted": enacted, "published": pub, "url": E.BASE + page + ".html"})
    return enacted, pub


def build(page: str, key: str, slug: str, short: str, title: str, law_title: str, start_fn) -> dict:
    units = P.doc_units(page)
    E.scan_law_dates(units)
    enacted, pub = register_first(key, page, law_title)
    start, why, note = start_fn(units, enacted, pub)
    E.IN_FORCE[key], E.IN_FORCE_WHY[key] = start, why
    res = E.build_act(page, start)
    vs = P.finish(res, page)
    vs[0]["note"] = note
    DECISIONS.append(f"{title}: first version from {start}: {why}")
    return {"slug": slug, "short": short, "title": title, "url": E.BASE + page + ".html",
            "first_law": key, "earlier_laws": [], "versions": vs}


def start_comercio(units, enacted, pub):
    a = article_text(units, "2038")
    if "empezará a regir el 1o. de enero de 1972, con excepción del artículo 821" not in a or not enacted:
        raise SystemExit(f"Código de Comercio art. 2038 or heading: {a!r}")
    return (enacted, f"Decreto 410 de 1971, art. 2038: '{a}' (the first version is dated from the day it was issued, "
                     f"{enacted}, when the parts excepted took effect; the rest from 1 January 1972)",
            f"The code as issued (Decreto 410 de 1971, of {enacted}, Diario Oficial of {pub}). Its art. 2038: '{a}' The "
            f"history dates the whole code from {enacted}, the day the excepted parts (art. 821, Libro IV Título XIII "
            f"Capítulo V and Libro VI) took effect; the rest took effect on 1 January 1972.")


def start_cpaca(units, enacted, pub):
    a = article_text(units, "308")
    m = re.search(r"comenzar[áa] a regir el dos \(2\) de julio del año 2012", a)
    if not m:
        raise SystemExit(f"CPACA art. 308: {a[:300]!r}")
    return ("2012-07-02", f"Ley 1437 de 2011, art. 308: '{a[:300]}'",
            f"The code as promulgated (Ley 1437 de 2011, Diario Oficial of {pub}), in force from 2 July 2012 under its art. "
            f"308: '{a[:300]}'")


def start_cpp(units, enacted, pub):
    a = article_text(units, "533")
    b = article_text(units, "530")
    if "Los artículos 531 y 532 del presente código, entrarán en vigencia a partir de su publicación" not in a or             "1o. de enero de 2005" not in b or not pub:
        raise SystemExit(f"CPP arts. 530/533: {a[:300]!r}")
    return (pub, f"Ley 906 de 2004, art. 533: '{a}' and art. 530 (by judicial district from 1 January 2005 to 1 January "
                 f"2008). The first version is dated from publication ({pub}), when arts. 531 and 532 took effect.",
            f"The code as promulgated (Ley 906 de 2004, Diario Oficial of {pub}). Its arts. 531 and 532 took effect on "
            f"publication; the rest applies to crimes after 1 January 2005, by judicial district as its art. 530 sets out "
            f"(2005 to 2008). The history dates the whole code from publication. Art. 533: '{a}'")


def start_cia(units, enacted, pub):
    a = article_text(units, "216")
    if not re.search(r"seis \(6\) meses después de su promulgación", a) or "El artículo 199" not in a or not pub:
        raise SystemExit(f"CIA art. 216: {a[:300]!r}")
    return (pub, f"Ley 1098 de 2006, art. 216: '{a[:600]}' The first version is dated from promulgation ({pub}), when "
                 f"art. 199 took effect; the rest six months later ({E.add_months(pub, 6)}), the adolescent criminal "
                 f"system gradually from 2007 to 2009.",
            f"The code as promulgated (Ley 1098 de 2006, Diario Oficial of {pub}). Its art. 199 took effect on "
            f"promulgation; the rest six months later ({E.add_months(pub, 6)}), and the system of criminal responsibility "
            f"for adolescents gradually from 1 January 2007 to 31 December 2009 (art. 216). The history dates the whole "
            f"code from promulgation.")


BUILDERS = {
    "codigo-de-comercio": lambda: build("codigo_comercio", "dec-410-1971", "codigo-de-comercio", "CCo",
                                        "Código de Comercio (Decreto 410 de 1971)", "Por el cual se expide el Código de Comercio",
                                        start_comercio),
    "cpaca": lambda: build("ley_1437_2011", "ley-1437-2011", "cpaca", "CPACA",
                           "Código de Procedimiento Administrativo y de lo Contencioso Administrativo (Ley 1437 de 2011)",
                           "Por la cual se expide el Código de Procedimiento Administrativo y de lo Contencioso Administrativo",
                           start_cpaca),
    "codigo-de-procedimiento-penal": lambda: build("ley_0906_2004", "ley-906-2004", "codigo-de-procedimiento-penal", "CPP",
                                                   "Código de Procedimiento Penal (Ley 906 de 2004)",
                                                   "Por la cual se expide el Código de Procedimiento Penal", start_cpp),
    "codigo-de-la-infancia-y-la-adolescencia": lambda: build("ley_1098_2006", "ley-1098-2006",
                                                             "codigo-de-la-infancia-y-la-adolescencia", "CIA",
                                                             "Código de la Infancia y la Adolescencia (Ley 1098 de 2006)",
                                                             "Por la cual se expide el Código de la Infancia y la Adolescencia",
                                                             start_cia),
}
P.PREFIX.update({"codigo-de-comercio": ("codigo_comercio", "CCo"), "cpaca": ("ley_1437_2011", "CPACA"),
                 "codigo-de-procedimiento-penal": ("ley_0906_2004", "CPP"),
                 "codigo-de-la-infancia-y-la-adolescencia": ("ley_1098_2006", "CIA")})
NAMES = ("Código de Comercio", "Código de Procedimiento Administrativo", "Código de Procedimiento Penal",
         "Código de la Infancia")


def anachronisms(acts: list[dict]) -> list[str]:
    """No change may take effect before its act exists: a version credited to an act dated before that act's own
    sanction or publication (unless the act's own clause reaches back) is an error; so is a ruling dated before the
    text it rules on. Returns the problems found."""
    out = []
    for a in acts:
        for v in a["versions"]:
            for k, ls in v.get("credits", {}).items():
                for l in ls:
                    law = E.LAWS.get(l, {})
                    first = min(d for d in (law.get("enacted"), law.get("published")) if d) if (
                        law.get("enacted") or law.get("published")) else None
                    if first and v["from"] < first:
                        out.append(f"{a['slug']} {k}: {l} credited on {v['from']}, before the act's own date {first}")
                    act0 = E.LAWS.get(a["first_law"] or "", {})
                    born = act0.get("enacted") or act0.get("published")
                    if law.get("kind") == "court" and born and law.get("enacted") and law["enacted"] < born:
                        out.append(f"{a['slug']} {k}: ruling {l} ({law['enacted']}) is older than the code ({born})")
    return out


def main(argv: list[str]) -> None:
    only = argv[argv.index("--only") + 1].split(",") if "--only" in argv else list(BUILDERS)
    acts = [BUILDERS[s]() for s in BUILDERS if s in only]
    problems = anachronisms(acts)
    for p in problems:
        E.note("anachronism " + p)
    d = argv[argv.index("--out-dir") + 1] if "--out-dir" in argv else OUT_DIR
    P.write_part(acts, os.path.join(d, "80-batch3.json"), tuple(n for n in NAMES))
    print(f"  {len(problems)} anachronisms")
    if "--report" in argv:
        for r in E.REPORT:
            print("  ", r)


if __name__ == "__main__":
    main(sys.argv[1:])
