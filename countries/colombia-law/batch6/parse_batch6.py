"""Build corpus.d/97-batch6.json for Colombia: Estatuto Orgánico del Sistema Financiero (Decreto 663 de 1993), Código de
Minas (Ley 685 de 2001), Código Procesal del Trabajo y de la Seguridad Social (Decreto-Ley 2158 de 1948), Régimen de
Insolvencia Empresarial (Ley 1116 de 2006) and Régimen de los Servicios Públicos Domiciliarios (Ley 142 de 1994).

Reads only ../.cache/ (batch6/fetch_batch6.py, ../fetch.py); no network; deterministic. Imports the batch 5 driver
(batch5/parse_batch5.py: its generic page repairs and key fixes), which imports the batch 4, batch 3 and Phase 2 drivers
and the engine (phase2/engine.py): the same per-provision reconstruction from the Senado basedoc, rulings as `court`
laws, and in-force days from each act's own vigencia clause.

Usage:  python -X utf8 batch6/parse_batch6.py [--report] [--out-dir DIR] [--only slug,...] [--show page:art,...]
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COUNTRY = os.path.dirname(HERE)
for _d in ("batch5", "batch4", "batch3", "phase2"):
    sys.path.insert(0, os.path.join(COUNTRY, _d))
import parse_batch5 as B5  # noqa: E402

B4 = B5.B4
B3 = B5.B3
P = B5.P
E = B5.E
OUT_DIR = os.path.join(COUNTRY, "corpus.d")
PART = "97-batch6.json"
DECISIONS = P.DECISIONS
E.RETRIEVED = "2026-10-29"  # this batch's fetch day (the part's `retrieved`)
PRE_START = B4.PRE_START
PRE_START.clear()

# Typing slips in these acts' notes and earlier-text headings, each fixed by what the same article shows. wrong -> right.
KEY_FIXES = {
    "dec-673-1999": "dec-673-1994",   # EOSF art. 83: marker '<Numeral derogado por el artículo 17 del Decreto 673 de 1994>'
    "dec-674-1999": "dec-673-1994",   # EOSF art. 83 num. 3: same marker; Decreto 673 de 1994, art. 17, names both numerals
    "dec-2489-1989": "dec-2489-1999",  # EOSF art. 327: 'Texto modificado por el Decreto 2489 de 1989' (notes: art. 4 Decreto 2489 de 1999, DO 43.819)
    "ley-685-2021": "ley-685-2001",   # Código de Minas art. 295: 'Texto original de la Ley 685 de 2021' (the code's own original)
}
E.KEY_FIXES.update(KEY_FIXES)
DECISIONS.append("Estatuto Orgánico del Sistema Financiero and Código de Minas: typing slips in act numbers or years of the "
                 "source's notes and earlier-text headings are read as the act the same article names: "
                 + "; ".join(f"{E.law_label(a)} as {E.law_label(b)}" for a, b in KEY_FIXES.items()) + ".")
# Acts the basedoc and Colpensiones do not hold, dated from what the EOSF's own notes or the act's text say.
E.HAND_RULES["dec-673-1994"] = ("1994-05-01", "Decreto 673 de 1994 (Diario Oficial No. 41.287 of 29 March 1994), art. 17: "
                                              "'El presente Decreto rige a partir del 1o de mayo de 1994, y deja sin efecto "
                                              "... los numerales 1o y 3o del artículo 83 del Estatuto Orgánico del Sistema "
                                              "Financiero ...' (the basedoc does not hold it: read from the Secretaría "
                                              "Jurídica Distrital de Bogotá's Régimen Legal, "
                                              "https://www.alcaldiabogota.gov.co/sisjur/normas/Norma1.jsp?i=7036, in the "
                                              "cache)")
E.HAND_RULES["dec-2423-1993"] = ("1994-01-01", "the Estatuto Orgánico del Sistema Financiero's note on art. 12: 'el ordinal "
                                               "a) del artículo 6o. del Decreto 2423 de 1993; el cual entra en vigencia a "
                                               "partir del 1o. de enero de 1994' (the basedoc does not hold the decree)")
# Decreto 1154 de 1999 (struck whole by Sentencia C-969 de 1999): no source holds it; the EOSF's notes give its Diario
# Oficial ('No 43.623, de 29 de Junio de 1999', a capital the engine's date pattern does not read). Default rule.
E.PUB["dec-1154-1999"] = "1999-06-29"
DECISIONS.append("Estatuto Orgánico del Sistema Financiero: " + E.HAND_RULES["dec-673-1994"][1] + ".")
DECISIONS.append("Estatuto Orgánico del Sistema Financiero: Decreto 2423 de 1993 is dated 1 January 1994 from "
                 + E.HAND_RULES["dec-2423-1993"][1] + ".")
DECISIONS.append("Estatuto Orgánico del Sistema Financiero: Decreto 1154 de 1999 (struck whole by Sentencia C-969 de 1999) "
                 "is held by no cached source; its Diario Oficial day (29 June 1999) is the EOSF notes', and it is dated by "
                 "the default rule (two months after promulgation).")

_page_header = E.page_header


DO_MONTH_FIRST = re.compile(r"Diario Oficial No\.? ?[\d.]+,? de ([a-z]+) (\d{1,2}) de (\d{4})$")
MONTH_FIRST_DO: set[str] = set()


def page_header(page: str, year: str):
    """The Estatuto Orgánico del Sistema Financiero's heading writes its day month first: '(Abril 2 de 1993)'. Some
    amending acts' headings write the Diario Oficial day month first ('Diario Oficial No. 44.537, de agosto 31 de
    2001', Ley 689 de 2001), which the engine does not read: that day is read here when the engine finds none."""
    if page != "estatuto_organico_sistema_financiero":
        enacted, pub = _page_header(page, year)
        if pub is None and not page.startswith("http"):
            ps = E.page_paras(page)
            for p in ps[:12]:
                m = DO_MONTH_FIRST.match(p)
                if m and m.group(1) in E.MONTHS and m.group(3) == year:
                    pub = f"{m.group(3)}-{E.MONTHS[m.group(1)]:02d}-{int(m.group(2)):02d}"
                    MONTH_FIRST_DO.add(f"{page}: '{p}'")
                    break
        return enacted, pub
    ps = E.page_paras(page)
    i = ps.index("DECRETO 663 DE 1993")
    m = re.fullmatch(r"\(([A-Za-z]+) (\d{1,2}) de (\d{4})\)", ps[i + 1])
    d = E.DO_RE.search(ps[i + 2])
    if not m or not d or ps[i + 2] != "Diario Oficial No. 40.820, del 5 de abril de 1993":
        raise SystemExit(f"EOSF heading: {ps[i:i + 3]}")
    return f"{m.group(3)}-{E.MONTHS[m.group(1).lower()]:02d}-{int(m.group(2)):02d}", E.date_es(d.group(1))


