"""Tanzania's Constitution in English, from the cache only -> corpus.d/10-constitution.json.

    python -X utf8 scripts/tanzania-law/constitution.py

Source: the official Revised version in English of the Constitution of the United Republic of Tanzania, 1977 (Cap. 2),
"up to the 14th Amendment of 2005", printed under section 4 of the Laws Revision Act (G.N. No. 150 of 2005), as the
Ministry of Constitutional and Legal Affairs publishes it on nalis.sheria.go.tz/en/constitution. The PDF has a text
layer (PyMuPDF reads it; no OCR). TanzLII publishes the Constitution in Kiswahili only.

Layout of the PDF (body pages 12-89 of the printed edition, 0-based pages 11-88):
- margin notes x < 155 at 9.7 pt: each article's title, then the amending Acts ("Act No.15 of 1984 Art.6");
- body x >= 160 at 11.7 pt: paragraphs start indented (x = 195, continuation at 160), items "(a)" at 195 with their
  text at 230, sub-items "(i)" at 230 with text at 265; chapter and part headings are centred, sub-headings italic;
- the two Schedules (pages 90-91) are set at 9.7 pt.

One version only: the text as revised up to the 14th Amendment, dated 2005-04-22 (the day TanzLII's history gives
that amendment). Credited to the Ministry as "oldest version available"; the amending Acts it lists are earlier_laws.
The per-article margin references to amending Acts are not legal text and are left out of the units.
Deterministic: same cache, same bytes.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF

HERE = Path(__file__).resolve().parent
CACHE = HERE / ".cache"
PDF = CACHE / "nalis" / "katiba_ya_jamhuri_ya_muungano_wa_tanzania__english_version__2009_1.pdf"
PDF_SHA = "ba2f319ffaf839581f6ae289ab3866c179de51cf3c003b941df1085ee40031bd"
NALIS = "https://nalis.sheria.go.tz/en/constitution"
TANZLII_HISTORY = "https://web.archive.org/web/20250918092127id_/https://tanzlii.org/akn/tz/act/1977/1/swa@2002-07-31"
BUNGE_ACTS = "https://polis.bunge.go.tz/api/acts/async"
BUNGE_BILLS = "https://polis.bunge.go.tz/api/bills/async"
VERSION_FROM = "2005-04-22"
PUBLISHER = {"name": "Ministry of Constitutional and Legal Affairs (Tanzania)", "email": "nalis@sheria.invalid"}

FIRST_BODY, FIRST_SCHEDULE = 11, 89  # 0-based PDF pages
MARGIN_X = 155
REF = re.compile(r"^(Acts? Nos?\b|G\.\s?N|Cap\.?\s?\d|of \d{4}|Arts?\.\s?\d|\d+\s+(and \d+\s+)?of \d{4}|ss?\.\s?\d)")
LABEL = re.compile(r"^\((?:[a-z]{1,3}|[ivxl]+|\d+)\)$")
HEAD = re.compile(r"^(\d+)([A-Z]?)\.\s*-?\s*(.*)$")

# The amending Acts and notices the edition names on its first page (margin of the long title), in that order.
EARLIER = [("act", 1979, 14), ("act", 1980, 1), ("act", 1980, 28), ("act", 1982, 21), ("act", 1984, 15),
           ("act", 1990, 14), ("act", 1990, 16), ("act", 1992, 4), ("act", 1992, 20), ("act", 1993, 7),
           ("act", 1994, 7), ("act", 1994, 34), ("act", 1995, 12), ("act", 2000, 3), ("act", 2005, 1),
           ("gn", 2001, 133), ("gn", 2005, 150)]
# Titles only where an official list names them: Parliament's Acts list (by year and act_no), and TanzLII's history
# for the 14th Amendment.
TITLE_2005_1 = "Sheria ya Mabadiliko ya Kumi na Nne Katika Katiba ya Jamhuri ya Muungano wa Tanzania ya Mwaka, 2005"


def norm(s: str) -> str:
    s = s.replace(" ", " ").replace("‘", "'").replace("’", "'").replace("“", '"')
    s = s.replace("”", '"').replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip()


def cached(url: str) -> bytes:
    return (CACHE / hashlib.sha256(url.encode()).hexdigest()).read_bytes()


def page_rows(page, small: bool):
    """Rows of one page: fragments grouped by baseline, sorted by x. small=True keeps the 9.7 pt text."""
    frags = []
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            spans = ln["spans"]
            raw = "".join(s["text"] for s in spans)
            if not raw.strip():
                continue
            size = max(s["size"] for s in spans if s["text"].strip())
            italic = all("Italic" in s["font"] for s in spans if s["text"].strip())
            x0, y0, x1, _ = ln["bbox"]
            frags.append({"x": x0, "x1": x1, "y": y0, "raw": raw, "t": norm(raw), "size": size, "italic": italic})
    frags.sort(key=lambda f: (round(f["y"]), f["x"]))
    rows = []
    for f in frags:
        if rows and abs(rows[-1][0]["y"] - f["y"]) < 3:
            rows[-1].append(f)
        else:
            rows.append([f])
    return [sorted(r, key=lambda f: f["x"]) for r in rows]


def join(prev_raw: str, prev: str, nxt: str) -> str:
    if prev_raw.endswith("-") and not prev_raw.endswith(" -"):
        return prev + nxt
    return f"{prev} {nxt}"


class Para:
    """Paragraph assembly: a row continues the open paragraph when it starts at the paragraph's continuation x."""

    def __init__(self):
        self.lines: list[str] = []
        self.cont = None
        self.last_raw = ""

    def row(self, row):
        body = [f for f in row if f["size"] >= 10]
        if not body:
            return
        x = body[0]["x"]
        if len(body) > 1 and LABEL.match(body[0]["t"]):
            self.lines.append(f'{body[0]["t"]} {" ".join(f["t"] for f in body[1:])}')
            # a subarticle "(4)" set like an item still wraps to the margin; items "(a)", "(i)" wrap under their text
            self.cont = 160 if re.fullmatch(r"\(\d+\)", body[0]["t"]) else body[1]["x"]
        else:
            text = " ".join(f["t"] for f in body)
            last = self.lines[-1] if self.lines else ""
            # "(2) ..." indented at 195 starts a subarticle (wrapped cross-references such as "(3) of this Article"
            # sit at the margin, 160)
            opens = abs(x - 195) < 4 and re.match(r"\((?:\d+|[a-z]{1,3}|[ivxl]+)\)\s", text)
            at_cont = self.cont is not None and abs(x - self.cont) < 4 and not last.endswith((":", ":-", " -"))
            # a lowercase word after a line that ends in a bare word carries on the sentence, whatever the indent
            carries = bool(re.match(r"[a-z]", text)) and bool(re.search(r"[A-Za-z]$", last))
            if self.lines and not opens and (at_cont or carries):
                self.lines[-1] = join(self.last_raw.rstrip(), last, text)
            else:
                self.lines.append(text)
                if text.startswith('"') and abs(x - 160) < 4:
                    self.cont = 195  # a definition: hanging indent
                else:
                    self.cont = x - 35 if any(abs(x - i) < 4 for i in (195, 230, 265, 300)) else x
        self.last_raw = body[-1]["raw"]


