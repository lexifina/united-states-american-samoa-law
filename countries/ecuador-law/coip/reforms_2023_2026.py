"""The COIP's amending acts of 2023 to 2026 whose Registro Oficial edition has a text layer, as edit functions for
coip_replay.py (which holds their LAWS entries, in-force days and STEPS).

Each act's amending items are cut out of its own gazette edition: an item is the instruction paragraph ("Artículo 41.-
Sustitúyase el artículo 154 ...", "5. Sustitúyase el artículo 268 ...") and the payload paragraphs up to the next item.
Whole articles an act substitutes or adds are taken exactly as it prints them. A partial amendment (a numeral, an
inciso, a phrase) is applied only to a provision whose text in this record is the law (coip_replay.editable); one an
earlier, image-only reform had already amended is credited to the act as not applied.
"""
from __future__ import annotations

import re

from replay import Units  # civil/replay.py
from s107_2019 import span, unq  # coip/s107_2019.py

import coip_replay as R


# ---------------------------------------------------------------- cutting an act into items

_CLEAN: dict[str, object] = {}


def src(url: str):
    """coip_replay.csrc, with one more typesetting fix for these editions: the private-use glyph U+F020 (a space set
    in a symbol font, as in Cuarto Supl. 275 of 2026) is a space; runs of spaces collapse and paragraphs are
    trimmed."""
    if url not in _CLEAN:
        s = R.csrc(url)
        c = object.__new__(type(s))
        c.url = s.url
        c.paras = [re.sub(r" {2,}", " ", p.replace("", " ")).strip() for p in s.paras]
        c.flat = re.sub(r"\s+", " ", "\n".join(c.paras))
        _CLEAN[url] = c
    return _CLEAN[url]


def items(src, start: str, stop: str, item: str, numbers: range, inline: bool = False) -> dict[int, tuple[str, list[str]]]:
    """{n: (instruction, payload)} for the items numbered `numbers` between the paragraph holding `start` and the one
    holding `stop`. `item` is a regex with one group, the item's number, matched at the start of a paragraph. With
    `inline`, the payload begins inside the instruction paragraph, at its first double quote."""
    i0 = src.index(start)
    i1 = src.index(stop, src.paras[i0])
    want = list(numbers)
    pos: dict[int, int] = {}
    for i in range(i0 + 1, i1):
        m = re.match(item, src.paras[i])
        if m and want and int(m.group(1)) == want[0]:
            pos[want.pop(0)] = i
    if want:
        raise SystemExit(f"{src.url[-24:]}: items not found from {want[0]}")
    out = {}
    keys = list(pos)
    for j, n in enumerate(keys):
        a = pos[n]
        b = pos[keys[j + 1]] if j + 1 < len(keys) else i1
        ins = src.paras[a]
        payload = src.paras[a + 1:b]
        if inline and ': "' in ins:
            q = ins.index(': "') + 2
            ins, payload = ins[:q].rstrip(), [ins[q:]] + payload
        out[n] = (ins, payload)
    return out


def check(ins: str, *phrases: str) -> None:
    for ph in phrases:
        if ph not in ins:
            raise SystemExit(f"instruction lacks {ph!r}: {ins[:140]!r}")


def num_key(n: str) -> str:
    """'477.10' -> 'art-477-10'; '678-A' -> 'art-678-a'; '4' -> 'art-004'."""
    m = re.fullmatch(r"(\d+)(?:[.-](\w+))?", n)
    if not m:
        raise SystemExit(f"article number {n!r}")
    return f"art-{int(m.group(1)):03d}" + (f"-{m.group(2).lower()}" if m.group(2) else "")


HEAD = re.compile(r"(?:Art\.|Artículo\.?)\s*(\d+(?:[.-]\w+)?)\s*\.?\s*(?:-|(?=[A-ZÁÉÍÓÚ]))")


