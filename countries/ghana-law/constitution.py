"""The Constitution of the Republic of Ghana, 1992: two versions, from two government-hosted PDFs with a text layer.

    python -X utf8 scripts/ghana-law/constitution.py      # prints the checks; parse.py imports build()

Why not GhaLII: the Internet Archive holds no GhaLII page of the 1992 Constitution (one CDX query over every archived
ghalii.org URL, 2026-10-28), and parliament.gh lists no Constitution among its Acts.

Sources (cached by fetch.py under .cache/, sha256 of the URL; read here with PyMuPDF, no OCR):
- OSP: https://osp.gov.gh/media/Resources/Ghana_Constitution.pdf, "The Constitution of the Republic of Ghana, 1992
  (as Amended to 1996)". The 1996 Amendment Act is integrated; each changed passage is bracketed as `N[...]` and its
  endnote N names the section of the Act that made it. This is the text in force from 31 December 1996 (today's text:
  the Constitution has not been amended since).
- AUDIT: https://audit.gov.gh/files/publications/The_1992_Constitution_of_the_Republic_of_Ghana635603143.pdf, the
  Constitution as made in 1992. Only the wording of the passages the 1996 Act replaced is taken from it.

Version 1 (7 January 1993, P.N.D.C.L. 282 s. 1): OSP text with each bracketed passage replaced by its 1992 wording
from AUDIT, or removed where the 1996 Act only inserted text. Version 2 (31 December 1996, Act 527 as GhaLII dates its
commencement): OSP text with the brackets and endnote numbers removed. Every provision Act 527 changed is credited to
it; nothing else changes between the versions.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OSP = "https://osp.gov.gh/media/Resources/Ghana_Constitution.pdf"
AUDIT = "https://audit.gov.gh/files/publications/The_1992_Constitution_of_the_Republic_of_Ghana635603143.pdf"
ACT527_PAGE = "https://web.archive.org/web/20251206102736id_/https://ghalii.org/akn/gh/act/1996/527/eng@1996-12-31"
ACT527_PDF = "https://web.archive.org/web/20260424191240id_/https://ghalii.org/akn/gh/act/1996/527/eng@1996-12-31/source.pdf"

QUOTES = str.maketrans({"“": '"', "”": '"', "„": '"', "″": '"', "‘": "'", "’": "'", "‚": "'", "′": "'",
                        " ": " ", " ": " ", " ": " ", " ": " ", "​": "", "­": "",
                        "‐": "-", "‑": "-", "‒": "-", "−": "-", "―": "—", "﻿": "", "–": "—"})

ORDINALS = ["ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE", "TEN", "ELEVEN", "TWELVE",
            "THIRTEEN", "FOURTEEN", "FIFTEEN", "SIXTEEN", "SEVENTEEN", "EIGHTEEN", "NINETEEN", "TWENTY",
            "TWENTY-ONE", "TWENTY-TWO", "TWENTY-THREE", "TWENTY-FOUR", "TWENTY-FIVE", "TWENTY-SIX"]

# The section of Act 527 behind each endnote, as the OSP endnotes state it ("As amended by Section 5, subsection (b)").
ENDNOTE_SECTION = {1: "s. 1", 2: "s. 2", 3: "s. 3", 4: "s. 4", 5: "s. 5(b)", 6: "s. 5(a)", 7: "s. 5(c)", 8: "s. 6",
                   9: "s. 7", 10: "s. 8", 11: "s. 9"}


def cache_path(url: str) -> Path:
    return HERE / ".cache" / hashlib.sha256(url.encode("utf-8")).hexdigest()


def norm(s: str) -> str:
    s = s.translate(QUOTES)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s*--\s*", "—", s)
    s = re.sub(r"\s+([,;:.])", r"\1", s)
    return s


def blocks(url: str) -> list[tuple[int, str]]:
    """(page, paragraph) for every text block of a PDF, internal line breaks joined."""
    import fitz  # PyMuPDF  # noqa: PLC0415
    doc = fitz.open(cache_path(url))
    out = []
    for pn, page in enumerate(doc):
        for b in sorted(page.get_text("blocks"), key=lambda b: (round(b[1]), b[0])):
            if b[6] != 0:  # image block
                continue
            t = norm(b[4])
            if t:
                out.append((pn, t))
    return out


# ---------------------------------------------------------------- OSP: today's text, with the 1996 spans marked

def osp_paragraphs() -> tuple[list[str], dict]:
    """The Constitution's paragraphs (Preamble to the Second Schedule), page-break continuations joined."""
    bl = blocks(OSP)
    texts = [t for _, t in bl]
    # body: the second "THE CONSTITUTION OF THE REPUBLIC OF GHANA" title (the first heads the arrangement of articles)
    start = [i for i, t in enumerate(texts) if t.startswith("IN THE NAME OF THE ALMIGHTY GOD")
             or t == "IN THE NAME OF THE ALMIGHTY GOD"]
    if not start:
        start = [i for i, t in enumerate(texts) if "IN THE NAME OF THE ALMIGHTY GOD" in t]
    i0 = start[0]
    i1 = next(i for i, t in enumerate(texts) if t.startswith("Made this 8th day of May, 1992"))
    paras: list[str] = []
    joined = 0
    prev_page = None
    for (pn, t) in bl[i0:i1]:
        # "IN THE NAME OF THE ALMIGHTY GOD We the People..." may share a block: keep the invocation its own line
        if pn != prev_page and paras and re.match(r"[a-z]", t):
            paras[-1] += " " + t  # a paragraph continued on the next page
            joined += 1
        else:
            paras.append(t)
        prev_page = pn
    # the invocation's block also holds "THE CONSTITUTION OF THE REPUBLIC OF GHANA" title lines before it: drop them
    return paras, {"blocks": i1 - i0, "page_break_joins": joined, "first": paras[0][:60], "last": paras[-1][:60]}


