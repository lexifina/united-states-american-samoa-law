"""Write corpus.d/80-cogep.json: the Código Orgánico General de Procesos (COGEP, 2015) and its amending acts.

Reads only the cache (fetch with `python -X utf8 codes/editions.py`, which finds and downloads every edition named in
codes/editions.json). Deterministic: the same cache gives the same bytes. The part is written atomically.

    python -X utf8 codes/cogep.py            (COGEP_OUT=... to write elsewhere)

Base: Registro Oficial Suplemento 506, 22-V-2015 (text layer). Amending acts and rulings from the 'Nota:' lines of a
Lexis consolidation to 7-II-2023 (codes/index_docx.py cogep, reading only) and, after it, from the text layers of every
law on the Asamblea's 'leyes aprobadas' list 2023-2026 (codes/screen.py -> codes/screen_cogep.json).
Every applied change is cut from the text layer of the amending act's gazette edition; acts printed only as page
images are NOT applied (no OCR), and get a version of their own that changes no words.
"""
from __future__ import annotations

import copy
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
from replay import Units, S506_2015  # noqa: E402
import strict  # noqa: E402

OUT = Path(os.environ.get("COGEP_OUT", HERE.parent / "corpus.d" / "80-cogep.json"))
RETRIEVED = "2026-10-29"
_EDITIONS = {**json.loads((HERE.parent / "coip" / "editions.json").read_text(encoding="utf-8")),
             **json.loads((HERE / "editions.json").read_text(encoding="utf-8"))}


def ed(name: str, title: str) -> str:
    hits = [e["pdf"] for e in _EDITIONS[name] if e["title"] == title]
    if len(hits) != 1:
        raise SystemExit(f"edition {name} {title!r}: {len(hits)} matches")
    return hits[0]


S1_652_2015 = ed("s652-2015", "Primer Suplemento")
S899_2016 = ed("s899-2016", "Primer Suplemento")
EC1_2017 = ed("ec1-2017", "Ediciones Constitucionales")
S2_31_2017 = ed("s31-2017", "Segundo Suplemento")
EC19_2017 = ed("ec19-2017", "Ediciones Constitucionales")
S309_2018 = ed("s309-2018", "Primer Suplemento")
S517_2019 = ed("s517-2019", "Primer Suplemento")
S345_2020 = ed("s345-2020", "Primer Suplemento")
EC137_2021 = ed("ec137-2021", "Ediciones Constitucionales")
EC156_2021 = ed("ec156-2021", "Ediciones Constitucionales")
S5_452_2021 = ed("s452-2021", "Quinto Suplemento")
S3_587_2021 = ed("s587-2021", "Tercer Suplemento")
EC53_2022 = ed("ec53-2022", "Ediciones Constitucionales")
S3_245_2023 = ed("s245-2023", "Tercer Suplemento")
S3_68_2025 = ed("s68-2025", "Tercer Suplemento")
EC96_2025 = ed("ec96-2025", "Ediciones Constitucionales")

ORD = ["PRIMERA", "SEGUNDA", "TERCERA", "CUARTA", "QUINTA", "SEXTA", "SÉPTIMA", "OCTAVA", "NOVENA", "DÉCIMA"]
ORD_LOW = ["primera", "segunda", "tercera", "cuarta", "quinta", "sexta", "séptima", "octava", "novena", "décima"]


def ordinal(word: str) -> int:
    w = word.replace("DECIMO", "DÉCIMO")
    if w.startswith("DÉCIMO "):
        return 10 + ORD.index(w[7:]) + 1
    return ORD.index(w) + 1


def ordinal_label(n: int) -> str:
    return ORD_LOW[n - 1] if n <= 10 else "décimo " + ORD_LOW[n - 11]


DISP = {"DISPOSICIONES GENERALES": ("disp-general", "Disposición general", "general"),
        "DISPOSICIONES TRANSITORIAS": ("disp-transitoria", "Disposición transitoria", "transitional"),
        "DISPOSICIONES REFORMATORIAS": ("disp-reformatoria", "Disposición reformatoria", "amending"),
        "DISPOSICIONES DEROGATORIAS": ("disp-derogatoria", "Disposición derogatoria", "repeal"),
        "DISPOSICIONES FINALES": ("disp-final", "Disposición final", "final")}
ORDRX = r"((?:D[ÉE]CIMO )?(?:%s))\.-" % "|".join(ORD)
ART = re.compile(r"^Artículo (\d+)\.-")
# literals set in one paragraph by the text layer ("... de: a) El pago ...; b) La ...") go one per line, in the base
# and in the amending acts' text alike (same rule as codes/comercio.py)
ITEM = re.compile(r"(?<=[:;,.]) (?=[a-z]\) [A-ZÁÉÍÓÚÑ¿\"])")


def split_items(ps: list[str]) -> list[str]:
    out: list[str] = []
    for p in ps:
        out.extend(ITEM.split(p))
    return out


def art_key(n: int, extra: int = 0) -> str:
    return f"art-{n:03d}" + (f"-{extra}" if extra else "")


def order(key: str) -> tuple:
    m = re.match(r"art-(\d{3})(?:-(\d+))?$", key)
    if m:
        return (1, int(m.group(1)), int(m.group(2) or 0), "")
    rank = {"disp-general": 2, "disp-transitoria": 3, "disp-reformatoria": 4, "disp-derogatoria": 5,
            "disp-final": 6, "titulos": 7}
    return (rank.get(key.rsplit("-", 1)[0], 8), 0, int(key.rsplit("-", 1)[1]) if key[-1].isdigit() else 0, key)


def sha_of(url: str) -> str:
    return hashlib.sha256(fetch.cached(url).read_bytes()).hexdigest()


# ---------------------------------------------------------------- one gazette edition, strict text layer

class Ed:
    _cache: dict[str, "Ed"] = {}

    def __new__(cls, url: str):
        if url in cls._cache:
            return cls._cache[url]
        self = super().__new__(cls)
        path = fetch.cached(url)
        if path is None:
            raise SystemExit(f"not in cache: {url}")
        self.url = url
        self.paras = strict.paragraphs(path)
        self.flat = re.sub(r"\s+", " ", "\n".join(self.paras))
        cls._cache[url] = self
        return self

    def check(self, *phrases: str) -> None:
        for p in phrases:
            if re.sub(r"\s+", " ", p) not in self.flat:
                raise SystemExit(f"phrase not in {self.url[-24:]}: {p!r}")

    def index(self, anchor: str, after: str | None = None) -> int:
        start = self.index(after) + 1 if after else 0
        hits = [i for i in range(start, len(self.paras)) if anchor in self.paras[i]]
        if not hits:
            raise SystemExit(f"anchor not found in {self.url[-24:]}: {anchor!r}")
        return hits[0]

    def block(self, anchor: str, stop: str, after: str | None = None) -> list[str]:
        """The paragraphs after the one holding `anchor`, up to (not including) the next one matching `stop`,
        without the act's opening and closing quotation marks."""
        i = self.index(anchor, after) + 1
        out = []
        while i < len(self.paras) and not re.match(stop, self.paras[i]):
            out.append(self.paras[i])
            i += 1
        if not out:
            raise SystemExit(f"empty block after {anchor!r}")
        return split_items(dequote(out))

    def inline(self, anchor: str, after: str | None = None) -> list[str]:
        """The rest of the anchor's paragraph after `anchor`, without its quotation marks."""
        p = self.paras[self.index(anchor, after)]
        return split_items(dequote([p[p.index(anchor) + len(anchor):].strip()]))


