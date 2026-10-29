"""The Constitution of Lesotho 1993, as it came into operation, from LesLII's earlier website (archived copy).

    python -X utf8 scripts/lesotho-law/constitution.py fetch   # one archived page into .cache/ (shared archive.org rate)
    python -X utf8 scripts/lesotho-law/constitution.py parse   # cache only: writes corpus.d/10-constitution.json

Why a second source. LesLII's current (Laws.Africa Peachjam) site has no archived expression page of the Constitution:
the Internet Archive holds no /akn/ls/act/1993/... page for it. LesLII's earlier website (Drupal, until 2023) printed
the Constitution's full text at /ls/legislation/num-act/1993/1, with the editorial note "This is the official text"
and the history of its making. The Internet Archive holds 17 copies of that page (2019-05-15 to 2023-03-26); the newest
is used and pinned here.

What that page is: the Constitution as it came into operation on 2 April 1993, with none of the amendments applied
(the page lists five amending Acts as related legislation; section 56 still reads "eighty members", the wording the
Fourth Amendment of 2001 replaced). So this part has one version, and its text is NOT today's Constitution. That is
why this part has no corpus.d/10-constitution.PUBLISH: it builds only to the preview branch.

Text rules (the same as the Peachjam adapter's): one file per section or schedule, one paragraph per line, the
section's number and heading as the first line; Chapter and Part headings are left out; typesetting normalised with
peachjam.norm. The source's own typing errors ("national nag" in s. 3(2)) are kept as printed.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "gitlaw_common"))

ORIGINAL = "https://lesotholii.org/ls/legislation/num-act/1993/1"
CAPTURE = "20230326214103"
URL = f"https://web.archive.org/web/{CAPTURE}id_/{ORIGINAL}"
CACHE = HERE / ".cache"
OUT = HERE / "corpus.d" / "10-constitution.json"
FROM = "1993-04-02"
AMENDING = [  # listed by the archived page itself as related legislation (title, page on the old site)
    ("Second Amendment of the Constitution Act, 1997", "/ls/legislation/num-act/1997/7"),
    ("Fourth Amendment to the Constitution Act, 2001", "/ls/legislation/num-act/2001/4"),
    ("Fifth Amendment to the Constitution Act, 2004", "/ls/legislation/num-act/2004/8"),
    ("Sixth Amendment to the Constitution Act, 2011", "/ls/legislation/num-act/2011/13"),
    ("Seventh Amendment of the Constitution Act, 2011", "/ls/legislation/num-act/2011/15"),
]


def fetch() -> None:
    import wayback  # noqa: PLC0415
    b = wayback.fetch(URL, CACHE)
    print(URL, len(b or b""))


def norm(s: str) -> str:
    import peachjam  # noqa: PLC0415
    return peachjam.norm(s)


def clean(fragment: str) -> str:
    return norm(html.unescape(re.sub(r"<[^>]+>", " ", fragment.replace("<br />", " ").replace("<br>", " "))))


def parse() -> dict:
    raw = (CACHE / hashlib.sha256(URL.encode()).hexdigest()).read_bytes()
    t = raw.decode("utf-8")
    note = re.search(r"<p>(Ed Note:.*?)</p>", t, re.S)
    start = t.index('<h1 id="Title">')
    body = t[start:t.index("</div>", start)]
    units: dict = {}
    cur = None
    dropped: list[str] = []
    for tag, inner in re.findall(r"<(h1|h2|p)[^>]*>(.*?)</\1>", body, re.S):
        s = clean(inner)
        if not s:
            continue
        if tag == "h1":
            continue
        if tag == "h2":
            m = re.match(r"(\d+)([A-Z]?)\. (.+)$", s)
            sm = re.match(r"SCHEDULE (\d+)\b", s)
            if m:
                key = f"sec-{int(m.group(1)):03d}" + (f"-{m.group(2).lower()}" if m.group(2) else "")
                cur = units.setdefault(key, {"label": f"Section {m.group(1)}{m.group(2)}", "kind": "sec", "lines": [f"# {s}"]})
            elif sm:
                key = f"sch-{int(sm.group(1)):02d}"
                cur = units.setdefault(key, {"label": f"Schedule {sm.group(1)}", "kind": "sch", "lines": [f"# {s}"]})
            elif re.match(r"(CHAPTER [IVXL]+|Part \d+) ", s):
                dropped.append(s)
                cur = None
            else:
                raise SystemExit(f"unexpected heading: {s}")
            continue
        if cur is None:
            raise SystemExit(f"text outside any section: {s[:80]}")
        cur["lines"].append(s)
    out = {k: {"label": u["label"], "kind": u["kind"], "text": "\n".join(u["lines"]) + "\n"} for k, u in sorted(units.items())}
    # fidelity: every paragraph of the page is in exactly one unit
    paras = [clean(p) for p in re.findall(r"<p[^>]*>(.*?)</p>", body, re.S)]
    paras = [p for p in paras if p]
    in_units = sum(len(u["text"].splitlines()) - 1 for u in out.values())
    assert in_units == len(paras), (in_units, len(paras))
    secs = [k for k in out if k.startswith("sec-")]
    assert len(secs) == 166 and secs[0] == "sec-001" and secs[-1] == "sec-166", secs[-3:]
    assert "eighty members" in out["sec-056"]["text"]
    sha = hashlib.sha256(raw).hexdigest()
    law_key = "constitution-1993"
    part = {
        "sources": [{
            "name": "LesLII, earlier website (lesotholii.org/ls/..., until 2023), through the Internet Archive",
            "url": ORIGINAL, "retrieved": "2026-10-28", "requests": 1,
            "licence": "LesLII content, CC BY-NC 4.0 crediting LesLII as the source (https://lesotholii.org/terms-of-use/)",
            "notes": f"The Constitution's full text as printed on LesLII's earlier website; read from the Internet "
                     f"Archive's raw copy {URL} (sha256 {sha}). The page carries no licence line of its own; LesLII's "
                     f"current terms are applied.",
        }],
        "laws": {law_key: {
            "label": "Constitution of Lesotho 1993", "title": "Constitution of Lesotho", "kind": "law",
            "enacted": None, "published": "1993-02-05", "url": ORIGINAL, "temporary_until": None, "restores": None,
            "note": None}},
        "acts": [{
            "slug": "constitution", "short": "Constitution", "title": "Constitution of Lesotho",
            "url": ORIGINAL, "first_law": law_key, "earlier_laws": [],
            "versions": [{
                "from": FROM, "source_url": URL, "sha256": sha, "units": out, "credits": {},
                "note": "The Constitution as it came into operation on 2 April 1993. No later amendment is applied: "
                        "this is not the text in force today.",
            }],
        }],
        "decisions": [
            "Constitution: LesLII's current site has no archived expression page of the Constitution, so its text is "
            "read from the archived page of LesLII's earlier website (" + ORIGINAL + ", Internet Archive capture "
            + CAPTURE + "). That page's editorial note reads: \"" + clean(note.group(1)) + "\"",
            "Constitution: the version is dated 2 April 1993, the day that editorial note gives for the Constitution "
            "coming into operation; the same page's \"Date of commencement\" field says 01 April 1993, the day the "
            "note gives for the appointment of the Prime Minister Designate that triggered commencement. The law's "
            "Published date is 5 February 1993, when the Revised Draft was published as Government Notice No. 12 of "
            "1993 (it was amended by Government Notice No. 211 of 1993 on 27 March 1993).",
            "Constitution: the page prints the Constitution as it came into operation, with no amendment applied "
            "(section 56 reads \"The National Assembly shall consist of eighty members\"). The amending Acts are not "
            "applied, because no archived copy gives a dated consolidated text after them and no text is "
            "reconstructed: " + "; ".join(a for a, _ in AMENDING) + " (the five the page lists), and the others "
            "the page does not list. The repository's history of the Constitution therefore stops at 2 April 1993, "
            "and this part (corpus.d/10-constitution.json) is not marked verified, so it builds only to the preview "
            "branch.",
            "Constitution: Chapter and Part headings are left out; " + str(len(dropped)) + " were dropped. All "
            + str(len(paras)) + " paragraphs of the page are in the 166 section files and 3 schedule files "
            "(checked by constitution.py). The source's own typing errors are kept as printed.",
        ],
        "ai_use": [],
    }
    return part


def write(part: dict) -> None:
    OUT.parent.mkdir(exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(part, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(OUT)


if __name__ == "__main__":
    if sys.argv[1:] == ["fetch"]:
        fetch()
    else:
        p = parse()
        write(p)
        u = p["acts"][0]["versions"][0]["units"]
        print(f"constitution: {len(u)} units, {sum(len(x['text']) for x in u.values())} chars -> {OUT}")