def whole(u: Units, n: str, payload: list[str], printed: str | None = None) -> None:
    """Article n substituted entirely by the payload (which must begin with its own heading, numbered `printed` when
    the act misprints it)."""
    new = unq(payload)
    m = HEAD.match(new[0])
    if not m or m.group(1) != (printed or n):
        raise SystemExit(f"art. {n}: payload starts {new[0][:50]!r}")
    key = num_key(n)
    u.set_unit(key, new, label=f"Art. {n}")
    R.fresh(u, key)


def add(u: Units, payload: list[str], expect: str | None = None) -> str:
    """A new article, numbered by its own heading."""
    new = unq(payload)
    m = HEAD.match(new[0])
    if not m:
        raise SystemExit(f"new article: payload starts {new[0][:50]!r}")
    n = m.group(1)
    if expect and n != expect:
        raise SystemExit(f"new article {n}, expected {expect}")
    key = num_key(n)
    if key in u.u:
        raise SystemExit(f"new article {n}: {key} exists")
    u.set_unit(key, new, label=f"Art. {n}")
    R.fresh(u, key)
    return key


def numeral(u: Units, key: str, n: int) -> tuple[int, int]:
    """Paragraph range of numeral n up to the next numeral (or the first later paragraph that is not part of it:
    an unnumbered paragraph after the last numeral is the article's next inciso)."""
    a, b = span(u, key, n)
    ps = u.paras(key)
    if b == len(ps):
        b = a + 1
    return a, b


WHOLE = re.compile(r"(?:Sustitúyase|Sustitúyese) (?:el texto del |el contenido del )?(?:el )?artículo (\d+(?:\.\d+)?)"
                   r"(?: del Código Orgánico Integral(?: Penal)?)?,? por el siguiente(?: texto)?:?$")
AFTER = re.compile(r"(?:Agréguese|Agréguense|Agrégase) (?:el siguiente artículo [\d.]+ )?a continuación del (?:nuevo )?"
                   r"artículo (\d+(?:\.\d+)?)(?: supra)?(?: del Código Orgánico Integral Penal)?(?: añadido)?(?:,| la)? "
                   r"(?:el siguiente|los siguientes artículos|el siguiente artículo)?:?$")


# ---------------------------------------------------------------- 2023: Supl. 279

