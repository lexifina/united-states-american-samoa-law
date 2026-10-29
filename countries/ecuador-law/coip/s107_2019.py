"""Ley Orgánica Reformatoria al Código Orgánico Integral Penal (Registro Oficial, Suplemento 107, 24-XII-2019).

Its articles 1 to 121 amend the COIP (122 to 127 amend other laws and are not replayed here). Each amending article
k is a paragraph "Artículo k.- <instruction>" followed by its payload: the quoted text it adds or substitutes, which
is cut out of the gazette edition's text layer (the paragraphs between instruction k and instruction k+1). Short
phrases an instruction carries inline are checked against the edition. The law is in force 180 days after its
publication (its Disposición final): from 22 June 2020.

Pages of this edition carry stray text fragments over the real text blocks, so it is read with
coip_replay.clean_src (rotext drop_overlaps).
"""
from __future__ import annotations

import re

from replay import Units  # civil/replay.py


def payloads(src) -> dict[int, list[str]]:
    """Amending article number -> its payload paragraphs (raw, quotes still on)."""
    idx: dict[int, int] = {}
    k = 1
    for i, p in enumerate(src.paras):
        m = re.match(r"Artículo (\d+)\.- ", p)
        if m and int(m.group(1)) == k and k <= 127 and re.match(
                r"Artículo \d+\.- (Agr|Sus|En |Sup|Der|Inc|Al |Refórm|A continuación)", p):
            idx[k] = i
            k += 1
    if k != 128:
        raise SystemExit(f"S107: found amending articles up to {k - 1}")
    end = src.index("DISPOSICIONES TRANSITORIAS", src.paras[idx[127]])
    out = {}
    for k in range(1, 128):
        stop = idx[k + 1] if k < 127 else end
        out[k] = src.paras[idx[k] + 1:stop]
    out[0] = [src.paras[idx[k]] for k in range(1, 128)]  # the instruction paragraphs themselves, 1-based below
    return out


def unq(block: list[str]) -> list[str]:
    """Strip the act's quotation marks around a payload. Spanish sets the stop after the closing quote: when the
    quoted text has no final stop of its own and a stop follows the quote, the stop belongs to the quoted text."""
    b = [x.strip() for x in block]
    if not b:
        raise SystemExit("empty payload")
    if b[0].startswith('"'):
        b[0] = b[0][1:].lstrip()
    m = re.search(r"(?:\"|'')\s*([.,;]?)\s*$", b[-1])
    if m:
        inner = b[-1][:m.start()].rstrip()
        if m.group(1) == "." and not re.search(r"[.:;]$", inner):
            inner += "."
        b[-1] = inner
    return b


def span(u: Units, key: str, n: int | str, last: int | None = None) -> tuple[int, int]:
    """Paragraph range of numeral n ('n. ' up to the next numeral 'n+1. ', or to the end / `last`)."""
    ps = u.paras(key)
    tag = f"{n}. "
    starts = [i for i, p in enumerate(ps) if i > 0 and p.startswith(tag)]
    if len(starts) != 1:
        raise SystemExit(f"{key}: {len(starts)} paragraphs start with {tag!r}")
    a = starts[0]
    b = len(ps) if last is None else last
    if isinstance(n, int):
        nxt = [i for i, p in enumerate(ps) if i > a and p.startswith(f"{n + 1}. ")]
        if nxt:
            b = nxt[0]
    return a, b


def letter_span(u: Units, key: str, letter: str) -> int:
    ps = u.paras(key)
    hits = [i for i, p in enumerate(ps) if p.startswith(f"{letter}) ")]
    if len(hits) != 1:
        raise SystemExit(f"{key}: {len(hits)} paragraphs start with {letter!r})")
    return hits[0]


def check_instr(P: dict, k: int, *phrases: str) -> None:
    ins = P[0][k - 1]
    for ph in phrases:
        if ph not in ins:
            raise SystemExit(f"S107 art. {k}: {ph!r} not in {ins[:120]!r}")