def is_caps(row) -> bool:
    t = " ".join(f["t"] for f in row if f["size"] >= 10)
    return bool(re.search(r"[A-Z]", t)) and t == t.upper()


def centred(row) -> bool:
    b = [f for f in row if f["size"] >= 10]
    return len(b) == 1 and b[0]["x"] > 165 and 300 <= (b[0]["x"] + b[0]["x1"]) / 2 <= 345


def contents_titles(doc) -> dict:
    """Article titles from the printed Arrangement of Contents (pages 3-11), to check the margin titles."""
    out, cur, tx = {}, None, None
    for p in range(2, FIRST_BODY):
        for row in page_rows(doc[p], small=True):
            t = [f["t"] for f in row]
            if len(t) >= 2 and re.match(r"^\d+[A-Z]?\.?$", t[0]):
                cur, tx = t[0].rstrip("."), row[1]["x"]
                out[cur] = " ".join(t[1:])
            elif cur and len(row) == 1 and abs(row[0]["x"] - tx) < 4 and not is_caps(row):
                out[cur] = join(out[cur], out[cur], t[0])
            else:
                cur = None
    return {k: v.rstrip(".").strip() for k, v in out.items()}


def art_key(num: str, letter: str) -> str:
    return f"art-{int(num):03d}{letter.lower()}"


