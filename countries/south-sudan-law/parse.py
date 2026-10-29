"""Turn the cached official PDFs into corpus.d/*.json (scripts/gitlaw_common/SCHEMA.md). Reads only .cache/.

    python -X utf8 scripts/south-sudan-law/parse.py

Every act here is one dated version read from a PDF with a text layer (PyMuPDF, deterministic). No OCR, no network,
no model. The layout reader is generic: it drops running heads, page numbers and margin notes, takes section or
article headings from their own blocks, and rebuilds one paragraph per line from the marker lines ("(1)", "(a)")
and the line geometry. Output:

- corpus.d/10-constitution.json: the Transitional Constitution 2011 as signed (preview only: later amendments are
  not available as text, see decisions).
- corpus.d/20-codes.json: the Penal Code Act 2008 and the Code of Criminal Procedure Act 2008, plus `country`.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

import fitz  # PyMuPDF

HERE = Path(__file__).resolve().parent
CACHE = HERE / ".cache"
SOURCES = json.loads((HERE / "sources.json").read_text(encoding="utf-8"))

QUOTES = str.maketrans({"“": '"', "”": '"', "„": '"', "″": '"', "‘": "'", "’": "'", " ": " ",
                        " ": " ", " ": " ", " ": " ", "​": "", "": "", "­": ""})
MARKER = re.compile(r"^\((?:\d+[A-Za-z]?|[a-z]{1,6}|[A-Z])\)$|^\d+\.$")
MARKER_LEAD = re.compile(r"^\((?:\d+[A-Za-z]?|[a-z]{1,6}|[A-Z])\)\s+\S")
TERMINAL = re.compile(r"[.;:—–\-]$|[.;:]\s*[\"')]$")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s).translate(QUOTES)
    s = re.sub(r"\s+", " ", s).strip()
    return s.replace(" – ", " — ")


def cached(url: str) -> Path:
    return CACHE / hashlib.sha256(url.encode("utf-8")).hexdigest()


def doc(key: str) -> dict:
    return next(d for d in SOURCES["documents"] if d["key"] == key)


# ---------------------------------------------------------------- layout

class Block:
    def __init__(self, page: int, b: dict, width: float):
        self.page = page
        self.x0, self.y0, self.x1, self.y1 = b["bbox"]
        self.lines = []  # (text, x0, x1)
        for ln in b["lines"]:
            t = norm("".join(sp["text"] for sp in ln["spans"]))
            if t:
                self.lines.append((t, ln["bbox"][0], ln["bbox"][2]))
        self.text = "\n".join(t for t, _, _ in self.lines)
        self.width = width


def blocks(path: Path, cfg: dict) -> list[Block]:
    out = []
    with fitz.open(path) as d:
        for i, page in enumerate(d):
            w = page.rect.width
            bs = [Block(i, b, w) for b in page.get_text("dict")["blocks"] if b.get("type") == 0]
            for b in sorted(bs, key=lambda b: (round(b.y0), b.x0)):
                if not b.lines:
                    continue
                if b.y0 < cfg.get("head_y", 0):           # running head
                    continue
                if re.fullmatch(r"[-–\s]*\d+[-–\s]*", b.text):  # page number
                    continue
                if b.x0 > 0.76 * w and b.x1 - b.x0 < 0.2 * w:  # margin note ("Signed on ...")
                    continue
                out.append(b)
    return out


def centered(b: Block, cfg: dict) -> bool:
    if MARKER.match(b.lines[0][0]) or MARKER_LEAD.match(b.text) or len(b.lines) > 2:
        return False
    mid = (b.x0 + b.x1) / 2
    return (abs(mid - cfg["center"]) < 16 and b.x0 > cfg["left"] + 25 and b.x1 < cfg["right"] - 15)


class Paras:
    """One paragraph per line, rebuilt from PDF lines."""

    def __init__(self):
        self.p: list[str] = []

    def new(self, t: str):
        self.p.append(t)

    def join(self, t: str):
        if not self.p:
            self.p.append(t)
        elif self.p[-1].endswith("-") and len(self.p[-1]) > 1 and self.p[-1][-2].isalpha() and t[:1].islower():
            self.p[-1] += t
        else:
            self.p[-1] += " " + t

    def pending_marker(self) -> bool:
        return bool(self.p) and bool(MARKER.match(self.p[-1]))

    def add_block(self, b: Block, lines=None, right: float | None = None):
        lines = b.lines if lines is None else lines
        right = right or b.x1
        prev = None
        for t, x0, x1 in lines:
            if self.pending_marker():
                self.join(t)
            elif MARKER.match(t) or MARKER_LEAD.match(t):
                self.new(t)
            elif prev is None:
                if self.p and not TERMINAL.search(self.p[-1]):
                    self.join(t)
                else:
                    self.new(t)
            else:
                pt, _, px1 = prev
                if TERMINAL.search(pt) and px1 < right - 40 and (t[:1].isupper() or t[:1] in "\"'"):
                    self.new(t)
                else:
                    self.join(t)
            prev = (t, x0, x1)

    def text(self, head: str) -> str:
        return "\n".join([head] + [re.sub(r"\s+", " ", x).strip() for x in self.p if x.strip()]) + "\n"


# ---------------------------------------------------------------- acts

def parse_act(path: Path, cfg: dict) -> dict:
    """Units of one act: preamble, numbered sections/articles, schedules, closing formula."""
    bs = blocks(path, cfg)
    start = next(i for i, b in enumerate(bs) if b.text.startswith(cfg["start"]))
    units: dict[str, dict] = {}
    order: list[str] = []
    cur = None          # (key, label, head, Paras)
    last_centered = None
    num_rx = re.compile(r"^(\d+[A-Z]?)\.(?:\s|$)")

    def close():
        if cur:
            key, label, kind, head, paras = cur
            units[key] = {"label": label, "kind": kind, "text": paras.text(head)}
            order.append(key)

    def open_(key, label, kind, head):
        nonlocal cur
        close()
        cur = (key, label, kind, head, Paras())

    open_("preamble", cfg.get("preamble_label", "Enacting formula"), "preamble",
          f"# {cfg.get('preamble_label', 'Enacting formula')}")
    mode = "body"
    expect = 1
    for b in bs[start:]:
        t0 = b.lines[0][0]
        if cfg.get("stop") and re.match(cfg["stop"], b.text):
            break
        if centered(b, cfg):
            m = re.match(r"^Schedule \(([A-Z])\)$", b.text)
            if m:
                mode = "schedule"
                s = m.group(1)
                open_(f"sch-{s.lower()}", f"Schedule ({s})", "schedule", f"# Schedule ({s})")
                continue
            if cfg.get("closing") and b.text.startswith(cfg["closing"]):
                mode = "closing"
                open_("assent", "Assent", "closing", f"# {b.text}")
                continue
            if mode == "schedule" and cur and cur[3] == f"# {cur[1]}" and not cur[4].p:
                key, label, kind, head, paras = cur
                cur = (key, label, kind, f"# {label} — {b.text}", paras)
                continue
            if cur and cur[0] == "preamble" and b.text.upper() == "PREAMBLE":
                cur[4].new("Preamble")
                continue
            last_centered = b.text
            continue
        m = num_rx.match(t0) if mode == "body" and b.x0 < cfg["left"] + 8 else None
        if m and int(re.match(r"\d+", m.group(1)).group()) == expect:
            n = m.group(1)
            expect += 1
            rest = b.lines[1:] if t0 == m.group(0).strip() else [(t0[m.end():].strip(), b.x0, b.x1)] + b.lines[1:]
            if cfg["kind"] == "sec":
                # gazette layout: "N.\nTitle." is its own block
                title = norm(" ".join(t for t, _, _ in rest)).rstrip(".").strip()
                open_(f"sec-{int(n):03d}", f"Section {n}", "sec", f"# Section {n} — {title}")
            else:
                title = (last_centered or "").strip()
                open_(f"art-{int(n):03d}", f"Article {n}", "art", f"# Article {n} — {title}" if title else f"# Article {n}")
                cur[4].add_block(b, rest)
            last_centered = None
            continue
        if last_centered and cur and cur[2] in ("sec", "art"):
            # a centred line inside a section that is not a heading of the next one (e.g. "Explanation")
            cur[4].new(last_centered)
        last_centered = None
        cur[4].add_block(b)
    close()
    return {k: units[k] for k in order}


def version(key: str, cfg: dict, frm: str, note: str | None = None) -> dict:
    d = doc(key)
    p = cached(d["url"])
    units = parse_act(p, cfg)
    v = {"from": frm, "source_url": d["original"], "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
         "units": units, "credits": {}}
    if note:
        v["note"] = note
    return v


GAZETTE = {"head_y": 50, "left": 44, "right": 376, "center": 210, "kind": "sec", "start": "In accordance with",
           "stop": r"^_{5,}$"}
TCRSS = {"head_y": 0, "left": 72, "right": 540, "center": 306, "kind": "art",
         "start": "In accordance with the provisions of Article 59", "preamble_label": "Preamble",
         "closing": "Assent of the President"}


def write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=False) + "\n", encoding="utf-8",
                   newline="\n")
    os.replace(tmp, path)


def main() -> None:
    meta = json.loads((HERE / "corpus_meta.json").read_text(encoding="utf-8"))
    acts = {}
    acts["constitution"] = {
        "slug": "constitution", "short": "TCRSS",
        "title": "The Transitional Constitution of the Republic of South Sudan, 2011",
        "url": doc("tcrss-2011")["original"], "first_law": "tcrss-2011", "earlier_laws": [],
        "versions": [version("tcrss-2011", TCRSS, "2011-07-09")]}
    acts["penal-code"] = {
        "slug": "penal-code", "short": "PCA 2008", "title": "The Penal Code Act, 2008 (Act 9 of 2008)",
        "url": doc("pca-2008")["original"], "first_law": "pca-2008", "earlier_laws": [],
        "versions": [version("pca-2008", GAZETTE, "2008-08-22")]}
    acts["criminal-procedure"] = {
        "slug": "criminal-procedure", "short": "CCPA 2008",
        "title": "The Code of Criminal Procedure Act, 2008 (Act 5 of 2008)",
        "url": doc("ccpa-2008")["original"], "first_law": "ccpa-2008", "earlier_laws": [],
        "versions": [version("ccpa-2008", GAZETTE, "2008-03-20")]}
    report = {k: len(a["versions"][0]["units"]) for k, a in acts.items()}
    laws = meta["laws"]
    srcs = meta["sources"]
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "corpus.d"
    write(out / "10-constitution.json", {
        "acts": [acts["constitution"]], "laws": {"tcrss-2011": laws["tcrss-2011"]},
        "decisions": meta["decisions_constitution"], "ai_use": meta["ai_use"], "sources": srcs})
    write(out / "20-codes.json", {
        "country": meta["country"], "acts": [acts["penal-code"], acts["criminal-procedure"]],
        "laws": {k: laws[k] for k in ("pca-2008", "ccpa-2008")}, "applies": [],
        "decisions": meta["decisions"], "ai_use": meta["ai_use"], "sources": srcs})
    print(json.dumps(report))


if __name__ == "__main__":
    main()
