"""The COIP's amending acts, replayed in order of entry into force on the Code as enacted (RO Supl. 180, 2014).

Every act with a text layer in the Registro Oficial is a function that edits a copy of the previous version's units
(civil/replay.py's Units). New wording is never typed here as such: it is cut out of the act's own cached gazette PDF
(civil/replay.py's Src) after an anchor phrase, and every short phrase an act inserts is checked to occur, word for
word, in that act's PDF. Changed units are credited to the act automatically.

Acts whose gazette edition has no text layer are NOT applied (no OCR, by the user's decision): they get a version of
their own that changes no words, credited to the provisions an editorial index names, with a note saying so.

Anachronism rule: a version in force on day D may only carry wording from acts published on or before D, and every
act is applied on its own in-force day, never earlier. `check_anachronism` enforces it on the finished versions.
"""
from __future__ import annotations

import datetime as dt
import json
import hashlib
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "civil"))
import fetch  # noqa: E402
import rotext  # noqa: E402
from replay import Src, Units, unquote  # noqa: E402  (civil/replay.py: gazette cutting and unit edits)

H = "http://esacc.corteconstitucional.gob.ec/storage/api/v1/10_DWL_FL/"


def ro(b64: str) -> str:
    return H + b64


_EDITIONS = json.loads((HERE / "editions.json").read_text(encoding="utf-8"))


def ed(name: str, title: str) -> str:
    """PDF URL of one edition found by coip/find_editions.py ('s598-2015', 'Tercer Suplemento')."""
    hits = [e["pdf"] for e in _EDITIONS[name] if e["title"] == title]
    if len(hits) != 1:
        raise SystemExit(f"edition {name} {title!r}: {len(hits)} matches")
    return hits[0]


S180_2014 = ro("eyJjYXJwZXRhIjoicm8iLCJ1dWlkIjoiMjkwYzMxODUtNTY0OC00MzNjLTk1ZDEtZDg0NjY1NDc5NWI0LnBkZiJ9")
S2_332_2014 = ro("eyJjYXJwZXRhIjoicm8iLCJ1dWlkIjoiNDIwM2NhZGUtMzY2Yy00ZWIzLTgzZmQtZDI5Yzg3NGY3ZjU0LnBkZiJ9")
S3_598_2015 = ed("s598-2015", "Tercer Suplemento")
S615_2015 = ed("s615-2015", "Primer Suplemento")
S711_2016 = ed("s711-2016", "Primer Suplemento")
S2_802_2016 = ed("s802-2016", "Segundo Suplemento")
S2_150_2017 = ed("s150-2017", "Segundo Suplemento")
S133_2017 = ro("eyJjYXJwZXRhIjoicm8iLCJ1dWlkIjoiYTg1ZGM4YzMtM2U4ZS00OGI5LWI1YjEtZGJmZWQzZGJhNWE0LnBkZiJ9")
S180_2018 = ro("eyJjYXJwZXRhIjoicm8iLCJ1dWlkIjoiOGMwNTA4ZmMtYTQ0NS00MWRlLTk3OWEtZmZiMjY5NGMyNWQ0LnBkZiJ9")
S175_2018 = ed("s175-2018", "Primer Suplemento")
S478_2019 = ed("s478-2019", "Primer Suplemento")
S481_2019 = ed("s481-2019", "Primer Suplemento")
EC90_2019 = ed("ec90-2019", "Ediciones Constitucionales")
EC6_2019 = ed("ec6-2019", "Ediciones Constitucionales")
EC21_2019 = _EDITIONS["ec21-2019"][0]["pdf"]
S107_2019 = ed("s107-2019", "Primer Suplemento")
S3_386_2021 = ed("s386-2021b", "Tercer Suplemento")
S2_392_2021 = ed("s392-2021", "Segundo Suplemento")
S5_452_2021 = ro("eyJjYXJwZXRhIjoicm8iLCJ1dWlkIjoiNzE1OWU4NzctZDI2OS00ZDBjLWJlNTctOTk0YzRiNzU0MTAyLnBkZiJ9")  # civil/replay.py
EC194_2021 = ed("ec194-2021", "Ediciones Constitucionales")
S5_512_2021 = ed("s512-2021", "Quinto Suplemento")
S5_525_2021 = ed("s525-2021", "Quinto Suplemento")
S4_526_2021 = ed("s526-2021", "Cuarto Suplemento")
EC222_2021 = ed("ec222-2021", "Ediciones Constitucionales")
EC261_2022 = ed("ec261-2022", "Ediciones Constitucionales")
EC267_2022 = ed("ec267-2022", "Ediciones Constitucionales")
EC268_2022 = ed("ec268-2022", "Ediciones Constitucionales")
EC20_2022 = ed("ec20-2022", "Ediciones Constitucionales")
S3_131_2022 = ed("s131-2022", "Tercer Suplemento")
S222_2023 = ed("s222-2023", "Primer Suplemento")
# 2023 to 2026 (coip/find_editions.py; amending acts indexed by coip/index_el2026.py and coip/index_asamblea.py)
S279_2023 = ed("s279-2023", "Primer Suplemento")
S471_2024 = ed("s471-2024", "Primer Suplemento")
S2_496_2024 = ed("s496-2024", "Segundo Suplemento")
EC319_2024 = ed("ec319-2024", "Ediciones Constitucionales")
S3_588_2024 = ed("s588-2024", "Tercer Suplemento")
S599_2024 = ed("s599-2024", "Primer Suplemento")
S4_610_2024 = ed("s610-2024", "Cuarto Suplemento")
S5_700_2024 = ed("s700-2024", "Quinto Suplemento")
EC8_2025 = ed("ec8-2025", "Ediciones Constitucionales")
EC15_2025 = ed("ec15-2025", "Ediciones Constitucionales")
S5_38_2025 = ed("s38-2025", "Quinto Suplemento")
S6_56_2025 = ed("s56-2025", "Sexto Suplemento")
S3_68_2025 = ed("s68-2025", "Tercer Suplemento")
EC96_2025 = ed("ec96-2025", "Ediciones Constitucionales")
S7_151_2025 = ed("s151-2025", "Séptimo Suplemento")
S4_275_2026 = ed("s275-2026", "Cuarto Suplemento")
S5_290_2026 = ed("s290-2026", "Quinto Suplemento")
S5_316_2026 = ed("s316-2026", "Quinto Suplemento")
S5_343_2026 = ed("s343-2026", "Quinto Suplemento")


def plazo_days(published: str, days: int) -> str:
    """In force after a plazo of `days` days counted from publication: Código Civil art. 33 (plazos are complete days
    and run to midnight of the last day), the publication day not counted, so the act binds from the next day."""
    return (dt.date.fromisoformat(published) + dt.timedelta(days=days + 1)).isoformat()


