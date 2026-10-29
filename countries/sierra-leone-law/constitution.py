"""The Constitution of Sierra Leone, 1991 (Act No. 6 of 1991), as a dated history, from Parliament's own PDFs.

    python -X utf8 scripts/sierra-leone-law/constitution.py fetch   # network: the pinned archive copies (archive.org)
    python -X utf8 scripts/sierra-leone-law/constitution.py         # cache only: prints a summary

SierraLII does not publish the 1991 Constitution, and no consolidated, point-in-time text of it is published anywhere
we can read. The Parliament of Sierra Leone (parliament.gov.sl) publishes the Constitution as enacted and the amending
Acts as PDFs with a text layer. Its site serves an invalid TLS certificate (Traefik default), so each PDF is read from
its Internet Archive copy (raw `id_` form), pinned below by capture timestamp and sha256.

The history is rebuilt by replaying each amending Act's own instructions on the 1991 text. Every instruction is
applied by code written for that instruction (no model touches the text); the new wording is read from the amending
Act's PDF text layer, not typed in. Each version is dated by the Act's commencement: the date it states, else its
Gazette publication, under s. 106(3) of the Constitution.

Amendments that cannot be applied are listed in DECISIONS with the reason (scan only, no text layer; no sourced date).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / ".cache"
WB = "https://web.archive.org/web/{ts}id_/{orig}"
P = "https://www.parliament.gov.sl/uploads/"

# Pinned sources: (timestamp, original URL). sha256 is checked on every parse.
SRC = {
    "c1991": ("20210814090237", P + "other_resources/2-Sierra%20Leone%201991%20Constitution.pdf",
              "6609ec0e5a303fb82075b8407695162c8279d2b3c74908df6b4a85424388506a"),
    "a2001": ("20210813203802", P + "acts/The%20Constitution%20of%20Sierra%20Leone%20(Amendment)%20Act,%202001.pdf",
              None),
    "a2008": ("20210813203436", P + "acts/CONSTITUTION%20OF%20SIERRA%20LEONE%20AMENDMENT%20ACT%202008.pdf", None),
    "a2013": ("20240712030009", P + "acts/The%20%20Constitution%20of%20Sierra%20Leone%20(Amendment)%20Act,%202013..pdf",
              None),
    "a2016": ("20210813203135", P + "acts/The%20Constitution%20of%20Sierra%20Leone%20(Amendment)%20Act,2016.pdf", None),
}


def url(key: str) -> str:
    ts, orig, _ = SRC[key]
    return WB.format(ts=ts, orig=orig)


def raw(key: str) -> bytes:
    p = CACHE / hashlib.sha256(url(key).encode("utf-8")).hexdigest()
    return p.read_bytes()


def sha(key: str) -> str:
    return hashlib.sha256(raw(key)).hexdigest()


def fetch() -> None:
    sys.path.insert(0, str(HERE.parent / "gitlaw_common"))
    import wayback  # noqa: PLC0415
    for k, (ts, orig, _) in SRC.items():
        b = wayback.get(orig, ts=ts, cache=CACHE)
        print(k, len(b) if b else None)


# ---------------------------------------------------------------- text helpers

def norm(s: str) -> str:
    s = s.replace(" ", " ").replace("�", "—")
    s = s.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    s = s.replace("–", "—") if re.search(r"\s–\s", s) else s
    return re.sub(r"\s+", " ", s).strip()


def join(a: str, b: str) -> str:
    if not a:
        return b
    if re.search(r"[A-Za-z]-$", a):  # a word broken at a hyphen: "Anti-" + "Corruption", "bye-" + "elections"
        return a + b
    return a + " " + b


# ---------------------------------------------------------------- the 1991 text

def lines_1991(b: bytes) -> list[dict]:
    import fitz  # PyMuPDF  # noqa: PLC0415
    doc = fitz.open(stream=b, filetype="pdf")
    out = []
    for pn, page in enumerate(doc):
        for blk in page.get_text("dict")["blocks"]:
            for ln in blk.get("lines", []):
                spans = [s for s in ln["spans"]]
                text = "".join(s["text"] for s in spans)
                if not text.strip():
                    continue
                x, y = ln["bbox"][0], ln["bbox"][1]
                if y < 60 and ("Sierra Leone Web" in text or "Constitution of Sierra Leone, 1991" in text):
                    continue  # running head
                if y > 735 and re.fullmatch(r"\s*\d+\s*", text):
                    continue  # page number
                size = max(round(s["size"], 1) for s in spans if s["text"].strip())
                bold = any("Bold" in s["font"] for s in spans if s["text"].strip())
                out.append({"p": pn, "x": x, "y": y, "text": text, "size": size, "bold": bold})
    # merge a list marker ("a.") with its text on the same baseline (x 135 then x 153)
    merged = []
    for ln in out:
        if (merged and ln["p"] == merged[-1]["p"] and abs(ln["y"] - merged[-1]["y"]) < 3 and ln["x"] > merged[-1]["x"]
                and merged[-1]["x"] >= 100 and ln["x"] >= 100):
            merged[-1]["text"] = merged[-1]["text"].rstrip() + " " + ln["text"].lstrip()
            continue
        merged.append(dict(ln))
    return merged


LIST_RE = re.compile(r"^(?:[a-z]{1,2}|[ivx]+|\d{1,2})\.(?:\s|$)")
SUB_RE = re.compile(r"^(?:\d+[A-Z]?\.\s*)?\((\d+[A-Za-z]?)\)")


def parse_1991(b: bytes) -> tuple[dict, list[str]]:
    """{unit key: {label, kind, heading, paras: [str]}} in order, and the structural lines dropped (chapter and part
    headings). Marginal notes (x < 60) are grouped by vertical spacing; a group beside a section's first line is the
    section's heading, any other group is a marginal reference, kept as a "[Margin: ...]" line at the end of its unit."""
    lines = lines_1991(b)
    start = next(i for i, ln in enumerate(lines) if norm(ln["text"]).startswith("Being an Act to make provision")) - 1
    lines = lines[start:]
    body = [ln for ln in lines if ln["x"] >= 60]
    groups: list[list[dict]] = []
    for ln in sorted((ln for ln in lines if ln["x"] < 60), key=lambda l: (l["p"], l["y"])):
        last = groups[-1][-1] if groups else None
        if last and last["p"] == ln["p"] and ln["y"] - last["y"] < 10:
            groups[-1].append(ln)
        elif (last and ln["p"] == last["p"] + 1 and last["y"] > 690 and ln["y"] < 100
              and not norm(last["text"]).endswith(".")):  # a note that runs over the page break
            ln = dict(ln, p=last["p"], y=last["y"] + 1)
            groups[-1].append(ln)
        else:
            groups.append([ln])
    # each group belongs to the first body line at or below its top (same page), else the last line of the page
    owner: dict[int, list[str]] = {}
    for g in groups:
        top = g[0]
        cands = [k for k, ln in enumerate(body) if ln["p"] == top["p"] and ln["y"] >= top["y"] - 4]
        if not cands:
            cands = [max(k for k, ln in enumerate(body) if ln["p"] <= top["p"])]
        owner.setdefault(cands[0], []).append(norm(" ".join(m["text"] for m in g)))
    units: dict = {}
    dropped: list[str] = []
    cur = None
    prev = None
    expect = 1
    sched_no = 0
    in_sched = False

    def new_unit(key, label, kind, heading):
        nonlocal cur
        cur = {"label": label, "kind": kind, "heading": heading, "paras": [], "margin": []}
        units[key] = cur

    def add_line(t, newpara):
        if newpara or not cur["paras"]:
            cur["paras"].append(t)
        else:
            cur["paras"][-1] = join(cur["paras"][-1], t)

    new_unit("preamble", "Long title and enacting words", "preamble", None)
    for k, ln in enumerate(body):
        t = norm(ln["text"])
        notes = owner.get(k, [])
        m = re.match(r"^(\d+)\.\s", t)
        sched = re.fullmatch(r"(FIRST|SECOND|THIRD|FOURTH) SCHEDULE", t)
        if sched:
            in_sched = True
            sched_no += 1
            new_unit(f"sch-{sched_no}", t.title(), "schedule", None)
            cur["margin"] += notes
            prev = ln
            continue
        if not in_sched and m and int(m.group(1)) == expect and ln["bold"]:
            n = expect
            expect += 1
            new_unit(f"sec-{n:03d}", f"Section {n}", "sec", notes[0] if notes else None)
            cur["margin"] += notes[1:]
            add_line(t, True)
            prev = ln
            continue
        cur["margin"] += notes
        if not in_sched and ln["x"] > 160 and (ln["size"] == 8.0 or t.isupper()):
            dropped.append(t)
            prev = ln
            continue
        newpara = (
            prev is None
            or (ln["p"] == prev["p"] and ln["y"] - prev["y"] > 16)
            or (ln["p"] != prev["p"] and (SUB_RE.match(t) or t.startswith("Provided") or LIST_RE.match(t)))
            or (round(ln["x"]) == 135 and LIST_RE.match(t))
            or (in_sched and ln["x"] > 160 and t.isupper())
        )
        add_line(t, newpara)
        prev = ln
    for u in units.values():
        u["paras"] += [f"[Margin: {m}]" for m in u.pop("margin")]
    return units, dropped


