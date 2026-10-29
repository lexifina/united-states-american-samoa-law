"""The Código Civil's amending acts, replayed in order of entry into force on the 2005 codification.

Every act with a text layer in the Registro Oficial is a function that edits a copy of the previous version's
units. New wording is never typed here as such: whole articles and paragraphs are cut out of the act's own cached
gazette PDF after an anchor (Src.quoted / Src.inline), and every short phrase an act inserts or deletes is checked to
occur, word for word, in that act's PDF (Src.check). Changed units are credited to the act automatically.

Acts whose gazette edition is page images only (no text layer) are NOT applied: by the user's decision there is no
OCR. They still get a version of their own, with no change of wording, credited to the provisions an editorial index
(Ediciones Legales, gob.ec copy of 2025) names, and a note saying plainly that their change is missing.
"""
from __future__ import annotations

import copy
import hashlib
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import fetch  # noqa: E402
import rotext  # noqa: E402

H = "http://esacc.corteconstitucional.gob.ec/storage/api/v1/10_DWL_FL/"


def ro(uuid_b64: str) -> str:
    return H + uuid_b64


RO79_2005 = ro("eyJjYXJwZXRhIjoicm8iLCJ1dWlkIjoiZDVlMTU4NDEtZDkyZC00NDM4LTlhZTctNzlkYWZlN2NjOWZlLnBkZiJ9")
RO169_2005 = ro("eyJjYXJwZXRhIjoicm8iLCJ1dWlkIjoiZTY2NWRkMzQtNTY5MC00MWQ5LThkMzAtMzAzZmFkNmFiY2IyLnBkZiJ9")
RO274_2006 = ro("eyJjYXJwZXRhIjoicm8iLCJ1dWlkIjoiYzIwZDljNzMtZTFkNy00OTVjLWI1N2YtNzY1YWNlMTU4MDAwLnBkZiJ9")
RO285_2010 = ro("eyJjYXJwZXRhIjoicm8iLCJ1dWlkIjoiYjJhNDAxYmItNDJjMy00MTkyLTliMjEtMTg1Y2RjZTgxMTI0LnBkZiJ9")
S452_2011 = ro("eyJjYXJwZXRhIjoicm8iLCJ1dWlkIjoiZjQ5ZDdkYTItYzQ2OC00NmRjLTkyM2QtM2RhMzE4MDY5MjNmLnBkZiJ9")
S732_2012 = ro("eyJjYXJwZXRhIjoicm8iLCJ1dWlkIjoiZjA4NGQxYWEtNzNlYS00NTQ1LTk0NjMtZjgzYjlkZGQxNjc4LnBkZiJ9")
S796_2012 = ro("eyJjYXJwZXRhIjoicm8iLCJ1dWlkIjoiY2E5NGRlNjEtYmFhNC00ZDc3LWE4MDctODU0OThkYmQ1NTk2LnBkZiJ9")
S797_2012 = ro("eyJjYXJwZXRhIjoicm8iLCJ1dWlkIjoiYTEzMjRiNDYtOTBjNy00NjBlLTg5OTItOTIxMGVmOGI1MzI3LnBkZiJ9")
S843_2012 = ro("eyJjYXJwZXRhIjoicm8iLCJ1dWlkIjoiZWM0MTIyMWUtZDI1OC00NDJiLWJkNzAtNDI5OGM4MDNhMjdiLnBkZiJ9")
S332_2014 = ro("eyJjYXJwZXRhIjoicm8iLCJ1dWlkIjoiNDIwM2NhZGUtMzY2Yy00ZWIzLTgzZmQtZDI5Yzg3NGY3ZjU0LnBkZiJ9")
S506_2015 = ro("eyJjYXJwZXRhIjoicm8iLCJ1dWlkIjoiOGZmZjFhOTEtYWFiYi00YjE0LTllYzEtODkxODAxYjk3MTQ2LnBkZiJ9")
S526_2015 = ro("eyJjYXJwZXRhIjoicm8iLCJ1dWlkIjoiZDE4NTIwNDMtZTg4OS00NmM1LWI3MDUtYmE2ODgzMmNiZDUyLnBkZiJ9")
S983_2017 = ro("eyJjYXJwZXRhIjoicm8iLCJ1dWlkIjoiODk0Yjc3Y2YtZTIyMy00M2IwLTg3ODAtYTAyNWQ2YzM2NDBlLnBkZiJ9")
EC96_2019 = ro("eyJjYXJwZXRhIjoicm8iLCJ1dWlkIjoiNDY3MjQyMzEtN2Y2OC00ODNmLWI1Y2UtMzJjYzQ2MmM5NzMwLnBkZiJ9")
S452_2021 = ro("eyJjYXJwZXRhIjoicm8iLCJ1dWlkIjoiNzE1OWU4NzctZDI2OS00ZDBjLWJlNTctOTk0YzRiNzU0MTAyLnBkZiJ9")
S561_2021 = ro("eyJjYXJwZXRhIjoicm8iLCJ1dWlkIjoiNjVlNzdhNGItMmQ2NS00MWEyLTk5NTgtZmFhNjNmMjU3NzBhLnBkZiJ9")
EC15_2022 = ro("eyJjYXJwZXRhIjoicm8iLCJ1dWlkIjoiZjE3ODBiMDgtNWM1Mi00MGJhLTlhYjgtYzcwNDg1MzY1MjljLnBkZiJ9")
S471_2024 = ro("eyJjYXJwZXRhIjoicm8iLCJ1dWlkIjoiZGU1NjI0MjctNTlhMy00NTNiLWEwMzUtZGNjNjNhYTA0NzU5LnBkZiJ9")
S496_2024 = ro("eyJjYXJwZXRhIjoicm8iLCJ1dWlkIjoiZTU0ZDJlY2MtYzkzNi00NDkxLTk0OTMtM2UzMzA2MTNhZTlhLnBkZiJ9")
S517_2024 = ro("eyJjYXJwZXRhIjoicm8iLCJ1dWlkIjoiN2ZhNDgwZDgtOTU0NS00NzY5LWE1NWMtM2Q3NWMyZmE1ZTQwLnBkZiJ9")
S588_2024 = ro("eyJjYXJwZXRhIjoicm8iLCJ1dWlkIjoiNjk3NGIxZDMtODkzMS00MTU3LThmYmMtOGQ0MGNiNTA0MDcxLnBkZiJ9")