def dequote(block: list[str]) -> list[str]:
    """Strip the act's quotation marks around a block. Spanish sets the full stop after the closing quote: when the
    quoted text has no final stop of its own and the act's stop follows the quote, the stop belongs to the text."""
    b = [x.strip() for x in block]
    if b[0].startswith('"'):
        b[0] = b[0][1:].lstrip()
    m = re.search(r'"\s*([.,;]?)$', b[-1])
    if m and b[-1].count('"') % 2 == 1:
        inner = b[-1][:m.start()].rstrip()
        if m.group(1) == "." and not re.search(r"[.:;]$", inner):
            inner += "."
        b[-1] = inner
    return b


# ---------------------------------------------------------------- base

TITLE = "CÓDIGO ORGÁNICO GENERAL DE PROCESOS "


def base_units() -> dict:
    ps = strict.paragraphs(fetch.cached(S506_2015))
    start = next(i for i, p in enumerate(ps) if p.startswith(TITLE + "LIBRO I"))
    units: dict[str, dict] = {}
    heads: list[str] = []
    cur: str | None = None
    disp: tuple | None = None
    expect = 1
    for p in ps[start:]:
        if p.startswith("Dado y suscrito"):
            break
        if p.startswith(TITLE):
            p = p[len(TITLE):]
        if p in DISP and expect == 440:
            disp = DISP[p]
            heads.append(p)
            cur = None
            continue
        if disp:
            m2 = re.match(ORDRX, p)
            if m2:
                n = ordinal(m2.group(1))
                cur = f"{disp[0]}-{n:02d}"
                if cur in units:
                    raise SystemExit(f"{cur} twice")
                units[cur] = {"label": f"{disp[1]} {ordinal_label(n)}", "kind": disp[2], "text": ""}
            elif cur is None:
                raise SystemExit(f"text outside a disposition: {p[:60]!r}")
            units[cur]["text"] += "".join(x + "\n" for x in split_items([p]))
            continue
        m = ART.match(p)
        if m:
            n = int(m.group(1))
            if n != expect:
                raise SystemExit(f"article {n} where {expect} was expected")
            expect += 1
            cur = art_key(n)
            units[cur] = {"label": f"Art. {n}", "kind": "art", "text": ""}
        elif not re.search(r"[a-zñáéíóúü]", p) or cur is None:
            heads.append(p)  # LIBRO / TÍTULO / CAPÍTULO / SECCIÓN headings with their names
            continue
        units[cur]["text"] += "".join(x + "\n" for x in split_items([p]))
    if expect != 440:
        raise SystemExit(f"stopped at article {expect - 1}")
    units["titulos"] = {"label": "Libros, títulos, capítulos y secciones", "kind": "headings",
                        "text": "".join(h + "\n" for h in heads)}
    return dict(sorted(units.items(), key=lambda kv: order(kv[0])))


# ---------------------------------------------------------------- edit helpers

_WHOLE: set[str] = set()  # units an edit substituted whole in the current step
HEAD = r'^Art(?:ículo|\.)?\s*\.?\s*-?\s*{n}\s*\.?\s*-?\s*'


def whole(u: Units, n: int, b: list[str], extra: int = 0, label: str | None = None) -> None:
    """Substitute art. n entirely. The act's own heading form ('Art. 19.-', 'Artículo. 256.-', 'Artículo.- 249.') is
    written in the Code's form 'Artículo 19.-'; a text given without its number gets the number in front."""
    b = list(b)
    _WHOLE.add(art_key(n, extra))
    num = f"{n}.{extra}" if extra else str(n)
    m = re.match(HEAD.format(n=re.escape(num)), b[0])
    b[0] = f"Artículo {num}.- " + (b[0][m.end():] if m else b[0])
    u.set_unit(art_key(n, extra), b, label=label or f"Art. {num}")


def para_of(u: Units, key: str, prefix: str) -> int:
    return u.find(key, prefix)


def after_word(u: Units, key: str, para: int, word: str, phrase: str, strip_comma: bool = False) -> None:
    """Insert `phrase` after the one occurrence of `word` in paragraph `para` (a whole word)."""
    ps = u.paras(key)
    hits = [m for m in re.finditer(rf"\b{re.escape(word)}\b", ps[para])]
    if len(hits) != 1:
        raise SystemExit(f"{key} para {para}: {len(hits)} x {word!r}")
    e = hits[0].end()
    ins = phrase.rstrip(",") if strip_comma and ps[para][e:e + 1] == "," else phrase
    ps[para] = ps[para][:e] + " " + ins + ps[para][e:]
    u.put(key, ps)


def numeral(u: Units, key: str, n: int) -> int:
    hits = [i for i, p in enumerate(u.paras(key)) if re.match(rf"{n}\s*\.-?\s", p)]
    if len(hits) != 1:
        raise SystemExit(f"{key}: {len(hits)} paragraphs numbered {n}")
    return hits[0]


# ---------------------------------------------------------------- the acts

def ley_app_2015(u: Units) -> None:
    """Ley Orgánica de Incentivos para Asociaciones Público-Privadas, Primer Suplemento 652, 18-XII-2015,
    Disposición derogatoria primera; in force on publication (its Disposición final)."""
    e = Ed(S1_652_2015)
    e.check('Disposiciones Derogatorias Primera.- Deróguense en el artículo 329 del Código Orgánico General de Procesos, '
            'la frase: "Serán ejecutables, desde que se encuentren firmes o se hallen ejecutoriados.", y el último inciso.',
            "Disposición Final.- La presente Ley Orgánica entrará en vigencia a partir de su publicación en el Registro Oficial.")
    u.drop("art-329", "Serán ejecutables, desde que se encuentren firmes o se hallen ejecutoriados.")
    ps = u.paras("art-329")
    u.put("art-329", ps[:-1])


def coescci_2016(u: Units) -> None:
    """Código Orgánico de la Economía Social de los Conocimientos, Creatividad e Innovación, Primer Suplemento 899,
    9-XII-2016, Disposición reformatoria décima primera (11.1); in force on publication (its Disposición final)."""
    e = Ed(S899_2016)
    e.check("DÉCIMA PRIMERA.- Refórmese en el Código Orgánico General de Procesos, lo siguiente:",
            "ÚNICA.- El Presente Código entrará en vigencia a partir de su publicación en el Registro Oficial.")
    b = e.block("11.1.- Agréguese a continuación del artículo 133 el siguiente artículo innumerado:", r"^DÉCIMA SEGUNDA\.-")
    u.set_unit(art_key(133, 1), b, label="Art. innumerado (tras el art. 133)")


