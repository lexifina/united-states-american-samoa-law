"""Write corpus.d/70-comercio.json: the Código de Comercio of 2019 and its amending acts.

Reads only the cache (fetch with `python -X utf8 codes/fetch_codes.py`). Deterministic: the same cache gives the
same bytes. The part is written atomically (.tmp, then rename).

    python -X utf8 codes/comercio.py            (COMERCIO_OUT=... to write elsewhere)

Base: Registro Oficial Suplemento 497, 29-V-2019 (text layer). Amending acts found with codes/screen.py (every law
on the Asamblea's 'leyes aprobadas' list since 2019, text layer searched for the Code) and the Lexis consolidation
of 10-XII-2020 (derechoecuador.com, archived 2024; read only, for the 'Nota:' lines).
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
import fetch  # noqa: E402
import rotext  # noqa: E402
from replay import Src, Units, unquote  # noqa: E402,F401
import strict  # noqa: E402

# typesetting the text layer of Suplemento 497 carries, normalised once (listed in decisions): a combining acute
# accent after an already accented vowel ("tendrá́", art. 552) and a space inside one word (art. 566)
LAYER_FIXES = [("té rminos", "términos")]


def fix_layer(p: str) -> str:
    p = re.sub("(?<=[áéíóúÁÉÍÓÚ])́", "", p)
    for a, b in LAYER_FIXES:
        p = p.replace(a, b)
    return p

OUT = Path(os.environ.get("COMERCIO_OUT", HERE.parent / "corpus.d" / "70-comercio.json"))
RETRIEVED = "2026-10-29"
H = "http://esacc.corteconstitucional.gob.ec/storage/api/v1/10_DWL_FL/"
S497_2019 = H + "eyJjYXJwZXRhIjoicm8iLCJ1dWlkIjoiYWNkMzY5YjMtYzIxNC00YWE2LWFlN2MtY2NmNzQ2ZjZlMjFmLnBkZiJ9"
S347_2020 = ("https://esacc.corteconstitucional.gob.ec/storage/api/v1/10_DWL_FL/"
             "eyJjYXJwZXRhIjogInJvIiwgInV1aWQiOiAiMmVhOGRmODQtZDMyYS00MGUxLWI3YWMtY2E3OTM5ZjA5OGY5LnBkZiJ9")
S245_2023 = H + "eyJjYXJwZXRhIjoicm8iLCJ1dWlkIjoiN2U1MmIzZDctMGJhNS00YzU4LWE0NzQtMDBlMTlmY2JlMTI3LnBkZiJ9"
LEXIS_2020 = ("https://web.archive.org/web/20240527012147id_/"
              "https://derechoecuador.com/uploads/content/2021/01/file_1609955536_1609955541.pdf")

ORD = ["PRIMERA", "SEGUNDA", "TERCERA", "CUARTA", "QUINTA", "SEXTA", "SÉPTIMA", "OCTAVA", "NOVENA", "DÉCIMA"]
ORD_LOW = ["primera", "segunda", "tercera", "cuarta", "quinta", "sexta", "séptima", "octava", "novena", "décima"]
DISP = {"DISPOSICIONES GENERALES": ("disp-general", "Disposición general", "general"),
        "DISPOSICIONES TRANSITORIAS": ("disp-transitoria", "Disposición transitoria", "transitional"),
        "DISPOSICIONES DEROGATORIAS": ("disp-derogatoria", "Disposición derogatoria", "repeal"),
        "DISPOSICIÓN FINAL": ("disp-final", "Disposición final", "final")}
ART = re.compile(r"^Art[íi]culo (\d+)\.? ?-")  # printed "Artículo 43-" and "Artículo 327. -" (kept as printed)
# literals set in one paragraph by the text layer ("... son: a) Las personas ...; b) Las sociedades ...") go one per
# line; the same split is applied to the base and to the amending acts' quoted text
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
    rank = {"disp-general": 2, "disp-transitoria": 3, "disp-derogatoria": 4, "disp-final": 5, "titulos": 6}
    return (rank.get(key.rsplit("-", 1)[0] if key[-1].isdigit() else key, 7), 0, 0, key)


def sha_of(url: str) -> str:
    return hashlib.sha256(fetch.cached(url).read_bytes()).hexdigest()


# ---------------------------------------------------------------- base

def base_units() -> dict:
    path = fetch.cached(S497_2019)
    if path is None:
        raise SystemExit(f"not in cache: {S497_2019}")
    ps = [fix_layer(p) for p in strict.paragraphs(path)]
    start = ps.index("CÓDIGO DE COMERCIO", 10)
    units: dict[str, dict] = {}
    heads: list[str] = []
    cur: str | None = None
    disp: tuple | None = None
    expect = 1
    for p in ps[start + 1:]:
        if p.startswith("Dado y suscrito"):
            break
        m = ART.match(p)
        if p in DISP and expect == 1349:  # the closing dispositions (the same words also head sections inside)
            disp = DISP[p]
            heads.append(p)
            cur = None
            continue
        if disp:
            m2 = re.match(r"^(%s)\.-" % "|".join(ORD + ["ÚNICA"]), p)
            if m2:
                if m2.group(1) == "ÚNICA":
                    cur = disp[0]
                    units[cur] = {"label": disp[1], "kind": disp[2], "text": ""}
                else:
                    i = ORD.index(m2.group(1))
                    cur = f"{disp[0]}-{i + 1:02d}"
                    units[cur] = {"label": f"{disp[1]} {ORD_LOW[i]}", "kind": disp[2], "text": ""}
            elif cur is None:
                raise SystemExit(f"text outside a disposition: {p[:60]!r}")
            units[cur]["text"] += p + "\n"
            continue
        if m:
            n = int(m.group(1))
            if n != expect:
                raise SystemExit(f"article {n} where {expect} was expected")
            expect += 1
            cur = art_key(n)
            units[cur] = {"label": f"Art. {n}", "kind": "art", "text": ""}
            units[cur]["text"] += "".join(x + "\n" for x in split_items([p]))
            continue
        if not re.search(r"[a-zñáéíóúü]", p) or cur is None:
            heads.append(p)  # LIBRO / TÍTULO / CAPÍTULO / SECCIÓN / SUBSECCIÓN headings and their names
            continue
        units[cur]["text"] += "".join(x + "\n" for x in split_items([p]))
    if expect != 1349:
        raise SystemExit(f"stopped at article {expect - 1}")
    units["titulos"] = {"label": "Libros, títulos, capítulos y secciones", "kind": "headings",
                        "text": "".join(h + "\n" for h in heads)}
    return dict(sorted(units.items(), key=lambda kv: order(kv[0])))


# ---------------------------------------------------------------- amending acts

def q(s: Src, anchor: str, count: int = 1) -> list[list[str]]:
    return [split_items(b) for b in s.quoted(anchor, count=count)]


def whole(u: Units, s: Src, n: int, anchor: str) -> None:
    (b,) = q(s, anchor)
    m = re.match(rf"Art(?:\.|ículo)\s*{n}\.-\s*", b[0])
    if not m:
        raise SystemExit(f"art. {n}: quoted text starts {b[0][:30]!r}")
    # the act quotes "Art. 78.- ..."; the Code numbers its articles "Artículo 78.- ..."
    b[0] = f"Artículo {n}.- " + b[0][m.end():]
    u.set_unit(art_key(n), b)


def transformacion_digital_2023(u: Units) -> None:
    """Ley Orgánica para la Transformación Digital y Audiovisual, Título IV (arts. 45-61), Tercer Suplemento 245,
    7-II-2023; in force on publication (its Disposición final)."""
    s = Src(S245_2023)
    s.check("TÍTULO IV REFORMAS AL CÓDIGO DE COMERCIO",
            "Las disposiciones de la presente Ley entrarán en vigencia a partir de la fecha de su publicación en el Registro Oficial")
    whole(u, s, 78, "Artículo 45.- Reemplácese el artículo 78 por el siguiente:")
    whole(u, s, 79, "Artículo 46.- Reemplácese el artículo 79 por el siguiente:")
    whole(u, s, 80, "Artículo 47.- En el artículo 80, eliminar el segundo inciso posterior al literal b")
    whole(u, s, 85, "Artículo 48.- Reemplácese el artículo 85 por el siguiente:")
    whole(u, s, 88, "Artículo 49.- Reemplácese el artículo 88 por el siguiente:")
    whole(u, s, 90, "Artículo 50.- Reemplácese el artículo 90 por el siguiente:")
    whole(u, s, 92, "Artículo 51.- Reemplácese el artículo 92 por el siguiente:")
    whole(u, s, 95, "Artículo 52.- Reemplácese el artículo 95 por el siguiente:")
    whole(u, s, 96, "Artículo 53.- Reemplácese el artículo 96 por el siguiente:")
    # art. 54: two paragraphs "al final del penúltimo inciso" of art. 84: set after it as incisos of their own
    (b,) = q(s, "Artículo 54.- En el artículo 84, al final del penúltimo inciso, agréguese lo siguiente:")
    n = u.count("art-0084")
    u.insert("art-0084", n - 1, b)
    # art. 55: a phrase after "El endoso de títulos valores desmaterializados" in art. 109
    s.check('Artículo 55.- En el artículo 109, luego de la frase: "El endoso de títulos valores desmaterializados", '
            'agréguese la frase: "negociables en el mercado de valores".')
    u.sub("art-0109", "El endoso de títulos valores desmaterializados",
          "El endoso de títulos valores desmaterializados negociables en el mercado de valores")
    # art. 56: art. 112, second inciso substituted (a) and a third added (b)
    (b1,) = q(s, "a. Reemplácese el segundo inciso por el siguiente:")
    (b2,) = q(s, "b. Agréguese como tercer inciso lo siguiente:")
    if u.count("art-0112") != 2:
        raise SystemExit("art. 112: expected two incisos")
    u.set_para("art-0112", 1, b1 + b2)
    (b,) = q(s, "Artículo 57.- A continuación del artículo 112, agréguese el siguiente artículo innumerado:")
    u.set_unit("art-0112-1", b, label="Art. innumerado (tras el art. 112)")
    (b,) = q(s, "Artículo 58.- Después del artículo 113, agréguese el siguiente artículo innumerado:")
    u.set_unit("art-0113-1", b, label="Art. innumerado (tras el art. 113)")
    whole(u, s, 126, "Artículo 59.- Sustitúyase el artículo 126 por el siguiente:")
    (b,) = q(s, "Artículo 60.- Después del artículo 189, agréguese el siguiente:")
    u.set_unit("art-0189-1", b, label="Art. innumerado (tras el art. 189)")
    (b,) = q(s, "Artículo 61.- Agréguese un segundo inciso en el artículo 272 con el siguiente texto:")
    if u.count("art-0272") != 1:
        raise SystemExit("art. 272: expected one inciso")
    u.insert("art-0272", 1, b)


IMAGE_ONLY = ("NOT APPLIED here: the Registro Oficial edition that publishes it is page images without a text layer, "
              "and this repository does not OCR. Its wording is missing: the chapter and articles it adds are absent "
              "and the files named in this commit keep the earlier text (provisions named from the Lexis index of "
              "10-XII-2020).")

LAWS = {
    "codigo-comercio-2019": dict(label="Código de Comercio (2019)", kind="law", enacted="2019-05-09",
                                 published="2019-05-29", url=S497_2019, title="Código de Comercio"),
    "ley-modernizacion-companias-2020": dict(label="Ley de Modernización a la Ley de Compañías (2020)", kind="law",
                                             enacted="2020-12-01", published="2020-12-10", url=S347_2020,
                                             title="Ley de Modernización a la Ley de Compañías", note=IMAGE_ONLY),
    "ley-transformacion-digital-2023": dict(label="Ley Orgánica para la Transformación Digital y Audiovisual (2023)",
                                            kind="law", enacted=None, published="2023-02-07", url=S245_2023,
                                            title="Ley Orgánica para la Transformación Digital y Audiovisual"),
}

STEPS = [
    # Disposición reformatoria única: Capítulo Tercero 'De la asociación o cuentas de participación', arts. 607.1-607.6,
    # after art. 607 (Lexis index); credited to art. 607 and the headings, where they would go
    ("ley-modernizacion-companias-2020", "2020-12-10", ["art-0607", "titulos"]),
    ("ley-transformacion-digital-2023", "2023-02-07", transformacion_digital_2023),
]

DECISIONS = [
    "Código de Comercio: the first version is the Code as enacted (Registro Oficial Suplemento 497, 29-V-2019), in force on its publication (its Disposición final única). It replaced the codification of 1960, which is not part of this history.",
    "Código de Comercio: units are art-NNNN for each article (articles added later keep their place: art-0112-1 for the article innumerado after art. 112); disp-general-NN, disp-transitoria-01, disp-derogatoria-NN, disp-final; 'titulos' holds the Libro, Título, Capítulo, Sección and Subsección headings in order. The Asamblea's oficio, certification and considerandos are not units.",
    "Código de Comercio: literals the text layer sets in one paragraph ('a) ...; b) ...') are split one per line, in the base and in the amending acts' quoted text alike; nothing else is reworded. The heading 'UBSECCIÓN' (for 'SUBSECCIÓN') is kept as the text layer prints it.",
    "Código de Comercio: amending acts were found by screening the text layer of every law on the Asamblea Nacional's 'leyes aprobadas' list from 2019 to October 2026 that could touch commercial law (codes/screen.py, 35 laws) and from the Lexis consolidation of 10-XII-2020 (read only). Only two acts amend the Code: the Ley de Modernización a la Ley de Compañías (2020) and the Ley Orgánica para la Transformación Digital y Audiovisual (2023).",
    "Código de Comercio: the Ley Orgánica para la Transformación Digital y Audiovisual (Tercer Suplemento 245, 7-II-2023, Título IV, arts. 45-61) is applied from the gazette's text layer, in force on publication (its Disposición final). Its art. 54 adds two paragraphs 'al final del penúltimo inciso' of art. 84; they are set as incisos of their own after that inciso. Where it quotes a whole article as 'Art. 78.-' the Code's own form 'Artículo 78.-' is kept.",
    "Código de Comercio: NOT APPLIED, image-only gazette edition (no text layer; no OCR by the user's decision): the Ley de Modernización a la Ley de Compañías (Tercer Suplemento 347, 10-XII-2020; 80 of 83 pages are images), whose Disposición reformatoria única adds Capítulo Tercero 'De la asociación o cuentas de participación' (arts. 607.1-607.6) after art. 607 (Lexis index). It has a version of its own that changes no words; those six articles are missing from 10-XII-2020 on.",
    "Código de Comercio: gaps that could not be closed: many laws of 2020-2026 are printed only as page images, so whether they amend the Code could not be read. A Lexis consolidation hosted by the Cuerpo de Bomberos de Quito (cdc25.pdf, cdc26.pdf; unreachable from here and not archived) is reported in a search snippet to give 7-II-2023 (2025 copy) and then 13-X-2025 (2026 copy) as its last reform. The only law published on 13-X-2025 on the Asamblea's list is the Ley Orgánica Reformatoria del Código Orgánico Monetario y Financiero (Sexto Suplemento 142), image-only; any change it made to this Code is missing and not recorded as a version because no provision could be identified.",
    "Código de Comercio: there is no official consolidated text. The version in force on 10-XII-2020 was compared, for reading only, with the Lexis consolidation of that date (codes/reconcile_comercio.py): 1,321 of 1,348 articles agree after normalising spacing and quotes; Lexis alone has arts. 607.1-607.6 (the 2020 act not applied). The 27 that disagree are (a) Lexis's own readings: 'cúratela' (24), 'cambiaría' (171, 173), 'nado' for 'fiado' (470), 'B)' (462), 'Léase' (1256), 'sub- contratar', 'know- how', 'joint- venture' (546, 577, 593, 597), its quote placement (125, 261, 1336) and 'Concordancias' run into the text (117, 215, 646); (b) the gazette's own wording, kept as printed: 'documento. b)' (187), a doubled full stop (202, 807), 'o c)' (309), 'compra venta' (370), 'rehúsa' (646, 653), 'adecúen' (215), 'fletadorrepuestos' (952), 'Sí la avería' (1120), 'árbitro' (1126), 'cada uno de las naves' (1157), 'indeminización' (1237).",
    "Código de Comercio text: pages of Suplemento 497 carry many small stray text fragments over and between the columns (pieces of nearby lines) and print some headings twice in the same place; a text block overlapping a fuller block by at least 15% of its area, and the second copy of an identical block, are skipped (codes/strict.py; no block of more than 25 characters is skipped by this rule). A combining accent after an accented vowel ('tendrá́', art. 552) is dropped and one space inside a word ('té rminos', art. 566) closed up. Articles printed 'Artículo 43-' and 'Artículo 327. -' keep that form.",
]

AI_USE = [
    "Código de Comercio: no generative model wrote legal text. The amendment map in codes/comercio.py (which provision each act changes, and the anchor phrases before its new text in the act's PDF) was written by an AI agent (Claude) from reading the act; the words are cut from the gazette PDFs' text layers. No OCR was used.",
]


def replay(first: dict) -> list[dict]:
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
        new = dict(sorted(u.u.items(), key=lambda kv: order(kv[0])))
        changed = sorted((k for k in set(units) | set(new) if units.get(k) != new.get(k)), key=order)
        if not changed:
            raise SystemExit(f"{law}: no change")
        out.append({"from": day, "source_url": url, "sha256": sha_of(url),
                    "changes": {k: new.get(k) for k in changed}, "credits": {k: [law] for k in changed}})
        units = new
    return out


def build_act() -> dict:
    units = base_units()
    first = {"from": "2019-05-29", "source_url": S497_2019, "sha256": sha_of(S497_2019), "units": units, "credits": {}}
    return {"slug": "codigo-comercio", "short": "CCom", "title": "Código de Comercio", "url": S497_2019,
            "first_law": "codigo-comercio-2019", "earlier_laws": [], "versions": [first] + replay(units)}


def laws() -> dict:
    return {k: {"label": v["label"], "title": v["title"], "kind": v["kind"], "enacted": v.get("enacted"),
                "published": v["published"], "url": v["url"], "temporary_until": None, "restores": None,
                "note": v.get("note")} for k, v in LAWS.items()}


def sources() -> list[dict]:
    return [
        {"name": "Registro Oficial del Ecuador (Código de Comercio and its amending acts)",
         "url": "https://www.registroficial.gob.ec", "retrieved": RETRIEVED, "requests": 3,
         "licence": "No licence stated on the site; official gazette text.",
         "notes": "One PDF per gazette edition, served by esacc.corteconstitucional.gob.ec, found through the site's month listings (codes/probe.py). Every version's wording is cut from the text layer of the 2019 Code and of the amending act; the edition without a text layer is listed in decisions and not applied."},
        {"name": "Asamblea Nacional, 'Leyes aprobadas'", "url": "https://www.asambleanacional.gob.ec/es/leyes-aprobadas",
         "retrieved": RETRIEVED, "requests": 53, "licence": "No licence stated; official copies of Registro Oficial editions.",
         "notes": "Index of laws 2019-2026; their PDFs' text layers were searched for the Code (codes/screen.py, codes/screen_comercio.json). Reading only."},
        {"name": "Lexis consolidation of the Código de Comercio, 10-XII-2020 (derechoecuador.com, Internet Archive capture 20240527012147)",
         "url": LEXIS_2020, "retrieved": RETRIEVED, "requests": 2,
         "licence": "Lexis copyright; read only, nothing copied.",
         "notes": "Index of the 2020 amendment ('Nota:' lines) and reading-only comparison of the 2019 base."},
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
