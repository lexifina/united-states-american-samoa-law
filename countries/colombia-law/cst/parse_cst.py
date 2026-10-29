"""Build corpus.d/70-cst.json for Colombia: the Código Sustantivo del Trabajo (CST).

Reads only ../.cache/ (written by ../fetch.py, ../phase2/fetch_phase2.py and cst/fetch_cst.py); no network.
Deterministic. The reconstruction engine is cst/engine.py (a copy of phase2/engine.py, itself the codes helper's
codes/parse_codes.py): per provision, versions are rebuilt from the basedoc's earlier texts ("Legislación
Anterior"), its inline amendment markers and its Notas de Vigencia; in-force days of amending acts come from their own
vigencia clauses (their basedoc pages) or the default rule. This driver began as build_cst() in phase2/parse_phase2.py.

Usage:  python -X utf8 cst/parse_cst.py [--report] [--out FILE]
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

OUT = os.path.join(COUNTRY, "corpus.d", "70-cst.json")
PAGE = "codigo_sustantivo_trabajo"
SIGN_OFF = re.compile(r"\s*(El Presidente del (honorable |H\. )?Senado|EL PRESIDENTE DEL (HONORABLE |H\. )?SENADO|"
                      r"REP[ÚU]BLICA DE COLOMBIA\s*-\s*GOBIERNO NACIONAL|PUBL[ÍI]QUESE Y (EJEC[ÚU]TESE|C[ÚU]MPLASE))")

# Typing slips in the CST's notes, fixed by what the same article says: art. 357's earlier texts are headed "Texto
# modificado por el Decreto 2351 de 1995" while its marker and Notas de Vigencia name art. 26 of Decreto 2351 de 1965.
E.KEY_FIXES.update({"dec-2351-1995": "dec-2351-1965"})
# Vigencia clauses read by hand from the cached Colpensiones copies (the simple patterns miss them).
E.HAND_RULES.update({
    "dec-59-1957": ("1957-07-01", "Decreto 59 de 1957, art. 8: 'Este Decreto rige a partir del primero (1o.) de julio del "
                                  "año en curso, y suspende todas las disposiciones legales que le sean contrarias.'"),
    "ley-3-1969": ("enacted", "Ley 3 de 1969, art. 7: 'Esta Ley regirá a partir de la fecha de su aprobación.' (sanctioned "
                              "13 October 1969, its heading '(octubre 13)')"),
})
# Spelling slips that hide an act from the engine's patterns: "Decreo 617 de 1954" (arts. 189, 230, 486), "Decreto -
# Ley 2737 de 1989" (art. 30).
TEXT_FIXES = [(re.compile(r"\bDecreo\b"), "Decreto"), (re.compile(r"Decreto\s*-\s*Ley\b"), "Decreto Ley"),
              # "<Apartes tachados suprimidos por el artículo 53 de la Ley 962 de 2005 ...>" (art. 73): words an act
              # removed, shown struck; the engine knows the form "tachados derogados por". Markers only, never text.
              (re.compile(r"(Apartes? tachados?) suprimidos? por"), r"\1 derogados por")]


def fix_text(h: str) -> str:
    for rx, rep in TEXT_FIXES:
        h = rx.sub(rep, h)
    return h


def fix_heading(u: dict) -> None:
    """Article headings the page breaks, made whole again (the words are the page's own):
    * the anchor holds only the first letters ('<a name="40">A</a>RTÍCULO 40. CARNÉ.', '<a name="266">ART</a>ICULO 266.');
    * the number stands in a marker after a numberless heading ('ARTICULO. DEDICACIÓN ...' then '<163A>', or
      '<391-1. Artículo adicionado ...>'), or in angle brackets ('ARTICULO <185-A>. LABORES AGROPECUARIAS.')."""
    ps = [k for k, it in enumerate(u["items"]) if it[0] == "p"]
    lab, nm = u["label"], u["name"]
    if ps and lab and len(lab) < 8 and ("ARTICULO".startswith(lab.upper()) or "ARTÍCULO".startswith(lab.upper())):
        k = ps[0]
        p = u["items"][k][1]
        m = re.search(r'<span class="b_aj"></span>|&lt;', p)
        head = E.plain(p[:m.start() if m else len(p)])
        if re.match(r"ART[IÍ]CULO\s+" + re.escape(nm) + r"o?\.", lab + head):
            u["label"] = (lab + head).strip()
            u["items"][k] = ("p", p[m.start() if m else len(p):]) + tuple(u["items"][k][2:])
            return
    m = re.match(r"ART[IÍ]CULO\s*<\s*(" + re.escape(nm) + r")\s*>\s*\.?\s*(.*)", lab)
    if m:
        u["label"] = f"ARTICULO {nm}. {m.group(2)}".strip()
        return
    m = re.match(r"(ART[IÍ]CULO)\.\s*(.*)", lab)
    if m and ps and re.fullmatch(r"\d+[A-Z]?(?:-\d+)?", nm):
        k = ps[0]
        p = u["items"][k][1]
        p2 = re.sub(r"^\s*&lt;" + re.escape(nm) + r"&gt;\s*", " ", p, count=1)
        p2 = re.sub(r"^\s*&lt;" + re.escape(nm) + r"\.\s*", " &lt;", p2, count=1)
        u["label"] = f"{m.group(1)} {nm}. {m.group(2)}".strip()
        u["items"][k] = ("p", p2) + tuple(u["items"][k][2:])


# Notes and earlier-text blocks that do not describe a change of the article's words, set aside before the engine reads
# them (each is listed in DECISIONS_FIXED with its reason). (anchor, box title, regex on the paragraph's plain text);
# for "Legislación Anterior" the regex matches a block heading, and the whole block (heading and texts) goes.
NOT_WORD_CHANGES = [
    # Ley 171 de 1961 changed the pension rules in its own articles (6, 7, 8, 12) and, by its art. 14, repealed only
    # arts. 261, 262 and 267 of the code ("Deróganse los artículos 261, 262, 267 del Código Sustantivo del Trabajo",
    # Colpensiones copy of Ley 171 de 1961). The notes "Artículo modificado por la Ley 171 de 1961 ... según lo
    # dispuesto en el artículo 14" on arts. 260, 266, 275 and 279 name no change of their words, and the "Texto original
    # de la Ley 171 de 1961" blocks on arts. 260 and 267 quote that act's own articles, not the code's.
    ("260", "Notas de Vigencia", r"modificado (?:por )?la Ley 171 de 1961"),
    ("266", "Notas de Vigencia", r"modificado (?:por )?la Ley 171 de 1961"),
    ("275", "Notas de Vigencia", r"modificado (?:por )?la Ley 171 de 1961"),
    ("279", "Notas de Vigencia", r"modificado (?:por )?la Ley 171 de 1961"),
    ("260", "Legislación Anterior", r"Texto original de la Ley 171 de 1961"),
    ("267", "Legislación Anterior", r"Texto original de la Ley 171 de 1961"),
]
DECISIONS_FIXED = [
    "Código Sustantivo del Trabajo: Ley 171 de 1961 changed the pension rules in its own articles and, by its art. 14, "
    "repealed only arts. 261, 262 and 267 of the code. The source's notes 'Artículo modificado por la Ley 171 de 1961 ... "
    "según lo dispuesto en el artículo 14' on arts. 260, 266, 275 and 279 name no change of their words, and its 'Texto "
    "original de la Ley 171 de 1961' boxes on arts. 260 and 267 quote that act's own articles 6, 7 and 8; they are not read "
    "as texts of the code. Ley 171 de 1961 is in force from 1 February 1962 (its art. 15: 'desde el día 1o. del mes "
    "siguiente al de su promulgación'; Diario Oficial No. 30.696 of 16 January 1962 in the source's notes).",
    "Código Sustantivo del Trabajo: arts. 260, 273, 275, 277, 278 and 280 to 284 were repealed or replaced ('subrogado') by "
    "Ley 100 de 1993; the source still prints their original words under markers such as '<Artículo derogado por el "
    "artículo 289 de la Ley 100 de 1993. El texto derogado continua vigente para los trabajadores sometidos al régimen de "
    "transición creado por el artículo 36 de la Ley 100. El texto original es el es el siguiente:>' or '<Artículo subrogado "
    "por La ley 100 de 1993. Ver Notas del Editor. El texto original es el siguiente:>'. Those words are read as the "
    "articles' original text, and the articles are removed on Ley 100's in-force day, like arts. 268 to 272 that the same "
    "act repealed. Court rulings on the repealed words (art. 260: Sentencia C-862-06, on the text kept for the transition "
    "regime of Ley 100, art. 36) are not recorded.",
    "Código Sustantivo del Trabajo: articles the source shows with no words today but whose original words it gives in "
    "a 'Texto original' box keep those words until the act the source names for their end: arts. 210 and 211 until "
    "Decreto 1295 de 1994 (its art. 98 repealed them tacitly, as the Corte Constitucional's Sentencia C-184-10, quoted "
    "in the source's Notas del Editor, says); art. 346 until Ley 75 de 1986 ('derogado tácitamente por el artículo 35'); "
    "arts. 454 to 461 (labour arbitration) until 12 October 2012, when Ley 1563 de 2012, art. 118, repealed arts. 183 to "
    "190 of Decreto 1818 de 1998, the compilation that had incorporated them; the source's marker gives that day. The "
    "source's own Notas del Editor add that the Corte Suprema de Justicia (AL2314-2014) holds the code's arbitration "
    "rules still in force; the history follows the source's current text, which has no words for them.",
    "Código Sustantivo del Trabajo: struck words or whole articles the source marks INEXEQUIBLE without naming a dated "
    "ruling (arts. 323 and 409, whole; the words of art. 247 that the Corte Constitucional, Sentencia C-823-06, found "
    "already repealed) are left out of every version. Art. 162, num. 1, lit. d) (repealed by Decreto 1393 de 1970, art. "
    "56) reads as repealed in every version: the source gives that decree's Diario Oficial number (33.131) but no day, "
    "and no other source in reach gives its in-force day.",
    "Código Sustantivo del Trabajo: the Corte Suprema de Justicia's ruling of 18 July 1973 that struck the second "
    "sentence of art. 44 is a court law keyed csj-1973-07-18 (the source names it by its day only).",
    "Código Sustantivo del Trabajo: art. 200 (enfermedad profesional) was repealed by Decreto 1295 de 1994, art. 98, and "
    "revived by the Corte Constitucional's Sentencia C-1155-08 of 26 November 2008 ('la presente declaración de "
    "inexequibilidad revive el artículo 200 del Código Sustantivo del Trabajo', quoted in its Notas de Vigencia): absent "
    "from 24 June 1994, back with its original words from the ruling's day.",
    "Código Sustantivo del Trabajo, source slips fixed: headings whose anchor holds only 'A' or 'ART' (arts. 40, 266) or "
    "whose number stands in a marker (163A, 167A, 185-A, 235-A, 391-1, 481-1) are made whole; 'Decreo' and 'Decreto - "
    "Ley' read as 'Decreto' and 'Decreto Ley'; art. 357's 'Texto modificado por el Decreto 2351 de 1995' is Decreto 2351 "
    "de 1965 (its marker); '<Apartes tachados suprimidos por el artículo 53 de la Ley 962 de 2005>' (art. 73) is read as "
    "words that act removed; the publisher's cross-reference stubs ('l0146_94+[...]', art. 236) are dropped.",
]
E.HAND_RULES.update({
    "ley-171-1961": ("1962-02-01", "Ley 171 de 1961, art. 15: 'Esta ley regirá desde el día 1o. del mes siguiente al de su "
                                   "promulgación ...' (Diario Oficial No. 30.696 of 16 January 1962, as the source's notes "
                                   "give it)"),
})


def drop_paras(box: str, rx: str, block: bool) -> tuple[str, int]:
    parts = re.split(r"(<p\b[^>]*>.*?</p>)", box, flags=re.S | re.I)
    out, dropping, n = [], False, 0
    for s in parts:
        m = re.match(r"<p\b[^>]*>(.*?)</p>", s, re.S | re.I)
        if m:
            t = E.plain(m.group(1))
            if block and re.match(r"\s*Texto\b", t):
                dropping = bool(re.search(rx, t))
            if dropping or (not block and re.search(rx, t)):
                n += 1
                continue
        out.append(s)
    return "".join(out), n


def set_aside(u: dict) -> None:
    for anchor, title, rx in NOT_WORD_CHANGES:
        if u["name"] != anchor:
            continue
        hit = 0
        for k, it in enumerate(u["items"]):
            if it[0] == "box" and it[1] == title:
                b, n = drop_paras(it[2], rx, title == "Legislación Anterior")
                u["items"][k] = (it[0], it[1], b) + tuple(it[3:])
                hit += n
        if not hit:
            raise SystemExit(f"CST: nothing set aside for {anchor} {title} {rx!r}: the source changed; check the rule")
    repealed_text_shown(u)


# "<Artículo derogado por el artículo 289 de la Ley 100 de 1993. El texto derogado continua vigente para ... El texto
# original es el es el siguiente:>" (art. 260), "<Artículo subrogado por La ley 100 de 1993. Ver Notas del Editor. El
# texto original es el siguiente:>" (arts. 273, 275, 277, 278, 280 to 284): the words that follow are the repealed text.
SHOWN_REPEALED = re.compile(r"\s*&lt;(Art&iacute;culo (?:derogado|subrogado) por (?:el art&iacute;culo (?:<[^>]*>)?\d+(?:</A>)? de )?"
                            r"[Ll]a [Ll]ey (?:<[^>]*>)?100(?:</A>)? de 1993)\.(?:(?!&gt;).)*?El texto original es el (?:es el )?siguiente:&gt;", re.I)
SHOWN_REPEALED_UNITS: list[str] = []


def repealed_text_shown(u: dict) -> None:
    """The repealed words become the article's original text (a 'Texto original' block, as the source gives every other
    earlier text), and the marker alone stays: the article has no words in force today. Court rulings on the repealed
    words (Jurisprudencia Vigencia) are set aside with them: they concern the text kept for the transition regime."""
    ps = [k for k, it in enumerate(u["items"]) if it[0] == "p" and "antsig" not in it[1]]
    m = SHOWN_REPEALED.match(u["items"][ps[0]][1]) if ps else None
    if not m:
        return
    SHOWN_REPEALED_UNITS.append(u["name"])
    first = u["items"][ps[0]][1][m.end():]
    paras = [p for p in [first] + [u["items"][k][1] for k in ps[1:]] if E.plain(p).strip()]
    has_orig = any(it[0] == "box" and it[1] == "Legislación Anterior" and
                   re.search(r"Texto original del C(?:&oacute;|ó)digo", it[2]) for it in u["items"])
    marker = "&lt;" + re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).replace("La ley", "la Ley") + ".&gt;"
    items = [it for k, it in enumerate(u["items"]) if (it[0] == "p" and k not in ps[1:])
             or (it[0] == "box" and it[1] != "Jurisprudencia Vigencia")]
    items = [("p", " " + marker) if it[0] == "p" and it[1] == u["items"][ps[0]][1] else it for it in items]
    if not has_orig:
        # As the source writes earlier texts: the heading, then the first paragraph on the same line.
        paras = [html_escape(u["label"]) + " " + (paras[0] if paras else "")] + paras[1:]
        body = "".join(f"<p>{p}</p>" for p in paras)
        items.append(("box", "Legislación Anterior",
                      "<tbody><tr><td><p><span class='b_aj'>Texto original del Código Sustantivo del Trabajo:</span></p>"
                      f"{body}</td></tr></tbody>"))
    u["items"] = items


_article_history = E.article_history
KEPT_ORIGINAL: list[str] = []  # articles with no text on the page today whose words no act or ruling removed


def keep_original(u: dict, h: dict) -> None:
    """An article the page shows with no words today, whose notes name no act and no ruling that removed it (only a
    tacit derogation, 'Derógado tácitamente', or its incorporation in the Decreto 1818 de 1998 compilation, whose art.
    183 Ley 1563 de 2012 later repealed): its original words, from the source's 'Texto original' box, stay in every
    version, as for the Código Civil's tacitly derogated articles. Articles marked '<Artículo INEXEQUIBLE>' or
    expressly derogated are not kept."""
    ps = [it[1] for it in u["items"] if it[0] == "p" and "antsig" not in it[1]]
    mks = E.markers(ps[0]) if ps else []
    if any(re.search(r"INEXEQUIBLE", m) or (re.match(r"(Art[íi]culo\s+)?derogad", m, re.I) and not E.TACIT.search(m))
           for m in mks):
        return
    for it in u["items"]:
        if it[0] == "box" and it[1] == "Legislación Anterior":
            for b in E.la_blocks(it[2]):
                if b["state"] == ("orig", None) and E.is_full(b["paras"]):
                    lines = E.block_text(b["paras"], True)
                    if lines:
                        h["states"] = [("", lines, "")]
                        gone = gone_by(u, mks)
                        if gone:
                            h["states"].append(gone)
                        else:
                            KEPT_ORIGINAL.append(u["name"])
                        return


def gone_by(u: dict, mks: list[str]) -> tuple | None:
    """The act the source itself names for an article it shows with no words (state: absent from that act's day).
    * arts. 209-211: the source's Notas del Editor quote the Corte Constitucional (Sentencia C-184-10): 'El artículo 98
      del Decreto ley 1295 de 1994 dispone la derogación tácita de ... los artículos 209, 210 y 211 del Código';
    * '<Artículo derogado tácitamente por el artículo 35 de la Ley 75 de 1986.>' (art. 346);
    * '<El artículo 183 del Estatuto ... - Decreto Extraordinario 1818 de 1998 fue derogado por el artículo 118 de la
      Ley 1563 de 2012. Entra a regir a partir del 12 de octubre de 2012>' (arts. 454-461, which that decree had
      incorporated)."""
    ed = " ".join(E.plain(p) for it in u["items"] if it[0] == "box" and it[1] == "Notas del Editor" for p in E.box_paras(it[2]))
    m = re.search(r"art[íi]culo 98 del Decreto ley 1295 de 1994 dispone la derogaci[óo]n t[áa]cita de .{0,80}"
                  r"art[íi]culos 209, 210 y 211 del C[óo]digo", ed)
    if m and u["name"] in ("209", "210", "211"):
        k = E.register("dec-1295-1994")
        return (E.law_day(k), None, k)
    for mk in mks:
        a = re.match(r"Art[íi]culo derogado t[áa]citamente por el art[íi]culo \d+ de la (Ley \d+ de \d{4})", mk)
        if a:
            k = E.register(E.al_key(*E.AL_RE.search(a.group(1)).groups()))
            return (E.law_day(k), None, k) if E.law_day(k) else None
        a = re.search(r"Decreto Extraordinario 1818 de 1998 fue derogado por el art[íi]culo 118 de la Ley 1563 de 2012\. "
                      r"Entra a regir a partir del (\d+ de \w+ de \d{4})", mk)
        if a:
            return (E.date_es(a.group(1)), None, E.register("ley-1563-2012"))
    return None


def article_history(u: dict, jv_extra=None) -> dict:
    """Art. 200 (enfermedad profesional): repealed by Decreto 1295 de 1994, art. 98 (its Notas de Vigencia), and revived
    by the Corte Constitucional's Sentencia C-1155-08 of 26 November 2008, which struck art. 11 of that decree: 'la presente
    declaración de inexequibilidad revive el artículo 200 del Código Sustantivo del Trabajo' (the ruling as the same note
    quotes it). The page's text, with no amendment marker, is the code's original text, in force again."""
    h = _article_history(u, jv_extra)
    if [s[1] for s in h["states"]] == [None]:
        keep_original(u, h)
    if u["name"] != "200":
        return h
    nv = " ".join(E.plain(p) for it in u["items"] if it[0] == "box" and it[1] == "Notas de Vigencia" for p in E.box_paras(it[2]))
    m = re.search(r"Sentencia (C-1155-08) de (\d+ de \w+ de \d{4}).{0,900}?revive el art[íi]culo 200 del C[óo]digo Sustantivo", nv)
    if not m or "derogado por el artículo 98 del Decreto 1295 de 1994" not in nv:
        raise SystemExit("CST art. 200: the revival note changed; check the rule")
    today = h["states"][-1][1]
    if not today or today is E.UNKNOWN:
        raise SystemExit("CST art. 200: no current text")
    rep = E.register("dec-1295-1994")
    ck = E.add_court(m.group(1), E.date_es(m.group(2)), None)
    h["states"] = [("", today, ""), (E.law_day(rep), None, rep), (E.date_es(m.group(2)), today, ck)]
    return h


E.article_history = article_history


def html_escape(s: str) -> str:
    import html
    return html.escape(s, quote=False)


_doc_units = E.doc_units


def doc_units(name: str) -> list[dict]:
    """The engine's split, with the signatures after the last article cut off (they are not part of the text)."""
    units = _doc_units(name)
    for u in units:
        fix_heading(u)
        set_aside(u)
        u["items"] =[(it[0], fix_text(it[1])) + tuple(it[2:]) if it[0] == "p"
                      else (it[0], it[1], fix_text(it[2])) + tuple(it[3:]) if it[0] == "box" else it
                      for it in u["items"]]
        # The publisher's cross-reference stubs left as paragraphs ("\tl0146_94+[Artículo 7 de la Convención]", art.
        # 236): not part of the text.
        u["items"] = [it for it in u["items"] if not (it[0] == "p" and re.match(r"\s*l\d{4}_\d{2}\+\[", E.plain(it[1])))]
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