def plazo_months(published: str, months: int) -> str:
    """Código Civil art. 33: a plazo of months ends on the same date of the later month."""
    d = dt.date.fromisoformat(published)
    m = d.month - 1 + months
    return dt.date(d.year + m // 12, m % 12 + 1, d.day).isoformat()


# ---------------------------------------------------------------- cutting quoted text out of a gazette edition

def qfrom(src: Src, anchor: str, after: str | None = None) -> list[str]:
    """The quotation that opens right after `anchor` (in the same paragraph or the next one), as paragraphs.

    The quotation closes at the first double quote that leaves an even count of quotes and is followed by the end
    of a paragraph, a stop/comma/semicolon, or the act's next lettered or numbered item ('" b) Agregar ...')."""
    i = src.index(anchor, after)
    p = src.paras[i]
    head = p[p.index(anchor) + len(anchor):]
    text = "\n".join([head] + src.paras[i + 1:i + 80])
    start = text.find('"')
    if start < 0 or text[:start].strip():
        raise SystemExit(f"no quotation right after {anchor!r}: {text[:60]!r}")
    count = 0
    for m in re.finditer('"', text):
        if m.start() < start:
            continue
        count += 1
        if count % 2 or m.start() == start:
            continue
        rest = text[m.end():]
        if re.match(r"[.,;]?\s*(\n|$|[a-z]\)\s|\d+\.-?\s|[A-ZÁÉÍÓÚ])", rest):
            stop = rest[:1] if rest[:1] in ".,;" else ""
            inner = text[start:m.end()] + stop
            return unquote(inner.split("\n"))
    raise SystemExit(f"quotation after {anchor!r} does not close")


def paras_between(src: Src, first: str, last: str, after: str | None = None) -> list[str]:
    """Whole paragraphs from the one starting with `first` to the one containing `last` (unquoted text an act adds)."""
    i = src.index(first, after)
    if not src.paras[i].startswith(first):
        raise SystemExit(f"{first!r} does not start its paragraph")
    j = src.index(last, src.paras[i]) if last not in src.paras[i] else i
    return src.paras[i:j + 1]


def phrase(src: Src, text: str) -> str:
    """A short phrase an act inserts, checked to occur word for word in the act's PDF."""
    src.check(text)
    return text


# ---------------------------------------------------------------- the acts (text layer available)

def comf_2014(u: Units) -> None:
    """Código Orgánico Monetario y Financiero (Segundo Supl. 332, 12-IX-2014), Disposición reformatoria trigésima
    séptima: art. 278, fourth inciso replaced (by two paragraphs); art. 557 num. 3, a sentence added after 'para el
    efecto.'."""
    s = csrc(S2_332_2014)
    new = qfrom(s, "sustitúyase el cuarto inciso por el siguiente:")
    if len(new) != 2:
        raise SystemExit(f"COMF 278: {len(new)} paragraphs")
    u.set_para("art-278", 3, new)
    add = qfrom(s, 'numeral 3, después de "para el efecto." agréguese:')[0]
    u.sub("art-557", "para el efecto.", "para el efecto. " + add, para="3. ")


def reformatoria_coip_2015(u: Units) -> None:
    """Ley Orgánica Reformatoria del Código Orgánico Integral Penal (Tercer Supl. 598, 30-IX-2015), arts. 1-13; in
    force on publication (its Disposición final)."""
    s = csrc(S3_598_2015)
    # 1. art. 19: second and third paragraphs removed
    s.check("En el artículo 19, elimínense los párrafos segundo y tercero.")
    ps = u.paras("art-019")
    u.put("art-019", ps[:1] + ps[3:])
    # 2. art. 186, fourth paragraph (numerals are not counted as paragraphs): 'privados,' after 'fondos'
    s.check('En el párrafo cuarto del artículo 186, después de la palabra "fondos", poner la palabra "privados,".')
    u.sub("art-186", "fondos públicos", "fondos privados, públicos", para="La estafa cometida")
    # 3. new article 208 A after art. 208
    new = qfrom(s, "luego del artículo 208, agréguese el siguiente artículo:")
    u.set_unit("art-208-a", new, label="Art. 208 A")
    # 4. art. 278, fourth paragraph: 'y vigilancia' after 'consejo de administración' (the paragraph, as replaced by
    #    the COMF in 2014, reads 'consejos de administración'; see decisions)
    s.check('En el párrafo cuarto del artículo 278, después de la frase "consejo de administración", agregar las '
            'palabras "y vigilancia".')
    u.sub("art-278", "consejos de administración", "consejos de administración y vigilancia", para=3)
    # 5. art. 298, penultimate paragraph: 'prejuicio' -> 'perjuicio'
    s.check('En el párrafo penúltimo del artículo 298, sustituir la palabra "prejuicio" por "perjuicio".')
    n = len(u.paras("art-298"))
    u.sub("art-298", "prejuicio", "perjuicio", para=n - 2)
    # 6. art. 380: a paragraph after the fourth
    new = paras_between(s, "Si la persona se encontrare en estado de embriaguez", "de treinta a cuarenta y cinco días.")
    u.insert("art-380", 4, new)
    # 7. art. 415, numeral 4 replaced
    u.set_para("art-415", u.find("art-415", "4. "), qfrom(s, "En el artículo 415, sustitúyase el numeral 4 por el siguiente:"))
    # 8. art. 473, second paragraph replaced
    u.set_para("art-473", 1, qfrom(s, "En el artículo 473, sustitúyase el párrafo segundo por:"))
    # 9. art. 581, last paragraph: the final stop becomes ', cuando el objeto de la infracción sea recursos públicos.'
    add = phrase(s, ", cuando el objeto de la infracción sea recursos públicos.")
    ps = u.paras("art-581")
    if not ps[-1].endswith("."):
        raise SystemExit("581: last paragraph has no final stop")
    ps[-1] = ps[-1][:-1] + add
    u.put("art-581", ps)
    # 10. art. 640, numeral 2, second paragraph replaced
    u.set_para("art-640", u.find("art-640", "2. ") + 1,
               qfrom(s, "Sustitúyase el párrafo segundo del numeral 2 del artículo 640 por el siguiente texto:"))
    # 11. art. 643, numeral 14 removed
    s.check("Elimínese el numeral 14 del artículo 643.")
    u.delete_para("art-643", "14. ")
    # 12. art. 663, numeral 2 replaced
    u.set_para("art-663", u.find("art-663", "2. "),
               qfrom(s, "Sustitúyase el numeral 2 del artículo 663 por el siguiente texto:"))
    # 13. Disposición reformatoria duodécima: 'plazo' -> 'término'
    s.check('En la Disposición Reformatoria Décimo Segunda, sustitúyase la palabra "plazo" por "término".')
    u.sub("disp-reformatoria-12", "plazo", "término")


def drogas_2015_a(u: Units) -> None:
    """Ley Orgánica de Prevención Integral del Fenómeno Socio Económico de las Drogas (Supl. 615, 26-X-2015),
    Disposición reformatoria primera, which its Disposición final applies from publication: arts. 220, 474, 557."""
    s = csrc(S615_2015)
    p = s.paras[s.index("1.- En el número 1 del artículo 220, sustitúyanse los literales a) y b) por los siguientes:")]
    rest = p.split("por los siguientes: ", 1)[1]
    a, b = rest.split(" b) ", 1)
    if not a.startswith("a) "):
        raise SystemExit("220: literals not found")
    u.set_para("art-220", u.find("art-220", "a) "), [a.strip()], count=2)
    u.insert("art-220", u.find("art-220", "a) ") + 1, ["b) " + b.strip()])
    old = "al organismo competente en materia de sustancias catalogadas sujetas a fiscalización"
    new = phrase(s, "a la institución encargada de la administración y gestión inmobiliaria del Estado")
    s.check("En el número seis del artículo 474, sustitúyase la expresión")
    u.sub("art-474", old, new, para="6. ")
    s.check("En el inciso segundo, del número uno del artículo 557, sustitúyase la expresión")
    u.sub("art-557", old, new, para=u.find("art-557", "1. ") + 1)


def drogas_2015_b(u: Units) -> None:
    """The same law, Disposición derogatoria cuarta, in force with the rest of the law ninety days after publication:
    the Code's Disposición reformatoria décimo primera is repealed."""
    s = csrc(S615_2015)
    s.check("Derógase la disposición reformatoria décimo primera del Código Orgánico Integral Penal")
    u.remove("disp-reformatoria-11")


def tierras_2016(u: Units) -> None:
    """Ley Orgánica de Tierras Rurales y Territorios Ancestrales (Supl. 711, 14-III-2016), Disposición reformatoria
    quinta: a numeral 7 after numeral 6 of art. 557. The law sets no vigencia, so it binds from publication."""
    s = csrc(S711_2016)
    new = qfrom(s, "En el artículo 557 del Código Orgánico Integral Penal, incorpórese después del numeral sexto uno "
                   "que diga:")
    u.insert("art-557", u.find("art-557", "6. ") + 1, new)


def lavado_2016(u: Units) -> None:
    """Ley Orgánica de Prevención, Detección y Erradicación del Delito de Lavado de Activos y del Financiamiento de
    Delitos (Segundo Supl. 802, 21-VII-2016), Disposición reformatoria 1: art. 298. In force on publication."""
    s = csrc(S2_802_2016)
    a = "Refórmese el artículo 298 del Código Orgánico Integral Penal de la siguiente manera: a) Sustituir el primer inciso por el siguiente:"
    first = qfrom(s, a)
    ps = u.paras("art-298")
    head = re.match(r"(Artículo 298\.- Defraudación tributaria\.- )", ps[0]).group(1)
    ps[0] = head + first[0]
    u.put("art-298", ps)
    num20 = qfrom(s, "b) Agregar el siguiente numeral a continuación del numeral 19:")
    u.insert("art-298", u.find("art-298", "19. ") + 1, num20)
    s.check('c) En el quinto inciso posterior al numeral 19, sustitúyase "18 y 19" por lo siguiente "18, 19 y 20".')
    u.sub("art-298", "18 y 19", "18, 19 y 20", para="En el caso de los numerales 18 y 19")
    new = qfrom(s, "d) Sustitúyase el antepenúltimo inciso por el siguiente:")
    n = len(u.paras("art-298"))
    u.set_para("art-298", n - 3, new)


_SRC: dict[tuple[str, bool], Src] = {}


def csrc(url: str, drop_overlaps: bool = False) -> Src:
    """One gazette edition as civil/replay.Src paragraphs, with the COIP's hyphenation rule (coip_base.join_broken:
    the vocabulary is the Code's and the edition's own unbroken words). With drop_overlaps, stray text fragments laid
    over the real text blocks are skipped (rotext drop_overlaps), for the editions whose pages carry them."""
    if (url, drop_overlaps) in _SRC:
        return _SRC[(url, drop_overlaps)]
    import coip_base
    raw = rotext.paragraphs(fetch.cached(url), drop_overlaps=drop_overlaps)
    vocab = coip_base.base_vocab() | coip_base.vocabulary(raw)
    s = object.__new__(Src)
    s.url = url
    s.paras = coip_base.join_broken(raw, vocab)
    s.flat = re.sub(r"\s+", " ", "\n".join(s.paras))
    _SRC[(url, drop_overlaps)] = s
    return s


def clean_src(url: str) -> Src:
    return csrc(url, drop_overlaps=True)


def open_quote(src: Src, anchor: str, until: str) -> list[str]:
    """A quotation the act opens after `anchor` and never closes: it runs to the paragraph before the one starting
    with `until` (the act's next provision). A closing quote, if printed at the end, is dropped."""
    i = src.index(anchor)
    p = src.paras[i]
    head = p[p.index(anchor) + len(anchor):].strip()
    j = src.index(until, src.paras[i])
    if not src.paras[j].startswith(until):
        raise SystemExit(f"{until!r} does not start its paragraph")
    block = ([head] if head else []) + src.paras[i + 1:j]
    if not block or not block[0].startswith('"'):
        raise SystemExit(f"no opening quote after {anchor!r}")
    block[0] = block[0][1:].strip()
    block[-1] = re.sub(r'"\s*([.,;]?)$', r"\1", block[-1]).rstrip()
    return block


def quoted_para(src: Src, start: str, after: str | None = None) -> list[str]:
    """The single quoted paragraph beginning with '"' + start (the first one after the paragraph holding `after`)."""
    i0 = src.index(after) + 1 if after else 0
    hits = [p for p in src.paras[i0:] if p.startswith('"' + start)]
    if after and hits:
        hits = hits[:1]
    if len(hits) != 1:
        raise SystemExit(f"{len(hits)} quoted paragraphs start with {start!r}")
    return unquote([hits[0]])


def violencia_mujeres_2018(u: Units) -> None:
    """Ley Orgánica Integral para Prevenir y Erradicar la Violencia contra las Mujeres (Supl. 175, 5-II-2018),
    Disposiciones reformatorias cuarta to séptima and décima; in force on publication (its Disposición final). Its
    quotations open and are never closed; each runs to the next disposición."""
    s = clean_src(S175_2018)
    u.set_unit("art-558-1", open_quote(s, "Agrégase, a continuación del artículo 558 del Código Orgánico Integral Penal, "
                                          "el siguiente artículo:", "QUINTA.-"), label="Art. 558.1")
    u.set_unit("art-078-1", open_quote(s, "A continuación del artículo 78 del Código Orgánico Integral Penal, "
                                          "incorpórase el siguiente artículo:", "SEXTA.-"), label="Art. 78.1")
    u.set_unit("art-157", open_quote(s, "Sustitúyase el artículo 157 del Código Orgánico Integral Penal, por el "
                                        "siguiente:", "SÉPTIMA.-"))
    u.set_unit("art-159", open_quote(s, "Refórmase el artículo 159 del Código Orgánico Integral Penal por el "
                                        "siguiente texto:", "OCTAVA.-"))
    u.set_unit("art-570", open_quote(s, "Refórmase el artículo 570 del Código Orgánico Integral Penal por el "
                                        "siguiente:", "DÉCIMA PRIMERA.-"))


def referendo_2018(u: Units) -> None:
    """Referéndum y consulta popular of 4 February 2018, questions 1 and 4: the annexes' reforms of the COIP, as put
    to the vote by Decreto Ejecutivo 229 (Supl. 133, 4-XII-2017); in force on the publication of the CNE's results
    (Supl. 180, 14-II-2018), as for the Constitution's amendments of the same vote."""
    s = clean_src(S133_2017)
    s.check("Agréguese el número 14 al artículo 60 del Código Orgánico Integral Penal, que disponga:")
    u.insert("art-060", u.find("art-060", "13. ") + 1, quoted_para(s, "14. Inhabilitación para contratar"))
    s.check("Agréguese como segundo inciso en el artículo 68 del Código Orgánico Integral Penal, el siguiente:")
    u.insert("art-068", 1, quoted_para(s, "En el caso de los delitos de peculado"))
    s.check("En el artículo 77 del Código Orgánico Integral Penal incorpórese el siguiente inciso final:")
    u.insert("art-077", u.count("art-077"), quoted_para(s, "Las personas condenadas con sentencia ejecutoriada"))
    pj = "En caso de determinarse responsabilidad de la persona jurídica será sancionada"
    a280 = "En el artículo 280 del Código Orgánico Integral Penal añádase el siguiente inciso final:"
    u.insert("art-280", u.count("art-280"), quoted_para(s, pj, after=a280))
    a285 = "En el artículo 285 del Código Orgánico Integral Penal incorpórese como tercer inciso, el siguiente:"
    u.insert("art-285", 2, quoted_para(s, pj, after=a285))
    s.check("En el artículo 289 del Código Orgánico Integral Penal incorpórese como segundo inciso, el siguiente:")
    u.insert("art-289", 1, quoted_para(s, "En caso de establecerse responsabilidad de personas jurídicas"))
    s.check("Sustitúyase el numeral 4 del artículo 16 del Código Orgánico Integral Penal por el siguiente texto:")
    u.set_para("art-016", u.find("art-016", "4. "), ["4. " + quoted_para(s, "Las infracciones de agresión a un Estado")[0]])
    s.check("Sustitúyase el inciso final del artículo 75 del Código Orgánico Integral Penal por el siguiente texto:")
    u.set_para("art-075", u.count("art-075") - 1, quoted_para(s, "No prescriben las penas determinadas"))


def deporte_2019(u: Units) -> None:
    """Ley Orgánica de Prevención y Sanción de la Violencia en el Deporte (Supl. 478, 30-IV-2019), Disposición
    reformatoria primera: art. 397 replaced (unquoted, up to the next disposición). No vigencia clause: in force on
    publication (Código Civil art. 6)."""
    s = csrc(S478_2019)
    i = s.index("PRIMERA.- Sustitúyase el artículo 397 por el siguiente texto:")
    j = s.index("DISPOSICIONES TRANSITORIAS", s.paras[i])
    new = s.paras[i + 1:j]
    if not new[0].startswith("Artículo 397.-"):
        raise SystemExit("397: replacement not found")
    u.set_unit("art-397", new)


def defensoria_2019(u: Units) -> None:
    """Ley Orgánica de la Defensoría del Pueblo (Supl. 481, 6-V-2019), Disposiciones reformatorias séptima (art. 675,
    first inciso) and octava (a new Disposición general); in force on publication (its Disposición final)."""
    s = csrc(S481_2019)
    new = open_quote(s, "Refórmese el inciso primero del artículo 675 del Código Integral Penal de la siguiente manera:",
                     "OCTAVA.-")
    if len(new) != 1 or not new[0].startswith("Art. 675.- Directorio.-"):
        raise SystemExit("675: unexpected replacement")
    ps = u.paras("art-675")
    ps[0] = new[0]
    u.put("art-675", ps)
    i = s.index("Agrégase una Disposición General al Código Orgánico Integral Penal, que dicte:")
    j = s.index("Durante las visitas, el Mecanismo Nacional", s.paras[i])
    block = s.paras[i + 1:j + 1]
    u.set_unit("disp-general-05", unquote(block), label="Disposición general (quinta)")
    u.u["disp-general-05"]["kind"] = "general"


class Heads:
    """The 'titulos' unit as [heading, first unit after it] pairs, so a heading can be inserted before an article."""

    def __init__(self) -> None:
        import coip_base
        self.lines = [list(h) for h in coip_base.HEAD_NEXT]

    def _write(self, u: Units) -> None:
        u.u["titulos"]["text"] = "".join(h[0] + "\n" for h in self.lines)

    def rename(self, u: Units, old: str, new: str) -> None:
        hits = [h for h in self.lines if h[0] == old]
        if len(hits) != 1:
            raise SystemExit(f"heading {old!r}: {len(hits)} matches")
        hits[0][0] = new
        self._write(u)

    def insert(self, u: Units, text: str, before: str) -> None:
        pos = next((i for i, h in enumerate(self.lines) if order(h[1]) > order(before)), len(self.lines))
        self.lines.insert(pos, [text, before])
        self._write(u)

    def remove(self, u: Units, text: str) -> None:
        hits = [i for i, h in enumerate(self.lines) if h[0] == text]
        if len(hits) != 1:
            raise SystemExit(f"heading {text!r}: {len(hits)} matches")
        del self.lines[hits[0]]
        self._write(u)


HEADS: Heads | None = None


def reformatoria_coip_2019(u: Units) -> None:
    """Ley Orgánica Reformatoria al Código Orgánico Integral Penal (Supl. 107, 24-XII-2019), arts. 1-121; in force
    180 days after publication (its Disposición final). See coip/s107_2019.py."""
    import s107_2019
    s107_2019.apply(u, clean_src(S107_2019), HEADS)


def cc_34_19_in_21(u: Units) -> None:
    """Corte Constitucional, sentencia 34-19-IN/21 (Edición Constitucional 194, 29-VI-2021): the phrase 'en una
    mujer que padezca de discapacidad mental' of art. 150 numeral 2 is unconstitutional."""
    s = csrc(EC194_2021)
    s.check('Declarar la inconstitucionalidad por el fondo del artículo 150 numeral 2 del Código Orgánico Integral '
            'Penal en la frase "en una mujer que padezca de discapacidad mental"')
    u.drop("art-150", " en una mujer que padezca de discapacidad mental", para="2. ")


def cc_11_ruling_75(u: Units) -> None:
    """Corte Constitucional (Edición Constitucional 261, 14-I-2022): 'máximo' and 'el tipo penal' of art. 75
    numeral 1 are unconstitutional; the ruling states how the numeral reads until the Asamblea legislates."""
    s = csrc(EC261_2022)
    s.check('Declarar la inconstitucionalidad de las palabras "máximo" y "el tipo penal" del artículo 75 (1)')
    i = s.index("El artículo 75 (1) del COIP, hasta que la Asamblea Nacional no adecúe la norma a esta sentencia, dirá:")
    new = s.paras[i + 2]
    if not new.startswith("1. Las penas restrictivas de libertad prescribirán en el tiempo de la pena"):
        raise SystemExit("EC 261: reading of art. 75 (1) not found")
    u.set_para("art-075", u.find("art-075", "1. "), [new])


def cc_53_20_in_21(u: Units) -> None:
    """Corte Constitucional, sentencia 53-20-IN/21 (Edición Constitucional 267, 25-I-2022): art. 47 numeral 20 is
    unconstitutional."""
    s = csrc(EC267_2022)
    s.check("Declarar la inconstitucionalidad por el fondo artículo 47, numeral 20, del Código Orgánico Integral Penal.")
    u.delete_para("art-047", "20. ")


# footnote calls the text layer prints glued to words inside a ruling's quoted reading
FOOTNOTE_CALLS = {"EC268_2022": [("coerción70;", "coerción;"), ("consentimiento71.", "consentimiento.")]}


def cc_13_ruling_175(u: Units) -> None:
    """Corte Constitucional (Edición Constitucional 268, 28-I-2022): additive constitutionality of art. 175
    numeral 5, which 'en adelante se leerá' as the ruling prints it (three paragraphs; footnote calls removed)."""
    s = csrc(EC268_2022)
    i = s.index("declarar la constitucionalidad aditiva del artículo 175 numeral 5 del Código Orgánico Integral Penal, "
                "el cual en adelante se leerá de la siguiente forma:")
    new = s.paras[i + 2:i + 5]
    if not (new[0].startswith("5. En los delitos sexuales") and new[2].startswith("a) El consentimiento")):
        raise SystemExit("EC 268: reading not found")
    for a, b in FOOTNOTE_CALLS["EC268_2022"]:
        if a not in new[2]:
            raise SystemExit(f"EC 268: {a!r} not found")
        new[2] = new[2].replace(a, b)
    a = u.find("art-175", "5. ")
    u.set_para("art-175", a, new)


def cc_77_ruling_476(u: Units) -> None:
    """Corte Constitucional (Edición Constitucional 20, 16-III-2022): additive constitutionality of art. 476, first
    inciso and numeral 6, which 'dirá' as the ruling prints them (its markers '(...)' and '(Las negritas se
    incluyen)' are not part of the reading)."""
    s = csrc(EC20_2022)
    i = s.index("Declarar la constitucionalidad aditiva del primer inciso del artículo 476")
    first = s.paras[i + 1]
    tail = " (...) (Las negritas se incluyen)"
    if not (first.startswith("Art. 476.- Interceptación") and first.endswith(tail)):
        raise SystemExit("EC 20: reading of the first inciso")
    u.set_para("art-476", 0, [first[:-len(tail)]])
    j = s.index("Declarar la constitucionalidad aditiva del numeral 6 del artículo 476")
    six, added = s.paras[j + 1], s.paras[j + 2]
    if not six.startswith("(...) 6. ") or not added.endswith(" (Las negritas se incluyen)"):
        raise SystemExit("EC 20: reading of numeral 6")
    k = u.find("art-476", "6. ")
    if u.paras("art-476")[k] != six[len("(...) "):]:
        raise SystemExit("EC 20: numeral 6 does not match the Code's")
    u.insert("art-476", k + 1, [added[:-len(" (Las negritas se incluyen)")]])


def economia_campesina_2023(u: Units) -> None:
    """Ley Orgánica para la Defensa y Desarrollo de la Economía Familiar Campesina (Primer Supl. 222, 4-I-2023),
    Disposición reformatoria cuarta: numeral 4 of art. 308; in force on publication (its Disposición final)."""
    s = csrc(S222_2023)
    s.check("CUARTA.- Incorpórese como numeral 4 del artículo 308 del Código Orgánico Integral Penal el siguiente texto:")
    new = quoted_para(s, "4. La persona que, de manera habitual")
    u.insert("art-308", u.find("art-308", "3. ") + 1, new)


def order(key: str) -> tuple:
    m = re.match(r"art-(\d{3})(?:-(\w+))?$", key)
    if m:
        # a numeric suffix sorts as a number (art-477-2 before art-477-10); single digits sort as before
        sfx = m.group(2) or ""
        return (1, int(m.group(1)), sfx.zfill(3) if sfx.isdigit() else sfx)
    for i, p in enumerate(("disp-general", "disp-transitoria", "disp-reformatoria", "disp-derogatoria", "disp-final",
                           "titulos")):
        if key.startswith(p):
            return (2 + i, 0, key)
    return (9, 0, key)


def sha_of(url: str) -> str:
    return hashlib.sha256(fetch.cached(url).read_bytes()).hexdigest()


IMAGE_ONLY = ("NOT APPLIED here: the Registro Oficial edition that publishes it is page images without a text layer, "
              "and this repository does not OCR. Its wording is missing from the files named in this commit; they "
              "keep the earlier text (provisions named from the editorial indexes: Ediciones Legales 2021, Lexis 2023).")

IMAGE_ONLY_2026 = ("NOT APPLIED here: the Registro Oficial edition that publishes it is page images without a text "
                   "layer, and this repository does not OCR. Its wording is missing from the files named in this "
                   "commit; they keep the earlier text (provisions named from the editorial indexes: Ediciones Legales "
                   "2026, Andina Ediciones 2026).")


def termino_days(published: str, days: int, holidays: tuple[str, ...]) -> str:
    """In force after a término of `days` días hábiles counted from publication (Saturdays, Sundays and the given
    national holidays not counted, the publication day not counted): the day after the last of them, as for
    plazo_days."""
    d = dt.date.fromisoformat(published)
    n = 0
    while n < days:
        d += dt.timedelta(days=1)
        if d.weekday() < 5 and d.isoformat() not in holidays:
            n += 1
    return (d + dt.timedelta(days=1)).isoformat()


def import_reforms():
    import reforms_2023_2026
    return reforms_2023_2026


def later(name: str):
    """Edit function defined in coip/reforms_2023_2026.py (imported when the step runs)."""
    def edit(u: Units) -> None:
        getattr(import_reforms(), name)(u)
    edit.__name__ = name
    return edit


LAWS: dict[str, dict] = {
    "comf-2014": dict(label="Código Orgánico Monetario y Financiero", kind="law", enacted="2014-07-24",
                      published="2014-09-12", url=S2_332_2014,
                      title="Código Orgánico Monetario y Financiero, Disposición reformatoria trigésima séptima "
                            "(Registro Oficial, Segundo Suplemento 332, 12-IX-2014)"),
    "reformatoria-coip-2015": dict(label="Ley Orgánica Reformatoria del COIP (2015)", kind="law",
                                   enacted="2015-09-24", published="2015-09-30", url=S3_598_2015,
                                   title="Ley Orgánica Reformatoria del Código Orgánico Integral Penal (Registro "
                                         "Oficial, Tercer Suplemento 598, 30-IX-2015)"),
    "ley-drogas-2015": dict(label="Ley Orgánica de Drogas (2015)", kind="law", enacted="2015-10-01",
                            published="2015-10-26", url=S615_2015,
                            title="Ley Orgánica de Prevención Integral del Fenómeno Socio Económico de las Drogas y de "
                                  "Regulación y Control del Uso de Sustancias Catalogadas Sujetas a Fiscalización "
                                  "(Registro Oficial, Suplemento 615, 26-X-2015)"),
    "ley-tierras-2016": dict(label="Ley Orgánica de Tierras Rurales (2016)", kind="law", enacted="2016-03-03",
                             published="2016-03-14", url=S711_2016,
                             title="Ley Orgánica de Tierras Rurales y Territorios Ancestrales (Registro Oficial, "
                                   "Suplemento 711, 14-III-2016)"),
    "ley-lavado-2016": dict(label="Ley Orgánica contra el Lavado de Activos (2016)", kind="law", enacted="2016-07-13",
                            published="2016-07-21", url=S2_802_2016,
                            title="Ley Orgánica de Prevención, Detección y Erradicación del Delito de Lavado de Activos "
                                  "y del Financiamiento de Delitos (Registro Oficial, Segundo Suplemento 802, "
                                  "21-VII-2016)"),
    "ley-reactivacion-2017": dict(label="Ley Orgánica para la Reactivación de la Economía (2017)", kind="law",
                                  published="2017-12-29", url=S2_150_2017, note=IMAGE_ONLY,
                                  title="Ley Orgánica para la Reactivación de la Economía, Fortalecimiento de la "
                                        "Dolarización y Modernización de la Gestión Financiera (Registro Oficial, "
                                        "Segundo Suplemento 150, 29-XII-2017): art. 299, first inciso. NOT APPLIED "
                                        "(image-only edition)"),
    "ley-violencia-mujeres-2018": dict(label="Ley Orgánica contra la Violencia hacia las Mujeres (2018)", kind="law",
                                       enacted="2018-01-23", published="2018-02-05", url=S175_2018,
                                       title="Ley Orgánica Integral para Prevenir y Erradicar la Violencia contra las "
                                             "Mujeres (Registro Oficial, Suplemento 175, 5-II-2018)"),
    "referendo-2018": dict(label="Referéndum de 2018", kind="referendum", enacted="2018-02-04", published="2018-02-14",
                           url=S180_2018,
                           title="Referéndum y consulta popular de 4 de febrero de 2018, preguntas 1 y 4 (anexos del "
                                 "Decreto Ejecutivo 229, RO Supl. 133 de 4-XII-2017; resultados del CNE, RO Supl. 180 "
                                 "de 14-II-2018)"),
    "ley-deporte-2019": dict(label="Ley Orgánica contra la Violencia en el Deporte (2019)", kind="law",
                             enacted="2019-03-27", published="2019-04-30", url=S478_2019,
                             title="Ley Orgánica de Prevención y Sanción de la Violencia en el Deporte (Registro "
                                   "Oficial, Suplemento 478, 30-IV-2019)"),
    "ley-defensoria-2019": dict(label="Ley Orgánica de la Defensoría del Pueblo (2019)", kind="law",
                                published="2019-05-06", url=S481_2019,
                                title="Ley Orgánica de la Defensoría del Pueblo (Registro Oficial, Suplemento 481, "
                                      "6-V-2019)"),
    "cc-ec90-2019": dict(label="Corte Constitucional, Edición Constitucional 90 (2019)", kind="court",
                         published="2019-06-03", url=EC90_2019, note=IMAGE_ONLY,
                         title="Corte Constitucional, sentencia publicada en la Edición Constitucional 90 (3-VI-2019) "
                               "que declara la inconstitucionalidad parcial del art. 202. NOT APPLIED (image-only "
                               "edition)"),
    "cc-ec6-2019": dict(label="Corte Constitucional, sentencia 5-13-IN/19", kind="court", published="2019-08-15",
                        url=EC6_2019, note=IMAGE_ONLY,
                        title="Corte Constitucional, sentencia 5-13-IN/19 (Edición Constitucional 6, 15-VIII-2019): "
                              "inconstitucionalidad del último inciso del art. 581. NOT APPLIED (image-only edition)"),
    "cc-ec21-2019": dict(label="Corte Constitucional, Edición Constitucional 21 (2019)", kind="court",
                         published="2019-11-13", url=EC21_2019, note=IMAGE_ONLY,
                         title="Corte Constitucional, sentencia publicada en la Edición Constitucional 21 (13-XI-2019): "
                               "constitucionalidad condicionada aditiva del art. 653. NOT APPLIED (image-only edition)"),
    "reformatoria-coip-2019": dict(label="Ley Orgánica Reformatoria del COIP (2019)", kind="law", enacted="2019-12-17",
                                   published="2019-12-24", url=S107_2019,
                                   title="Ley Orgánica Reformatoria al Código Orgánico Integral Penal (Registro "
                                         "Oficial, Suplemento 107, 24-XII-2019)"),
    "ley-movilidad-humana-2021": dict(label="Ley Reformatoria de la Ley Orgánica de Movilidad Humana (2021)",
                                      kind="law", published="2021-02-05", url=S3_386_2021, note=IMAGE_ONLY,
                                      title="Ley Orgánica Reformatoria de la Ley Orgánica de Movilidad Humana "
                                            "(Registro Oficial, Tercer Suplemento 386, 5-II-2021): art. 91, first "
                                            "inciso. NOT APPLIED (image-only edition)"),
    "reformatoria-coip-2021": dict(label="Ley Reformatoria del COIP en materia anticorrupción (2021)", kind="law",
                                   published="2021-02-17", url=S2_392_2021, note=IMAGE_ONLY,
                                   title="Ley Orgánica Reformatoria del Código Orgánico Integral Penal en materia "
                                         "anticorrupción (Registro Oficial, Segundo Suplemento 392, 17-II-2021): arts. "
                                         "45, 47, 49, 60, 68, 69, 77, 270, 278, 280, 281, 285, 286, 430.1, 430.2, 536, "
                                         "581, 630, 698, 699 and new arts. 294.1, 320.1, 422.1, 550.1, 581.1. NOT "
                                         "APPLIED (image-only edition)"),
    "ley-extincion-dominio-2021": dict(label="Ley Orgánica de Extinción de Dominio", kind="law",
                                       published="2021-05-14", url=S5_452_2021, note=IMAGE_ONLY,
                                       title="Ley Orgánica de Extinción de Dominio (Registro Oficial, Quinto "
                                             "Suplemento 452, 14-V-2021): art. 452. NOT APPLIED (image-only edition)"),
    "cc-34-19-in-21": dict(label="Sentencia 34-19-IN/21", kind="court", enacted="2021-04-28", published="2021-06-29",
                           url=EC194_2021,
                           title="Corte Constitucional, sentencia 34-19-IN/21 y acumulados (Edición Constitucional "
                                 "194, 29-VI-2021): inconstitucionalidad de una frase del art. 150 numeral 2"),
    "ley-transito-2021": dict(label="Ley Reformatoria de la Ley de Tránsito (2021)", kind="law", published="2021-08-10",
                              url=S5_512_2021, note=IMAGE_ONLY,
                              title="Ley Orgánica Reformatoria de la Ley Orgánica de Transporte Terrestre, Tránsito y "
                                    "Seguridad Vial (Registro Oficial, Quinto Suplemento 512, 10-VIII-2021): arts. 17, "
                                    "388 to 392, 404. NOT APPLIED (image-only edition)"),
    "ley-comercio-ilicito-2021": dict(label="Ley contra el Comercio Ilícito (2021)", kind="law", published="2021-08-27",
                                      url=S5_525_2021, note=IMAGE_ONLY,
                                      title="Ley Orgánica que reforma diversos cuerpos legales para reforzar la "
                                            "prevención y el combate al comercio ilícito (Registro Oficial, Quinto "
                                            "Suplemento 525, 27-VIII-2021): arts. 60, 65, 208 A (and new 208 B, 208 C), "
                                            "267, 299, 300, 301, 303, 317 and the final provisions. NOT APPLIED "
                                            "(image-only edition)"),
    "reformatoria-coip-violencia-digital-2021": dict(
        label="Ley Reformatoria del COIP sobre violencia sexual digital (2021)", kind="law", published="2021-08-30",
        url=S4_526_2021, note=IMAGE_ONLY,
        title="Ley Orgánica Reformatoria del Código Orgánico Integral Penal para Prevenir y Combatir la Violencia "
              "Sexual Digital y Fortalecer la Lucha contra los Delitos Informáticos (Registro Oficial, Cuarto "
              "Suplemento 526, 30-VIII-2021): arts. 47, 103, 157, 166, 169, 170, 171, 175, 179, 230, 232, 234, 396, "
              "497 and new arts. 154.2, 154.3, 172.1, 234.1 to 234.4, 477.1. NOT APPLIED (image-only edition)"),
    "cc-8-20-cn-21": dict(label="Sentencia 8-20-CN/21", kind="court", published="2021-10-13", url=EC222_2021,
                          note=("NOT APPLIED here: the ruling strikes the words 'en las infracciones sancionadas con "
                                "pena privativa de libertad superior a cinco años, ni' from the first inciso of art. "
                                "536 as worded by the anticorruption reform of February 2021, which this record could "
                                "not apply (image-only edition); the words it strikes are not in this record's text."),
                          title="Corte Constitucional, sentencia 8-20-CN/21 (Edición Constitucional 222, 13-X-2021): "
                                "inconstitucionalidad de una frase del art. 536. NOT APPLIED (it strikes words of a "
                                "reform this record could not apply)"),
    "cc-ec261-2022": dict(label="Corte Constitucional, Edición Constitucional 261 (2022)", kind="court",
                          published="2022-01-14", url=EC261_2022,
                          title="Corte Constitucional, sentencia de consulta de norma sobre el art. 75 (1) (Edición "
                                "Constitucional 261, 14-I-2022)"),
    "cc-53-20-in-21": dict(label="Sentencia 53-20-IN/21", kind="court", published="2022-01-25", url=EC267_2022,
                           title="Corte Constitucional, sentencia 53-20-IN/21 (Edición Constitucional 267, 25-I-2022): "
                                 "inconstitucionalidad del art. 47 numeral 20"),
    "cc-ec268-2022": dict(label="Corte Constitucional, Edición Constitucional 268 (2022)", kind="court",
                          published="2022-01-28", url=EC268_2022,
                          title="Corte Constitucional, sentencia de consulta de norma sobre el art. 175 numeral 5 "
                                "(Edición Constitucional 268, 28-I-2022): constitucionalidad aditiva"),
    "cc-ec20-2022": dict(label="Corte Constitucional, Edición Constitucional 20 (2022)", kind="court",
                         published="2022-03-16", url=EC20_2022,
                         title="Corte Constitucional, sentencia sobre el art. 476 (Edición Constitucional 20, "
                               "16-III-2022): constitucionalidad aditiva del primer inciso y del numeral 6"),
    "ley-uso-fuerza-2022": dict(label="Ley Orgánica que regula el Uso Legítimo de la Fuerza (2022)", kind="law",
                                published="2022-08-22", url=S3_131_2022, note=IMAGE_ONLY,
                                title="Ley Orgánica que regula el Uso Legítimo de la Fuerza (Registro Oficial, Tercer "
                                      "Suplemento 131, 22-VIII-2022): arts. 30.1, 47, 274, 275, 293, 537, 685, 686 and "
                                      "new arts. 30.2, 533.1. NOT APPLIED (image-only edition)"),
    "ley-economia-campesina-2023": dict(label="Ley de la Economía Familiar Campesina (2023)", kind="law",
                                        published="2023-01-04", url=S222_2023,
                                        title="Ley Orgánica para la Defensa y Desarrollo de la Economía Familiar "
                                              "Campesina (Registro Oficial, Suplemento 222, 4-I-2023)"),
    # ---- 2023 to 2026
    "ley-seguridad-integral-2023": dict(
        label="Ley Reformatoria para la Seguridad Integral (2023)", kind="law",
        published="2023-03-29", url=S279_2023,
        title="Ley Orgánica Reformatoria a Varios Cuerpos Legales para el Fortalecimiento de las Capacidades "
              "Institucionales y la Seguridad Integral (Registro Oficial, Suplemento 279, 29-III-2023), arts. 38 to 126"),
    "ley-salud-mental-2024": dict(
        label="Ley Orgánica de Salud Mental", kind="law", published="2024-01-05", url=S471_2024,
        note=IMAGE_ONLY_2026,
        title="Ley Orgánica de Salud Mental (Registro Oficial, Suplemento 471, 5-I-2024), Disposición reformatoria "
              "primera: art. 76. NOT APPLIED (image-only edition)"),
    "ley-ahorro-monetizacion-2024": dict(
        label="Ley Orgánica para el Ahorro y la Monetización de Recursos", kind="law", published="2024-02-09",
        url=S2_496_2024, note=IMAGE_ONLY_2026,
        title="Ley Orgánica para el Ahorro y la Monetización de Recursos Económicos para el Financiamiento de la Lucha "
              "contra la Corrupción (Registro Oficial, Segundo Suplemento 496, 9-II-2024), Disposición reformatoria "
              "segunda: arts. 69 and 443. NOT APPLIED (image-only edition)"),
    "cc-61-18-in-23": dict(
        label="Sentencia 61-18-IN/23", kind="court", published="2024-02-26", url=EC319_2024,
        title="Corte Constitucional, sentencia 61-18-IN/23 (Edición Constitucional 319, 26-II-2024): "
              "inconstitucionalidad de la frase 'pena privativa de libertad de cinco a quince días' del art. 383"),
    "ley-victimas-femicidio-2024": dict(
        label="Ley Orgánica de Reparación a Familiares de Víctimas de Femicidio", kind="law", published="2024-06-27",
        url=S3_588_2024, note=IMAGE_ONLY_2026,
        title="Ley Orgánica de Acompañamiento y Reparación Transformadora e Integral a Hijas, Hijos, Madres, Padres y "
              "demás familiares de víctimas de femicidio y otras muertes violentas por razones de género (Registro "
              "Oficial, Tercer Suplemento 588, 27-VI-2024), Disposición reformatoria primera: arts. 78.1, 441, 520, "
              "558.1, 570 and a new art. 77.1. NOT APPLIED (image-only edition)"),
    "ley-consulta-popular-2024": dict(
        label="Ley para la Aplicación de la Consulta Popular de 2024", kind="law", published="2024-07-12",
        url=S599_2024, note=IMAGE_ONLY_2026,
        title="Ley Orgánica para la Aplicación de la Consulta Popular y Referéndum del 21 de abril de 2024 (Registro "
              "Oficial, Suplemento 599, 12-VII-2024), which carries out the referendum's penal questions: arts. 92, "
              "140, 143, 162, 260, 317, 362, 366, 367, 369, 698, 699 and new arts. 360.1, 474.2, 474.3, 474.4. NOT "
              "APPLIED (image-only edition)"),
    "ley-lavado-2024": dict(
        label="Ley Orgánica contra el Lavado de Activos (2024)", kind="law", published="2024-07-29", url=S4_610_2024,
        title="Ley Orgánica de Prevención, Detección y Combate del Delito de Lavado de Activos y de la Financiación de "
              "Otros Delitos (Registro Oficial, Cuarto Suplemento 610, 29-VII-2024), Disposición reformatoria primera; "
              "in force a year after publication"),
    "dl-477-2024": dict(
        label="Decreto Ley 477 (2024)", kind="decree", published="2024-12-10", url=S5_700_2024, note=IMAGE_ONLY_2026,
        title="Ley Orgánica para la Mejora Recaudatoria a través del Combate al Lavado de Activos, Decreto Ley 477 "
              "(Registro Oficial, Quinto Suplemento 700, 10-XII-2024): arts. 69 and 552. NOT APPLIED (image-only "
              "edition)"),
    "cc-94-24-in-25": dict(
        label="Sentencia 94-24-IN/25", kind="court", published="2025-03-27", url=EC8_2025,
        note=("Declares Decreto Ley 477 of 2024 unconstitutional in form, with retroactive effect. This record could "
              "not apply that decree (image-only edition), so the ruling changes none of the words here."),
        title="Corte Constitucional, sentencia 94-24-IN/25 (Edición Constitucional 8, 27-III-2025): "
              "inconstitucionalidad por la forma, con efectos retroactivos, del Decreto Ley 477"),
    "cc-49-21-cn-25": dict(
        label="Sentencia 49-21-CN/25", kind="court", published="2025-04-02", url=EC15_2025,
        title="Corte Constitucional, sentencia 49-21-CN/25 (Edición Constitucional 15, 2-IV-2025): "
              "inconstitucionalidad de una frase del último inciso del art. 536"),
    "ley-transito-2025": dict(
        label="Ley Reformatoria de la Ley de Tránsito (2025)", kind="law", published="2025-05-14", url=S5_38_2025,
        note=IMAGE_ONLY_2026,
        title="Ley Orgánica Reformatoria a la Ley Orgánica de Transporte Terrestre, Tránsito y Seguridad Vial (Registro "
              "Oficial, Quinto Suplemento 38, 14-V-2025), Disposición reformatoria primera: art. 388. NOT APPLIED "
              "(image-only edition)"),
    "ley-solidaridad-2025": dict(
        label="Ley Orgánica de Solidaridad Nacional (2025)", kind="law", published="2025-06-10",
        url=S6_56_2025,
        title="Ley Orgánica de Solidaridad Nacional (Registro Oficial, Sexto Suplemento 56, 10-VI-2025), Disposición "
              "reformatoria segunda and Disposición derogatoria segunda; annulled with retroactive effect by sentencia "
              "51-25-IN/25"),
    "ley-integridad-2025": dict(
        label="Ley Orgánica de Integridad Pública (2025)", kind="law", published="2025-06-26",
        url=S3_68_2025,
        title="Ley Orgánica de Integridad Pública (Registro Oficial, Tercer Suplemento 68, 26-VI-2025), Disposición "
              "reformatoria segunda and Disposición derogatoria tercera; its penal reforms annulled with retroactive "
              "effect by sentencia 52-25-IN/25"),
    "cc-52-25-in-25": dict(
        label="Sentencia 52-25-IN/25", kind="court", published="2025-10-03", url=EC96_2025,
        restores="ley-integridad-2025",
        title="Corte Constitucional, sentencia 52-25-IN/25 y acumulados (Edición Constitucional 96, 3-X-2025): "
              "inconstitucionalidad por la forma de la Ley Orgánica de Integridad Pública, con efectos retroactivos, "
              "entre otras en materia penal y de ejecución de penas"),
    "cc-51-25-in-25": dict(
        label="Sentencia 51-25-IN/25", kind="court", published="2025-10-03", url=EC96_2025,
        restores="ley-solidaridad-2025",
        title="Corte Constitucional, sentencia 51-25-IN/25 y acumulados (Edición Constitucional 96, 3-X-2025): "
              "inconstitucionalidad por la forma de la totalidad de la Ley Orgánica de Solidaridad Nacional, con efecto "
              "retroactivo a partir de su publicación"),
    "ley-movilidad-humana-2025": dict(
        label="Ley Reformatoria de la Ley Orgánica de Movilidad Humana (2025)", kind="law", published="2025-10-24",
        url=S7_151_2025, note=IMAGE_ONLY_2026,
        title="Ley Orgánica Reformatoria a la Ley Orgánica de Movilidad Humana (Registro Oficial, Séptimo Suplemento "
              "151, 24-X-2025), Disposición reformatoria primera: arts. 12, 61, 667.1, 729, 730 and a new art. 633.1. "
              "NOT APPLIED (image-only edition)"),
    "ley-penitenciaria-2026": dict(
        label="Ley Reformatoria del Sistema Penitenciario (2026)", kind="law", published="2026-04-29",
        url=S4_275_2026,
        title="Ley Orgánica Reformatoria para el Fortalecimiento del Sistema Penitenciario (Registro Oficial, Cuarto "
              "Suplemento 275, 29-IV-2026), arts. 7 to 24"),
    "ley-ciberseguridad-2026": dict(
        label="Ley Orgánica de Ciberseguridad (2026)", kind="law", published="2026-05-22", url=S5_290_2026,
        title="Ley Orgánica para el Fortalecimiento de la Ciberseguridad (Registro Oficial, Quinto Suplemento 290, "
              "22-V-2026), art. 11"),
    "ley-uniformes-2026": dict(
        label="Ley contra el Uso Delictivo de Uniformes (2026)", kind="law", published="2026-07-01", url=S5_316_2026,
        note=IMAGE_ONLY_2026,
        title="Ley Orgánica Reformatoria para Prevenir y Sancionar el Uso Delictivo de Uniformes, Insignias y "
              "Distintivos Institucionales para el Fortalecimiento de la Seguridad Pública (Registro Oficial, Quinto "
              "Suplemento 316, 1-VII-2026), arts. 1 to 3: arts. 47, 69 and new arts. 362.1, 362.2. NOT APPLIED "
              "(image-only edition)"),
    "ley-extradicion-2026": dict(
        label="Ley Orgánica de Extradición (2026)", kind="law", published="2026-08-07", url=S5_343_2026,
        note=IMAGE_ONLY_2026,
        title="Ley Orgánica de Extradición (Registro Oficial, Quinto Suplemento 343, 7-VIII-2026), Disposición "
              "reformatoria segunda: art. 541. NOT APPLIED (image-only edition)"),
}

# (law, in-force day, edit function, or the list of provisions a not-applied act concerns)
STEPS: list[tuple] = [
    ("comf-2014", "2014-09-12", comf_2014),
    ("reformatoria-coip-2015", "2015-09-30", reformatoria_coip_2015),
    ("ley-drogas-2015", "2015-10-26", drogas_2015_a),
    ("ley-drogas-2015", plazo_days("2015-10-26", 90), drogas_2015_b),
    ("ley-tierras-2016", "2016-03-14", tierras_2016),
    ("ley-lavado-2016", "2016-07-21", lavado_2016),
    ("ley-reactivacion-2017", "2017-12-29", ["art-299"]),
    ("ley-violencia-mujeres-2018", "2018-02-05", violencia_mujeres_2018),
    ("referendo-2018", "2018-02-14", referendo_2018),
    ("ley-deporte-2019", "2019-04-30", deporte_2019),
    ("ley-defensoria-2019", "2019-05-06", defensoria_2019),
    ("cc-ec90-2019", "2019-06-03", ["art-202"]),
    ("cc-ec6-2019", "2019-08-15", ["art-581"]),
    ("cc-ec21-2019", "2019-11-13", ["art-653"]),
    ("reformatoria-coip-2019", plazo_days("2019-12-24", 180), reformatoria_coip_2019),
    ("ley-movilidad-humana-2021", "2021-02-05", ["art-091"]),
    ("reformatoria-coip-2021", "2021-02-17",
     ["art-045", "art-047", "art-049", "art-060", "art-068", "art-069", "art-077", "art-270", "art-278", "art-280",
      "art-281", "art-285", "art-286", "art-430-1", "art-430-2", "art-536", "art-581", "art-630", "art-698",
      "art-699"]),
    ("ley-extincion-dominio-2021", "2021-05-14", ["art-452"]),
    ("cc-34-19-in-21", "2021-06-29", cc_34_19_in_21),
    ("ley-transito-2021", "2021-08-10", ["art-017", "art-388", "art-389", "art-390", "art-391", "art-392", "art-404"]),
    ("ley-comercio-ilicito-2021", "2021-08-27",
     ["art-060", "art-065", "art-208-a", "art-267", "art-299", "art-300", "art-301", "art-303", "art-317"]),
    ("reformatoria-coip-violencia-digital-2021", "2021-08-30",
     ["art-047", "art-103", "art-157", "art-166", "art-169", "art-170", "art-171", "art-175", "art-179", "art-230",
      "art-232", "art-234", "art-396", "art-497"]),
    ("cc-8-20-cn-21", "2021-10-13", ["art-536"]),
    ("cc-ec261-2022", "2022-01-14", cc_11_ruling_75),
    ("cc-53-20-in-21", "2022-01-25", cc_53_20_in_21),
    ("cc-ec268-2022", "2022-01-28", cc_13_ruling_175),
    ("cc-ec20-2022", "2022-03-16", cc_77_ruling_476),
    ("ley-uso-fuerza-2022", "2022-08-22",
     ["art-030-1", "art-047", "art-274", "art-275", "art-293", "art-537", "art-685", "art-686"]),
    ("ley-economia-campesina-2023", "2023-01-04", economia_campesina_2023),
    # ---- 2023 to 2026
    # Disposición transitoria séptima: the COIP reforms in force 'en el término de treinta (30) días' after
    # publication: 30 días hábiles (holidays in the span: Viernes Santo 7-IV-2023 and 1-V-2023)
    ("ley-seguridad-integral-2023", termino_days("2023-03-29", 30, ("2023-04-07", "2023-05-01")),
     later("seguridad_integral_2023")),
    ("ley-salud-mental-2024", "2024-01-05", ["art-076"]),
    ("ley-ahorro-monetizacion-2024", "2024-02-09", ["art-069", "art-443"]),
    ("cc-61-18-in-23", "2024-02-26", later("cc_61_18_in_23")),
    ("ley-victimas-femicidio-2024", "2024-06-27", ["art-078-1", "art-441", "art-520", "art-558-1", "art-570"]),
    ("ley-consulta-popular-2024", "2024-07-12",
     ["art-092", "art-140", "art-143", "art-162", "art-260", "art-317", "art-362", "art-366", "art-367", "art-369",
      "art-698", "art-699"]),
    ("dl-477-2024", "2024-12-10", ["art-069", "art-552"]),
    ("cc-94-24-in-25", "2025-03-27", ["art-069", "art-552"]),
    ("cc-49-21-cn-25", "2025-04-02", later("cc_49_21_cn_25")),
    ("ley-transito-2025", "2025-05-14", ["art-388"]),
    ("ley-solidaridad-2025", "2025-06-10", later("solidaridad_2025")),
    ("ley-integridad-2025", "2025-06-26", later("integridad_2025")),
    # its Disposición final: in force 'en el plazo de un año posterior a su publicación'; Código Civil art. 33: the
    # year ends on 29-VII-2025, and the act binds from the next day
    ("ley-lavado-2024", (dt.date.fromisoformat(plazo_months("2024-07-29", 12)) + dt.timedelta(days=1)).isoformat(),
     later("lavado_2024")),
    ("cc-52-25-in-25", "2025-10-03", lambda u: restore_law("ley-integridad-2025")(u)),
    ("cc-51-25-in-25", "2025-10-03", lambda u: restore_law("ley-solidaridad-2025")(u)),
    ("ley-movilidad-humana-2025", "2025-10-24", ["art-012", "art-061", "art-667-1", "art-729", "art-730"]),
    ("ley-penitenciaria-2026", "2026-04-29", later("penitenciario_2026")),
    ("ley-ciberseguridad-2026", "2026-05-22", later("ciberseguridad_2026")),
    ("ley-uniformes-2026", "2026-07-01", ["art-047", "art-069"]),
    ("ley-extradicion-2026", "2026-08-07", ["art-541"]),
]


# Provisions whose text in this record is not the law in force: an act this record could not apply (image-only
# edition) amended them, and no applied act has since replaced them whole. A later act's partial amendment of such a
# provision (a numeral, an inciso, a phrase) is not applied either: it would graft new words onto wording that was
# no longer law. Acts after 2023 consult it through editable(); replay() keeps it current.
STALE: set[str] = set()
# law -> (units, headings, stale set) just before the law's first step, and law -> keys its steps changed: what a
# ruling that annuls a law with retroactive effect restores (restore_law)
BEFORE: dict[str, tuple] = {}
CHANGED: dict[str, set[str]] = {}

PARTLY = ("{} here: an earlier reform this record could not apply (image-only edition) had already "
          "amended {}, so this act's partial amendment of {} is not applied either; {} the earlier text, which is not "
          "the law from this date.")


def editable(u: Units, key: str) -> bool:
    """True if `key` may take a partial amendment; otherwise the act is credited to it as not applied."""
    if key in STALE:
        u.skipped.append(key)
        return False
    return True


def fresh(u: Units, key: str) -> None:
    """`key` was replaced whole (or added) from an applied act: its text is the law again."""
    u.fresh.add(key)


def restore_law(law: str):
    """Edit function for a ruling that annuls `law` with retroactive effect: every provision the law's steps changed
    goes back to its text just before the law, headings included."""
    def edit(u: Units) -> None:
        units, heads, stale = BEFORE[law]
        for k in sorted(CHANGED[law], key=order):
            if k in units:
                u.u[k] = json.loads(json.dumps(units[k]))
            else:
                u.u.pop(k, None)
            (u.restale if k in stale else u.fresh).add(k)
        if "titulos" in CHANGED[law]:
            HEADS.lines = [list(h) for h in heads]
        u.note = (f"The ruling annuls the Code's reforms by the {LAWS[law]['label']} with retroactive effect from "
                  f"that law's publication. This record keeps the wording as published and in force until the "
                  f"ruling's publication, and restores the earlier wording from that day.")
    return edit


def replay(first: dict) -> list[dict]:
    global HEADS
    HEADS = Heads()
    STALE.clear()
    BEFORE.clear()
    CHANGED.clear()
    out = []
    units = first
    for law, day, edit in STEPS:
        url = LAWS[law]["url"]
        if law not in BEFORE:
            BEFORE[law] = (units, [list(h) for h in HEADS.lines], set(STALE))
        if isinstance(edit, list):
            for k in edit:
                if k not in units:
                    raise SystemExit(f"{law}: no unit {k}")
            v = {"from": day, "source_url": url, "sha256": sha_of(url), "changes": {},
                 "credits": {k: [law] for k in sorted(edit, key=order)}}
            if LAWS[law].get("note"):
                v["note"] = LAWS[law]["note"]
            if out and out[-1]["from"] == day:
                v["same_day"] = True
            out.append(v)
            STALE.update(edit)
            continue
        u = Units(units)
        u.skipped, u.fresh, u.restale, u.note = [], set(), set(), None
        edit(u)
        new = u.u
        changed = sorted((k for k in set(units) | set(new) if units.get(k) != new.get(k)), key=order)
        skipped = sorted(set(u.skipped) - set(changed) - set(u.fresh), key=order)
        if not changed and not skipped:
            raise SystemExit(f"{law}: no change")
        v = {"from": day, "source_url": url, "sha256": sha_of(url),
             "changes": {k: new.get(k) for k in changed},
             "credits": {k: [law] for k in sorted(set(changed) | set(skipped), key=order)}}
        note = u.note
        if skipped:
            names = ", ".join(new[k].get("label") or k for k in skipped)
            one = len(skipped) == 1
            note = ((note + " ") if note else "") + PARTLY.format(
                "Partly NOT APPLIED" if changed else "NOT APPLIED", names, "it" if one else "them",
                "it keeps" if one else "they keep")
        if note:
            v["note"] = note
        if out and out[-1]["from"] == day:
            v["same_day"] = True
        out.append(v)
        CHANGED.setdefault(law, set()).update(changed)
        STALE.difference_update(u.fresh)
        STALE.difference_update(k for k in changed if k not in new)
        STALE.update(u.restale)
        units = new
    return out


def check_anachronism(versions: list[dict], laws: dict) -> list[str]:
    """No version may carry a law published after its own in-force day; versions are in order of in-force day."""
    errs = []
    prev = ""
    for v in versions:
        if v["from"] < prev:
            errs.append(f"version {v['from']} comes after {prev}")
        prev = v["from"]
        for k, ls in v.get("credits", {}).items():
            for law in ls:
                pub = laws[law]["published"]
                if pub > v["from"]:
                    errs.append(f"{v['from']}: {k} credited to {law}, published {pub}")
    return errs


DECISIONS: list[str] = [
    "COIP: the amending acts were found from two editorial indexes, read only: the Ediciones Legales consolidation "
    "(Consejo de Comunicación repository, to 13-X-2021; coip/index_notes.py) and the Lexis consolidation on FAOLEX (to "
    "8-III-2023; coip/index_lexis.py). Each act was then read in its own Registro Oficial edition (coip/editions.json, "
    "found by coip/find_editions.py; the portal's listing date can be a day off the masthead, so editions are matched "
    "by number within three days).",
    "COIP, acts of 2023 to 2026: indexed from the editorial notes of the Ediciones Legales consolidation of 2026 "
    "(aduana.gob.ec copy, last reform 29-IV-2026; coip/index_el2026.py) and of the Andina Ediciones compilation "
    "updated to 24-VIII-2026 (legalcloud.ec copy), both read only, and from the Asamblea Nacional's list of laws "
    "published in the Registro Oficial (coip/index_asamblea.py; decree-laws are not on it): every law on that list from 2023 to 19-X-2026 was "
    "downloaded and its text layer searched for the Code (coip/screen_laws.py, coip/screen.json). That search found "
    "one reform no index named (Ley Orgánica para el Fortalecimiento de la Ciberseguridad, 2026, art. 232). Coverage: "
    "acts published to 7-VIII-2026 as indexed; laws published from 25-VIII-2026 to 28-X-2026 whose editions are page "
    "images (no text layer) could not be checked for COIP reforms and may be missing.",
    "COIP: the Ley Orgánica para enfrentar el Conflicto Armado Interno, la Crisis Social y Económica (Suplemento 516, "
    "12-III-2024) is image-only and neither index credits it with a reform of the Code, so it has no version. The "
    "referendum of 21-IV-2024 changed no words of the Code: its penal questions (annexes of Decreto Ejecutivo 163, "
    "Segundo Suplemento 498, read in its text layer) ordered the President to send a reform bill, enacted as the Ley "
    "Orgánica para la Aplicación de la Consulta Popular (Suplemento 599, 12-VII-2024).",
    "COIP, in-force days of 2023 to 2026: the Ley de Seguridad Integral (Suplemento 279, 29-III-2023) puts its COIP "
    "reforms in force 'en el término de treinta (30) días posteriores' to publication (Disposición transitoria "
    "séptima): a término counts días hábiles, so with Viernes Santo (7-IV-2023) and 1-V-2023 excluded the thirtieth is "
    "12-V-2023 and the reforms bind from 13-V-2023 (Ediciones Legales gives 12 May). The Ley de Lavado de Activos "
    "(Cuarto Suplemento 610, 29-VII-2024) enters into force 'en el plazo de un año posterior a su publicación' "
    "(Disposición final única): under Código Civil art. 33 the year ends with 29-VII-2025, so it binds from "
    "30-VII-2025 (Ediciones Legales gives 29 July). Every other act states it is in force on publication, or is "
    "image-only and is dated by Código Civil art. 6 (publication), the editorial indexes reporting no other date.",
    "COIP: the Corte Constitucional annulled the Ley Orgánica de Solidaridad Nacional entirely (sentencia "
    "51-25-IN/25) and the penal and penitentiary reforms of the Ley Orgánica de Integridad Pública (sentencia "
    "52-25-IN/25), both with retroactive effect, in Edición Constitucional 96 (3-X-2025). The two laws are applied on "
    "their in-force days as published, and each ruling restores, on its publication day, the exact earlier wording of "
    "every provision and heading the law changed (Integridad first, then Solidaridad, as the second law amended the "
    "first's art. 72 and repealed its art. 699.1).",
    "COIP, partial amendments of provisions this record could not keep current: once an image-only reform has "
    "amended a provision, a later act's partial amendment of it (a numeral, an inciso, a phrase) is not applied, so "
    "no version grafts new words onto wording that was no longer law; the act is credited to the provision with a "
    "note. Whole articles substituted or added are always applied, and make the provision current again. Not applied "
    "on this ground: art. 47 numeral 24 and art. 430.1 (2023), arts. 47, 77 and 536 (Solidaridad 2025), arts. 45, "
    "698 and 699 (Integridad 2025), arts. 698 and 699 (Penitenciaria 2026), art. 232 (Ciberseguridad 2026).",
    "COIP NOT APPLIED, image-only editions of 2024 to 2026 (no OCR by the user's decision; provisions named from the "
    "Ediciones Legales 2026 and Andina 2026 notes): Ley Orgánica de Salud Mental (Supl. 471, 5-I-2024: art. 76); Ley "
    "para el Ahorro y la Monetización de Recursos (Segundo Supl. 496, 9-II-2024: arts. 69, 443); Ley de Reparación a "
    "Familiares de Víctimas de Femicidio (Tercer Supl. 588, 27-VI-2024: arts. 78.1, 441, 520, 558.1, 570, new 77.1); "
    "Ley para la Aplicación de la Consulta Popular (Supl. 599, 12-VII-2024: 12 articles, new 360.1, 474.2 to 474.4); "
    "Decreto Ley 477 (Quinto Supl. 700, 10-XII-2024: arts. 69, 552), annulled with retroactive effect by sentencia "
    "94-24-IN/25 (Edición Constitucional 8, 27-III-2025), a version that changes no words; Ley Reformatoria de la Ley "
    "de Tránsito (Quinto Supl. 38, 14-V-2025: art. 388); Ley Reformatoria de la Ley Orgánica de Movilidad Humana "
    "(Séptimo Supl. 151, 24-X-2025: arts. 12, 61, 667.1, 729, 730, new 633.1); Ley contra el uso delictivo de "
    "uniformes (Quinto Supl. 316, 1-VII-2026: arts. 47, 69, new 362.1, 362.2); Ley Orgánica de Extradición (Quinto "
    "Supl. 343, 7-VIII-2026: art. 541). The editorial notes place some of these only roughly; articles they add do "
    "not exist in this record.",
    "COIP rulings of 2023 to 2026: sentencia 61-18-IN/23 (Edición Constitucional 319, 26-II-2024) strikes 'pena "
    "privativa de libertad de cinco a quince días' from art. 383, which then reads 'será sancionada con y disminución "
    "de cinco puntos', the words the ruling leaves; sentencia 49-21-CN/25 (Edición Constitucional 15, 2-IV-2025) "
    "strikes the phrase that is the whole last inciso of art. 536 here, so the inciso goes. Sentencia 129-21-IN/25 "
    "(Edición Constitucional 78, 19-IX-2025) strikes words of art. 294.1, an article the image-only anticorruption "
    "reform of 2021 added and this record does not have, so it has no version. Rulings that only condition or "
    "interpret change no words and are not versions: 67-23-IN/24 (art. 144), 67-19-IN/24 (art. 300), 106-20-IN/24 "
    "(art. 386), 38-22-CN/25 (arts. 439, 654).",
    "COIP, acts of 2023 to 2026 as printed: the 2023 law heads its new art. 477.1 'Art. 471.1' and its art. 725.8 "
    "'Art. 725.8.' without the dash; the 2026 Ley Penitenciaria heads its new arts. 731 to 734 'Artículo' and sets "
    "some numerals and the inciso after them in one paragraph of the text layer ('3. Centros de mínima seguridad. El "
    "Organismo Técnico ...'). Its text layer sets spaces in a symbol font (U+F020), read as spaces. The Ley de "
    "Integridad Pública prints its new text without quotation marks; it is cut by item.",
    "COIP: in-force dates follow the default rule (Código Civil art. 6: from publication) unless the act says otherwise: "
    "the Code itself and the 2019 reform 180 days after publication (10-VIII-2014, 22-VI-2020); the drug law of 2015 "
    "90 days after publication for its repeal of the Code's Disposición reformatoria décimo primera (25-I-2016) and "
    "on publication for its Disposición reformatoria primera, as its Disposición final says. Day plazos are counted "
    "under Código Civil art. 33 (complete days, the publication day not counted; the act binds the next day).",
    "COIP: constitutional rulings that strike or rewrite words take effect on the day of their publication in the "
    "Registro Oficial. Rulings that only fix an interpretation or declare conditional constitutionality change no "
    "words and are not versions (sentencias 14-19-CN/20 on art. 301, 17-21-CN/23 on art. 171, and the interpretations "
    "noted by the indexes for arts. 220, 268, 387, 649, 652, 653).",
    "COIP: rulings that state how a provision 'dirá' or 'se leerá' are applied in the ruling's own words: art. 75 "
    "numeral 1 (Edición Constitucional 261, 2022), art. 175 numeral 5 (Edición Constitucional 268, 2022; two footnote "
    "calls the text layer glues to words, 'coerción70' and 'consentimiento71', are removed), art. 476 first inciso and "
    "numeral 6 (Edición Constitucional 20, 2022; the ruling's markers '(...)' and '(Las negritas se incluyen)' are not "
    "part of the reading).",
    "COIP NOT APPLIED, image-only gazette editions (no text layer; no OCR by the user's decision). Each has a version "
    "of its own that changes no words, credited to the provisions the editorial indexes name, and the files named keep "
    "their earlier wording, which is not the law from that date: Ley Orgánica para la Reactivación de la Economía "
    "(Segundo Supl. 150, 29-XII-2017: art. 299); Corte Constitucional, Edición Constitucional 90 (3-VI-2019: art. "
    "202), sentencia 5-13-IN/19 (Edición Constitucional 6, 15-VIII-2019: art. 581) and Edición Constitucional 21 "
    "(13-XI-2019: art. 653); Ley Reformatoria de la Ley Orgánica de Movilidad Humana (Tercer Supl. 386, 5-II-2021: "
    "art. 91); Ley Reformatoria del COIP en materia anticorrupción (Segundo Supl. 392, 17-II-2021: 20 articles and 5 "
    "new ones); Ley Orgánica de Extinción de Dominio (Quinto Supl. 452, 14-V-2021: art. 452); Ley Reformatoria de la "
    "Ley de Tránsito (Quinto Supl. 512, 10-VIII-2021: arts. 17, 388 to 392, 404); Ley contra el comercio ilícito "
    "(Quinto Supl. 525, 27-VIII-2021: 9 articles and new arts. 208 B, 208 C); Ley Reformatoria del COIP sobre "
    "violencia sexual digital (Cuarto Supl. 526, 30-VIII-2021: 14 articles and 8 new ones); Ley Orgánica que regula "
    "el Uso Legítimo de la Fuerza (Tercer Supl. 131, 22-VIII-2022: 8 articles and new arts. 30.2, 533.1). Articles "
    "these acts add do not exist in this record.",
    "COIP: the anticorruption reform of 2021 (Segundo Suplemento 392, 17-II-2021) is dated on publication (Código "
    "Civil art. 6). A Lexis note (derechoecuador.com) says its Disposición final única puts it in force 180 days after "
    "publication, but the edition's text layer holds only the cover, the Asamblea's letter, the certification and the "
    "signature page; the law itself (pages 4 to 26), its vigencia clause included, is page images, so the clause "
    "could not be read and the date is left as it is.",
    "COIP: sentencia 8-20-CN/21 (Edición Constitucional 222, 13-X-2021) strikes words that the anticorruption reform "
    "of February 2021 (not applied, image-only) put into art. 536; those words are not in this record's text, so the "
    "ruling is a version that changes no words, with a note.",
    "COIP: the 2018 referendum's reforms (questions 1 and 4) take the wording of the annexes of Decreto Ejecutivo 229 "
    "(Supl. 133, 4-XII-2017), which put them to the vote, and the in-force day of the CNE's results (Supl. 180, "
    "14-II-2018), as for the Constitution. The CNE reprinted the annexes in Supl. 181 (15-II-2018), but only as page "
    "images. Ediciones Legales reads art. 75 as 'niñas, niños' where the decree's annex reads 'niños, niñas'.",
    "COIP: the Ley Orgánica Integral para Prevenir y Erradicar la Violencia contra las Mujeres (Supl. 175, 2018) opens "
    "its quotations and never closes them; each quoted text is taken to run to the next disposición. That edition, "
    "the decree annexes of Supl. 133 (2017) and the 2019 reform (Supl. 107) carry stray text fragments laid over the "
    "real text blocks; they are read with rotext's drop_overlaps (text blocks lying mostly inside a fuller block, and "
    "blocks of at most eight characters touching one, are skipped).",
    "COIP: the Registro Oficial hyphenates words at line ends and the text layer keeps the hyphen; a hyphenated pair "
    "of lower-case words is joined when the joined word occurs unbroken in the Code's text (or the same edition), "
    "otherwise the printed hyphen stays ('penas in-definidas' in art. 53 and 'investí-gación' in art. 412 keep it). "
    "Other typesetting of the text layer is kept as printed ('necesariala' in art. 466; 'visolencia' in art. 157 as "
    "enacted in 2018; 'reglamento..' in art. 708 as enacted in 2019).",
    "COIP, words the acts quote slightly differently from the Code, changed where they evidently point: the 2015 "
    "reform's art. 4 adds 'y vigilancia' after 'consejo de administración', which in art. 278 (as replaced by the COMF "
    "in 2014) reads 'consejos de administración'; the 2019 reform's art. 92 removes 'de existir méritos.' from art. "
    "558 numeral 12, whose second paragraph reads 'la o el fiscal de existir méritos, solicitará' (the words go, the "
    "comma stays); its art. 52 and art. 60 quote the headings in another case and 'mascotas y animales' for 'mascotas "
    "o animales'; the replacement headings are taken as the act prints them.",
    "COIP: replacement text is taken exactly as each act prints it, including its heading style ('Art. 157.-' where "
    "the Code had 'Artículo 157.-'), its typos and numbering ('1. 1. Las infracciones' in art. 635, 'Artículo. 651.4'), "
    "and the absence of a final stop where the act gives none (art. 30: 'debidamente comprobados').",
    "COIP: the 2019 reform's art. 19 replaces 'the third paragraph of numeral 2' of art. 69; counting the numeral's "
    "own line ('2. Comiso penal ...') as the first and not counting its lettered items, the third is 'En caso de "
    "sentencia condenatoria ejecutoriada ...', which is also how the replacement begins. Its art. 110 "
    "replaces the first inciso of art. 677, which in the Code is the article's first two paragraphs ('... El Centro de "
    "formación ...' and 'Sus funciones serán:'). Its arts. 122 to 127 amend other laws and are not part of the Code; "
    "its own transitional provisions are not added to the Code.",
    "COIP: the Ley Orgánica de la Defensoría del Pueblo (2019) adds 'una Disposición General' without an ordinal; it "
    "is the fifth (disp-general-05), before the 2019 reform's sexta to octava.",
    "COIP: the replayed text on 13-X-2021 was compared, for reading only, with the Ediciones Legales consolidation "
    "(coip/reconcile_coip.py): 663 of 754 articles agree after normalising spacing, quotes and amendment notes. Of the "
    "91 that differ, 51 are explained by acts not applied here (image-only editions) and 40 by the consolidation's "
    "own editorial changes, typos and note residue, its headings run into article text, and the literal readings "
    "listed above.",
]