def apply(u: Units, src, heads) -> None:
    """`heads` is the replay's heading helper (insert/rename lines of the 'titulos' unit)."""
    P = payloads(src)

    def pay(k: int) -> list[str]:
        return unq(P[k])

    def new_unit(k: int, key: str, label: str) -> None:
        if key in u.u:
            raise SystemExit(f"S107 art. {k}: {key} exists")
        u.set_unit(key, pay(k), label=label)

    def whole(k: int, n: int, prefix: str | None = None) -> None:
        key = f"art-{n:03d}"
        new = pay(k)
        if not re.match(rf"(Artículo|Art\.)\s*{n}\b", new[0]):
            raise SystemExit(f"S107 art. {k}: payload starts {new[0][:40]!r}")
        u.set_unit(key, new)

    def add_end(k: int, key: str) -> None:
        u.insert(key, u.count(key), pay(k))

    # 1. art. 2: a paragraph added
    check_instr(P, 1, "Agrégase al artículo 2 el siguiente párrafo")
    add_end(1, "art-002")
    # 2. art. 12, numeral 1 replaced (with its sub-paragraphs)
    check_instr(P, 2, "Sustitúyese el número 1 del artículo 12")
    a, b = span(u, "art-012", 1)
    u.set_para("art-012", a, pay(2), count=b - a)
    # 3. art. 12, numeral 11, second inciso replaced
    check_instr(P, 3, "segundo inciso del número 11 del artículo 12")
    a, b = span(u, "art-012", 11)
    u.set_para("art-012", a + 1, pay(3))
    # 4. art. 12: an inciso after numeral 16 (the last)
    check_instr(P, 4, "a continuación del número 16 del artículo 12")
    add_end(4, "art-012")
    # 5, 6. arts. 17, 26 replaced
    check_instr(P, 5, "Sustitúyese el artículo 17")
    whole(5, 17)
    check_instr(P, 6, "Sustitúyese el artículo 26")
    whole(6, 26)
    # 7. art. 28.1
    check_instr(P, 7, "a continuación del artículo 28")
    new_unit(7, "art-028-1", "Art. 28.1")
    # 8. art. 30, second inciso: final stop -> comma + 'debidamente comprobados'
    check_instr(P, 8, 'En el segundo inciso del artículo 30, sustitúyese "el punto" por una "coma" y agrégase el '
                      'siguiente texto: "debidamente comprobados"')
    ps = u.paras("art-030")
    if not ps[1].endswith("."):
        raise SystemExit("S107 art. 8: no final stop")
    ps[1] = ps[1][:-1] + ", debidamente comprobados"
    u.put("art-030", ps)
    # 9. art. 30.1
    check_instr(P, 9, "a continuación del artículo 30")
    new_unit(9, "art-030-1", "Art. 30.1")
    # 10. art. 35 replaced; 11. art. 35.1
    check_instr(P, 10, "Sustitúyese el artículo 35")
    whole(10, 35)
    check_instr(P, 11, "a continuación del artículo 35")
    new_unit(11, "art-035-1", "Art. 35.1")
    # 12. art. 47: numeral 9 replaced; numeral 20 after numeral 19 (the payload holds both, with the second
    #     instruction between them)
    check_instr(P, 12, "En el artículo 47 sustitúyese el número 9")
    raw = P[12]
    if len(raw) != 3 or not raw[1].startswith("Y, agrégase, a continuación del número 19"):
        raise SystemExit("S107 art. 12: unexpected payload")
    a, b = span(u, "art-047", 9)
    u.set_para("art-047", a, unq(raw[:1]), count=b - a)
    a, b = span(u, "art-047", 19)
    u.insert("art-047", b, unq(raw[2:]))
    # 13. art. 48, numeral 2 replaced
    check_instr(P, 13, "Sustitúyese el número 2 del artículo 48")
    a, b = span(u, "art-048", 2)
    u.set_para("art-048", a, pay(13), count=b - a)
    # 14. art. 57, second inciso replaced
    check_instr(P, 14, "Sustitúyese el segundo inciso del artículo 57")
    u.set_para("art-057", 1, pay(14))
    # 15. art. 60, numeral 6 replaced
    check_instr(P, 15, "Sustitúyese el número 6 del artículo 60")
    a, b = span(u, "art-060", 6)
    u.set_para("art-060", a, pay(15), count=b - a)
    # 16. art. 62: final inciso
    check_instr(P, 16, "inciso final del artículo 62")
    add_end(16, "art-062")
    # 17. art. 65 replaced
    check_instr(P, 17, "Sustitúyese el artículo 65")
    whole(17, 65)
    # 18. art. 69, numeral 2: letter f) after e)
    check_instr(P, 18, "a continuación de la letra e) del número 2 del artículo 69")
    u.insert("art-069", letter_span(u, "art-069", "e") + 1, pay(18))
    # 19. art. 69, numeral 2, third paragraph replaced: the numeral's own line '2. Comiso penal ...' is the first,
    #     its letters a) to f) are not counted, 'Cuando tales bienes ...' is the second, so the third is 'En caso de
    #     sentencia condenatoria ejecutoriada ...', as the replacement itself begins (see decisions).
    check_instr(P, 19, "Sustitúyese el tercer párrafo del número 2 del artículo 69")
    i = u.find("art-069", "En caso de sentencia condenatoria ejecutoriada")
    u.set_para("art-069", i, pay(19))
    # 20, 21, 22. arts. 84, 89, 111 replaced (art. 84's payload is printed without quotation marks)
    check_instr(P, 20, "Sustitúyese el artículo 84")
    whole(20, 84)
    check_instr(P, 21, "Sustitúyese el artículo 89")
    whole(21, 89)
    check_instr(P, 22, "Sustitúyese el artículo 111")
    whole(22, 111)
    # 23. art. 112: numerals after numeral 5 (the last)
    check_instr(P, 23, "a continuación del número 5 del artículo 112")
    add_end(23, "art-112")
    # 24. art. 114, final paragraph replaced
    check_instr(P, 24, "Sustitúyese el párrafo final del artículo 114")
    u.set_para("art-114", u.count("art-114") - 1, pay(24))
    # 25. art. 121 replaced
    check_instr(P, 25, "Sustitúyese el artículo 121")
    whole(25, 121)
    # 26. art. 122: second inciso
    check_instr(P, 26, "segundo inciso del artículo 122")
    u.insert("art-122", 1, pay(26))
    # 27. art. 124: 'desastre natural' -> 'desastre de origen natural'
    check_instr(P, 27, 'Sustitúyese en el artículo 124 la frase "desastre natural", por el siguiente texto: '
                       '"desastre de origen natural"')
    u.sub("art-124", "desastre natural", "desastre de origen natural")
    # 28, 29, 30. arts. 125, 127, 129 replaced
    for k, n in ((28, 125), (29, 127), (30, 129)):
        check_instr(P, k, f"Sustitúyese el artículo {n}")
        whole(k, n)
    # 31. art. 148: 'obligue, fuerce o' after 'la persona que'
    check_instr(P, 31, 'Agrégase en el artículo 148 a continuación de la frase: "la persona que", el siguiente '
                       'texto: "obligue, fuerce o"')
    u.sub("art-148", "La persona que haga abortar", "La persona que obligue, fuerce o haga abortar")
    # 32. art. 154.1
    check_instr(P, 32, "después del artículo 154")
    new_unit(32, "art-154-1", "Art. 154.1")
    # 33. art. 158 replaced
    check_instr(P, 33, "Sustitúyese el artículo 158")
    whole(33, 158)
    # 34. art. 159, first paragraph: 'de diez a treinta días' -> 'de quince a treinta días'
    check_instr(P, 34, 'En el primer párrafo del artículo 159 reemplácese la expresión: "de diez a treinta días", '
                       'por "de quince a treinta días"')
    u.sub("art-159", "de diez a treinta días", "de quince a treinta días", para=0)
    # 35. art. 163.1
    check_instr(P, 35, "a continuación del artículo 163")
    new_unit(35, "art-163-1", "Art. 163.1")
    # 36. art. 170: penalties in the second and third paragraphs
    check_instr(P, 36, 'En el segundo párrafo del artículo 170 reemplázase la frase "de cinco a siete años" por "de '
                       'siete a diez años". Y en el tercer párrafo, reemplázase la frase "de siete a diez años" por '
                       '"de diez a trece años"')
    u.sub("art-170", "de cinco a siete años", "de siete a diez años", para=1)
    u.sub("art-170", "de siete a diez años", "de diez a trece años", para=2)
    # 37. art. 171, numeral 5 (of the second list) replaced; 38. numeral 6 removed
    check_instr(P, 37, "Sustitúyese el número 5 del artículo 171")
    ps = u.paras("art-171")
    i5 = [i for i, p in enumerate(ps) if p.startswith("5. ")]
    if len(i5) != 1:
        raise SystemExit("S107 art. 37: numeral 5")
    u.set_para("art-171", i5[0], pay(37))
    check_instr(P, 38, "Suprímese el número 6 del artículo 171")
    u.delete_para("art-171", "6. ")
    # 39. art. 171.1
    check_instr(P, 39, "a continuación del artículo 171")
    new_unit(39, "art-171-1", "Art. 171.1")
    # 40. art. 172
    check_instr(P, 40, 'En el artículo 172, reemplázase la frase "de cinco a siete años" por "de siete a diez años"')
    u.sub("art-172", "de cinco a siete años", "de siete a diez años")
    # 41. art. 186: numeral 6 after numeral 5; 42. a final paragraph
    check_instr(P, 41, "Agrégase como número 6 del artículo 186")
    u.insert("art-186", u.find("art-186", "5. ") + 1, pay(41))
    check_instr(P, 42, "párrafo final del artículo 186")
    add_end(42, "art-186")
    # 43. art. 199: text added to the final inciso
    check_instr(P, 43, "Agrégase en el inciso final del artículo 199")
    ps = u.paras("art-199")
    ps[-1] = ps[-1] + " " + pay(43)[0]
    u.put("art-199", ps)
    # 44. art. 202 replaced
    check_instr(P, 44, "Sustitúyese el artículo 202")
    whole(44, 202)
    # 45. art. 204, numeral 1 replaced
    check_instr(P, 45, "Sustitúyese el número 1 del artículo 204")
    u.set_para("art-204", u.find("art-204", "1. "), pay(45))
    # 46. art. 217 replaced; 47. art. 217.1
    check_instr(P, 46, "Sustitúyese el artículo 217")
    whole(46, 217)
    check_instr(P, 47, "a continuación del artículo 217")
    new_unit(47, "art-217-1", "Art. 217.1")
    # 48, 49, 50, 51. arts. 220, 222, 246, 247 replaced
    for k, n in ((48, 220), (49, 222), (50, 246), (51, 247)):
        check_instr(P, k, f"Sustitúyese el artículo {n}")
        whole(k, n)
    # 52. heading 'PARÁGRAFO ÚNICO Contravención de maltrato y muerte de mascotas ...' replaced
    check_instr(P, 52, 'Sustitúyese el texto: "PARÁGRAFO ÚNICO Contravención de maltrato y muerte de mascotas y '
                       'animales de compañía"')
    heads.rename(u, "PARÁGRAFO ÚNICO Contravención de maltrato y muerte de mascotas o animales de compañía",
                 pay(52)[0])
    # 53, 54. arts. 249, 250 replaced
    for k, n in ((53, 249), (54, 250)):
        check_instr(P, k, f"Sustitúyese el artículo {n}")
        whole(k, n)
    # 55, 56. arts. 250.1, 250.2
    check_instr(P, 55, "a continuación del artículo 250,")
    new_unit(55, "art-250-1", "Art. 250.1")
    check_instr(P, 56, "a continuación del artículo 250.1")
    new_unit(56, "art-250-2", "Art. 250.2")
    # 57. a heading after art. 250.2; 58, 59. arts. 250.3, 250.4 under it
    check_instr(P, 57, "a continuación del artículo 250.2, el siguiente parágrafo")
    check_instr(P, 58, "el siguiente artículo")
    new_unit(58, "art-250-3", "Art. 250.3")
    check_instr(P, 59, "a continuación del artículo 250.3")
    new_unit(59, "art-250-4", "Art. 250.4")
    heads.insert(u, pay(57)[0], before="art-250-3")
    # 60. section headings of Capítulo cuarto renumbered (the act quotes them in title case)
    check_instr(P, 60, "Sustitúyese en el Capítulo Cuarto del Título IV del Libro Primero, lo siguiente:")
    line = P[60][0]
    pairs = re.findall(r'"([^"]+)" por "([^"]+)"', line)
    if len(pairs) != 4:
        raise SystemExit(f"S107 art. 60: {len(pairs)} pairs")
    olds = ["SECCIÓN SEGUNDA Delitos contra los recursos naturales", "SECCIÓN TERCERA Delitos contra la gestión ambiental",
            "SECCIÓN CUARTA Disposiciones comunes", "SECCIÓN QUINTA Delitos contra los recursos naturales no renovables"]
    for old, (quoted_old, new) in zip(olds, pairs):
        if quoted_old.lower().rstrip(".") != old.lower():
            raise SystemExit(f"S107 art. 60: {quoted_old!r} vs {old!r}")
        heads.rename(u, old, new.rstrip(".") if new.endswith("renovables.") else new)
    # 61, 62, 63, 64, 65, 66. arts. 256, 264, 265, 275, 276, 277 replaced
    for k, n in ((61, 256), (62, 264), (63, 265), (64, 275), (65, 276), (66, 277)):
        check_instr(P, k, f"artículo {n}")
        whole(k, n)
    # 67. art. 283, first paragraph replaced
    check_instr(P, 67, "Sustitúyese el párrafo primero del artículo 283")
    u.set_para("art-283", 0, pay(67))
    # 68. art. 289, fourth inciso replaced
    check_instr(P, 68, "Sustitúyese el cuarto inciso del artículo 289")
    u.set_para("art-289", 3, pay(68))
    # 69. art. 299, first inciso: 'natural o jurídica' after 'persona'
    check_instr(P, 69, 'En el primer inciso del artículo 299, luego de la frase "persona", agrégase "natural o jurídica"')
    u.sub("art-299", "La persona que", "La persona natural o jurídica que", para=0)
    # 70. art. 308, numeral 2 replaced
    check_instr(P, 70, "Sustitúyese el número 2 del artículo 308")
    u.set_para("art-308", u.find("art-308", "2. "), pay(70))
    # 71. art. 328.1
    check_instr(P, 71, "a continuación del artículo 328")
    new_unit(71, "art-328-1", "Art. 328.1")
    # 72. art. 359 repealed
    check_instr(P, 72, "Derógase el artículo 359.")
    u.remove("art-359")
    # 73. art. 393: numeral 6
    check_instr(P, 73, "Agréguese en el artículo 393, el siguiente número")
    add_end(73, "art-393")
    # 74. art. 412: a final paragraph
    check_instr(P, 74, "Al final del artículo 412 agrégase un párrafo")
    add_end(74, "art-412")
    # 75. art. 415: numeral 5
    check_instr(P, 75, "Agrégase en el artículo 415, un número 5")
    add_end(75, "art-415")
    # 76. art. 421: a final paragraph; 77. art. 427: a final paragraph
    check_instr(P, 76, "Al final del artículo 421 agrégase un párrafo")
    add_end(76, "art-421")
    check_instr(P, 77, "párrafo final del artículo 427")
    add_end(77, "art-427")
    # 78, 79. arts. 430.1, 430.2
    check_instr(P, 78, "a continuación del artículo 430 el siguiente")
    new_unit(78, "art-430-1", "Art. 430.1")
    check_instr(P, 79, "a continuación del artículo 430.1")
    new_unit(79, "art-430-2", "Art. 430.2")
    # 80. art. 443, numeral 4 (the last): text added at its end
    check_instr(P, 80, "Agrégase al final del número 4 del artículo 443")
    i = u.find("art-443", "4. ")
    ps = u.paras("art-443")
    ps[i] = ps[i] + " " + pay(80)[0]
    u.put("art-443", ps)
    # 81. art. 457: a final paragraph
    check_instr(P, 81, "Incorpórase al final del artículo 457 el siguiente párrafo")
    add_end(81, "art-457")
    # 82. art. 474.1
    check_instr(P, 82, "a continuación del artículo 474")
    new_unit(82, "art-474-1", "Art. 474.1")
    # 83. art. 478: paragraphs after numeral 3 (the last)
    check_instr(P, 83, "Agrégase al final del número 3 del artículo 478, los siguientes párrafos")
    add_end(83, "art-478")
    # 84. art. 491 replaced
    check_instr(P, 84, "Sustitúyese el artículo 491")
    whole(84, 491)
    # 85. art. 493: a final paragraph
    check_instr(P, 85, "párrafo final del artículo 493")
    add_end(85, "art-493")
    # 86. art. 520: numeral 9
    check_instr(P, 86, "Agrégase en el artículo 520 el siguiente número")
    add_end(86, "art-520")
    # 87. art. 529.1
    check_instr(P, 87, "a continuación del artículo 529")
    new_unit(87, "art-529-1", "Art. 529.1")
    # 88. art. 534 replaced
    check_instr(P, 88, "Sustitúyese el artículo 534")
    whole(88, 534)
    # 89. art. 536: a final paragraph
    check_instr(P, 89, "Al final del artículo 536, agrégase el siguiente párrafo")
    add_end(89, "art-536")
    # 90. art. 537: numeral 4 after numeral 3 (before the closing inciso)
    check_instr(P, 90, "Agrégase al artículo 537 un número 4")
    u.insert("art-537", u.find("art-537", "3. ") + 1, pay(90))
    # 91. art. 544: numeral 4 replaced, numeral 5 added
    check_instr(P, 91, "Sustitúyese el número 4 del artículo 544 y agrégase un número 5 final")
    new = pay(91)
    i = u.find("art-544", "4. ")
    u.set_para("art-544", i, new)
    # 92. art. 558, numeral 12: a sentence at the end of its first paragraph; 'de existir méritos.' removed from the
    #     second
    check_instr(P, 92, 'En el párrafo primero del número 12 del artículo 558 agrégase al final, el siguiente texto: "En '
                       'caso de ratificarse la presunción de inocencia del procesado, la medida se revocará."; y, en el '
                       'segundo párrafo elimínese la frase: "de existir méritos."')
    a, b = span(u, "art-558", 12)
    ps = u.paras("art-558")
    ps[a] = ps[a] + " En caso de ratificarse la presunción de inocencia del procesado, la medida se revocará."
    u.put("art-558", ps)
    # the act quotes the phrase with its own closing stop ('de existir méritos.'); the paragraph reads 'la o el fiscal
    # de existir méritos, solicitará', so the words are removed and the comma stays (see decisions)
    u.drop("art-558", "de existir méritos", para=a + 1)
    # 93. art. 570: heading and first inciso replaced (one paragraph)
    check_instr(P, 93, "Sustitúyese el epígrafe e inciso primero del artículo 570")
    u.set_para("art-570", 0, pay(93), count=2)
    # 94. art. 575: numeral 6
    check_instr(P, 94, "Agrégase en el artículo 575 el siguiente número")
    add_end(94, "art-575")
    # 95. art. 585, numeral 3: second paragraph
    check_instr(P, 95, "como segundo párrafo del número 3 del artículo 585")
    u.insert("art-585", u.find("art-585", "3. ") + 1, pay(95))
    # 96. art. 630: a final paragraph
    check_instr(P, 96, "Agrégase en el artículo 630, el siguiente párrafo final")
    add_end(96, "art-630")
    # 97. art. 634: numeral 5
    check_instr(P, 97, "Agrégase un número al artículo 634")
    add_end(97, "art-634")
    # 98. art. 635, numeral 1 replaced (printed '1. 1. Las infracciones ...', see decisions)
    check_instr(P, 98, "Sustitúyese el número 1 del artículo 635")
    u.set_para("art-635", u.find("art-635", "1. "), pay(98))
    # 99, 100. arts. 640, 641 replaced
    check_instr(P, 99, "Sustitúyese el artículo 640")
    whole(99, 640)
    check_instr(P, 100, "Sustitúyese el artículo 641")
    whole(100, 641)
    # 101. art. 647: numeral 5 after numeral 4 (the last)
    check_instr(P, 101, "a continuación del número 4 del artículo 647 un número 5")
    add_end(101, "art-647")
    # 102. after art. 651: a new section heading and arts. 651.1 to 651.6
    check_instr(P, 102, "Incorporánse a continuación del artículo 651 los siguientes textos")
    block = unq(P[102])
    if not block[0].startswith("Sección Quinta Procedimiento unificado"):
        raise SystemExit("S107 art. 102: heading")
    starts = [i for i, p in enumerate(block) if re.match(r"Artículo\.? 651\.\d\.-", p)]
    if len(starts) != 6:
        raise SystemExit(f"S107 art. 102: {len(starts)} articles")
    for j, i in enumerate(starts):
        stop = starts[j + 1] if j + 1 < len(starts) else len(block)
        u.set_unit(f"art-651-{j + 1}", block[i:stop], label=f"Art. 651.{j + 1}")
    heads.insert(u, block[0], before="art-651-1")
    # 103. art. 653: numeral 6
    check_instr(P, 103, "Agrégase en el artículo 653, el siguiente número")
    add_end(103, "art-653")
    # 104. art. 669: an inciso after the second; 105. a final paragraph
    check_instr(P, 104, "En el artículo 669, agréguese el siguiente inciso a continuación del segundo")
    u.insert("art-669", 2, pay(104))
    check_instr(P, 105, "Agrégase al artículo 669, el siguiente párrafo final")
    add_end(105, "art-669")
    # 106. art. 670: final paragraphs
    check_instr(P, 106, "Agréganse al final del artículo 670 los siguientes párrafos")
    add_end(106, "art-670")
    # 107, 108, 109. arts. 672, 673, 674 replaced
    for k, n in ((107, 672), (108, 673), (109, 674)):
        check_instr(P, k, f"Sustitúyese el artículo {n}")
        whole(k, n)
    # 110. art. 677, first inciso replaced: the payload is the article's head and first inciso, which in the Code
    #      are the first two paragraphs ('... El Centro ...' and 'Sus funciones serán:')
    check_instr(P, 110, "Sustitúyese el inciso primero del artículo 677")
    new = pay(110)
    if not new[0].endswith("sus funciones serán:"):
        raise SystemExit("S107 art. 110: payload")
    u.set_para("art-677", 0, new, count=2)
    # 111. art. 678, numeral 2, second paragraph replaced
    check_instr(P, 111, "Sustitúyese el segundo párrafo del número 2 del artículo 678")
    u.set_para("art-678", u.find("art-678", "2. ") + 1, pay(111))
    # 112. art. 694, last inciso replaced
    check_instr(P, 112, "Sustitúyese el último inciso del artículo 694")
    u.set_para("art-694", u.count("art-694") - 1, pay(112))
    # 113, 114, 115, 116. arts. 698, 699, 708, 722 replaced
    for k, n in ((113, 698), (114, 699), (115, 708), (116, 722)):
        check_instr(P, k, f"Sustitúyese el artículo {n}")
        whole(k, n)
    # 117. art. 723: numeral 12; 118. art. 724: numeral 6
    check_instr(P, 117, "Agrégase como número 12 del artículo 723")
    add_end(117, "art-723")
    check_instr(P, 118, "Agrégase como número 6 del artículo 724")
    add_end(118, "art-724")
    # 119, 120, 121. Disposiciones generales sexta, séptima, octava
    for k, n, word in ((119, 6, "sexta"), (120, 7, "séptima"), (121, 8, "octava")):
        check_instr(P, k, f"Agrégase como Disposición General {word.capitalize()}")
        key = f"disp-general-{n:02d}"
        u.set_unit(key, pay(k), label=f"Disposición general {word}")
        u.u[key]["kind"] = "general"