def parse_body(doc):
    units, order, structure = {}, [], []
    margins = []  # (page, y, text)
    title_rows, pre = [], None
    art = None  # (key, label, number, page, y)
    paras: dict[str, Para] = {}
    pending_heads: list[str] = []
    heading = None  # list collecting a CHAPTER/PART title
    last_key = (0, "")
    for p in range(FIRST_BODY, FIRST_SCHEDULE):
        for row in page_rows(doc[p], small=True):
            for f in row:
                if f["size"] < 10:  # margin notes are set at 9.7 pt, the body at 11.7 pt
                    assert f["x"] < MARGIN_X, (p, f["t"])
                    margins.append((p, f["y"], f["t"]))
            body = [f for f in row if f["size"] >= 10]
            if not body:
                continue
            t = " ".join(f["t"] for f in body)
            if len(body) == 1 and re.fullmatch(r"\d+", t) and body[0]["y"] > 740:
                continue  # page number
            if pre is None:  # the title block before the preamble
                if t == "PREAMBLE":
                    pre = Para()
                    paras["preamble"] = pre
                    order.append("preamble")
                else:
                    title_rows.append(t)
                continue
            if re.fullmatch(r"(CHAPTER [A-Z]+|PART (?:[IVX]+|[A-Z]+))", t):
                heading = [t]
                pending_heads.append(heading)
                continue
            if heading is not None:
                if is_caps(body) and not HEAD.match(t):
                    heading.append(t)
                    continue
                heading = None
            if body[0]["italic"] and centred(body):
                pending_heads.append([t])
                continue
            m = HEAD.match(t)
            if m and abs(body[0]["x"] - 195) < 5:
                k = (int(m[1]), m[2])
                if k > last_key:
                    last_key = k
                    key = art_key(m[1], m[2])
                    num = f"{int(m[1])}{m[2]}"
                    art = (key, num, p, body[0]["y"])
                    order.append(key)
                    units[key] = {"num": num, "page": p, "y": body[0]["y"]}
                    for h in pending_heads:
                        structure.append((h, num))
                    pending_heads = []
                    paras[key] = Para()
                    rest = m[3]
                    first = dict(body[0], t=rest, x=195)
                    paras[key].row([first] + body[1:])
                    continue
            if art is None:
                if pre is not None and t == "FOUNDATIONS OF THE CONSTITUTION":
                    pre.lines.append(t)
                    pre.cont = None
                    continue
                pre.row(row)
            else:
                paras[art[0]].row(row)
    assert not pending_heads, pending_heads
    return units, order, structure, margins, title_rows, paras


def margin_title(margins, page, y, nxt):
    """The margin lines from the article's first line down to the first reference to an amending Act. A title that
    reaches the foot of the page without one runs on at the top of the next page (before the next article)."""
    stop = nxt[1] if nxt[0] == page else 10_000
    lines = [t for (p, my, t) in margins if p == page and y - 3 <= my < stop]
    if stop == 10_000:
        stop2 = nxt[1] if nxt[0] == page + 1 else 10_000
        lines += [t for (p, my, t) in margins if p == page + 1 and my < stop2]
    out = ""
    for t in lines:
        if REF.match(t) or t.startswith("["):
            break
        out = join(out, out, t) if out else t
    return out.strip()


def parse_schedules(doc):
    """The two Schedules: 9.7 pt, labels '1.' as separate fragments, Cap. references in the left margin."""
    scheds, cur = [], None
    for p in range(FIRST_SCHEDULE, doc.page_count):
        prev_y = None
        for row in page_rows(doc[p], small=True):
            frs = [f for f in row if not re.fullmatch(r"_+", f["t"])]
            if not frs:
                continue
            t = " ".join(f["t"] for f in frs)
            if len(frs) == 1 and re.fullmatch(r"\d+", t) and frs[0]["y"] > 740:
                continue
            m = re.fullmatch(r"(FIRST|SECOND) SCHEDULE", t)
            if m:
                cur = {"name": m[1].title() + " Schedule", "paras": [], "caps": {}}
                scheds.append(cur)
                prev_y = frs[0]["y"]
                continue
            y = frs[0]["y"]
            capf = [f for f in frs if f["x"] < 100 and not re.fullmatch(r"\d+\.", f["t"])]
            main = [f for f in frs if f not in capf]
            prev = cur["paras"][-1] if cur["paras"] else ""
            # A new entry: a gap, a label, a Cap. reference, an opening bracket, or the entry before it is closed or
            # is a heading in capitals.
            new = (not prev or prev_y is None or y - prev_y >= 14
                   or (main and re.fullmatch(r"\d+\.", main[0]["t"]))
                   or any(f["t"].startswith("Cap") for f in capf)
                   or (main and main[0]["t"].startswith(("[", "(")))
                   or prev.endswith((".", "]", ")")) or prev == prev.upper())
            if main:
                text = " ".join(f["t"] for f in main)
                if new:
                    cur["paras"].append(text)
                else:
                    cur["paras"][-1] += " " + text
            if capf:
                i = len(cur["paras"]) - 1
                cur["caps"].setdefault(i, []).extend(f["t"] for f in capf)
            prev_y = y
    out = []
    for s in scheds:
        paras = [f'[{" ".join(s["caps"][i])}] {t}' if i in s["caps"] else t for i, t in enumerate(s["paras"])]
        out.append((s["name"], paras))
    return out