E.page_header = page_header

# Sentencia C-366 de 2011 (13 May 2011) declared Ley 1382 de 2010 (which reformed the Código de Minas) INEXEQUIBLE with its
# effect deferred for two years (the code's notes: 'Ley 1382 de 2010 declarada INEXEQUIBLE ... Sentencia C-366-11 de 13
# de mayo 2011 ... Efectos diferidos por el término de dos (2) años'): the reformed words stay until 13 May 2013, when
# the earlier text returns. The law keeps the decision day as `enacted`; its commit is dated from the end of the deferral.
C366_NOTE = ("Sentencia C-366 de 2011 (13 May 2011) declared Ley 1382 de 2010, which reformed the Código de Minas, "
             "INEXEQUIBLE, deferring the effect for two years; the reformed text leaves the code on 13 May 2013 and the "
             "earlier text returns.")
E.IN_FORCE["c-366-11"] = "2013-05-13"
E.IN_FORCE_WHY["c-366-11"] = ("the ruling's effect was deferred for two years from its day, 13 May 2011 (the Código de "
                              "Minas's notes: 'Efectos diferidos por el término de dos (2) años')")
DECISIONS.append("Código de Minas: " + C366_NOTE + " The commit is dated from the end of the deferral, two years after "
                 "the decision day the source gives; the law's enacted day is the decision's.")


def cut_signers(a: str) -> str:
    for s in ("El Presidente del", "La Presidenta del", "El presidente del", "Dado en", "Publíquese"):
        if s in a:
            a = a[:a.index(s)]
    return a.strip()


def start_eosf(units, enacted, pub):
    a = cut_signers(B3.article_text(units, "339"))
    if not a.startswith("El presente Decreto rige a partir del 2o. de mayo de 1993") or enacted != "1993-04-02" or not pub:
        raise SystemExit(f"EOSF art. 339: {a[:300]!r} {enacted} {pub}")
    return ("1993-05-02", f"Decreto 663 de 1993, art. 339: '{a[:700]}' (issued {enacted}, published {pub})",
            f"The Estatuto as issued (Decreto 663 de 1993, of {enacted}, Diario Oficial No. 40.820 of {pub}), in force from "
            f"2 May 1993 under its art. 339: '{a[:400]} ...'")


def start_minas(units, enacted, pub):
    a = cut_signers(B3.article_text(units, "362"))
    if a != "El presente Código rige desde su promulgación." or not pub:
        raise SystemExit(f"Código de Minas art. 362: {a[:300]!r}")
    return (pub, f"Ley 685 de 2001, art. 362: '{a}' (sanctioned {enacted}, Diario Oficial No. 44.545 of {pub})",
            f"The code as promulgated (Ley 685 de 2001, sanctioned {enacted}, Diario Oficial No. 44.545 of {pub}), in force "
            f"from promulgation under its art. 362: '{a}'")