def toc_titles() -> dict[str, str]:
    """Arrangement of articles: '8. Dual Citizenship' -> {'8': 'Dual Citizenship'} (the source's own title case)."""
    out = {}
    texts = [t for _, t in blocks(OSP)]
    body = next(i for i, t in enumerate(texts) if "IN THE NAME OF THE ALMIGHTY GOD" in t)
    for t in texts[:body]:
        m = re.match(r"^(\d{1,3})\. ([A-Z](?:[^.]|\.(?= [a-z]))*?\S)\s*$", t)  # "195. Appointments, etc. of ..."
        if m and m.group(1) not in out:
            out[m.group(1)] = m.group(2)
    return out


# ---------------------------------------------------------------- AUDIT: the 1992 wording of the replaced passages

def audit_text() -> str:
    import fitz  # noqa: PLC0415
    doc = fitz.open(cache_path(AUDIT))
    return "\n".join(p.get_text() for p in doc)


def audit_article(full: str, num: int) -> list[str]:
    """Body text of article `num` in AUDIT (its body lines read 'N. ' alone, then the clauses), as paragraphs split at
    clause and paragraph markets."""
    lines = full.split("\n")
    # body starts after the arrangement of articles: the second 'CHAPTER ONE'
    first = [i for i, l in enumerate(lines) if l.strip() == "CHAPTER ONE"][1]
    starts = [i for i in range(first, len(lines)) if lines[i].strip() == f"{num}."]
    s = starts[0]
    e = next(i for i in range(s + 1, len(lines)) if re.fullmatch(rf"{num + 1}\.", lines[i].strip())
             or lines[i].strip().startswith("CHAPTER ") or lines[i].strip() in ("Privileges and Immunities",))
    paras: list[str] = []
    for l in lines[s + 1:e]:
        l = l.strip()
        if not l:
            continue
        if not paras or re.match(r"\((?:\d+|[a-z]|[ivx]+)\) ", l):  # a clause or paragraph marker opens a line
            paras.append(l)
        else:
            paras[-1] += " " + l
    return [norm(p) for p in paras if norm(p)]