def seguridad_integral_2023(u: Units) -> None:
    """Ley Orgánica Reformatoria a Varios Cuerpos Legales para el Fortalecimiento de las Capacidades Institucionales y
    la Seguridad Integral (Registro Oficial, Suplemento 279, 29-III-2023), Capítulo III, arts. 38 to 126."""
    s = src(R.S279_2023)
    P = items(s, "Capítulo III REFORMAS AL CÓDIGO ORGÁNICO INTEGRAL PENAL", "Capítulo IV REFORMAS",
              r"Artículo (\d+)\.- ", range(38, 127))
    special = {39, 40, 45, 46, 48, 59, 60, 61, 62, 63, 64, 65, 66, 67, 78, 81, 82, 84, 96, 109, 125, 126}
    for k, (ins, pay) in P.items():
        body = re.sub(r"^Artículo \d+\.- ", "", ins)
        if k in special:
            continue
        m = WHOLE.match(body)
        if m:
            whole(u, m.group(1), pay)
            continue
        m = AFTER.match(body) or re.match(r"A continuación de artículo (616) .* agréguese un artículo 616\.1 con el "
                                           r"siguiente texto:$", body) or re.match(
            r"Agréguese el siguiente artículo 552\.1 a continuación del artículo (552) del Código Orgánico Integral "
            r"Penal:$", body)
        if m:
            add(u, pay)
            continue
        raise SystemExit(f"S279 art. {k}: unhandled {body[:100]!r}")

    def ins_(k: int) -> str:
        return P[k][0]

    def pay(k: int) -> list[str]:
        return unq(P[k][1])

    # 39. art. 48 numeral 8: a phrase
    check(ins_(39), 'En el número 8 del artículo 48', 'sustitúyase la frase: "funcionaria o funcionario público" por: '
                    '"servidora o servidor público"')
    if R.editable(u, "art-048"):
        u.sub("art-048", "funcionaria o funcionario público", "servidora o servidor público", para="8. ")
    # 40. art. 47: numeral 24 after numeral 23
    check(ins_(40), "a continuación del número 23 del artículo 47")
    if R.editable(u, "art-047"):
        raise SystemExit("S279 art. 40: art. 47 is current")
    # 45. art. 219 numeral 2
    check(ins_(45), "Sustitúyase el número 2 del artículo 219")
    if R.editable(u, "art-219"):
        a, b = numeral(u, "art-219", 2)
        u.set_para("art-219", a, pay(45), count=b - a)
    # 46. art. 220 first paragraph
    check(ins_(46), "Sustitúyase el párrafo primero del artículo 220")
    if R.editable(u, "art-220"):
        new = pay(46)
        if len(new) != 1 or not new[0].startswith("Art. 220.-"):
            raise SystemExit("S279 art. 46: payload")
        u.set_para("art-220", 0, new)
    # 48. art. 260: a final paragraph
    check(ins_(48), "Agréguese un párrafo final al artículo 260")
    if R.editable(u, "art-260"):
        u.insert("art-260", u.count("art-260"), pay(48))
    # 59. art. 430.1: an inciso
    check(ins_(59), "Agréguese como inciso del artículo 430.1")
    if R.editable(u, "art-430-1"):
        raise SystemExit("S279 art. 59: art. 430.1 is current")
    # 60. art. 444 numerals 8 and 9
    check(ins_(60), "Sustitúyase los numerales 8 y 9 del artículo 444")
    if R.editable(u, "art-444"):
        new = pay(60)
        if len(new) != 2 or not (new[0].startswith("8. ") and new[1].startswith("9. ")):
            raise SystemExit("S279 art. 60: payload")
        a = u.find("art-444", "8. ")
        if not u.paras("art-444")[a + 1].startswith("9. ") or not u.paras("art-444")[a + 2].startswith("10. "):
            raise SystemExit("S279 art. 60: numerals 8, 9 are not one paragraph each")
        u.set_para("art-444", a, new, count=2)
    # 61. art. 444: numerals 15 to 17 after numeral 14
    check(ins_(61), "a continuación del numeral 14 del artículo 444")
    if R.editable(u, "art-444"):
        u.insert("art-444", u.find("art-444", "14. ") + 1, pay(61))
    # 62. art. 459 numeral 1
    check(ins_(62), "Sustitúyase el número 1 del artículo 459")
    if R.editable(u, "art-459"):
        a, b = numeral(u, "art-459", 1)
        u.set_para("art-459", a, pay(62), count=b - a)
    # 63. art. 471 first paragraph
    check(ins_(63), "Sustitúyase el párrafo primero del artículo 471")
    if R.editable(u, "art-471"):
        new = pay(63)
        if len(new) != 1 or not new[0].startswith("Art. 471.-"):
            raise SystemExit("S279 art. 63: payload")
        u.set_para("art-471", 0, new)
    # 64. art. 474 numerals 2 and 4 (the act quotes each numeral apart)
    check(ins_(64), "Sustitúyase los numerales 2 y 4 del artículo 474")
    if R.editable(u, "art-474"):
        raw = P[64][1]
        two, four = unq(raw[:1]), unq(raw[1:])
        if not (two[0].startswith("2. ") and four[0].startswith("4. ")):
            raise SystemExit("S279 art. 64: payload")
        a, b = numeral(u, "art-474", 4)
        u.set_para("art-474", a, four, count=b - a)
        a, b = numeral(u, "art-474", 2)
        u.set_para("art-474", a, two, count=b - a)
    # 65. art. 474: numeral 7 after numeral 6
    check(ins_(65), "Agréguese a continuación del texto del número 6 del artículo 474")
    if R.editable(u, "art-474"):
        a, b = numeral(u, "art-474", 6)
        u.insert("art-474", b, pay(65))
    # 66, 67. a heading after art. 477, and art. 477.1 (which the act heads 'Art. 471.1')
    check(ins_(66), "Agréguese a continuación del artículo 477", "la siguiente sección innumerada")
    check(ins_(67), "Sustitúyase el artículo 477.1")
    whole(u, "477.1", P[67][1], printed="471.1")
    R.HEADS.insert(u, pay(66)[0], before="art-477-1")
    # 78. art. 484 numerals 3 and 4
    check(ins_(78), "Sustitúyase el contenido de los números 3 y 4 del artículo 484")
    if R.editable(u, "art-484"):
        new = pay(78)
        if len(new) != 2 or not (new[0].startswith("3. ") and new[1].startswith("4. ")):
            raise SystemExit("S279 art. 78: payload")
        a = u.find("art-484", "3. ")
        if not u.paras("art-484")[a + 1].startswith("4. ") or not u.paras("art-484")[a + 2].startswith("5. "):
            raise SystemExit("S279 art. 78: numerals 3, 4")
        u.set_para("art-484", a, new, count=2)
    # 81. art. 500 first paragraph: a phrase
    check(ins_(81), 'En el primer párrafo del artículo 500', 'sustitúyase la frase: "acto informático", por la '
                    'siguiente: "dato informático"')
    if R.editable(u, "art-500"):
        u.sub("art-500", "acto informático", "dato informático", para=0)
    # 82. art. 520 numeral 3
    check(ins_(82), "Sustitúyase el número 3 del artículo 520")
    if R.editable(u, "art-520"):
        a, b = numeral(u, "art-520", 3)
        u.set_para("art-520", a, pay(82), count=b - a)
    # 84. art. 529: paragraphs added
    check(ins_(84), "Agréguese al artículo 529", "los siguientes párrafos")
    if R.editable(u, "art-529"):
        u.insert("art-529", u.count("art-529"), pay(84))
    # 96. art. 635 numeral 1
    check(ins_(96), "Sustitúyase el número 1 del artículo 635")
    if R.editable(u, "art-635"):
        a, b = numeral(u, "art-635", 1)
        u.set_para("art-635", a, pay(96), count=b - a)
    # 109. art. 718: text added
    check(ins_(109), "Agréguese en el artículo 718", "el siguiente texto")
    if R.editable(u, "art-718"):
        u.insert("art-718", u.count("art-718"), pay(109))
    # 125. art. 726 repealed
    check(ins_(125), "Deróguese el artículo 726")
    u.remove("art-726")
    # 126. Disposición general novena
    check(ins_(126), "Agréguese como DISPOSICIÓN GENERAL NOVENA")
    new = pay(126)
    if not new[0].startswith("DISPOSICIÓN GENERAL NOVENA.-"):
        raise SystemExit("S279 art. 126: payload")
    u.set_unit("disp-general-09", new, label="Disposición general novena")
    u.u["disp-general-09"]["kind"] = "general"
    R.fresh(u, "disp-general-09")