# ---------------------------------------------------------------- sources

# Spaces the text layer puts inside one word (justified typesetting), corrected once (listed in decisions).
LAYER_FIXES = [("se presumir á que", "se presumirá que")]


def fix_layer(p: str) -> str:
    for a, b in LAYER_FIXES:
        p = p.replace(a, b)
    return p


class Src:
    """One cached gazette edition as normalised paragraphs."""
    _cache: dict[str, "Src"] = {}

    def __new__(cls, url: str):
        if url in cls._cache:
            return cls._cache[url]
        self = super().__new__(cls)
        path = fetch.cached(url)
        if path is None:
            raise SystemExit(f"not in cache: {url}")
        self.url = url
        self.paras = [fix_layer(p) for p in rotext.paragraphs(path)]
        self.flat = re.sub(r"\s+", " ", "\n".join(self.paras))
        cls._cache[url] = self
        return self

    def check(self, *phrases: str) -> None:
        for p in phrases:
            if re.sub(r"\s+", " ", p) not in self.flat:
                raise SystemExit(f"phrase not in {self.url[-24:]}: {p!r}")

    def index(self, anchor: str, after: str | None = None) -> int:
        start = 0
        if after is not None:
            start = self.index(after) + 1
        hits = [i for i in range(start, len(self.paras)) if anchor in self.paras[i]]
        if not hits:
            raise SystemExit(f"anchor not found in {self.url[-24:]}: {anchor!r}")
        return hits[0]

    def inline(self, anchor: str, after: str | None = None) -> str:
        """The rest of the paragraph after `anchor`, without its quotation marks."""
        p = self.paras[self.index(anchor, after)]
        rest = p[p.index(anchor) + len(anchor):].strip()
        return unquote([rest])[0]

    def quoted(self, anchor: str, count: int = 1, after: str | None = None) -> list[list[str]]:
        """The `count` quoted blocks that follow the paragraph holding `anchor` (each a list of paragraphs)."""
        i = self.index(anchor, after) + 1
        blocks: list[list[str]] = []
        while len(blocks) < count:
            if not self.paras[i].startswith('"'):
                raise SystemExit(f"no quotation after {anchor!r}: {self.paras[i][:60]!r}")
            block = []
            while True:
                p = self.paras[i]
                block.append(p)
                i += 1
                if re.search(r'"\s*[.,;]?$', p) and (len(block) > 1 or p.count('"') >= 2):
                    break
            blocks.append(unquote(block))
        return blocks


def unquote(block: list[str]) -> list[str]:
    """Strip the act's quotation marks. Spanish sets the full stop after the closing quote: when the quoted text has
    no final stop of its own and the act's stop follows the quote, the stop belongs to the quoted sentence."""
    b = list(block)
    b[0] = b[0][1:] if b[0].startswith('"') else b[0]
    m = re.search(r'"\s*([.,;]?)$', b[-1])
    if m:
        inner = b[-1][:m.start()].rstrip()
        if m.group(1) == "." and not re.search(r"[.:;]$", inner):
            inner += "."
        b[-1] = inner
    b = [x.strip() for x in b]
    for x in b:
        if x.count('"') % 2:
            raise SystemExit(f"unbalanced quote: {x[:80]!r}")
    return b


# ---------------------------------------------------------------- unit edits

def art_key(n: int, extra: str = "") -> str:
    return f"art-{n:04d}" + (f"-{extra}" if extra else "")