def originals(full: str) -> dict[int, list[str]]:
    """The 1992 wording behind each OSP endnote span (paragraphs); [] where Act 527 only inserted text."""
    a8 = audit_article(full, 8)
    a9 = audit_article(full, 9)
    a112 = audit_article(full, 112)
    a114 = audit_article(full, 114)
    a166 = audit_article(full, 166)
    a201 = audit_article(full, 201)
    a206 = audit_article(full, 206)
    a211 = audit_article(full, 211)

    def clause(paras, mark):
        hit = [p for p in paras if p.startswith(mark + " ")]
        if len(hit) != 1:
            raise SystemExit(f"AUDIT: clause {mark} found {len(hit)} times in {paras[:2]}")
        return hit[0]

    if not any(" fifteen members" in p for p in a166):
        raise SystemExit("AUDIT: article 166(1) does not say fifteen")
    return {
        1: ["8."] + a8,                                         # s. 1: article 8 repealed and replaced
        2: [clause(a9, "(5)")],                                 # s. 2: clause (5) repealed and replaced
        3: [clause(a112, "(5)")],                               # s. 3: clause (5) repealed and replaced
        4: ["114."] + a114,                                     # s. 4: article 114 repealed and replaced
        5: ["fifteen"],                                         # s. 5(b): "fifteen" -> "eighteen"
        6: [],                                                  # s. 5(a): sub-paragraphs (ix) to (xi) inserted
        7: [],                                                  # s. 5(c): clause (3) inserted
        8: [],                                                  # s. 6: article 199 clause (4) inserted
        9: [clause(a201, "(a)")],                               # s. 7: paragraph (a) repealed and replaced
        10: [clause(a206, "(a)")],                              # s. 8: idem, article 206
        11: [clause(a211, "(a)")],                              # s. 9: idem, article 211
    }


# ---------------------------------------------------------------- units

# an article heading in capitals; "ETC." may sit inside it ("195. APPOINTMENTS, ETC. OF PUBLIC OFFICERS.",
# "297. IMPLIED POWER, ETC..")
HEAD = re.compile(r"^(\d{1,3})\. ([A-Z](?:[A-Z0-9 ,;:'()\-—&]|ETC\.)+?)\.{0,2}$")


def resolve(paras: list[str], which: str, orig: dict[int, list[str]]) -> list[str]:
    """Apply the endnote spans: which='1996' keeps the bracketed text, '1993' puts the 1992 wording back."""
    full = "\n".join(paras)

    def sub(m):
        n = int(m.group(1))
        inner = m.group(2)
        if which == "1996":
            inner = re.sub(r'^(\d+\. )"', r"\1", inner)        # 1[8. "DUAL CITIZENSHIP.  (Act 527's quotation marks)
            inner = re.sub(r'"\.?$', ".", inner) if n == 1 else inner
            return inner
        o = orig[n]
        if n == 5:
            return o[0]
        return "\n".join(o)
    out = re.sub(r"(?<![\w])(\d{1,2})\[(.*?)\]", sub, full, flags=re.S)
    if "[" in out or "]" in out:
        raise SystemExit("unresolved bracket in the OSP text")
    return [p for p in (norm(x) for x in out.split("\n")) if p]