def coa_2017(u: Units) -> None:
    """Código Orgánico Administrativo, Segundo Suplemento 31, 7-VII-2017, Disposición reformatoria primera; in force
    twelve months after publication (its Disposición final)."""
    e = Ed(S2_31_2017)
    top = "PRIMERA.- Refórmase en el Código Orgánico General de Procesos, las siguientes disposiciones:"
    e.check("El Código Orgánico Administrativo entrará en vigencia luego de transcurridos doce meses, contados a partir "
            "de su publicación en el Registro Oficial.")
    stop = r"^(\d\. |SEGUNDA\.-)"
    b = e.block("1. Incluir después del artículo 14 el siguiente artículo:", stop, after=top)
    b[0] = re.sub(r"^Artículo 14 A\.-", "Artículo 14 A.-", b[0])
    u.set_unit(art_key(14, 1), b, label="Art. 14 A")
    b = e.block("2. Agrégase en el artículo 53 como párrafo final el siguiente texto:", stop, after=top)
    u.insert("art-053", u.count("art-053"), b)
    b = e.block("3. Sustitúyese el número 4 del artículo 326 por el siguiente:", stop, after=top)
    ps = u.paras("art-326")
    i = numeral(u, "art-326", 4)
    j = i + 1
    while j < len(ps) and re.match(r"[a-z]\) ", ps[j]):
        j += 1
    u.set_para("art-326", i, b, count=j - i)
    b = e.block("4. Sustitúyese el artículo 327 por el siguiente:", stop, after=top)
    whole(u, 327, b)
    b = e.block("5. A continuación del artículo 370 incorpórase el siguiente artículo:", stop, after=top)
    u.set_unit(art_key(370, 1), b, label="Art. 370 A")
    b = e.block("6. Añádase como Disposición General Cuarta, la siguiente:", stop, after=top)
    u.u["disp-general-04"] = {"label": "Disposición general cuarta", "kind": "general", "text": ""}
    u.put("disp-general-04", b)


def fomento_productivo_2018(u: Units) -> None:
    """Ley Orgánica para el Fomento Productivo, Atracción de Inversiones, Generación de Empleo, y Estabilidad y
    Equilibrio Fiscal, Primer Suplemento 309, 21-VIII-2018, Disposición derogatoria segunda; in force on publication."""
    e = Ed(S309_2018)
    e.check('SEGUNDA.- Elimínese en los artículos 102 al 106 del Código Orgánico General de Procesos - COGEP las palabras '
            '"laudo arbitral". Déjese sin efecto la Disposición Derogatoria Décima Tercera del COGEP')
    n = 0
    for a in range(102, 107):
        k = art_key(a)
        ps = u.paras(k)
        for i, p in enumerate(ps):
            while "laudo arbitral" in p:
                left, right = p.split("laudo arbitral", 1)
                if left.endswith(" ") and right[:1] in (" ", ".", ",", ";", ":"):
                    left = left.rstrip(" ")
                p = left + right
                n += 1
            ps[i] = p
        u.put(k, ps)
    if n != 3:
        raise SystemExit(f"laudo arbitral: {n} occurrences")
    u.remove("disp-derogatoria-13")


R517 = r'^(Artículo \d+\.- (?:Agr[eé]gase|Sustit|Elim|A continuaci)|DISPOSICIONES)'


