"""Build Nigeria's corpus from the cache only: corpus.json (country + Data Protection Act) and two parts in corpus.d/.

    python -X utf8 scripts/nigeria-law/parse.py

Reads sources.json (pins written by fetch.py) and the cached PDFs, through gazette.py (the Federal Government Printer
text-layer reader; no OCR). Writes, atomically:
- corpus.json: the country, the Nigeria Data Protection Act, 2023 (verified: PUBLISH);
- corpus.d/10-constitution.json: the Constitution of 1999 as promulgated (not today's text: no PUBLISH);
- corpus.d/20-companies.json: the Companies and Allied Matters Act, 2020 as enacted (amended since: no PUBLISH);
- verification.json: the checks; repo/README.md and repo/LICENSE.
Deterministic: the same cache gives the same bytes.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gazette as g  # noqa: E402

RETRIEVED = "2026-10-28"
PINS = json.loads((HERE / "sources.json").read_text(encoding="utf-8"))["sources"]

STRUCT_CONSTITUTION = re.compile(r"^(?:PART|CHAPTER)\b|^(?:Part|Chapter) [0-9IVXLC]+[A-Z]?\s*[—-]|^[A-H]\.?\s?—\s?[A-Z][a-z]")

ACTS = {
    "data-protection": {
        "pages": (0, None), "head_max_y": 148, "start": r"^ENACTED by", "stop": r"^I,? certify|^EXPLANATORY MEMORANDUM",
        "schedule": r"^SCHEDULE\b", "schedule_pages_from": None, "structure": None, "renumber": None,
    },
    "companies": {
        "pages": (32, 526), "head_max_y": 148, "start": r"^ENACTED by", "stop": r"^I,? certify|^EXPLANATORY MEMORANDUM",
        "schedule": r"^(?:[A-Z]+ )?SCHEDULE\b(?!S)", "schedule_pages_from": None, "structure": None, "renumber": None,
    },
    "constitution": {
        # pages 12-171: from "We the People" to the Seventh Schedule; the Promulgation Act (pages 4-5) and the three
        # Alteration Act gazettes (pages 172-208) are not part of the Constitution's text.
        "pages": (12, 171), "head_max_y": 185, "start": None, "stop": None,
        "schedule": r"^(?:[A-Z]+ +)?SCHEDULE(?!S)\b", "schedule_pages_from": 136, "structure": STRUCT_CONSTITUTION,
        # the print numbers section 281 "285" (sections 280, 285, 282, 283, 284, 285 follow one another)
        "renumber": {"285.—(1) The appointment of a person to the office of President of a": "281"},
    },
}


def pdf_path(key: str) -> Path:
    return HERE / ".cache" / hashlib.sha256(PINS[key]["url"].encode("utf-8")).hexdigest()


def notes_into_body(pg: g.Page, page: int) -> None:
    """On schedule pages the margin holds table cells, item numbers and paragraph headings, not section headings:
    each becomes body text at its own height (an item number joins the line it stands beside)."""
    for y, t in pg.notes:
        same = [l for l in pg.body if abs(l.y0 - y) < 3]
        if same and re.fullmatch(r"\d{1,3}\.|Item", t):
            same[0].text = t + " " + same[0].text
        else:
            pg.body.append(g.Line(page, 99.0, y, 100.0, t))
    pg.body.sort(key=lambda l: l.y0)
    pg.notes = []


def read_act(slug: str) -> tuple[dict, dict]:
    import fitz  # PyMuPDF  # noqa: PLC0415
    cfg = ACTS[slug]
    doc = fitz.open(pdf_path(slug))
    first, last = cfg["pages"]
    last = len(doc) - 1 if last is None else last
    pages = g.read_pages(doc, first, last, head_max_y=cfg["head_max_y"])
    no_text = [i for i, p in pages.items() if p.chars == 0]
    # words of the body text (before any side note is moved into it), for rejoining side notes broken at a line end
    body = " ".join(l.text for p in pages.values() for l in p.body)
    vocab = set(re.findall(r"[a-z]+", body.lower()))
    hyph = set(re.findall(r"[a-z]+-[a-z]+", body.lower()))
    if cfg["schedule_pages_from"] is not None:
        for i, p in pages.items():
            if i >= cfg["schedule_pages_from"]:
                notes_into_body(p, i)
    rx = (lambda s: re.compile(s) if s else None)
    units, rep = g.split_units(pages, rx(cfg["start"]), rx(cfg["stop"]), rx(cfg["schedule"]),
                               preamble_key="preamble" if slug == "constitution" else None,
                               structure_rx=cfg["structure"], renumber=cfg["renumber"])
    out: dict = {}
    headings = []
    sch_names = {}
    for u in units:
        if u.heading and u.kind == "sec":
            u.heading = g.dehyphen(u.heading, vocab, hyph)
            headings.append(u.heading)
        if u.kind == "schedule":
            name = re.match(r"^((?:[A-Z]+ +)?SCHEDULE)", u.heading).group(1)
            name = re.sub(r"\s+", " ", name).title()
            sch_names[u.key] = name
            u.label = name
        text = g.unit_text(u)
        text = re.sub(r" {2,}", " ", text)
        out[u.key] = {"label": u.label, "kind": {"sec": "sec", "schedule": "schedule", "preamble": "preamble"}[u.kind],
                      "text": text}
    secs = [k for k in out if k.startswith("sec-")]
    # every side note not used as a section heading is listed (cross-references such as "Cap. 192 LFN.")
    used = set(headings)
    unused = [t for i, p in sorted(pages.items()) for _, t in p.notes if g.dehyphen(t, vocab, hyph) not in used]
    dup = sorted({h for h in headings if headings.count(h) > 1})
    # fidelity: every word of the enacted text as printed is in a provision file (its body, a section's number, a
    # schedule's heading line), in a Part/Chapter heading left out, or in a dropped line; and nothing else is
    import collections  # noqa: PLC0415
    printed = collections.Counter(rep["words"])
    ours = collections.Counter()
    for k, uu in out.items():
        head, _, rest = uu["text"].partition("\n")
        ours.update(re.findall(r"\w+", rest))
        if k.startswith("sch-"):
            ours.update(re.findall(r"\w+", head))
        elif k.startswith("sec-"):
            ours.update([re.sub(r"^0+", "", k[4:7]) + k[8:].upper()])
    for t in rep["structure_lines"] + rep["dropped"]:
        ours.update(re.findall(r"\w+", t))
    seq_words, unit_words = sum(printed.values()), sum(ours.values())
    missing = sorted((printed - ours).items())
    extra = sorted((ours - printed).items())
    report = {"pages": [first, last], "pages_without_text": no_text, "units": len(out), "sections": len(secs),
              "first_section": secs[0] if secs else None, "last_section": secs[-1] if secs else None,
              "schedules": sch_names, "sections_without_heading": rep["no_heading"],
              "orphan_lines": rep["orphans"], "renumbered": rep["renumbered"],
              "headings_used_twice": dup, "side_notes_not_headings": unused,
              "structure_lines": len(rep["structure_lines"]), "dropped_lines": rep["dropped"],
              "words_printed": seq_words, "words_kept": unit_words,
              "words_missing": missing, "words_added": extra}
    return out, report


def source_entry(key: str, name: str, notes: str) -> dict:
    p = PINS[key]
    return {"name": name, "url": p["original"], "retrieved": RETRIEVED, "requests": 1,
            "licence": "Federal Republic of Nigeria legislation as printed by the Federal Government Printer; the "
                       "source states no licence. The repository is private.",
            "notes": notes + (f" Read from the Internet Archive's raw capture {p['capture']} ({p['url']})."
                              if p["via"] == "wayback" else f" Read directly from {p['url']}.")
                     + f" sha256 {p['sha256']}, {p['bytes']} bytes, {p['pages']} pages, text layer (no OCR)."}


def law(label, title, kind, enacted, published, url, note=None) -> dict:
    return {"label": label, "title": title, "kind": kind, "enacted": enacted, "published": published, "url": url,
            "temporary_until": None, "restores": None, "note": note}


COUNTRY = {
    "code": "NG", "name": "Nigeria", "slug": "nigeria", "lang": "en", "tz": "Africa/Lagos", "future_branch": "future",
    "publisher": {"name": "Federal Government Printer (Nigeria)", "email": "fgp@federal-government-printer.invalid"},
    "default_in_force_rule": {
        "text": "Not applied: each Act's version is dated by the commencement date printed under its long title in "
                "the Federal Government Printer's gazette (\"[12th Day of June, 2023]\", \"[7th Day of August, "
                "2020]\"), and the Constitution by section 1(2) of the Constitution of the Federal Republic of Nigeria "
                "(Promulgation) Act (\"shall come into force on 29 May 1999\"). No date is computed from a default rule.",
        "source": "https://ncc.gov.ng/media/801/view"},
    "licence_note": "Texts: Federal Republic of Nigeria Official Gazette supplements printed and published by the "
                    "Federal Government Printer, Lagos, and the Federal Ministry of Justice's print of the Constitution "
                    "of the Federal Republic of Nigeria, 1999. No licence is stated on these copies.",
}

AI_USE = ["Claude Code (Claude Opus 5.5, claude-opus-5-5) wrote fetch.py, get.py, gazette.py and parse.py and chose "
          "the sources. No model wrote, summarised or transformed legal text: parse.py is deterministic code reading "
          "the PDFs' text layer."]

COMMON_DECISIONS = [
    "Nigeria: NigeriaLII (nigerialii.org) lists no legislation (its /legislation/ page showed 0 documents on "
    "2026-10-28, and every archived /akn/ng/act/ page is a 404), so no point-in-time versions exist online; each act "
    "is read from a Federal Government Printer text with a text layer, one version per printed text.",
    "Text: read from each PDF's text layer by position (gazette.py): side notes give the section headings, paragraphs "
    "are rebuilt from the typesetting, and Part and Chapter headings are left out (each provision file starts with its "
    "number and heading). The printer's space before ';', ':' and ',' is removed, curly quotes become straight quotes, "
    "and line-end hyphens in side notes are rejoined only where the joined word occurs in the body text. Spelling "
    "errors in the prints are kept as printed.",
    "Side notes that are not section headings (cross-references such as \"Cap. I24, LFN, 2004.\" or \"Third "
    "Schedule.\") are the printer's annotations and are left out; verification.json lists every one. parse.py checks "
    "each act word for word: every word of the enacted text as printed is in a provision file, in a Part or Chapter "
    "heading, and nothing is added (verification.json, words_missing and words_added).",
]


def write_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def main() -> None:
    verification = {}

    # ---------------------------------------------------------------- Nigeria Data Protection Act, 2023
    u, r = read_act("data-protection")
    verification["data-protection"] = r
    ndpa = {"slug": "data-protection", "short": "NDPA 2023", "title": "Nigeria Data Protection Act, 2023",
            "url": PINS["data-protection"]["original"], "first_law": "act-2023-37", "earlier_laws": [],
            "versions": [{"from": "2023-06-12", "source_url": PINS["data-protection"]["url"],
                          "sha256": PINS["data-protection"]["sha256"], "units": u,
                          "note": "The Act as enacted (Act No. 37 of 2023), from the Federal Government Printer's "
                                  "Official Gazette No. 119, Vol. 110, of 1 July 2023; in force from 12 June 2023, the "
                                  "commencement date printed under its long title."}]}
    corpus = {
        "country": COUNTRY,
        "sources": [source_entry("data-protection",
                                 "Federal Government Printer: Nigeria Data Protection Act, 2023 (Official Gazette No. 119, Vol. 110, 1 July 2023)",
                                 "Act No. 37 of 2023 as gazetted, served by the Nigerian Communications Commission (ncc.gov.ng).")],
        "laws": {"act-2023-37": law("Act No. 37 of 2023", "Nigeria Data Protection Act, 2023", "law", "2023-06-12",
                                    "2023-07-01", PINS["data-protection"]["original"])},
        "acts": [ndpa],
        "applies": [],
        "decisions": COMMON_DECISIONS + [
            "NDPA 2023: one version, the Act as enacted, dated 12 June 2023 (\"[12th Day of June, 2023]\" under the long "
            "title; the President's assent is dated the same day). The gazette's running head reads \"2022 No. 37\" "
            "on some pages; the Act is Act No. 37 of 2023 as its cover and title say.",
            "NDPA 2023: no amending Act was found in any source consulted (NigeriaLII, the National Assembly's Acts "
            "list, the Federal Ministry of Justice's media library), so the enacted text is taken as today's text.",
            "NDPA 2023: the gazette's Schedule (Section 8(3), supplementary provisions on the Council) is one file, "
            "sch-01; the gazette's back matter (the clerk's certificate, the explanatory memorandum and the schedule "
            "of the Bill's passage) is not law and is left out.",
        ],
        "ai_use": AI_USE,
    }

    # ---------------------------------------------------------------- Companies and Allied Matters Act, 2020
    u, r = read_act("companies")
    verification["companies"] = r
    cama = {"slug": "companies", "short": "CAMA 2020", "title": "Companies and Allied Matters Act, 2020",
            "url": PINS["companies"]["original"], "first_law": "act-2020-3", "earlier_laws": [],
            "versions": [{"from": "2020-08-07", "source_url": PINS["companies"]["url"],
                          "sha256": PINS["companies"]["sha256"], "units": u,
                          "note": "The Act as enacted (Act No. 3 of 2020), from the Federal Government Printer's "
                                  "Official Gazette No. 124, Vol. 107, of 10 August 2020; in force from 7 August 2020, "
                                  "the commencement date printed under its long title. Later amendments are not in "
                                  "this history (see the README)."}]}
    part_cama = {
        "sources": [source_entry("companies",
                                 "Federal Government Printer: Companies and Allied Matters Act, 2020 (Official Gazette No. 124, Vol. 107, 10 August 2020)",
                                 "Act No. 3 of 2020 as gazetted, published by the Corporate Affairs Commission (pre.cac.gov.ng).")],
        "laws": {"act-2020-3": law("Act No. 3 of 2020", "Companies and Allied Matters Act, 2020", "law", "2020-08-07",
                                   "2020-08-10", PINS["companies"]["original"])},
        "acts": [cama],
        "decisions": [
            "CAMA 2020: one version, the Act as enacted, dated 7 August 2020 (\"[7th Day of August, 2020]\" under the "
            "long title; the President's assent is dated the same day).",
            "CAMA 2020: the Business Facilitation (Miscellaneous Provisions) Act, 2022 (in force February 2023) "
            "amended the Act (among others sections 127, 142, 149 and 868, as commentators report); no Federal "
            "Government Printer text of it with a text layer was found, so it is not applied. The last version is "
            "therefore not today's text, and this part is not verified (no PUBLISH).",
            "CAMA 2020: the fifteen Schedules are one file each (sch-01 to sch-15); forms and tables in them are read "
            "line by line as printed, without their table layout.",
        ],
    }

    # ---------------------------------------------------------------- Constitution of 1999
    u, r = read_act("constitution")
    verification["constitution"] = r
    const = {"slug": "constitution", "short": "Constitution", "title": "Constitution of the Federal Republic of Nigeria, 1999",
             "url": PINS["constitution"]["original"], "first_law": "promulgation-1999-24",
             "earlier_laws": [],
             "versions": [{"from": "1999-05-29", "source_url": PINS["constitution"]["url"],
                           "sha256": PINS["constitution"]["sha256"], "units": u,
                           "note": "The Constitution as promulgated, in force from 29 May 1999 (section 1(2) of the "
                                   "Promulgation Act). Text: the body of the Federal Ministry of Justice's print. None "
                                   "of the Alteration Acts (2010, 2011, 2017-2018, 2023) is applied."}]}
    part_const = {
        "sources": [source_entry("constitution",
                                 "Federal Ministry of Justice: Constitution of the Federal Republic of Nigeria, 1999 [With the First, Second and Third Alterations]",
                                 "The Ministry's print (foreword by the Attorney-General of the Federation, Mohammed Bello Adoke): the Promulgation Act, the Constitution, and the Federal Government Printer gazettes of the First, Second and Third Alteration Acts.")],
        "laws": {
            "promulgation-1999-24": law(
                "Act No. 24 of 1999", "Constitution of the Federal Republic of Nigeria (Promulgation) Act", "decree",
                "1999-05-05", None, PINS["constitution"]["original"],
                note="The Provisional Ruling Council promulgates the Constitution set out in the Schedule, in force "
                     "on 29 May 1999 (section 1(2)); the print dates the Act \"[5th May, 1999]\"."),
        },
        "acts": [const],
        "decisions": [
            "Constitution: the Federal Ministry of Justice's print is titled \"[With the First, Second and Third "
            "Alterations]\", and its foreword says the Federal Government Printer was directed to print the "
            "Constitution as altered. Its body is not altered: it still has, for example, \"the 1991 census\" in "
            "section 75 (deleted by the First Alteration Act), section 66(1)(h) (deleted by the same Act), no section "
            "254A to 254F (inserted by the Third Alteration Act) and the Sixth Schedule's tribunals of \"a Chairman and "
            "four other members\" (replaced by the Second Alteration Act). The three Alteration Acts follow it only as "
            "gazettes. So the body is read as the Constitution as promulgated, in force from 29 May 1999, credited to "
            "the Promulgation Act (Act No. 24 of 1999, as the print styles it).",
            "Constitution: not applied, so missing from this history: the First Alteration Act, 2010 (Act No. 1, "
            "\"[16th July, 2010]\", assent 10 January 2011, Official Gazette No. 2 of 11 January 2011), the Second "
            "Alteration Act, 2010 (Act No. 2, \"[29th November, 2010]\", assent 10 January 2011, Gazette No. 3 of 12 "
            "January 2011), the Third Alteration Act, 2010 (Act No. 3, \"[4th Day of March, 2011]\", Gazette No. 20 of "
            "7 March 2011), all three printed in the same PDF and replayable; and the Fourth Alteration Acts "
            "(2017-2018) and Fifth Alteration Acts (2023), for which no official text-layer source was found. The last "
            "version is therefore not today's text, and this part is not verified (no PUBLISH).",
            "Constitution: the print numbers section 281 as \"285\" (sections 280, \"285\", 282, 283, 284 and 285 "
            "follow one another, and the Arrangement of Sections lists 281); it is filed as sec-281, and its heading "
            "line reads 281. Nothing else is renumbered. Section 267 has no side note in the print, so its file starts "
            "\"# Section 267\" with no heading.",
            "Constitution: the Promulgation Act's own text and the print's foreword and Arrangement of Sections are "
            "left out; the Preamble (\"We the People ...\", spaced \"We the P eople\" in the print and kept so), the 320 "
            "sections and the seven Schedules are in the provision files. On the Schedule pages the margin holds table "
            "cells (capital cities), item numbers and paragraph headings: each is kept as a line of the Schedule at its "
            "own height (item numbers joined to their item). The First Schedule's table of States and Local Government "
            "Areas is read row by row as printed, without its table layout.",
        ],
    }

    write_atomic(HERE / "corpus.json", corpus)
    write_atomic(HERE / "corpus.d" / "10-constitution.json", part_const)
    write_atomic(HERE / "corpus.d" / "20-companies.json", part_cama)
    write_atomic(HERE / "verification.json", verification)
    print(json.dumps({k: {x: v[x] for x in ("units", "sections", "last_section", "sections_without_heading",
                                             "orphan_lines", "words_printed", "words_kept", "words_missing", "words_added")}
                      for k, v in verification.items()}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