def main():
    data = PDF.read_bytes()
    assert hashlib.sha256(data).hexdigest() == PDF_SHA, "cached PDF changed"
    doc = fitz.open(stream=data, filetype="pdf")
    note_p1 = norm(doc[1].get_text())
    assert "up to the 14th Amendment of 2005" in note_p1, note_p1
    contents = contents_titles(doc)
    arts, order, structure, margins, title_rows, paras = parse_body(doc)

    keys = [k for k in order if k.startswith("art-")]
    pos = [(arts[k]["page"], arts[k]["y"]) for k in keys]
    units, mism, fallback, dehyph = {}, [], [], []
    title = norm(" ".join(title_rows[:2]))
    units["title"] = {"label": "Title", "kind": "preface",
                      "text": f"# {title}\n" + "".join(f"{r}\n" for r in title_rows[2:])}
    units["preamble"] = {"label": "Preamble", "kind": "preface",
                         "text": "# Preamble\n" + "".join(f"{l}\n" for l in paras["preamble"].lines)}
    for i, k in enumerate(keys):
        a = arts[k]
        nxt = pos[i + 1] if i + 1 < len(pos) else (None, None)
        mt = margin_title(margins, a["page"], a["y"], nxt)
        ct = contents.get(a["num"], "")
        for x, y in re.findall(r"\b(\w+)-(\w+)\b", mt):  # a word broken over two margin lines
            if (x + y).lower() in ct.lower() and f"{x}-{y}".lower() not in ct.lower():
                mt = mt.replace(f"{x}-{y}", x + y)
                dehyph.append(a["num"])
        if not mt:
            mt = ct
            fallback.append(a["num"])
        elif norm(mt).lower().rstrip(".") != ct.lower().rstrip("."):
            mism.append((a["num"], mt, ct))
        head = f'# {a["num"]}. {mt}'.rstrip() if mt else f'# {a["num"]}.'
        lines = paras[k].lines
        units[k] = {"label": f'Article {a["num"]}', "kind": "art", "text": head + "\n" + "".join(f"{l}\n" for l in lines)}
    for name, ps in parse_schedules(doc):
        key = "sch-1" if name.startswith("First") else "sch-2"
        units[key] = {"label": name, "kind": "schedule", "text": f"# {name}\n" + "".join(f"{p}\n" for p in ps)}
    struct_lines = [(f'{h[0]}: {" ".join(h[1:])}' if len(h) > 1 else h[0]) + f" (from Article {num})"
                    for h, num in structure]
    units["structure"] = {"label": "Chapters and parts", "kind": "structure",
                          "text": "# Chapters and parts\n" + "".join(f"{l}\n" for l in struct_lines)}

    # laws
    bunge = json.loads(cached(BUNGE_ACTS))["data"]
    laws, earlier = {}, []
    for kind, year, no in EARLIER:
        key = f"{kind}-{year}-{no}"
        label = f"Act {no} of {year}" if kind == "act" else f"G.N. {no} of {year}"
        t = None
        if kind == "act":
            hit = [r for r in bunge if str(r.get("posted")) == str(year) and str(r.get("act_no")).strip() == str(no)
                   and re.search(r"katiba", r.get("title_sw") or "", re.I)]
            if hit:
                t = norm(re.sub(r"\(Toleo la Kiingereza\)", "", hit[0]["title_sw"]))
            if key == "act-2005-1":
                t = TITLE_2005_1
        laws[key] = {"label": label, **({"title": t} if t else {}), "kind": "law" if kind == "act" else "decree",
                     "enacted": None, "published": None, "url": None, "temporary_until": None, "restores": None,
                     "note": None}
        earlier.append(key)

    n_art = len(keys)
    version = {
        "from": VERSION_FROM,
        "source_url": NALIS,
        "sha256": PDF_SHA,
        "units": {k: units[k] for k in sorted(units, key=sort_key)},
        "credits": {},
        "note": ("The official Revised version in English of the Constitution (Cap. 2), which incorporates all "
                 "amendments up to the 14th Amendment of 2005 and is printed under section 4 of the Laws Revision Act "
                 "(G.N. No. 150 of 2005), as published by the Ministry of Constitutional and Legal Affairs. Dated by "
                 "the day TanzLII's history gives the 14th Amendment (22 April 2005)."),
    }
    act = {"slug": "constitution", "short": "Constitution",
           "title": "Constitution of the United Republic of Tanzania, 1977", "url": NALIS,
           "publisher": PUBLISHER, "first_law": None, "earlier_laws": earlier, "versions": [version]}
    sources = [
        {"name": "Ministry of Constitutional and Legal Affairs, National Legal Information System (NALIS)",
         "url": NALIS, "retrieved": "2026-10-28", "requests": 1,
         "licence": "Official government publication of the United Republic of Tanzania; no licence terms stated on "
                    "the page",
         "notes": f"The official Revised version in English of the Constitution, PDF with a text layer (sha256 "
                  f"{PDF_SHA}, 519,926 bytes, 91 pages), downloaded through the site's download button (a signed "
                  "storage URL, not stable, so the page URL is recorded)."},
        {"name": "TanzLII history of the Constitution (Internet Archive capture)", "url": TANZLII_HISTORY,
         "retrieved": "2026-10-28", "requests": 1,
         "licence": "CC BY-NC 4.0, crediting TanzLII as the source",
         "notes": "Kiswahili expression page, capture 20250918092127. Its history lists the 14th Amendment on "
                  "22 April 2005 ('amendment not yet applied') and no later amendment."},
        {"name": "Parliament of Tanzania, Acts and Bills lists (polis.bunge.go.tz)", "url": BUNGE_ACTS,
         "retrieved": "2026-10-29", "requests": 3,
         "licence": "Official government publication; no licence terms stated",
         "notes": f"{BUNGE_ACTS} (1,177 Acts) and {BUNGE_BILLS} (146 Bills), behind www.parliament.go.tz/acts. Used "
                  "for the titles of the amending Acts and to look for later amendments: neither list names a "
                  "Constitution amendment after 1995, but neither covers 1996-2014, and the Acts list also lacks the "
                  "2000 and 2005 amendments. These requests are logged in .cache/requests-constitution.jsonl, apart "
                  "from the TanzLII log."},
    ]
    decisions = [
        "Constitution: read from the Ministry of Constitutional and Legal Affairs' official Revised version in "
        "English (Cap. 2, up to the 14th Amendment of 2005), because TanzLII publishes the Constitution in Kiswahili "
        "only; the act names the Ministry as its publisher.",
        f"Constitution: one version, from {VERSION_FROM}, the day TanzLII's history gives the 14th Amendment (Act 1 of "
        "2005); the edition is dated only '2005' and G.N. No. 150 of 2005 is not sourced with a date.",
        "Constitution: credited as the oldest version available; the 15 amending Acts and 2 notices the edition lists "
        "beside its long title are earlier_laws, with Parliament's titles where its Acts list gives the number.",
        "Constitution: the per-article margin references to amending Acts (for example 'Act No.15 of 1984 Art.6') "
        "are not legal text and are left out; article titles come from the margin notes.",
        f"Constitution: {len(mism)} article margin titles differ from the Arrangement of Contents wording "
        f"({', '.join(m[0] for m in mism) or 'none'}); the margin title is used. "
        f"{len(fallback)} article(s) have no margin title and take the Contents title "
        f"({', '.join(fallback) or 'none'}). A word hyphenated across two margin lines is rejoined where the Contents "
        f"spell it whole ({', '.join(dehyph) or 'none'}).",
        "Constitution: chapter, part and italic sub-headings are kept in one 'structure' unit naming the first "
        "article under each.",
        "Constitution: the source's typographical errors (for example 'Untied Republic', '[26th April, 1977)') are "
        "kept as printed.",
        "Constitution: held on the preview branch (no corpus.d/10-constitution.PUBLISH): that no amendment came after "
        "the 14th could not be confirmed. TanzLII's history (captured 2025-09-18) and Parliament's Acts and Bills "
        "lists (2015-2026) show none, but no official list read covers 2006-2014, and the CIA World Factbook says the "
        "Constitution was last amended in 2017.",
    ]
    part = {"acts": [act], "laws": laws, "sources": sources, "applies": [], "decisions": decisions,
            "ai_use": ["Constitution: none. The text is parsed from the PDF's text layer by rule; no model wrote or "
                       "corrected legal text."]}
    out = HERE / "corpus.d" / "10-constitution.json"
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(part, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    tmp.replace(out)
    print(json.dumps({"articles": n_art, "units": len(version["units"]), "margin_title_mismatches": mism,
                      "contents_fallback": fallback, "structure": len(struct_lines),
                      "schedules": [n for n, _ in parse_schedules(doc)]}, indent=1, ensure_ascii=False))


def sort_key(k: str):
    order = {"title": 0, "preamble": 1, "structure": 4}
    if k.startswith("art-"):
        return (2, k)
    if k.startswith("sch-"):
        return (3, k)
    return (order.get(k, 5), k)


if __name__ == "__main__":
    sys.exit(main())