class Units:
    def __init__(self, units: dict):
        self.u = copy.deepcopy(units)

    def paras(self, key: str) -> list[str]:
        return self.u[key]["text"].rstrip("\n").split("\n")

    def put(self, key: str, paras: list[str]) -> None:
        self.u[key]["text"] = "".join(p + "\n" for p in paras)

    def find(self, key: str, prefix: str) -> int:
        hits = [i for i, p in enumerate(self.paras(key)) if p.startswith(prefix)]
        if len(hits) != 1:
            raise SystemExit(f"{key}: {len(hits)} paragraphs start with {prefix!r}")
        return hits[0]

    def _one(self, key: str, old: str, para: str | int | None) -> tuple[list[str], int]:
        ps = self.paras(key)
        if para is None:
            idx = list(range(len(ps)))
        elif isinstance(para, int):
            idx = [para]
        else:
            idx = [self.find(key, para)]
        hits = [(i, ps[i].count(old)) for i in idx if old in ps[i]]
        if len(hits) != 1 or hits[0][1] != 1:
            raise SystemExit(f"{key}: phrase {old!r} found {hits}")
        return ps, hits[0][0]

    def sub(self, key: str, old: str, new: str, para: str | int | None = None) -> None:
        """Replace one exact phrase (once) in a unit, or in one paragraph (by prefix or index)."""
        ps, i = self._one(key, old, para)
        ps[i] = ps[i].replace(old, new)
        self.put(key, ps)

    def drop(self, key: str, old: str, para: str | int | None = None) -> None:
        """Delete one exact phrase; the space left before a following space or punctuation mark goes with it."""
        ps, i = self._one(key, old, para)
        left, right = ps[i].split(old)
        if left.endswith(" ") and (right[:1] in (" ", ".", ",", ";", ":") or not right):
            left = left.rstrip(" ")
        ps[i] = left + right
        self.put(key, ps)

    def set_para(self, key: str, index: int, new: list[str], count: int = 1) -> None:
        ps = self.paras(key)
        ps[index:index + count] = new
        self.put(key, ps)

    def insert(self, key: str, index: int, new: list[str]) -> None:
        """Insert paragraphs before position `index` (len = at the end)."""
        ps = self.paras(key)
        ps[index:index] = new
        self.put(key, ps)

    def delete_para(self, key: str, prefix: str) -> None:
        ps = self.paras(key)
        del ps[self.find(key, prefix)]
        self.put(key, ps)

    def set_unit(self, key: str, new: list[str], label: str | None = None) -> None:
        if key not in self.u:
            self.u[key] = {"label": label, "kind": "art", "text": ""}
        self.put(key, new)

    def remove(self, key: str) -> None:
        if key not in self.u:
            raise SystemExit(f"cannot remove {key}: not present")
        del self.u[key]

    def count(self, key: str) -> int:
        return len(self.paras(key))


def whole(u: Units, src: Src, n: int, anchor: str, after: str | None = None) -> None:
    """An act article that substitutes CC art. n entirely with the quoted text after `anchor`."""
    (block,) = src.quoted(anchor, after=after)
    if not re.match(rf"Art\.?\s*{n}\s*\.?\s*-", block[0]):
        raise SystemExit(f"art. {n}: quoted text starts {block[0][:30]!r}")
    u.set_unit(art_key(n), block)


# ---------------------------------------------------------------- the acts (text layer available)

def fe_erratas_2005_08(u: Units) -> None:
    s = Src(RO79_2005)
    s.check('En el artículo 1059, sustitúyase la palabra: "tres", por "cinco".')
    u.sub("art-1059", "notario y tres testigos", "notario y cinco testigos")


def fe_erratas_2005_12(u: Units) -> None:
    s = Src(RO169_2005)
    s.check("En el inciso segundo del artículo 99, sustitúyanse los ordinales: 4° por 3°, 7° y 8° por 6° y 7°")
    u.sub("art-0099", "ordinales 1°, 4°, 7° y 8° del", "ordinales 1°, 3°, 6° y 7° del", para=1)


def cc_0001_11_sin_cc(u: Units) -> None:
    s = Src(S452_2011)
    s.check('Declarar la inconstitucionalidad de la frase "o ha estado" del inciso primero del artículo 23')
    u.drop("art-0023", "o ha estado", para=0)


def ley_creditos_vivienda_2012(u: Units) -> None:
    s = Src(S732_2012)
    u.insert("art-2327", u.count("art-2327"), [s.inline("PRIMERA.- En el artículo 2327 del Código Civil incluir un inciso con el siguiente texto:")])
    tail = s.inline("SEGUNDA.- En el artículo 2367 del Código Civil incluir al final del artículo el siguiente texto:")
    ps = u.paras("art-2367")
    if not ps[-1].endswith("Art. 1634."):
        raise SystemExit("art. 2367 does not end as expected")
    u.set_para("art-2367", len(ps) - 1, [ps[-1][:-1] + " " + tail])


def lod_2012(u: Units) -> None:
    s = Src(S796_2012)
    phrase = "que no pueda darse a entender de manera verbal, por escrito o por lengua de señas"
    s.check(phrase)
    i = u.find("art-0103", "2o.-")
    u.set_para("art-0103", i, [s.inline("2. Reemplácese el numeral 2 del artículo 103 del Código Civil, por el siguiente")])
    u.set_unit("art-0126", [s.inline("3. Sustitúyase el Artículo 126 del Código Civil por el siguiente texto:")])
    old = "y si éste fuere demente o sordomudo, no será necesario su consentimiento."
    s.check(f'"{old}"')
    new = s.inline('fuere demente o sordomudo, no será necesario su consentimiento." por el siguiente:')
    u.sub("art-0256", old, new)
    s.check('la palabra "sordomudo" por "persona sorda"')
    u.sub("art-0490", "del sordomudo", "del persona sorda " + phrase + ",")
    u.sub("art-0491", "al sordomudo.", "al persona sorda " + phrase + ".")
    u.sub("art-0492", "del sordomudo,", "del persona sorda " + phrase + ",")
    s.check('sustitúyase el texto "y de ser entendido por escrito" por el siguiente "y de darse a entender de manera verbal, por escrito o por lengua de señas"')
    u.sub("art-0493", "el sordomudo se haya", "el persona sorda se haya")
    u.sub("art-0493", "y de ser entendido por escrito", "y de darse a entender de manera verbal, por escrito o por lengua de señas")
    u.sub("art-1012", "demente o sordomudo, el ascendiente", "demente o persona sorda " + phrase + ", el ascendiente", para=0)
    i = u.find("art-1050", "5o.-")
    if not u.paras("art-1050")[i + 1].startswith("6o.-"):
        raise SystemExit("art. 1050: numeral 6o does not follow 5o")
    u.set_para("art-1050", i, [s.inline("10. Sustitúyanse, en el Artículo 1050 del Código Civil, los numerales 5o y 6o por el siguiente:")], count=2)
    s.check('la frase "sordomudos que no puedan darse a entender por escrito.", por la siguiente: "persona sorda que no pueda darse a entender de manera verbal, por escrito o por lengua de señas.".')
    # the act quotes "puedan"; the codified text reads "pueden" (decisions)
    u.sub("art-1463", "sordomudos que no pueden darse a entender por escrito.",
          "persona sorda " + phrase + ".", para=0)
    s.check('la palabra "sordomudos", por la siguiente frase: "persona sorda que no puedan darse a entender de manera verbal, por escrito o por lengua de señas,".')
    u.sub("art-2409", "dementes, sordomudos y de cuantos",
          "dementes, persona sorda que no puedan darse a entender de manera verbal, por escrito o por lengua de señas, y de cuantos")