def reformatoria_2019(u: Units) -> None:
    """Ley Orgánica Reformatoria del Código Orgánico General de Procesos, Primer Suplemento 517, 26-VI-2019; in force
    on publication (its Disposición final)."""
    e = Ed(S517_2019)
    e.check("La presente reforma entrará en vigencia a partir de su publicación en el Registro Oficial.")

    def b(anchor: str) -> list[str]:
        return e.block(anchor, R517)

    u.insert("art-009", u.count("art-009"), b("Artículo 1.- Agregase como párrafo final del artículo 9"))
    u.set_para("art-010", u.count("art-010") - 1, b("Artículo 2.- Sustitúyase el párrafo final del artículo 10"))
    e.check('Artículo 3.- Agregase en el primer párrafo del artículo 16, después de la palabra "preliminar", la frase: '
            '"o hasta en la primera fase de la audiencia única,"')
    after_word(u, "art-016", 0, "preliminar", "o hasta en la primera fase de la audiencia única,", strip_comma=True)
    (p,) = b("Artículo 4.- Sustitúyase el primer párrafo del artículo 19")
    u.set_para("art-019", 0, [re.sub(r"^Art\. 19\.-", "Artículo 19.-", p)])
    whole(u, 27, b("Artículo 5.- Sustitúyase el artículo 27 por el siguiente:"))
    whole(u, 28, b("Artículo 6.- Sustitúyase el artículo 28 por el siguiente:"))
    whole(u, 36, b("Artículo 7.- Sustitúyase el artículo 36 por el siguiente texto:"))
    whole(u, 42, b("Artículo 8.- Sustitúyase el artículo 42, por el siguiente texto:"))
    whole(u, 43, b("Artículo 9.- Sustitúyase el artículo 43, por el siguiente texto:"))
    (new,) = b('Artículo 10.- Sustitúyase en el primer párrafo del artículo 55 la frase')
    e.check('la frase: "en su domicilio o residencia a cualquier persona de la familia." por el siguiente texto:')
    # the act quotes the old phrase with its final full stop and the new one without: the stop stays
    u.sub("art-055", "en su domicilio o residencia a cualquier persona de la familia.", new + ".", para=0)
    (p,) = e.inline("Artículo 11.- Sustitúyase el tercer párrafo del artículo 56 por el siguiente texto·")
    # 'párrafo' counts incisos: the numerals 1 and 2 belong to the first, so the third is the one on persons abroad
    if not u.paras("art-056")[4].startswith("Para el caso anterior"):
        raise SystemExit("art. 56: third inciso not where expected")
    u.set_para("art-056", 4, [p])
    e.check('Artículo 12.- Eliminase en el artículo 58, luego de la palabra "desconocidos", la frase: "cuya residencia sea '
            'imposible determinar."')
    u.drop("art-058", " cuya residencia sea imposible determinar")
    whole(u, 60, b("Artículo 13.- Sustitúyase el artículo 60 por el siguiente texto:"))
    u.set_para("art-064", numeral(u, "art-064", 4), b("Artículo 14.- Sustitúyase el número 4 del artículo 64"))
    whole(u, 68, b("Artículo 15.- A continuación del artículo 68, agregase un artículo"), extra=1)
    (p,) = b("Artículo 16.- Agrégase al final del número 1 del artículo 87 el siguiente texto:")
    i = numeral(u, "art-087", 1)
    ps = u.paras("art-087")
    ps[i] = ps[i] + " " + p
    u.put("art-087", ps)
    # the act says 'número 2' but its text is numeral 7, the only numeral on testimonial declarations: numeral 7 is
    # replaced (decisions)
    (p,) = b("Artículo 17.- Sustitúyase el número 2 del artículo 122 por el siguiente texto:")
    u.set_para("art-122", numeral(u, "art-122", 7), [p])
    whole(u, 137, b("Artículo 18.- Sustitúyase el artículo 137 por el siguiente texto:"))
    whole(u, 146, b("Artículo 19.- Sustitúyase el artículo 146 por el siguiente texto:"))
    whole(u, 148, b("Artículo 20.- Sustitúyase el artículo 148 por el siguiente texto:"))
    # Artículo 21 (art. 148 first paragraph, "o única en los procedimientos de una sola audiencia" after "preliminar"):
    # the wording Artículo 20 gave already reads "preliminar o única en los procesos de una sola audiencia" (decisions)
    e.check('Artículo 21.- Agregase en primer párrafo del artículo 148, después de la palabra "preliminar"')
    u.set_para("art-151", 2, b("Artículo 22.- Sustitúyase el tercer párrafo del artículo 151"))
    n2, n3 = [dequote([x])[0] for x in b("Artículo 23.- Sustitúyase los números 2 y 3 del artículo 153")]
    u.set_para("art-153", numeral(u, "art-153", 2), [n2])
    u.set_para("art-153", numeral(u, "art-153", 3), [n3])
    e.check('Artículo 24.- Agregase en los artículos 156, 159 párrafo cuarto, 174 párrafo primero y 188, después de la '
            'palabra "juicio", la frase:', '"o en la segunda fase de la audiencia única."')
    ph = "o en la segunda fase de la audiencia única"
    for k, para in (("art-156", 0), ("art-159", 3), ("art-174", 0), ("art-188", 0)):
        after_word(u, k, para, "juicio", ph)
    u.insert("art-156", 1, b("Artículo 25.- Agregase como segundo párrafo en el artículo 156"))
    e.check('Artículo 26.- Sustitúyase en el artículo 157, la palabra "podrá" por "deberá" y agregase a continuación de la '
            'frase: "otro efecto", el siguiente texto: "La falta de contestación se tendrá como negativa de los '
            'fundamentos de la demanda."')
    u.sub("art-157", "podrá", "deberá")
    u.sub("art-157", "otro efecto.", "otro efecto. La falta de contestación se tendrá como negativa de los fundamentos "
          "de la demanda.")
    e.check('Artículo 27.- Agregase en el segundo párrafo del artículo 160, 163 número 1 y 177 número 4, después de la '
            'palabra "preliminar", la frase: "o en la segunda fase de la audiencia única."')
    after_word(u, "art-160", 1, "preliminar", ph)
    after_word(u, "art-163", numeral(u, "art-163", 1), "preliminar", ph)
    after_word(u, "art-177", numeral(u, "art-177", 4), "preliminar", ph)
    u.set_para("art-169", 2, b("Artículo 28.- Sustitúyase el párrafo tercero del artículo 169"))
    u.insert("art-169", u.count("art-169"), b("Artículo 29.- Agregase como párrafo final del artículo 169"))
    e.check('Artículo 30.- Agregase en los artículos 166, 181, 196 párrafo primero, 198, 202 párrafo segundo, 222 párrafo '
            'primero, 223 párrafo segundo, después de la palabra "juicio", la frase: "o única."')
    for k, para in (("art-166", 0), ("art-181", 0), ("art-196", 0), ("art-198", 0), ("art-202", 1), ("art-222", 0),
                    ("art-223", 1)):
        after_word(u, k, para, "juicio", "o única")
    u.set_para("art-204", 1, b("Artículo 31.- Sustitúyase el segundo párrafo del artículo 204"))
    e.check('Artículo 32.- Agregase en el número 1 del artículo 234, después de la frase "se realiza en", la frase: '
            '"la audiencia única."')
    i = numeral(u, "art-234", 1)
    u.sub("art-234", "se realiza en", "se realiza en la audiencia única", para=i)
    u.insert("art-236", u.count("art-236"), b("Artículo 33.- Agregase a final del artículo 236 lo siguiente:"))
    whole(u, 245, b("Artículo 34.- Sustitúyase el artículo 245 por el siguiente texto:"))
    whole(u, 247, b("Artículo 35.- Sustitúyase el artículo 247 por el siguiente texto:"))
    u.insert("art-248", 1, b("Artículo 36.- Agregase como párrafo segundo en el artículo 248"))
    whole(u, 249, b("Artículo 37.- Sustitúyase el artículo 249, por el siguiente texto:"))
    whole(u, 256, b("Artículo 38.- Sustitúyase el artículo 256, por el siguiente texto:"))
    whole(u, 257, b("Artículo 39.- Sustitúyase el artículo 257 por el siguiente texto:"))
    (p,) = b("Artículo 40.- Sustitúyase el párrafo primero del artículo 258")
    u.set_para("art-258", 0, [re.sub(HEAD.format(n=258), "Artículo 258.- ", p)])
    u.insert("art-263", u.count("art-263"), b("Artículo 41.- Agregase como párrafo final en el artículo 263"))
    e.check('Artículo 42.- Sustitúyase en el párrafo final del artículo 266 la frase "dentro del término de diez días", '
            'por el siguiente texto: "dentro del término de treinta días"')
    u.sub("art-266", "dentro del término de diez días", "dentro del término de treinta días", para=u.count("art-266") - 1)
    whole(u, 270, b("Artículo 43.- Sustitúyase el artículo 270 por el siguiente texto:"))
    (p,) = b("Artículo 44.- Agregase al final del número 3 del artículo 273")
    i = numeral(u, "art-273", 3)
    ps = u.paras("art-273")
    ps[i] = ps[i] + " " + p
    u.put("art-273", ps)
    u.insert("art-283", u.count("art-283"), b("Artículo 45.- Agregase como párrafo final en el artículo 283"))
    u.set_para("art-294", numeral(u, "art-294", 3), b("Artículo 46.- Sustitúyase el número 3 del artículo 294"))
    u.set_para("art-304", numeral(u, "art-304", 1), b("Artículo 47.- Sustitúyase el número 1 del artículo 304"))
    u.set_para("art-306", numeral(u, "art-306", 5), b("Artículo 48.- Sustitúyase el número 5 del artículo 306"))
    u.insert("art-308", 1, b("Artículo 49.- Agregase como segundo párrafo en el artículo 308"))
    whole(u, 317, b("Artículo 50.- Sustitúyase el artículo 317 por el siguiente texto:"))
    blk = b("Artículo 51.- Agregase luego del primer párrafo del artículo 330 lo siguiente:")
    u.insert("art-330", 1, [x.strip('"').strip() if x.endswith('"') and x.count('"') == 1 else x for x in blk])
    u.set_para("art-332", numeral(u, "art-332", 6), b("Artículo 52.- Sustitúyase el número 6 del artículo 332"))
    u.set_para("art-332", numeral(u, "art-332", 8), b("Artículo 53.- Sustitúyase el número 8 del artículo 332"))
    i = numeral(u, "art-332", 9)
    u.insert("art-332", i + 1, b("Artículo 54.- Agregase como número 10 en el artículo 332"))
    u.set_para("art-333", numeral(u, "art-333", 3), b("Artículo 55.- Sustitúyase el número 3 del artículo 333"))
    (fase,) = b("Artículo 56.- Agregase en el párrafo primero del número 4 del artículo 333, artículo 354 párrafo segundo y "
                "artículo 359 párrafo primero")
    # inserted after the word "alegatos", which ends its sentence: the new sentence follows the full stop (decisions)
    for k, para in (("art-333", numeral(u, "art-333", 4)), ("art-354", 1), ("art-359", 0)):
        u.sub(k, "alegatos.", "alegatos. " + fase, para=para)
    i = numeral(u, "art-333", 4)
    u.set_para("art-333", i + 1, b("Artículo 57.- Sustitúyase el párrafo segundo del número 4 del artículo 333"))
    e.check("Artículo 58.- Elimínese el párrafo tercero del número 4 del artículo 333.")
    ps = u.paras("art-333")
    del ps[i + 2]
    u.put("art-333", ps)
    u.set_para("art-334", numeral(u, "art-334", 3), b("Artículo 59.- Sustitúyase el número 3 del artículo 334"))
    e.check("Artículo 60.- Eliminase el número 5 del artículo 334.")
    ps = u.paras("art-334")
    del ps[numeral(u, "art-334", 5)]
    u.put("art-334", ps)
    whole(u, 340, b("Artículo 61.- Sustitúyase el artículo 340 por el siguiente texto:"))
    (p,) = e.inline("Artículo 62.- Agregase como párrafo quinto del artículo 351, el siguiente texto:")
    if not u.paras("art-351")[4].startswith("La o el demandado al contestar"):
        raise SystemExit("art. 351: fifth paragraph not where expected")
    u.insert("art-351", 4, [p])
    (p,) = b("Artículo 63.- Agregase en el artículo 360, el siguiente texto:")
    ps = u.paras("art-360")
    if len(ps) != 1:
        raise SystemExit("art. 360: expected one paragraph")
    u.put("art-360", [ps[0] + " " + p])
    whole(u, 363, b("Artículo 64.- Sustitúyase el artículo 363 por el siguiente texto:"))
    u.insert("art-400", 1, b("Artículo 65.- Agregase a continuación del primer párrafo del artículo 400"))
    e.check('Artículo 66.- Sustitúyase en el artículo 403 el epígrafe: "Posturas iguales" por la frase:',
            '"Posturas que se conceptúen iguales"')
    u.sub("art-403", "Posturas iguales", "Posturas que se conceptúen iguales", para=0)


