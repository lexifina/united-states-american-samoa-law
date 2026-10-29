"""Write corpus.d/60-coip.json: the Código Orgánico Integral Penal (2014) and its amending acts.

Reads only the cache (fetch with coip/fetch_coip.py). Deterministic: the same cache gives the same bytes. The part is
written atomically (.tmp, then rename). Versions after the first are stored as deltas (`changes`).

    python -X utf8 coip/parse_coip.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import coip_base  # noqa: E402
import coip_replay as R  # noqa: E402
import index_el2026  # noqa: E402

OUT = Path(os.environ.get("COIP_OUT", HERE.parent / "corpus.d" / "60-coip.json"))
RETRIEVED = "2026-10-28"
BASE_LAW = "coip-2014"
IN_FORCE = R.plazo_days("2014-02-10", 180)  # 2014-08-10

BASE_LAWS = {
    BASE_LAW: dict(label="Código Orgánico Integral Penal (2014)", kind="law", enacted="2014-01-28",
                   published="2014-02-10", url=coip_base.S180_2014,
                   title="Código Orgánico Integral Penal (Asamblea Nacional; Registro Oficial, Suplemento 180, "
                         "10-II-2014)"),
}

DECISIONS = [
    "COIP: the first version is the Code as enacted, from the text layer of Registro Oficial Suplemento 180 "
    "(10-II-2014). Its Disposición final puts it in force 'en ciento ochenta días contados a partir de su publicación'. "
    "Código Civil art. 33 counts plazos in complete days running to midnight of the last day, the publication day not "
    "counted, so the Code binds from 10 August 2014, the day generally given for its entry into force. The same rule "
    "dates every later act with a plazo in days.",
    "COIP: the Code's Disposiciones reformatorias amending the Código Orgánico de la Función Judicial took effect on "
    "publication; they change another law, not the Code's own provisions, and are kept as units of the Code as "
    "enacted (disp-reformatoria-NN) with the rest of its text, from 10 August 2014.",
    "COIP: every later version replays an amending act's own Registro Oficial text (pymupdf text layer) on the version "
    "before it, in order of entry into force (coip/coip_replay.py, using civil/replay.py's gazette cutting). Quoted "
    "replacement text is cut from the act's PDF after an anchor phrase; every short phrase an act inserts is checked to "
    "occur word for word in the act's PDF.",
    "COIP anachronism rule: a version in force on day D carries wording only from acts published on or before D, each "
    "act applied on its own in-force day; parse_coip.py stops if any version breaks it.",
    "COIP: the Fe de erratas of Segundo Suplemento 224 (11-IV-2014) corrects the dates of the second debate in the "
    "Asamblea's certification printed before the Code; the certification is not part of the Code's units, so it "
    "changes nothing here.",
    "COIP: interpretative or binding-precedent resolutions of the Corte Nacional de Justicia and drug-quantity tables "
    "of the CONSEP (cited by editorial notes) change no words and are not versions.",
    "COIP: general renaming clauses that name no article (COGEP Disposición reformatoria primera: 'Código de "
    "Procedimiento Civil' -> 'Código Orgánico General de Procesos') are not applied to the text.",
    "COIP units: art-NNN for each article (articles added later keep their place: art-208-a for 'Artículo 208 A', "
    "art-028-1 for 'Art. 28.1'); disp-general-NN, disp-transitoria-NN, disp-reformatoria-NN, disp-derogatoria-NN, "
    "disp-final; 'titulos' holds the Libro, Título, Capítulo, Sección and Parágrafo headings in order.",
]

AI_USE = [
    "COIP: no generative model wrote legal text. The amendment map in coip/coip_replay.py (which provision each act "
    "changes, and the anchor phrases around its new text in the act's PDF) was written by an AI agent (Claude) from "
    "reading each act; the words themselves are cut from the gazette PDFs' text layers. No OCR was used.",
]


def build_act() -> dict:
    units = coip_base.first_version()
    first = {"from": IN_FORCE, "source_url": coip_base.S180_2014, "sha256": R.sha_of(coip_base.S180_2014),
             "units": dict(sorted(units.items(), key=lambda kv: R.order(kv[0]))), "credits": {}}
    return {"slug": "coip", "short": "COIP", "title": "Código Orgánico Integral Penal", "url": coip_base.S180_2014,
            "first_law": BASE_LAW, "earlier_laws": [], "versions": [first] + R.replay(units)}


def laws() -> dict:
    out = {}
    for key, law in list(BASE_LAWS.items()) + list(R.LAWS.items()):
        out[key] = {"label": law["label"], "title": law["title"], "kind": law["kind"], "enacted": law.get("enacted"),
                    "published": law["published"], "url": law["url"], "temporary_until": None,
                    "restores": law.get("restores"), "note": law.get("note")}
    return out


def sources(act: dict) -> list[dict]:
    urls = sorted({v["source_url"] for v in act["versions"]})
    return [
        {"name": "Registro Oficial del Ecuador (COIP and its amending acts)", "url": "https://www.registroficial.gob.ec",
         "retrieved": RETRIEVED, "requests": len(urls),
         "licence": "No licence stated on the site; official gazette text.",
         "notes": "One PDF per gazette edition, served by esacc.corteconstitucional.gob.ec, found through the site's "
                  "month listings (coip/find_editions.py). Every version's wording is cut from the text layer of the "
                  "2014 Code and of each amending act; editions without a text layer are listed in decisions and not "
                  "applied."},
        {"name": "Ediciones Legales consolidation of the COIP (Consejo de Comunicación repository, gob.ec)",
         "url": "https://repositorio.consejodecomunicacion.gob.ec/bitstream/CONSEJO_REP/250/1/COIP.pdf",
         "retrieved": RETRIEVED, "requests": 1,
         "licence": "All rights reserved (Ediciones Legales); read only, nothing copied.",
         "notes": "Index of amending acts to 13-X-2021 (coip/index_notes.py) and reading-only comparison."},
        {"name": "Lexis consolidation of the COIP (FAOLEX copy, last change 2023-03-08)",
         "url": "https://faolex.fao.org/docs/pdf/ecu204126.pdf", "retrieved": RETRIEVED, "requests": 1,
         "licence": "Lexis copyright; read only, nothing copied.",
         "notes": "Index of amending acts and rulings to 8-III-2023 (coip/index_lexis.py)."},
        {"name": "Ediciones Legales consolidation of the COIP (Servicio Nacional de Aduana copy, last reform 29-IV-2026)",
         "url": "https://www.aduana.gob.ec/wp-content/uploads/2026/05/CODIGO-ORGANICO-INTEGRAL-PENAL-COIP.pdf",
         "retrieved": RETRIEVED, "requests": 1,
         "licence": "All rights reserved (Ediciones Legales); read only, nothing copied.",
         "notes": "Index of amending acts and rulings of 2023 to 2026 (coip/index_el2026.py)."},
        {"name": "Andina Ediciones compilation of the COIP (legalcloud.ec copy, updated to 24-VIII-2026)",
         "url": index_el2026.ANDINA2026, "retrieved": RETRIEVED, "requests": 1,
         "licence": "All rights reserved (Andina Ediciones); read only, nothing copied.",
         "notes": "Index of amending acts from May to August 2026 (coip/index_el2026.py --andina)."},
        {"name": "Asamblea Nacional, leyes aprobadas (published in the Registro Oficial)",
         "url": "https://www.asambleanacional.gob.ec/es/leyes-aprobadas", "retrieved": RETRIEVED,
         "requests": 8 + len(screened()),
         "licence": "No licence stated; official site.",
         "notes": "List of laws with their Registro Oficial references (coip/index_asamblea.py); each law's edition "
                  "from 2023 on (the Asamblea's copy, the same bytes as the Registro Oficial's) was searched in its "
                  "text layer for reforms of the Code (coip/screen_laws.py, coip/screen.json)."},
    ]


def screened() -> dict:
    return json.loads((HERE / "screen.json").read_text(encoding="utf-8"))


def main() -> None:
    act = build_act()
    lw = laws()
    errs = R.check_anachronism(act["versions"], lw)
    if errs:
        raise SystemExit("anachronism:\n" + "\n".join(errs))
    part = {"laws": lw, "acts": [act], "sources": sources(act), "applies": [],
            "decisions": DECISIONS + R.DECISIONS, "ai_use": AI_USE}
    OUT.parent.mkdir(exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    data = json.dumps(part, ensure_ascii=False, indent=1) + "\n"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(data)
    os.replace(tmp, OUT)
    n = sum(len(v.get("changes", {})) for v in act["versions"][1:])
    print(f"{OUT.name}: {len(act['versions'])} versions, {len(lw)} laws, {n} unit changes, {len(data)} bytes")


if __name__ == "__main__":
    main()