def loddl_2012(u: Units) -> None:
    s = Src(S797_2012)
    (b,) = s.quoted("Artículo 7.- Añádase un Artículo innumerado a continuación del Artículo 36 del Código Civil")
    u.set_unit("art-0036-1", b, label="Art. innumerado (tras el art. 36)")


def ley_buros_2012(u: Units) -> None:
    s = Src(S843_2012)
    (b,) = s.quoted("NOVENA: Agregar el siguiente inciso a continuación del primer inciso del artículo 1611 del Código Civil:")
    u.insert("art-1611", 1, b)


def comf_2014(u: Units) -> None:
    s = Src(S332_2014)
    s.check('En el Código Civil, sustitúyase en el artículo 1611 el texto: "El Directorio del Banco Central del Ecuador" '
            'por "El organismo regulador de los sistemas monetario y financiero".')
    u.sub("art-1611", "El Directorio del Banco Central del Ecuador", "El organismo regulador de los sistemas monetario y financiero")


def reformatoria_cc_2015(u: Units) -> None:
    s = Src(S526_2015)
    top = "LEY REFORMATORIA AL CÓDIGO CIVIL"
    s.check("Art. 1.-Elimínese el numeral 4 del artículo 67.")
    u.delete_para("art-0067", "4a.-")
    for n, a in [(74, "Art. 2.- Sustitúyase el artículo 74"), (83, "Art. 3.-Sustitúyase el artículo 83"),
                 (95, "Art. 4.-Sustitúyase el artículo 95"), (96, "Art. 5.-Sustitúyase el artículo 96"),
                 (98, "Art. 6.-Sustitúyase el artículo 98"), (99, "Art. 7.-Sustitúyase el artículo 99")]:
        whole(u, s, n, a, after=top)
    (b,) = s.quoted("Art. 8.-Sustitúyase el numeral 3 del artículo 102", after=top)
    u.set_para("art-0102", u.find("art-0102", "3a.-"), b)
    whole(u, s, 103, "Art. 9.-Sustitúyase el artículo 103", after=top)
    s.check('Art. 10.-En el numeral 6 del artículo 108 elimínese la frase "del ministerio público o".')
    u.drop("art-0108", "del ministerio público o", para="6a.-")
    whole(u, s, 110, "Art. 11.-Sustitúyase el artículo 110", after=top)
    whole(u, s, 112, "Art. 12.-Sustitúyase el artículo 112", after=top)
    whole(u, s, 114, "Art. 13.-Sustitúyase el artículo 114", after=top)
    whole(u, s, 116, "Art. 14.-Sustitúyase el artículo 116", after=top)
    s.check('Art. 15.- En el primer párrafo del artículo 122 elimínese la frase "e intervendrá en ellas, como parte, el ministerio público".')
    u.drop("art-0122", "e intervendrá en ellas, como parte, el ministerio público", para=0)
    whole(u, s, 124, "Art. 16.-Sustitúyase el artículo 124", after=top)
    whole(u, s, 128, "Art. 17.-Sustitúyase el artículo 128", after=top)
    whole(u, s, 129, "Art. 18.-Sustitúyase el artículo 129", after=top)
    (b,) = s.quoted("Art. 19.-En el artículo 139, después del primer inciso agréguese como segundo inciso", after=top)
    u.insert("art-0139", 1, b)
    s.check('Art. 20.- Elimínese del artículo 146 la frase ", oído el ministerio público,".')
    u.drop("art-0146", ", oído el ministerio público,")
    for n, k in [(180, 21), (190, 22), (222, 23), (223, 24), (230, 25), (233, 26)]:
        whole(u, s, n, f"Art. {k}.-Sustitúyase el artículo {n}", after=top)
    (b,) = s.quoted("Art. 27.-Agréguese después del artículo 233 el siguiente artículo innumerado:", after=top)
    u.set_unit("art-0233-a", b, label="Art. 233 A")
    ba, bb = s.quoted("Art. 28.- Agréguese después del artículo 242 los siguientes artículos innumerados:", count=2, after=top)
    u.set_unit("art-0242-a", ba, label="Art. 242 A")
    u.set_unit("art-0242-b", bb, label="Art. 242 B")
    for n, a in [(245, "Art. 29.-"), (246, "Art. 30.-"), (248, "Art. 31.-"), (249, "Art. 32.-"), (250, "Art. 33.- "),
                 (255, "Art. 34.-"), (258, "Art. 35.-"), (269, "Art. 36.- "), (304, "Art. 37.-"), (332, "Art. 38.-")]:
        whole(u, s, n, f"{a}Sustitúyase el artículo {n}", after=top)
    for n, law_phrase, para in [
            (379, 'Art. 39.-Elimínese en el primer párrafo del artículo 379 la frase "y al ministerio público".', 0),
            (380, 'Art. 40.-Suprímase en el primer inciso del Artículo 380 la frase "y el ministerio público".', 0),
            (405, 'Art. 41.- Elimínese del artículo 405 la frase "y el ministerio público".', None),
            (424, 'Art. 42.- Elimínese del artículo 424 la frase "con audiencia del ministerio público,".', None),
            (441, 'Art. 43.- Elimínese del segundo párrafo del artículo 441 la frase ", o el ministerio público".', 1),
            (447, 'Art. 44.-Elimínese del segundo párrafo del artículo 447 la frase ", oído el ministerio público".', 1),
            (459, 'Art. 45.-Elimínese del tercer párrafo del artículo 459 la frase ", oyendo al ministerio público".', 2)]:
        s.check(law_phrase)
        u.drop(art_key(n), re.search(r'la frase "(.*)"\.$', law_phrase).group(1), para=para)
    whole(u, s, 464, "Art. 46.-Sustitúyase el artículo 464", after=top)
    s.check('Art. 47.-Elimínese del numeral 1 del artículo 533 la frase "y demás personas que ejercen el ministerio público".')
    u.drop("art-0533", "y demás personas que ejercen el ministerio público", para="1o.-")
    # the act quotes "o que contraviene la disposición del Art. 90"; the codified text reads "contraviene a la" (decisions)
    s.check('Art. 48.-Elimínese del artículo 552 la frase "o que contraviene la disposición del Art. 90".')
    u.drop("art-0552", ", o que contraviene a la disposición del Art. 90", para=0)
    whole(u, s, 560, "Art. 49.-Sustitúyase el artículo 560", after=top)
    whole(u, s, 561, "Art. 50.Sustitúyase el artículo 561", after=top)
    whole(u, s, 839, "Art. 51.-Sustitúyase el artículo 839", after=top)
    whole(u, s, 841, "Art. 52.-Sustitúyase el artículo 841", after=top)
    s.check('Art. 53.- Elimínese en el párrafo cuarto del artículo 842 la frase ", con conocimiento de causa y audiencia del ministerio público".')
    u.drop("art-0842", ", con conocimiento de causa y audiencia del ministerio público", para=3)
    whole(u, s, 853, "Art. 54.- Sustitúyase el artículo 853", after=top)
    s.check('Art. 55.- Elimínese del tercer párrafo del artículo 1094 la frase "al ministerio público y".')
    u.drop("art-1094", "al ministerio público y", para=2)
    whole(u, s, 1312, "Art. 56.- Sustitúyase el artículo 1312", after=top)
    b1619, b1699 = s.quoted("Artículo 57.- Sustitúyanse los artículos 1619 y 1699, por los siguientes:", count=2, after=top)
    u.set_unit("art-1619", b1619)
    u.set_unit("art-1699", b1699)
    whole(u, s, 1700, "Art. 58.- Sustitúyase el artículo 1700", after=top)
    s.check("Deróguense los artículos 82, 84, 85, 86, 87, 88, 89, 90,109, 111, 125, 135, 149, 154, 234, 235, 236, 237, "
            "238, 239, 240, 241, 251, 253, 254, 256, 257, 260, 261, 262, 263, 264, el numeral 2 del Art. 310, 462, 473, "
            "497 y 543 del Código Civil.")
    for n in [82, 84, 85, 86, 87, 88, 89, 90, 109, 111, 125, 135, 149, 154, 234, 235, 236, 237, 238, 239, 240, 241,
              251, 253, 254, 256, 257, 260, 261, 262, 263, 264, 462, 473, 497, 543]:
        u.remove(art_key(n))
    u.delete_para("art-0310", "2o.-")