# ---------------------------------------------------------------- the amending Acts

def pdf_text(b: bytes) -> str:
    import fitz  # noqa: PLC0415
    return "\n".join(p.get_text() for p in fitz.open(stream=b, filetype="pdf"))


def reflow(block: str) -> list[str]:
    """Narrow Gazette columns back into paragraphs. A paragraph starts at "(n)", "(a)", "N. (n)" or "Provided", but
    only after a paragraph that has ended (".", ":", ";", a dash) or a bare marker, so a wrapped line that happens to
    begin "(3) of section 42" stays in its sentence."""
    paras: list[str] = []
    for raw_line in block.split("\n"):
        t = norm(raw_line)
        if not t:
            continue
        opens = re.match(r'^["“]?(?:\d+[A-Z]?\.?\s*)?\((?:\d+|[a-z]{1,4})\)|^Provided\b', t)
        ended = bool(paras) and (re.search(r"[.:;—–-]\W?$", paras[-1])
                                 or re.search(r";\s*(?:or|and)$", paras[-1])
                                 or re.fullmatch(r"\W*\(\w+\)\W*", paras[-1]))
        if not paras or (opens and ended):
            paras.append(t)
        else:
            paras[-1] = join(paras[-1], t)
    return paras


def unquote(paras: list[str]) -> list[str]:
    """Keep only the wording inside the quotation marks that delimit it: drop the opening and closing marks and a
    full stop printed after the closing mark (it ends the amending sentence, as in Act No. 9 of 2008); drop an
    unpaired mark inside, as in Act No. 5 of 2013 ("ten years", and who are not less than forty years.), whose
    wording is otherwise kept whole."""
    out = []
    for p in paras:
        p = re.sub(r'^"+', "", p)
        p = re.sub(r'"+\.?$', "", p)
        if p.count('"') % 2:
            p = p.replace('"', "")
        out.append(re.sub(r"\s+", " ", p).strip())
    return [p for p in out if p]


