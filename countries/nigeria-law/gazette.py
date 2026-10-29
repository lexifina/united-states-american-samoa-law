"""Read a Federal Government Printer (Nigeria) Act from the text layer of its PDF into provision units.

Layout of an FGP print (Official Gazette supplement, and the Federal Ministry of Justice's 2011 print of the
Constitution): one body column, side notes (the section headings, and a few references such as "Cap. 192 LFN.") in a
narrow column beside it, a running head at the top of each page. Every printed line is read with its position
(PyMuPDF), so:
- side notes are told apart from the body by position (outside the body column), never by wording;
- a section's heading is the side note printed level with the section's first line;
- paragraphs are rebuilt from the typesetting: a line starts a new paragraph if it starts with an enumerator ((1),
  (a), (iv), (2A)) or a section number, if it is indented further than the line before it, or if the line before it
  stopped short of the right margin and this one does not start in lower case. Otherwise it is a wrapped line and is
  joined to the one before with a space (without one after a line-end hyphen).

No OCR is used: a page without a text layer has no lines, and is reported. Nothing here is specific to one Act except
the configuration passed in (pages, where the enacted text starts and stops, running-head band).
"""
from __future__ import annotations

import collections
import re
import unicodedata
from dataclasses import dataclass, field

QUOTES = str.maketrans({"“": '"', "”": '"', "„": '"', "″": '"', "‘": "'", "’": "'", "‚": "'", "´": "'",
                        "–": "-", "‑": "-", "­": "", "·": " "})
ENUM = re.compile(r"^\((?:[a-z]{1,3}|[ivxl]{1,6}|\d{1,3}[A-Z]{0,2})\)(?=\s|$|[A-Z\"(])")
SEC = re.compile(r"^(\d{1,3}[A-Z]{0,2})\s?\.\s*(?:—\s*|-\s*)?(?=\(1\)|[A-Z\"(]|$)")
SEC_DASH = re.compile(r"^(\d{1,3}[A-Z]{1,2})\s?(?:—|-)+\s*(?=\(1\)|[A-Z\"(])")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s).translate(QUOTES).replace(" ", " ").replace("\t", " ")
    s = re.sub(r"\(\s*([a-zA-Z0-9]{1,6})\s*\)", r"(\1)", s)  # "(f )" -> "(f)"
    s = re.sub(r"(?<=\S) +([;:,])(?=\s|$)", r"\1", s)  # the printer's space before ; : , ("dies ;")
    return re.sub(r" {2,}", " ", s).strip()


@dataclass
class Line:
    page: int
    x0: float  # relative to the page's body column
    y0: float
    x1: float  # distance short of the body column's right edge
    text: str


@dataclass
class Page:
    body: list[Line] = field(default_factory=list)
    notes: list[tuple[float, str]] = field(default_factory=list)  # (y0, text)
    chars: int = 0


def _segments(spans: list[dict], gap: float = 22.0) -> list[list[dict]]:
    segs: list[list[dict]] = []
    for s in spans:
        if not s["text"].strip():
            continue
        if segs and s["bbox"][0] - segs[-1][-1]["bbox"][2] <= gap:
            segs[-1].append(s)
        else:
            segs.append([s])
    return segs


def read_pages(doc, first: int, last: int, head_max_y: float, foot_min_y: float = 10_000.0) -> dict[int, Page]:
    """Body lines and side notes of pages first..last (0-based, inclusive)."""
    out: dict[int, Page] = {}
    for i in range(first, last + 1):
        pg = Page()
        raw = []
        for b in doc[i].get_text("dict")["blocks"]:
            if b.get("type") != 0:
                continue
            for ln in b["lines"]:
                for seg in _segments(ln["spans"]):
                    x0 = min(s["bbox"][0] for s in seg)
                    x1 = max(s["bbox"][2] for s in seg)
                    y0 = min(s["bbox"][1] for s in seg)
                    y1 = max(s["bbox"][3] for s in seg)
                    if y1 <= head_max_y or y0 >= foot_min_y:
                        continue
                    txt = ""
                    for k, s in enumerate(seg):
                        if k and s["bbox"][0] - seg[k - 1]["bbox"][2] > 1.0 and not txt.endswith(" ")                                 and not s["text"].startswith(" "):
                            txt += " "
                        txt += s["text"]
                    raw.append((x0, y0, x1, txt))
        pg.chars = sum(len(r[3].strip()) for r in raw)
        wide = [r for r in raw if r[2] - r[0] > 200]
        if not wide:
            pg.notes = [(r[1], norm(r[3])) for r in raw]
            out[i] = pg
            continue
        left = min(r[0] for r in wide)
        right = collections.Counter(round(r[2]) for r in wide).most_common(1)[0][0]
        right = max(x for x in (round(r[2]) for r in wide) if x <= right + 3)
        merged: list[list] = []
        for x0, y0, x1, t in sorted(raw, key=lambda r: (r[1], r[0])):
            if x0 >= right - 2 or x1 <= left + 2:
                # a side note ends with a full stop: the next line after one that does starts the next note
                # ("Remuneration and allowances of members." / "Proceedings of the Board."); "Cap." and "etc." are
                # abbreviations, not ends
                ended = re.search(r"(?:[a-z]{4,}|\))\.$", pg.notes[-1][1]) if pg.notes else None
                if (pg.notes and abs(pg.notes[-1][2] - y0) < 14 and pg.notes[-1][3] == (x0 >= right - 2)
                        and not (ended and re.match(r"[A-Z]", norm(t)))):
                    # next line of the same side note; a line-end hyphen joins without a space ("re-" "registration")
                    pg.notes[-1][1] += ("" if pg.notes[-1][1].endswith("-") else " ") + norm(t)
                    pg.notes[-1][2] = y0
                else:
                    pg.notes.append([y0, norm(t), y0, x0 >= right - 2])
                continue
            # pieces of one printed line (same baseline) are joined left to right
            if merged and abs(merged[-1][1] - y0) < 3 and x0 > merged[-1][2] - 1:
                merged[-1][2] = x1
                merged[-1][3] = merged[-1][3].rstrip() + " " + t.lstrip()
            else:
                merged.append([x0, y0, x1, t])
        pg.notes = [(n[0], n[1]) for n in pg.notes]
        pg.body = [Line(i, x0 - left, y0, right - x1, t) for x0, y0, x1, t in merged]
        out[i] = pg
    return out


