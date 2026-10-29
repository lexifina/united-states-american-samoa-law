"""Cameroon: reads only .cache/ and writes corpus.json (preview; not verified, no PUBLISH).

Phase 1 so far: the Constitution in French, one version (Loi 96/06 as amended by Loi 2008/001), from the
born-digital PDF the Chambre des comptes (Supreme Court Audit Bench) published, read through a pinned Wayback capture.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

import fitz  # pymupdf

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fetch  # noqa: E402

CONST_FR = ("https://web.archive.org/web/20240422094215id_/https://chambredescomptes.cm/rails/active_storage/disk/"
            "eyJfcmFpbHMiOnsibWVzc2FnZSI6IkJBaDdDVG9JYTJWNVNTSWhPV1IxWTJsbU0yRm9jSEZrTm5GMVkyeG5jV3hvY1hkbmFqVnFlZ1k2"
            "QmtWVU9oQmthWE53YjNOcGRHbHZia2tpVVdsdWJHbHVaVHNnWm1sc1pXNWhiV1U5SWt4aFgwTnZibk4wYVhSMWRHbHZiaTV3WkdZaU95"
            "Qm1hV3hsYm1GdFpTbzlWVlJHTFRnbkoweGhYME52Ym5OMGFYUjFkR2x2Ymk1d1pHWUdPd1pVT2hGamIyNTBaVzUwWDNSNWNHVkpJaFJo"
            "Y0hCc2FXTmhkR2x2Ymk5d1pHWUdPd1pVT2hGelpYSjJhV05sWDI1aGJXVTZDbXh2WTJGcyIsImV4cCI6IjIwMjQtMDQtMjJUMDk6NDc6"
            "MTUuMTc3WiIsInB1ciI6ImJsb2Jfa2V5In19--4c0d4390889e0a72ddcbc865ce5c7dd74796e817/La_Constitution.pdf")


def norm(s: str) -> str:
    s = s.replace(" ", " ").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("–", "-").replace("—", "-")
    return re.sub(r"[ \t]+", " ", s).strip()


def paragraphs(lines: list[str]) -> list[str]:
    out: list[str] = []
    for ln in lines:
        starts_new = (not out or re.match(r"^(\(\d+\)|\(\w\)|- |[a-z]\s?[-)]\s|\d+[°)-])", ln)
                      or out[-1].endswith((".", ";", ":")))
        if starts_new:
            out.append(ln)
        else:
            out[-1] = out[-1] + " " + ln
    return out


def const_fr() -> dict:
    raw = fetch.cached(CONST_FR)
    if raw is None:
        raise SystemExit("not cached: " + CONST_FR)
    doc = fitz.open(stream=raw, filetype="pdf")
    lines = []
    for page in doc:
        for ln in page.get_text().splitlines():
            ln = norm(ln)
            if not ln or re.fullmatch(r"\d{1,2}", ln):
                continue
            lines.append(ln)
    text = "\n".join(lines)
    i = text.index("PREAMBULE")
    body = text[i:].splitlines()
    units: dict[str, dict] = {}
    cur_key, cur_label, buf = "preambule", "Préambule", []
    heading = None

    def flush():
        if buf:
            paras = paragraphs(buf)
            units[cur_key] = {"label": cur_label, "kind": "preamble" if cur_key == "preambule" else "art",
                              "text": f"# {cur_label}\n" + "\n".join(paras) + "\n"}

    for ln in body[1:]:
        m = re.match(r"^ARTICLE\s+(\d+)(?:\s*(?:\(nouveau\)))?\s*:?\s*(.*)$", ln)
        if m:
            flush()
            n = int(m.group(1))
            cur_key, cur_label, buf = f"art-{n:03d}", f"Article {n}", []
            if m.group(2):
                buf.append(m.group(2))
            continue
        if re.match(r"^(TITRE|TITRE PREMIER)\b", ln):
            heading = ln
            continue
        buf.append(ln)
    flush()
    return {
        "slug": "constitution",
        "short": "Constitution",
        "title": "Constitution de la République du Cameroun (Loi n°96/06 du 18 janvier 1996 portant révision de la "
                 "Constitution du 02 juin 1972, modifiée et complétée par la loi n°2008/001 du 14 avril 2008)",
        "url": "https://www.prc.cm/en/cameroon/constitution",
        "first_law": None,
        "earlier_laws": ["loi-1996-06", "loi-2008-001"],
        "versions": [{
            "from": "2008-04-14",
            "source_url": CONST_FR,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "units": units,
            "credits": {},
            "note": ("Oldest version available as text: the 1996 text as amended by Loi 2008/001. Loi 2026/002 of "
                     "14 April 2026 (amending the Constitution) exists only as a scan and is NOT applied."),
        }],
    }


def main() -> None:
    corpus = {
        "country": {
            "code": "CM", "name": "Cameroon", "slug": "cameroon", "lang": "fr", "tz": "Africa/Douala",
            "future_branch": "future",
            "publisher": {"name": "Chambre des comptes de la Cour suprême du Cameroun (via Internet Archive)",
                          "email": "publisher@chambredescomptes.invalid"},
            "default_in_force_rule": {"text": "Not yet sourced: versions are dated by promulgation day (decision).",
                                      "source": "https://www.prc.cm/en/news/the-acts/laws"},
            "licence_note": "Official legislative text of the Republic of Cameroon; no licence stated by the publisher.",
        },
        "sources": [{"name": "Chambre des comptes, La_Constitution.pdf (Wayback 20240422094215)",
                     "url": CONST_FR, "retrieved": "2026-10-29", "requests": 1,
                     "licence": "none stated", "notes": "Born-digital PDF (Microsoft Word, 2015-05-26), 30 pages"}],
        "laws": {
            "loi-1996-06": {"label": "Loi n°96/06", "title": "Loi n°96/06 du 18 janvier 1996 portant révision de la "
                            "Constitution du 02 juin 1972", "kind": "law", "enacted": "1996-01-18",
                            "published": None, "url": None, "temporary_until": None, "restores": None, "note": None},
            "loi-2008-001": {"label": "Loi n°2008/001", "title": "Loi n°2008/001 du 14 avril 2008 modifiant et "
                             "complétant certaines dispositions de la loi n°96/06 du 18 janvier 1996",
                             "kind": "law", "enacted": "2008-04-14", "published": None,
                             "url": "https://www.prc.cm/en/multimedia/documents/6282-loi-n-2008-001-du-14-04-2008-modifian-constitution-1972-en",
                             "temporary_until": None, "restores": None, "note": None},
        },
        "acts": [const_fr()],
        "applies": [],
        "decisions": [
            "Every prc.cm text (Loi 96/06, Loi 2008/001, Loi 2026/002, Penal Code 2016, Loi 2019/020, Loi 2024/017) is "
            "a scan, at most with an Acrobat Paper Capture OCR layer full of errors; under the no-OCR rule none is used.",
            "WIPO Lex's HTML of the 2016 Penal Code is itself OCR-derived ('the Jaw set out below'); not used.",
            "The Constitution is read from the Chambre des comptes' born-digital French PDF (pinned Wayback capture).",
            "The version is dated 14 April 2008 (promulgation of Loi 2008/001); no sourced in-force rule yet.",
            "Loi 2026/002 of 14 April 2026 amends the Constitution, but only a scan exists: not applied, so this is "
            "preview only and not published.",
        ],
        "ai_use": ["none at data-build time"],
    }
    tmp = HERE / "corpus.json.tmp"
    tmp.write_text(json.dumps(corpus, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, HERE / "corpus.json")
    a = corpus["acts"][0]["versions"][0]["units"]
    print(len(a), "units;", sorted(a)[:3], sorted(a)[-3:])


if __name__ == "__main__":
    main()