def start_cpt(units, enacted, pub):
    a = cut_signers(B3.article_text(units, "156"))
    if a != "Este decreto regirá cinco días después de su expedición." or enacted != "1948-06-24":
        raise SystemExit(f"CPT art. 156: {a[:300]!r} {enacted}")
    start = E.add_days(enacted, 5)
    return (start, f"Decreto-Ley 2158 de 1948, art. 156: '{a}' (issued {enacted}; the source gives no Diario Oficial)",
            f"The code as issued (Decreto-Ley 2158 de 1948, of {enacted}, 'Sobre los procedimientos en los juicios del "
            f"trabajo'), in force from {start} under its art. 156: '{a}' The source gives no Diario Oficial for it.")


def start_1116(units, enacted, pub):
    a = cut_signers(B3.article_text(units, "126"))
    if not a.startswith("Salvo lo que se indica en los incisos anteriores, la presente ley comenzará a regir seis (6) "
                        "meses después de su promulgación") or not pub:
        raise SystemExit(f"Ley 1116 art. 126: {a[:300]!r}")
    later = E.add_months(pub, 6)
    return (pub, f"Ley 1116 de 2006, art. 126: '{a}' The first version is dated from promulgation ({pub}), when the "
                 f"parts of arts. 125 and 126 that say so took effect; the rest six months later ({later}).",
            f"The act as promulgated (Ley 1116 de 2006, Diario Oficial No. 46.494 of {pub}). Under its art. 126 it took "
            f"effect six months after promulgation ({later}), save the parts of arts. 125 and 126 that apply from "
            f"promulgation (the extension of Ley 550 de 1999 and the restructuring agreements of territorial entities). "
            f"The history dates the whole act from promulgation. Art. 126: '{a}'")


def start_142(units, enacted, pub):
    a = cut_signers(B3.article_text(units, "189"))
    if a != "Salvo cuando ella disponga otra cosa, esta Ley rige a partir de la fecha de su publicación en el Diario " \
            "Oficial." or not pub:
        raise SystemExit(f"Ley 142 art. 189: {a[:300]!r}")
    return (pub, f"Ley 142 de 1994, art. 189: '{a}' (Diario Oficial No. 41.433 of {pub})",
            f"The act as published (Ley 142 de 1994, Diario Oficial No. 41.433 of {pub}), in force from publication under "
            f"its art. 189: '{a}'")


EOSF = "estatuto_organico_sistema_financiero"
CPT = "codigo_procedimental_laboral"
# EOSF arts. 168 to 175 (Parte V, Capítulo VI, voluntary pension funds) carry the marker '<Artículo derogado el a partir
# del 25 de mayo de 2021 por el artículo 336 de la Ley 1955 de 2019 ...>' (a slip, 'el a partir'); Ley 1955 de 2019,
# art. 336, par. 3 (its own page): 'Las disposiciones del Capítulo VI de la Parte V del Estatuto Orgánico del Sistema
# Financiero perderán vigencia en el término de 24 meses contados a partir de la vigencia de la presente ley.' They are
# given to the engine as articles repealed by that act, dated 25 May 2021.
DEROG_2021 = re.compile(r"derogado el a partir del 25 de mayo de 2021 por (el art(?:í|&iacute;|i)culo (?:<A [^>]*>)?336(?:</A>)? "
                        r"de la Ley 1955 de 2019)\.?(?:(?!&gt;).)*", re.S)
DEROG_2021_UNITS: set[str] = set()
SUPRIMIDO = re.compile(r"(?<=culo )Suprimido por disposici(?:ó|&oacute;|o)n del")
SUPRIMIDO_UNITS: set[str] = set()
# Articles without a number of their own: (page, exact heading on the page, heading given to the engine, engine number)
NEW_ARTS = [
    ("ley_0142_1994", "ARTÍCULO NUEVO. DEL SISTEMA ÚNICO DE INFORMACIÓN.", None, "53NUEVO1"),
    ("ley_0142_1994", "ARTÍCULO NUEVO. DEL FORMATO ÚNICO DE INFORMACIÓN.", None, "53NUEVO2"),
    ("ley_0685_2001", "ARTÍCULO <L1382>. RESPONSABILIDAD SOCIAL EMPRESARIAL.",
     "ARTÍCULO NUEVO. RESPONSABILIDAD SOCIAL EMPRESARIAL.", "342NUEVO"),
]
NEW_KEYS = {"53NUEVO1": ("art-0053-nuevo-1", "Art. nuevo 1 (después del art. 53)"),
            "53NUEVO2": ("art-0053-nuevo-2", "Art. nuevo 2 (después del art. 53)"),
            "342NUEVO": ("art-0342-nuevo", "Art. nuevo (después del art. 342)")}
NUMBER_IN_TEXT: list[str] = []
WHOLE_MARK_DOT = re.compile(r"^(\s*&lt;Art(?:í|&iacute;|i)culo (?:INEXEQUIBLE|derogado|suspendido)(?:(?!&gt;).)*&gt;)\s*\.\s*$",
                            re.S)
_units_b5 = P.doc_units