def note_at(pg: Page, y: float, tol: float = 14.0) -> str | None:
    best = None
    for (y0, t) in pg.notes:
        if -6 <= y0 - y <= tol and (best is None or abs(y0 - y) < abs(best[0] - y)):
            best = (y0, t)
    if best is None:  # a long side note may start a line or so above its section ("Establish-ment and ...")
        for (y0, t) in pg.notes:
            if -16 <= y0 - y < -6 and (best is None or abs(y0 - y) < abs(best[0] - y)):
                best = (y0, t)
    return best[1] if best else None


def dehyphen(text: str, vocab: set[str], hyphenated: set[str]) -> str:
    """Rejoin words a side note broke at a line end ("Establish-ment" -> "Establishment"): only where the joined word
    occurs in the body text and the hyphenated form does not ("re-registration" keeps its hyphen)."""
    def fix(m):
        a, b = m.group(1), m.group(2)
        joined = (a + b).lower()
        if joined in vocab and f"{a}-{b}".lower() not in hyphenated:
            return a + b
        return m.group(0)
    return re.sub(r"\b([A-Za-z]+)-([a-z]+)\b", fix, text)


def _num(s: str) -> tuple[int, str]:
    m = re.match(r"(\d+)([A-Z]*)", s)
    return int(m.group(1)), m.group(2)


def is_next(prev: str | None, cur: str) -> bool:
    if prev is None:
        return _num(cur) == (1, "")
    pn, ps = _num(prev)
    cn, cs = _num(cur)
    return (cn == pn + 1 and cs in ("", "A")) or (cn == pn and cs > ps and len(cs) <= 2)


def key_of(num: str, prefix: str = "sec") -> str:
    n, s = _num(num)
    return f"{prefix}-{n:03d}" + (f"-{s.lower()}" if s else "")


def starts_para(prev: Line | None, ln: Line, t: str) -> bool:
    if prev is None:
        return True
    if ENUM.match(t) or SEC.match(t):
        return True
    if prev.x1 > 25 and not re.match(r"^[a-z]", t):
        return True  # the line before stopped short of the margin: it ended a paragraph
    if re.search(r"[;:]$", norm(prev.text)) and re.match(r'^["A-Z]', t):
        return True  # e.g. the next definition in an interpretation section
    if ln.page == prev.page and ln.x0 > prev.x0 + 4 and not re.match(r"^[a-z]", t):
        return True  # indented further than the line before (a first line); not across pages, whose margins differ
    return False


def paragraphs(lines: list[Line]) -> list[str]:
    paras: list[str] = []
    prev = None
    for ln in lines:
        t = norm(ln.text)
        if not t:
            continue
        if not paras or starts_para(prev, ln, t):
            paras.append(t)
        elif paras[-1].endswith("-") and not paras[-1].endswith(" -"):
            paras[-1] += t
        else:
            paras[-1] += " " + t
        prev = ln
    return [re.sub(r" {2,}", " ", p).strip() for p in paras if p.strip()]


@dataclass
class Unit:
    key: str
    label: str
    kind: str
    heading: str | None
    lines: list[Line]


