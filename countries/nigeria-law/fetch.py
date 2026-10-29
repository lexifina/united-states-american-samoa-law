"""Fetch and pin Nigeria's sources: three Federal Government Printer texts with a text layer (no OCR).

    python -X utf8 scripts/nigeria-law/fetch.py

Each source is fetched once through get.py (curl, cached under .cache/ by the sha256 of the URL, every request logged
to .cache/requests.jsonl; archive.org through scripts/gitlaw_common/wayback.py), checked to be a whole PDF, and
checked against the sha256 pinned below. The pins (URL, original URL, capture timestamp, sha256, bytes, pages) are
written to sources.json, which parse.py reads. Re-running is free once the cache holds the files.

Why these copies:
- constitution: the Federal Ministry of Justice's print "Constitution of the Federal Republic of Nigeria, 1999 [With
  the First, Second and Third Alterations]" (foreword by the Attorney-General, Mohammed Bello Adoke), followed by the
  Federal Government Printer gazettes of the three Alteration Acts. justice.gov.ng no longer serves the file (the URL
  now answers with the home page), so it is read from the Internet Archive's raw capture of 15 October 2021.
- data-protection: the Official Gazette supplement of the Nigeria Data Protection Act, 2023 (Act No. 37, Gazette
  No. 119, Vol. 110, 1 July 2023), as served by the Nigerian Communications Commission.
- companies: the Official Gazette supplement of the Companies and Allied Matters Act, 2020 (Act No. 3, Gazette
  No. 124, Vol. 107, 10 August 2020), as published by the Corporate Affairs Commission; the Internet Archive's
  capture of 1 March 2021 is whole (a later capture, 20210506145030, is cut off at 1 MiB and is not used).
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import get  # noqa: E402

SOURCES = {
    "constitution": {
        "url": "https://web.archive.org/web/20211015170245id_/https://justice.gov.ng/wp-content/uploads/2020/09/Nigerian-Constitution.pdf",
        "original": "https://justice.gov.ng/wp-content/uploads/2020/09/Nigerian-Constitution.pdf",
        "via": "wayback", "capture": "20211015170245",
        "publisher": "Federal Ministry of Justice, Abuja (print of the Constitution); Federal Government Printer, Lagos (gazettes of the Alteration Acts)",
        "sha256": "e29305389be5e213bd66984ddd49b3228e1791a3d403dda217fd81f6b6e8adbc",
    },
    "data-protection": {
        "url": "https://ncc.gov.ng/media/801/view",
        "original": "https://ncc.gov.ng/media/801/view",
        "via": "direct", "capture": None,
        "publisher": "Federal Government Printer, Lagos (Official Gazette No. 119, Vol. 110, 1 July 2023)",
        "sha256": "5bfb22cf7b344e92ecca9b80decf73db694a0d1000c4f42188f46e047d8df075",
    },
    "companies": {
        "url": "https://web.archive.org/web/20210301095237id_/https://pre.cac.gov.ng/assets/images/CAMA-NOTE%20FINAL-FULL-VERSION.pdf",
        "original": "https://pre.cac.gov.ng/assets/images/CAMA-NOTE%20FINAL-FULL-VERSION.pdf",
        "via": "wayback", "capture": "20210301095237",
        "publisher": "Federal Government Printer, Lagos (Official Gazette No. 124, Vol. 107, 10 August 2020)",
        "sha256": "d39745af4eaeceb8dbdc3678bb5d072b48ad5e022ead3b1cec7f94b88b01a2c8",
    },
}


def main() -> None:
    import fitz  # PyMuPDF, only to record the page count  # noqa: PLC0415
    out = {"retrieved": "2026-10-28", "sources": {}}
    bad = []
    for key, s in SOURCES.items():
        b = get.get(s["url"], pdf=True)
        sha = hashlib.sha256(b).hexdigest()
        if sha != s["sha256"]:
            bad.append(f"{key}: sha256 {sha} != pinned {s['sha256']}")
            continue
        pages = len(fitz.open(stream=b, filetype="pdf"))
        out["sources"][key] = {**s, "bytes": len(b), "pages": pages}
        print(f"{key}: {len(b)} bytes, {pages} pages, sha256 ok")
    if bad:
        sys.exit("\n".join(bad))
    tmp = HERE / "sources.json.tmp"
    tmp.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    tmp.replace(HERE / "sources.json")


if __name__ == "__main__":
    main()