def doc_units(name: str) -> list[dict]:
    units = _units_b5(name)
    for u in units[1:]:
        # A heading anchor that holds only 'ARTÍCULO', the number starting the paragraph ('75. SOLICITUD DE
        # PRÓRROGAS. ...', Código de Minas arts. 75, 76 and 90): the number goes back into the heading.
        ps = [k for k, it in enumerate(u["items"]) if it[0] == "p"]
        if (u["label"] or "").strip() in ("ARTÍCULO", "ARTICULO") and ps:
            it = u["items"][ps[0]]
            m = re.match(r'\s*<B><A name="[^"]*"><span class="i_aj">(\d+)\.\s+(.*?)</span></A></B>\s*', it[1], re.S)
            if not m or m.group(1) != u["name"]:
                raise SystemExit(f"{name}: heading 'ARTÍCULO' without its number: {E.plain(it[1])[:80]}")
            u["label"] = E.tidy(f"ARTÍCULO {m.group(1)}. {E.plain(m.group(2))}")
            u["items"][ps[0]] = ("p", it[1][m.end():]) + tuple(it[2:])
            NUMBER_IN_TEXT.append(f"{name} {m.group(1)}")
        for page, head, new, _ in NEW_ARTS:
            if page == name and u["label"] == head and new:
                u["label"] = new
        # EOSF arts. 143 to 145: '<Artículo Suprimido por disposición del artículo 57 de la Ley 454 de 1998>' (the
        # chapter they belonged to was abolished): read as repealed by that act.
        if name == EOSF:
            for k, it in enumerate(u["items"]):
                if it[0] == "p" and SUPRIMIDO.search(it[1]):
                    u["items"][k] = ("p", SUPRIMIDO.sub("derogado por", it[1])) + tuple(it[2:])
                    SUPRIMIDO_UNITS.add(u["name"])
        # '<Artículo INEXEQUIBLE>.', '<Artículo derogado por ...>.': a paragraph that is only a whole-article marker
        # and a full stop; the full stop is the publisher's, not a word of the article.
        u["items"] = [(it[0], WHOLE_MARK_DOT.sub(r"\1", it[1])) + tuple(it[2:]) if it[0] == "p" else it
                      for it in u["items"]]
        if name == EOSF:
            # The page prints these articles' last text under the marker: the marker paragraph is taken out, so the
            # engine rebuilds their history up to that text, and build_eosf() removes them on 25 May 2021.
            ps = [it for it in u["items"] if it[0] == "p"]
            if ps and DEROG_2021.search(ps[0][1]):
                if E.plain(E.strip_markers(ps[0][1])).strip():
                    raise SystemExit(f"EOSF art. {u['name']}: words beside the 2021 marker")
                u["items"] = [it for it in u["items"] if it is not ps[0]]
                DEROG_2021_UNITS.add(u["name"])
            # Art. 12 lit. d: '{menor de un (1) año}' in braces marks the words whose effect Decreto 2423 de 1993, art. 6,
            # set aside for financial corporations (its marker: 'en cuanto al plazo menor'); the decree changed no words
            # of the Estatuto, so the braces go.
            if u["name"] == "12":
                u["items"] = [(it[0], re.sub(r"\{(menor de un \(1\) a(?:ñ|&ntilde;)o)\}", r"\1", it[1])) + tuple(it[2:])
                              if it[0] == "p" else it for it in u["items"]]
    if name == EOSF and sorted(DEROG_2021_UNITS, key=int) != [str(n) for n in range(168, 176)]:
        raise SystemExit(f"EOSF: 'derogado el a partir' markers on {sorted(DEROG_2021_UNITS)}")
    return units


P.doc_units = doc_units
E.doc_units = doc_units
def remove_on(act: dict, keys: list[str], day: str, law: str) -> None:
    """Remove `keys` from every version from `day` on, credited to `law` on that day (a version on that day is added,
    reading as the one before it, if there is none)."""
    vs = act["versions"]
    if not any(v["from"] == day for v in vs):
        prev = next(v for v in reversed(vs) if v["from"] < day and "units" in v)
        k = next(i for i, v in enumerate(vs) if v["from"] > day) if any(v["from"] > day for v in vs) else len(vs)
        vs.insert(k, {"from": day, "units": dict(prev["units"]), "credits": {}, "source_url": prev["source_url"],
                      "sha256": prev["sha256"]})
    for v in vs:
        if v["from"] < day:
            continue
        if v["from"] > day and any(x in v["credits"] for x in keys):
            raise SystemExit(f"{act['short']}: {keys} changed again on {v['from']}")
        if "units" not in v:
            raise SystemExit(f"{act['short']}: version {v['from']} without units after {day}")
        gone = [x for x in keys if x in v["units"]]
        if v["from"] == day:
            if len(gone) != len(keys):
                raise SystemExit(f"{act['short']}: {set(keys) - set(gone)} absent before {day}")
            for x in gone:
                v["credits"][x] = [law]
        for x in gone:
            del v["units"][x]


ART306: list[str] = []