def between(t: str, a: str, b: str) -> str:
    i = t.index(a) + len(a)
    return t[i:t.index(b, i)]


def clean_pdf(t: str) -> str:
    """Amending Act text: one dash form, and Sierra Leone Web page heads removed."""
    t = t.replace("–", "—").replace("“", '"').replace("”", '"')
    t = re.sub(r"The Laws of Sierra Leone on the Sierra Leone Web *\n.*\(Amendment\) Act, \d{4} *\n", "", t)
    return t


# ---------------------------------------------------------------- structural edits on a unit's paragraphs

def opens_sub(p: str, sec: str, k: str) -> bool:
    return re.match(rf"^(?:{sec}\.?\s*)?\({k}\)", p) is not None


def sub_span(paras: list[str], sec: str, n: str) -> tuple[int, int]:
    """Paragraph range [i, j) of subsection (n): from the paragraph that opens it to the one that opens (n+1)."""
    i = next(k for k, p in enumerate(paras) if opens_sub(p, sec, n))
    nxt = str(int(n) + 1)
    j = next((k for k in range(i + 1, len(paras)) if opens_sub(paras[k], sec, nxt)), None)
    if j is None:
        j = len(paras)
        while j > i + 1 and paras[j - 1].startswith("[Margin:"):
            j -= 1
    return i, j