def cogep_2015(u: Units) -> None:
    s = Src(S506_2015)
    top = "QUINTA.- Refórmense en el Código Civil, las siguientes disposiciones:"
    (b,) = s.quoted("1. Sustitúyase el numeral 2 del artículo 67 por el siguiente:", after=top)
    u.set_para("art-0067", u.find("art-0067", "2a.-"), b)
    for n, a in [(107, "2."), (108, "3."), (117, "4."), (118, "5."), (119, "6.")]:
        whole(u, s, n, f"{a} Sustitúyase el artículo {n} por el siguiente:", after=top)
    (b,) = s.quoted("7. En el artículo 145 añádase como tercer inciso el siguiente:", after=top)
    if u.count("art-0145") != 2:
        raise SystemExit("art. 145 should have two incisos")
    u.insert("art-0145", 2, b)
    whole(u, s, 146, "8. Sustitúyase el artículo 146 por el siguiente:", after=top)
    (b,) = s.quoted("9. Sustitúyanse los incisos segundo y tercero del artículo 181 por el siguiente:", after=top)
    u.set_para("art-0181", 1, b, count=2)
    (b,) = s.quoted("10. Sustitúyanse los literales a) y b) del artículo 226 por lo siguiente:", after=top)
    # the gazette sets both literals in one paragraph; one item per line (decisions)
    (one,) = b
    a_, b_ = re.split(r" (?=b\) )", one)
    if not (u.paras("art-0226")[1].startswith("a)") and u.paras("art-0226")[2].startswith("b)")):
        raise SystemExit("art. 226 literals not where expected")
    u.set_para("art-0226", 1, [a_, b_], count=2)
    (b,) = s.quoted("11. Sustitúyase el inciso segundo del artículo 309 por el siguiente:", after=top)
    u.set_para("art-0309", 1, b)
    (b,) = s.quoted("12. Añádase en el artículo 835 como segundo inciso el siguiente:", after=top)
    u.insert("art-0835", 1, b)
    (b,) = s.quoted("13. Sustitúyase el tercer inciso del artículo 842 por el siguiente:", after=top)
    u.set_para("art-0842", 2, b)
    s.check('14. Sustitúyase en el artículo 845 la frase "Para obtener la licencia judicial" por "Para obtener la autorización judicial para constituir el patrimonio familiar".')
    u.sub("art-0845", "Para obtener la licencia judicial", "Para obtener la autorización judicial para constituir el patrimonio familiar")
    s.check('15. Sustitúyase en el segundo inciso del artículo 847 la palabra "licencia" por "autorización".')
    u.sub("art-0847", "licencia", "autorización", para=1)
    s.check('16. Agréguese en el numeral 4 del artículo 851 luego de la frase "el juez" la frase "o el notario o notaria".')
    u.sub("art-0851", "por el juez,", "por el juez o el notario o notaria,", para="4a.-")
    whole(u, s, 853, "17. Sustitúyase el artículo 853 por el siguiente:", after=top)
    s.check('18. Sustitúyase en el inciso tercero del artículo 1245, la frase "por el ministerio del juez, con las formalidades legales", '
            'por "en procedimiento voluntario, según las disposiciones del Código Orgánico General de Procesos".')
    u.sub("art-1245", "por el ministerio del juez, con las formalidades legales",
          "en procedimiento voluntario, según las disposiciones del Código Orgánico General de Procesos", para=2)
    (b,) = s.quoted("19. Sustitúyase en el artículo 1263 el primer inciso por el siguiente:", after=top)
    u.set_para("art-1263", 0, b)
    s.check('20. En el artículo 1267, sustitúyase la frase "el juez," por "la jueza o el juez en procedimiento voluntario".')
    u.sub("art-1267", "el juez,", "la jueza o el juez en procedimiento voluntario")
    (b,) = s.quoted("21. Agréguese en el artículo 1631 como segundo inciso el siguiente:", after=top)
    u.insert("art-1631", 1, b)
    (b,) = s.quoted("22. Sustitúyase el inciso segundo del artículo 1715 por el siguiente:", after=top)
    u.set_para("art-1715", 1, b)
    whole(u, s, 1844, "23. Sustitúyase el artículo 1844 por el siguiente:", after=top)
    s.check("SÉPTIMA.- Deróguense los artículos 121, 1050, 1617, 1618 y 1716 del Código Civil")
    for n in [121, 1050, 1617, 1618, 1716]:
        u.remove(art_key(n))