def units_of(paras: list[str], titles: dict[str, str], keep_titles_for: set[str]) -> tuple[dict, list[str]]:
    """Paragraphs -> {key: unit}. Chapter, Part and cross-headings are left out (returned as `skipped`)."""
    units: dict[str, dict] = {}
    skipped: list[str] = []
    cur = None
    section = "body"
    i = 0
    n = len(paras)
    while i < n:
        p = paras[i]
        nxt = paras[i + 1] if i + 1 < n else ""
        if p.startswith("IN THE NAME OF THE ALMIGHTY GOD"):
            cur = "preamble"
            units[cur] = {"label": "Preamble", "kind": "preamble", "lines": ["# Preamble"]}
            units[cur]["lines"].append(p)
            i += 1
            continue
        m_ch = re.fullmatch(r"CHAPTER (" + "|".join(ORDINALS) + r")", p) or re.fullmatch(
            r"CHAPTER (" + "|".join(ORDINALS) + r") [A-Z ,'—\-]+", p)
        if m_ch:
            skipped.append(p)
            if re.fullmatch(r"[A-Z ,'—\-]+", nxt) and not HEAD.match(nxt):
                skipped.append(nxt)
                i += 1
            cur = None
            i += 1
            continue
        if re.match(r"(FIRST|SECOND) SCHEDULE( |$)", p):
            section = "sch1" if p.startswith("FIRST") else "sch2"
            skipped.append(p)
            if p.endswith("SCHEDULE") and re.fullmatch(r"[A-Z ,'—\-]+", nxt) and not HEAD.match(nxt):
                skipped.append(nxt)
                i += 1
            cur = None
            i += 1
            continue
        if section == "sch1" and re.fullmatch(r"PART [IVX]+( [A-Z ,'—\-]+)?", p):
            skipped.append(p)
            if re.fullmatch(r"[A-Z ,'—\-]+", nxt) and not HEAD.match(nxt):
                skipped.append(nxt)
                i += 1
            i += 1
            continue
        m = HEAD.match(p) or re.fullmatch(r"(\d{1,3})\.", p)
        if m and section in ("body", "sch1"):
            num = m.group(1)
            if section == "body":
                key = f"art-{int(num):03d}"
                label = f"Article {num}"
                t = titles.get(num) if (m.lastindex and m.lastindex >= 2) else None
                head = f"# Article {num}" + (f" — {t}" if t and (key not in keep_titles_for or True) else "")
                if not (m.lastindex and m.lastindex >= 2):
                    head = f"# Article {num}"
            else:
                key = f"sch1-sec-{int(num):02d}"
                label = f"First Schedule, section {num}"
                t = m.group(2).title() if m.lastindex and m.lastindex >= 2 else None
                head = f"# First Schedule, section {num}" + (f" — {m.group(2).capitalize()}" if t else "")
            if key in units:
                raise SystemExit(f"duplicate unit {key}")
            cur = key
            units[cur] = {"label": label, "kind": "art" if section == "body" else "transitional", "lines": [head]}
            i += 1
            continue
        if section == "sch2" and re.fullmatch(r"THE [A-Z ,'\-]*OATH[A-Z ,'\-]*", p):
            k = f"sch2-{len([u for u in units if u.startswith('sch2-')]) + 1:02d}"
            cur = k
            units[cur] = {"label": f"Second Schedule, {p.title()}", "kind": "schedule", "lines": [f"# Second Schedule — {p.title()}"]}
            i += 1
            continue
        # a cross-heading: short, no closing punctuation, followed by an article heading
        if (len(p) < 80 and not re.search(r"[.;:,—\-]$", p) and not p.startswith("(")
                and (HEAD.match(nxt) or re.fullmatch(r"\d{1,3}\.", nxt))):
            skipped.append(p)
            i += 1
            continue
        if cur is None:
            raise SystemExit(f"text outside any provision: {p[:120]}")
        units[cur]["lines"].append(p)
        i += 1
    out = {k: {"label": u["label"], "kind": u["kind"], "text": "\n".join(u["lines"]) + "\n"} for k, u in units.items()}
    return out, skipped