def edit(units: dict, key: str, fn) -> None:
    units[key] = dict(units[key], paras=fn(list(units[key]["paras"])))


# ---------------------------------------------------------------- the replay

def amend_2001(units: dict, t: str) -> list[str]:
    """Act No. 15 of 2001: insert s. 38A; in s. 43's proviso drop "and" after (a), end (b) with "; and", add (c)."""
    t = clean_pdf(t)
    blk = between(t, "of the following:—", "(b) in section 43,")
    head, rest = blk.split("38A.", 1)
    new = {"label": "Section 38A", "kind": "sec", "heading": norm(head), "paras": reflow("38A." + rest)}
    items = list(units.items())
    items.insert([k for k, _ in items].index("sec-038") + 1, ("sec-038a", new))
    units.clear()
    units.update(items)
    c = unquote(reflow(between(t, "of the following paragraph:—", "PASSED in Parliament")))
    assert len(c) == 1 and c[0].startswith("(c) "), c
    c = [c[0].replace('(c) "', "(c) ", 1)]

    def f(paras):
        i = next(k for k, p in enumerate(paras) if p.startswith("Provided that"))
        a = i + 1
        assert paras[a].startswith("a. ") and paras[a].endswith("; and"), paras[a]
        paras[a] = paras[a][: -len(" and")]
        b = a + 1
        assert paras[b].startswith("b. ") and paras[b].endswith("."), paras[b]
        paras[b] = paras[b][:-1] + "; and"
        paras.insert(b + 1, c[0])
        return paras
    edit(units, "sec-043", f)
    return ["sec-038a", "sec-043"]


def amend_2008(units: dict, t: str) -> list[str]:
    """Act No. 9 of 2008: replace s. 64(3) and s. 66(4)(a)."""
    t = clean_pdf(t)
    s64 = unquote(reflow(between(t, "following subsection:—", "\n2.\n")))
    s66 = unquote(reflow(between(t, "following paragraph:—", "\nAmendment\nof section 64")))
    assert len(s64) == 1 and s64[0].startswith("(3) "), s64
    assert len(s66) == 1 and s66[0].startswith("(a) "), s66

    def f64(paras):
        i, j = sub_span(paras, "64", "3")
        return paras[:i] + s64 + paras[j:]

    def f66(paras):
        i, j = sub_span(paras, "66", "4")
        a = next(k for k in range(i, j) if paras[k].startswith("a. "))
        paras[a] = s66[0]
        return paras
    edit(units, "sec-064", f64)
    edit(units, "sec-066", f66)
    return ["sec-064", "sec-066"]


def amend_2013(units: dict, t: str) -> list[str]:
    """Act No. 5 of 2013: replace s. 79(1) and s. 80(2) and (3)."""
    t = clean_pdf(t)
    s79 = unquote(reflow(between(t, "\n2\n79", "\n2.\n")))
    s79[0] = "79. " + s79[0]
    s80 = unquote(reflow(between(t, "section 80 by the following:—", "PRINTED AND PUBLISHED")))
    assert s79[0].startswith("79. (1) The Speaker") and s79[-1].endswith("forty years."), s79
    assert s80[0].startswith("(2) ") and s80[-1].endswith("convenient."), s80

    def f79(paras):
        i, j = sub_span(paras, "79", "1")
        return paras[:i] + s79 + paras[j:]

    def f80(paras):
        i, _ = sub_span(paras, "80", "2")
        _, j = sub_span(paras, "80", "3")
        return paras[:i] + s80 + paras[j:]
    edit(units, "sec-079", f79)
    edit(units, "sec-080", f80)
    return ["sec-079", "sec-080"]


def amend_2016(units: dict, t: str) -> list[str]:
    """Act No. 10 of 2016: replace s. 38(8)."""
    t = clean_pdf(t)
    s38 = unquote(reflow(between(t, "following new subsection-", "\nAmendment\nof section 38")))
    assert s38[0].startswith("(8) ") and s38[-1].endswith("register of voters."), s38

    def f(paras):
        i, j = sub_span(paras, "38", "8")
        return paras[:i] + s38 + paras[j:]
    edit(units, "sec-038", f)
    return ["sec-038"]


