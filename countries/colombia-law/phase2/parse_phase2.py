"""Build corpus.d/60-phase2.json for Colombia: Código Penal (Ley 599 de 2000), Código General del Proceso
(Ley 1564 de 2012) and Código Sustantivo del Trabajo.

Reads only ../.cache/ (written by ../fetch.py and phase2/fetch_phase2.py); no network. Deterministic.
The reconstruction engine is phase2/engine.py (a frozen copy of the codes helper's codes/parse_codes.py, itself a
generalisation of ../parse.py): per provision, versions are rebuilt from the basedoc's earlier texts ("Legislación
Anterior"), its inline amendment markers and its Notas de Vigencia; in-force days of amending acts come from their own
vigencia clauses (their basedoc pages) or the default rule.

Usage:  python -X utf8 phase2/parse_phase2.py [--report] [--out FILE] [--only codigo-penal,...]
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COUNTRY = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import engine as E  # noqa: E402

OUT = os.path.join(COUNTRY, "corpus.d", "60-phase2.json")
SIGN_OFF = re.compile(r"\s*(El Presidente del (honorable |H\. )?Senado|EL PRESIDENTE DEL (HONORABLE |H\. )?SENADO|"
                      r"REP[ÚU]BLICA DE COLOMBIA\s*-\s*GOBIERNO NACIONAL|PUBL[ÍI]QUESE Y (EJEC[ÚU]TESE|C[ÚU]MPLASE))")

# Typing slips in the codes' notes, fixed by what the same page shows: "Texto original de la Ley 599 de 0000" (the
# Código Penal's own original), "Texto original de la Ley 1565 de 2012" in the Código General del Proceso (Ley 1564 de
# 2012 is the code; Ley 1565 de 2012 is an unrelated act on returning nationals).
E.KEY_FIXES.update({"ley-599-0000": "ley-599-2000", "ley-1565-2012": "ley-1564-2012"})

# Vigencia clauses read by hand from the acts' own cached basedoc pages, where a clause has a general rule and a
# one-year exception that the pattern rules would take for the whole act.
E.HAND_RULES.update({
    "ley-2080-2021": ("pub", "Ley 2080 de 2021, art. 86: 'La presente ley rige a partir de su publicación, con excepción de "
                             "las normas que modifican las competencias de los juzgados y tribunales administrativos y del "
                             "Consejo de Estado, las cuales solo se aplicarán respecto de las demandas que se presenten un año "
                             "después de publicada esta ley.' (the exception is about which suits the new competences apply "
                             "to, not when the words took effect)"),
    "ley-2502-2025": ("pub+12m", "Ley 2502 de 2025, art. 6: 'La presente Ley rige a partir de su sanción, promulgación y "
                                 "publicación en el Diario Oficial ... La modificación del artículo 296 de la Ley 599 de 2000, "
                                 "establecida en esta ley, comenzará a regir un (1) año después de su sanción y promulgación.' "
                                 "(its only change to these codes is art. 296 of the Código Penal)"),
})

_unit_day = E.unit_day


def unit_day(key: str, text: str) -> None:
    """Ley 890 de 2004, art. 15 (its own page): 'La presente ley rige a partir del 1o. de enero de 2005, con excepción de
    los artículos 7o. a 13, los que entrarán en vigencia en forma inmediata.' A Código Penal note naming one of its
    articles 7 to 13 ("Artículo adicionado por el artículo 7 de la Ley 890 de 2004, publicada en el Diario Oficial No.
    45.602, de 7 de julio de 2004") dates that change from the act's publication."""
    _unit_day(key, text)
    m = re.search(r"art[íi]culo (\d+)o?\.? de la Ley 890 de 2004", text)
    if key == "ley-890-2004" and m and 7 <= int(m.group(1)) <= 13 and E.LAWS[key].get("published"):
        E.UNIT_DAYS[key] = E.LAWS[key]["published"]


E.unit_day = unit_day

_doc_units = E.doc_units


def doc_units(name: str) -> list[dict]:
    """The engine's split, with the signatures after the last article cut off (they are not part of the text)."""
    units = _doc_units(name)
    for u in units:
        # "<Penas aumentadas por el artículo 14 de la Ley 890 de 2004 ...>" is how the Código Penal marks an article
        # whose penalties Ley 890 raised (with its earlier text in Legislación Anterior): for the engine it is an
        # article-level change by that law. Only the marker is rewritten; markers are never part of the text.
        # "<Ley 1288 de 2009 declarada INEXEQUIBLE>" on an article that law added: the whole article was struck.
        u["items"] = [(it[0], re.sub(r"&lt;Ley \d+ de \d{4} declarada INEXEQUIBLE&gt;", "&lt;Artículo INEXEQUIBLE&gt;",
                                     re.sub(r"&lt;Penas? aumentadas? por el art", "&lt;Artículo modificado por el art", it[1])))
                      + tuple(it[2:]) if it[0] == "p" else it for it in u["items"]]
    for u in units[1:]:
        items = u["items"]
        for k, it in enumerate(items):
            if it[0] == "p" and SIGN_OFF.match(E.plain(it[1])):
                # the signer's name stands on the paragraph before "El Presidente ..."
                cut = k - 1 if k > 0 and items[k - 1][0] == "p" and E.plain(items[k - 1][1]).isupper() else k
                u["items"] = items[:cut]
                break
    return units


E.doc_units = doc_units


def para_text(units: list[dict], anchor: str) -> str:
    u = next(u for u in units if u["name"] == anchor)
    return " ".join(E.plain(E.strip_markers(it[1])) for it in u["items"] if it[0] == "p")


def first_law(key: str, page: str, title: str, units: list[dict], vig_anchor: str | None, rule_note: str) -> str:
    """Register the act itself, dated by its own heading (sanction, Diario Oficial) and its own vigencia article."""
    kind, n, y = key.split("-")
    enacted, pub = E.page_header(page, y)
    E.register(key)
    law = E.LAWS[key]
    law.update({"title": title, "enacted": enacted, "published": pub, "url": E.BASE + page + ".html"})
    return enacted, pub


def finish(res: dict, page: str) -> list[dict]:
    sha = E.doc_sha(page)
    for v in res["versions"]:
        v["source_url"] = E.BASE + page + ".html"
        v["sha256"] = sha
    return res["versions"]


DECISIONS: list[str] = []


def build_penal() -> dict:
    page = "ley_0599_2000"
    units = doc_units(page)
    E.scan_law_dates(units)
    key = "ley-599-2000"
    enacted, pub = first_law(key, page, "Por la cual se expide el Código Penal", units, "476", "")
    clause = para_text(units, "476")
    m = re.search(r"un \(1\) año después de su promulgación", clause)
    if not m or not pub:
        raise SystemExit(f"Código Penal: vigencia clause or publication day not found ({clause!r}, {pub})")
    start = E.add_months(pub, 12)
    E.IN_FORCE[key], E.IN_FORCE_WHY[key] = start, f"Ley 599 de 2000, art. 476: '{clause}'"
    res = E.build_act(page, start)
    vs = finish(res, page)
    vs[0]["note"] = (f"The code as enacted (Ley 599 de 2000, sanctioned {enacted}, Diario Oficial No. 44.097 of {pub}), in "
                     f"force from {start} under its art. 476: '{clause}'")
    DECISIONS.append(
        "Código Penal: the figures of the penalties in the Parte Especial after 1 January 2005 are the publisher's: Ley 890 "
        "de 2004, art. 14, raised every penalty of the Parte Especial by a third in the minimum and a half in the maximum "
        "without rewriting the articles, and the source shows each article 'con las penas aumentadas' under the marker "
        "'<Penas aumentadas por el artículo 14 de la Ley 890 de 2004, a partir del 1o. de enero de 2005>', with the "
        "earlier wording in its Legislación Anterior. Those changes are credited to Ley 890 de 2004 on 1 January 2005; "
        "the source's own warning says the computation is the editor's reading of art. 14.")
    return {"slug": "codigo-penal", "short": "CPen", "title": "Código Penal (Ley 599 de 2000)", "url": E.BASE + page + ".html",
            "first_law": key, "earlier_laws": [], "versions": vs}


def build_cgp() -> dict:
    page = "ley_1564_2012"
    units = doc_units(page)
    E.scan_law_dates(units)
    key = "ley-1564-2012"
    enacted, pub = first_law(key, page, "Por medio de la cual se expide el Código General del Proceso y se dictan otras "
                                        "disposiciones", units, "627", "")
    clause = para_text(units, "627")
    if not pub or "entrarán a regir a partir de la promulgación" not in clause:
        raise SystemExit(f"CGP: art. 627 or publication day not found ({pub})")
    start = pub
    res = E.build_act(page, start)
    vs = finish(res, page)
    vs[0]["note"] = (f"The code as promulgated (Ley 1564 de 2012, Diario Oficial No. 48.489 of {pub}). Its entry into force "
                     "was staggered by its art. 627: some articles (24, 30 num. 8, 31 num. 2, 33 num. 2, 206, 467, 610 to "
                     "627) from promulgation, others from 1 October 2012 or 1 July 2013, and the rest from 1 January 2014, "
                     "gradually, as the Consejo Superior de la Judicatura put it in place in each district. The history "
                     "dates the whole code from promulgation; art. 627 gives each article's own start.")
    DECISIONS.append(
        "Código General del Proceso: its first version is dated from promulgation (" + pub + "), the day the first of its "
        "articles took effect under art. 627 num. 1; the article itself (in the text) gives the later starts of the rest. "
        "Splitting the first version by article would need the Consejo Superior de la Judicatura's district-by-district "
        "acts, which the source does not give.")
    return {"slug": "codigo-general-del-proceso", "short": "CGP", "title": "Código General del Proceso (Ley 1564 de 2012)",
            "url": E.BASE + page + ".html", "first_law": key, "earlier_laws": [], "versions": vs}


BRACED = {"empleador": "patrono", "empleadores": "patronos", "EMPLEADOR": "PATRONO", "EMPLEADORES": "PATRONOS"}


def debrace(text: str, before: bool) -> str:
    """'{empleador}': Ley 50 de 1990 art. 107 replaced 'patrono' with 'empleador' throughout the code; the source shows
    the replaced word in braces. Before that law the word was 'patrono'."""
    def rep(m):
        w = m.group(1)
        return BRACED[w] if before and w in BRACED else w
    return re.sub(r"\{([^{}\n]{1,40})\}", rep, text)


def build_cst() -> dict:
    page = "codigo_sustantivo_trabajo"
    units = doc_units(page)
    E.scan_law_dates(units)
    head = " ".join(E.plain(it[1]) for it in units[0]["items"] if it[0] == "p")
    m = re.search(r"Diario Oficial No\.? ?27\.622, del (\d+ de \w+ de \d{4})", head)
    start = E.date_es(m.group(1)) if m else None
    clause = para_text(units, "490")
    if not start or "primero (1o) de enero del año de mil novecientos cincuenta y uno" not in clause:
        raise SystemExit("CST: edition day or art. 490 not found")
    earlier = []
    for k in ("dec-2663-1950", "dec-3743-1950", "dec-905-1951"):
        E.register(k)
        earlier.append(k)
    res = E.build_act(page, start)
    vs = res["versions"]
    # Ley 50 de 1990, art. 107: 'patrono' -> 'empleador' everywhere (shown in braces).
    l50 = E.register("ley-50-1990")
    d50 = E.law_day(l50)
    if not d50:
        raise SystemExit("CST: Ley 50 de 1990 has no in-force day")
    out, prev = [], None
    inserted = False
    for v in vs:
        if not inserted and v["from"] >= d50:
            base = prev
            if v["from"] > d50 and base is not None:
                out.append({"from": d50, "units": {k: dict(u, text=debrace(u["text"], False)) for k, u in base.items()},
                            "credits": {}})
                prev_units_new = out[-1]["units"]
                old = {k: dict(u, text=debrace(u["text"], True)) for k, u in base.items()}
                out[-1]["credits"] = {k: [l50] for k, u in prev_units_new.items() if old.get(k, {}).get("text") != u["text"]}
            inserted = True
        if "units" in v:
            before = v["from"] < d50
            new_units = {k: dict(u, text=debrace(u["text"], before)) for k, u in v["units"].items()}
            if v["from"] == d50 and prev is not None:
                old = {k: dict(u, text=debrace(u["text"], True)) for k, u in prev.items()}
                for k, u in new_units.items():
                    if old.get(k, {}).get("text") != u["text"] and l50 not in v["credits"].get(k, []):
                        v["credits"].setdefault(k, []).append(l50)
            prev = v["units"]
            v = dict(v, units=new_units)
        out.append(v)
    vs = out
    sha = E.doc_sha(page)
    for v in vs:
        v["source_url"] = E.BASE + page + ".html"
        v["sha256"] = sha
    vs[0]["note"] = (f"The official edition of the code ordered by Decreto 3743 de 1950, art. 46, published in Diario Oficial "
                     f"No. 27.622 of {start}, compiling Decretos 2663 and 3743 de 1950 and 905 de 1951, as the source gives "
                     f"it. Its art. 490: '{clause}' The edition's text is dated from its publication; the source does not "
                     "give the text of 1 January 1951.")
    DECISIONS.append(
        "Código Sustantivo del Trabajo: the oldest text the source gives is the official edition published in Diario Oficial "
        f"No. 27.622 of {start}; it is the first version (credited as oldest version available, naming Decretos 2663 and "
        "3743 de 1950 and 905 de 1951). Ley 50 de 1990, art. 107, replaced the word 'patrono' with 'empleador' "
        "throughout the code; the source shows the replaced word in braces ('{empleador}', its Resumen de Notas de "
        f"Vigencia, note 74). Before {d50} those words read 'patrono(s)', from {d50} 'empleador(es)', credited to Ley 50 "
        "de 1990; the braces are dropped.")
    return {"slug": "codigo-sustantivo-del-trabajo", "short": "CST", "title": "Código Sustantivo del Trabajo",
            "url": E.BASE + page + ".html", "first_law": None, "earlier_laws": earlier, "versions": vs}


BUILDERS = {"codigo-penal": build_penal, "codigo-general-del-proceso": build_cgp,
            "codigo-sustantivo-del-trabajo": build_cst}


def to_deltas(versions: list[dict]) -> list[dict]:
    """After the first version, each version gives `changes` ({unit key: unit, or None to remove}) instead of the full
    `units` (SCHEMA.md, "Large acts"); versions that changed no words keep no units at all."""
    out, prev = [], None
    for v in versions:
        if "units" not in v or prev is None:
            out.append(v)
            if "units" in v:
                prev = v["units"]
            continue
        cur = v["units"]
        ch = {k: cur[k] for k in cur if prev.get(k) != cur[k]}
        ch.update({k: None for k in prev if k not in cur})
        w = {k: x for k, x in v.items() if k != "units"}
        w["changes"] = dict(sorted(ch.items()))
        out.append(w)
        prev = cur
    return out


def full_versions(versions: list[dict]) -> list[dict]:
    """The inverse of to_deltas (for checks): every version with its full units."""
    out, cur = [], None
    for v in versions:
        if "units" in v:
            cur = dict(v["units"])
        elif "changes" in v:
            cur = dict(cur)
            for k, u in v["changes"].items():
                if u is None:
                    cur.pop(k, None)
                else:
                    cur[k] = u
        out.append(dict({k: x for k, x in v.items() if k != "changes"}, units=cur))
    return out


# The Código Sustantivo del Trabajo belongs to another agent's part (corpus.d/70-cst.json) since 2026-10-28 19:20Z;
# build_cst() is kept for reference only and is not run.
PARTS = [("60-phase2.json", ["codigo-penal", "codigo-general-del-proceso"], ("Código Penal", "Código General del Proceso"))]
PREFIX = {"codigo-penal": ("ley_0599_2000", "CP"), "codigo-general-del-proceso": ("ley_1564_2012", "CGP"),
          "codigo-sustantivo-del-trabajo": ("codigo_sustantivo_trabajo", "CST")}


def write_part(acts: list[dict], out: str, names: tuple) -> None:
    used = ({l for a in acts for v in a["versions"] for ls in v["credits"].values() for l in ls}
            | {a["first_law"] for a in acts if a["first_law"]} | {l for a in acts for l in a["earlier_laws"]})
    laws = {k: dict(v) for k, v in sorted(E.LAWS.items()) if k in used}
    rules = [f"In force {E.IN_FORCE[k]}: {laws[k]['label']} ({E.IN_FORCE_WHY[k]})."
             for k in sorted(laws, key=lambda k: (E.IN_FORCE.get(k, ""), k)) if k in E.IN_FORCE]
    pages = [PREFIX[a["slug"]][0] for a in acts]
    approx = sorted({r.split(":")[0] for r in E.REPORT if "latest earlier text differs" in r
                     and r.split(" ")[0] in pages})
    gaps = sorted({m for m in E.MISSING_UNITS})
    part = {
        "sources": [{
            "name": "Secretaría General del Senado, basedoc: " + ", ".join(names) + " and the acts that amended them",
            "url": E.BASE, "retrieved": E.RETRIEVED, "requests": 0,
            "licence": "Official legal text is free to reproduce (Ley 23 de 1982, art. 41). The compilation's editorial notes "
                       "(Avance Jurídico) are not reproduced; only the official text and the facts the notes state are used.",
            "notes": ", ".join(pages) + " (base, continuation pages and js/ note files), plus the base and last page of each "
                     "amending act. Requests are counted in the country's shared log (corpus.json's source)."}],
        "laws": laws,
        "acts": [dict(a, versions=to_deltas(a["versions"])) for a in acts],
        "decisions": [
            ", ".join(names) + " (phase2/parse_phase2.py, with the engine phase2/engine.py): versions are rebuilt per "
            "article from the basedoc's earlier texts, inline amendment markers and Notas de Vigencia, as for the "
            "Constitution and the Código Civil. Where the source names an act but gives no text after it, the article "
            "reads '" + E.MISSING_LINE + "' for that period.",
            "Constitutional Court rulings that struck text are laws of kind 'court', dated by the ruling's day as the "
            "source gives it; rulings that upheld text on a condition are court laws with a note and change no words.",
            "In-force days of amending acts: the act's own vigencia clause as its basedoc page gives it; otherwise the "
            "default rule (Ley 4 de 1913, art. 52: two months after promulgation). A day a provision's own note gives "
            "applies to that provision. The list below gives the day and the rule for each act.",
            "Dates come only from the act itself: the Diario Oficial day on the act's own page wins over a day the code's "
            "notes give; a note's Diario Oficial day is not given to an act named only inside another act's quoted title; "
            "and an act whose vigencia clause has a general rule and exceptions is dated by the rule that covers the "
            "changed provision (Ley 890 de 2004: arts. 7 to 13 immediately, the rest from 1 January 2005; Ley 2502 de "
            "2025: art. 296 of the Código Penal one year after promulgation; Ley 2080 de 2021: from publication).",
            "The source's earlier texts often leave out the article's epigraph (its title); where the latest earlier text "
            "differs from today's only by that or by a change no note names, today's text is used from the latest "
            "named act's day. Articles where that happened: " + (", ".join(approx) or "none") + ".",
        ] + [d for d in DECISIONS if d.startswith(names)] + rules,
        "ai_use": ["None at data-build time: phase2/fetch_phase2.py, phase2/parse_phase2.py and phase2/engine.py are "
                   "deterministic code, written with Claude Code (claude-opus-5-5); no model reads, writes or summarises "
                   "legal text."],
    }
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(part, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    os.replace(tmp, out)
    print(f"wrote {out}: {len(acts)} acts, {sum(len(a['versions']) for a in acts)} versions, {len(laws)} laws, "
          f"{os.path.getsize(out) // 1024} KB")
    for a in acts:
        print(f"  {a['slug']}: {len(a['versions'])} versions")


def main(argv: list[str]) -> None:
    """Writes corpus.d/60-phase2.json (Código Penal, CGP) and corpus.d/61-cst.json (CST); --out-dir DIR elsewhere."""
    acts = {s: BUILDERS[s]() for _, slugs, _ in PARTS for s in slugs}
    d = argv[argv.index("--out-dir") + 1] if "--out-dir" in argv else os.path.dirname(OUT)
    for fname, slugs, names in PARTS:
        write_part([acts[s] for s in slugs], os.path.join(d, fname), names)
    if "--report" in argv:
        for r in E.REPORT:
            print("  ", r)
    else:
        print(f"  {len(E.REPORT)} report lines (--report to print)")


if __name__ == "__main__":
    main(sys.argv[1:])