def art306_timeline(units) -> list[tuple]:
    """EOSF art. 306: the page prints only '<Inciso 1o. declarado INEXEQUIBLE>' ... '<Parágrafo declarado INEXEQUIBLE>',
    each with its ruling and its original wording ('Texto original del artículo 306 del EOSF: ARTICULO 306. <INCISO
    1o.> En la propuesta ...'), which the engine does not read. The history is read from those boxes: the original
    wording from the start; inciso 3 struck by Sentencia C-037 de 1994 (3 February 1994); the rest by Sentencia C-452 de
    1995 (5 October 1995)."""
    u = next(x for x in units if x["name"] == "306")
    las = [E.plain(it[2]) for it in u["items"] if it[0] == "box" and it[1] == "Legislación Anterior"]
    jvs = [E.plain(it[2]) for it in u["items"] if it[0] == "box" and it[1] == "Jurisprudencia Vigencia"]
    paras = []
    for t in las:
        m = re.match(r"Texto original (?:del artículo 306|inciso 3o\. artículo 306) del EOSF: (?:ARTICULO 306\. )?"
                     r"(?:<INCISO \do\.> )?(.*)$", t)
        if not m:
            raise SystemExit(f"EOSF art. 306 earlier text: {t[:120]}")
        paras.append(m.group(1).strip())
    ok = (len(paras) == 5 and paras[4].startswith("PARAGRAFO.") and len(jvs) == 5
          and all("Sentencia C-452-95 del 5 de octubre de 1995" in j for k, j in enumerate(jvs) if k != 2)
          and "INEXEQUIBLE por la Corte Constitucional mediante Sentencia C-037-94 del 3 de febrero de 1994" in jvs[2])
    if not ok:
        raise SystemExit("EOSF art. 306: boxes changed")
    epi = "CONTENIDO DEL PROGRAMA."
    whole = [f"{epi} {paras[0]}"] + paras[1:]
    c037 = E.add_court("C-037-94", "1994-02-03", None)
    c452 = E.add_court("C-452-95", "1995-10-05", None)
    ART306.extend(paras)
    return [(None, "\n".join(whole), None),
            ("1994-02-03", "\n".join(whole[:2] + whole[3:]), c037),
            ("1995-10-05", None, c452)]


def set_history(act: dict, key: str, label: str, timeline: list[tuple]) -> None:
    """Give unit `key` the texts of `timeline` [(day or None for the first version, text or None, law)], adding a version
    (reading as the one before it) on a day that has none, and crediting each change to its law."""
    vs = act["versions"]
    for day, _, _ in timeline[1:]:
        if not any(v["from"] == day for v in vs):
            prev = next(v for v in reversed(vs) if v["from"] < day and "units" in v)
            k = next((i for i, v in enumerate(vs) if v["from"] > day), len(vs))
            vs.insert(k, {"from": day, "units": dict(prev["units"]), "credits": {}, "source_url": prev["source_url"],
                          "sha256": prev["sha256"]})
    days = {d: (t, l) for d, t, l in timeline[1:]}
    state = timeline[0][1]
    for i, v in enumerate(vs):
        if v["from"] in days:
            state, law = days[v["from"]]
            v["credits"][key] = [law]
        else:
            v["credits"].pop(key, None)
        if "units" not in v:
            continue
        v["units"] = dict(v["units"])
        if state is None:
            v["units"].pop(key, None)
        else:
            v["units"][key] = {"label": label, "kind": "art", "text": f"# {label}\n{state}\n"}


def build_eosf() -> dict:
    act = B3.build(EOSF, "dec-663-1993", "estatuto-organico-del-sistema-financiero", "EOSF",
                   "Estatuto Orgánico del Sistema Financiero (Decreto 663 de 1993)",
                   "Por medio del cual se actualiza el Estatuto Orgánico del Sistema Financiero y se modifica su "
                   "titulación y numeración", start_eosf)
    l = E.register("ley-1955-2019")
    remove_on(act, [E.unit_key(n)[0] for n in sorted(DEROG_2021_UNITS, key=int)], "2021-05-25", l)
    set_history(act, "art-0306", "Art. 306", art306_timeline(P.doc_units(EOSF)))
    DECISIONS.append("Estatuto Orgánico del Sistema Financiero: " + art306_timeline.__doc__.replace("\n    ", " ") .split(
        ": ", 1)[1])
    return act


_label_num = E.label_num
_unit_key = E.unit_key


def label_num(label: str):
    for _, head, new, num in NEW_ARTS:
        if label in (head, new):
            return num
    return _label_num(label)


def unit_key(name: str):
    return NEW_KEYS.get(name) or _unit_key(name)


E.label_num = label_num
E.unit_key = unit_key
STRUCK_NO_RULING: list[str] = []
_note = E.note


def note(msg: str) -> None:
    if "struck text but no dated ruling" in msg or "marked INEXEQUIBLE but no dated ruling" in msg:
        STRUCK_NO_RULING.append(f"{E.CUR_UNIT[0]}: {msg.split(': ', 1)[1]}")
    _note(msg)


E.note = note
EPIGRAPH_ONLY: list[str] = []