# Each amending Act: law key, label, title, enacted (signed), published (Gazette), in force, the evidence for that
# day (from the Act's own PDF), the source, the replay function.
AMENDMENTS = [
    ("act-2001-15", "Act No. 15 of 2001", "The Constitution of Sierra Leone (Amendment) Act, 2001",
     "2002-01-25", "2002-02-07", "2002-02-07",
     "\"Date of Commencement [7th February, 2002]\"; Supplement to the Sierra Leone Gazette Vol. CXXXIII, No. 6 dated "
     "7th February, 2002; signed 25th January, 2002", "a2001", amend_2001),
    ("act-2008-9", "Act No. 9 of 2008", "The Constitution of Sierra Leone (Amendment) Act, 2008",
     "2008-07-24", "2008-07-31", "2008-07-31",
     "date of commencement \"[31st July, 2008.]\"; Gazette No. 37 of 31st July, 2008; signed 24th July, 2008",
     "a2008", amend_2008),
    ("act-2013-5", "Act No. 5 of 2013", "The Constitution of Sierra Leone (Amendment) Act, 2013",
     "2013-11-29", "2014-01-09", "2014-01-09",
     "date of commencement left blank; Supplement to the Sierra Leone Gazette Vol. CXLV, No. 2 dated 9th January, "
     "2014, so in force on publication under s. 106(3); signed 29th November, 2013", "a2013", amend_2013),
    ("act-2016-10", "Act No. 10 of 2016", "The Constitution of Sierra Leone (Amendment) Act, 2016",
     "2016-06-08", "2016-06-16", "2016-06-16",
     "date of commencement left blank; Supplement to the Sierra Leone Gazette Vol. CXLVII, No. 29 dated 16th June, "
     "2016, so in force on publication under s. 106(3); signed 8th June, 2016", "a2016", amend_2016),
]


def text_of(u: dict) -> str:
    if u["kind"] == "sec":
        num = u["label"].split()[-1]
        head = f"# Section {num}: {u['heading'].rstrip('.')}" if u.get("heading") else f"# Section {num}"
    else:
        head = f"# {u['label']}"
    return "\n".join([head] + u["paras"]) + "\n"


def as_units(units: dict) -> dict:
    return {k: {"label": u["label"], "kind": u["kind"], "text": text_of(u)} for k, u in units.items()}