def cc_92_15_in_21(u: Units) -> None:
    """Corte Constitucional, sentencia 92-15-IN/21 (Edición Constitucional 137, 23-II-2021): the last inciso of art. 324
    is unconstitutional and the article 'dirá' with a new last inciso."""
    e = Ed(EC137_2021)
    e.check("2. Declarar la inconstitucionalidad del inciso final del artículo 324 del Código Orgánico General de "
            "Procesos, publicado en el Registro Oficial Suplemento No. 506 del 22 de mayo de 2015, y disponer que el "
            "texto del artículo 324 del Código Orgánico General de Procesos dirá:")
    i = e.index("La o el juzgador calificará la demanda y dispondrá que se rinda la caución en el término de veinticinco "
                "días, en caso de no hacerlo los efectos del acto impugnado no se suspenderán",
                after="2. Declarar la inconstitucionalidad del inciso final del artículo 324")
    u.set_para("art-324", u.count("art-324") - 1, [e.paras[i]])


def transformacion_digital_2023(u: Units) -> None:
    """Ley Orgánica para la Transformación Digital y Audiovisual, Tercer Suplemento 245, 7-II-2023, Título VII
    (arts. 70-82); in force on publication (its Disposición final)."""
    e = Ed(S3_245_2023)
    top = "TÍTULO VII REFORMAS AL CÓDIGO ORGÁNICO GENERAL DE PROCESOS"
    stop = r"^(Artículo \d+\.- |TÍTULO VIII)"

    def b(anchor: str) -> list[str]:
        return e.block(anchor, stop, after=top)

    whole(u, 4, b("Artículo 70.- Refórmese el artículo 4 con la siguiente redacción:"))
    i2, i4 = b("Artículo 71.- Refórmense los incisos segundo y cuarto del artículo 25")
    if u.count("art-025") < 4:
        raise SystemExit("art. 25: fewer than four incisos")
    u.set_para("art-025", 1, [i2])
    u.set_para("art-025", 3, [i4])
    whole(u, 53, b("Artículo 72.- Sustitúyase el artículo 53 por el siguiente:"))
    blk = b("Artículo 73.- Agréguese continuación del artículo 55, el siguiente artículo:")
    blk[0] = re.sub(r"^Artículo 55\.1- ", "Artículo 55.1.- ", blk[0])
    u.set_unit(art_key(55, 1), blk, label="Art. 55.1")
    whole(u, 55, b("Artículo 74.- Sustitúyase el artículo 55 por el siguiente:"))
    whole(u, 115, b("Artículo 75.- Refórmese el artículo 115 con el siguiente texto:"))
    whole(u, 193, b("Artículo 76.- Sustitúyase el artículo 193 por el siguiente:"))
    whole(u, 194, b("Artículo 77.- Sustitúyase el artículo 194 por el siguiente:"))
    whole(u, 196, b("Artículo 78.- Sustitúyase el artículo 196 por el siguiente:"))
    whole(u, 347, b("Artículo 79.- Reemplácese el contenido del artículo 347 por el siguiente:"))
    (p,) = b("Artículo 80.- Reemplácese el numeral 10 del artículo 363 por el siguiente:")
    u.set_para("art-363", numeral(u, "art-363", 10), [p])
    (p,) = b("Artículo 81.- Agréguese a continuación del numeral 7 del artículo 373 el siguiente numeral:")
    u.insert("art-373", numeral(u, "art-373", 7) + 1, [p])
    whole(u, 405, b("Artículo 82.- Reemplácese el texto del artículo 405 por el siguiente:"))


def integridad_2025(u: Units) -> None:
    """Ley Orgánica de Integridad Pública, Tercer Suplemento 68, 26-VI-2025, Disposición reformatoria sexta; in force
    on publication."""
    e = Ed(S3_68_2025)
    top = "Sexta.- En el Código Orgánico General de Procesos -COGEP-, efectúese las siguientes reformas:"
    stop = r"^(\d\. (?:En |Sustit|Agr|Elim)|Séptima\.-)"
    e.check('1. En el tercer inciso del numeral 2 del artículo 96, sustitúyase la frase "el plusvalor" por "la plusvalía".')
    u.sub("art-096", "el plusvalor", "la plusvalía")
    (p,) = e.block("2. Sustitúyase el inciso sexto del artículo 146, por el siguiente:", stop, after=top)
    u.set_para("art-146", 5, [p])
    blk = e.inline("3. Sustitúyase el literal e) del numeral 4 del artículo 326, e inclúyase el literal f), conforme lo "
                   "siguiente:", after=top)
    i = u.find("art-326", "e) ")
    u.set_para("art-326", i, blk)
    e.check('4. Sustitúyase en el artículo 327 la frase "pago por consignación" por la frase "pago por consignación y la '
            'prevista en el literal e) del numeral 4 del artículo 326 de este Código".')
    u.sub("art-327", "pago por consignación", "pago por consignación y la prevista en el literal e) del numeral 4 del "
          "artículo 326 de este Código")
    (p,) = e.block("5. En el artículo 332 sustitúyase el numeral 9 por el siguiente:", stop, after=top)
    u.set_para("art-332", numeral(u, "art-332", 9), [p])


IMAGE_ONLY = ("NOT APPLIED here: the Registro Oficial edition that publishes it is page images without a text layer, "
              "and this repository does not OCR. Its wording is missing: the files named in this commit keep the "
              "earlier text and any article it adds is absent (provisions named from the Lexis index of 7-II-2023).")
IMAGE_RULING = ("NOT APPLIED here: the ruling sets a conditioned reading of the provisions named in this commit, and the "
                "Lexis consolidation of 7-II-2023 shows words it added to arts. 23 and 25. Its Edición Constitucional "
                "is page images without a text layer, and this repository does not OCR, so those words are missing and "
                "the files keep the earlier text.")
PARTLY = ("{} here: an earlier ruling or act this record could not apply (image-only edition) had already changed {}, "
          "so this act's partial amendment of it is not applied either; the file keeps the earlier text, which is not "
          "the law from this date.")