def drop_epigraph_only(act: dict) -> None:
    """An article whose words were all struck or repealed but whose epigraph the page still prints ('ARTICULO 306.
    CONTENIDO DEL PROGRAMA.' with every inciso INEXEQUIBLE) is not in force: the epigraph alone is not kept."""
    for v in act["versions"]:
        for k, u in list((v.get("units") or {}).items()):
            body = [l for l in u["text"].split("\n")[1:] if l.strip()]
            if k.startswith("art-") and len(body) == 1 and not re.search(r"[a-zñáéíóú]", body[0]) and body[0].endswith("."):
                del v["units"][k]
                EPIGRAPH_ONLY.append(f"{act['short']} {k} ({v['from']})")


TITULOS_CREDITED: list[str] = []


def credit_titulos(act: dict) -> None:
    """titulos.md shows a heading while an article under it is in force, so a heading that comes or goes with an
    article changes with it: where titulos changes on a day whose other changes are all credited to one law, it is
    credited to that law (Ley 142 de 1994: 'CAPÍTULO I. PRINCIPIOS Y REGLAS' returns with the article Sentencia C-969 de
    1999 restored)."""
    prev = None
    for v in act["versions"]:
        if "units" not in v:
            continue
        cur = (v["units"].get("titulos") or {}).get("text")
        if prev is not None and cur != prev[0] and "titulos" not in v["credits"]:
            laws = {tuple(ls) for k, ls in v["credits"].items() if k != "titulos"}
            if len(laws) == 1:
                v["credits"]["titulos"] = list(next(iter(laws)))
                TITULOS_CREDITED.append(f"{act['short']} {v['from']} ({', '.join(v['credits']['titulos'])})")
        prev = (cur,)


def debrace_versions(vs: list[dict], d50: str, l50: str) -> list[dict]:
    """'{empleador}' (Código Procesal del Trabajo): Ley 50 de 1990, art. 107, replaced 'patrono' with 'empleador'; the
    source shows the replaced word in braces (its Resumen de Notas de Vigencia, note 36). Before that law's day the
    words read 'patrono(s)', from it 'empleador(es)', credited to Ley 50 de 1990 (as the CST part does)."""
    out: list[dict] = []
    raw = shown = None  # the last version's units as the source gives them, and as shown
    for v in vs:
        before = v["from"] < d50
        if out and out[-1]["from"] < d50 < v["from"]:
            nu = {k: dict(u, text=P.debrace(u["text"], False)) for k, u in raw.items()}
            cr = {k: [l50] for k in nu if nu[k]["text"] != shown[k]["text"]}
            if cr:
                out.append({"from": d50, "units": nu, "credits": cr, "source_url": v["source_url"], "sha256": v["sha256"]})
                shown = nu
        if "units" not in v:  # a version that changed no words (a ruling that upheld text)
            out.append(dict(v))
            continue
        nu = {k: dict(u, text=P.debrace(u["text"], before)) for k, u in v["units"].items()}
        cr = {k: list(ls) for k, ls in v["credits"].items()}
        if out and out[-1]["from"] < d50 == v["from"]:
            # a version on Ley 50's own day: a unit whose braced words change on it is credited to Ley 50 too
            for k, u in nu.items():
                if (P.debrace(v["units"][k]["text"], True) != u["text"] and (shown.get(k) or {}).get("text") != u["text"]
                        and l50 not in cr.get(k, [])):
                    cr.setdefault(k, []).append(l50)
        out.append(dict(v, units=nu, credits=cr))
        raw, shown = v["units"], nu
    return out


def build_cpt() -> dict:
    act = B3.build(CPT, "dec-2158-1948", "codigo-procesal-del-trabajo-1948", "CPTSS48",
                   "Código Procesal del Trabajo y de la Seguridad Social (Decreto-Ley 2158 de 1948)",
                   "Sobre los procedimientos en los juicios del trabajo", start_cpt)
    l50 = E.register("ley-50-1990")
    d50 = E.law_day(l50)
    if d50 != "1991-01-01":
        raise SystemExit(f"Ley 50 de 1990: {d50}")
    vs = debrace_versions(act["versions"], d50, l50)
    left = sorted({w for v in vs for u in v.get("units", {}).values() for w in re.findall(r"\{([^{}\n]{1,40})\}", u["text"])})
    if left:
        raise SystemExit(f"CPT: braces left: {left}")
    # Ley 2452 de 2025 (the new Código Procesal del Trabajo y de la Seguridad Social), art. 331: 'Deróguense todas las
    # disposiciones que le sean contrarias, especialmente el Decreto Ley 2158 de 1948 ...'; in force one year after its
    # publication (art. 330), 2 April 2026. The page marks the articles '<Código derogado a partir del 2 de abril de
    # 2026 por el artículo 331 de la Ley 2452 de 2025>'. The whole code leaves the record on that day.
    l = E.register("ley-2452-2025")
    d = E.law_day(l)
    if d != "2026-04-02" or vs[-1]["from"] >= d:
        raise SystemExit(f"Ley 2452 de 2025: {d}; last CPT version {vs[-1]['from']}")
    last = next(v["units"] for v in reversed(vs) if "units" in v)
    vs.append({"from": d, "units": {}, "credits": {k: [l] for k in sorted(last)}, "source_url": vs[-1]["source_url"],
               "sha256": vs[-1]["sha256"],
               "note": "Ley 2452 de 2025, art. 331, repealed the Decreto Ley 2158 de 1948 as a whole, from the day the new "
                       "Código Procesal del Trabajo y de la Seguridad Social took effect (art. 330: one year after its "
                       "publication of 2 April 2025)."})
    DECISIONS.append("Código Procesal del Trabajo y de la Seguridad Social (Decreto-Ley 2158 de 1948): " + debrace_versions.__doc__
                     .replace("\n    ", " ").split(": ", 1)[1])
    DECISIONS.append("Código Procesal del Trabajo y de la Seguridad Social (Decreto-Ley 2158 de 1948): Ley 2452 de 2025, "
                     "art. 331, repealed it as a whole ('Deróguense todas las disposiciones que le sean contrarias, "
                     "especialmente el Decreto Ley 2158 de 1948 sobre los procedimientos en los juicios del trabajo, "
                     "adoptado como legislación permanente mediante la Ley 141 de 1961 ...'), in force on 2 April 2026 "
                     "(art. 330); the source marks its articles '<Código derogado a partir del 2 de abril de 2026 por el "
                     "artículo 331 de la Ley 2452 de 2025>'. The record's last version, on that day, holds no provisions; "
                     "the version before it is checked against the text the page prints.")
    act["versions"] = vs
    return act