# ---------------------------------------------------------------- 2024: Cuarto Supl. 610 (in force a year later)

def lavado_2024(u: Units) -> None:
    """Ley Orgánica de Prevención, Detección y Combate del Delito de Lavado de Activos y de la Financiación de Otros
    Delitos (Registro Oficial, Cuarto Suplemento 610, 29-VII-2024), Disposición reformatoria primera: arts. 318 and
    368 repealed, art. 553 substituted (its quotation is never closed: it runs to the next disposición)."""
    s = src(R.S4_610_2024)
    s.check("PRIMERA.- Refórmese en el Código Orgánico Integral Penal lo siguiente:", "Uno.- Deróguese el artículo 318.",
            "Dos.- Deróguese el artículo 368.")
    u.remove("art-318")
    u.remove("art-368")
    new = R.open_quote(s, "Tres.- Sustitúyase el artículo 553 por el siguiente:", "SEGUNDA.- Refórmese en el Código "
                       "Orgánico Monetario")
    whole(u, "553", new)


# ---------------------------------------------------------------- 2025: Sexto Supl. 56 and Tercer Supl. 68

def solidaridad_2025(u: Units) -> None:
    """Ley Orgánica de Solidaridad Nacional (Registro Oficial, Sexto Suplemento 56, 10-VI-2025), Disposición
    reformatoria segunda, numerals 1 to 21, and Disposición derogatoria segunda (art. 296); in force on publication
    (its Disposición final)."""
    s = src(R.S6_56_2025)
    P = items(s, "SEGUNDA.- Refórmese en el Código Orgánico Integral Penal, lo siguiente:",
              "TERCERA.- Refórmese en la Ley Orgánica de Personal y Disciplina",
              r"(\d+)\. (?:A continuación|Incorpórese|Sustitúyase|Agréguese)", range(1, 22))

    def pay(k: int) -> list[str]:
        return unq(P[k][1])

    # 1. art. 47: numerals 25 and 26 after numeral 24
    check(P[1][0], "A continuación del numeral 24 del artículo 47")
    if R.editable(u, "art-047"):
        raise SystemExit("S56 1: art. 47 is current")
    # 2. art. 72: numeral 8 after numeral 7
    check(P[2][0], "A continuación del numeral 7 del artículo 72")
    if R.editable(u, "art-072"):
        if u.paras("art-072")[-1][:3] != "7. ":
            raise SystemExit("S56 2: numeral 7 is not the last")
        u.insert("art-072", u.count("art-072"), pay(2))
    # 3. art. 77: a last inciso
    check(P[3][0], "Incorpórese en el artículo 77 el siguiente último inciso")
    if R.editable(u, "art-077"):
        u.insert("art-077", u.count("art-077"), pay(3))
    # 4. after art. 139: a section heading and arts. 139.1, 139.2
    check(P[4][0], "A continuación del artículo 139, agréguese")
    new = pay(4)
    if not new[0].startswith("Sección Quinta De los delitos cometidos"):
        raise SystemExit("S56 4: heading")
    j = next(i for i, p in enumerate(new) if p.startswith("Art. 139.2.-"))
    add(u, new[1:j], "139.1")
    add(u, new[j:], "139.2")
    R.HEADS.insert(u, new[0], before="art-139-1")
    # 5. art. 220: the 'trasantepenúltimo' inciso replaced and the 'antepenúltimo' removed (incisos counted from the
    #    end, numerals not counted)
    check(P[5][0], "Sustitúyase el trasantepenúltimo y elimínese el antepenúltimo inciso del artículo 220")
    if R.editable(u, "art-220"):
        ps = u.paras("art-220")
        inc = [i for i, p in enumerate(ps) if i > 0 and not re.match(r"\d+\. |[a-z]\) ", p)]
        tras, ante = inc[-4], inc[-3]
        if ante != tras + 1 or not ps[tras].startswith("La tenencia o posesión de sustancias estupefacientes"):
            raise SystemExit("S56 5: incisos of art. 220")
        u.set_para("art-220", tras, pay(5), count=2)
    # 6-10. arts. 228, 262, 264, 265, 266 substituted
    for k, n in ((6, "228"), (7, "262"), (8, "264"), (9, "265"), (10, "266")):
        check(P[k][0], f"Sustitúyase el artículo {n}, por el siguiente:")
        whole(u, n, P[k][1])
    # 11-13, 16, 18, 21. new articles
    for k, n in ((11, "267.1"), (12, "362.1"), (13, "474.5"), (16, "534.1"), (18, "542.1"), (21, "699.1")):
        check(P[k][0], "A continuación del artículo")
        add(u, P[k][1], n)
    # 14. art. 480: numeral 8 after numeral 7
    check(P[14][0], "A continuación del numeral 7 del artículo 480")
    if R.editable(u, "art-480"):
        u.insert("art-480", u.find("art-480", "7. ") + 1, pay(14))
    # 15. art. 482: numeral 6 after numeral 5
    check(P[15][0], "Agréguese a continuación del numeral 5 del artículo 482")
    if R.editable(u, "art-482"):
        if u.paras("art-482")[-1][:3] != "5. ":
            raise SystemExit("S56 15: numeral 5 is not the last")
        u.insert("art-482", u.count("art-482"), pay(15))
    # 17. art. 536: a final inciso
    check(P[17][0], "Agréguese como inciso final del artículo 536")
    if R.editable(u, "art-536"):
        u.insert("art-536", u.count("art-536"), pay(17))
    # 19. after art. 651.6: a section heading and art. 651.7
    check(P[19][0], "A continuación del artículo 651.6, agréguese")
    new = pay(19)
    if not new[0].startswith("Sección Sexta Procedimiento unificado"):
        raise SystemExit("S56 19: heading")
    add(u, new[1:], "651.7")
    R.HEADS.insert(u, new[0], before="art-651-7")
    # 20. art. 562: a final inciso
    check(P[20][0], "Agréguese el siguiente inciso final en el artículo 562")
    if R.editable(u, "art-562"):
        u.insert("art-562", u.count("art-562"), pay(20))
    # Disposición derogatoria segunda: art. 296
    s.check("SEGUNDA. - Deróguese el artículo 296 del Código Orgánico Integral Penal.")
    u.remove("art-296")