def split_units(pages: dict[int, Page], start: re.Pattern, stop: re.Pattern | None,
                schedule_rx: re.Pattern | None, prefix: str = "sec", label_word: str = "Section",
                preamble_key: str | None = None, preamble_label: str = "Preamble",
                drop_rx: re.Pattern | None = None, structure_rx: re.Pattern | None = None,
                renumber: dict[str, str] | None = None) -> tuple[list[Unit], dict]:
    """Cut the body into sections (numbered in sequence), an optional preamble before section 1, and schedules.

    start: the first body line of the enacted text comes after the line matching it (e.g. "ENACTED by ...").
    stop: the first body line after the enacted text (e.g. "I certify", "EXPLANATORY MEMORANDUM").
    Part and Chapter headings (structure_rx, or a line in capitals) are left out of every unit and listed in the
    report, so nothing is dropped silently.
    """
    # "Part 1 of the Sixth Schedule apply ..." and "Chapter to be done ..." are wrapped body lines, not headings: a
    # heading in mixed case must carry its number and a dash.
    structure_rx = structure_rx or re.compile(r"^(?:PART|CHAPTER)\b|^(?:Part|Chapter) [0-9IVXLC]+[A-Z]?\s*[—-]")
    units: list[Unit] = []
    report: dict = {"structure_lines": [], "no_heading": [], "dropped": [], "orphans": [], "renumbered": []}
    seq = [l for i in sorted(pages) for l in pages[i].body]
    if start is not None:  # None: the enacted text starts on the first page read
        i0 = next((k for k, l in enumerate(seq) if start.search(norm(l.text))), None)
        if i0 is None:
            raise ValueError(f"start line not found: {start.pattern}")
        seq = seq[i0 + 1:]
    if stop is not None:
        k = next((k for k, l in enumerate(seq) if stop.search(norm(l.text))), None)
        if k is not None:
            seq = seq[:k]
    # every word of the enacted text, as printed, for the caller's fidelity check
    report["words"] = [w for l in seq for w in re.findall(r"\w+", norm(l.text))]
    cur: Unit | None = None
    prev_num: str | None = None
    in_schedules = False
    sch_n = 0
    pre: list[Line] = []
    prev_line: Line | None = None
    for l in seq:
        t = norm(l.text)
        if not t:
            continue
        if drop_rx and drop_rx.search(t):
            report["dropped"].append(t)
            continue
        if schedule_rx and prev_num is not None and schedule_rx.match(t):
            in_schedules = True
            sch_n += 1
            cur = Unit(f"sch-{sch_n:02d}", re.sub(r"\s*[—-].*$", "", t).title(), "schedule", t, [])
            units.append(cur)
            prev_line = l
            continue
        if not in_schedules:
            for line_start, right_num in (renumber or {}).items():
                if t.startswith(line_start):  # a misprinted section number, corrected (the caller lists why)
                    t = right_num + t[len(re.match(r"\d+[A-Z]*", t).group(0)):]
                    report["renumbered"].append((line_start, right_num))
            m = SEC.match(t) or SEC_DASH.match(t)
            if m and is_next(prev_num, m.group(1)) and (prev_line is None or starts_para(prev_line, l, t)):
                num = m.group(1)
                prev_num = num
                head = note_at(pages[l.page], l.y0)
                rest = t[m.end():].strip()
                cur = Unit(key_of(num, prefix), f"{label_word} {num}", "sec", head,
                           [Line(l.page, l.x0, l.y0, l.x1, rest)] if rest else [])
                if head is None:
                    report["no_heading"].append(num)
                units.append(cur)
                prev_line = l
                continue
            is_struct = bool(structure_rx.match(t)) or (t.upper() == t and re.search(r"[A-Z]{3}", t)
                                                        and not ENUM.match(t))
            if is_struct and (prev_line is None or prev_line.x1 > 25 or structure_rx.match(t)):
                report["structure_lines"].append(t)
                cur = None if prev_num is not None else cur
                prev_line = l
                continue
            if cur is None:
                if prev_num is None:
                    pre.append(l)
                else:  # the second line of a structure heading
                    report["structure_lines"].append(t)
                    # a heading's second line is centred (short of both margins); a line that reaches either
                    # margin and has lower-case words is body text outside any section: the caller must check
                    if re.search(r"[a-z]{2}", t) and not (l.x0 > 30 and l.x1 > 30):
                        report["orphans"].append(t)
                prev_line = l
                continue
        cur.lines.append(l)
        prev_line = l
    if pre and preamble_key:
        units.insert(0, Unit(preamble_key, preamble_label, "preamble", None, pre))
    elif pre:
        report["dropped"] += [norm(l.text) for l in pre]
    return units, report


def unit_text(u: Unit) -> str:
    body = paragraphs(u.lines)
    if u.kind == "schedule":
        head = f"# {u.heading}"
    elif u.kind == "preamble":
        head = f"# {u.label}"
    else:
        num = u.label.split()[-1]
        head = f"# {num}. {u.heading.rstrip('.').rstrip()}" if u.heading else f"# {u.label}"
    return "\n".join([head] + body) + "\n"