DECISIONS: list[str] = []


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



def write_part(act: dict, out: str) -> None:
    acts = [act]
    used = ({l for a in acts for v in a["versions"] for ls in v["credits"].values() for l in ls}
            | {a["first_law"] for a in acts if a["first_law"]} | {l for a in acts for l in a["earlier_laws"]})
    laws = {k: dict(v) for k, v in sorted(E.LAWS.items()) if k in used}
    rules = [f"In force {E.IN_FORCE[k]}: {laws[k]['label']} ({E.IN_FORCE_WHY[k]})."
             for k in sorted(laws, key=lambda k: (E.IN_FORCE.get(k, ""), k)) if k in E.IN_FORCE]
    approx = sorted({r.split(":")[0] for r in E.REPORT if "latest earlier text differs" in r and r.startswith(PAGE)})
    part = {
        "sources": [{
            "name": "Secretaría General del Senado, basedoc: Código Sustantivo del Trabajo and the acts that amended it",
            "url": E.BASE + PAGE + ".html", "retrieved": E.RETRIEVED, "requests": 0,
            "licence": "Official legal text is free to reproduce (Ley 23 de 1982, art. 41). The compilation's editorial notes "
                       "(Avance Jurídico) are not reproduced; only the official text and the facts the notes state are used.",
            "notes": PAGE + " (base, continuation pages and js/ note files), plus the base and last page of each amending "
                     "act. Requests are counted in the country's shared log (corpus.json's source)."}],
        "laws": laws,
        "acts": [dict(a, versions=to_deltas(a["versions"])) for a in acts],
        "decisions": [
            "Código Sustantivo del Trabajo (cst/parse_cst.py, with the engine cst/engine.py): versions are rebuilt per "
            "article from the basedoc's earlier texts, inline amendment markers and Notas de Vigencia, as for the "
            "Constitution and the Código Civil. Where the source names an act but gives no text after it, the article "
            "reads '" + E.MISSING_LINE + "' for that period.",
            "Constitutional Court and Corte Suprema rulings that struck text are laws of kind 'court', dated by the ruling's "
            "day as the source gives it; rulings that upheld text on a condition are court laws with a note and change no words.",
            "In-force days of amending acts: the act's own vigencia clause as its basedoc page gives it; otherwise the "
            "default rule (Ley 4 de 1913, art. 52: two months after promulgation). A day a provision's own note gives "
            "applies to that provision. The list below gives the day and the rule for each act.",
            "The source's earlier texts often leave out the article's epigraph (its title); where the latest earlier text "
            "differs from today's only by that or by a change no note names, today's text is used from the latest "
            "named act's day. Articles where that happened: " + (", ".join(approx) or "none") + ".",
        ] + DECISIONS + DECISIONS_FIXED + rules,
        "ai_use": ["None at data-build time: cst/fetch_cst.py, cst/parse_cst.py and cst/engine.py are deterministic code, "
                   "written with Claude Code (claude-opus-5-5); no model reads, writes or summarises legal text."],
    }
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline=chr(10)) as f:
        json.dump(part, f, ensure_ascii=False, separators=(",", ":"))
        f.write(chr(10))
    os.replace(tmp, out)
    print(f"wrote {out}: {len(act['versions'])} versions, {len(laws)} laws, {os.path.getsize(out) // 1024} KB")


def main(argv: list[str]) -> None:
    act = build_cst()
    out = argv[argv.index("--out") + 1] if "--out" in argv else OUT
    write_part(act, out)
    if "--report" in argv:
        for r in E.REPORT:
            print("  ", r)
    else:
        print(f"  {len(E.REPORT)} report lines (--report to print)")


if __name__ == "__main__":
    main(sys.argv[1:])