def integridad_2025(u: Units) -> None:
    """Ley Orgánica de Integridad Pública (Registro Oficial, Tercer Suplemento 68, 26-VI-2025), Disposición
    reformatoria segunda, numerals 1 to 13 (printed without quotation marks), and Disposición derogatoria tercera
    (art. 699.1); in force on publication (its Disposición final)."""
    s = src(R.S3_68_2025)
    P = items(s, "Segunda.- Refórmese el Código Orgánico Integral Penal en lo siguiente:",
              "Tercera.- Refórmese el Código de la Niñez y Adolescencia",
              r"(\d+)\. (?:Agréguese|En el|Sustitúyase|Elimínese|A continuación)", range(1, 14))

    def plain(k: int) -> list[str]:
        return [p.strip() for p in P[k][1]]

    # 1. art. 45: a numeral 8
    check(P[1][0], "Agréguese en el artículo 45 el siguiente numeral")
    if R.editable(u, "art-045"):
        raise SystemExit("S68 1: art. 45 is current")
    # 2. art. 61: a) a phrase of the first inciso; b) incisos added at the end
    check(P[2][0], 'a) En el primer inciso, sustitúyase la frase "Procede en delitos sancionados con pena privativa de '
                   'libertad mayor a cinco años" por la siguiente frase: "Procede en todos los delitos sancionados con '
                   'pena privativa de libertad". b) Agréguese como inciso final lo siguiente:')
    if R.editable(u, "art-061"):
        u.sub("art-061", "Procede en delitos sancionados con pena privativa de libertad mayor a cinco años",
              "Procede en todos los delitos sancionados con pena privativa de libertad", para=0)
        u.insert("art-061", u.count("art-061"), plain(2))
    # 3. art. 61.1
    check(P[3][0], "Agréguese a continuación del artículo 61, el siguiente artículo")
    add(u, P[3][1], "61.1")
    # 4. art. 72 numeral 8 (added by the Ley de Solidaridad Nacional) substituted
    check(P[4][0], "Sustitúyase el numeral 8 del artículo 72, por el siguiente")
    if R.editable(u, "art-072"):
        new = plain(4)
        if len(new) != 1 or not new[0].startswith("8. "):
            raise SystemExit("S68 4: payload")
        u.set_para("art-072", u.find("art-072", "8. "), new)
    # 5, 6, 8. arts. 268, 272, 360 substituted
    for k, n in ((5, "268"), (6, "272"), (8, "360")):
        check(P[k][0], f"Sustitúyase el artículo {n}")
        whole(u, n, P[k][1])
    # 7. the heading of Sección Segunda of Capítulo Quinto removed, and art. 277 substituted
    check(P[7][0], 'Elimínese el título de la Sección Segunda denominado "Contravenciones contra la Tutela Judicial '
                   'Efectiva" del Capítulo Quinto y sustitúyase el artículo 277 por el siguiente:')
    R.HEADS.remove(u, "SECCIÓN SEGUNDA Contravenciones contra la tutela judicial efectiva")
    whole(u, "277", P[7][1])
    # 9. art. 480 numeral 8: a phrase added
    check(P[9][0], 'En el artículo 480 numeral 8, luego de la frase "las fuerzas del orden" agréguese la frase: "o la '
                   'entidad rectora del Sistema Nacional de Inteligencia".')
    if R.editable(u, "art-480"):
        u.sub("art-480", "las fuerzas del orden", "las fuerzas del orden o la entidad rectora del Sistema Nacional de "
              "Inteligencia", para="8. ")
    # 10. art. 529: an inciso after the first
    check(P[10][0], "A continuación del primer inciso del artículo 529 agréguese el siguiente inciso")
    if R.editable(u, "art-529"):
        u.insert("art-529", 1, plain(10))
    # 11. art. 633.1
    check(P[11][0], "Agréguese a continuación del artículo 633, el siguiente artículo")
    add(u, P[11][1], "633.1")
    # 12, 13. arts. 698 and 699, last inciso: a phrase
    check(P[12][0], 'En el último inciso del artículo 698, sustitúyase la frase final "y extorsión."')
    check(P[13][0], 'En el último inciso del artículo 699, sustitúyase la frase final "y extorsión."')
    for key in ("art-698", "art-699"):
        if R.editable(u, key):
            raise SystemExit(f"S68: {key} is current")
    # Disposición derogatoria tercera: art. 699.1 (added by the Ley de Solidaridad Nacional sixteen days earlier)
    s.check("Tercera.- Deróguese el artículo 699.1 del Código Orgánico Integral Penal.")
    u.remove("art-699-1")