def build() -> dict:
    """The corpus part for the Constitution: acts, laws, sources and decisions (no country block)."""
    for k, (_, _, want) in SRC.items():
        if want and sha(k) != want:
            raise SystemExit(f"{k}: cached bytes changed ({sha(k)})")
    units, dropped = parse_1991(raw("c1991"))
    versions = [{"from": "1991-10-01", "source_url": url("c1991"), "sha256": sha("c1991"),
                 "units": as_units(units),
                 "note": ("The Constitution as enacted (Act No. 6 of 1991), in force on 1 October 1991 under its "
                          "s. 192, from the Sierra Leone Web transcription that Parliament publishes.")}]
    laws = {"act-1991-6": {"label": "Act No. 6 of 1991", "title": "The Constitution of Sierra Leone, 1991",
                           "kind": "law", "enacted": None, "published": None,
                           "url": url("c1991"), "temporary_until": None, "restores": None, "note": None}}
    prev = as_units(units)
    for key, label, title, enacted, published, day, evidence, src, fn in AMENDMENTS:
        touched = fn(units, pdf_text(raw(src)))
        now = as_units(units)
        changes = {k: now.get(k) for k in sorted(set(prev) | set(now)) if prev.get(k) != now.get(k)}
        assert set(changes) == set(touched), (key, sorted(changes), touched)
        versions.append({"from": day, "source_url": url(src), "sha256": sha(src), "changes": changes,
                         "credits": {k: [key] for k in changes},
                         "note": f"{label}, replayed on the text before it. In force {day}: {evidence}."})
        laws[key] = {"label": label, "title": title, "kind": "law", "enacted": enacted, "published": published,
                     "url": url(src), "temporary_until": None, "restores": None, "note": None}
        prev = now
    act = {"slug": "constitution", "short": "Constitution", "title": "The Constitution of Sierra Leone, 1991",
           "url": url("c1991"), "first_law": "act-1991-6", "earlier_laws": [], "versions": versions}
    decisions = [
        "Constitution: SierraLII does not publish the 1991 Constitution and no consolidated point-in-time text of it "
        "is published anywhere we could read, so its history is rebuilt from Parliament's own PDFs (parliament.gov.sl, "
        "read through Internet Archive id_ captures because the site serves an invalid TLS certificate): the "
        "Constitution as enacted, then each amending Act replayed on it by code written for its instructions.",
        "Constitution: the 1991 text is the Sierra Leone Web transcription that Parliament publishes "
        "(uploads/other_resources/2-Sierra Leone 1991 Constitution.pdf). Parliament's other copy "
        "(uploads/acts/THE CONSTITUTION OF SIERRA LEONE 1991.pdf, the same transcription) lost its subsection numbers "
        "in conversion and was not used. The transcription prints paragraph letters as \"a.\", \"b.\"; the amending "
        "Acts print \"(a)\"; each is kept as its source prints it.",
        "Constitution: chapter and part headings, the Arrangement of Sections and the page heads are not provisions "
        f"and are left out ({len(dropped)} heading lines). A marginal note beside a section's first line is its "
        "heading; other marginal notes (citations such as \"Act No. 12 of 1978\") are kept as \"[Margin: ...]\" "
        "lines at the end of the section they sit beside.",
        "Constitution: each version is dated by the amending Act's stated commencement date or, where the Act leaves "
        "it blank, its Gazette publication date (Constitution s. 106(3)); 1 October 1991 is the Constitution's own "
        "commencement (s. 192).",
        "Constitution: quotation marks that delimit inserted wording in the amending Acts are dropped, and a word "
        "broken at a hyphen across lines is joined; the wording is otherwise as printed.",
        "Constitution: not in this history, because their only copies are scans without a text layer: the "
        "Constitution of Sierra Leone Amendment Decree, 1997 and The Constitution Reinstatement (1996) on "
        "parliament.gov.sl. The suspension of the Constitution under military rule (1992-1996, 1997-1998) is not "
        "recorded.",
        "Constitution: not applied, so the last version is not today's text: the Constitution of Sierra Leone "
        "(Amendment) Act, 2022 (Act No. 22 of 2022; Gazette No. 89 of 22 December 2022; renames the Political "
        "Parties Registration Commission and amends ss. 34 and 35), whose only copy on parliament.gov.sl is a scan "
        "with an unusable OCR layer (no OCR is done here); and a Constitution of Sierra Leone (Amendment) Act, 2022 "
        "amending s. 32(2) and (8), whose only copy is an unnumbered, undated print, so no in-force date can be "
        "sourced. The 2017, 2018, 2021 and 2022 (s. 76) texts on parliament.gov.sl are Bills, not enacted Acts, and "
        "are not applied. For these reasons the Constitution is not published to main.",
    ]
    sources = [{"name": "Parliament of Sierra Leone (parliament.gov.sl), through the Internet Archive",
                "url": "https://www.parliament.gov.sl", "retrieved": "2026-10-28", "requests": len(SRC),
                "licence": "Acts of Parliament of Sierra Leone; parliament.gov.sl states no licence. The 1991 text and "
                           "the 2001 Act are Sierra Leone Web (sierra-leone.org) transcriptions that Parliament "
                           "publishes.",
                "notes": "; ".join(f"{k}: {url(k)}" for k in SRC)}]
    return {"acts": [act], "laws": laws, "sources": sources, "decisions": decisions}


if __name__ == "__main__":
    if sys.argv[1:] == ["fetch"]:
        fetch()
        sys.exit()
    part = build()
    if sys.argv[1:2] == ["show"]:
        for x in part["acts"][0]["versions"][1:]:
            for k, u in x["changes"].items():
                print("=====", x["from"], k)
                print(u["text"] if u else None)
        sys.exit()
    for v in part["acts"][0]["versions"]:
        print(v["from"], len(v.get("units", v.get("changes", {}))), sorted(v.get("credits", {})))
