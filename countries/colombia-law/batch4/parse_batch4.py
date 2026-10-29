"""Build corpus.d/90-batch4.json for Colombia: Código Nacional de Seguridad y Convivencia Ciudadana (Ley 1801 de 2016),
Ley 100 de 1993 (Sistema de Seguridad Social Integral), Código General Disciplinario (Ley 1952 de 2019) and Código
Electoral (Decreto 2241 de 1986).

Reads only ../.cache/ (batch4/fetch_batch4.py, ../fetch.py); no network; deterministic. Imports the batch 3 driver
(batch3/parse_batch3.py: its page repairs, sign-off rule and anachronism check), which imports the Phase 2 driver and
engine (phase2/parse_phase2.py, phase2/engine.py): the same per-provision reconstruction from the Senado basedoc, rulings
as `court` laws, and in-force days from each act's own vigencia clause.

Usage:  python -X utf8 batch4/parse_batch4.py [--report] [--out-dir DIR] [--only slug,...]
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COUNTRY = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(COUNTRY, "batch3"))
sys.path.insert(0, os.path.join(COUNTRY, "phase2"))
import parse_batch3 as B3  # noqa: E402

P = B3.P
E = B3.E
OUT_DIR = os.path.join(COUNTRY, "corpus.d")
PART = "90-batch4.json"
DECISIONS = P.DECISIONS

# Events a provision's history dates before the act's own first day: the engine would fold them into the first version
# (credited to the act itself), so they are listed and the build stops unless each is explained here.
PRE_START: list[str] = []
_assemble = E.assemble


def assemble(timelines, labels, notes_all, order, start):
    for key, sts in timelines.items():
        for d, stt, law in sts[1:]:
            if d < start:
                PRE_START.append(f"{E.CUR_UNIT[0].split(' ')[0]} {key}: {law} on {d}, before the first day {start}")
    return _assemble(timelines, labels, notes_all, order, start)


E.assemble = assemble


# Typing slips in the headings of the source's earlier texts ('Legislación Anterior'), fixed per page by what the same
# article shows: the heading names an act that cannot have written the text. (page, wrong heading, right heading, why)
HEADING_FIXES = [
    ("ley_1801_2016", "Texto original de la Ley 1810 de 2016", "Texto original de la Ley 1801 de 2016",
     "Ley 1801 de 2016, art. 41: its earlier text is headed 'Texto original de la Ley 1810 de 2016'; it is the code's own "
     "original paragraph 3 (Ley 1810 de 2016 is an unrelated act), struck by Sentencia C-281 de 2017"),
    ("ley_1801_2016", "Texto original de la Ley 1805 de 2016", "Texto original de la Ley 1801 de 2016",
     "Ley 1801 de 2016, art. 88: its earlier text is headed 'Texto original de la Ley 1805 de 2016'; it is the code's own "
     "original article (Ley 1805 de 2016 is an unrelated act)"),
    ("ley_1801_2016", "Texto original de la Ley 906 de 2004", "Texto original de la Ley 1801 de 2016",
     "Ley 1801 de 2016, art. 206: its earlier text is headed 'Texto original de la Ley 906 de 2004'; it is the code's own "
     "original article (the Código de Procedimiento Penal never held it; the same article's notes name only Leyes 2030 "
     "de 2020 and 2492 de 2025 as its amenders)"),
    ("ley_0100_1993", "Texto original de la Ley 100 de 2007", "Texto original de la Ley 100 de 1993",
     "Ley 100 de 1993, arts. 204 and 214: their earlier texts are headed 'Texto original de la Ley 100 de 2007'; they are "
     "the act's own original wording (there is no Ley 100 de 2007 in these notes; the next text is Ley 1122 de 2007's)"),
    ("ley_0100_1993", "Texto original del Decreto 2277 de 1979", "Texto original de la Ley 100 de 1993",
     "Ley 100 de 1993, art. 157: the earlier text of its paragraph 4 is headed 'Texto original del Decreto 2277 de 1979' "
     "(the teachers' statute, which never held it); it is the act's own original paragraph"),
]
# Rulings whose effect the Court deferred: the engine dates a strike by the ruling's day, so the ruling's day in the
# source's Jurisprudencia Vigencia note is read as the day the deferral ends (the text leaves the history then); the
# law keeps the decision day as `enacted` and says so in its note. (page, text in the note, read as, law key,
# decision day, effect day, why)
DEFERRED = [
    ("ley_1801_2016", "C-223-17</A> de abril de 2017de 20 de abril de 2017", "C-223-17</A> de 20 de junio de 2019", "c-223-17",
     "2017-04-20", "2019-06-20",
     "Sentencia C-223 de 2017 (20 April 2017) declared Título VI of the Código Nacional de Seguridad y Convivencia "
     "Ciudadana (arts. 47 to 75, the right of assembly) INEXEQUIBLE, deferring the effect 'hasta antes del 20 de junio de "
     "2019' so that Congress could pass a statutory law; the articles leave the text on 20 June 2019."),
]
# Notes that name an act as having "modified" an article whose words it did not change (the act only reassigned a
# function or set rules beside it); read as a plain reference, so the article's wording runs on unbroken.
# (page, text in the Notas de Vigencia, read as, why)
NOTE_FIXES = [
    ("ley_0100_1993", "- Art&iacute;culo modificado parcialmente por el Decreto 132 de 2010, seg&uacute;n lo dispuesto en su",
     "- Ver el Decreto 132 de 2010,",
     "Ley 100 de 1993, arts. 215 and 216: the note 'Artículo modificado parcialmente por el Decreto 132 de 2010, según lo "
     "dispuesto en su artículo 5' names an emergency decree (struck by Sentencia C-374 de 2010) that changed none of their "
     "words and that the source gives no text for; their wording is unbroken"),
    ("ley_0100_1993", "- Art&iacute;culo modificado por el art&iacute;culo <A href='decreto_1280_2002.html#9' >9</A> del "
                      "Decreto 1280 de 2002",
     "- Ver el art&iacute;culo <A href='decreto_1280_2002.html#9' >9</A> del Decreto 1280 de 2002",
     "Ley 100 de 1993, art. 271: Decreto 1280 de 2002, art. 9, gave the competence the article assigns to the Ministerio de "
     "Salud to the Superintendencia Nacional de Salud without rewriting it (the note quotes it); the article's wording is "
     "unbroken"),
]
REPLACED = re.compile(r"&lt;Apartes? tachados? (reemplazad|eliminad)(os?|as?) por ")
NEW_WORDS = re.compile(r"(</S>\s*)&lt;((?:(?!&gt;).)*)&gt;", re.S | re.I)


def replaced_words(h: str) -> str:
    """Words an act replaced or removed, as the Código General Disciplinario shows them: '<Aparte tachado reemplazado por
    el artículo 72 de la Ley 2094 de 2021> ... del <S>auto de citación a audiencia y formulación de cargos</S> <pliego de
    cargos> y ...'. The struck words are the earlier text; the words in angle brackets right after them are the new text
    (not an editor's note), and 'eliminado' means struck with nothing in their place. Given to the engine in the forms it
    reads: words struck by an act ('Aparte tachado derogado por ...') and new words underlined with the correction marker,
    so the earlier version reads the struck words and the later one the new words, credited to the act."""
    m = REPLACED.search(h)
    if not m:
        return h
    h = REPLACED.sub(lambda m: "&lt;Aparte tachado derogado por ", h)
    if m.group(1) == "reemplazad":
        h2 = NEW_WORDS.sub(lambda x: x.group(1) + "<u>" + x.group(2) + "</u>", h)
        if h2 == h:
            raise SystemExit("replaced words without the new words after them: " + E.plain(h)[:200])
        h = "&lt;Texto subrayado corresponde a la corrección&gt; " + h2
    return h


# Ruling notes the engine would misread: the note dates the ruling that struck these words by a ruling on an older act's
# same words. (page, text in the Jurisprudencia Vigencia note, read as, why)
JV_FIXES = [
    ("ley_1952_2019", "- La Corte Constitucional declar&oacute; estarse a lo resuelto en la Sentencia C-181-02, que "
                      "declar&oacute; INEXEQUIBLE la expresi&oacute;n &#8220;grave&#8221; que figuraba en el "
                      "art&iacute;culo 25 de la Ley 200 de 1995 y, en consecuencia, declara INEXEQUIBLE la "
                      "expresi&oacute;n &#8220;grave&#8221;, mediante",
     "- Aparte tachado (la expresi&oacute;n &#8220;grave&#8221;) declarado INEXEQUIBLE por la Corte Constitucional mediante",
     "Código General Disciplinario, art. 52: the word 'grave' (num. 1 lit. b) was struck by Sentencia C-560 de 2019 (20 "
     "November 2019), which applied Sentencia C-181 de 2002 on the same words of Ley 200 de 1995; the 2002 ruling and "
     "C-1076 de 2002 (on Ley 734 de 2002) are about earlier acts and are not credited"),
    ("ley_1952_2019", "- El aparte tachado, que en similar sentido corresponde a parte del",
     "(Ley 200 de 1995:) El aparte tachado, que en similar sentido corresponde a parte del", None),
]
DEFERRED_ART = re.compile(r"(?:\s*<[^<>]*>)*?\s*<Art[íi]culo INEXEQUIBLE\. Efectos diferidos")
SYNTH: list[str] = []
_units_b3 = B3.doc_units


def doc_units(name: str) -> list[dict]:
    units = _units_b3(name)
    fixes = [(old, new) for page, old, new, _ in HEADING_FIXES if page == name]
    hits = {old: 0 for old, _ in fixes}
    defer = [(old, new) for page, old, new, *_ in DEFERRED if page == name]
    dhits = {old: 0 for old, _ in defer}
    nhits = {o: 0 for page, o, _, _ in NOTE_FIXES + JV_FIXES if page == name}
    for u in units:
        items = []
        for it in u["items"]:
            if it[0] == "box" and it[1] == "Legislación Anterior":
                h = it[2]
                for old, new in fixes:
                    hits[old] += h.count(old)
                    h = h.replace(old, new)
                it = (it[0], it[1], h) + tuple(it[3:])
            if it[0] == "box" and it[1] == "Notas de Vigencia":
                h = it[2]
                for page, o, n, _ in NOTE_FIXES:
                    if page == name:
                        nhits[o] = nhits.get(o, 0) + h.count(o)
                        h = h.replace(o, n)
                it = (it[0], it[1], h) + tuple(it[3:])
            if it[0] == "box" and it[1] == "Jurisprudencia Vigencia":
                h = it[2]
                for page, o, n, _ in JV_FIXES:
                    if page == name:
                        nhits[o] = nhits.get(o, 0) + h.count(o)
                        h = h.replace(o, n)
                it = (it[0], it[1], h) + tuple(it[3:])
            if it[0] == "box" and it[1] == "Jurisprudencia Vigencia" and "se difieren" in it[2]:
                # only notes that state the deferral (the same ruling struck other articles at once, e.g. art. 162)
                h = it[2]
                for old, new in defer:
                    dhits[old] += h.count(old)
                    h = h.replace(old, new)
                it = (it[0], it[1], h) + tuple(it[3:])
            items.append(it)
        items = [("p", replaced_words(it[1])) + tuple(it[2:]) if it[0] == "p" else it for it in items]
        u["items"] = items
        ps = [it for it in items if it[0] == "p"]
        if defer and ps and DEFERRED_ART.match(E.plain(ps[0][1])):
            # A whole article struck with a deferred effect: the page prints the text that stood until the deferral
            # ended. Given to the engine as that text ("Texto vigente hasta su declaratoria de
            # INEXEQUIBILIDAD"), so the article stands from the act's first day and leaves on the ruling's (deferred) day.
            body = [E.html.escape(u["label"], quote=False) + " " + E.strip_markers(ps[0][1])] + [
                E.strip_markers(it[1]) for it in ps[1:]]
            box = ("<p><span class='b_aj'>Texto vigente hasta su declaratoria de INEXEQUIBILIDAD</span>:</p>"
                   + "".join(f"<p>{b}</p>" for b in body))
            u["items"] = items + [("box", "Legislación Anterior", box)]
            SYNTH.append(f"{name} {u['name']}")
    missing = [o for o, n in hits.items() if n == 0] + [o for o, n in dhits.items() if n == 0] + [o for o, n in nhits.items() if n == 0]
    if missing:
        raise SystemExit(f"{name}: page fixes that did not match: {missing}")
    return units


def fix_deferred() -> None:
    for page, _, _, key, decided, effect, why in DEFERRED:
        if key in E.LAWS:
            E.LAWS[key]["enacted"] = decided
            E.LAWS[key]["note"] = why


P.doc_units = doc_units
E.doc_units = doc_units
DECISIONS.extend("Código Nacional de Seguridad y Convivencia Ciudadana: " + why for page, _, _, why in HEADING_FIXES
                 if page == "ley_1801_2016")
DECISIONS.extend("Ley 100 de 1993: " + why for page, _, _, why in HEADING_FIXES + NOTE_FIXES if page == "ley_0100_1993")
DECISIONS.extend("Código Nacional de Seguridad y Convivencia Ciudadana: " + d[-1] + " The commit is dated from the end of the "
                 "deferral; the law's enacted day is the decision's." for d in DEFERRED if d[0] == "ley_1801_2016")


E.HAND_RULES["dec-207-2022"] = ("pub", "Decreto 207 de 2022 (corrects errors in Ley 2197 de 2022), art. 29: 'El presente "
                                       "decreto se entiende incorporado a la Ley 2197 de 2022 y rige a partir de la fecha "
                                       "de publicación.' (Diario Oficial No. 51.942 of 8 February 2022; the basedoc does "
                                       "not hold it: read from the Secretaría Jurídica Distrital de Bogotá's Régimen Legal, "
                                       "https://www.alcaldiabogota.gov.co/sisjur/normas/Norma1.jsp?i=120878, in the cache)")


def start_1801(units, enacted, pub):
    a = B3.article_text(units, "243")
    if "La presente ley regirá seis (6) meses después de su promulgación" not in a or not pub:
        raise SystemExit(f"Ley 1801 art. 243: {a!r}")
    start = E.add_months(pub, 6)
    return (start, f"Ley 1801 de 2016, art. 243: '{a}' (published {pub})",
            f"The code as promulgated (Ley 1801 de 2016, sanctioned {enacted}, Diario Oficial No. 49.949 of {pub}), in "
            f"force from {start} under its art. 243: '{a}'")


def start_ley100(units, enacted, pub):
    a = B3.article_text(units, "289")
    b = B3.article_text(units, "151")
    if not a.startswith("La presente Ley rige a partir de la fecha de su publicación") or "1o. de Abril de 1.994" not in b \
            or not pub:
        raise SystemExit(f"Ley 100 arts. 289/151: {a[:200]!r}")
    a = a[:a.index("El presidente del Honorable Senado")].strip() if "El presidente del Honorable Senado" in a else a
    return (pub, f"Ley 100 de 1993, art. 289: '{a}'",
            f"The act as promulgated (Ley 100 de 1993, Diario Oficial No. 41.148 of {pub}), in force from publication under "
            f"its art. 289: '{a}' Its Sistema General de Pensiones applied from 1 April 1994 (art. 151: '{b}'). The history "
            f"dates the whole act from publication.")


CGD_265 = ("Las disposiciones previstas en la presente ley, y las contenidas en la Ley 1952 de 2019, que no son objeto de "
           "reforma, entrarán a regir nueve (9) meses después de su promulgación.")
# Ley 2094 de 2021 reformed the Código General Disciplinario before it took effect; its art. 73 (now art. 265 of the code,
# read from the code's page) fixes the days. The engine's patterns would read "nueve (9) meses" as "from promulgation".
E.HAND_RULES["ley-2094-2021"] = ("pub+9m", "Ley 2094 de 2021, art. 73 (art. 265 of the Código General Disciplinario as it "
                                           "reformed it): '" + CGD_265 + " ... PARÁGRAFO 1o. El artículo 1 de la presente "
                                           "Ley, relativo a las funciones jurisdiccionales entrará a regir a partir de su "
                                           "promulgación. PARÁGRAFO 2o. El artículo 7o de la presente ley entrará a regir "
                                           "treinta meses (30) después de su promulgación.'")
_unit_day = E.unit_day


def unit_day(key: str, text: str) -> None:
    """Ley 2094 de 2021, art. 73 (above): its art. 1 (art. 2 of the code) took effect on promulgation, its art. 7 (art. 33
    of the code) thirty months after it, the rest nine months after it."""
    _unit_day(key, text)
    m = re.search(r"art[íi]culo (\d+)o?\.? de la Ley 2094 de 2021", text)
    pub = E.LAWS.get(key, {}).get("published")
    if key == "ley-2094-2021" and m and pub:
        if m.group(1) == "1":
            E.UNIT_DAYS[key] = pub
        elif m.group(1) == "7":
            E.UNIT_DAYS[key] = E.add_months(pub, 30)


E.unit_day = unit_day


E.HAND_RULES["dec-1656-2021"] = ("2022-03-29", "Decreto 1656 de 2021 corrected errors in Ley 2094 de 2021 (Diario Oficial "
                                              "No. 51.880 of 6 December 2021); the basedoc does not hold it. Its "
                                              "corrections here (arts. 225D and 238A of the Código General Disciplinario) "
                                              "are to articles Ley 2094 de 2021 added, which took effect on 29 March 2022 "
                                              "(its art. 73), so they are shown from that day (no text before the act that "
                                              "inserted it)")
DECISIONS.append("Código General Disciplinario: " + E.HAND_RULES["dec-1656-2021"][1] + ".")
DECISIONS.extend("Código General Disciplinario: " + why for page, _, _, why in JV_FIXES if page == "ley_1952_2019" and why)


def start_cgd(units, enacted, pub):
    a = B3.article_text(units, "265")
    if not a.startswith(CGD_265) or "PARÁGRAFO 2o. El artículo 7o de la presente ley entrará a regir treinta meses" not in a \
            or not pub:
        raise SystemExit(f"CGD art. 265: {a[:300]!r}")
    return (pub, "Ley 1952 de 2019, art. 265 as enacted: 'La presente ley entrará a regir cuatro (4) meses después de su "
                 "sanción y publicación ...' (arts. 33, 101, 102, 208 to 235 and 254 eighteen months after promulgation); "
                 "postponed to 1 July 2021 by Ley 1955 de 2019, art. 140, and replaced by Ley 2094 de 2021, art. 73: '"
                 f"{a[:600]}'. The first version is dated from promulgation ({pub}).",
            f"The code as promulgated (Ley 1952 de 2019, sanctioned {enacted}, Diario Oficial No. 50.850 of {pub}). It was "
            "not yet in force: its art. 265 set four months after sanction and publication (eighteen months for the "
            "procedural articles), Ley 1955 de 2019, art. 140, postponed that to 1 July 2021, and Ley 2094 de 2021, which "
            "reformed the code, put it in force nine months after its own promulgation (29 June 2021), on 29 March 2022. "
            "The history dates the code from its promulgation so that each reform shows as its own change.")


def build_cgd() -> dict:
    act = B3.build("ley_1952_2019", "ley-1952-2019", "codigo-general-disciplinario", "CGD",
                   "Código General Disciplinario (Ley 1952 de 2019)",
                   "Por medio de la cual se expide el Código General Disciplinario, se derogan la Ley 734 de 2002 y algunas "
                   "disposiciones de la Ley 1474 de 2011, relacionadas con el derecho disciplinario", start_cgd)
    # Ley 1955 de 2019, art. 140, postponed the code's start and changed no words. The code's note on art. 265 ("El plazo
    # de entrada en vigencia de esta ley se prorrogó hasta el 1 de julio de 2021 por el artículo 140 de la Ley 1955 de 2019
    # ... publicada en el Diario Oficial No. 50.964 de 25 de mayo 2019") is shown as a change of no words on that day.
    key = E.register("ley-1955-2019")
    day = E.LAWS[key]["published"]
    if day != "2019-05-25":
        raise SystemExit(f"Ley 1955 de 2019: published {day}")
    vs = act["versions"]
    # Art. 225D was inserted by Ley 2094 de 2021, art. 43 ("Artículo adicionado por el artículo 43 de la Ley 2094 de
    # 2021, corregido por el artículo 1 del Decreto 1656 de 2021"): with two acts on one day the engine leaves it as a
    # placeholder before that day; an inserted article is absent before the act that inserted it (coordinator rule).
    l2094 = E.law_day("ley-2094-2021")
    for v in vs:
        u = v.get("units", {}).get("art-0225d")
        if v["from"] < l2094 and u is not None:
            if u["text"] != f"# Art. 225D\n{E.MISSING_LINE}\n":
                raise SystemExit("CGD art. 225D before Ley 2094 de 2021 is not a placeholder")
            del v["units"]["art-0225d"]
            v["credits"].pop("art-0225d", None)
    DECISIONS.append("Código General Disciplinario: art. 225D, inserted by Ley 2094 de 2021 (art. 43, corrected by "
                     "Decreto 1656 de 2021), is absent before " + l2094 + ".")
    if any(v["from"] == day for v in vs):
        raise SystemExit("CGD: a version already on " + day)
    vs.append({"from": day, "credits": {"art-0265": [key]}, "source_url": vs[0]["source_url"], "sha256": vs[0]["sha256"],
               "note": "Ley 1955 de 2019 (Plan Nacional de Desarrollo 2018-2022), art. 140, postponed the entry into force "
                       "of the Código General Disciplinario to 1 July 2021; it changed no words of the code."})
    vs.sort(key=lambda v: v["from"])
    DECISIONS.append("Código General Disciplinario: Ley 1955 de 2019, art. 140 (postponing the code's start to 1 July "
                     "2021), is shown on its publication day (25 May 2019) as a change of no words to art. 265, from the "
                     "code's own note on that article.")
    return act


def start_ce(units, enacted, pub):
    a = B3.article_text(units, "218")
    if not a.startswith("El presente Decreto rige desde la fecha de su publicación") or not pub:
        raise SystemExit(f"Código Electoral art. 218: {a[:200]!r}")
    a = a[:a.index("Dado en")].strip() if "Dado en" in a else a
    return (pub, f"Decreto 2241 de 1986, art. 218: '{a}'",
            f"The code as issued (Decreto 2241 de 1986, of {enacted}, Diario Oficial No. 37.571 of {pub}), in force from "
            f"publication under its art. 218: '{a}'")


def build_1801() -> dict:
    act = B3.build("ley_1801_2016", "ley-1801-2016", "codigo-nacional-de-seguridad-y-convivencia-ciudadana", "CNSCC",
                   "Código Nacional de Seguridad y Convivencia Ciudadana (Ley 1801 de 2016)",
                   "Por la cual se expide el Código Nacional de Seguridad y Convivencia Ciudadana", start_1801)
    # The same ruling struck Título VI itself ("Título declarado INEXEQUIBLE ... C-223-17"): the headings that leave with
    # its articles on 20 June 2019 are credited to it (the engine credits headings only to acts).
    for v in act["versions"]:
        for page, _, _, key, _, effect, _ in DEFERRED:
            if page == "ley_1801_2016" and v["from"] == effect and "titulos" not in v["credits"] and "units" in v:
                v["credits"]["titulos"] = [key]
    return act


BUILDERS = {
    "codigo-nacional-de-seguridad-y-convivencia-ciudadana": build_1801,
    "sistema-de-seguridad-social-integral": lambda: B3.build(
        "ley_0100_1993", "ley-100-1993", "sistema-de-seguridad-social-integral", "L100",
        "Ley 100 de 1993 (Sistema de Seguridad Social Integral)",
        "Por la cual se crea el sistema de seguridad social integral y se dictan otras disposiciones", start_ley100),
    "codigo-general-disciplinario": build_cgd,
    "codigo-electoral": lambda: B3.build(
        "decreto_2241_1986", "dec-2241-1986", "codigo-electoral", "CE", "Código Electoral (Decreto 2241 de 1986)",
        "Por el cual se adopta el Código Electoral", start_ce),
}
P.PREFIX.update({"codigo-nacional-de-seguridad-y-convivencia-ciudadana": ("ley_1801_2016", "CNSCC"),
                 "sistema-de-seguridad-social-integral": ("ley_0100_1993", "L100"),
                 "codigo-general-disciplinario": ("ley_1952_2019", "CGD"),
                 "codigo-electoral": ("decreto_2241_1986", "CE")})
NAMES = ("Código Nacional de Seguridad y Convivencia Ciudadana", "Ley 100 de 1993", "Código General Disciplinario",
         "Código Electoral")


def finish_part(path: str) -> None:
    """write_part is the Phase 2 one; name this batch's own scripts in ai_use and rewrite atomically."""
    with open(path, encoding="utf-8") as f:
        part = json.load(f)
    part["ai_use"] = ["None at data-build time: batch4/fetch_batch4.py and batch4/parse_batch4.py (with batch3/ and "
                      "phase2/, which they import) are deterministic code, written with Claude Code (claude-opus-5-5); no "
                      "model reads, writes or summarises legal text."]
    part["sources"][0]["notes"] += (" Terms checked 2026-10-28: robots.txt disallows only the Joomla system folders, not "
                                    "/senado/basedoc/; each page's footer reserves Avance Jurídico's notes, concordances "
                                    "and arrangement (no use in similar publications for commercial ends), so only the "
                                    "official text and the facts the notes state are used; requests at most one per 2 s.")
    part["sources"] += [
        {"name": "Colpensiones, Normativa (Avance Jurídico compilation): Ley 62 de 1988, which the basedoc lacks",
         "url": E.COLPENSIONES + "ley_0062_1988.htm", "retrieved": E.RETRIEVED, "requests": 0,
         "licence": "Official legal text (Ley 23 de 1982, art. 41); only the heading and the vigencia clause are read.",
         "notes": "Requests are counted in the country's shared log."},
        {"name": "Secretaría Jurídica Distrital de Bogotá, Régimen Legal (Sisjur): Decreto 207 de 2022",
         "url": "https://www.alcaldiabogota.gov.co/sisjur/normas/Norma1.jsp?i=120878", "retrieved": E.RETRIEVED,
         "requests": 0,
         "licence": "Official legal text (Ley 23 de 1982, art. 41); only the decree's vigencia article (art. 29) is read.",
         "notes": "The basedoc does not hold Decreto 207 de 2022 (404). Requests are counted in the country's shared log."},
    ]
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(part, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    os.replace(tmp, path)


def main(argv: list[str]) -> None:
    only = argv[argv.index("--only") + 1].split(",") if "--only" in argv else list(BUILDERS)
    acts = [BUILDERS[s]() for s in BUILDERS if s in only]
    fix_deferred()
    arts = sorted({x.split(" ")[1] for x in SYNTH if x.startswith("ley_1801_2016 ")}, key=lambda a: (len(a), a))
    if arts:
        DECISIONS.append("Código Nacional de Seguridad y Convivencia Ciudadana: arts. " + ", ".join(arts) + ": the page still prints them under '<Artículo INEXEQUIBLE. Efectos diferidos ...>'. That "
                         "printed text is their text from the code's first day until the deferral ended (Sentencia C-223 "
                         "de 2017); from 20 June 2019 they are absent.")
    problems = B3.anachronisms(acts)
    for p in problems:
        E.note("anachronism " + p)
    for p in PRE_START:
        E.note("pre-start " + p)
    d = argv[argv.index("--out-dir") + 1] if "--out-dir" in argv else OUT_DIR
    out = os.path.join(d, PART)
    P.write_part(acts, out, tuple(n for n in NAMES if any(a["title"].startswith(n) for a in acts)))
    finish_part(out)
    print(f"  {len(problems)} anachronisms, {len(PRE_START)} pre-start events")
    if "--report" in argv:
        for r in E.REPORT:
            print("  ", r)


if __name__ == "__main__":
    main(sys.argv[1:])