# ---------------------------------------------------------------- 2026: Cuarto Supl. 275 and Quinto Supl. 290

def penitenciario_2026(u: Units) -> None:
    """Ley Orgánica Reformatoria para el Fortalecimiento del Sistema Penitenciario (Registro Oficial, Cuarto
    Suplemento 275, 29-IV-2026), Capítulo II, arts. 7 to 24; in force on publication (its Disposición final). Each
    article carries its quotation inside its own paragraph."""
    s = src(R.S4_275_2026)
    P = items(s, "DE LAS REFORMAS AL CÓDIGO ORGÁNICO INTEGRAL PENAL", "Capítulo III", r"Artículo (\d+)\.- ",
              range(7, 25), inline=True)

    def pay(k: int) -> list[str]:
        return unq(P[k][1])

    # 7. art. 565: a last paragraph
    check(P[7][0], "Agréguese como último párrafo del artículo 565 el siguiente texto:")
    if R.editable(u, "art-565"):
        u.insert("art-565", u.count("art-565"), pay(7))
    # 8, 10-14, 16-18, 22. articles substituted
    for k, n in ((8, "668"), (10, "668.2"), (11, "669"), (12, "674"), (13, "675"), (14, "678"), (16, "684"),
                 (17, "685"), (18, "691"), (22, "715")):
        check(P[k][0], f"Sustitúyase el artículo {n} por el siguiente:")
        whole(u, n, P[k][1])
    # 9. art. 668.1, second inciso
    check(P[9][0], "Sustitúyase el segundo inciso del artículo 668.1 por el siguiente:")
    if R.editable(u, "art-668-1"):
        new = pay(9)
        if len(new) != 1:
            raise SystemExit("S275 9: payload")
        u.set_para("art-668-1", 1, new)
    # 15. arts. 678-A and 678-B
    check(P[15][0], "Agréguense a continuación del artículo 678 los siguientes artículos:")
    new = pay(15)
    j = next(i for i, p in enumerate(new) if p.startswith("Art. 678-B.-"))
    add(u, new[:j], "678-A")
    add(u, new[j:], "678-B")
    # 19. art. 694-A
    check(P[19][0], "Agréguese a continuación del artículo 694 el siguiente artículo:")
    add(u, P[19][1], "694-A")
    # 20, 21. arts. 698 (a final inciso) and 699 (a numeral 3)
    check(P[20][0], "Agréguese al final del artículo 698 el siguiente inciso:")
    check(P[21][0], "Agréguese a continuación del numeral 2 del artículo 699 el siguiente numeral 3:")
    for key in ("art-698", "art-699"):
        if R.editable(u, key):
            raise SystemExit(f"S275: {key} is current")
    # 23. art. 724: numerals 23 to 31 at the end
    check(P[23][0], "Agréguese al final del artículo 724 los siguientes numerales:")
    if R.editable(u, "art-724"):
        u.insert("art-724", u.count("art-724"), pay(23))
    # 24. Título VI, arts. 731 to 734
    check(P[24][0], 'a continuación del Título V "De la Repatriación", incorpórese el siguiente:')
    new = pay(24)
    if new[0] != "TÍTULO VI RÉGIMEN PENITENCIARIO ESPECIAL":
        raise SystemExit("S275 24: heading")
    starts = [i for i, p in enumerate(new) if re.match(r"Artículo 73[1-4]\.-", p)] + [len(new)]
    if len(starts) != 5 or starts[0] != 1:
        raise SystemExit("S275 24: articles")
    for a, b, n in zip(starts, starts[1:], ("731", "732", "733", "734")):
        add(u, new[a:b], n)
    R.HEADS.insert(u, new[0], before="art-731")


