"""Write corpus.d/50-civil.json: the Código Civil (codificación 2005) and its amending acts.

Reads only the cache (fetch with civil/fetch_civil.py). Deterministic: the same cache gives the same bytes.
The part is written atomically (.tmp, then rename).

    python -X utf8 civil/parse_civil.py
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import fetch  # noqa: E402
import base  # noqa: E402
import replay  # noqa: E402

OUT = Path(os.environ.get("CIVIL_OUT", HERE.parent / "corpus.d" / "50-civil.json"))
RETRIEVED = "2026-10-28"

BASE_LAW = "codificacion-cc-2005-010"
EXTRA_LAWS = {
    BASE_LAW: dict(label="Codificación 2005-010 del Código Civil", kind="law", enacted="2005-05-10",
                   published="2005-06-24", url=base.RO46_2005,
                   title="Codificación del Código Civil (Comisión de Legislación y Codificación del Congreso Nacional)"),
}

DECISIONS = [
    "Código Civil: the oldest version is the Codificación 2005-010 (Registro Oficial Suplemento 46, 24-VI-2005), in force from its publication (its Disposición final: the code and its reforms are in force from their publication). The Code itself dates from 1861; older texts are not in the gazette's text layer, so the first version is credited to the publisher as the oldest version available.",
    "Código Civil: every later version replays an amending act's own Registro Oficial text (pymupdf text layer) on the version before it, in order of entry into force. Whole articles and paragraphs are cut from the act's PDF after an anchor phrase; every short phrase an act inserts or deletes is checked to occur word for word in the act's PDF (civil/replay.py).",
    "Código Civil: in-force dates follow Código Civil art. 6 (in force on publication in the Registro Oficial) unless the act says otherwise: the Código Orgánico General de Procesos (published 22-V-2015) took effect twelve months later, on 22-V-2016 (its Disposición final segunda); the Código Orgánico del Ambiente (published 12-IV-2017) twelve months later, on 12-IV-2018 (its Disposición final única).",
    "Código Civil: COGEP's Disposición final segunda puts in force on publication the norms 'que regulan ... citación'; its Civil Code reforms (Disposición reformatoria quinta, including numerals 1 and 6, which refer citation to COGEP) are dated 22-V-2016 with the rest of the Code, as the Lexis index also dates them.",
    "Código Civil: constitutional rulings that strike words (0001-11-SIN-CC, 56-09-IN/22) take effect on the day of their publication in the Registro Oficial; 56-09-IN/22 itself states how arts. 567 and 577 'se leerán', and that text is taken from the ruling.",
    "Código Civil: corrections (fe de erratas) of the 2005 codification by the Comisión de Legislación y Codificación take effect on the day they were published (RO 79, 10-VIII-2005: art. 1059; RO 169, 20-XII-2005: art. 99).",
    "Código Civil: NOT APPLIED, image-only gazette editions (no text layer; no OCR by the user's decision): Sentencia 10-18-CN/19 (Edición Constitucional 96, 8-VII-2019: art. 81), Ley Orgánica de Extinción de Dominio (Quinto Suplemento 452, 14-V-2021: art. 603), Ley Reformatoria al Código Civil en materia de regulación marítima / CONVEMAR (Quinto Suplemento 561, 19-X-2021: arts. 606, 609, 610, 613), Ley Orgánica de Salud Mental (Suplemento 471, 5-I-2024: the heading of Título XXII, arts. 478-482, 484-487, 489, 496, 1012, and 'demente(s)' read as 'persona(s) con trastorno(s) mental(es)' in arts. 192, 518, 738, 1463, 2219, 2409), Ley Orgánica para el Ahorro y la Monetización de Recursos (Segundo Suplemento 496, 9-II-2024: art. 603), Ley Orgánica Reformatoria de la LOGIDAC (Suplemento 517, 13-III-2024: art. 21), Ley Orgánica de reparación a familiares de víctimas de femicidio (Tercer Suplemento 588, 27-VI-2024: art. 1010). Each has a version of its own on its publication date that changes no words; its commit says the change is missing, and the files it names keep the earlier wording. Their own vigencia clauses could not be read, so their dates follow art. 6.",
    "Código Civil: NOT APPLIED, gazette text unreachable: Resolución del Tribunal Constitucional 002-06-DI (Suplemento 274, 19-V-2006: art. 260) and Sentencia 025-10-SCN-CC (Suplemento 285, 23-IX-2010: art. 257). The portal links for both suplementos serve the ordinary edition of the same day; the sumario of Suplemento 285 confirms 'Declárase inconstitucional el artículo 257 del Código Civil'. Both articles were then repealed by the Ley Reformatoria al Código Civil (19-VI-2015), which is applied.",
    "Código Civil: the articles named for acts that are not applied come from the editorial indexes (Ediciones Legales on gob.ec, 2025; Lexis at WIPO Lex, 2017) and, for the Ley Orgánica de Salud Mental, from comparing today's text with the Ediciones Legales one; read only, no wording is taken from them.",
    "Código Civil: the provisions named as affected by not-applied acts therefore read, from those dates on, in their earlier wording, which is no longer the law: art. 81 from 8-VII-2019; art. 603 from 14-V-2021; arts. 606, 609, 610, 613 from 19-X-2021; arts. 21, 192, 478-482, 484-487, 489, 496, 518, 738, 1010, 1012, 1463, 2219, 2409 and the Título XXII heading from 2024; arts. 257 and 260 between 2006/2010 and 19-VI-2015.",
    "Código Civil: phrases are replaced exactly as the act words them, even where the result is ungrammatical (Ley Orgánica de Discapacidades 2012: 'del persona sorda', 'al persona sorda', 'el persona sorda', 'los persona sorda' in arts. 490-493 and 1463). Editorial consolidations adjust the article ('de la persona sorda'); the official text does not.",
    "Código Civil: where an act quotes the words it changes slightly differently from the codified text, the evident words are changed and the difference is recorded: Ley Orgánica de Discapacidades 2012, num. 11 quotes 'sordomudos que no puedan darse a entender por escrito.' for art. 1463, which reads 'pueden'; Ley Reformatoria 2015, art. 48 quotes 'o que contraviene la disposición del Art. 90' for art. 552, which reads 'contraviene a la disposición' (the comma before it is removed with it).",
    "Código Civil: when an act deletes a phrase, the space it leaves before a following space or punctuation mark goes with it; nothing else is tidied ('nueva decisión judicial que, la apruebe' in art. 424 and 'El juez, aceptará' in art. 459 are the literal results).",
    "Código Civil: the Ley Orgánica para la Regulación de los Créditos para Vivienda y Vehículos (2012) adds 'y los demás casos previstos en la ley.' 'al final' of art. 2367; it is joined to the last sentence in place of its full stop ('designados en el Art. 1634 y los demás casos previstos en la ley.').",
    "Código Civil: quoted text that closes without a stop of its own, followed by the act's full stop (Spanish sets it after the closing quote), keeps that stop.",
    "Código Civil: COGEP, Disposición reformatoria quinta num. 10 prints the new literals a) and b) of art. 226 in one paragraph; they are split into one line each, like the other literals of the article.",
    "Código Civil: COGEP num. 13 substitutes the third inciso of art. 842 ('En todo caso, el usufructo ...') with a text close to its sixth inciso; it is applied as worded, so the article keeps both 'Puede la jueza o el juez nombrar administrador ...' (third) and 'Puede el juez nombrar administrador ...' (last).",
    "Código Civil: the Código Orgánico del Ambiente (Disposiciones reformatorias sexta and séptima) re-enacts the first incisos of arts. 588 and 589 in the words they already had; they are credited to it with no change of wording. Its quinta adds the last inciso of art. 585.",
    "Código Civil: general renaming clauses that name no article are not applied to the text (COGEP Disposición reformatoria primera: 'Código de Procedimiento Civil' and 'juicio verbal sumario'; COIP Disposición reformatoria primera; LOGIDAC Disposición reformatoria primera), nor are editorial notes about renamed ministries and courts.",
    "Código Civil: the Corte Nacional de Justicia's Resolución 07-2025 (Segundo Suplemento 61, 17-VI-2025, last reform named by Ediciones Legales) declares a binding precedent on reivindicación and prescripción; it changes no words and is not recorded as a version.",
    "Código Civil: no reform published after 17-VI-2025 was found (Ediciones Legales consolidation of 2025; one web search; the Registro Oficial site search does not page reliably). Later reforms, if any, are missing.",
    "Código Civil: there is no official consolidated text of the Código Civil after the 2005 codification. Today's text was compared, for reading only, with the Ediciones Legales consolidation on gob.ec (tools/civil/reconcile_civil.py): of 2,428 articles, 2,362 agree after normalising spacing, quotes and amendment notes.",
    "Código Civil, the 66 that disagree with Ediciones Legales: (a) 26 from the acts not applied above (arts. 21, 81, 192, 478-482, 484-487, 489, 496, 518, 603, 606, 609, 610, 613, 738, 1010, 1012, 1463, 2219, 2409); (b) 12 where Ediciones applies COGEP's general renaming 'Código de Procedimiento Civil' -> 'Código Orgánico General de Procesos' (arts. 16, 27, 229, 337, 406, 419, 1276, 1638, 1731, 2155, 2162, 2239), not applied here (see above; Lexis 2017 does not apply it either); (c) words struck by the Constitutional Court that Ediciones keeps in bold (arts. 23, 567, 577); (d) Ediciones' editorial grammar for the literal LOD 2012 wording (arts. 490-493) and its comma in art. 1267; Ediciones also inserts COGEP num. 16's 'o el notario o notaria' after the capitalised 'El juez' in art. 851, here only after 'el juez' as quoted; (e) Ediciones keeps numeral styles or stubs of the earlier text (arts. 7, 67, 74, 102, 310); (f) modernised spellings in Ediciones where the gazette reads 'constituído', 'restituirsela', 'aservo', 'superviniente', 'rehusa', 'notaria', 'éste' (arts. 229, 231, 835, 851, 872, 933, 1001, 1296, 1362, 1550); (g) the comparison's own splitting of the consolidation at notes and headings (arts. 533, 853, 1591, 1605, 1643, 2145).",
    "Código Civil units: art-NNNN for each article; articles added later keep their place (art-0036-1 for the article innumerado after art. 36, art-0233-a, art-0242-a, art-0242-b); disp-transitoria, disp-final; 'titulos' holds the Libro, Título and Parágrafo headings and the numbered sub-headings (I, II ...) in order. Repealed articles are removed.",
    "Código Civil text: two paragraphs cut by a column break right after 'Art.' (arts. 845 and 907) are joined; one space the text layer puts inside a word ('presumir á', Ley Reformatoria 2015, art. 223) is closed up.",
]

AI_USE = [
    "Código Civil: no generative model wrote legal text. The amendment map in civil/replay.py (which provision each act changes, and the anchor phrases around its new text in the act's PDF) was written by an AI agent (Claude) from reading each act; the words themselves are cut from the gazette PDFs' text layers. No OCR was used.",
]


def sha_of(url: str) -> str:
    return hashlib.sha256(fetch.cached(url).read_bytes()).hexdigest()


def build_act() -> dict:
    units, src = base.base_units()
    first = {"from": "2005-06-24", "source_url": src, "sha256": sha_of(src),
             "units": dict(sorted(units.items(), key=lambda kv: replay.order(kv[0]))), "credits": {}}
    return {"slug": "codigo-civil", "short": "CC", "title": "Código Civil (Codificación 2005-010)", "url": src,
            "first_law": None, "earlier_laws": [BASE_LAW], "versions": [first] + replay.replay(units)}


def laws() -> dict:
    out = {}
    for key, law in list(EXTRA_LAWS.items()) + list(replay.LAWS.items()):
        out[key] = {"label": law["label"], "title": law["title"], "kind": law["kind"], "enacted": law.get("enacted"),
                    "published": law["published"], "url": law["url"], "temporary_until": None, "restores": None,
                    "note": law.get("note")}
    return out


def sources(act: dict) -> list[dict]:
    urls = sorted({v["source_url"] for v in act["versions"]})
    return [
        {"name": "Registro Oficial del Ecuador (Código Civil and its amending acts)", "url": "https://www.registroficial.gob.ec",
         "retrieved": RETRIEVED, "requests": len(urls),
         "licence": "No licence stated on the site; official gazette text.",
         "notes": "One PDF per gazette edition, served by esacc.corteconstitucional.gob.ec, found through the site's month "
                  "listings. Every version's wording is cut from the text layer of the 2005 codification and of each "
                  "amending act; editions without a text layer are listed in decisions and not applied."},
        {"name": "Ediciones Legales consolidation of the Código Civil (gob.ec)", "url": "https://www.gob.ec/regulaciones/codigo-civil-codificacion-no-2005-010",
         "retrieved": RETRIEVED, "requests": 2, "licence": "All rights reserved (Ediciones Legales); read only, nothing copied.",
         "notes": "Index of amending acts and reading-only comparison of today's text (civil/reconcile_civil.py). Last reform it names: Segundo Suplemento 61, 17-VI-2025."},
        {"name": "Lexis consolidation of the Código Civil, 12-IV-2017 (WIPO Lex)", "url": "https://www.wipo.int/wipolex/en/legislation/details/18926",
         "retrieved": RETRIEVED, "requests": 1, "licence": "Lexis copyright; read only, nothing copied.",
         "notes": "Index of amending acts 2005-2017 ('Nota:' lines) and reading-only comparison."},
    ]


def main() -> None:
    act = build_act()
    part = {"laws": laws(), "acts": [act], "sources": sources(act), "applies": [], "decisions": DECISIONS, "ai_use": AI_USE}
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