LAWS = {
    "cogep-2015": dict(label="Código Orgánico General de Procesos", kind="law", published="2015-05-22", url=S506_2015,
                       title="Código Orgánico General de Procesos (COGEP)"),
    "ley-app-2015": dict(label="Ley Orgánica de Incentivos para Asociaciones Público-Privadas (2015)", kind="law",
                         published="2015-12-18", url=S1_652_2015,
                         title="Ley Orgánica de Incentivos para Asociaciones Público-Privadas y la Inversión Extranjera"),
    "coescci-2016": dict(label="Código Orgánico de la Economía Social de los Conocimientos (2016)", kind="law",
                         published="2016-12-09", url=S899_2016,
                         title="Código Orgánico de la Economía Social de los Conocimientos, Creatividad e Innovación"),
    "cc-ec1-2017": dict(label="Corte Constitucional, Edición Constitucional 1 (2017)", kind="court",
                        published="2017-05-31", url=EC1_2017, note=IMAGE_ONLY,
                        title="Corte Constitucional, sentencia publicada en la Edición Constitucional 1, 31-V-2017: "
                              "inconstitucionalidad sustitutiva del art. 137 (Lexis index). NOT APPLIED (image-only edition)"),
    "codigo-organico-administrativo-2017": dict(label="Código Orgánico Administrativo (2017)", kind="law",
                                                published="2017-07-07", url=S2_31_2017,
                                                title="Código Orgánico Administrativo"),
    "cc-ec19-2017": dict(label="Corte Constitucional, Edición Constitucional 19 (2017)", kind="court",
                         published="2017-11-14", url=EC19_2017, note=IMAGE_RULING,
                         title="Corte Constitucional, sentencia 006-17-SCN-CC (Edición Constitucional 19, 14-XI-2017): "
                               "interpretación condicionada de los arts. 23, 25, 27 y 28 (Lexis index)"),
    "ley-fomento-productivo-2018": dict(label="Ley Orgánica para el Fomento Productivo (2018)", kind="law",
                                        published="2018-08-21", url=S309_2018,
                                        title="Ley Orgánica para el Fomento Productivo, Atracción de Inversiones, "
                                              "Generación de Empleo, y Estabilidad y Equilibrio Fiscal"),
    "ley-reformatoria-cogep-2019": dict(label="Ley Orgánica Reformatoria del COGEP (2019)", kind="law",
                                        published="2019-06-26", url=S517_2019, enacted="2019-06-20",
                                        title="Ley Orgánica Reformatoria del Código Orgánico General de Procesos"),
    "ley-reformatoria-cofj-2020": dict(label="Ley Orgánica Reformatoria del Código Orgánico de la Función Judicial (2020)",
                                       kind="law", published="2020-12-08", url=S345_2020, note=IMAGE_ONLY,
                                       title="Ley Orgánica Reformatoria del Código Orgánico de la Función Judicial "
                                             "(Suplemento 345, 8-XII-2020), Disposición reformatoria quinta: arts. 53, "
                                             "55 and a new art. 53.1. NOT APPLIED (image-only edition)"),
    "cc-92-15-in-21": dict(label="Sentencia 92-15-IN/21", kind="court", published="2021-02-23", url=EC137_2021,
                           enacted="2021-01-13",
                           title="Corte Constitucional, sentencia 92-15-IN/21 (Edición Constitucional 137, 23-II-2021): "
                                 "inconstitucionalidad del inciso final del art. 324"),
    "cc-19-20-cn-21": dict(label="Sentencia 19-20-CN/21", kind="court", published="2021-04-09", url=EC156_2021,
                           enacted="2021-02-24",
                           note="Changes no words: the Corte Constitucional answered a consulta on art. 22 numeral 8 "
                                "and set the reading under which it is compatible with the Constitution.",
                           title="Corte Constitucional, sentencia 19-20-CN/21 (Edición Constitucional 156, 9-IV-2021): "
                                 "constitucionalidad condicionada del art. 22 numeral 8"),
    "ley-extincion-dominio-2021": dict(label="Ley Orgánica de Extinción de Dominio", kind="law", published="2021-05-14",
                                       url=S5_452_2021, note=IMAGE_ONLY,
                                       title="Ley Orgánica de Extinción de Dominio"),
    "ley-desarrollo-economico-2021": dict(label="Ley Orgánica para el Desarrollo Económico y Sostenibilidad Fiscal (2021)",
                                          kind="law", published="2021-11-29", url=S3_587_2021, note=IMAGE_ONLY,
                                          title="Ley Orgánica para el Desarrollo Económico y Sostenibilidad Fiscal tras "
                                                "la Pandemia COVID-19 (Tercer Suplemento 587, 29-XI-2021), arts. "
                                                "106-109: arts. 10, 76, 317, 324. NOT APPLIED (image-only edition)"),
    "cc-36-16-in-22": dict(label="Sentencia 36-16-IN/22", kind="court", published="2022-07-15", url=EC53_2022,
                           enacted="2022-06-08",
                           note="Changes no words: the ruling declares unconstitutional art. 27 as first published "
                                "(2015), for the cases in which that wording still applies; the article had been "
                                "replaced in 2019.",
                           title="Corte Constitucional, sentencia 36-16-IN y acumulados/22 (Edición Constitucional 53, "
                                 "15-VII-2022): inconstitucionalidad del art. 27 en su texto de 2015"),
    "ley-transformacion-digital-2023": dict(label="Ley Orgánica para la Transformación Digital y Audiovisual (2023)",
                                            kind="law", published="2023-02-07", url=S3_245_2023,
                                            title="Ley Orgánica para la Transformación Digital y Audiovisual"),
    "ley-integridad-2025": dict(label="Ley Orgánica de Integridad Pública (2025)", kind="law", published="2025-06-26",
                                url=S3_68_2025, title="Ley Orgánica de Integridad Pública"),
    "cc-52-25-in-25": dict(label="Sentencia 52-25-IN/25", kind="court", published="2025-10-03", url=EC96_2025,
                           restores="ley-integridad-2025",
                           title="Corte Constitucional, sentencia 52-25-IN/25 y acumulados (Edición Constitucional 96, "
                                 "3-X-2025): inconstitucionalidad por la forma de la Ley Orgánica de Integridad Pública"),
}

FIRST_DAY = "2016-05-22"  # Disposición final segunda: in force twelve months after publication (decisions)

# (law, in-force day, edit or list of provisions credited without a change of words, same_day)
STEPS = [
    ("ley-app-2015", FIRST_DAY, ley_app_2015, True),
    ("coescci-2016", "2016-12-09", coescci_2016, False),
    ("cc-ec1-2017", "2017-05-31", ["art-137"], False),
    ("cc-ec19-2017", "2017-11-14", ["art-023", "art-025", "art-027", "art-028"], False),
    ("codigo-organico-administrativo-2017", "2018-07-07", coa_2017, False),
    ("ley-fomento-productivo-2018", "2018-08-21", fomento_productivo_2018, False),
    ("ley-reformatoria-cogep-2019", "2019-06-26", reformatoria_2019, False),
    ("ley-reformatoria-cofj-2020", "2020-12-08", ["art-053", "art-055"], False),
    ("cc-92-15-in-21", "2021-02-23", cc_92_15_in_21, False),
    ("cc-19-20-cn-21", "2021-04-09", ["art-022"], False),
    ("ley-extincion-dominio-2021", "2021-05-14", ["art-001", "art-036"], False),
    ("ley-desarrollo-economico-2021", "2021-11-29", ["art-010", "art-076", "art-317", "art-324"], False),
    ("cc-36-16-in-22", "2022-07-15", ["art-027"], False),
    ("ley-transformacion-digital-2023", "2023-02-07", transformacion_digital_2023, False),
    ("ley-integridad-2025", "2025-06-26", integridad_2025, False),
    ("cc-52-25-in-25", "2025-10-03", "restore:ley-integridad-2025", False),
]