def words(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", s.lower())


def build(folder: Path = HERE) -> tuple[dict, dict, list[str], dict]:
    """-> (act, laws, decisions, report)."""
    paras, rep = osp_paragraphs()
    titles = toc_titles()
    full = audit_text()
    orig = originals(full)
    spans = sorted({int(m.group(1)) for m in re.finditer(r"(?<![\w])(\d{1,2})\[", "\n".join(paras))})
    if spans != list(range(1, 12)):
        raise SystemExit(f"expected endnote spans 1..11, got {spans}")
    p96 = resolve(paras, "1996", orig)
    p93 = resolve(paras, "1993", orig)
    u96, sk96 = units_of(p96, titles, set())
    u93, sk93 = units_of(p93, titles, set())
    # Articles 8 and 114 were replaced whole by Act 527, headings included; the 1992 marginal notes are not in either
    # text source (AUDIT's body has no marginal notes, its arrangement of articles already shows the 1996 ones).
    for k in ("art-008", "art-114"):
        lines = u93[k]["text"].split("\n")
        lines[0] = f"# Article {int(k[4:])}"
        u93[k]["text"] = "\n".join(lines)
    arts = sorted(k for k in u96 if k.startswith("art-"))
    if arts != [f"art-{i:03d}" for i in range(1, 300)]:
        raise SystemExit(f"articles: {len(arts)}, missing {sorted(set(f'art-{i:03d}' for i in range(1, 300)) - set(arts))}")
    changed = sorted(k for k in set(u93) | set(u96) if (u93.get(k) or {}).get("text") != (u96.get(k) or {}).get("text"))
    expect = ["art-008", "art-009", "art-112", "art-114", "art-166", "art-199", "art-201", "art-206", "art-211"]
    if changed != expect:
        raise SystemExit(f"changed units {changed} != {expect}")

    # checks: (a) the 1993 text of each changed article against AUDIT's article; (b) every other article, OSP vs AUDIT
    report = {"osp": rep, "skipped_headings_1996": len(sk96), "units": len(u96), "changed": changed, "audit_check": {}}
    for k in expect:
        a = " ".join(audit_article(full, int(k[4:])))
        ours = " ".join(u93[k]["text"].split("\n")[1:])
        sm = difflib.SequenceMatcher(None, words(ours), words(a), autojunk=False)
        report["audit_check"][k] = {"ratio": round(sm.ratio(), 4),
                                    "diffs": [(" ".join(words(ours)[i1:i2]), " ".join(words(a)[j1:j2]))
                                              for op, i1, i2, j1, j2 in sm.get_opcodes() if op != "equal"]}
    same = differ = 0
    worst = []
    for k in arts:
        if k in expect:
            continue
        try:
            a = " ".join(audit_article(full, int(k[4:])))
        except (StopIteration, IndexError):
            continue
        ours = " ".join(u96[k]["text"].split("\n")[1:])
        r = difflib.SequenceMatcher(None, words(ours), words(a), autojunk=False).ratio()
        if r == 1.0:
            same += 1
        else:
            differ += 1
            worst.append((round(r, 3), k))
    report["unchanged_articles_osp_vs_audit"] = {"identical_words": same, "differing": differ,
                                                 "lowest": sorted(worst)[:8]}
    # (c) the 1996 wording against Act 527's own printed text (GhaLII's PDF, whose text layer GhaLII made by OCR;
    # used only as a check, never as text)
    p527 = cache_path(ACT527_PDF)
    if p527.exists():
        import fitz  # noqa: PLC0415
        t527 = " ".join(p.get_text() for p in fitz.open(p527))
        w527 = words(t527)
        chk = {}
        for k in expect:
            new = [l for l in u96[k]["text"].split("\n")[1:] if l and l not in u93[k]["text"].split("\n")]
            for l in new:
                w = words(l)
                sm = difflib.SequenceMatcher(None, w, w527, autojunk=False)
                mb = sm.find_longest_match(0, len(w), 0, len(w527))
                chk.setdefault(k, []).append(round(mb.size / max(1, len(w)), 3))
        report["act527_longest_match_share"] = chk

    osp_sha = hashlib.sha256(cache_path(OSP).read_bytes()).hexdigest()
    audit_sha = hashlib.sha256(cache_path(AUDIT).read_bytes()).hexdigest()
    credits = {k: ["act-1996-527"] for k in changed}
    act = {
        "slug": "constitution",
        "short": "Constitution",
        "title": "Constitution of the Republic of Ghana, 1992",
        "url": OSP,
        "first_law": "pndcl-282",
        "earlier_laws": [],
        "versions": [
            {"from": "1993-01-07", "source_url": AUDIT, "sha256": audit_sha, "units": u93,
             "note": ("The Constitution as made (approved at the referendum of 28 April 1992), in force from 7 January "
                      "1993 under section 1 of P.N.D.C.L. 282. Text: the Office of the Special Prosecutor's copy "
                      f"(osp.gov.gh, sha256 {osp_sha[:12]}) for every provision the 1996 Amendment Act left alone, and "
                      "the Audit Service's copy of the 1992 text (audit.gov.gh, this version's source) for the nine "
                      "passages that Act replaced or that it inserted.")},
            {"from": "1996-12-31", "source_url": OSP, "sha256": osp_sha, "changes": {k: u96.get(k) for k in changed},
             "credits": credits,
             "note": ("The Constitution as amended by the Constitution of the Republic of Ghana (Amendment) Act, 1996 "
                      "(Act 527), assented to 16 December 1996, Gazette notification and commencement 31 December 1996 "
                      "as GhaLII records them. Text: the Office of the Special Prosecutor's copy (\"as Amended to "
                      "1996\"), which brackets each passage the Act changed. This is today's text: no later amendment "
                      "of the Constitution has been made.")},
        ],
    }
    laws = {
        "pndcl-282": {"label": "P.N.D.C.L. 282",
                      "title": "Constitution of the Fourth Republic of Ghana (Promulgation) Law, 1992",
                      "kind": "decree", "enacted": "1992-05-08", "published": "1992-05-15", "url": OSP,
                      "temporary_until": None, "restores": None,
                      "note": ("The Constitution approved at the referendum of 28 April 1992, set out in the Schedule to "
                               "P.N.D.C.L. 282 (made 8 May 1992, Gazette notification 15 May 1992), comes into force on "
                               "7 January 1993 (section 1).")},
        "act-1996-527": {"label": "Act 527 of 1996",
                         "title": "Constitution of the Republic of Ghana (Amendment) Act, 1996",
                         "kind": "law", "enacted": "1996-12-16", "published": "1996-12-31",
                         "url": "https://ghalii.org/akn/gh/act/1996/527", "temporary_until": None, "restores": None,
                         "note": None},
    }
    decisions = [
        "Constitution: the Internet Archive holds no GhaLII page of the 1992 Constitution, and parliament.gh lists no Constitution among its Acts; the two versions are read from government-hosted PDFs with a text layer (no OCR): the Office of the Special Prosecutor's \"Constitution of the Republic of Ghana, 1992 (as Amended to 1996)\" (osp.gov.gh, a compilation marked Oceana) and the Audit Service's copy of the 1992 text (audit.gov.gh). Neither is a Government Printer edition.",
        "Constitution, 1993 version: the 1992 text is rebuilt as the OSP text with the eleven passages it brackets as 1996 amendments (endnotes 1 to 11, naming sections 1 to 9 of Act 527) put back to their 1992 wording from the Audit Service copy: article 8 whole, article 9(5), article 112(5), article 114 whole, \"fifteen\" in article 166(1), and paragraph (a) of articles 201, 206 and 211; the passages Act 527 only inserted (article 166(1)(a)(ix) to (xi), article 166(3), article 199(4)) are left out. Every other provision is the OSP text in both versions, so the only differences between the versions are the nine articles Act 527 changed.",
        "Constitution: the 1992 marginal notes of articles 8 and 114, which Act 527 replaced whole, are in neither text source (the Audit Service copy's articles carry no marginal notes, and its arrangement of articles already shows the 1996 ones), so in the 1993 version those two files start \"# Article 8\" and \"# Article 114\" with no title.",
        "Constitution: article titles are the source's own arrangement of articles (title case); the body prints the same titles in capitals. Chapter titles, cross-headings, the Promulgation Law's own sections and its signature (\"Made this 8th day of May, 1992\") are left out; the Preamble, the 299 articles, the First Schedule's 37 transitional sections and the Second Schedule's oaths are in the provision files.",
        "Constitution: the OSP compilation keeps Act 527's quotation marks around the new article 8 (\"DUAL CITIZENSHIP. ... citizen of Ghana\".); they are dropped.",
        "Constitution: Act 527 is dated by GhaLII's record of it (archived page, Internet Archive capture 20251206102736): assented to 16 December 1996, published and commenced 31 December 1996. GhaLII's own page links Act 527 to the 1960 Constitution under \"Amends\"; that link is wrong (the Act amends articles 8 to 211 of the 1992 Constitution), and is not used.",
        "Constitution: GhaLII's source PDF of Act 527 (archived) has a text layer that GhaLII made by OCR (its terms, s. 7); it is used only as a check that the 1996 wording matches the Act (verification.json), never as text.",
        "Constitution: the Audit Service copy has typing errors in places (e.g. \"Parliamentary may make\" in article 9(1), \"agaisnt\" in article 167); only its wording of the nine replaced passages is used, and those passages are listed against the OSP text in verification.json.",
    ]
    return act, laws, decisions, report


if __name__ == "__main__":
    act, laws, decisions, report = build()
    print(json.dumps(report, indent=1, ensure_ascii=False))
    v0, v1 = act["versions"]
    for k in report["changed"]:
        print("=====", k)
        print("1993:", v0["units"].get(k, {}).get("text"))
        print("1996:", (v1["changes"].get(k) or {}).get("text"))
