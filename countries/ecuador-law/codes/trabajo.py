"""Write corpus.d/90-trabajo.json: the Código del Trabajo (Codificación 2005-017) and its amending acts.

Reads only the cache (editions located and fetched with `python -X utf8 codes/editions_trabajo.py`). Deterministic:
the same cache gives the same bytes. The part is written atomically (.tmp, then rename).

    python -X utf8 codes/trabajo.py            (TRABAJO_OUT=... to write elsewhere)

Base: Registro Oficial Suplemento 167, 16-XII-2005 (text layer). Amending acts from the 'Nota:' lines of a Lexis-style
consolidation to 1-II-2023 (codes/index_docx.py trabajo, reading only), the SRI's consolidation to 27-VI-2024 (notes
in parentheses, codes/reconcile_trabajo.py --sri, reading only) and the Asamblea's law list screened by text
layer for 2023-2026 (codes/screen.py -> codes/screen_trabajo.json, reading only). Every word is cut from the text layer
of a gazette edition; editions that are page images only are NOT applied (no OCR).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "civil"))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import fetch  # noqa: E402
import rotext  # noqa: E402
import replay as civil_replay  # noqa: E402
from replay import Src, Units, unquote  # noqa: E402,F401
import strict  # noqa: E402

OUT = Path(os.environ.get("TRABAJO_OUT", HERE.parent / "corpus.d" / "90-trabajo.json"))
RETRIEVED = "2026-10-29"
EDITIONS = json.loads((HERE / "editions_trabajo.json").read_text(encoding="utf-8"))


def ed(name: str, title: str) -> str:
    return next(e["pdf"] for e in EDITIONS[name] if e["title"] == title)


S167_2005 = ed("s167-2005", "Primer Suplemento")

ORD = ["PRIMERA", "SEGUNDA", "TERCERA", "CUARTA", "QUINTA", "SEXTA", "SÉPTIMA", "OCTAVA", "NOVENA", "DECIMA"]
ORD_LOW = ["primera", "segunda", "tercera", "cuarta", "quinta", "sexta", "séptima", "octava", "novena", "décima"]
HEAD = re.compile(r"^(T[ÍI]TULO|Cap[íi]tulo|CAP[ÍI]TULO|Par[áa]grafo|PAR[ÁA]GRAFO|Secci[óo]n|SECCI[ÓO]N)\b")
ART = re.compile(r"^Art\.\s*(\d+)\s*\.?\s*-")
# literals the text layer sets in one paragraph ("...; f) Los contratos a prueba;") go one per line, in the base and in
# the amending acts' quoted text alike
ITEM = re.compile(r"(?<=[:;,.]) (?=[a-z]\) [A-ZÁÉÍÓÚÑ¿\"])")


def split_items(ps: list[str]) -> list[str]:
    out: list[str] = []
    for p in ps:
        out.extend(ITEM.split(p))
    return out


def art_key(n: int, extra: str = "") -> str:
    return f"art-{n:04d}" + (f"-{extra}" if extra else "")


def order(key: str) -> tuple:
    m = re.match(r"art-(\d{4})(?:-(\d+))?$", key)
    if m:
        return (1, int(m.group(1)), int(m.group(2) or 0), "")
    rank = {"disp-general": 2, "disp-transitoria": 3, "disp-final": 5, "titulos": 6}
    base = re.sub(r"-\d+$", "", key)
    return (rank.get(base, 7), 0, 0, key)


def sha_of(url: str) -> str:
    return hashlib.sha256(fetch.cached(url).read_bytes()).hexdigest()


class SSrc(Src):
    """A gazette edition read through codes/strict.py (stray overlay fragments dropped)."""
    _cache: dict[str, "SSrc"] = {}

    def __new__(cls, url: str):
        if url in cls._cache:
            return cls._cache[url]
        self = object.__new__(cls)
        path = fetch.cached(url)
        if path is None:
            raise SystemExit(f"not in cache: {url}")
        self.url = url
        self.paras = [civil_replay.fix_layer(p) for p in strict.paragraphs(path)]
        self.flat = re.sub(r"\s+", " ", "\n".join(self.paras))
        cls._cache[url] = self
        return self


# ---------------------------------------------------------------- base

def base_units() -> dict:
    path = fetch.cached(S167_2005)
    if path is None:
        raise SystemExit(f"not in cache: {S167_2005}")
    ps = rotext.paragraphs(path)
    start = ps.index("TÍTULO PRELIMINAR DISPOSICIONES FUNDAMENTALES")
    units: dict[str, dict] = {}
    heads: list[str] = []
    cur: str | None = None
    pending: list[str] = []  # "De la Ley 133, ...:" lines that head the next transitoria
    expect = 1
    trans = False
    in_head = False
    for p in ps[start:]:
        if p.startswith("Esta Codificación fue elaborada"):
            break
        m = ART.match(p)
        if not trans and m:
            n = int(m.group(1))
            if n != expect:
                raise SystemExit(f"article {n} where {expect} was expected")
            expect += 1
            cur = art_key(n)
            units[cur] = {"label": f"Art. {n}", "kind": "art", "text": ""}
        elif p == "DISPOSICIONES TRANSITORIAS" and expect == 638:
            trans = True
            heads.append(p)
            cur = None
            continue
        elif trans and re.match(r"^De la Ley [\d-]+", p):
            pending.append(p)
            continue
        elif trans and re.match(r"^(%s)\.-" % "|".join(ORD), p):
            i = ORD.index(p.split(".-")[0])
            cur = f"disp-transitoria-{i + 1:02d}"
            units[cur] = {"label": f"Disposición transitoria {ORD_LOW[i]}", "kind": "transitional",
                          "text": "".join(x + "\n" for x in pending)}
            pending = []
        elif trans and p.startswith("ARTÍCULO FINAL.-"):
            cur = "disp-final"
            units[cur] = {"label": "Artículo final", "kind": "final", "text": ""}
        elif not trans and (HEAD.match(p) or cur is None):
            heads.append(p)
            in_head = True
            continue
        elif in_head and not trans:
            # a heading set on two lines ("Capítulo XI Del fondo de reserva, de su disponibilidad y de la" +
            # "jubilación Parágrafo 1ro. Del fondo de reserva"): joined, then split before a following heading
            heads[-1:] = re.split(r" (?=Par[áa]grafo \d)", heads[-1] + " " + p)
            continue
        in_head = False
        if cur is None:
            raise SystemExit(f"text outside a unit: {p[:60]!r}")
        units[cur]["text"] += "".join(x + "\n" for x in split_items([p]))
    if expect != 638 or pending:
        raise SystemExit(f"stopped at article {expect - 1}")
    units["titulos"] = {"label": "Títulos, capítulos y parágrafos", "kind": "headings",
                        "text": "".join(h + "\n" for h in heads)}
    return dict(sorted(units.items(), key=lambda kv: order(kv[0])))


# ---------------------------------------------------------------- helpers for the amending acts

STRAY_ACCENT = re.compile(r"(?<=[áéíóúÁÉÍÓÚ])́+")


def q(s: Src, anchor: str, count: int = 1, after: str | None = None) -> list[list[str]]:
    """Quoted blocks after an anchor, literals one per line; a combining acute accent the text layer sets after an
    already accented vowel ('convocará́') is dropped (decisions)."""
    return [split_items([STRAY_ACCENT.sub("", p) for p in b]) for b in s.quoted(anchor, count=count, after=after)]


def whole(u: Units, s: Src, n: int, anchor: str, after: str | None = None, key: str | None = None) -> None:
    (b,) = q(s, anchor, after=after)
    if not re.match(rf"Art\.?\s*{n}\s*\.?\s*-", b[0]):
        raise SystemExit(f"art. {n}: quoted text starts {b[0][:30]!r}")
    u.set_unit(key or art_key(n), b)


def innominate(u: Units, after_n: int, block: list[str], start: int = 1) -> list[str]:
    """Split a quoted block of 'Art. ...-' articles into units art-NNNN-1, -2 ... placed after art. after_n."""
    arts: list[list[str]] = []
    for p in block:
        if re.match(r"^Art\.\s*\.{3}|^Art\.{3}\s|^Art\.\s*\(\.\.\.\)|^Art\.\s*innumerado", p):
            arts.append([p])
        elif arts:
            arts[-1].append(p)
        else:
            raise SystemExit(f"text before the first article: {p[:40]!r}")
    keys = []
    for i, a in enumerate(arts, start):
        k = art_key(after_n, str(i))
        u.set_unit(k, a, label=f"Art. innumerado {i} (tras el art. {after_n})")
        keys.append(k)
    return keys


def paras_after(s: Src, anchor: str, n: int, after: str | None = None, tail: str = '"') -> list[str]:
    """The n paragraphs after the one holding `anchor`, for quotations Src.quoted cannot close (the act ends the
    quotation with '"; y,' or similar): the opening quote and the closing `tail` are stripped and must be there."""
    i = s.index(anchor, after) + 1
    b = list(s.paras[i:i + n])
    if not (b[0].startswith('"') and b[-1].endswith(tail)):
        raise SystemExit(f"quotation after {anchor!r} not as expected: {b[0][:30]!r} ... {b[-1][-30:]!r}")
    b[0] = b[0][1:]
    b[-1] = b[-1][:-len(tail)]
    for x in b:
        if x.count('"') % 2:
            raise SystemExit(f"unbalanced quote: {x[:80]!r}")
    return split_items(b)


def heading_before(u: Units, before: str, lines: list[str]) -> None:
    ps = u.paras("titulos")
    i = ps.index(before)
    u.put("titulos", ps[:i] + lines + ps[i:])


def literal(u: Units, key: str, prefix: str) -> int:
    return u.find(key, prefix)


# ---------------------------------------------------------------- the amending acts (text layer)

RO198_2006 = ed("ro198-2006", "Registro Oficial")
RO223_2006 = ed("ro223-2006", "Registro Oficial")
RO250_2006 = ed("ro250-2006", "Registro Oficial")


def ley_2006_28(u: Units) -> None:
    """Ley 2006-28 Reformatoria al Código del Trabajo (RO 198, 30-I-2006), numerals 1 and 2 of its art. 1: the parts
    that fit the codified text as published (the rest waits for the fe de erratas of RO 223)."""
    s = Src(RO198_2006)
    s.check("Artículo Final.- La presente Ley Reformatoria, entrará en vigencia a partir de su publicación en el Registro Oficial.")
    (b,) = q(s, "1. Sustitúyese el numeral 2, por el siguiente:")
    u.set_para("art-0042", u.find("art-0042", "2. Instalar"), b)
    (b,) = q(s, "2. Sustitúyase el numeral 33, por el siguiente:")
    u.set_para("art-0042", u.find("art-0042", "33. Contratar"), b)


def erratas_2006_28(u: Units) -> None:
    """Fe de erratas (RO 223, 7-III-2006) of Ley 2006-28: its art. 1 num. 3 adds numeral 35 after numeral 34, its
    art. 2 adds the Título after art. 346 and its art. 3 substitutes art. 403 (the published text named numeral 35,
    art. 352 and art. 409, the numbering before the 2005 codification)."""
    e = Src(RO223_2006)
    e.check('En el numeral 3 del artículo 1, donde dice: "Sustitúyase el numeral 35, por el siguiente:", debe decir: '
            '"A continuación del numeral 34, agrégase el siguiente:"',
            'debe decir: "A continuación del artículo 346, añádase el siguiente Título:"',
            'debe decir: "Sustitúyase el artículo 403, por el siguiente: ".')
    s = Src(RO198_2006)
    (b,) = q(s, "3. Sustitúyase el numeral 35, por el siguiente:")
    ps = u.paras("art-0042")
    i = u.find("art-0042", "34. Contratar")
    u.insert("art-0042", i + 1, b)
    (b,) = q(s, "Art. 2.- A continuación del artículo 352, añádase el siguiente Título:")
    if not (b[0] == "TITULO ...." and b[1] == "DEL TRABAJO PARA PERSONAS CON DISCAPACIDAD"):
        raise SystemExit(f"Ley 2006-28 art. 2: {b[:2]}")
    heading_before(u, "TÍTULO IV DE LOS RIESGOS DEL TRABAJO", [b[0] + " " + b[1]])
    innominate(u, 346, b[2:])
    (b,) = q(s, "Art. 3.- Sustitúyase el artículo 409, por el siguiente:")
    b[0] = re.sub(r"^Art\. 409\.-", "Art. 403.-", b[0])  # the fe de erratas corrects the article's number
    whole_ = b
    if not whole_[0].startswith("Art. 403.- Prescripción de las acciones.-"):
        raise SystemExit("Ley 2006-28 art. 3")
    u.set_unit("art-0403", whole_)
    del ps


def comma_end(b: list[str]) -> list[str]:
    """unquote() adds the act's full stop to a quoted text that ends without one; a literal that ends '; y,' keeps
    its comma (the stop after the closing quote ends the act's sentence)."""
    b = list(b)
    if b[-1].endswith(",."):
        b[-1] = b[-1][:-1]
    return b


def ley_2006_39(u: Units) -> None:
    """Ley 2006-39 Reformatoria al Código del Trabajo (RO 250, 13-IV-2006), in force on publication (its Artículo
    final). Edits whose target words do not occur once in the codified text are not applied (decisions)."""
    s = Src(RO250_2006)
    s.check("Artículo Final.- La presente Ley entrará en vigencia a partir de su publicación en el Registro Oficial.")
    # art. 1: a new literal k) in art. 19; the former k) becomes l)
    (b,) = q(s, 'Art. 1.- En el artículo 19, inclúyese como literal k), el siguiente:')
    s.check("El actual literal k) pasa a ser literal l), con el mismo contenido.")
    i = u.find("art-0019", "k) En general")
    u.sub("art-0019", "k) En general", "l) En general", para=i)
    u.insert("art-0019", i, comma_end(b))
    (b,) = q(s, "Art. 2.- En el artículo 20, añádanse los siguientes incisos:")
    u.insert("art-0020", u.count("art-0020"), b)
    whole(u, s, 35, "Art. 3.- Sustitúyese el artículo 35, por el siguiente:")
    whole(u, s, 134, "Art. 4.- Sustitúyese el artículo 134, por el siguiente:")
    s.check('a) Luego de la palabra: "...contrataren", añádese: "mayores de quince años y"; además, sustitúyese: '
            '"...instrucción primaria", por: "instrucción básica"')
    u.sub("art-0135", "contrataren menores", "contrataren mayores de quince años y menores")
    u.sub("art-0135", "instrucción primaria", "instrucción básica")
    (b,) = q(s, "b) Agréguense los siguientes incisos:", after="Art. 5.- En el artículo 135")
    u.insert("art-0135", u.count("art-0135"), b)
    whole(u, s, 136, "Art. 6.- Sustitúyese el artículo 136, por el siguiente:")
    whole(u, s, 138, "Art. 7.- Sustitúyese el artículo 138, por el siguiente:")
    # art. 8 b): the scale of art. 139 (letter a), 'menores' -> 'adolescentes de quince años', names a word that occurs
    # twice in the article and is not applied)
    i = s.index("b) Sustitúyese los límites máximos de carga de acuerdo a la siguiente escala:",
                after="Art. 8.- En el artículo 139")
    scale = s.paras[i + 1]
    if not scale.startswith("Varones de 15 a 18 años 25 libras"):
        raise SystemExit(f"Ley 2006-39 art. 8: {scale[:40]!r}")
    u.set_para("art-0139", u.find("art-0139", "LÍMITES MÁXIMOS DE CARGA"), [scale])
    s.check('Art. 9.- En el artículo 141, luego de la palabra: "... trabajadores", añádese: "... mayores de dieciocho años y".',
            'Art. 10.- En el artículo 144, luego de la palabra: "...personas", añádese: "...mayores de dieciocho años y".',
            "Art. 11.- Derógase el artículo 146 del Código del Trabajo.")
    u.sub("art-0141", "trabajadores menores", "trabajadores mayores de dieciocho años y menores")
    u.sub("art-0144", "personas menores", "personas mayores de dieciocho años y menores")
    u.remove("art-0146")
    whole(u, s, 147, "Art. 12.- Sustitúyese el artículo 147, por el siguiente:")
    (b,) = q(s, "Art. 13.- En el artículo 148, añádese el siguiente inciso:")
    u.insert("art-0148", u.count("art-0148"), b)
    s.check('Art. 14.- En el título del artículo 149, reemplácese: "... menores", por: "adolescentes"; y, luego de: '
            '"...reglamento aprobado", añádese la siguiente frase: "... o lo prescrito en el TITULO V del LIBRO I del '
            'Código de la Niñez y Adolescencia".')
    u.sub("art-0149", "enfermedades de menores atribuidos", "enfermedades de adolescentes atribuidos")
    u.sub("art-0149", "reglamento aprobado", "reglamento aprobado o lo prescrito en el TITULO V del LIBRO I del Código "
          "de la Niñez y Adolescencia")
    s.check('a) En lugar de: "Consejo Nacional de la Niñez y Adolescencia", deberá decir: "... los jueces de la niñez y '
            'adolescencia y las juntas cantonales de protección de derechos";',
            'b) Sustitúyese: "menores de edad", por: "adolescentes menores de quince años"; y,')
    # 'el Consejo Nacional ...' -> 'los jueces ...': the article 'el' goes with the name it introduced
    u.sub("art-0151", "el Consejo Nacional de la Niñez y Adolescencia",
          "los jueces de la niñez y adolescencia y las juntas cantonales de protección de derechos")
    u.sub("art-0151", "menores de edad", "adolescentes menores de quince años")
    (b,) = q(s, "c) Añádase los siguientes incisos:", after="Art. 15.- En el artículo 151")
    u.insert("art-0151", u.count("art-0151"), b)
    (b,) = q(s, "Art. 16.- Sustitúyese el primer inciso del artículo 156, por el siguiente:")
    u.set_para("art-0156", 0, b)
    # art. 17 a) (numeral 1 of art. 158) names a semicolon and words the codified numeral already holds in other
    # words: not applied; b) 'Agréguese como numeral 4': the article already has a numeral 4, so the new one follows it
    (b,) = q(s, "b) Agréguese como numeral 4, el siguiente:", after="Art. 17.- En el artículo 158")
    u.insert("art-0158", u.count("art-0158"), b)
    whole(u, s, 168, "Art. 18.- Sustitúyese el artículo 168, por el siguiente:")
    (b,) = q(s, "Art. 19.- Al artículo 262, agréguese como tercer inciso, el siguiente:")
    u.insert("art-0262", 2, b)
    s.check('Art. 20.- En el artículo 268, en lugar de la última frase: "Si es menor impúber estará el empleador obligado '
            'a darle instrucción primaria", deberá decir:')
    new = s.inline('Art. 20.- En el artículo 268, en lugar de la última frase: "Si es menor impúber estará el empleador '
                   'obligado a darle instrucción primaria", deberá decir:') or None
    if not new:
        (nb,) = s.quoted('Art. 20.- En el artículo 268, en lugar de la última frase:')
        new = nb[0]
    u.sub("art-0268", "Si es menor impúber estará el empleador obligado a darle instrucción primaria", new.rstrip("."))
    b = paras_after(s, "a) Sustitúyese los incisos segundo y tercero, por los siguientes:", 2,
                    after="Art. 21.- En el artículo 616", tail='"; y,')
    u.set_para("art-0616", 1, b, count=2)
    (b,) = q(s, "b) Añádese como inciso final, el siguiente:", after="Art. 21.- En el artículo 616")
    u.insert("art-0616", u.count("art-0616"), b)
    # art. 22 ('menores de edad' occurs twice in art. 381) and art. 23 ('Tribunal de Menores', in neither art. 381 nor
    # art. 402) are not applied


RO259_2006 = ed("ro259-2006", "Registro Oficial")
S298_2006 = ed("s298-2006", "Primer Suplemento")
RO340_2006 = ed("ro340-2006", "Registro Oficial")
S387_2006 = ed("s387-2006", "Primer Suplemento")
RO75_2007 = ed("ro75-2007", "Registro Oficial")
S330_2008 = ed("s330-2008", "Primer Suplemento")
S528_2009 = ed("s528-2009", "Primer Suplemento")
S351_2010 = ed("s351-2010", "Primer Suplemento")
S372_2011 = ed("s372-2011", "Primer Suplemento")
S797_2012 = ed("s797-2012", "Segundo Suplemento")
S332_2014 = ed("s332-2014", "Segundo Suplemento")


def ley_2006_40(u: Units) -> None:
    """Ley 2006-40 Reformatoria del Código del Trabajo (RO 259, 27-IV-2006): five articles innumerados after art. 156
    (medical examination of minors) and a numeral 10 in art. 542. No vigencia clause: in force on publication."""
    s = Src(RO259_2006)
    (b,) = q(s, "Art. 1.- A continuación del artículo 156, agréguense los siguientes artículos innumerados:")
    innominate(u, 156, b)
    (b,) = q(s, "Art. 2.- El numeral 10 del artículo 542 del Código del Trabajo, pasa a ser 11 y agréguese como numeral 10,")
    i = u.find("art-0542", "10. Las demás atribuciones")
    u.sub("art-0542", "10. Las demás atribuciones", "11. Las demás atribuciones", para=i)
    u.insert("art-0542", i, b)


def ley_2006_48(u: Units) -> None:
    """Ley 2006-48 Reformatoria al Código del Trabajo (Suplemento 298, 23-VI-2006): a Capítulo on intermediación
    laboral and tercerización after art. 346, at the end of Título III, and an article after art. 557; in force on
    publication (its Disposición final segunda)."""
    s = Src(S298_2006)
    s.check("SEGUNDA.- La presente Ley Reformatoria entrará en vigencia a partir de su publicación en el Registro Oficial.")
    (b,) = q(s, "Art. 1.- Al final del TITULO III y luego del artículo 346 del Código del Trabajo, incorpórese el siguiente Capítulo:")
    if not (b[0] == "CAPITULO ..." and b[1].startswith("DE LA INTERMEDIACION LABORAL")):
        raise SystemExit(f"Ley 2006-48 art. 1: {b[:2]}")
    heading_before(u, "TITULO .... DEL TRABAJO PARA PERSONAS CON DISCAPACIDAD", [b[0] + " " + b[1]])
    keys = innominate(u, 346, b[2:], start=4)
    if len(keys) != 21:
        raise SystemExit(f"Ley 2006-48: {len(keys)} articles")
    (b,) = q(s, "Art. 2.- A continuación del artículo 557, agréguese el siguiente artículo innumerado:")
    innominate(u, 557, b)


def erratas_2006_216(u: Units) -> None:
    """Fe de erratas of the codification (RO 340, 23-VIII-2006), Comisión de Legislación y Codificación: art. 216
    num. 2, first inciso."""
    s = Src(RO340_2006)
    s.check('1.- En el primer inciso del numeral 2 del artículo 216, se dice: "remuneración básica mínima unificada '
            'medio", debiendo corregirse por la siguiente expresión: "remuneración básica unificada media".')
    u.sub("art-0216", "remuneración básica mínima unificada medio", "remuneración básica unificada media", para="2. ")


def ley_2006_60(u: Units) -> None:
    """Ley 2006-60 Reformatoria al Código del Trabajo (Suplemento 387, 30-X-2006): an article after art. 304 (mining
    workers). No vigencia clause: in force on publication."""
    s = Src(S387_2006)
    (b,) = q(s, "Art. 1.- A continuación del artículo 304, incorpórese el siguiente:")
    innominate(u, 304, b)


def ley_2007_77(u: Units) -> None:
    """Ley Reformatoria al Código del Trabajo (RO 75, 2-V-2007): first inciso of art. 113 (decimocuarta
    remuneración); in force on publication (its art. 2)."""
    s = Src(RO75_2007)
    s.check("Art. 2.- La presente Ley reformatoria entrará en vigencia desde la fecha de su publicación en el Registro Oficial.")
    (b,) = q(s, "Art. 1.- Sustitúyese el primer inciso del artículo 113, por el siguiente:")
    u.set_para("art-0113", 0, b)


def mandato_8(u: Units) -> None:
    """Mandato Constituyente No. 8 (Asamblea Constituyente, 30-III-2008; Suplemento 330, 6-V-2008), Disposición final
    primera: repeals Ley 2006-48 and, in the Code, art. 11 literal h), 14 literal g), the phrase 'por horas' and the
    sixth to thirteenth incisos of art. 17, 19 literal j), 41 second inciso and the words 'o intermediarios' of art.
    100. In force 'en forma inmediata, sin perjuicio de su publicación' (Disposición final tercera)."""
    s = Src(S330_2008)
    s.check('PRIMERA: Deróguese la Ley Reformatoria al Código de Trabajo, mediante la cual se reguló la actividad de '
            'intermediación laboral y la de tercerización de servicios complementarios, publicada en el Suplemento del '
            'Registro Oficial 298 de 23 de junio del 2006; los artículos 11 literal h), 14 literal g), 17 la frase: '
            '"por horas" incisos sexto al décimotercero, 19 literal j), 41 inciso 2º y las palabras "o intermediarios" '
            'del artículo 100 de la Codificación del Código del Trabajo;',
            "entrará en vigencia en forma inmediata, sin perjuicio de su publicación en la Gaceta Constituyente y/o en "
            "el Registro Oficial.")
    for k in [k for k in u.u if re.fullmatch(r"art-0346-(\d+)", k) and int(k.rsplit("-", 1)[1]) >= 4] + ["art-0557-1"]:
        u.remove(k)
    ps = u.paras("titulos")
    ps.remove("CAPITULO ... DE LA INTERMEDIACION LABORAL Y DE LA TERCERIZACION DE SERVICIOS COMPLEMENTARIOS")
    u.put("titulos", ps)
    # art. 11 h) 'Por horas.' is the last literal: g) keeps its '; y,' as printed
    u.delete_para("art-0011", "h) Por horas.")
    u.delete_para("art-0014", "g) Los que se pacten por horas")
    ps = u.paras("art-0017")
    if len(ps) != 13 or not ps[5].startswith("Son contratos por hora aquellos"):
        raise SystemExit("art. 17: incisos not as expected")
    u.put("art-0017", ps[:5])
    u.drop("art-0017", "por horas")
    u.delete_para("art-0019", "j) Los que se pacten por horas")
    ps = u.paras("art-0041")
    if len(ps) != 2:
        raise SystemExit("art. 41: expected two incisos")
    u.put("art-0041", ps[:1])
    ps = u.paras("art-0100")
    if sum(p.count(" o intermediarios") for p in ps) != 3:
        raise SystemExit("art. 100: 'o intermediarios' not found three times")
    u.put("art-0100", [p.replace(" o intermediarios", "") for p in ps])


def ley_2009_licencias(u: Units) -> None:
    """Ley Orgánica Reformatoria a la LOSCCA y al Código del Trabajo (Suplemento 528, 13-II-2009): art. 152
    substituted (maternity and paternity leave) and two articles innumerados after it; in force on publication."""
    s = Src(S528_2009)
    s.check("La presente Ley entrará en vigencia a partir de su publicación en el Registro Oficial.")
    i = s.index("Art. 4.- Sustitúyase el artículo 152 del Código del Trabajo por el siguiente:")
    j = s.index("Art. 5.- A continuación del artículo 152 agréguese los siguientes artículos innumerados:")
    k = s.index("DISPOSICION GENERAL UNICA.-")
    if j - i != 5 or k - j != 4:
        raise SystemExit("Suplemento 528: layout not as expected")
    # printed without quotation marks and without the article's number and heading
    u.set_unit("art-0152", s.paras[i + 1:j])
    innominate(u, 152, s.paras[j + 1:k])


S644_2009 = ed("s644-2009", "Primer Suplemento")


def ley_fondo_reserva_2009(u: Units) -> None:
    """Ley para el Pago Mensual del Fondo de Reserva y Régimen Solidario de Cesantía por parte del Estado (Suplemento
    644, 29-VII-2009), art. 4 (arts. 95 and 201); in force on publication (its Disposición final). Where the act
    inserts or removes words of a series, the commas of the series are kept once (decisions)."""
    s = Src(S644_2009)
    s.check('1.- En el artículo 95, luego de la palabra "utilidades" inclúyase las palabras "el pago mensual del fondo de '
            'reserva,"; suprímase las palabras "decimoquinto y decimosexto sueldos"; y entre decimotercera y decimocuarta '
            'remuneraciones agréguese la conjunción "y".',
            '2.- En el artículo 201 elimínese la palabra "o anualmente", y al final del artículo luego de la palabra '
            '"Instituto", añádese "y en el caso de que el trabajador haya decidido no recibirla de manera mensual y '
            'directa por parte del empleador."',
            "Disposición Final.- Esta ley entrará en vigencia desde la fecha de su publicación en el Registro Oficial.")
    u.sub("art-0095", "el porcentaje legal de utilidades, los viáticos",
          "el porcentaje legal de utilidades, el pago mensual del fondo de reserva, los viáticos", para=1)
    u.sub("art-0095", "remuneraciones, decimoquinto y decimosexto sueldos, componentes", "remuneraciones, componentes",
          para=1)
    u.sub("art-0095", "la decimotercera, decimocuarta remuneraciones", "la decimotercera y decimocuarta remuneraciones",
          para=1)
    u.drop("art-0201", "o anualmente")
    u.sub("art-0201", "a dicho Instituto.", "a dicho Instituto y en el caso de que el trabajador haya decidido no "
          "recibirla de manera mensual y directa por parte del empleador.")


def copci_2010(u: Units) -> None:
    """Código Orgánico de la Producción, Comercio e Inversiones (Suplemento 351, 29-XII-2010), Disposición
    reformatoria quinta; in force on publication. Its numeral 5 (art. 95) names the words 'la decimotercera y
    decimocuarta remuneraciones,' as the Ley de 2009 on the fondo de reserva left them."""
    s = Src(S351_2010)
    s.check("Las disposiciones de este Código y sus derogatorias entrarán en vigencia desde la fecha de su promulgación en el Registro Oficial.")
    top = "QUINTA.- Refórmese el Código de Trabajo en las siguientes disposiciones:"
    (b,) = q(s, "1. En el Artículo 81, agréguense los siguientes incisos:", after=top)
    u.insert("art-0081", u.count("art-0081"), b)
    (b,) = q(s, "2. A continuación del Art. 105, incorpórese el siguiente artículo innumerado:", after=top)
    u.set_unit("art-0105-1", b, label="Art. 105.1")
    s.check('3. En el segundo inciso del Art. 17 del Código del Trabajo, luego de la palabra "continuos", agréguese la '
            'frase "o discontinuos", y al final del mismo inciso agréguese lo siguiente: "El sueldo o salario que se '
            'pague en los contratos eventuales, tendrá un incremento del 35% del valor hora del salario básico del '
            'sector al que corresponda el trabajador.".',
            'Al final del tercer inciso agréguese lo siguiente: "El sueldo o salario que se pague en los contratos '
            'ocasionales, tendrá un incremento del 35% del valor hora del salario básico del sector al que corresponda '
            'el trabajador."')
    u.sub("art-0017", "ciento ochenta días continuos", "ciento ochenta días continuos o discontinuos", para=1)
    ps = u.paras("art-0017")
    ps[1] += (" El sueldo o salario que se pague en los contratos eventuales, tendrá un incremento del 35% del valor "
              "hora del salario básico del sector al que corresponda el trabajador.")
    ps[2] += (" El sueldo o salario que se pague en los contratos ocasionales, tendrá un incremento del 35% del valor "
              "hora del salario básico del sector al que corresponda el trabajador.")
    u.put("art-0017", ps)
    (b,) = q(s, "4. A continuación del Artículo 23 agréguese el siguiente artículo:", after=top)
    u.set_unit("art-0023-1", b, label="Art. 23.1")
    s.check('5. En el segundo inciso del Art. 95 del Código del Trabajo, a continuación de la frase "la decimotercera y '
            'decimocuarta remuneraciones,", agréguese el siguiente texto: "la compensación económica para el salario '
            'digno,"')
    u.sub("art-0095", "la decimotercera y decimocuarta remuneraciones,", "la decimotercera y decimocuarta remuneraciones, "
          "la compensación económica para el salario digno,", para=1)


def cc_031_10_scn_cc(u: Units) -> None:
    """Corte Constitucional, sentencia 031-10-SCN-CC (Suplemento 372, 27-I-2011): the second inciso of art. 581 is
    unconstitutional and expelled from the legal order."""
    s = Src(S372_2011)
    s.check('1. Declarar que el contenido del inciso segundo del artículo 581 del Código del Trabajo, que señala "Si una '
            'de las partes ha obtenido directamente documentos no adjuntados en la diligencia preliminar, necesarios '
            'para justificar sus afirmaciones o excepciones, podrá entregarlos al juez antes de los alegatos", '
            'contraviene')
    u.delete_para("art-0581", "Si una de las partes ha obtenido directamente documentos no adjuntados")


def ley_derechos_laborales_2012(u: Units) -> None:
    """Ley Orgánica para la Defensa de los Derechos Laborales (Segundo Suplemento 797, 26-IX-2012), arts. 3-6. No
    vigencia clause: in force on publication."""
    s = Src(S797_2012)
    (b,) = q(s, "Artículo 3.- En el Artículo 104 del Código del Trabajo, añádase el inciso siguiente:")
    u.insert("art-0104", u.count("art-0104"), b)
    (b,) = q(s, "Artículo 4.- Sustitúyase el tercer inciso del Artículo 155 del Código del Trabajo, por el siguiente:")
    u.set_para("art-0155", 2, b)
    s.check("Artículo 5.- Derógase el Artículo 269 del Código del Trabajo.")
    u.remove("art-0269")
    (b,) = q(s, "Artículo 6.- Añádase el siguiente artículo innumerado después del Artículo 268 del Código de Trabajo:")
    u.set_unit("art-0268-1", b, label="Art. innumerado 1 (tras el art. 268)")


def comf_2014(u: Units) -> None:
    """Código Orgánico Monetario y Financiero (Segundo Suplemento 332, 12-IX-2014), Disposición reformatoria sexta:
    a last inciso of art. 36; in force on publication (its Disposición final)."""
    s = Src(S332_2014)
    s.check("DISPOSICIÓN FINAL.- El presente Código entrará en vigencia desde la fecha de su publicación en el Registro Oficial.")
    p = s.paras[s.index("Sexta.- En el Código del Trabajo, en el artículo 36, incorpórese como último inciso, lo siguiente:")]
    rest = p.split("lo siguiente: ", 1)[1]
    (new,) = unquote([rest])
    u.insert("art-0036", u.count("art-0036"), [new])


S483_2015 = ed("s483-2015", "Tercer Suplemento")
CSAL = "Consejo Nacional de Salarios"


def ley_justicia_laboral_2015(u: Units) -> None:
    """Ley Orgánica para la Justicia Laboral y Reconocimiento del Trabajo en el Hogar (Tercer Suplemento 483,
    20-IV-2015), Capítulo I (arts. 1-59), in force on publication (its Disposición final), except its art. 15 (art.
    97.1), which its Disposición transitoria tercera puts in force on 1-I-2016 (ley_justicia_laboral_2015_art15).
    Read with plain rotext.paragraphs (codes/strict.py drops half of this edition)."""
    s = Src(S483_2015)
    s.check("La presente Ley Orgánica para la Justicia Laboral y Reconocimiento del Trabajo en el Hogar, entrará en "
            "vigencia a partir de la fecha de su publicación en el Registro Oficial.",
            "Tercera.- La reforma a que se refiere el Artículo 15 de esta Ley entrará en vigor a partir del 1 de enero del 2016.")
    whole(u, s, 11, "Artículo 1.- Sustitúyase el artículo 11 por el siguiente:")
    whole(u, s, 14, "Artículo 2.- Sustitúyase el artículo 14 por el siguiente:")
    whole(u, s, 15, "Artículo 3.- Sustitúyase el artículo 15 por el siguiente:")
    (b,) = q(s, "Artículo 4.- A continuación del artículo 16 agréguese el siguiente:")
    if not b[0].startswith("Art. 16.1.-"):
        raise SystemExit("Justicia Laboral art. 4")
    u.set_unit("art-0016-1", b, label="Art. 16.1")
    whole(u, s, 19, "Artículo 5.- Sustitúyase el artículo 19 por el siguiente:")
    (b,) = q(s, "Artículo 6.- Sustitúyanse los párrafos primero y segundo del artículo 20, por los siguientes:")
    if not b[0].startswith("Art. 20.- Cruce de información.-") or len(b) != 1:
        raise SystemExit("Justicia Laboral art. 6")
    u.set_para("art-0020", 0, b, count=2)
    s.check('Artículo 7.- En el título del Parágrafo Segundo del Capítulo I del Título I, elimínese la frase: "de enganche"')
    u.drop("titulos", "de enganche", para="Parágrafo 2do. De los contratos de enganche")
    s.check("Artículo 8.- Deróguense los artículos 24, 25, 26, 27, 28, 29 y 30.")
    for n in range(24, 31):
        u.remove(art_key(n))
    (b,) = q(s, "1. Sustitúyase el numeral 7 por el siguiente:", after="Artículo 9.- En el artículo 42")
    u.set_para("art-0042", u.find("art-0042", "7. Llevar un registro"), b)
    s.check('"El contrato laboral deberá ser escrito e inscrito en la Inspección del Trabajo correspondiente, que '
            'mantendrá un registro específico para el caso.".')
    # the sentence opens its paragraph: the space after it goes with it
    u.drop("art-0042", "El contrato laboral deberá ser escrito e inscrito en la Inspección del Trabajo correspondiente, "
           "que mantendrá un registro específico para el caso. ")
    s.check('Artículo 10.- En el párrafo 4 del Capítulo VI del Título I, sustitúyase el título "De la política de '
            'salarios" por "De las políticas de trabajo y salarios".')
    u.sub("titulos", "Parágrafo 4to. De la política de salarios", "Parágrafo 4to. De las políticas de trabajo y salarios")
    whole(u, s, 118, "Artículo 11.- Sustitúyase el artículo 118 por el siguiente:")
    whole(u, s, 119, "Artículo 12.- Sustitúyase el artículo 119 por el siguiente:")
    s.check('Artículo 13.- En los artículos 81, 117, 120, 121, 122, 123, 124, 125, 126 y 127 del Código del Trabajo, '
            'sustitúyase las palabras "Consejo Nacional de Salarios" por "Consejo Nacional de Trabajo y Salarios".')
    for n in (81, 117, 120, 121, 122, 123, 124, 125, 126, 127):
        k = art_key(n)
        u.put(k, [p.replace(CSAL, "Consejo Nacional de Trabajo y Salarios") for p in u.paras(k)])
    (b,) = q(s, "Artículo 14.- Sustitúyase el segundo inciso del artículo 32, por el siguiente:")
    if not u.paras("art-0032")[1].startswith("En consecuencia, el empleador no podrá despedir ni desahuciar"):
        raise SystemExit("art. 32 second inciso")
    u.set_para("art-0032", 1, b)
    # art. 15 (art. 97.1): 1-I-2016
    whole(u, s, 100, "Artículo 16.- Sustitúyase al artículo 100 por el siguiente:")
    whole(u, s, 103, "Artículo 17.- Sustitúyase el artículo 103 por el siguiente:")
    (b,) = q(s, "Artículo 18.- A continuación del artículo 103, agréguese el siguiente:")
    if not b[0].startswith("Art. 103.1.-"):
        raise SystemExit("Justicia Laboral art. 18")
    u.set_unit("art-0103-1", b, label="Art. 103.1")
    whole(u, s, 104, "Artículo 19.- Sustitúyase el artículo 104 por el siguiente:")
    whole(u, s, 106, "Artículo 20.- Sustitúyase el artículo 106, por el siguiente:")
    whole(u, s, 111, "Artículo 21.- Sustitúyase el artículo 111, por el siguiente:")
    # art. 22: the quotation of art. 113 is never closed; it runs to the next article of the act
    i = s.index("Artículo 22.- Sustitúyase el artículo 113, por el siguiente:")
    j = s.index("Artículo 23. - A continuación del artículo 133")
    b = list(s.paras[i + 1:j])
    if not (len(b) == 4 and b[0].startswith('"Art. 113.- Derecho a la decimocuarta remuneración.-')
            and all(x.count('"') == 0 for x in b[1:])):
        raise SystemExit("Justicia Laboral art. 22")
    b[0] = b[0][1:]
    u.set_unit("art-0113", split_items(b))
    (b,) = q(s, "Artículo 23. - A continuación del artículo 133, agréguese el siguiente artículo Innumerado:")
    if not b[0].startswith("Art. 133.1.-"):
        raise SystemExit("Justicia Laboral art. 23")
    u.set_unit("art-0133-1", b, label="Art. 133.1")
    s.check('1. En el tercer inciso del Artículo 154, elimínese la frase: "ni de desahucio".', "2. Deróguese el último inciso.")
    u.drop("art-0154", "ni de desahucio", para=2)
    if u.count("art-0154") != 4:
        raise SystemExit("art. 154: four incisos expected")
    u.put("art-0154", u.paras("art-0154")[:3])
    s.check("Artículo 25.- En el primer párrafo del cuarto artículo innumerado, agregado a continuación del artículo "
            "156, suprímase lo siguiente:",
            '"Este certificado deberá acompañarse al contrato cuando éste sea registrado en las dependencias del '
            'Ministerio de Trabajo y Empleo.".')
    u.drop("art-0156-4", "Este certificado deberá acompañarse al contrato cuando éste sea registrado en las "
           "dependencias del Ministerio de Trabajo y Empleo.", para=0)
    (b,) = q(s, "Artículo 26.- Sustitúyase el numeral 9 del artículo 169 por el siguiente:")
    u.set_para("art-0169", u.find("art-0169", "9. Por desahucio."), b)
    s.check("Artículo 27.- Al final del número 1 del artículo 173, sustitúyase el punto y coma (;) por punto seguido "
            "(.), y añádase lo siguiente:")
    (b,) = q(s, "Artículo 27.- Al final del número 1 del artículo 173")
    i = u.find("art-0173", "1. Por injurias graves")
    ps = u.paras("art-0173")
    if not ps[i].endswith(";"):
        raise SystemExit("art. 173 num. 1")
    ps[i] = ps[i][:-1] + ". " + b[0]
    u.put("art-0173", ps)
    s.check("Artículo 28.- En el artículo 175, elimínese la frase: ''desahuciar ni\".")
    u.drop("art-0175", "desahuciar ni")
    s.check("Artículo 29.- Deróguese el artículo 181.")
    u.remove("art-0181")
    (b,) = q(s, "1. Sustitúyase el primer inciso del artículo 184 por el siguiente:", after="Artículo 30.-")
    u.set_para("art-0184", 0, b)
    (b,) = q(s, "2. Sustitúyase el segundo inciso por el siguiente:", after="Artículo 30.-")
    u.set_para("art-0184", 1, b)
    whole(u, s, 185, "Artículo 31.- Sustitúyase el artículo 185, por lo siguiente:")
    s.check("Artículo 32.- Deróguese el artículo 186.")
    u.remove("art-0186")
    whole(u, s, 187, "Artículo 33.- Sustitúyase el artículo 187 por el siguiente:")
    s.check("Artículo 34.- Deróguese el artículo 189.")
    u.remove("art-0189")
    (b,) = q(s, "Artículo 35.- Añádanse a continuación del artículo 195, los siguientes artículos:")
    arts: list[list[str]] = []
    for p in b:
        m = re.match(r"Art\. 195\.(\d)\.-", p)
        if m:
            if int(m.group(1)) != len(arts) + 1:
                raise SystemExit("Justicia Laboral art. 35: numbering")
            arts.append([p])
        else:
            arts[-1].append(p)
    if len(arts) != 3:
        raise SystemExit("Justicia Laboral art. 35: three articles expected")
    for n, a in enumerate(arts, 1):
        u.set_unit(art_key(195, str(n)), a, label=f"Art. 195.{n}")
    (b,) = q(s, "Artículo 36.- Agréguese un párrafo final en el artículo 220, con el siguiente texto:")
    u.insert("art-0220", u.count("art-0220"), b)
    s.check("Artículo 37.- En el título del artículo 233, elimínese \"y desahucio\" y en el inciso primero del mismo, "
            "elimínese la frase ''desahuciar ni\".")
    u.drop("art-0233", "y desahucio", para=0)
    u.drop("art-0233", "desahuciar ni", para=0)
    s.check("Artículo 38.- Deróguese el artículo 264.", "Artículo 40.- Deróguese el artículo 266.")
    u.remove("art-0264")
    whole(u, s, 265, "Artículo 39.- Sustitúyase el artículo 265, por el siguiente:")
    u.remove("art-0266")
    s.check('Artículo 41.- En el primer párrafo del artículo 275, elimínese lo siguiente:',
            '"Una copia del registro se enviará a la Dirección de Empleo y Recursos Humanos.".')
    u.drop("art-0275", "Una copia del registro se enviará a la Dirección de Empleo y Recursos Humanos.", para=0)
    s.check("Artículo 42.- Deróguese el artículo 277.")
    u.remove("art-0277")
    s.check('"que los empleadores se hayan inscrito en el registro de empleadores del trabajo a domicilio, '
            'exigiéndoles la presentación del correspondiente certificado;".')
    u.drop("art-0283", "que los empleadores se hayan inscrito en el registro de empleadores del trabajo a domicilio, "
           "exigiéndoles la presentación del correspondiente certificado;", para="1.-")
    s.check('", debidamente registrado en el Ministerio de Trabajo y Empleo"')
    u.drop("art-0285", ", debidamente registrado en el Ministerio de Trabajo y Empleo", para=1)
    whole(u, s, 310, "Artículo 45.- Sustitúyase el artículo 310 por el siguiente:")
    s.check("Artículo 46.- Deróguense los artículos 311 y 312.")
    u.remove("art-0311")
    u.remove("art-0312")
    whole(u, s, 452, "Artículo 47.- Sustitúyase el artículo 452 por el siguiente:")
    whole(u, s, 455, "Artículo 48.- Sustitúyase el artículo 455, por el siguiente:")
    (b,) = q(s, "1. Sustitúyase el número 3 por el siguiente:", after="Artículo 49.- En el artículo 459")
    u.set_para("art-0459", u.find("art-0459", "3. La directiva"), b)
    (b,) = q(s, "2. Sustitúyase el número 4 por el siguiente:", after="Artículo 49.- En el artículo 459")
    u.set_para("art-0459", u.find("art-0459", "4. Los miembros"), comma_end(b))
    (b,) = q(s, "Artículo 50.- Sustitúyase el número 5 del artículo 462 por el siguiente:")
    u.set_para("art-0462", u.find("art-0462", "5. Controlar"), comma_end(b))
    s.check('Artículo 51.- En el número 2 del artículo 497, elimínese "o desahuciare".')
    u.drop("art-0497", "o desahuciare", para="2. ")
    (b,) = q(s, "Artículo 52.- A continuación del primer inciso del artículo 539 agréguese el siguiente párrafo:")
    u.insert("art-0539", 1, b)
    s.check('Artículo 53.- En el número 5 del artículo 545, suprímase la frase "notificar los desahucios".')
    u.drop("art-0545", "notificar los desahucios", para="5. ")
    s.check("Artículo 54.- Deróguese el artículo 560.", "Artículo 55.- Deróguense los artículos 562 y 563.")
    for n in (560, 562, 563):
        u.remove(art_key(n))
    whole(u, s, 624, "Artículo 56.- Sustitúyase el artículo 624, por el siguiente:")
    whole(u, s, 566, "Artículo 57.- Sustitúyase el artículo 566 por el siguiente:")
    s.check('Artículo 58.- En el primer inciso del artículo 630, a continuación de la palabra "multas" agréguese "y de '
            'las utilidades a favor de personas trabajadoras y ex trabajadoras señaladas en el artículo 104 de este '
            'Código.".')
    # the full stop inside the quotation ends the act's sentence, not the inserted words (decisions)
    u.sub("art-0630", "recaudación de las multas se empleará", "recaudación de las multas y de las utilidades a favor de "
          "personas trabajadoras y ex trabajadoras señaladas en el artículo 104 de este Código se empleará", para=0)
    (b,) = q(s, "Artículo 59.- En el artículo 224 de éste Código, incorpórese los siguientes párrafos:")
    u.insert("art-0224", u.count("art-0224"), b)


S506_2015 = ed("s506-2015", "Primer Suplemento")
COGEP_TOP = "SEXTA.- Refórmense en el Código del Trabajo, las siguientes disposiciones:"


def cogep_2015_abandono(u: Units) -> None:
    """Código Orgánico General de Procesos (Suplemento 506, 22-V-2015), Disposición reformatoria sexta num. 9 (art.
    634, término para el abandono): in force on publication, as its Disposición final segunda says of the rules 'que
    regulan períodos de abandono'; the rest of its reforms wait twelve months (cogep_2015)."""
    s = Src(S506_2015)
    s.check("con excepción de las normas que reforman el Código Orgánico de la Función Judicial, la Ley Notarial y la "
            "Ley de Arbitraje y Mediación y aquellas que regulan períodos de abandono, copias certificadas, registro de "
            "contratos de inquilinato y citación, que entrarán en vigencia a partir de la fecha de publicación de esta Ley.")
    whole(u, s, 634, "9. Sustitúyase el artículo 634 por el siguiente:", after=COGEP_TOP)


def cogep_2015(u: Units) -> None:
    """COGEP, Disposición reformatoria sexta nums. 1-8 and Disposición derogatoria octava, in force twelve months
    after publication (its Disposición final segunda): 22-V-2016."""
    s = Src(S506_2015)
    s.check("SEGUNDA.- El Código Orgánico General de Procesos entrará en vigencia luego de transcurridos doce meses, "
            "contados a partir de su publicación en el Registro Oficial")
    whole(u, s, 6, "1. Sustitúyase el artículo 6 por el siguiente:", after=COGEP_TOP)
    (b,) = q(s, "2. Agréguese en el artículo 153 como último inciso el siguiente texto:", after=COGEP_TOP)
    u.insert("art-0153", u.count("art-0153"), b)
    whole(u, s, 491, "3. Sustitúyase el artículo 491 por el siguiente:", after=COGEP_TOP)
    s.check('4. Añádase en el artículo 571 a continuación de la palabra "excepción" la palabra "previa".')
    u.sub("art-0571", "como excepción.", "como excepción previa.")
    whole(u, s, 572, "5. Sustitúyase el artículo 572 por el siguiente:", after=COGEP_TOP)
    whole(u, s, 575, "6. Sustitúyase el artículo 575 por el siguiente:", after=COGEP_TOP)
    whole(u, s, 577, "7. Sustitúyase el artículo 577 por el siguiente:", after=COGEP_TOP)
    (b,) = q(s, "8. Sustitúyase el segundo inciso del artículo 606 por el siguiente:", after=COGEP_TOP)
    u.set_para("art-0606", 1, b)
    s.check("OCTAVA.- Deróguense los artículos 568, 570, 574, 576, 578, 579, 580, 581, 582, 583, 584, 585, 586, 587, "
            "590, 591, 592, 593, 596, 597, 598, 599, 600, 601, 602, 603, 604, 605, 607, 608, 609, 610, 611, 612, 613, "
            "614, 616, 618, 619 y 620 del Código del Trabajo")
    for n in [568, 570, 574, 576, 578, 579, 580, 581, 582, 583, 584, 585, 586, 587, 590, 591, 592, 593, 596, 597, 598,
              599, 600, 601, 602, 603, 604, 605, 607, 608, 609, 610, 611, 612, 613, 614, 616, 618, 619, 620]:
        u.remove(art_key(n))


S720_2016 = ed("s720-2016", "Primer Suplemento")
S906_2016 = ed("s906-2016", "Primer Suplemento")
S1008_2017 = ed("s1008-2017", "Primer Suplemento")
S116_2017 = ed("s116-2017", "Primer Suplemento")
S175_2018 = ed("s175-2018", "Primer Suplemento")
EC40_2018 = ed("ec40-2018", "Ediciones Constitucionales")
S309_2018 = ed("s309-2018", "Primer Suplemento")
S517_2019 = ed("s517-2019", "Primer Suplemento")
S229_2020 = ed("s229-2020", "Primer Suplemento")
EC231_2021 = ed("ec231-2021", "Ediciones Constitucionales")
S222_2023 = ed("s222-2023", "Primer Suplemento")
S234_2023 = ed("s234-2023", "Primer Suplemento")
S242_2023 = ed("s242-2023", "Primer Suplemento")


def drop_conj(u: Units, key: str, prefix: str) -> None:
    """An act's 'al final del numeral N, elimínese: "y"': the closing '; y,' of that numeral becomes ';'."""
    i = u.find(key, prefix)
    ps = u.paras(key)
    if not ps[i].endswith("; y,"):
        raise SystemExit(f"{key} {prefix!r}: does not end '; y,'")
    ps[i] = ps[i][:-3]
    u.put(key, ps)


def end_with(u: Units, key: str, prefix: str, old: str, new: str) -> None:
    """Replace the final punctuation `old` of one paragraph with `new`, as an act directs."""
    i = u.find(key, prefix)
    ps = u.paras(key)
    if not ps[i].endswith(old):
        raise SystemExit(f"{key} {prefix!r}: does not end {old!r}")
    ps[i] = ps[i][:-len(old)] + new
    u.put(key, ps)


def ley_trabajo_juvenil_2016(u: Units) -> None:
    """Ley Orgánica para la Promoción del Trabajo Juvenil, Regulación Excepcional de la Jornada de Trabajo, Cesantía y
    Seguro de Desempleo (Suplemento 720, 28-III-2016), arts. 3-5; in force on publication (its Disposición final)."""
    s = Src(S720_2016)
    s.check("Las disposiciones de la presente Ley entrarán en vigencia a partir de su publicación en el Registro Oficial.")
    (b,) = q(s, "Artículo 3.- A continuación del artículo 34, añádase el siguiente parágrafo y los artículos que lo contienen:")
    if b[0] != "Parágrafo 3o Del contrato de trabajo juvenil":
        raise SystemExit(f"Trabajo juvenil art. 3: {b[0]!r}")
    heading_before(u, "Capítulo II De la capacidad para contratar", [b[0]])
    arts: list[list[str]] = []
    for p in b[1:]:
        m = re.match(r"Art\. 34\.(\d)\.-", p)
        if m:
            if int(m.group(1)) != len(arts) + 1:
                raise SystemExit("Trabajo juvenil art. 3: numbering")
            arts.append([p])
        else:
            arts[-1].append(p)
    if len(arts) != 4:
        raise SystemExit("Trabajo juvenil art. 3: four articles expected")
    for n, a in enumerate(arts, 1):
        u.set_unit(art_key(34, str(n)), a, label=f"Art. 34.{n}")
    (b,) = q(s, "Artículo 4.- A continuación del artículo 47, añádanse los siguientes artículos:")
    i = next(k for k, p in enumerate(b) if p.startswith("Art. 47.2.-"))
    if not b[0].startswith("Art. 47.1.-"):
        raise SystemExit("Trabajo juvenil art. 4")
    u.set_unit("art-0047-1", b[:i], label="Art. 47.1")
    u.set_unit("art-0047-2", b[i:], label="Art. 47.2")
    # art. 5: printed without quotation marks, up to the next Capítulo of the act
    i = s.index("Artículo 5.- A continuación del artículo 152, añádase el siguiente artículo innumerado:")
    j = s.index("Reformas a la Ley de Seguridad Social", after="Artículo 5.- A continuación del artículo 152")
    b = list(s.paras[i + 1:j - 1])
    if not (b[0].startswith("Artículo ... .- Licencia o permiso sin remuneración") and s.paras[j - 1] == "CAPÍTULO III"):
        raise SystemExit("Trabajo juvenil art. 5")
    # the text layer splits one word: 'est e hecho' (decisions)
    b = [p.replace("por est e hecho", "por este hecho") for p in b]
    # placed after the articles innumerados of 2009 so that their file names stay (decisions)
    if "art-0152-3" in u.u:
        raise SystemExit("art-0152-3 exists")
    u.set_unit("art-0152-3", b, label="Art. innumerado 3 (tras el art. 152)")


def ley_feriados_2016(u: Units) -> None:
    """Ley Orgánica Reformatoria a la Ley Orgánica del Servicio Público y al Código del Trabajo (Suplemento 906,
    20-XII-2016), art. 3 (art. 65, días de descanso obligatorio); in force on publication (its Disposición final)."""
    s = Src(S906_2016)
    s.check("Las disposiciones de la presente Ley Orgánica entrarán en vigencia a partir de su publicación en el Registro Oficial.",
            'Artículo 3.- Refórmase el artículo 65 del Código del Trabajo, de la siguiente manera:',
            '1. En el primer inciso, sustitúyase la frase "y 25 de diciembre", por la siguiente: ", 25 de diciembre y los '
            'días lunes y martes de carnaval".')
    u.sub("art-0065", " y 25 de diciembre", ", 25 de diciembre y los días lunes y martes de carnaval", para=0)
    (b,) = q(s, "2. Añádanse como tercer y cuarto incisos, los siguientes:", after="Artículo 3.- Refórmase el artículo 65")
    if u.count("art-0065") != 2 or len(b) != 2:
        raise SystemExit("art. 65")
    u.insert("art-0065", 2, b)


def ley_sector_publico_2017(u: Units) -> None:
    """Ley Orgánica Reformatoria a las Leyes que rigen el Sector Público (Suplemento 1008, 19-V-2017), art. 22: an
    article innumerado after art. 247; in force on publication (its Disposición final única)."""
    s = Src(S1008_2017)
    s.check("la que entrará en vigencia a partir de la fecha de su publicación en el Registro Oficial.")
    (b,) = q(s, "Art. 22.- A continuación del artículo 247 incorpórese el siguiente artículo innumerado:")
    if not b[0].startswith("Art....- La negociación y contratación colectiva en el sector público"):
        raise SystemExit("Sector público art. 22")
    u.set_unit("art-0247-1", b, label="Art. innumerado (tras el art. 247)")


def ley_acoso_laboral_2017(u: Units) -> None:
    """Ley Orgánica Reformatoria a la LOSEP y al Código del Trabajo para prevenir el Acoso Laboral (Suplemento 116,
    9-XI-2017), arts. 4-10; in force on publication (its Disposición final). Read through codes/strict.py: the plain
    text layer interleaves stray fragments into art. 9. The numeral or literal an act names ('añádase un numeral 36',
    'un literal m)') opens the added paragraph (decisions)."""
    s = SSrc(S116_2017)
    s.check("Las disposiciones de la presente Ley Orgánica Reformatoria entrarán en vigencia a partir de su publicación "
            "en el Registro Oficial.")
    (b,) = q(s, "Artículo 4. Incluir un artículo no numerado después del artículo 46:")
    if not b[0].startswith("Definición de acoso laboral:") or len(b) != 1:
        raise SystemExit("Acoso laboral art. 4")
    u.set_unit("art-0046-1", b, label="Art. innumerado (tras el art. 46)")
    (b,) = q(s, "Artículo 5: En el artículo 42, añádase un numeral 36, que dirá:")
    if not u.paras("art-0042")[-1].startswith("35.-"):
        raise SystemExit("art. 42: numeral 35 is not last")
    u.insert("art-0042", u.count("art-0042"), ["36. " + b[0]])
    (b,) = q(s, "Artículo 6. En el artículo 44, añádase un literal m) que dirá:")
    # literal l) is followed by the article's closing inciso on fines ('En caso de reincidencia ...')
    u.insert("art-0044", u.find("art-0044", "l) Recibir en trabajos") + 1, ["m) " + b[0]])
    (b,) = q(s, "Artículo 7. En el artículo 46, añádase un literal j) que dirá:")
    u.insert("art-0046", u.count("art-0046"), ["j) " + b[0]])
    s.check('Artículo 8. En el artículo 172, al final del numeral 6, elimínese: "y"; al final de numeral 7, sustitúyase '
            'el punto final ".", por "; y," y añádase un numeral 8, que dirá:')
    (b,) = q(s, "Artículo 8. En el artículo 172, al final del numeral 6")
    drop_conj(u, "art-0172", "6. Por denuncia")
    end_with(u, "art-0172", "7. Por no acatar", ".", "; y,")
    u.insert("art-0172", u.count("art-0172"), ["8. " + b[0]])
    s.check('Artículo 9. En el artículo 173, al final del numeral 2, elimínese: "y"; al final del numeral 3, sustitúyase '
            'el punto final: ".", por "y,"; y añádase un num eral 4, que dirá:')
    (b,) = q(s, "Artículo 9. En el artículo 173, al final del numeral 2")
    if len(b) != 2:
        raise SystemExit("Acoso laboral art. 9")
    drop_conj(u, "art-0173", "2. Por disminución")
    end_with(u, "art-0173", "3. Por exigir", ".", " y,")
    u.insert("art-0173", u.count("art-0173"), ["4. " + b[0], b[1]])
    s.check('Artículo 10.- En el artículo 545, al final del numeral 7, elimínese: "y"; el numeral 8 pasa a ser numeral 9, '
            'el numeral 8 dirá: "En los casos de acoso laboral, podrá disponer se efectúen las disculpas públicas de quien '
            'cometió la conducta". Y al final del numeral 8, sustitúyase el punto final por "; y,".')
    drop_conj(u, "art-0545", "7. Imponer multas")
    u.sub("art-0545", "8. Las demás conferidas", "9. Las demás conferidas", para="8. Las demás")
    u.insert("art-0545", u.find("art-0545", "9. Las demás"), ["8. En los casos de acoso laboral, podrá disponer se "
                                                              "efectúen las disculpas públicas de quien cometió la "
                                                              "conducta; y,"])


def ley_violencia_mujeres_2018(u: Units) -> None:
    """Ley Orgánica Integral para Prevenir y Erradicar la Violencia contra las Mujeres (Suplemento 175, 5-II-2018),
    Disposición reformatoria primera: a numeral '10.' after numeral 9 of art. 42, without renumbering the numerals
    that follow (so art. 42 has two numerals 10). In force on publication."""
    s = Src(S175_2018)
    s.check('PRIMERA.- Agrégase a continuación del numeral 9 del artículo 42 del Código de Trabajo, el numeral siguiente:')
    new = s.inline("PRIMERA.- Agrégase a continuación del numeral 9 del artículo 42 del Código de Trabajo, el numeral siguiente:")
    if not new.startswith("10. Conceder a las trabajadoras víctimas de violencia de género"):
        raise SystemExit("Violencia mujeres DR primera")
    u.insert("art-0042", u.find("art-0042", "9. Conceder a los trabajadores el tiempo") + 1, [new])


def ley_fomento_productivo_2018(u: Units) -> None:
    """Ley Orgánica para el Fomento Productivo, Atracción de Inversiones, Generación de Empleo, y Estabilidad y
    Equilibrio Fiscal (Suplemento 309, 21-VIII-2018), art. 50 (art. 112); in force on publication."""
    s = Src(S309_2018)
    (b,) = q(s, "Artículo 50.- Sustitúyase el artículo 112 por el siguiente:")
    if not b[0].startswith("Art. 112. Exclusión de la decimotercera remuneración.-"):
        raise SystemExit("Fomento productivo art. 50")
    u.set_unit("art-0112", b)


def ley_reformatoria_cogep_2019(u: Units) -> None:
    """Ley Orgánica Reformatoria del COGEP (Suplemento 517, 26-VI-2019), Disposición reformatoria primera (art.
    195.2); in force on publication (its Disposición final)."""
    s = Src(S517_2019)
    s.check("La presente reforma entrará en vigencia a partir de su publicación en el Registro Oficial.")
    (b,) = q(s, "PRIMERA.- Reformase el artículo 195.2 del Código de Trabajo por el siguiente texto:")
    if not b[0].startswith("Art. 195.2.- Acción de despido ineficaz."):
        raise SystemExit("Reformatoria COGEP 2019")
    u.set_unit("art-0195-2", b)


def ley_apoyo_humanitario_2020(u: Units) -> None:
    """Ley Orgánica de Apoyo Humanitario para combatir la crisis sanitaria derivada del COVID-19 (Suplemento 229,
    22-VI-2020), Disposiciones reformatorias primera (teletrabajo, an article innumerado after art. 16) and segunda
    (art. 363 num. 4); in force on publication (its Disposición final). Its Disposición interpretativa única
    (art. 169 num. 6) changes no words of the Code (decisions)."""
    s = Src(S229_2020)
    s.check("Disposición Final.- La presente Ley entrará en vigencia a partir de su publicación en el Registro Oficial.")
    (b,) = q(s, "Primera.- Agréguese el siguiente artículo innumerado a continuación del artículo 16 del Código del Trabajo:")
    if not b[0].startswith("Artículo (...).- Del teletrabajo.-"):
        raise SystemExit("Apoyo humanitario DR primera")
    u.set_unit("art-0016-2", b, label="Art. innumerado (teletrabajo, tras el art. 16)")
    (b,) = q(s, "Segunda.- Añádase al final del artículo 363 del Código del Trabajo como un nuevo numeral la siguiente categoría:")
    u.insert("art-0363", u.count("art-0363"), b)


def cc_36_19_in_21(u: Units) -> None:
    """Corte Constitucional, sentencia 36-19-IN/21 (Edición Constitucional 231, 4-XI-2021): 'posteriores al parto' in
    the third inciso of art. 155 is unconstitutional and is to read 'a partir de que haya concluido su licencia por
    maternidad'."""
    s = Src(EC231_2021)
    s.check('2. Declarar la inconstitucionalidad por el fondo de la frase "posteriores al parto" del inciso tercero del '
            'artículo 155 del Código de Trabajo y determinar que en su lugar deberá decir:',
            '"Art. 155.- Guardería infantil y lactancia [...] Durante los doce (12) meses a partir de que haya concluido su '
            'licencia por maternidad, la jornada de la madre lactante durará seis (6) horas, de conformidad con la '
            'necesidad de la beneficiaria".')
    u.sub("art-0155", "posteriores al parto", "a partir de que haya concluido su licencia por maternidad", para=2)


def ley_juventudes_2023(u: Units) -> None:
    """Ley Orgánica de las Juventudes (Suplemento 222, 4-I-2023), Disposición reformatoria primera: art. 34.1 and two
    final incisos of art. 42 num. 27; in force on publication (its Disposición final única)."""
    s = Src(S222_2023)
    top = "PRIMERA.- REFORMA EL CÓDIGO DEL TRABAJO:"
    s.check("ÚNICA.- La presente Ley entrará en vigencia a partir de la fecha de su publicación en el Registro Oficial.")
    (b,) = q(s, "1. Sustitúyase el Art. 34.1 por el siguiente texto:", after=top)
    if not b[0].startswith("Trabajo Juvenil.-"):
        raise SystemExit("Juventudes 1")
    # printed without the article's number, as the act gives it (decisions)
    u.set_unit("art-0034-1", b)
    (b,) = q(s, "2. Agréguese los siguientes incisos finales al numeral 27 del artículo 42:", after=top)
    i = u.find("art-0042", "27. Conceder permiso")
    if not u.paras("art-0042")[i + 1].startswith("El becario"):
        raise SystemExit("art. 42 num. 27")
    u.insert("art-0042", i + 2, b)


def ley_economia_violeta_2023(u: Units) -> None:
    """Ley Orgánica para Impulsar la Economía Violeta (Suplemento 234, 20-I-2023), arts. 22-25; in force on
    publication (its Disposición final única)."""
    s = Src(S234_2023)
    s.check("ÚNICA.- La presente Ley entrará en vigencia a partir de su publicación en el Registro Oficial.")
    (b,) = q(s, "Artículo 22.- A continuación del artículo 42, agréguese el siguiente artículo:")
    if not b[0].startswith("Art. 42.1.-"):
        raise SystemExit("Economía violeta 22")
    u.set_unit("art-0042-1", b, label="Art. 42.1")
    (b,) = q(s, "Artículo 23.- Sustitúyase el artículo 79 por el siguiente artículo:")
    if not b[0].startswith("Artículo 79.- Igualdad de remuneración.-"):
        raise SystemExit("Economía violeta 23")
    u.set_unit("art-0079", b)
    (b,) = q(s, "Artículo 24.- Luego del primer inciso del artículo 152, agréguese lo siguiente:")
    u.insert("art-0152", 1, b)
    (b,) = q(s, "Artículo 25.- A continuación del artículo 154, añádase el siguiente artículo innumerado:")
    if not b[0].startswith("Art. (...).- Licencia con remuneración por el período de lactancia.-"):
        raise SystemExit("Economía violeta 25")
    u.set_unit("art-0154-1", b, label="Art. innumerado (tras el art. 154)")


def clean_242(p: str) -> str:
    """Suplemento 242 (2023): the running head 'Miércoles 1º de febrero de 2023' sits inside paragraphs, and 'podrá'
    carries two stray combining accents (decisions)."""
    return p.replace("Miércoles 1º de febrero de 2023 ", "").replace("á́́", "á")


def ley_derechos_trabajadores_2023(u: Units) -> None:
    """Ley Orgánica Reformatoria a Varias Leyes para la Defensa y Garantía de los Derechos Individuales y Colectivos
    de los Trabajadores (Suplemento 242, 1-II-2023), arts. 1-3; in force on publication (its Disposición final)."""
    s = Src(S242_2023)
    s.check("ÚNICA.- La presente Ley entrará en vigencia a partir de su publicación en el Registro Oficial.")
    (b,) = q(s, "Artículo 1.- Sustitúyase el numeral 25 del artículo 42 del Código del Trabajo, por el siguiente texto:")
    if not b[0].startswith("25. Pagar al trabajador reemplazante"):
        raise SystemExit("Derechos trabajadores 1")
    u.set_para("art-0042", u.find("art-0042", "25. Pagar al trabajador reemplazante"), [clean_242(p) for p in b])
    (b,) = q(s, "Artículo 2.- Sustitúyase el artículo 57 del Código del Trabajo por el siguiente texto:")
    b = [clean_242(p) for p in b]
    if not b[0].startswith("Art. 57.- División de la jornada.- La jornada ordinaria de trabajo podrá ser dividida"):
        raise SystemExit(f"Derechos trabajadores 2: {b[0][:90]!r}")
    u.set_unit("art-0057", b)
    (b,) = q(s, "Artículo 3.- Añádase al final del artículo 58 del Código del Trabajo, el siguiente párrafo:")
    u.insert("art-0058", u.count("art-0058"), b)


S309_2023 = ed("s309-2023", "Primer Suplemento")
S559_2024 = ed("s559-2024", "Primer Suplemento")
S588_2024 = ed("s588-2024", "Tercer Suplemento")
S64_2025 = ed("s64-2025", "Quinto Suplemento")
S94_2025 = ed("s94-2025", "Segundo Suplemento")

# provisions an image-only reform amended (Lexis/SRI index) and no applied act has replaced whole since: a later
# partial amendment of them is not applied (the file would mix wording that never stood together) but is credited
# with a version note; filled by replay() from the list steps from 2024 on
STALE: set[str] = set()
PARTLY = ("Partly NOT APPLIED here: an earlier reform this record could not apply (image-only edition) had already "
          "amended {}, so this act's partial amendment of {} is not applied either; {} the earlier text, which is not "
          "the law from this date.")


def ley_cuidado_humano_2023(u: Units) -> None:
    """Ley Orgánica del Derecho al Cuidado Humano (Suplemento 309, 12-V-2023), Disposiciones reformatorias, Capítulos
    II (Código del Trabajo) and III (repeal of arts. 24 and 25 of the Ley de Economía Violeta, whose words leave art.
    152 and the article innumerado after art. 154); in force on publication (its Disposición final única). Its
    Capítulo II primera names 'plazo de diez días', which art. 152 does not contain: not applied (decisions)."""
    s = Src(S309_2023)
    s.check("ÚNICA.- La presente Ley entrará en vigencia desde su publicación en el Registro Oficial",
            'PRIMERA.- En el segundo párrafo del artículo 152 del Código del Trabajo, sustitúyase las palabras: "plazo de '
            'diez días" por las siguientes: "plazo de quince (15) días".')
    if any("plazo de diez días" in p for p in u.paras("art-0152")):
        raise SystemExit("art. 152 now holds 'plazo de diez días'")
    (b,) = q(s, "SEGUNDA.- Sustitúyase el artículo innumerado que se encuentra a continuación del artículo 152 del Código "
                "del Trabajo, que versa sobre la")
    if not (b[0].startswith("Art. 152.1.- Licencia o permiso sin remuneración para el cuidado de los hijos.-")
            and "cuidado de los hijos" in u.paras("art-0152-3")[0]):
        raise SystemExit("Cuidado humano segunda")
    u.set_unit("art-0152-3", b)
    u.u["art-0152-3"]["label"] = "Art. 152.1"
    s.check('TERCERA.- En el tercer párrafo del artículo 155 del Código del Trabajo, sustitúyase las palabras: "Durante '
            'los doce (12) meses" por las siguientes: "Durante los quince (15) meses".')
    u.sub("art-0155", "Durante los doce (12) meses", "Durante los quince (15) meses", para=2)
    (b,) = q(s, "CUARTA.- Sustitúyase el segundo artículo innumerado que se encuentra a continuación del artículo 152 del "
                "Código del Trabajo que versa sobre la")
    if not (b[0].startswith("Art. 155.2.- Licencia por Adopción.-") and "Licencia por Adopción" in u.paras("art-0152-1")[0]):
        raise SystemExit("Cuidado humano cuarta")
    u.set_unit("art-0152-1", b)
    u.u["art-0152-1"]["label"] = "Art. 155.2 (licencia por adopción, tras el art. 152)"
    s.check("PRIMERA.- Deróguese el artículo 24 incorporado en la Ley Orgánica para impulsar la Economía Violeta",
            "SEGUNDA.- Deróguese el artículo 25 incorporado en la Ley Orgánica para Impulsar la Economía Violeta")
    ps = u.paras("art-0152")
    if not (ps[1].startswith("No obstante la madre podrá, de común acuerdo con el padre")
            and ps[2].startswith("Las instituciones públicas o privadas que cuenten con más de 50 empleados")):
        raise SystemExit("art. 152: the incisos of 2023 are not where expected")
    u.put("art-0152", ps[:1] + ps[3:])
    u.remove("art-0154-1")


def ley_derechos_discapacidad_2025(u: Units) -> None:
    """Ley Orgánica Reformatoria a Diversos Cuerpos Legales para Garantizar los Derechos Laborales de las Personas con
    Discapacidad, Enfermedades Raras, Huérfanas, Catastróficas y de Alta Complejidad y sus Sustitutos (Quinto
    Suplemento 64, 20-VI-2025), arts. 10-11; in force on publication (its Disposición final única). Art. 10 adds
    numerals 37 and 38 to art. 42, which the image-only Ley of 16-V-2024 had amended: not applied (STALE)."""
    s = Src(S64_2025)
    s.check("entrará en vigencia a partir de su publicación en el Registro Oficial.",
            "Artículo 10.- Refórmese el artículo 42 del Código del Trabajo agregando los siguientes numerales:")
    if "art-0042" not in STALE:
        raise SystemExit("art. 42 expected STALE")
    u.skipped.append("art-0042")
    i = s.index("Artículo 11.- Agréguese después del artículo 152.3 del Código del Trabajo el siguiente artículo que "
                "diga lo siguiente:")
    b = [s.paras[i + 1]]
    if not (b[0].startswith("Artículo 152.4 Incentivos no Económicos.-") and s.paras[i + 2] == "DISPOSICIÓN GENERAL"):
        raise SystemExit("Derechos discapacidad art. 11")
    u.set_unit("art-0152-4", b, label="Art. 152.4")


def ley_justicia_laboral_2015_art15(u: Units) -> None:
    """Art. 15 of the Ley Orgánica para la Justicia Laboral: art. 97.1 (cap on profit shares), in force on 1-I-2016
    (its Disposición transitoria tercera)."""
    s = Src(S483_2015)
    (b,) = q(s, "Artículo 15.- A continuación del artículo 97, agréguese el siguiente artículo:")
    if not b[0].startswith("Art. 97.1.-"):
        raise SystemExit("Justicia Laboral art. 15")
    u.set_unit("art-0097-1", b, label="Art. 97.1")


# ---------------------------------------------------------------- laws, steps, part

BASE_LAW = "codificacion-ct-2005-017"
IMAGE_ONLY = ("NOT APPLIED here: the Registro Oficial edition that publishes it is page images without a text layer, "
              "and this repository does not OCR. Its wording is missing: the files named in this commit keep the "
              "earlier text (provisions named from the Lexis index).")
IMAGE_ONLY_SRI = IMAGE_ONLY.replace("the Lexis index", "the SRI consolidation of 27-VI-2024")

LAWS = {
    BASE_LAW: dict(label="Codificación 2005-017 del Código del Trabajo", kind="law", enacted="2005-10-18",
                   published="2005-12-16", url=S167_2005,
                   title="Codificación del Código del Trabajo (Comisión de Legislación y Codificación del Congreso "
                         "Nacional)"),
    "ley-2006-28": dict(label="Ley 2006-28 Reformatoria al Código del Trabajo", kind="law", enacted="2006-01-18",
                        published="2006-01-30", url=RO198_2006,
                        title="Ley 2006-28 Reformatoria al Código del Trabajo (personas con discapacidad)"),
    "fe-erratas-ley-2006-28": dict(label="Fe de erratas de la Ley 2006-28", kind="law", enacted="2006-02-24",
                                   published="2006-03-07", url=RO223_2006,
                                   title="Fe de erratas a la Ley 2006-28 Reformatoria al Código del Trabajo (Congreso "
                                         "Nacional, Registro Oficial 223)"),
    "ley-2006-39": dict(label="Ley 2006-39 Reformatoria al Código del Trabajo", kind="law", enacted="2006-03-28",
                        published="2006-04-13", url=RO250_2006,
                        title="Ley 2006-39 Reformatoria al Código del Trabajo (trabajo de adolescentes)"),
    "ley-2006-40": dict(label="Ley 2006-40 Reformatoria del Código del Trabajo", kind="law", published="2006-04-27",
                        url=RO259_2006, title="Ley 2006-40 Reformatoria del Código del Trabajo (examen médico de menores)"),
    "ley-2006-48": dict(label="Ley 2006-48 Reformatoria al Código del Trabajo", kind="law", published="2006-06-23",
                        url=S298_2006, title="Ley 2006-48 Reformatoria al Código del Trabajo (intermediación laboral y "
                                             "tercerización de servicios complementarios)"),
    "fe-erratas-codificacion-ct-2006": dict(label="Fe de erratas de la Codificación del Código del Trabajo (2006)",
                                            kind="law", published="2006-08-23", url=RO340_2006,
                                            title="Fe de erratas de la Codificación 2005-017 del Código del Trabajo "
                                                  "(Comisión de Legislación y Codificación, Registro Oficial 340)"),
    "ley-2006-60": dict(label="Ley 2006-60 Reformatoria al Código del Trabajo", kind="law", published="2006-10-30",
                        url=S387_2006, title="Ley 2006-60 Reformatoria al Código del Trabajo (trabajadores mineros)"),
    "ley-2007-77": dict(label="Ley 2007-77 Reformatoria al Código del Trabajo", kind="law", published="2007-05-02",
                        url=RO75_2007, title="Ley Reformatoria al Código del Trabajo (decimocuarta remuneración)"),
    "mandato-constituyente-8": dict(label="Mandato Constituyente 8 (2008)", kind="law", published="2008-05-06",
                                    url=S330_2008,
                                    title="Mandato Constituyente No. 8 (eliminación de la tercerización, la "
                                          "intermediación laboral y la contratación por horas)"),
    "ley-reformatoria-loscca-ct-2009": dict(label="Ley Reformatoria a la LOSCCA y al Código del Trabajo (2009)",
                                            kind="law", published="2009-02-13", url=S528_2009,
                                            title="Ley Orgánica Reformatoria a la Ley Orgánica de Servicio Civil y "
                                                  "Carrera Administrativa y al Código del Trabajo"),
    "ley-fondo-reserva-2009": dict(label="Ley para el Pago Mensual del Fondo de Reserva (2009)", kind="law",
                                   published="2009-07-29", url=S644_2009,
                                   title="Ley para el Pago Mensual del Fondo de Reserva y Régimen Solidario de Cesantía "
                                         "por parte del Estado"),
    "copci-2010": dict(label="Código Orgánico de la Producción, Comercio e Inversiones (2010)", kind="law",
                       published="2010-12-29", url=S351_2010,
                       title="Código Orgánico de la Producción, Comercio e Inversiones, Disposición reformatoria quinta"),
    "cc-031-10-scn-cc": dict(label="Sentencia 031-10-SCN-CC", kind="court", published="2011-01-27", url=S372_2011,
                             title="Corte Constitucional, sentencia 031-10-SCN-CC: inconstitucionalidad del inciso "
                                   "segundo del art. 581"),
    "ley-derechos-laborales-2012": dict(label="Ley Orgánica para la Defensa de los Derechos Laborales (2012)",
                                        kind="law", published="2012-09-26", url=S797_2012,
                                        title="Ley Orgánica para la Defensa de los Derechos Laborales"),
    "comf-2014": dict(label="Código Orgánico Monetario y Financiero", kind="law", enacted="2014-07-24",
                      published="2014-09-12", url=S332_2014,
                      title="Código Orgánico Monetario y Financiero (Registro Oficial, Segundo Suplemento 332, 12-IX-2014)"),
    "ley-justicia-laboral-2015": dict(label="Ley Orgánica para la Justicia Laboral (2015)", kind="law",
                                      enacted="2015-04-17", published="2015-04-20", url=S483_2015,
                                      title="Ley Orgánica para la Justicia Laboral y Reconocimiento del Trabajo en el "
                                            "Hogar"),
    "cogep-2015": dict(label="Código Orgánico General de Procesos", kind="law", published="2015-05-22", url=S506_2015,
                       title="Código Orgánico General de Procesos (Registro Oficial, Suplemento 506, 22-V-2015)"),
    "ley-trabajo-juvenil-2016": dict(label="Ley Orgánica para la Promoción del Trabajo Juvenil (2016)", kind="law",
                                     enacted="2016-03-22", published="2016-03-28", url=S720_2016,
                                     title="Ley Orgánica para la Promoción del Trabajo Juvenil, Regulación Excepcional de "
                                           "la Jornada de Trabajo, Cesantía y Seguro de Desempleo"),
    "ley-feriados-2016": dict(label="Ley Orgánica Reformatoria a la LOSEP y al Código del Trabajo (2016)", kind="law",
                              enacted="2016-12-16", published="2016-12-20", url=S906_2016,
                              title="Ley Orgánica Reformatoria a la Ley Orgánica del Servicio Público y al Código del "
                                    "Trabajo (días de descanso obligatorio)"),
    "ley-sector-publico-2017": dict(label="Ley Orgánica Reformatoria a las Leyes que rigen el Sector Público (2017)",
                                    kind="law", published="2017-05-19", url=S1008_2017,
                                    title="Ley Orgánica Reformatoria a las Leyes que rigen el Sector Público"),
    "ley-acoso-laboral-2017": dict(label="Ley Orgánica Reformatoria para prevenir el Acoso Laboral (2017)", kind="law",
                                   published="2017-11-09", url=S116_2017,
                                   title="Ley Orgánica Reformatoria a la Ley Orgánica del Servicio Público y al Código del "
                                         "Trabajo para prevenir el Acoso Laboral"),
    "ley-violencia-mujeres-2018": dict(label="Ley Orgánica contra la Violencia hacia las Mujeres (2018)", kind="law",
                                       published="2018-02-05", url=S175_2018,
                                       title="Ley Orgánica Integral para Prevenir y Erradicar la Violencia contra las "
                                             "Mujeres"),
    "cc-ec40-2018": dict(label="Corte Constitucional, Edición Constitucional 40 (2018)", kind="court",
                         published="2018-04-06", url=EC40_2018, note=IMAGE_ONLY,
                         title="Corte Constitucional, resolución publicada el 6-IV-2018 (cited by the Lexis index as "
                               "'Resolución No. 2, Registro Oficial Suplemento 40'): modulación de los efectos de los "
                               "arts. 15 y 49 de la Ley Orgánica para la Justicia Laboral (arts. 97.1 y 459). NOT "
                               "APPLIED (image-only edition)"),
    "ley-fomento-productivo-2018": dict(label="Ley Orgánica para el Fomento Productivo (2018)", kind="law",
                                        published="2018-08-21", url=S309_2018,
                                        title="Ley Orgánica para el Fomento Productivo, Atracción de Inversiones, "
                                              "Generación de Empleo, y Estabilidad y Equilibrio Fiscal"),
    "ley-reformatoria-cogep-2019": dict(label="Ley Orgánica Reformatoria del COGEP (2019)", kind="law",
                                        enacted="2019-06-20", published="2019-06-26", url=S517_2019,
                                        title="Ley Orgánica Reformatoria al Código Orgánico General de Procesos"),
    "ley-apoyo-humanitario-2020": dict(label="Ley Orgánica de Apoyo Humanitario (2020)", kind="law",
                                       published="2020-06-22", url=S229_2020,
                                       title="Ley Orgánica de Apoyo Humanitario para combatir la crisis sanitaria "
                                             "derivada del COVID-19"),
    "cc-36-19-in-21": dict(label="Sentencia 36-19-IN/21", kind="court", enacted="2021-09-22", published="2021-11-04",
                           url=EC231_2021,
                           title="Corte Constitucional, sentencia 36-19-IN/21: inconstitucionalidad sustitutiva de la "
                                 "frase 'posteriores al parto' del art. 155 (Edición Constitucional 231)"),
    "ley-juventudes-2023": dict(label="Ley Orgánica de las Juventudes (2023)", kind="law", published="2023-01-04",
                                url=S222_2023, title="Ley Orgánica de las Juventudes"),
    "ley-economia-violeta-2023": dict(label="Ley Orgánica para Impulsar la Economía Violeta (2023)", kind="law",
                                      published="2023-01-20", url=S234_2023,
                                      title="Ley Orgánica para Impulsar la Economía Violeta"),
    "ley-cuidado-humano-2023": dict(label="Ley Orgánica del Derecho al Cuidado Humano (2023)", kind="law",
                                    published="2023-05-12", url=S309_2023,
                                    title="Ley Orgánica del Derecho al Cuidado Humano"),
    "ley-violencia-acoso-laboral-2024": dict(
        label="Ley Orgánica Reformatoria para la Erradicación de la Violencia y el Acoso Laboral (2024)", kind="law",
        published="2024-05-16", url=S559_2024, note=IMAGE_ONLY_SRI,
        title="Ley Orgánica Reformatoria para la Erradicación de la Violencia y el Acoso en todas las Modalidades de "
              "Trabajo (Registro Oficial, Suplemento 559, 16-V-2024). NOT APPLIED (image-only edition)"),
    "ley-victimas-femicidio-2024": dict(
        label="Ley Orgánica de Reparación a Familiares de Víctimas de Femicidio", kind="law", published="2024-06-27",
        url=S588_2024,
        note=("NOT APPLIED here: the Registro Oficial edition that publishes it (Tercer Suplemento 588) is page images "
              "without a text layer, and this repository does not OCR. Its Disposición reformatoria octava adds an "
              "article 152.3 (licencia o permiso sin remuneración) after art. 152, which is missing from this record "
              "(provision named from the SRI consolidation of 27-VI-2024)."),
        title="Ley Orgánica de Acompañamiento y Reparación Transformadora e Integral a Hijas, Hijos, Madres, Padres y "
              "demás Familiares de Víctimas de Femicidio y otras Muertes Violentas por Razones de Género"),
    "ley-derechos-discapacidad-2025": dict(
        label="Ley Orgánica Reformatoria para los Derechos Laborales de las Personas con Discapacidad (2025)",
        kind="law", published="2025-06-20", url=S64_2025,
        title="Ley Orgánica Reformatoria a Diversos Cuerpos Legales para Garantizar los Derechos Laborales de las "
              "Personas con Discapacidad, Enfermedades Raras, Huérfanas, Catastróficas y de Alta Complejidad y sus "
              "Sustitutos"),
    "ley-derechos-trabajadores-2023": dict(label="Ley Orgánica Reformatoria para la Defensa de los Derechos de los "
                                                 "Trabajadores (2023)", kind="law", published="2023-02-01",
                                           url=S242_2023,
                                           title="Ley Orgánica Reformatoria a Varias Leyes para la Defensa y Garantía de "
                                                 "los Derechos Individuales y Colectivos de los Trabajadores"),
}

# (law key(s), in-force day, edit function or list of provisions for an act that is not applied); a tuple of law keys
# credits every changed unit to all of them
STEPS = [
    ("ley-2006-28", "2006-01-30", ley_2006_28),
    (("ley-2006-28", "fe-erratas-ley-2006-28"), "2006-03-07", erratas_2006_28),
    ("ley-2006-39", "2006-04-13", ley_2006_39),
    ("ley-2006-40", "2006-04-27", ley_2006_40),
    ("ley-2006-48", "2006-06-23", ley_2006_48),
    ("fe-erratas-codificacion-ct-2006", "2006-08-23", erratas_2006_216),
    ("ley-2006-60", "2006-10-30", ley_2006_60),
    ("ley-2007-77", "2007-05-02", ley_2007_77),
    ("mandato-constituyente-8", "2008-05-06", mandato_8),
    ("ley-reformatoria-loscca-ct-2009", "2009-02-13", ley_2009_licencias),
    ("ley-fondo-reserva-2009", "2009-07-29", ley_fondo_reserva_2009),
    ("copci-2010", "2010-12-29", copci_2010),
    ("cc-031-10-scn-cc", "2011-01-27", cc_031_10_scn_cc),
    ("ley-derechos-laborales-2012", "2012-09-26", ley_derechos_laborales_2012),
    ("comf-2014", "2014-09-12", comf_2014),
    ("ley-justicia-laboral-2015", "2015-04-20", ley_justicia_laboral_2015),
    ("cogep-2015", "2015-05-22", cogep_2015_abandono),
    ("ley-justicia-laboral-2015", "2016-01-01", ley_justicia_laboral_2015_art15),
    ("ley-trabajo-juvenil-2016", "2016-03-28", ley_trabajo_juvenil_2016),
    ("cogep-2015", "2016-05-22", cogep_2015),
    ("ley-feriados-2016", "2016-12-20", ley_feriados_2016),
    ("ley-sector-publico-2017", "2017-05-19", ley_sector_publico_2017),
    ("ley-acoso-laboral-2017", "2017-11-09", ley_acoso_laboral_2017),
    ("ley-violencia-mujeres-2018", "2018-02-05", ley_violencia_mujeres_2018),
    ("cc-ec40-2018", "2018-04-06", ["art-0097-1", "art-0459"]),
    ("ley-fomento-productivo-2018", "2018-08-21", ley_fomento_productivo_2018),
    ("ley-reformatoria-cogep-2019", "2019-06-26", ley_reformatoria_cogep_2019),
    ("ley-apoyo-humanitario-2020", "2020-06-22", ley_apoyo_humanitario_2020),
    ("cc-36-19-in-21", "2021-11-04", cc_36_19_in_21),
    ("ley-juventudes-2023", "2023-01-04", ley_juventudes_2023),
    ("ley-economia-violeta-2023", "2023-01-20", ley_economia_violeta_2023),
    ("ley-derechos-trabajadores-2023", "2023-02-01", ley_derechos_trabajadores_2023),
    ("ley-cuidado-humano-2023", "2023-05-12", ley_cuidado_humano_2023),
    ("ley-violencia-acoso-laboral-2024", "2024-05-16",
     ["art-0042", "art-0044", "art-0046-1", "art-0172", "art-0173", "art-0545"]),
    ("ley-victimas-femicidio-2024", "2024-06-27", ["art-0152"]),
    ("ley-derechos-discapacidad-2025", "2025-06-20", ley_derechos_discapacidad_2025),
]

# image-only reforms whose amended provisions become STALE (the femicidio law only adds an article, art. 152.3)
STALE_BY = {"ley-violencia-acoso-laboral-2024": ["art-0042", "art-0044", "art-0046-1", "art-0172", "art-0173",
                                                 "art-0545"]}

DECISIONS = [
    "Código del Trabajo: the oldest version is the Codificación 2005-017 (Registro Oficial Suplemento 167, 16-XII-2005), in force from its publication (its Artículo final: the Code, its reforms and repeals are in force from their publication). The Code dates from 1938; older texts are not part of this history, so the first version is credited to the publisher as the oldest version available.",
    "Código del Trabajo units: art-NNNN for each article; articles added later keep their place (art-0346-1, art-0346-2 ... for the articles innumerados after art. 346); disp-transitoria-NN (each with the 'De la Ley ...' line that heads it in the codification), disp-final for the Artículo final; 'titulos' holds the Título, Capítulo and Parágrafo headings in order (headings the text layer sets on two lines are joined). The codification's introduction, its concordance table and its list of sources are not units. Repealed articles are removed.",
    "Código del Trabajo text: literals the text layer sets in one paragraph ('...; f) Los contratos a prueba;') are split one per line, in the base and in the amending acts' quoted text alike; tables keep the run-together text the gazette's text layer gives (arts. 131, 139, 218, 438).",
    "Código del Trabajo: every later version replays an amending act's own Registro Oficial text on the version before it, in order of entry into force: whole articles and paragraphs are cut from the act's PDF after an anchor phrase, and every short phrase an act inserts or replaces is checked to occur word for word in the act's PDF.",
    "Código del Trabajo: Ley 2006-28 (RO 198, 30-I-2006) was written against the numbering before the 2005 codification; the Congress's fe de erratas (RO 223, 7-III-2006) moved three of its provisions: numeral 35 of art. 42 is added after numeral 34 (not 'substituted'), the Título on work of persons with disabilities goes after art. 346 (not 352) and the new text on prescription replaces art. 403 (not 409). Its numerals 2 and 33 of art. 42 fit the codified text as published and are dated 30-I-2006; the three corrected provisions are dated 7-III-2006 and credited to both the law and the fe de erratas. The substituted article, printed 'Art. 409.-', is numbered 'Art. 403.-' as the fe de erratas directs.",
    "Código del Trabajo: Ley 2006-39 (RO 250, 13-IV-2006) is applied as worded where the words it names occur once in the codified text. Not applied, because the codification already worded the provision otherwise or the words occur more than once or not at all: art. 8 a) ('menores' -> 'adolescentes de quince años' in art. 139: twice), art. 17 a) (art. 158 num. 1: the codified numeral already speaks of 'los mecanismos de transferencia de los conocimientos'), art. 22 ('menores de edad' in art. 381: twice) and art. 23 ('Tribunal de Menores': in neither art. 381 nor art. 402). Its art. 17 b) adds a numeral '4.' after the existing numeral 4 of art. 158, and art. 19 inserts the new text as the third inciso of art. 262, before the inciso that was third. In art. 151 'el Consejo Nacional de la Niñez y Adolescencia' becomes 'los jueces de la niñez y adolescencia ...' (the article 'el' goes with the name it introduced). Art. 20 replaces the last phrase of art. 268 without the full stop the act sets inside its quotation marks.",
    "Código del Trabajo: WHERE THE HISTORY STOPS. Every act and ruling with a text layer that amended the Code from the codification of 16-XII-2005 to 20-VI-2025 is applied from its own gazette edition. Indexes (reading only): the 'Nota:' lines of a Lexis-style consolidation, 'Última modificación: 01-02-2023' (LegalCloud DOCX), and the SRI's consolidation 'Última modificación: Tercer Suplemento 588 de 27 de junio de 2024' (Internet Archive capture 20250422103829); after 27-VI-2024 only the Asamblea's list of laws, whose text layers were searched for the Code (codes/screen_trabajo.json). NOT APPLIED, image-only: the Corte Constitucional's modulation of arts. 97.1 and 459 (Edición Constitucional 40, 6-IV-2018), the Ley Orgánica Reformatoria para la Erradicación de la Violencia y el Acoso en todas las Modalidades de Trabajo (Suplemento 559, 16-V-2024: arts. 42 nums. 26 and 36, 44 m), 46.1, 172 num. 8, 173 num. 4, 545 nums. 8-13), the Ley de reparación a familiares de víctimas de femicidio (Tercer Suplemento 588, 27-VI-2024: a new art. 152.3) and the Ley Orgánica Reformatoria al Código del Trabajo para dignificar el trabajo del hogar (Segundo Suplemento 94, 1-VIII-2025: its covering letter and certificate have a text layer, its articles are page images, so which provisions it changes is not known here and it has no version). Image-only laws published after 27-VI-2024 could not be checked for reforms of the Code at all (about 40 of the Asamblea's list, among them the Ley Orgánica de la Primera Infancia and the law on age discrimination of 14-V-2025). The last version here is therefore NOT the law in force today, and this part stays on the preview branch.",
    "Código del Trabajo: the Ley para el Pago Mensual del Fondo de Reserva (Suplemento 644, 29-VII-2009), art. 4, is applied to arts. 95 and 201 (the Lexis index lost it: its notes read 'Art. 4 de Ley No. 0', which codes/index_docx.py took for the next article; found by codes/reconcile_trabajo.py). In art. 95 the words 'el pago mensual del fondo de reserva,' go after 'utilidades,' (the comma after 'utilidades' kept, so the series keeps one comma per item; Lexis and the SRI drop it), 'decimoquinto y decimosexto sueldos' leaves with its comma, and the conjunction 'y' between 'decimotercera' and 'decimocuarta' takes the place of the comma (the reading the COPCI of 2010 then quotes word for word). In art. 201 'o anualmente' leaves 'mensual' (Lexis and the SRI print 'mensualmente').",
    "Código del Trabajo: Ley Orgánica para la Justicia Laboral (Tercer Suplemento 483, 20-IV-2015) is read with plain rotext.paragraphs (codes/strict.py drops half of this edition). Its art. 15 (art. 97.1) is dated 1-I-2016 (its Disposición transitoria tercera); the rest 20-IV-2015. Its art. 7 deletes 'de enganche' from the heading of Parágrafo 2do, which then reads 'De los contratos, de grupo y de equipo' (Lexis drops the comma too); art. 9 deletes the sentence opening the third paragraph of numeral 33 of art. 42, with the space after it; art. 13 replaces 'Consejo Nacional de Salarios' wherever it stands in the articles it names (none in arts. 124 and 126; 'CONADES' stays: Lexis and the SRI drop it or quote the new name); art. 22 (art. 113) has no closing quotation mark and runs to the act's next article; art. 27 adds its text to num. 1 of art. 173 after the full stop it puts in place of the semicolon, with the stop the act prints inside its quotation (Lexis ends with ';'); art. 44 leaves 'autónomo que, hubiere invertido' as the deletion leaves it (as Lexis); art. 58 inserts its words into art. 630 without the full stop printed inside the quotation (Lexis adds a comma). Art. 35 (art. 195.3) keeps the gazette's 'en el Ley Orgánica de Discapacidades'.",
    "Código del Trabajo: the COGEP (Suplemento 506, 22-V-2015) is applied in two steps: its Disposición reformatoria sexta num. 9 (art. 634, término para el abandono) on publication, because its Disposición final segunda puts the rules 'que regulan períodos de abandono' in force at once; the rest of its reforms of the Code and its Disposición derogatoria octava (40 articles of procedure) on 22-V-2016, twelve months after publication. Its num. 4 adds 'previa' after the word 'excepción' in art. 571 where that word stands in lower case (Lexis also changes the heading to 'Excepción previa de incompetencia').",
    "Código del Trabajo: articles innumerados added after an article that already had some keep the earlier files' names: the article of 2016 on unpaid leave for child care, which its act puts right after art. 152, is art-0152-3 (after the two of 2009); the teletrabajo article of 2020, put right after art. 16, is art-0016-2 (after art. 16.1 of 2015). Their labels follow the numbers later acts give them (the Ley del Derecho al Cuidado Humano of 2023 calls them 'Art. 152.1' and, for the adoption leave, 'Art. 155.2'). Where an act adds a numeral or literal and names it ('añádase un numeral 36', 'un literal m)', 'un numeral 8'), the added paragraph opens with that designation; where an act deletes 'y' at the end of a numeral it removes the closing ' y,' (leaving ';'), and its other instructions on the final punctuation are applied as worded.",
    "Código del Trabajo: other choices for 2016-2023. Ley de Promoción del Trabajo Juvenil (2016): the text layer splits 'est e hecho' (read 'este hecho'); its article on leave is printed without quotation marks, up to the act's next Capítulo. Ley Orgánica Reformatoria para prevenir el Acoso Laboral (2017) is read through codes/strict.py (stray fragments of other columns sit inside its art. 9 in the plain layer). Ley contra la violencia hacia las mujeres (2018) adds a numeral '10.' after numeral 9 of art. 42 without renumbering the rest, so art. 42 has two numerals 10, as the act leaves it. The Ley de Apoyo Humanitario (2020) interprets art. 169 num. 6 in a Disposición interpretativa, which changes no words of the Code, and the Corte Constitucional's ruling of 2022 (Suplemento 259) on that interpretation, the Corte Nacional's precedent on art. 452 (Suplemento 44 of 2022) and the interpretive law of 2016 on art. 113 are not versions either. Sentencia 36-19-IN/21 (Edición Constitucional 231) replaces 'posteriores al parto' in art. 155 with the words it sets out. Ley de las Juventudes (2023) replaces art. 34.1 with text that carries no article number, as printed. Suplemento 242 of 2023: the running head 'Miércoles 1º de febrero de 2023' inside two paragraphs and two stray combining accents on 'podrá' are removed; a combining acute accent after an already accented vowel is removed wherever the replay quotes an act ('convocará́' in art. 118).",
    "Código del Trabajo: the Ley Orgánica del Derecho al Cuidado Humano (Suplemento 309, 12-V-2023) replaces the article innumerado on unpaid child-care leave and the one on adoption leave, and the third inciso of art. 155; its Capítulo III repeals arts. 24 and 25 of the Ley de Economía Violeta, so the two incisos those articles had put into art. 152 and the article on lactation leave after art. 154 leave the Code (as in the SRI's consolidation). Its first reform names 'plazo de diez días' in the second paragraph of art. 152, words art. 152 does not contain: not applied (the SRI changes 'diez días' of the paternity leave to 'quince (15) días' and says so in a note).",
    "Código del Trabajo: STALE rule (as in the COIP part). Provisions an image-only reform amended (the Ley de 16-V-2024 on violence and harassment: arts. 42, 44, 46.1, 172, 173, 545) keep their earlier text, which is not the law from that date; a later partial amendment of them is not applied either and is credited with a 'Partly NOT APPLIED' version note (Ley de 20-VI-2025, art. 10: numerals 37 and 38 of art. 42). New articles a later act adds whole are applied (art. 152.4 of 2025).",
    "Código del Trabajo: reconciled (codes/reconcile_trabajo.py, reading only). Against the Lexis-style consolidation of 1-II-2023: 540 numbered articles agree after normalising spacing, quotes and dashes; the rest are repealed articles Lexis keeps as headings, articles innumerados (compared by hand), table layout of arts. 131, 139, 218 and 438, the choices named in these decisions, and Lexis's editorial accents and quotation marks ('Ámbito', 'Más', quotes around the new name of the Consejo Nacional de Trabajo y Salarios). Against the SRI's consolidation of 27-VI-2024: 576 agree; the rest are the same classes, the image-only reforms of 2024 (STALE), the SRI's own renumbering of the articles after art. 152, and transcription slips of the SRI copy where Lexis and the gazette agree with this record (arts. 228, 262, 280, 435, 442, 447, 628).",
    "Código del Trabajo: no official consolidation to the present was found. The SRI's (27-VI-2024) is the newest found from a public body; the Ministerio del Trabajo's copy (2024/01, Ediciones Legales) stops at 12-V-2023; Lexis (LegalCloud) at 1-II-2023. None can confirm the text after 27-VI-2024, so the part has no .PUBLISH.",
    "Código del Trabajo: acts with no vigencia clause of their own (Leyes 2006-40, 2006-60, the Ley Orgánica para la Defensa de los Derechos Laborales of 2012) are dated by their publication (Código Civil art. 6); the others state that they are in force on publication.",
    "Código del Trabajo: the Ley 2006-48 on intermediación laboral and tercerización (Suplemento 298, 23-VI-2006) added a Capítulo of 21 articles innumerados after art. 346 and one after art. 557; the Mandato Constituyente No. 8 (Suplemento 330, 6-V-2008) repealed that law and, in the Code, art. 11 h), 14 g), 19 j), the second inciso of art. 41, the incisos sexto to décimo tercero of art. 17 and the words 'por horas' (in its heading, which now reads 'de temporada y.-' as the repeal leaves it; Lexis also drops the 'y') and 'o intermediarios' (three times in art. 100). The Mandato is in force 'en forma inmediata, sin perjuicio de su publicación'; its printed date of adoption (30-III-2008) does not match the Asamblea's record of 30-IV-2008, so the version is dated by its publication, 6-V-2008. Its tacit effect on the fines of art. 628 changes no words and is not a version.",
    "Código del Trabajo: the Código Orgánico de la Producción, Comercio e Inversiones (Suplemento 351, 29-XII-2010), Disposición reformatoria quinta, is applied whole; its numeral 5 quotes the words of art. 95 as the Ley of 2009 on the fondo de reserva left them. The Disposiciones generales of the Ley on días de descanso (Suplemento 906, 2016), which Lexis and the SRI print under art. 637, and the Disposición general of the Ley Reformatoria a la LOSCCA y al Código del Trabajo (Suplemento 528, 13-II-2009), which Lexis prints under art. 637, are those laws' own provisions, not the Code's, and are not units.",
]

AI_USE = [
    "Código del Trabajo: no generative model wrote legal text. The amendment map in codes/trabajo.py (which provision each act changes, and the anchor phrases before its new text in the act's PDF) was written by an AI agent (Claude) from reading each act; the words are cut from the gazette PDFs' text layers. No OCR was used.",
]


def replay(first: dict) -> list[dict]:
    out = []
    units = first
    STALE.clear()
    for law, day, edit in STEPS:
        laws_ = list(law) if isinstance(law, tuple) else [law]
        url = LAWS[laws_[-1]]["url"]
        if isinstance(edit, list):
            for k in edit:
                if k not in units:
                    raise SystemExit(f"{law}: no unit {k}")
            STALE.update(STALE_BY.get(law, []))
            v = {"from": day, "source_url": url, "sha256": sha_of(url), "changes": {},
                 "credits": {k: laws_ for k in sorted(edit, key=order)}}
            if LAWS[laws_[-1]].get("note"):
                v["note"] = LAWS[laws_[-1]]["note"]
            if out and out[-1]["from"] == day:
                v["same_day"] = True
            out.append(v)
            continue
        u = Units(units)
        u.skipped = []
        edit(u)
        new = dict(sorted(u.u.items(), key=lambda kv: order(kv[0])))
        changed = sorted((k for k in set(units) | set(new) if units.get(k) != new.get(k)), key=order)
        skipped = sorted(set(u.skipped) - set(changed), key=order)
        if not changed:
            raise SystemExit(f"{law}: no change")
        v = {"from": day, "source_url": url, "sha256": sha_of(url),
             "changes": {k: new.get(k) for k in changed},
             "credits": {k: laws_ for k in sorted(set(changed) | set(skipped), key=order)}}
        if skipped:
            names = ", ".join(new[k].get("label") or k for k in skipped)
            v["note"] = PARTLY.format(names, "it" if len(skipped) == 1 else "them",
                                      "it keeps" if len(skipped) == 1 else "they keep")
        if out and out[-1]["from"] == day:
            v["same_day"] = True
        out.append(v)
        units = new
    return out


def build_act() -> dict:
    units = base_units()
    first = {"from": "2005-12-16", "source_url": S167_2005, "sha256": sha_of(S167_2005), "units": units, "credits": {}}
    return {"slug": "codigo-trabajo", "short": "CT", "title": "Código del Trabajo", "url": S167_2005,
            "first_law": None, "earlier_laws": [BASE_LAW], "versions": [first] + replay(units)}


def laws() -> dict:
    return {k: {"label": v["label"], "title": v["title"], "kind": v["kind"], "enacted": v.get("enacted"),
                "published": v["published"], "url": v["url"], "temporary_until": None,
                "restores": v.get("restores"), "note": v.get("note")} for k, v in LAWS.items()}


def sources() -> list[dict]:
    n = sum(len(v) for v in EDITIONS.values())
    return [
        {"name": "Registro Oficial del Ecuador (Código del Trabajo and its amending acts)",
         "url": "https://www.registroficial.gob.ec", "retrieved": RETRIEVED, "requests": n,
         "licence": "No licence stated on the site; official gazette text.",
         "notes": "One PDF per gazette edition, served by esacc.corteconstitucional.gob.ec, found through the site's month listings (codes/editions_trabajo.py -> codes/editions_trabajo.json). Every version's wording is cut from the text layer of the 2005 codification or of the amending act; editions without a text layer are listed in decisions and not applied."},
        {"name": "Lexis-style consolidation of the Código del Trabajo, 'Última modificación: 01-02-2023' (LegalCloud download)",
         "url": "https://legalcloud.ec/download/codigo-del-trabajo/", "retrieved": RETRIEVED, "requests": 1,
         "licence": "Publisher's copyright; read only, nothing copied.",
         "notes": "Index of amending acts ('Nota:' lines, codes/index_docx.py trabajo) and reconciliation to 1-II-2023 (codes/reconcile_trabajo.py). Reading only."},
        {"name": "Servicio de Rentas Internas (SRI), Dirección Nacional Jurídica: consolidation of the Código del Trabajo, 'Última modificación: Tercer Suplemento del Registro Oficial 588 de 27 de junio de 2024'",
         "url": "https://www.sri.gob.ec/o/sri-portlet-biblioteca-alfresco-internet/descargar/a5c99ffe-c498-4722-b408-fe672321c82c/Codigo_Trabajo_act_27062024.pdf",
         "retrieved": RETRIEVED, "requests": 1,
         "licence": "No licence stated; read through the Internet Archive (capture 20250422103829), reading only, nothing copied.",
         "notes": "Index of the reforms of 2023-2024 (its notes in parentheses) and reconciliation to 27-VI-2024 (codes/reconcile_trabajo.py --sri)."},
        {"name": "Asamblea Nacional, 'Leyes aprobadas'", "url": "https://www.asambleanacional.gob.ec/es/leyes-aprobadas",
         "retrieved": RETRIEVED, "requests": 0, "licence": "No licence stated; official copies of Registro Oficial editions.",
         "notes": "Laws 2023-2026 (the COIP part's cache); their text layers were searched for the Code (codes/screen.py -> codes/screen_trabajo.json). Reading only."},
        {"name": "Internet Archive (Wayback Machine) CDX index", "url": "https://web.archive.org/", "retrieved": RETRIEVED,
         "requests": 14, "licence": "Internet Archive terms of use; reading only.",
         "notes": "Searched for consolidations of the Code on gob.ec hosts (codes/find_consol.py); see decisions."},
    ]


def main() -> None:
    act = build_act()
    part = {"laws": laws(), "acts": [act], "sources": sources(), "applies": [], "decisions": DECISIONS, "ai_use": AI_USE}
    OUT.parent.mkdir(exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    data = json.dumps(part, ensure_ascii=False, indent=1) + "\n"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(data)
    os.replace(tmp, OUT)
    n = sum(len(v.get("changes", {})) for v in act["versions"][1:])
    print(f"{OUT.name}: {len(act['versions'])} versions, {len(part['laws'])} laws, {n} unit changes, {len(data)} bytes")


if __name__ == "__main__" and "--base" not in sys.argv:
    main()

if __name__ == "__main__" and "--base" in sys.argv:
    u = base_units()
    print(len(u))
    print(u["titulos"]["text"])
    for k in ["art-0011", "art-0014", "art-0131", "disp-transitoria-03", "disp-final"]:
        print(k, u[k]["text"])