def coa_2017(u: Units) -> None:
    s = Src(S983_2017)
    i = s.index("QUINTA.- Añádase como último inciso del artículo 585 del Código Civil, el siguiente:")
    u.insert("art-0585", u.count("art-0585"), [s.paras[i + 1]])
    # Sexta and Séptima re-enact the first incisos of arts. 588 and 589 in the words they already had (checked here)
    first588 = s.inline("SEXTA.- Sustitúyase el inciso primero del artículo 588 del Código Civil, por el siguiente:")
    first589 = s.inline("SÉPTIMA.- Sustitúyase el inciso primero del artículo 589 del Código Civil, por el siguiente:")
    if u.paras("art-0588")[0] != "Art. 588.- " + first588 or u.paras("art-0589")[0] != "Art. 589.- " + first589:
        raise SystemExit("COA: arts. 588/589 first incisos differ from the text in force")


def cc_56_09_in_22(u: Units) -> None:
    s = Src(EC15_2022)
    s.check('Declarar la inconstitucionalidad de las frases "o las buenas costumbres" del artículo 567 del Código Civil y '
            '"o los intereses, o no corresponden al objeto de su institución" del artículo 577 del Código Civil. '
            'De manera que los artículos impugnados se leerán de la siguiente manera:')
    i = s.index("De manera que los artículos impugnados se leerán de la siguiente manera:")
    if not (s.paras[i + 1].startswith("Art. 567.-") and s.paras[i + 3].startswith("Art. 577.-")):
        raise SystemExit("56-09-IN/22: read-as text not where expected")
    u.set_unit("art-0567", s.paras[i + 1:i + 3])
    u.set_unit("art-0577", s.paras[i + 3:i + 5])


# ---------------------------------------------------------------- laws and order of entry into force

IMAGE_ONLY = ("NOT APPLIED here: the Registro Oficial edition that publishes it is page images without a text layer, "
              "and this repository does not OCR. Its wording is missing from the files named in this commit; they "
              "keep the earlier text (provisions named from the Ediciones Legales index on gob.ec, 2025).")
NO_EDITION = ("NOT APPLIED here: the Registro Oficial portal's link for this suplemento serves the ordinary edition of "
              "the same day, so no official text of the ruling could be read. The file named in this commit keeps the "
              "earlier text (provision named from the Lexis index of 2017).")