def start_2452(units, enacted, pub):
    a = cut_signers(B3.article_text(units, "330"))
    if not a.startswith("El presente código entrará en vigencia un (1) año después de su publicación.") or not pub:
        raise SystemExit(f"Ley 2452 art. 330: {a[:300]!r}")
    start = E.add_months(pub, 12)
    return (start, f"Ley 2452 de 2025, art. 330: '{a[:300]}' (published {pub})",
            f"The code as promulgated (Ley 2452 de 2025, sanctioned {enacted}, Diario Oficial of {pub}), in force from "
            f"{start} under its art. 330: '{a[:300]}'")


BUILDERS: dict = {
    "estatuto-organico-del-sistema-financiero": build_eosf,
    "codigo-de-minas": lambda: B3.build(
        "ley_0685_2001", "ley-685-2001", "codigo-de-minas", "CMin", "Código de Minas (Ley 685 de 2001)",
        "Por la cual se expide el Código de Minas y se dictan otras disposiciones", start_minas),
    "codigo-procesal-del-trabajo-1948": build_cpt,
    "codigo-procesal-del-trabajo": lambda: B3.build(
        "ley_2452_2025", "ley-2452-2025", "codigo-procesal-del-trabajo", "CPTSS",
        "Código Procesal del Trabajo y de la Seguridad Social (Ley 2452 de 2025)",
        "Por medio de la cual se expide el Código Procesal del Trabajo y de la Seguridad Social y se dictan otras "
        "disposiciones", start_2452),
    "regimen-de-insolvencia": lambda: B3.build(
        "ley_1116_2006", "ley-1116-2006", "regimen-de-insolvencia", "RIE",
        "Régimen de Insolvencia Empresarial (Ley 1116 de 2006)",
        "Por la cual se establece el Régimen de Insolvencia Empresarial en la República de Colombia y se dictan otras "
        "disposiciones", start_1116),
    "servicios-publicos-domiciliarios": lambda: B3.build(
        "ley_0142_1994", "ley-142-1994", "servicios-publicos-domiciliarios", "LSPD",
        "Régimen de los Servicios Públicos Domiciliarios (Ley 142 de 1994)",
        "Por la cual se establece el régimen de los servicios públicos domiciliarios y se dictan otras disposiciones",
        start_142),
}
P.PREFIX.update({"estatuto-organico-del-sistema-financiero": ("estatuto_organico_sistema_financiero", "EOSF"),
                 "codigo-de-minas": ("ley_0685_2001", "CMin"),
                 "codigo-procesal-del-trabajo-1948": ("codigo_procedimental_laboral", "CPTSS48"),
                 "codigo-procesal-del-trabajo": ("ley_2452_2025", "CPTSS"),
                 "regimen-de-insolvencia": ("ley_1116_2006", "RIE"),
                 "servicios-publicos-domiciliarios": ("ley_0142_1994", "LSPD")})
NAMES = ("Estatuto Orgánico del Sistema Financiero", "Código de Minas", "Código Procesal del Trabajo",
         "Régimen de Insolvencia Empresarial", "Régimen de los Servicios Públicos Domiciliarios")