# provisions an image-only act amended and no applied act has replaced whole since (the COIP part's STALE rule): a
# later partial amendment of one of them is not applied, so no version grafts new words onto wording that was not law
STALE_BY = {"cc-ec1-2017": ["art-137"], "cc-ec19-2017": ["art-023", "art-025", "art-027", "art-028"],
"ley-reformatoria-cofj-2020": ["art-053", "art-055"],
            "ley-extincion-dominio-2021": ["art-001", "art-036"],
            "ley-desarrollo-economico-2021": ["art-010", "art-076", "art-317", "art-324"]}

DECISIONS = [
    "COGEP: the first version is the Code as enacted (Registro Oficial Suplemento 506, 22-V-2015), dated 22-V-2016: its Disposición final segunda puts it in force twelve months after publication, except the provisions reforming the Código Orgánico de la Función Judicial, the Ley Notarial and the Ley de Arbitraje y Mediación and those on abandono, copias certificadas, registro de contratos de inquilinato and citación (in force on publication) and those on remate (in force after 180 days). The history keeps one date for the whole Code, the general in-force day; the earlier days of those provisions are not separate versions.",
    "COGEP: units are art-NNN for each article (articles added later keep their place: art-014-1 for art. 14 A, art-055-1 for art. 55.1, art-068-1 for art. 68.1, art-133-1 for the article innumerado after art. 133, art-370-1 for art. 370 A); disp-general-NN, disp-transitoria-NN, disp-reformatoria-NN (the Code's own reforms of other laws, kept as printed), disp-derogatoria-NN, disp-final-NN; 'titulos' holds the Libro, Título, Capítulo and Sección headings in order. The Asamblea's oficio, certification, exposición de motivos and considerandos are not units.",
    "COGEP: literals the text layer sets in one paragraph ('a) ...; b) ...') are split one per line, in the base and in the amending acts' text alike; nothing else is reworded. Where an amending act gives a whole article as 'Art. 19.-', 'Artículo. 256.-' or 'Artículo.- 249.', or without its number (arts. 4, 53, 55 and 115 in 2023), the Code's own form 'Artículo 19.-' is written in front of the act's words.",
    "COGEP: amending acts and rulings were found from the 'Nota:' lines of a Lexis consolidation of the COGEP last amended 7-II-2023 (LegalCloud download, codes/index_docx.py; reading only), and for 2023-2026 by searching the text layer of every law on the Asamblea Nacional's 'leyes aprobadas' list (97 laws, codes/screen.py -> codes/screen_cogep.json): only the Ley Orgánica de Integridad Pública (2025) amends the Code there. Newer consolidations found in the archives (Función Judicial copy captured 29-IV-2026, gob.ec 2022, PGE, CES, Planificación) stop at 29-XI-2021 or earlier.",
    "COGEP: the editorial notes that only point to regulations (RO 539 of 2015 on abandono, Suplemento 584 of 2015 on remates, RO 636 of 2015 on citación abroad, Suplemento 104 of 2017 on apelación) change no words and are not versions. Generic clauses 'en todas las disposiciones legales ... sustitúyase' (Código de la Economía Social de los Conocimientos, Disposición reformatoria décimo tercera) are not applied to the Code's text.",
    "COGEP: the Ley de Incentivos para Asociaciones Público-Privadas (Primer Suplemento 652, 18-XII-2015) repealed a sentence and the last inciso of art. 329 before the Code took effect; its version shares the Code's first day (22-V-2016) and follows the as-enacted version.",
    "COGEP: the Código Orgánico Administrativo (Segundo Suplemento 31, 7-VII-2017) reforms the Code in force twelve months after publication (its Disposición final): from 7-VII-2018.",
    "COGEP: the Ley de Fomento Productivo (Primer Suplemento 309, 21-VIII-2018), Disposición derogatoria segunda, eliminates 'las palabras \"laudo arbitral\"' in arts. 102 to 106: the three occurrences of those words are removed as printed (a comma before them stays, as in 'la sentencia, o acta de mediación'); the plural 'laudos arbitrales' is a different form and is kept (Lexis removes it too). It also 'deja sin efecto' the Disposición derogatoria décima tercera, which is removed.",
    "COGEP: the Ley Orgánica Reformatoria del COGEP (Primer Suplemento 517, 26-VI-2019, in force on publication) is applied from its text layer, read with the same overlap filter as the Código de Comercio (codes/strict.py), because the edition prints stray fragments over its columns. Its art. 17 says 'número 2' of art. 122 but gives numeral 7, the only numeral on testimonial declarations: numeral 7 is replaced. Its art. 21 (art. 148, 'o única en los procedimientos de una sola audiencia' after 'preliminar') is not applied: the wording its art. 20 gave art. 148 already reads 'preliminar o única en los procesos de una sola audiencia'. Its art. 3 inserts a phrase ending in a comma before an existing comma: one comma is kept. Its art. 10 quotes the old phrase of art. 55 with its full stop and the new one without: the full stop stays. Its art. 56 inserts a sentence 'luego de la palabra \"alegatos\"', which ends its sentence: the new sentence follows the full stop. Its art. 63 adds a sentence to the one-paragraph art. 360: it is set at the end of that paragraph.",
    "COGEP: NOT APPLIED, image-only gazette editions (no text layer; no OCR by the user's decision), each with a version that changes no words: the Corte Constitucional ruling in Edición Constitucional 1 (31-V-2017; art. 137, 'inconstitucionalidad sustitutiva', per the Lexis index; art. 137 was replaced whole in 2019, so it is current again from 26-VI-2019); the Ley Orgánica Reformatoria del Código Orgánico de la Función Judicial (Suplemento 345, 8-XII-2020; arts. 53 and 55 replaced and art. 53.1 added: 53 and 55 are current again from 7-II-2023, art. 53.1 is missing from 8-XII-2020 on); the Ley Orgánica de Extinción de Dominio (Quinto Suplemento 452, 14-V-2021; arts. 1 and 36); the Ley Orgánica para el Desarrollo Económico y Sostenibilidad Fiscal (Tercer Suplemento 587, 29-XI-2021; arts. 10 (numeral 11 and last inciso), 76 (last inciso), 317 and 324 (last inciso)). Arts. 1, 10, 36, 76, 317 and 324 are therefore not the law in force after those dates.",
    "COGEP: NOT APPLIED, image-only ruling: sentencia 006-17-SCN-CC (Edición Constitucional 19, 14-XI-2017; 47 of 48 pages are images) sets a conditioned reading of arts. 23, 25, 27 and 28 (Lexis index); the Lexis consolidation shows words it added ('en el término de 2 días' in art. 23, 'en el término de veinticuatro horas' in art. 25). It has a version that changes no words; arts. 27 and 28 were replaced whole in 2019 and are current again from 26-VI-2019, arts. 23 and 25 are not the law in force after 14-XI-2017.",
    "COGEP: rulings that change no words are versions without a change of wording, credited to the provisions concerned: 19-20-CN/21 (Edición Constitucional 156, 9-IV-2021; art. 22 numeral 8) and 36-16-IN/22 (Edición Constitucional 53, 15-VII-2022; art. 27 as published in 2015, already replaced in 2019).",
    "COGEP: sentencia 92-15-IN/21 (Edición Constitucional 137, 23-II-2021) declares the last inciso of art. 324 unconstitutional and states the article's new text; the new last inciso is cut from the ruling and dated by its publication.",
    "COGEP: the Ley Orgánica de Integridad Pública (Tercer Suplemento 68, 26-VI-2025), Disposición reformatoria sexta, is applied on publication (arts. 96, 146, 326, 327, 332). Sentencia 52-25-IN/25 (Edición Constitucional 96, 3-X-2025) declares the whole law unconstitutional por la forma, with retroactive effect only in penal, childhood and human-mobility matters; the COGEP's earlier wording of those five articles is restored on the ruling's publication day.",
    "COGEP, partial amendments of provisions this record could not keep current (the COIP part's rule): once an image-only act has amended a provision, a later partial amendment of it is not applied; whole substitutions are applied and make it current again. Not applied on this ground: incisos 2 and 4 of art. 25 (Ley Orgánica para la Transformación Digital y Audiovisual, 7-II-2023), credited to art. 25 with a note.",
    "COGEP, other literal readings: the Reformatoria of 2019, art. 32, inserts 'la audiencia única' after 'se realiza en' in art. 234 numeral 1; it is applied as printed ('se realiza en la audiencia única audiencia preliminar o de juicio'), with no comma added (Lexis adds one). Where an act counts 'párrafos' of an article with numerals, the numerals belong to the inciso that introduces them (art. 56, third inciso).",
    "COGEP: the version in force on 7-II-2023 was compared, for reading only, with the Lexis consolidation of that date (codes/reconcile_cogep.py -> codes/reconcile_cogep.json): 358 articles agree after normalising spacing, quotes and the article heading. The others are (a) acts and rulings not applied here (arts. 1, 10, 23, 25, 36, 53.1, 76, 317, 324); (b) Lexis's editorial forms: epigraphs ending '.-', 'Litis consorcio', '(sic)', 'éste', 'rehusa', 'inventarío', 'regístrales', a comma in art. 234, the epigraphs it keeps where the 2023 act gives an article without one (arts. 4, 53, 115), and its removal of the plural 'laudos arbitrales' (arts. 102-105); (c) the gazette's own wording, kept as printed, e.g. 'de la o de la o del ejecutado' (375), 'Sí el alimentante' (137), '2.-' (247), 'Audiencia:' (28), and punctuation in arts. 30, 39, 79, 106, 143, 326, 392, 406 and 429; (d) headings Lexis prints inside the article text.",
    "COGEP: gaps that could not be closed: 50 of the 97 laws published 2023-2026 on the Asamblea's list are printed only as page images (codes/screen_cogep.json), so whether any of them amends the Code could not be read, and no consolidation newer than 7-II-2023 was found. There is no official consolidated text. For both reasons this part stays on the preview branch.",
]

