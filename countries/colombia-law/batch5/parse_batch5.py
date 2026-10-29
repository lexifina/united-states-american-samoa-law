"""Build corpus.d/95-batch5.json for Colombia: Estatuto Tributario (Decreto 624 de 1989), Estatuto General de
Contratación de la Administración Pública (Ley 80 de 1993), Estatuto del Consumidor (Ley 1480 de 2011) and Código
Nacional de Tránsito Terrestre (Ley 769 de 2002).

Reads only ../.cache/ (batch5/fetch_batch5.py, ../fetch.py); no network; deterministic. Imports the batch 4 driver
(batch4/parse_batch4.py: its generic page repairs, e.g. words replaced by an act), which imports the batch 3 and Phase 2
drivers and the engine (phase2/engine.py): the same per-provision reconstruction from the Senado basedoc, rulings as
`court` laws, and in-force days from each act's own vigencia clause.

Usage:  python -X utf8 batch5/parse_batch5.py [--report] [--out-dir DIR] [--only slug,...] [--show page:art,...]
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COUNTRY = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(COUNTRY, "batch4"))
sys.path.insert(0, os.path.join(COUNTRY, "batch3"))
sys.path.insert(0, os.path.join(COUNTRY, "phase2"))
import parse_batch4 as B4  # noqa: E402

B3 = B4.B3
P = B4.P
E = B4.E
OUT_DIR = os.path.join(COUNTRY, "corpus.d")
PART = "95-batch5.json"
DECISIONS = P.DECISIONS
E.RETRIEVED = "2026-10-29"  # this batch's fetch day (the part's `retrieved`)
PRE_START = B4.PRE_START
PRE_START.clear()


def build_all(only):
    return [BUILDERS[s]() for s in BUILDERS if s in only]


DECREE_ARTS = re.compile(r"\s*ART[IÍ]CULO (SEGUNDO|TERCERO|CUARTO)\.")
ET_DECREE: dict[str, str] = {}
HEAD_TAILS: list[str] = []
BRACKETS = re.compile(r"&lt;Aparte entre corchetes incluido por (el art&iacute;culo (?:<A [^>]*>)?\d+(?:</A>)? de la Ley \d+ de \d{4})\. El nuevo "
                      r"texto es el siguiente:&gt;")
_units_b4 = P.doc_units


def doc_units(name: str) -> list[dict]:
    """Batch 4's split, with one repair for the Estatuto Tributario: Decreto 624 de 1989 has four articles of its own, the
    first of which holds the whole Estatuto (arts. 1 to 933); the decree's arts. 2 to 4 (regulations, what the Estatuto
    replaces and when it takes effect, the decree's own vigencia) are printed after the Estatuto's art. 933. They are
    not provisions of the Estatuto: they are cut from art. 933 and read only for the first day (art. 3)."""
    units = _units_b4(name)
    if name != "estatuto_tributario":
        return units
    hits = 0
    for u in units:
        # Art. 368: '<Aparte entre corchetes incluido por el artículo 115 de la Ley 488 de 1998 ...>' with the words that
        # act put in, '{las uniones temporales}', in braces: given to the engine as a paragraph that act modified, with
        # its earlier text (the same paragraph without the words in braces) as the code's original text, so the
        # earlier version reads without them.
        for k, it in enumerate(u["items"]):
            if it[0] == "p" and BRACKETS.search(it[1]):
                h = BRACKETS.sub(r"&lt;Inciso modificado por \1. El nuevo texto es el siguiente:&gt;", it[1])
                before = re.sub(r"\s*\{[^{}]+\}", "", it[1])
                h = re.sub(r"\{([^{}]+)\}", r"\1", h)
                if before == it[1] or u["name"] != "368" or u["items"][k + 1][0] != "box":
                    raise SystemExit(f"Estatuto Tributario art. {u['name']}: words in braces")
                epi = E.html.escape(E.tidy(E.ART_HEAD.sub("", u["label"], count=1)), quote=False)
                box = ("<p><span class='b_aj'>Texto original del Estatuto Tributario</span>:</p>"
                       f"<p>{epi} {E.strip_markers(before).strip()}</p>")
                u["items"][k] = ("p", h) + tuple(it[2:])
                u["items"].insert(k + 2, ("box", "Legislación Anterior", box))
                hits += 1
                break
    if hits != 1:
        raise SystemExit(f"Estatuto Tributario: {hits} paragraphs with words in braces")
    out = []
    for u in units:
        # Articles whose anchor the publisher named 'TITULO PRE' (arts. 19-5 and 580-1): the engine would take them for
        # headings; they are numbered by their heading.
        if u is not units[0] and re.match(r"ART[IÍ]CULO\s+\d", u["label"] or "") and u["name"].startswith("TITULO"):
            u["name"] = E.label_num(u["label"])
        # Art. 424-7 has no anchor of its own: its heading starts a paragraph of art. 424-6.
        for k, it in enumerate(u["items"]):
            m = re.match(r"\s*(A(?:<span class=\"b_aj\">)?RT[IÍ]CULO (\d+-\d+)\. [A-ZÁÉÍÓÚÑ ]+\.(?:</span>)?)\s*", it[1]) \
                if it[0] == "p" and k > 0 else None
            if m:
                if (u["name"], m.group(2)) != ("424-6", "424-7"):
                    raise SystemExit(f"Estatuto Tributario: article {m.group(2)} inside art. {u['name']}")
                rest = {"name": m.group(2), "label": E.plain(m.group(1)), "page": u["page"],
                        "items": [("p", it[1][m.end():]) + tuple(it[2:])] + u["items"][k + 1:]}
                u["items"] = u["items"][:k]
                out += [u, rest]
                break
        else:
            out.append(u)
    units = out
    # Section headings the page prints at the end of an article without an anchor ('PROCEDIMIENTOS PARA LA
    # DETERMINACIÓN DE LA RETENCIÓN' after art. 384): capitals only, after the article's last note. They become a
    # heading of their own (as batch 3 does for 'SECCIÓN III.'), so they are not words of a repealed article.
    out = []
    for u in units:
        its = u["items"]
        k = len(its)
        while k > 0 and its[k - 1][0] == "p" and (not re.search(r"\w", E.plain(E.strip_markers(its[k - 1][1])))
                                                  or not re.search(r"[a-zñáéíóú]", E.plain(E.strip_markers(its[k - 1][1])))):
            k -= 1
        head = [E.tidy(E.to_text(x[1])) for x in its[k:]]
        head = [h for h in head if re.search(r"\w", h)]
        if u is not units[0] and re.match(r"ART[IÍ]CULO", u["label"] or "") and head and k > 0:
            u["items"] = its[:k]
            out += [u, {"name": f"Nivel-{u['name']}-tail", "label": head[0], "page": u["page"],
                        "items": [("p", E.html.escape(h, quote=False)) for h in head[1:]]}]
            HEAD_TAILS.append(f"{u['name']}: {' / '.join(head)}")
        else:
            out.append(u)
    units = out
    for u in units:
        items = u["items"]
        for k, it in enumerate(items):
            if it[0] == "p" and DECREE_ARTS.match(E.plain(it[1])):
                if u["name"] != "933":
                    raise SystemExit(f"Estatuto Tributario: decree article after art. {u['name']}")
                for x in items[k:]:
                    if x[0] == "p":
                        m = DECREE_ARTS.match(E.plain(x[1]))
                        if m:
                            ET_DECREE[m.group(1)] = E.plain(E.strip_markers(x[1]))
                u["items"] = items[:k]
                break
    return units


P.doc_units = doc_units
E.doc_units = doc_units


# Article headings of the Estatuto Tributario the engine cannot number: two articles that share a number (the publisher
# marks the second '<SIC>', or names its anchor '...BIS' / '...-INEXEQUIBLE'), its 'ARTICULO ADICIONAL' (added by Ley
# 546 de 1999, art. 56, after art. 57-1) and a heading without the full stop after the number ('ARTÍCULO 296-3 TARIFA.').
# (heading start, number given to the engine, why)
LABEL_FIXES = [
    ("ARTICULO 485-1. <SIC> DESCUENTO ESPECIAL", "485-1BIS",
     "art. 485-1 was added twice by Ley 223 de 1995 (arts. 22 and 170, as the source's own note says); the second, "
     "headed 'ARTICULO 485-1. <SIC> DESCUENTO ESPECIAL DEL IMPUESTO A LAS VENTAS', is the file art-0485-01-bis"),
    ("ARTÍCULO 512-22. IMPUESTO NACIONAL AL CONSUMO DE BIENES INMUEBLES", "512-22BIS",
     "two articles 512-22 stand on the page: the one added by Ley 1819 de 2016 and the one Ley 1943 de 2018 (art. 21) "
     "added on the national consumption tax on real estate, struck by Sentencia C-593 de 2019; the second is the file "
     "art-0512-22-bis"),
    ("ARTICULO 623-2. <sic> INFORMACIÓN POR OTRAS ENTIDADES", "623-2BIS",
     "two articles 623-2 stand on the page; the second, added by Ley 383 de 1997, art. 11, and headed 'ARTICULO 623-2. "
     "<sic> INFORMACIÓN POR OTRAS ENTIDADES DE CRÉDITO', is the file art-0623-02-bis"),
    ("ARTICULO ADICIONAL. INCENTIVOS", "ADICIONAL",
     "the 'ARTICULO ADICIONAL' that Ley 546 de 1999, art. 56, added after art. 57-1 is the file art-adicional"),
]
_label_num = E.label_num
_unit_key = E.unit_key


def label_num(label: str):
    for start, num, _ in LABEL_FIXES:
        if label.startswith(start):
            return num
    m = re.fullmatch(r"ART[IÍ]CULO TRANSITORIO (\d)\.", label)
    if m:
        return "T" + m.group(1)
    m = re.match(r"ART[IÍ]CULO\s+(\d+)-(\d+)\s+[A-ZÁÉÍÓÚÑ]", label)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return _label_num(label)


def unit_key(name: str):
    if name == "ADICIONAL":
        return "art-adicional", "Art. adicional"
    if re.fullmatch(r"T\d", name):
        return f"art-transitorio-{name[1]}", f"Art. transitorio {name[1]}"
    if name == "260-2A":
        return "art-0260-02a", "Art. sin número (después del art. 260-2)"
    if name.endswith("BIS"):
        k, lab = _unit_key(name[:-3])
        return k + "-bis", lab + " bis"
    return _unit_key(name)


E.label_num = label_num
E.unit_key = unit_key
# 'ADICIONAL' is the number of that article, not the start of its epigraph.
E.ART_HEAD = re.compile(E.ART_HEAD.pattern.replace("|NUEVO|", "|NUEVO|ADICIONAL|"), re.I)
DECISIONS.extend("Estatuto Tributario: " + why for _, _, why in LABEL_FIXES)

_page_header = E.page_header


def page_header(page: str, year: str):
    """The Estatuto Tributario's page opens with the publisher's warnings and the delegating statutes, so its heading
    ('DECRETO 624 DE 1989', '(30 de marzo de 1989)', 'Diario Oficial No. 38.756 de 30 de marzo de 1989') is further down
    than the engine looks, and its day is written in full."""
    if page == "ley_0769_2002":
        # its heading writes the day first: '(6 de julio)'
        enacted, pub = _page_header(page, year)
        ps = E.page_paras(page)
        i = ps.index("LEY 769 DE 2002")
        m = re.fullmatch(r"\((\d{1,2}) de ([a-z]+)\)", ps[i + 1])
        if enacted or not m:
            raise SystemExit(f"Ley 769 heading: {ps[i:i + 3]}")
        return f"{year}-{E.MONTHS[m.group(2)]:02d}-{int(m.group(1)):02d}", pub
    if page != "estatuto_tributario":
        return _page_header(page, year)
    ps = E.page_paras(page)
    i = ps.index("DECRETO 624 DE 1989")
    m = re.fullmatch(r"\((\d{1,2}) de ([a-z]+) de (\d{4})\)", ps[i + 1])
    d = E.DO_RE.search(ps[i + 2])
    if not m or not d or ps[i + 2] != "Diario Oficial No. 38.756 de 30 de marzo de 1989":
        raise SystemExit(f"Estatuto Tributario heading: {ps[i:i + 3]}")
    return f"{m.group(3)}-{E.MONTHS[m.group(2)]:02d}-{int(m.group(1)):02d}", E.date_es(d.group(1))


E.page_header = page_header


def start_et(units, enacted, pub):
    a = ET_DECREE.get("TERCERO", "")
    b = ET_DECREE.get("CUARTO", "")
    if "entrará en vigencia dos (2) meses después de la publicación" not in a or not pub or enacted != "1989-03-30":
        raise SystemExit(f"Decreto 624 de 1989 art. 3: {a!r} {enacted} {pub}")
    start = E.add_months(pub, 2)
    return (start, f"Decreto 624 de 1989, art. 3: '{a}' (published {pub}); art. 4: '{b}'",
            f"The Estatuto Tributario as issued (Decreto 624 de 1989, art. 1, of {enacted}, Diario Oficial No. 38.756 of "
            f"{pub}), in force from {start} under the decree's art. 3: '{a}' The decree's own arts. 2 to 4, printed after "
            "art. 933, are not provisions of the Estatuto and are not part of this record.")


# Typing slips in these acts' notes and earlier-text headings, each fixed by what the same article's notes say (the
# article number and the Diario Oficial they give). wrong key -> right key.
KEY_FIXES = {
    "ley-1111-2016": "ley-1111-2006",   # ET art. 147: 'Texto modificado por la Ley 1111 de 2016: <Inciso modificado por el artículo 5 de la Ley 1111 de 2006 ...>'
    "ley-111-2006": "ley-1111-2006",    # ET art. 276
    "ley-11111-2010": "ley-1111-2006",  # ET art. 245: its parágrafo 5 was added by Ley 1111 de 2006, art. 13
    "ley-11607-2012": "ley-1607-2012",  # ET art. 560: '<Numeral modificado por el artículo 134 de la Ley 1607 de 2012 ...>'
    "ley-1607-2016": "ley-1607-2012",   # ET art. 462-1: article modified by Ley 1607 de 2012, art. 46
    "ley-96-2012": "ley-1607-2012",     # ET art. 254: 'Artículo modificado por el artículo 96 de la Ley 1607 de 2012'
    "ley-1819-2006": "ley-1819-2016",   # ET art. 339 (added by Ley 1819 de 2016)
    "ley-1918-2016": "ley-1819-2016",   # ET art. 420: 'Artículo modificado por el artículo 173 de la Ley 1819 de 2016'
    "ley-2010-2010": "ley-2010-2019",   # ET art. 206: '<Parágrafo modificado por el artículo 32 de la Ley 2010 de 2019 ...>'
    "dec-2010-2019": "ley-2010-2019",   # ET art. 616-1: 'parcialmente modificado por el Decreto 2010 de 2019' (Ley 2010 de 2019)
    "dec-1943-2018": "ley-1943-2018",   # ET art. 616-1 (Ley 1943 de 2018)
    "ley-2106-2019": "dec-2106-2019",   # 'Decreto Ley 2106 de 2019' (ET and Código Nacional de Tránsito notes)
    "ley-223-1994": "ley-223-1995",     # ET arts. 253, 437-2: 'modificado por el artículo 250 de la Ley 223 de 1995'
    "ley-630-2000": "ley-633-2000",     # ET art. 689-1: 'Artículo modificado por el artículo 17 de la Ley 633 de 2000'
    "ley-633-2002": "ley-633-2000",     # ET art. 211: '<Artículo modificado por el artículo 13 de la Ley 633 de 2000 ...>'
    "ley-633-2020": "ley-633-2000",     # ET art. 36-1: '<Inciso modificado por el artículo 9 de la Ley 633 de 2000 ...>'
    "ley-863-2006": "ley-863-2003",     # ET art. 297: 'Artículo modificado por el artículo 17 de la Ley 863 de 2003'
    "ley-833-2003": "ley-863-2003",     # ET art. 468-3: 'Numeral 2. modificado por el artículo 52 de la Ley 863 de 2003'
    "dec-44715-2005": "dec-4715-2005",  # ET: 'Mediante el artículo 1 del Decreto 4715 de 2005 ... valores absolutos ... 2006'
    "dec-3804-2004": "dec-3804-2003",   # ET art. 55: 'Mediante el artículo 1 del Decreto 3804 de 2003 ... para el año 2004'
    "dec-3227-2002": "dec-3257-2002",   # ET art. 127-1: 'Mediante el artículo 1 del Decreto 3257 de 2002 ... para el año 2003'
    "dec-18-2012": "dec-19-2012",       # Ley 769 art. 53: 'Artículo modificado por el artículo 203 del Decreto 19 de 2012'
    "ley-633-2012": "ley-633-2000",     # ET art. 145: 'Parágrafo adicionado por el artículo 131 de la Ley 633 de 2000'
}
# Typing slips in earlier-text headings that leave them unreadable, fixed with batch 4's HEADING_FIXES (page, wrong,
# right, why).
B4.HEADING_FIXES.extend([
    ("estatuto_tributario", "Texto adicicionado por la Ley 6 1992", "Texto adicionado por la Ley 6 de 1992",
     "art. 659-1: 'Texto adicicionado por la Ley 6 1992' is read as 'Texto adicionado por la Ley 6 de 1992' (its note: "
     "added by Ley 6 de 1992)"),
    ("estatuto_tributario", "Texto modificado por la Ley 223 de 195:", "Texto modificado por la Ley 223 de 1995:",
     "art. 279: 'Texto modificado por la Ley 223 de 195' is read as Ley 223 de 1995"),
    ("ley_0080_1993", "Decreto Legistalico 537 de 2020", "Decreto Legislativo 537 de 2020",
     "an earlier text headed 'Texto adicionado por el Decreto Legistalico 537 de 2020' is read as Decreto Legislativo "
     "537 de 2020"),
    ("estatuto_tributario", "Texto vigente del Estatuto Tributario antes de su derogatoria:",
     "Texto vigente antes de la derogatoria por la Ley 223 de 1995:",
     "art. 212: the earlier text headed 'Texto vigente del Estatuto Tributario antes de su derogatoria' is the inciso "
     "that its own marker says Ley 223 de 1995, art. 285, derogated"),
    ("ley_1480_2011", "Texto original de la Ley 1448 de 2011", "Texto original de la Ley 1480 de 2011",
     "art. 47: its earlier text is headed 'Texto original de la Ley 1448 de 2011'; it is the "
     "act's own original wording (Ley 1448 de 2011, the victims' law, is older than the Estatuto and never amended it)"),
])
_PAGE_NAMES = {"estatuto_tributario": "Estatuto Tributario", "ley_1480_2011": "Estatuto del Consumidor",
               "ley_0080_1993": "Estatuto General de Contratación (Ley 80 de 1993)"}
DECISIONS.extend(_PAGE_NAMES[page] + ": " + why for page, _, _, why in B4.HEADING_FIXES if page in _PAGE_NAMES)
E.KEY_FIXES.update(KEY_FIXES)
DECISIONS.append("Estatuto Tributario and Código Nacional de Tránsito: typing slips in the act numbers or years of the "
                 "source's notes and earlier-text "
                 "headings are read as the act the same article's notes name (article and Diario Oficial): "
                 + "; ".join(f"{E.law_label(a)} as {E.law_label(b)}" for a, b in KEY_FIXES.items()) + ".")

E.HAND_RULES["dec-62-1996"] = ("1996-01-17", "Decreto 62 de 1996, art. 2: 'El presente decreto se entenderá incorporado al "
                                             "Decreto 2150 de 1995 y rige a partir de la fecha de su publicación en el "
                                             "Diario Oficial.' (its page: 'Diario Oficial No. 42.690, de enero 17 de 1996')")

# The decrees that updated the Estatuto Tributario's absolute values each year before the UVT (Ley 1111 de 2006): the
# Estatuto's own notes give the year they govern ('Mediante el artículo 1 del Decreto 4715 de 2005, publicada en el
# Diario Oficial No. 46.134 de 27 de diciembre de 2005, se establecen los valores absolutos que regirán para el año
# 2006'); the new values are dated from 1 January of that year.
VALUE_NOTE = re.compile(r"Mediante (?:el )?art[íi]culo [^,]{0,30}? del? Decreto (\d+) de (\d{4}),? publicad[oa] en el "
                        r"Diario Oficial[^,]{0,20},? (?:del? )?(\d{1,2}(?:o\.)? de [a-z]+ de \d{4}),? se "
                        r"(?:actualizaron|establecen)[^.]{0,80}? que regir[áa]n para el año (\d{4})")


def value_decrees(units) -> None:
    found = {}
    for u in units:
        for it in u["items"]:
            if it[0] == "box" and it[1] == "Notas de Vigencia":
                for m in VALUE_NOTE.finditer(E.plain(it[2])):
                    n, y, pub, year = m.groups()
                    if int(year) != int(y) + 1:
                        raise SystemExit(f"value decree {n} de {y} for {year}")
                    found[f"dec-{int(n)}-{y}"] = (f"{year}-01-01", f"the Estatuto Tributario's notes: 'Mediante el "
                                                 f"artículo ... del Decreto {n} de {y}, publicado en el Diario Oficial ... de "
                                                 f"{pub}, se actualizaron los valores absolutos que regirán para el año "
                                                 f"{year}' (the values apply from 1 January {year})")
    for k, rule in sorted(found.items()):
        if k not in E.HAND_RULES:
            E.HAND_RULES[k] = rule
    DECISIONS.append("Estatuto Tributario: the decrees that updated its absolute values each year (" + ", ".join(
        E.law_label(k) for k in sorted(found, key=lambda k: k.split("-")[2])) + ") are dated from 1 January of the year "
        "the Estatuto's own notes say the values govern.")


# 'Texto del Proyecto de Ley 12 de 2006 Cámara, 87 de 2007 Senado' (Código Nacional de Tránsito): the text of a bill,
# which never changed the code; its block is left out of the earlier texts.
BILL_HEAD = re.compile(r"Texto (?:reelaborado )?del Proyecto de Ley", re.I)
_units_et = doc_units


def doc_units_bills(name: str) -> list[dict]:
    units = _units_et(name)
    for u in units:
        for k, it in enumerate(u["items"]):
            if it[0] != "box" or it[1] != "Legislación Anterior" or not BILL_HEAD.search(E.plain(it[2])):
                continue
            keep, skip = [], False
            for m in re.finditer(r"<p\b[^>]*>.*?</p>", it[2], re.S | re.I):
                ph = re.match(r"<p\b[^>]*>(.*?)</p>", m.group(0), re.S | re.I).group(1)
                sp = re.match(r"(?:\s|&#160;|&nbsp;)*<span class='b_aj'>(.*?)</span>", ph, re.S)
                if sp and E.plain(sp.group(1)).lower().startswith("texto"):
                    skip = bool(BILL_HEAD.match(E.plain(sp.group(1))))
                    if skip:
                        BILLS.add(f"{name} {u['name']}")
                if not skip:
                    keep.append(m.group(0))
            u["items"][k] = (it[0], it[1], "".join(keep)) + tuple(it[3:])
    # Words an act repealed inside an article's epigraph, which the page prints in its heading anchor ('ARTÍCULO 11. DE
    # LA COMPETENCIA PARA DIRIGIR LICITACIONES <S>O CONCURSOS</S> Y PARA ...' with '<Aparte tachado derogado por el
    # artículo 32 de la Ley 1150 de 2007>' after it): the engine reads the heading as plain text, so the epigraph, struck
    # words and all, is moved to the start of the first paragraph, where the struck words are read like any other.
    # Ley 769 de 2002 has two articles headed only 'ARTÍCULO TRANSITORIO.' (added by Ley 1383 de 2010, art. 27, and Ley
    # 2155 de 2021, art. 49; anchors 'transitorio' and 'Transitorio 2'): numbered 1 and 2 in page order.
    if name == "ley_0769_2002":
        tr = [u for u in units[1:] if u["label"] == "ARTÍCULO TRANSITORIO."]
        if [u["name"] for u in tr] != ["transitorio", "Transitorio 2"]:
            raise SystemExit(f"Ley 769: transitional articles {[u['name'] for u in tr]}")
        for n, u in enumerate(tr, 1):
            u["label"] = f"ARTÍCULO TRANSITORIO {n}."
    # The Estatuto Tributario's article without a number that Ley 1111 de 2006, art. 16, added after art. 260-2 (anchor
    # '260-2A', heading 'ARTÍCULO.'; repealed by Ley 1430 de 2010, art. 67) is the file art-0260-02a.
    if name == "estatuto_tributario":
        a = [u for u in units if u["name"] == "260-2A"]
        if [u["label"] for u in a] != ["ARTÍCULO."]:
            raise SystemExit("Estatuto Tributario: art. 260-2A")
        # its earlier text starts 'ARTÍCULO. <Artículo adicionado ...>': the heading without a number is dropped like
        # any 'ARTÍCULO N.' heading
        it = [k for k, x in enumerate(a[0]["items"]) if x[0] == "box" and x[1] == "Legislación Anterior"]
        if len(it) != 1 or a[0]["items"][it[0]][2].count("<p>ART&Iacute;CULO. &lt;") != 1:
            raise SystemExit("Estatuto Tributario: art. 260-2A earlier text")
        x = a[0]["items"][it[0]]
        a[0]["items"][it[0]] = (x[0], x[1], x[2].replace("<p>ART&Iacute;CULO. &lt;", "<p>ART&Iacute;CULO &lt;")) + tuple(x[3:])
    # Section headings with anchors of their own that the engine does not know as headings ('SUJETOS PASIVOS.',
    # 'I. DE LAS DISPOSICIONES GENERALES.'): capitals only, not an article. They become headings (the engine would skip
    # them). Two whose anchor holds only the first letter ('I' + 'NGRESOS DE FUENTE NACIONAL ...') are joined.
    for u in units[1:]:
        lab = u["label"] or ""
        ps = [x for x in u["items"] if x[0] == "p"]
        if re.fullmatch(r"[A-Z]", lab) and ps and re.match(r"[A-ZÁÉÍÓÚÑ ,.]+$", E.plain(ps[0][1]).strip()):
            u["label"] = lab + E.plain(ps[0][1]).strip()
            u["items"] = [x for x in u["items"] if x is not ps[0]]
            lab = u["label"]
        if (lab and not re.search(r"[a-zñáéíóú]", lab) and re.search(r"[A-Z]{3}", lab) and not re.match(r"ART[IÍ]CULO", lab)
                and not E.heading_level(lab) and not u["name"].startswith("Nivel")
                and not re.match(r"(T[ÍI]TULO|CAP[ÍI]TULO)\b", u["name"])):
            u["name"] = "Nivel-" + u["name"]
            HEADINGS.add(f"{name}: {lab}")
    raw = {}
    for pg in E.pages(name):
        for m in E.ANC.finditer(E.read(E.BASE + pg + ".html") or ""):
            if re.search(r"<s\b", m.group(2), re.I):
                raw[m.group(1)] = m.group(2)
    for u in units[1:]:
        h = raw.get(u["name"])
        if h is None or not re.match(r"ART[IÍ]CULO\s+\d", u["label"] or ""):
            continue
        m = re.match(r"\s*(ART(?:Í|&Iacute;|I)CULO\s+\d+[A-Z]?\.)\s*(.*)$", h, re.S | re.I)
        ps = [k for k, it in enumerate(u["items"]) if it[0] == "p"]
        if not m or not ps or not any(re.search(r"tachad\w*\s+(derogad|INEXEQUIBLE)", x, re.I)
                                      for x in E.markers(u["items"][ps[0]][1])):
            raise SystemExit(f"{name} art. {u['name']}: struck words in the heading: {E.plain(h)[:120]}")
        u["label"] = E.plain(m.group(1))
        it = u["items"][ps[0]]
        u["items"][ps[0]] = ("p", m.group(2).strip() + " " + it[1]) + tuple(it[2:])
        STRUCK_EPI.add(f"{name} {u['name']}")
    return units


STRUCK_EPI: set[str] = set()
HEADINGS: set[str] = set()


BILLS: set[str] = set()
P.doc_units = doc_units_bills
E.doc_units = doc_units_bills


def start_ley80(units, enacted, pub):
    a = B3.article_text(units, "81")
    if "A partir de la promulgación de la presente ley, entrarán a regir el parágrafo del artículo 2o." not in a or \
            "entrarán a regir a partir del 1o. de enero de 1994" not in a or not pub:
        raise SystemExit(f"Ley 80 art. 81: {a[:300]!r}")
    a = a[:a.index("El Presidente del")].strip() if "El Presidente del" in a else a
    return (pub, f"Ley 80 de 1993, art. 81: '{a[:900]}' The first version is dated from promulgation ({pub}), when the "
                 "parts the article names took effect; the rest from 1 January 1994.",
            f"The act as promulgated (Ley 80 de 1993, sanctioned {enacted}, Diario Oficial of {pub}). Under its art. 81 the "
            "parts it names (concessions, public trusts, telecommunications, arts. 33 to 38 and others) took effect on "
            "promulgation, the rest on 1 January 1994, and the rules on the register of bidders one year after "
            "promulgation. The history dates the whole act from promulgation.")


def start_1480(units, enacted, pub):
    a = B3.article_text(units, "84")
    if not a.startswith("La presente ley entrará en vigencia seis (6) meses después de su promulgación") or not pub:
        raise SystemExit(f"Ley 1480 art. 84: {a[:300]!r}")
    a = a[:a.index("El Presidente del")].strip() if "El Presidente del" in a else a
    start = E.add_months(pub, 6)
    return (start, f"Ley 1480 de 2011, art. 84: '{a}' (published {pub})",
            f"The act as promulgated (Ley 1480 de 2011, sanctioned {enacted}, Diario Oficial of {pub}), in force from "
            f"{start} under its art. 84: '{a}'")


def start_769(units, enacted, pub):
    a = B3.article_text(units, "170")
    if not a.startswith("El presente código empezará a regir transcurridos tres (3) meses contados a partir de su "
                        "promulgación") or not pub:
        raise SystemExit(f"Ley 769 art. 170: {a[:300]!r}")
    a = a[:a.index("El Presidente del")].strip() if "El Presidente del" in a else a
    start = E.add_months(pub, 3)
    return (start, f"Ley 769 de 2002, art. 170: '{a}' (published {pub})",
            f"The code as promulgated (Ley 769 de 2002, sanctioned {enacted}, Diario Oficial of {pub}), in force from "
            f"{start} under its art. 170: '{a}'")


BUILDERS: dict = {
    "estatuto-tributario": lambda: value_decrees(P.doc_units("estatuto_tributario")) or B3.build(
        "estatuto_tributario", "dec-624-1989", "estatuto-tributario", "ET",
        "Estatuto Tributario (Decreto 624 de 1989)",
        "Por el cual se expide el Estatuto Tributario de los Impuestos Administrados por la Dirección General de "
        "Impuestos Nacionales", start_et),
    "estatuto-general-de-contratacion": lambda: B3.build(
        "ley_0080_1993", "ley-80-1993", "estatuto-general-de-contratacion", "EGC",
        "Estatuto General de Contratación de la Administración Pública (Ley 80 de 1993)",
        "Por la cual se expide el Estatuto General de Contratación de la Administración Pública", start_ley80),
    "estatuto-del-consumidor": lambda: B3.build(
        "ley_1480_2011", "ley-1480-2011", "estatuto-del-consumidor", "EC", "Estatuto del Consumidor (Ley 1480 de 2011)",
        "Por medio de la cual se expide el Estatuto del Consumidor y se dictan otras disposiciones", start_1480),
    "codigo-nacional-de-transito": lambda: B3.build(
        "ley_0769_2002", "ley-769-2002", "codigo-nacional-de-transito", "CNT",
        "Código Nacional de Tránsito Terrestre (Ley 769 de 2002)",
        "Por la cual se expide el Código Nacional de Tránsito Terrestre y se dictan otras disposiciones", start_769),
}
P.PREFIX.update({"estatuto-tributario": ("estatuto_tributario", "ET"),
                 "estatuto-general-de-contratacion": ("ley_0080_1993", "EGC"),
                 "estatuto-del-consumidor": ("ley_1480_2011", "EC"),
                 "codigo-nacional-de-transito": ("ley_0769_2002", "CNT")})
NAMES = ("Estatuto Tributario", "Estatuto General de Contratación", "Estatuto del Consumidor",
         "Código Nacional de Tránsito")


def finish_part(path: str) -> None:
    with open(path, encoding="utf-8") as f:
        part = json.load(f)
    part["ai_use"] = ["None at data-build time: batch5/fetch_batch5.py and batch5/parse_batch5.py (with batch4/, batch3/ "
                      "and phase2/, which they import) are deterministic code, written with Claude Code "
                      "(claude-opus-5-5); no model reads, writes or summarises legal text."]
    part["sources"][0]["notes"] += (" Terms checked 2026-10-28: robots.txt disallows only the Joomla system folders, not "
                                    "/senado/basedoc/; each page's footer reserves Avance Jurídico's notes, concordances "
                                    "and arrangement, so only the official text and the facts the notes state are used. "
                                    "Pages retrieved on 2026-10-28 (the base and last pages of Leyes 80 de 1993, 1480 de "
                                    "2011 and 769 de 2002) and 2026-10-29 (the rest); the source's footer gives the same "
                                    "last update on both days (15 October 2026, Diario Oficial No. 53.651).")
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
    acts = build_all(only)
    if "estatuto-tributario" in only:
        DECISIONS.append("Estatuto Tributario: Decreto 624 de 1989 has four articles of its own; art. 1 holds the whole "
                         "Estatuto (arts. 1 to 933). The decree's arts. 2 to 4, printed after art. 933, are not "
                         "provisions of the Estatuto and are left out; art. 3 (in force two months after publication) "
                         "dates the first version.")
        DECISIONS.append("Estatuto Tributario: section headings the page prints at the end of an article, without an "
                         "anchor and in capitals only, are headings, not words of that article: " + "; ".join(
                             sorted(set(HEAD_TAILS), key=lambda x: (len(x.split(':')[0]), x))) + ".")
        DECISIONS.append("Estatuto Tributario: art. 368, '<Aparte entre corchetes incluido por el artículo 115 de la Ley "
                         "488 de 1998>': the words in braces ('las uniones temporales') are absent before that act, and "
                         "only they (the comma before them stays, as printed).")
        DECISIONS.append("Estatuto Tributario: art. 424-7 has no anchor of its own on the page; its heading starts a "
                         "paragraph of art. 424-6 and is split off as its own article.")
        DECISIONS.append("Estatuto Tributario: the article without a number that Ley 1111 de 2006, art. 16, added after "
                         "art. 260-2 (the page heads it 'ARTÍCULO.'; repealed by Ley 1430 de 2010, art. 67) is the file "
                         "art-0260-02a.")
    if "codigo-nacional-de-transito" in only:
        DECISIONS.append("Código Nacional de Tránsito: its two articles headed only 'ARTÍCULO TRANSITORIO.' (added by Ley "
                         "1383 de 2010, art. 27, and Ley 2155 de 2021, art. 49) are the files art-transitorio-1 and "
                         "art-transitorio-2, in page order.")
    if HEADINGS:
        DECISIONS.append("Estatuto Tributario, Estatuto General de Contratación, Estatuto del Consumidor and Código Nacional "
                         f"de Tránsito: {len(HEADINGS)} section headings with anchors of their own in capitals only (for "
                         "example 'SUJETOS PASIVOS.', 'I. DE LAS DISPOSICIONES GENERALES.') are kept as headings in "
                         "titulos.md; two whose anchor holds only their first letter are joined with the rest.")
    for page, nm in (("ley_0080_1993", "Estatuto General de Contratación (Ley 80 de 1993)"),
                     ("ley_0769_2002", "Código Nacional de Tránsito")):
        arts = sorted(x.split(" ")[1] for x in STRUCK_EPI if x.startswith(page + " "))
        if arts:
            DECISIONS.append(f"{nm}: art(s). {', '.join(arts)}: words of the epigraph that the page prints struck in the "
                             "article's heading (repealed by an act, or struck by the Court, as the marker after it says) "
                             "are read like struck words of the text: present before, absent after.")
    if BILLS:
        DECISIONS.append("Código Nacional de Tránsito: earlier texts headed 'Texto del Proyecto de Ley 12 de 2006 Cámara, "
                         "87 de 2007 Senado' are the text of a bill, which never changed the code, and are left out ("
                         + ", ".join(sorted(BILLS)) + ").")
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