def finish_part(path: str) -> None:
    with open(path, encoding="utf-8") as f:
        part = json.load(f)
    part["ai_use"] = ["None at data-build time: batch6/fetch_batch6.py and batch6/parse_batch6.py (with batch5/, batch4/, "
                      "batch3/ and phase2/, which they import) are deterministic code, written with Claude Code "
                      "(claude-opus-5-5); no model reads, writes or summarises legal text."]
    part["sources"][0]["notes"] += (" Terms checked 2026-10-28: robots.txt disallows only the Joomla system folders, not "
                                    "/senado/basedoc/; each page's footer reserves Avance Jurídico's notes, concordances "
                                    "and arrangement, so only the official text and the facts the notes state are used. "
                                    "Pages retrieved on 2026-10-29 (some amending acts' pages earlier, for the other "
                                    "parts, from the same cache).")
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
        drop_epigraph_only(a)
        credit_titulos(a)
    if TITULOS_CREDITED:
        DECISIONS.append("Estatuto Orgánico del Sistema Financiero, Código de Minas, Código Procesal del Trabajo, Régimen de "
                         "Insolvencia Empresarial and Régimen de los Servicios Públicos Domiciliarios: a change of titulos.md "
                         "(the headings shown while an article under them is in force) on a day whose other changes are all "
                         "credited to one law is credited to that law: " + "; ".join(TITULOS_CREDITED) + ".")
    if "c-366-11" in E.LAWS:
        E.LAWS["c-366-11"]["note"] = C366_NOTE
    if EPIGRAPH_ONLY:
        DECISIONS.append("Estatuto Orgánico del Sistema Financiero, Código de Minas, Código Procesal del Trabajo, Régimen de "
                         "Insolvencia Empresarial and Régimen de los Servicios Públicos Domiciliarios: an article whose "
                         "words were all struck or repealed but whose epigraph the page still prints is absent, not kept "
                         "as its epigraph alone: " + ", ".join(sorted(set(x.split(" (")[0] for x in EPIGRAPH_ONLY))) + ".")
    if NUMBER_IN_TEXT:
        DECISIONS.append("Código de Minas: arts. " + ", ".join(sorted({x.split(" ")[1] for x in NUMBER_IN_TEXT}, key=int))
                         + ": the page's heading anchor holds only 'ARTÍCULO' and the number starts the paragraph; the "
                         "number is read as the article's.")
    DECISIONS.append("Régimen de los Servicios Públicos Domiciliarios (Ley 142 de 1994): the two articles headed 'ARTÍCULO "
                     "NUEVO.' that Ley 689 de 2001, arts. 14 and 15, added after art. 53 (Sistema Único de Información; "
                     "Formato Único de Información) are the files art-0053-nuevo-1 and art-0053-nuevo-2.")
    DECISIONS.append("Código de Minas: the article without a number that Ley 1382 de 2010 added after art. 342 "
                     "('Responsabilidad social empresarial'; the page heads it 'ARTÍCULO <L1382>.') is the file "
                     "art-0342-nuevo.")
    DECISIONS.append("Estatuto Orgánico del Sistema Financiero: arts. 168 to 175 (Parte V, Capítulo VI) leave the text on "
                     "25 May 2021, credited to Ley 1955 de 2019, whose art. 336, par. 3, reads: 'Las disposiciones del "
                     "Capítulo VI de la Parte V del Estatuto Orgánico del Sistema Financiero perderán vigencia en el "
                     "término de 24 meses contados a partir de la vigencia de la presente ley' (the page's marker: "
                     "'Artículo derogado el a partir del 25 de mayo de 2021 por el artículo 336 de la Ley 1955 de 2019'). "
                     "The page prints their last text under that marker; it is their text until that day.")
    if SUPRIMIDO_UNITS:
        DECISIONS.append("Estatuto Orgánico del Sistema Financiero: arts. " + ", ".join(sorted(SUPRIMIDO_UNITS, key=int))
                         + " ('<Artículo Suprimido por disposición del artículo 57 de la Ley 454 de 1998>': the chapter "
                         "they belonged to was abolished) are read as repealed by that act.")
    DECISIONS.append("Estatuto Orgánico del Sistema Financiero: art. 12, lit. d, prints '{menor de un (1) año}' in braces, "
                     "marking the words whose effect Decreto 2423 de 1993, art. 6, set aside for financial corporations "
                     "('en cuanto al plazo menor'); the decree changed no words, so the braces are dropped.")
    if MONTH_FIRST_DO:
        DECISIONS.append("Estatuto Orgánico del Sistema Financiero, Código de Minas, Código Procesal del Trabajo, Régimen "
                         "de Insolvencia Empresarial and Régimen de los Servicios Públicos Domiciliarios: amending acts "
                         "whose page writes the Diario Oficial day month first are read from that line: "
                         + "; ".join(sorted(MONTH_FIRST_DO)) + ".")
    if STRUCK_NO_RULING:
        DECISIONS.append("Estatuto Orgánico del Sistema Financiero, Código de Minas, Código Procesal del Trabajo, Régimen "
                         "de Insolvencia Empresarial and Régimen de los Servicios Públicos Domiciliarios: words the page "
                         "shows struck, with no ruling or act the source dates, are left out of every version (the "
                         "engine's rule): " + "; ".join(sorted(set(STRUCK_NO_RULING))) + ".")
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