LAWS = {
    "cc-fe-erratas-2005-08": dict(label="Fe de erratas, RO 79 (2005)", kind="law", enacted="2005-07-29",
                                   published="2005-08-10", url=RO79_2005,
                                   title="Fe de erratas a la Codificación del Código Civil (Comisión de Legislación y Codificación, oficio 215-CLC-CN)",
                                   note="A correction (fe de erratas) of the published codification by the Comisión de Legislación y Codificación."),
    "cc-fe-erratas-2005-12": dict(label="Fe de erratas, RO 169 (2005)", kind="law", enacted="2005-12-08",
                                   published="2005-12-20", url=RO169_2005,
                                   title="Fe de erratas a la Codificación del Código Civil (Comisión de Legislación y Codificación, oficio 377-CLC-CN)",
                                   note="A correction (fe de erratas) of the published codification by the Comisión de Legislación y Codificación."),
    "tc-002-06-di": dict(label="Resolución TC 002-06-DI", kind="court", enacted=None, published="2006-05-19",
                          url=RO274_2006, title="Tribunal Constitucional: inconstitucionalidad del art. 260 del Código Civil",
                          note=NO_EDITION),
    "cc-025-10-scn-cc": dict(label="Sentencia 025-10-SCN-CC", kind="court", enacted=None, published="2010-09-23",
                              url=RO285_2010, title="Corte Constitucional: declárase inconstitucional el artículo 257 del Código Civil",
                              note=NO_EDITION),
    "cc-0001-11-sin-cc": dict(label="Sentencia 0001-11-SIN-CC", kind="court", enacted="2011-04-14", published="2011-05-19",
                               url=S452_2011, title='Corte Constitucional: inconstitucionalidad de la frase "o ha estado" del art. 23 del Código Civil'),
    "ley-creditos-vivienda-vehiculos-2012": dict(label="Ley Orgánica de Créditos para Vivienda y Vehículos", kind="law",
                                                  enacted=None, published="2012-06-26", url=S732_2012,
                                                  title="Ley Orgánica para la Regulación de los Créditos para Vivienda y Vehículos"),
    "ley-organica-discapacidades-2012": dict(label="Ley Orgánica de Discapacidades", kind="law", enacted=None,
                                              published="2012-09-25", url=S796_2012, title="Ley Orgánica de Discapacidades"),
    "ley-defensa-derechos-laborales-2012": dict(label="Ley Orgánica para la Defensa de los Derechos Laborales", kind="law",
                                                 enacted="2012-07-31", published="2012-09-26", url=S797_2012,
                                                 title="Ley Orgánica para la Defensa de los Derechos Laborales"),
    "ley-buros-credito-2012": dict(label="Ley Orgánica Derogatoria a la Ley de Burós", kind="law", enacted=None,
                                    published="2012-12-03", url=S843_2012,
                                    title="Ley Orgánica Derogatoria a la Ley de Burós de Información Crediticia y Reformatoria a la Ley del Sistema Nacional del Registro de Datos Públicos, a la Ley Orgánica de la Economía Popular y Solidaria y del Sector Financiero Popular y Solidario y a la Ley de Compañías"),
    "comf-2014": dict(label="Código Orgánico Monetario y Financiero", kind="law", enacted=None, published="2014-09-12",
                      url=S332_2014, title="Código Orgánico Monetario y Financiero"),
    "ley-reformatoria-codigo-civil-2015": dict(label="Ley Reformatoria al Código Civil (2015)", kind="law",
                                                enacted="2015-06-16", published="2015-06-19", url=S526_2015,
                                                title="Ley Reformatoria al Código Civil"),
    "cogep-2015": dict(label="Código Orgánico General de Procesos", kind="law", enacted=None, published="2015-05-22",
                       url=S506_2015, title="Código Orgánico General de Procesos (COGEP)"),
    "codigo-organico-ambiente-2017": dict(label="Código Orgánico del Ambiente", kind="law", enacted=None,
                                           published="2017-04-12", url=S983_2017, title="Código Orgánico del Ambiente"),
    "cc-10-18-cn-19": dict(label="Sentencia 10-18-CN/19", kind="court", enacted=None, published="2019-07-08",
                            url=EC96_2019, title="Corte Constitucional: matrimonio entre personas del mismo sexo (art. 81 del Código Civil)",
                            note=IMAGE_ONLY),
    "ley-extincion-dominio-2021": dict(label="Ley Orgánica de Extinción de Dominio", kind="law", enacted=None,
                                        published="2021-05-14", url=S452_2021, title="Ley Orgánica de Extinción de Dominio",
                                        note=IMAGE_ONLY),
    "ley-reformatoria-cc-convemar-2021": dict(label="Ley Reformatoria al Código Civil (CONVEMAR)", kind="law",
                                               enacted=None, published="2021-10-19", url=S561_2021,
                                               title="Ley Reformatoria al Código Civil en materia de regulación marítima en concordancia con la CONVEMAR",
                                               note=IMAGE_ONLY),
    "cc-56-09-in-22": dict(label="Sentencia 56-09-IN/22", kind="court", enacted="2022-01-27", published="2022-03-14",
                            url=EC15_2022, title="Corte Constitucional: inconstitucionalidad de frases de los arts. 567 y 577 del Código Civil"),
    "ley-salud-mental-2024": dict(label="Ley Orgánica de Salud Mental", kind="law", enacted=None, published="2024-01-05",
                                   url=S471_2024, title="Ley Orgánica de Salud Mental", note=IMAGE_ONLY),
    "ley-ahorro-monetizacion-2024": dict(label="Ley Orgánica para el Ahorro y la Monetización de Recursos", kind="law",
                                          enacted=None, published="2024-02-09", url=S496_2024,
                                          title="Ley Orgánica para el Ahorro y la Monetización de Recursos Económicos para el Financiamiento de la Lucha contra la Corrupción",
                                          note=IMAGE_ONLY),
    "ley-reformatoria-logidac-2024": dict(label="Ley Orgánica Reformatoria de la LOGIDAC (2024)", kind="law", enacted=None,
                                           published="2024-03-13", url=S517_2024,
                                           title="Ley Orgánica Reformatoria de la Ley Orgánica de Gestión de Identidad y Datos Civiles",
                                           note=IMAGE_ONLY),
    "ley-victimas-femicidio-2024": dict(label="Ley Orgánica de Reparación a Familiares de Víctimas de Femicidio", kind="law",
                                         enacted=None, published="2024-06-27", url=S588_2024,
                                         title="Ley Orgánica de Acompañamiento y Reparación Transformadora e Integral a Hijas, Hijos, Madres, Padres y demás Familiares de Víctimas de Femicidio y otras Muertes Violentas por Razones de Género",
                                         note=IMAGE_ONLY),
}

