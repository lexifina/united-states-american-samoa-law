"""Parse the native-text 2022 reimbursement notice and its merged-cell table."""
import argparse
import hashlib
import html
import json
import os
import re
from pathlib import Path
import pymupdf as pdf

URL = "https://www.americansamoa.gov/_files/ugd/4bfff9_1bc87458e18b4a19a6a845ac583b39cd.pdf"
SHA = "113bb4ba773dae2a629a6f2acff39b6aae2074b3efe2b5df392a0217d413a208"


def clean(s):
    return re.sub(r"\s+", " ", s).strip()


def plain(page):
    # Page furniture only; no substantive word repairs or OCR.
    return "\n".join(clean(b[4]) for b in page.get_text("blocks")
                     if b[6] == 0 and clean(b[4]) and not clean(b[4]).startswith("Page ")) + "\n"


def parse(source):
    body = source.read_bytes()
    assert hashlib.sha256(body).hexdigest() == SHA, "unreviewed source bytes"
    with pdf.open(stream=body, filetype="pdf") as doc:
        assert len(doc) == 3
        p = doc[1]

        def cell(x0, y0, x1, y1, **attrs):
            value = clean(p.get_text(clip=pdf.Rect(x0, y0, x1, y1)))
            attr = "".join(f' {k}="{v}"' for k, v in attrs.items())
            return f"<td{attr}>" + html.escape(value, quote=False) + "</td>"

        x = [72, 254, 395, 550]
        rows = ["<tr>"+"".join(cell(x[i], 111, x[i+1], 158) for i in range(3))+"</tr>"]
        rows.append("<tr>"+"".join(cell(x[i], 158, x[i+1], 212) for i in range(3))+"</tr>")
        rows.append("<tr>"+cell(x[0], 212, x[1], 329, rowspan=2)+cell(x[1], 212, x[2], 270)+cell(x[2], 212, x[3], 270)+"</tr>")
        rows.append("<tr>"+cell(x[1], 270, x[3], 329, colspan=2)+"</tr>")
        for lo, hi in [(329,415),(415,479),(479,560)]:
            rows.append("<tr>"+cell(x[0], lo, x[1], hi)+cell(x[1], lo, x[3], hi, colspan=2)+"</tr>")
        rows.append("<tr>"+"".join(cell(x[i], 560, x[i+1], 613) for i in range(3))+"</tr>")
        heading = clean(p.get_text(clip=pdf.Rect(34, 68, 550, 108)))
        table = heading+"\n<table>\n"+"\n".join(rows)+"\n</table>\n"
        units = {
            "notice": {"label": "Public notice", "kind": "notice", "text": plain(doc[0])},
            "section-01": {"label": "I", "kind": "section", "text": table},
            "section-02": {"label": "II", "kind": "section", "text": plain(doc[2])},
        }
    return {"sources": [{"name": "American Samoa Government: Workmen's Compensation Commission reimbursement policy notice", "url": URL,
        "retrieved": "2026-11-11", "licence": "Official government policy text; no reuse terms stated on the source page."}],
        "laws": {}, "acts": [{"slug": "workmen-compensation-travel-reimbursement", "short": "WCTR", "title": "Reimbursement Policy for Other Allowable Travel Expenses",
        "url": URL, "first_law": None, "earlier_laws": [], "versions": [{"from": "2023-01-09", "source_url": URL, "sha256": SHA, "units": units}]}],
        "decisions": ["The Workmen's Compensation Commission approved the revisions on 7 December 2022; its notice dated 28 December 2022 expressly puts all changes into effect on 9 January 2023.",
        "One current source version; earlier reimbursement rules are not included. Native PDF text is preserved without word corrections; table row spans and column spans follow the published table. Page-number footers are omitted.",
        "Source images: zero normative images, zero referenced, zero omitted. Seven decorative letterhead images on notice page 1 are excluded."],
        "ai_use": ["A model wrote the deterministic parser and inspected the native-text table layout; it did not author or correct legal wording."]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--job", type=Path, required=True)
    args = ap.parse_args()
    with (args.job / "pids.txt").open("a") as f:
        f.write(f"{os.getpid()} parse_reimbursement.py\n")
    if os.name == "nt":
        import ctypes
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
    result = parse(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8", newline="\n")
    print(hashlib.sha256(args.output.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