def ciberseguridad_2026(u: Units) -> None:
    """Ley Orgánica para el Fortalecimiento de la Ciberseguridad (Registro Oficial, Quinto Suplemento 290,
    22-V-2026), art. 11: an inciso at the end of art. 232; in force on publication (its Disposición final)."""
    s = src(R.S5_290_2026)
    s.check('Artículo 11.- Al final del artículo 232 añadir el siguiente inciso: "No constituyen delito las acciones de '
            'acceso, prueba o evaluación')
    if R.editable(u, "art-232"):
        raise SystemExit("S290: art. 232 is current")


# ---------------------------------------------------------------- rulings with a text layer

def cc_61_18_in_23(u: Units) -> None:
    """Corte Constitucional, sentencia 61-18-IN/23 (Edición Constitucional 319, 26-II-2024): the phrase 'pena
    privativa de libertad de cinco a quince días' of art. 383 is unconstitutional; the other penalties stay."""
    s = src(R.EC319_2024)
    s.check('Declarar la inconstitucionalidad por el fondo de la frase "pena privativa de libertad de cinco a quince '
            'días" del artículo 383 del Código Orgánico Integral Penal')
    u.drop("art-383", "pena privativa de libertad de cinco a quince días", para=0)


def cc_49_21_cn_25(u: Units) -> None:
    """Corte Constitucional, sentencia 49-21-CN/25 (Edición Constitucional 15, 2-IV-2025): the phrase 'tampoco se
    podrá sustituir la prisión preventiva por otra medida cautelar cuando se trate de un caso de reincidencia' of art.
    536 is unconstitutional. In this record it is the whole last inciso, which goes."""
    s = src(R.EC15_2025)
    phrase = "tampoco se podrá sustituir la prisión preventiva por otra medida cautelar cuando se trate de un caso de " \
             "reincidencia"
    s.check(f'Declarar inconstitucional la frase contenida en el último inciso primero del artículo 536 del COIP que '
            f'establece: "{phrase}".')
    ps = u.paras("art-536")
    if ps[-1] != phrase[0].upper() + phrase[1:] + ".":
        raise SystemExit("EC 15: last inciso of art. 536")
    u.put("art-536", ps[:-1])