# (law, in force from, edit function or the provisions a not-applied act concerns)
STEPS = [
    ("cc-fe-erratas-2005-08", "2005-08-10", fe_erratas_2005_08),
    ("cc-fe-erratas-2005-12", "2005-12-20", fe_erratas_2005_12),
    ("tc-002-06-di", "2006-05-19", ["art-0260"]),
    ("cc-025-10-scn-cc", "2010-09-23", ["art-0257"]),
    ("cc-0001-11-sin-cc", "2011-05-19", cc_0001_11_sin_cc),
    ("ley-creditos-vivienda-vehiculos-2012", "2012-06-26", ley_creditos_vivienda_2012),
    ("ley-organica-discapacidades-2012", "2012-09-25", lod_2012),
    ("ley-defensa-derechos-laborales-2012", "2012-09-26", loddl_2012),
    ("ley-buros-credito-2012", "2012-12-03", ley_buros_2012),
    ("comf-2014", "2014-09-12", comf_2014),
    ("ley-reformatoria-codigo-civil-2015", "2015-06-19", reformatoria_cc_2015),
    ("cogep-2015", "2016-05-22", cogep_2015),
    ("codigo-organico-ambiente-2017", "2018-04-12", coa_2017),
    ("cc-10-18-cn-19", "2019-07-08", ["art-0081"]),
    ("ley-extincion-dominio-2021", "2021-05-14", ["art-0603"]),
    ("ley-reformatoria-cc-convemar-2021", "2021-10-19", ["art-0606", "art-0609", "art-0610", "art-0613"]),
    ("cc-56-09-in-22", "2022-03-14", cc_56_09_in_22),
    # the index marks the heading of Título XXII and arts. 478-496, 1012; the comparison with the same consolidation
    # also shows "demente(s)" replaced by "persona(s) con trastorno(s) mental(es)" in arts. 192, 518, 738, 1463, 2219, 2409
    ("ley-salud-mental-2024", "2024-01-05", ["titulos", "art-0192", "art-0478", "art-0479", "art-0480", "art-0481",
                                             "art-0482", "art-0484", "art-0485", "art-0486", "art-0487", "art-0489",
                                             "art-0496", "art-0518", "art-0738", "art-1012", "art-1463", "art-2219",
                                             "art-2409"]),
    ("ley-ahorro-monetizacion-2024", "2024-02-09", ["art-0603"]),
    ("ley-reformatoria-logidac-2024", "2024-03-13", ["art-0021"]),
    ("ley-victimas-femicidio-2024", "2024-06-27", ["art-1010"]),
]

# provisions an applied act re-enacts in unchanged words: credited, so the commit names them (Words-changed per unit)
ALSO_CONCERNS = {"codigo-organico-ambiente-2017": ["art-0588", "art-0589"]}


def sha_of(url: str) -> str:
    return hashlib.sha256(fetch.cached(url).read_bytes()).hexdigest()


def order(key: str) -> tuple:
    m = re.match(r"art-(\d{4})(?:-(\w+))?$", key)
    if m:
        return (1, int(m.group(1)), m.group(2) or "")
    return ({"disp-transitoria": 2, "disp-final": 3, "titulos": 4}.get(key, 5), 0, key)


def replay(first: dict) -> list[dict]:
    """Versions after the first: each {'from', 'source_url', 'sha256', 'changes', 'credits', 'note'?}."""
    out = []
    units = first
    for law, day, edit in STEPS:
        url = LAWS[law]["url"]
        if isinstance(edit, list):
            for k in edit:
                if k not in units:
                    raise SystemExit(f"{law}: no unit {k}")
            out.append({"from": day, "source_url": url, "sha256": sha_of(url), "changes": {},
                        "credits": {k: [law] for k in sorted(edit, key=order)}})
            continue
        u = Units(units)
        edit(u)
        new = u.u
        changed = sorted((k for k in set(units) | set(new) if units.get(k) != new.get(k)), key=order)
        if not changed:
            raise SystemExit(f"{law}: no change")
        credits = {k: [law] for k in changed}
        for k in ALSO_CONCERNS.get(law, []):
            credits[k] = [law]
        out.append({"from": day, "source_url": url, "sha256": sha_of(url),
                    "changes": {k: new.get(k) for k in changed},
                    "credits": dict(sorted(credits.items(), key=lambda kv: order(kv[0])))})
        units = new
    return out
