"""Law and act metadata for the Bolivia corpus, typed by hand from the official sources named next to each value.

parse.py imports this as `M`. Nothing here is legal text: it is labels, dates, URLs and the decisions made.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
CACHE = HERE / ".cache"

# ------------------------------------------------------------------ the Constitution (CPE 2009)

# Gaceta Oficial "texto de consulta" PDF, read through a pinned Internet Archive raw capture (the live site times out
# from the build machine). Header "07 de febrero de 2009"; no preamble.
CPE_GACETA = ("https://web.archive.org/web/20261006172245id_/"
              "http://www.gacetaoficialdebolivia.gob.bo/app/webroot/archivos/CONSTITUCION.pdf")
CPE_GACETA_PAGE = "http://www.gacetaoficialdebolivia.gob.bo/app/webroot/archivos/CONSTITUCION.pdf"
# Tribunal Constitucional Plurinacional edition (2023; "Autorización y publicación oficial: Ministerio de la
# Presidencia a través de la Gaceta Oficial"): used for the preamble and to cross-check every article.
CPE_TCP = "https://tcpbolivia.bo/wp-content/uploads/2025/04/CPE_2009.pdf"
# Cámara de Diputados edition (2025): second cross-check of every article and of the preamble.
CPE_DIPUTADOS = "https://diputados.gob.bo/wp-content/uploads/2025/11/constitucion_politica.pdf"

# Rulings and reports that describe events which changed no words of the CPE.
SCP_1010_2023 = "https://procuraduria.gob.bo/ckfinder/userfiles/files/PGE-WEB/_Opinion/ant/SENTENCIA10102023S4.pdf"
CIDH_121_24 = ("https://www.procuraduria.gob.bo/ckfinder/userfiles/files/PGE-WEB/_Subs/Sub1/03_Sistema_Interamericano/"
               "inadm/iad_121_24.pdf")

CPE_NOTE = ("Articles and the transitional, abrogating and final provisions are from the Gaceta Oficial's text; the "
            "preamble, which that text omits, is from the Tribunal Constitucional Plurinacional's edition and is "
            "identical in the Cámara de Diputados edition. The Constitution's words have not been amended since 2009.")

COUNTRY = {
    "code": "BO",
    "name": "Bolivia",
    "slug": "bolivia",
    "lang": "es",
    "tz": "America/La_Paz",
    "future_branch": "futuro",
    "publisher": {"name": "Gaceta Oficial del Estado Plurinacional de Bolivia",
                  "email": "gaceta@gacetaoficialdebolivia.invalid"},
    "default_in_force_rule": {
        "text": ('Constitución Política del Estado art. 164.II: "La ley será de cumplimiento obligatorio desde el día '
                 'de su publicación, salvo que en ella se establezca un plazo diferente para su entrada en vigencia." '
                 "(art. 164.I: the law is published in the Gaceta Oficial immediately after promulgation). A law's "
                 "own vigencia clause overrides this."),
        "source": CPE_GACETA_PAGE,
    },
    "licence_note": "Fuente: Gaceta Oficial del Estado Plurinacional de Bolivia (texto de consulta); "
                    "Tribunal Constitucional Plurinacional; Cámara de Diputados.",
}

# Source groups for the `sources` table: (name, url, host test, licence, notes)
_SOURCES = [
    ("Gaceta Oficial del Estado Plurinacional de Bolivia (Internet Archive raw captures)",
     "https://www.gacetaoficialdebolivia.gob.bo",
     lambda u: "gacetaoficialdebolivia" in u,
     "Marked \"TEXTO DE CONSULTA\" and \"Derechos Reservados © Gaceta Oficial de Bolivia\"; no open licence stated.",
     "The live site times out from the build machine; captures are pinned by timestamp in the URLs."),
    ("Tribunal Constitucional Plurinacional", "https://tcpbolivia.bo",
     lambda u: "tcpbolivia.bo" in u, "No licence stated.",
     "Official 2023 edition of the CPE (cross-check and preamble); lists of norms declared unconstitutional."),
    ("Cámara de Diputados", "https://diputados.gob.bo",
     lambda u: "diputados.gob.bo" in u, "No licence stated.", "2025 edition of the CPE (cross-check)."),
    ("Procuraduría General del Estado", "https://www.procuraduria.gob.bo",
     lambda u: "procuraduria.gob.bo" in u, "No licence stated.",
     "Hosts SCP 1010/2023-S4 and CIDH Informe 121/24, the sources for the no-words-changed events on the CPE."),
    ("Other official sites probed (Presidencia, Órgano Judicial, SEPDEP, Senado, SILEP, OEP)",
     "https://www.presidencia.gob.bo",
     lambda u: any(h in u for h in ("presidencia.gob.bo", "organojudicial", "sepdep", "senado", "silep", "oep.org")),
     "No licence stated.", "No usable consolidated text; Senado and SILEP did not resolve, OEP reset TLS."),
]


def sources() -> list[dict]:
    rows = [json.loads(l) for l in (CACHE / "requests.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    out = []
    for name, url, test, lic, notes in _SOURCES:
        hits = [r for r in rows if test(urlparse(r["url"]).netloc + urlparse(r["url"]).path)]
        if not hits:
            continue
        out.append({"name": name, "url": url, "retrieved": max(r["t"][:10] for r in hits), "requests": len(hits),
                    "licence": lic, "notes": notes})
    return out


# ------------------------------------------------------------------ laws

LAWS = {
    "cpe-2009": {
        "label": "CPE 2009",
        "title": "Constitución Política del Estado (aprobada en referendo de 25 de enero de 2009, promulgada el 7 de "
                 "febrero de 2009)",
        "kind": "referendum",
        "enacted": "2009-02-07",
        "published": "2009-02-07",
        "url": CPE_GACETA_PAGE,
        "temporary_until": None,
        "restores": None,
        "note": None,
    },
    "referendo-2016": {
        "label": "Referendo constitucional 2016",
        "title": "Referendo constitucional aprobatorio de 21 de febrero de 2016 (reforma del artículo 168)",
        "kind": "referendum",
        "enacted": "2016-02-21",
        "published": None,
        "url": CIDH_121_24,
        "temporary_until": None,
        "restores": None,
        "note": ("A referendum on a partial reform of art. 168 that would have allowed the President and Vice "
                 "President two consecutive re-elections. The reform was rejected (\"No\" won), so no words changed."),
    },
    "scp-0084-2017": {
        "label": "SCP 0084/2017",
        "title": "Sentencia Constitucional Plurinacional 0084/2017 de 28 de noviembre (acción de inconstitucionalidad "
                 "abstracta)",
        "kind": "court",
        "enacted": "2017-11-28",
        "published": None,
        "url": SCP_1010_2023,
        "temporary_until": None,
        "restores": None,
        "note": ("Declared the preferential application of art. 23 of the American Convention on Human Rights over "
                 "the re-election limits in arts. 156, 168, 285.II and 288 and struck the matching limits out of Ley "
                 "026 (Régimen Electoral). It changed no words of the Constitution: SCP 1010/2023-S4 records that the "
                 "declaration had no derogating effect on them."),
    },
    "scp-1010-2023-s4": {
        "label": "SCP 1010/2023-S4",
        "title": "Sentencia Constitucional Plurinacional 1010/2023-S4 de 28 de diciembre (Sala Cuarta Especializada, "
                 "acción de amparo constitucional)",
        "kind": "court",
        "enacted": "2023-12-28",
        "published": None,
        "url": SCP_1010_2023,
        "temporary_until": None,
        "restores": None,
        "note": ("Held, following Inter-American Court Advisory Opinion OC-28/21, that art. 23 of the American "
                 "Convention is not contrary to the re-election limit of art. 168 (and the identical rule of art. 156), "
                 "reversing the line of SCP 0084/2017. It changed no words of the Constitution."),
    },
}

# No-words-changed events on the CPE: (law, day, provisions). Each becomes a version with the same text.
CPE_EVENTS = [
    ("referendo-2016", "2016-02-21", ["art-168"]),
    ("scp-0084-2017", "2017-11-28", ["art-156", "art-168", "art-285", "art-288"]),
    ("scp-1010-2023-s4", "2023-12-28", ["art-156", "art-168"]),
]

DECISIONS = [
    "The Constitution's articles and transitional, abrogating and final provisions are taken from the Gaceta Oficial's "
    "texto de consulta (pinned Internet Archive capture of 6 October 2026), because the Gaceta is the official journal.",
    "The Gaceta text has no preamble, so the preamble is taken from the Tribunal Constitucional Plurinacional's 2023 "
    "edition; parse.py stops unless it equals the Cámara de Diputados edition ignoring whitespace.",
    "Every article of the Gaceta text is compared, ignoring whitespace, case and quote/dash style, with the TCP and "
    "Diputados editions; the result is in crosscheck.json and verification notes in PROGRESS.md.",
    "The Constitution is one version as enacted, in force 7 February 2009 under its disposición final (in force on "
    "publication in the Gaceta Oficial) and credited to its approving referendum of 25 January 2009 as promulgated.",
    "The Constitution's words have not been amended since 2009, so the three later events (the rejected 2016 "
    "referendum, SCP 0084/2017 and SCP 1010/2023-S4) are recorded as versions with identical text, each credited to "
    "the provisions it concerns so that it gets a commit marked Words-changed: no; their dates are the vote and the "
    "decision dates.",
    "The facts of those events are taken only from SCP 1010/2023-S4 and CIDH Informe 121/24, both hosted by the "
    "Procuraduría General del Estado; vote counts and the number of the reform law are not stated because no "
    "official source for them was read.",
    "Headings (Parte, Título, Capítulo, Sección) are kept in one structure file, estructura.md, with the first article "
    "under each, so that article files hold only article text.",
    "Typesetting is normalised once: ligature glyphs from the TCP PDF, NBSP, soft hyphens, quote and dash styles; "
    "page numbers and running headers are dropped.",
]

AI_USE = [
    "none: no model wrote, summarised or corrected legal text. The parser and this metadata were written with a "
    "coding assistant (Claude) and every value was read from the official sources named.",
]