AI_USE = [
    "COGEP: no generative model wrote legal text. The amendment map in codes/cogep.py (which provision each act changes, and the anchor phrases before its new text in the act's PDF) was written by an AI agent (Claude) from reading the act; the words are cut from the gazette PDFs' text layers. No OCR was used.",
]


def restore(before: dict, law: str) -> dict:
    return {k: copy.deepcopy(v) for k, v in before.items()}


def replay(first: dict) -> list[dict]:
    out = []
    units = first
    stale: set[str] = set()
    snaps: dict[str, tuple[dict, list[str]]] = {}
    for law, day, edit, same in STEPS:
        url = LAWS[law]["url"]
        v: dict = {"from": day, "source_url": url, "sha256": sha_of(url)}
        if same:
            v["same_day"] = True
        if isinstance(edit, list):
            for k in edit:
                if k not in units:
                    raise SystemExit(f"{law}: no unit {k}")
            v.update(changes={}, credits={k: [law] for k in sorted(edit, key=order)})
            out.append(v)
            stale |= set(STALE_BY.get(law, []))
            continue
        if isinstance(edit, str) and edit.startswith("restore:"):
            before, keys = snaps[edit.split(":", 1)[1]]
            new = dict(units)
            for k in keys:
                if k in before:
                    new[k] = copy.deepcopy(before[k])
                else:
                    new.pop(k, None)
        else:
            u = Units(units)
            _WHOLE.clear()
            edit(u)
            new = dict(sorted(u.u.items(), key=lambda kv: order(kv[0])))
        changed = sorted((k for k in set(units) | set(new) if units.get(k) != new.get(k)), key=order)
        if not changed:
            raise SystemExit(f"{law}: no change")
        skipped = [k for k in changed if k in stale and k in new and k in units and k not in _WHOLE]
        for k in skipped:
            new[k] = units[k]
        changed = [k for k in changed if k not in skipped]
        stale -= set(changed)
        snaps[law] = ({k: units.get(k) for k in changed if k in units}, changed)
        v.update(changes={k: new.get(k) for k in changed},
                 credits={k: [law] for k in sorted(set(changed) | set(skipped), key=order)})
        if skipped:
            names = ", ".join(units[k]["label"] for k in skipped)
            v["note"] = PARTLY.format("Partly NOT APPLIED" if changed else "NOT APPLIED", names)
        out.append(v)
        units = new
    return out


def build_act() -> dict:
    units = base_units()
    first = {"from": FIRST_DAY, "source_url": S506_2015, "sha256": sha_of(S506_2015), "units": units, "credits": {}}
    return {"slug": "cogep", "short": "COGEP", "title": "Código Orgánico General de Procesos", "url": S506_2015,
            "first_law": "cogep-2015", "earlier_laws": [], "versions": [first] + replay(units)}


def laws() -> dict:
    return {k: {"label": v["label"], "title": v["title"], "kind": v["kind"], "enacted": v.get("enacted"),
                "published": v["published"], "url": v["url"], "temporary_until": None,
                "restores": v.get("restores"), "note": v.get("note")} for k, v in LAWS.items()}


def sources() -> list[dict]:
    return [
        {"name": "Registro Oficial del Ecuador (COGEP and its amending acts and rulings)",
         "url": "https://www.registroficial.gob.ec", "retrieved": RETRIEVED, "requests": 16,
         "licence": "No licence stated on the site; official gazette text.",
         "notes": "One PDF per gazette edition, served by esacc.corteconstitucional.gob.ec, found through the site's month listings (codes/editions.py -> codes/editions.json). Every version's wording is cut from the text layer of the 2015 Code or of the amending act or ruling; the editions without a text layer are listed in decisions and not applied."},
        {"name": "Asamblea Nacional, 'Leyes aprobadas'", "url": "https://www.asambleanacional.gob.ec/es/leyes-aprobadas",
         "retrieved": RETRIEVED, "requests": 0, "licence": "No licence stated; official copies of Registro Oficial editions.",
         "notes": "Index of laws 2023-2026 (the COIP part's cache); their PDFs' text layers were searched for the Code (codes/screen.py, codes/screen_cogep.json). Reading only."},
        {"name": "Lexis consolidation of the COGEP, last amended 7-II-2023 (LegalCloud download, legalcloud.ec)",
         "url": "https://legalcloud.ec/download/codigo-organico-general-de-procesos-cogep/", "retrieved": RETRIEVED,
         "requests": 2, "licence": "Lexis / LegalCloud copyright; read only (its 'Nota:' lines), nothing copied.",
         "notes": "Index of amending acts and rulings 2015-2023 (codes/index_docx.py)."},
        {"name": "Internet Archive (Wayback Machine) CDX index", "url": "https://web.archive.org/", "retrieved": RETRIEVED,
         "requests": 36, "licence": "Internet Archive terms of use; reading only.",
         "notes": "Searched for newer consolidations on gob.ec hosts (codes/find_consol.py); the newest COGEP copy found (Función Judicial, capture 20260429133519) stops at 29-XI-2021."},
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


if __name__ == "__main__":
    main()
