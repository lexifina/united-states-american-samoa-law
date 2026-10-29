"""Shared adapter for the Laws.Africa Peachjam legal information institutes (LIIs): ZambiaLII, ULII, Kenya Law, ...

One module serves every LII. A country folder (scripts/<slug>-law/) holds only configuration (`acts.json`) and two
small scripts that call this module:

    fetch.py  ->  peachjam.fetch(folder)   network: Wayback CDX + archived expression pages + the LII's own listing
    parse.py  ->  peachjam.parse(folder)   cache only: writes corpus.json (scripts/gitlaw_common/SCHEMA.md)

Why the Wayback Machine. Every Peachjam LII serves its document pages (/akn/...) behind a bot challenge (Cloudflare
on ZambiaLII and ULII, AWS WAF on Kenya Law): curl gets 403 or an empty 202. Their listing pages (/legislation/) are
open. So each point-in-time expression page (/akn/<cc>/act/<work>/eng@<date>) is read from its latest Internet Archive
capture, in the raw `id_` form, and the capture timestamp is pinned in sources.json so parse.py is reproducible. The
LII's open listing page gives the current expression date, which the verification compares with the last version.

What a Peachjam expression page holds (all parsed here):
- the Akoma Ntoso document rendered as HTML (`<span class="akn-akomaNtoso">`, elements `akn-<name>` with `data-eid`);
- the coverpage: title, "Commenced on", "[This is the version of this document from D.]", verification and
  consolidation notices, and the amendment list "[Amended by <title> (Act N of YYYY) on D]";
- the History tab: a timeline of dated events ("Amended by <a href=work>", "Consolidation", "Commenced",
  "Repealed by") with "Read this version" links to the expressions that exist;
- editorial remarks inside provisions ("[section 5 amended by section 2 of <a href=/akn/..>Act 3 of 2020</a>]"),
  which are the LII's own per-provision amendment notes and the evidence for per-provision credits.

The text rule: one file per basic unit (section, article, rule, regulation; a schedule without basic units is one
unit), one paragraph or item per line, the unit's heading as the first line. Editorial remarks are left out of the
text and used as credit evidence, except where a provision has no text left at all (repealed, spent), where the remark
is the provision's whole printed content and is kept.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path
from urllib.parse import quote, urlparse

UA = "lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)"
# Every Peachjam LII's robots.txt says "Crawl-delay: 5" for User-agent *; that is stricter than our own 1 request per
# second, so it is the floor for any LII host (which this adapter does not fetch except for its open listing page).
# archive.org: at most 1 request per 3 s (coordinator, 2026-10-28: other agents use it too). The spacing is shared by
# every process on this machine through a stamp file per host (see Cache._wait), so parallel country fetches still
# add up to one request per 3 s.
CRAWL_DELAY = {"web.archive.org": 3.0}
RATE_DIR = Path(os.environ.get("TEMP", "/tmp")) / "peachjam-rate"
DEFAULT_DELAY = 5.0
WAYBACK = "https://web.archive.org"


# ---------------------------------------------------------------- fetching

class Cache:
    """curl-backed, resumable cache: one file per URL, named by sha256(url); every network request is logged."""

    def __init__(self, folder: Path, offline: bool = False):
        self.dir = Path(folder) / ".cache"
        self.offline = offline
        self._last: dict[str, float] = {}

    def path(self, url: str) -> Path:
        return self.dir / hashlib.sha256(url.encode("utf-8")).hexdigest()

    def has(self, url: str) -> bool:
        return self.path(url).exists()

    def sha256(self, url: str) -> str:
        return hashlib.sha256(self.path(url).read_bytes()).hexdigest()

    @staticmethod
    def _stamp_path(host: str) -> Path:
        RATE_DIR.mkdir(parents=True, exist_ok=True)
        return RATE_DIR / host

    def _wait(self, host: str, delay: float) -> None:
        """Sleep until `delay` seconds after the last request to `host` by any process using this adapter."""
        while True:
            st = self._stamp_path(host)
            last = max(self._last.get(host, 0), st.stat().st_mtime if st.exists() else 0)
            wait = delay - (time.time() - last)
            if wait <= 0:
                self._stamp(host)  # claim the slot before requesting
                return
            time.sleep(wait)

    def _stamp(self, host: str) -> None:
        self._last[host] = time.time()
        self._stamp_path(host).write_text(str(self._last[host]))

    def get(self, url: str, retries: int = 6) -> bytes:
        p = self.path(url)
        if p.exists():
            return p.read_bytes()
        if self.offline:
            raise FileNotFoundError(f"not in cache (run fetch.py): {url}")
        self.dir.mkdir(parents=True, exist_ok=True)
        gi = self.dir / ".gitignore"
        if not gi.exists():
            gi.write_text("*\n")
        host = urlparse(url).netloc
        if host == "web.archive.org":
            # archive.org goes through the machine-wide adaptive client (one rate for every agent; backs off on 429).
            # Same cache layout (sha256 of the URL in .cache/) and requests.jsonl.
            b = _wayback().fetch(url, self.dir)
            if b is None:
                raise RuntimeError(f"fetch failed {url}")
            return b
        delay = CRAWL_DELAY.get(host, DEFAULT_DELAY)
        code = "000"
        for attempt in range(retries):
            self._wait(host, delay)
            tmp = p.with_suffix(".part")
            t0 = time.time()
            r = subprocess.run(
                ["curl", "-sS", "-L", "--compressed", "--max-time", "240", "-A", UA, "-o", str(tmp),
                 "-w", "%{http_code}|%{content_type}|%{url_effective}", url],
                capture_output=True, text=True)
            self._stamp(host)
            code, ctype, eff = ((r.stdout or "000||").split("|", 2) + ["", ""])[:3]
            size = tmp.stat().st_size if tmp.exists() else 0
            with open(self.dir / "requests.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t0)), "url": url,
                                    "final": eff, "status": code, "type": ctype, "bytes": size,
                                    "err": r.stderr.strip()[:200]}) + "\n")
            if code == "200" and size > 0:
                tmp.replace(p)
                return p.read_bytes()
            if tmp.exists():
                tmp.unlink()
            if code in ("404", "403", "410"):
                break
            time.sleep(15 * (attempt + 1))  # archive.org drops connections under load
        raise RuntimeError(f"fetch failed {code} {url}")


def _wayback():
    """scripts/gitlaw_common/wayback.py: the shared archive.org and Common Crawl client (fetching only)."""
    common = Path(__file__).resolve().parents[1] / "gitlaw_common"
    if str(common) not in sys.path:
        sys.path.insert(0, str(common))
    import wayback  # noqa: PLC0415
    return wayback


# ---------------------------------------------------------------- configuration

def load_config(folder: Path) -> dict:
    """acts.json: {"lii": {...}, "country": {...corpus.json country block...}, "acts": [...], ...}."""
    return json.loads((Path(folder) / "acts.json").read_text(encoding="utf-8"))


def work_uri(cfg: dict, work: str) -> str:
    return f"/akn/{cfg['lii']['cc']}/act/{work}"


def law_key(uri: str) -> str:
    """/akn/zm/act/2016/2 -> act-2016-2; /akn/ug/act/genn/2024/2917 -> genn-2024-2917; si/2020/5 -> si-2020-5."""
    m = re.match(r"/(?:[a-z]{2}/)?akn/[a-z]{2}(?:-[a-z0-9]+)?/act/(.+?)/?$", uri)
    parts = (m.group(1) if m else uri).lower().split("/")
    if len(parts) == 2:
        parts = ["act"] + parts
    return re.sub(r"[^a-z0-9-]+", "-", "-".join(parts)).strip("-")


def _norm_original(u: str) -> str:
    return re.sub(r"^https?://(www\.)?", "", u.split("?")[0].split("#")[0]).rstrip("/")


# ---------------------------------------------------------------- Wayback discovery

def cdx_url(prefix: str) -> str:
    return (f"{WAYBACK}/cdx/search/cdx?url={quote(prefix, safe='/:@')}&matchType=prefix&output=json"
            f"&fl=timestamp,original,statuscode,mimetype,length&filter=statuscode:200")


def captures(cfg: dict, cache: Cache, work: str) -> dict[str, list[tuple[str, str]]]:
    """{expression date: [(timestamp, original url), ...] newest first} for one work, over every host/prefix."""
    lii = cfg["lii"]
    out: dict[str, list[tuple[str, str]]] = {}
    for host in lii["hosts"]:
        for pre in lii.get("path_prefixes", [""]):
            rows = json.loads(cache.get(cdx_url(f"{host}{pre}{work_uri(cfg, work)}/eng@")) or b"[]")
            for ts, orig, st, mt, *ln in rows[1:]:
                if "html" not in mt:
                    continue
                m = re.search(r"/eng@(\d{4}-\d{2}-\d{2})/?$", orig.split("?")[0])
                if m and "?" not in orig:
                    size = int(ln[0]) if ln and str(ln[0]).isdigit() else 0
                    out.setdefault(m.group(1), []).append((ts, orig, size))
    # Captures that hold the text are large; 2025-26 captures of older expressions are often a small shell (the text
    # is loaded by script, or older versions need a login). Try captures at least half the largest size first,
    # newest first, then the rest.
    res = {}
    for d, lst in out.items():
        lst = sorted(set(lst), key=lambda x: x[0], reverse=True)
        big = max(x[2] for x in lst)
        good = [x for x in lst if x[2] >= big / 2]
        res[d] = [(ts, o) for ts, o, _ in good + [x for x in lst if x not in good]]
    return dict(sorted(res.items()))


def cc_key(r: dict) -> str:
    """Cache key of one Common Crawl capture (the same key gitlaw_common/wayback.cc_get uses)."""
    return f'cc:{r["filename"]}:{r["offset"]}:{r["length"]}'


def cc_index(cfg: dict, cache: Cache) -> dict[str, dict[str, list[dict]]]:
    """{work: {expression date: [Common Crawl records, newest first]}} from one prefix query per host, path prefix
    and crawl (the newest `cc_crawls` crawls, default 12), over the whole /akn/<cc>/act/ tree."""
    wb = _wayback()
    lii = cfg["lii"]
    crawls = wb.cc_crawls(cache.dir)[: cfg.get("cc_crawls", 12)]
    out: dict = {}
    for host in lii["hosts"]:
        for pre in lii.get("path_prefixes", [""]):
            for r in wb.cc_captures(f"{host}{pre}/akn/{lii['cc']}/act/", crawls=crawls, match="prefix",
                                    cache=cache.dir):
                if str(r.get("status")) != "200" or "html" not in (r.get("mime") or r.get("mime-detected") or ""):
                    continue
                m = re.search(rf"/akn/{lii['cc']}/act/([^@?#]+?)/eng@(\d{{4}}-\d{{2}}-\d{{2}})/?$", r["url"])
                if m:
                    out.setdefault(m.group(1), {}).setdefault(m.group(2), []).append(r)
    for w in out:
        for d in out[w]:
            out[w][d].sort(key=lambda r: r["timestamp"], reverse=True)
    return out


def raw(ts: str, orig: str) -> str:
    return f"{WAYBACK}/web/{ts}id_/{orig}"


def good_expression_page(b: bytes, expr_uri: str) -> bool:
    """The archived page is this expression with its text: newer Peachjam pages name it in track-page-properties,
    older ones only in the table of contents (api.laws.africa/v3<expression>/!main~...). Pages whose text is loaded
    later by script (some 2026 captures) have no akn-akomaNtoso element and are rejected."""
    t = b.decode("utf-8", "replace")
    if 'class="akn-akomaNtoso"' not in t:
        return False
    if '"expression_frbr_uri"' in t:
        return f'"expression_frbr_uri": "{expr_uri}"' in t
    return f"{expr_uri}/!main" in t


# ---------------------------------------------------------------- page parsing

def _lxml():
    import lxml.html  # noqa: PLC0415
    return lxml.html


MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                      "september", "october", "november", "december"], 1)}


def parse_date(s: str) -> str | None:
    for m in re.finditer(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+),?\s+(\d{4})", s):
        if m.group(2).lower() in MONTHS:
            return dt.date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1))).isoformat()
    return None


def _text(el) -> str:
    return re.sub(r"\s+", " ", el.text_content()).strip()


def _classes(el) -> set[str]:
    return set((el.get("class") or "").split())


def page_info(b: bytes) -> dict:
    """Metadata of one expression page: uris, title, coverpage notices, amendment list, timeline."""
    h = _lxml()
    doc = h.fromstring(b.decode("utf-8", "replace"))
    info: dict = {}
    for s in doc.xpath('//script[@id="track-page-properties"]'):
        props = json.loads(s.text)
        info["work"] = props.get("work_frbr_uri")
        info["expression"] = props.get("expression_frbr_uri")
    t = doc.xpath("//title")
    info["page_title"] = re.sub(r"\s+", " ", t[0].text_content()).strip() if t else ""
    cover = doc.xpath('//div[contains(concat(" ", @class, " "), " coverpage ")]')
    info["notices"], info["amendments"] = [], []
    if cover:
        c = cover[0]
        h1 = c.xpath(".//h1")
        info["title"] = _text(h1[0]) if h1 else info["page_title"].split("–")[0].strip()
        info["notices"] = [{"class": li.get("class") or "", "text": _text(li)}
                           for li in c.xpath('.//ul[contains(@class,"notice-list")]/li')]
        for li in c.xpath('.//ol[contains(@class,"amendment-list")]/li'):
            a = li.xpath(".//a")
            info["amendments"].append({"text": _text(li), "uri": a[0].get("href") if a else None,
                                       "date": parse_date(_text(li))})
    info["timeline"] = []
    # Two History-tab layouts: older pages use div.vertical-timeline__item with an h5 date; newer pages (2026) use
    # li.document-history__item with <time datetime>, and mark an amendment that is not applied with a badge
    # "amendment not yet applied" beside it in the same card.
    items = doc.xpath('//div[contains(@class,"vertical-timeline__item")]')
    items += doc.xpath('//li[contains(concat(" ", @class, " "), " document-history__item ")]')
    for item in items:
        h5 = item.xpath(".//h5") or item.xpath(".//time")
        day = None
        if h5:
            day = h5[0].get("datetime") or parse_date(_text(h5[0]))
        body = item.xpath('.//div[contains(@class,"card-body")]')
        events = []
        read = None
        item_unapplied = bool(re.search(r"not (yet )?(been )?applied", _text(body[0]) if body else "", re.I))
        if body:
            for child in body[0]:
                if child.tag == "span" and "badge" in (child.get("class") or ""):
                    continue
                txt = _text(child)
                if child.tag == "a" and "Read this version" in txt:
                    read = child.get("href")
                    continue
                if not txt:
                    continue
                links = [(a.get("href"), _text(a)) for a in child.xpath(".//a")]
                kind = ("amended" if re.search(r"\bAmended by\b", txt) else
                        "consolidation" if re.search(r"Consolidation|Revised by|Revised edition", txt) else
                        "commenced" if "Commenced" in txt else
                        "repealed" if re.search(r"\bRepealed\b", txt) else "other")
                events.append({"kind": kind, "text": txt, "links": links,
                               "unapplied": item_unapplied})
        info["timeline"].append({"date": day, "header": _text(h5[0]) if h5 else "", "events": events,
                                 "read": read})
    # Peachjam prints a warning box when amendments are known but not yet applied to the consolidated text.
    page = b.decode("utf-8", "replace")
    info["unapplied_notice"] = sorted(set(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(0))).strip()
                                          for m in re.finditer(r"[^<>]{0,200}not yet been applied[^<>]{0,200}",
                                                               page, re.I)))
    return info


# ---------------------------------------------------------------- Akoma Ntoso HTML -> units

BASIC = ("section", "article", "rule", "regulation")
ABBR = {"section": "sec", "article": "art", "rule": "rule", "regulation": "reg", "attachment": "sch"}
LINE = {"akn-p", "akn-listIntroduction", "akn-listWrapUp", "akn-li", "akn-heading", "akn-subheading",
        "akn-crossHeading", "akn-blockList-intro", "akn-tr"}
QUOTES = str.maketrans({"“": '"', "”": '"', "„": '"', "″": '"', "‘": "'", "’": "'",
                        "‚": "'", "′": "'", " ": " ", " ": " ", " ": " ", " ": " ",
                        "​": "", "­": "", "‐": "-", "‑": "-", "‒": "-", "−": "-",
                        "―": "—", "﻿": ""})


def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s).translate(QUOTES)
    s = re.sub(r"\s+", " ", s).strip()
    s = s.replace(" – ", " — ")  # a spaced en dash is a dash: one form
    return s


def _kind_of(el) -> str | None:
    for c in _classes(el):
        if c.startswith("akn-"):
            return c[4:]
    return None


def _num_key(num: str) -> str:
    """'12A' -> '012a'; '3' -> '003'; 'nn_1' -> 'nn-001'; roman and other strings slugged."""
    num = num.strip().lower()
    m = re.fullmatch(r"(\d+)([a-z]*)(.*)", num)
    if m:
        rest = re.sub(r"[^a-z0-9]+", "-", m.group(3)).strip("-")
        return f"{int(m.group(1)):03d}{m.group(2)}" + (f"-{rest}" if rest else "")
    m = re.fullmatch(r"nn_(\d+)", num)
    if m:
        return f"nn-{int(m.group(1)):03d}"
    return re.sub(r"[^a-z0-9]+", "-", num).strip("-") or "x"


class Unit:
    def __init__(self, key, label, kind, el):
        self.key, self.label, self.kind, self.el = key, label, kind, el


def _line_text(el, drop: set[str]) -> tuple[str, list]:
    """Text of one line element, without remarks and footnotes; returns (text, remark elements, notes)."""
    parts: list[str] = []
    remarks: list = []
    notes: list[str] = []

    def walk(e):
        k = _classes(e)
        if "akn-remark" in k:
            remarks.append(e)
            if e.tail:
                parts.append(e.tail)
            return
        if "akn-authorialNote" in k:
            notes.append(note_text(e))
            if e.tail:
                parts.append(e.tail)
            return
        if e.tag in ("script", "style") or k & drop or is_note_marker(e):
            if e.tail:
                parts.append(e.tail)
            return
        if e.tag == "br":
            parts.append(" ")
        if e.tag == "img":
            parts.append(" [image] ")
        if e.text:
            parts.append(e.text)
        for c in e:
            walk(c)
        if e.tail and e is not el:
            parts.append(e.tail)

    walk(el)
    return norm("".join(parts)), remarks, notes


def unit_lines(el) -> tuple[list[str], list, list[str]]:
    """One paragraph or item per line. Returns (lines, remark elements, footnote texts)."""
    lines: list[str] = []
    remarks: list = []
    notes: list[str] = []
    pending: list[str] = []

    def emit(text: str):
        if pending:
            text = (" ".join(pending) + " " + text).strip() if text else " ".join(pending)
            pending.clear()
        if text:
            lines.append(text)

    def walk(e, top=False):
        k = _classes(e)
        if "akn-remark" in k:
            remarks.append(e)
            return
        if "akn-authorialNote" in k:
            notes.append(note_text(e))
            return
        if is_note_marker(e):
            return
        if "akn-num" in k:
            n = norm(e.text_content())
            if n:
                pending.append(n)
            return
        if e.tag in ("h1", "h2", "h3", "h4", "h5", "h6") and not top:
            emit(_line_text(e, set())[0])
            return
        if "akn-tr" in k or e.tag == "tr":
            cells = []
            for td in e:
                t, r, n = _line_text(td, set())
                remarks.extend(r)
                notes.extend(n)
                cells.append(t)
            emit(" | ".join(cells).strip())
            return
        is_line = bool(k & LINE) or e.tag in ("p", "li")
        if is_line and not any((_classes(d) & LINE) or d.tag in ("p", "li", "tr") for d in e.iterdescendants()):
            t, r, n = _line_text(e, set())
            remarks.extend(r)
            notes.extend(n)
            emit(t)
            return
        if e.tag in ("script", "style"):
            return
        own = norm(e.text or "")
        if own:  # loose text in a container is a line of its own; nothing is dropped silently
            emit(own)
        for c in e:
            walk(c)
            tail = norm(c.tail or "")
            if tail and c.tag not in ("h1", "h2", "h3", "h4", "h5", "h6"):
                emit(tail)
        if pending and is_line:
            emit("")

    walk(el, top=True)
    if pending:
        emit("")
    return lines, remarks, notes


def note_text(e) -> str:
    """A footnote (authorialNote) as 'marker: text'."""
    content = [c for c in e.iterdescendants() if "akn-authorialNote--content" in _classes(c)]
    body = norm((content[0] if content else e).text_content())
    return f"{e.get('data-marker')}: {body}" if e.get("data-marker") else body


def is_note_marker(e) -> bool:
    """The superscript link to a footnote, e.g. <sup><a href="#..._authorialNote_1">1</a></sup>."""
    return e.tag == "sup" and any("authorialNote" in (a.get("href") or "") for a in e.iter("a"))


def heading_of(el) -> str:
    for c in el:
        if c.tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            return _line_text(c, set())[0]
        if "akn-num" in _classes(c):
            continue
        break
    return ""


def _own_text(e) -> str:
    """Text of a container without its headings and editorial remarks (a Part's '[As amended by ...]' is not law)."""
    import copy  # noqa: PLC0415
    c = copy.deepcopy(e)
    for d in list(c.iterdescendants()):
        if d.getparent() is not None and (d.tag in ("h1", "h2", "h3", "h4", "h5", "h6")
                                          or _classes(d) & {"akn-remark", "akn-heading", "akn-subheading"}):
            d.drop_tree()
    return norm(c.text_content())


def find_units(root, attachment_prefix: dict | None = None) -> list[Unit]:
    """Basic units in document order. A unit is a section/article/rule/regulation not inside another one; a schedule
    (attachment) without basic units is one unit; the preface and preamble together are the unit `preamble`."""
    attachment_prefix = attachment_prefix or {}
    units: list[Unit] = []
    seen: dict[str, int] = {}

    def add(key, label, kind, el):
        if key in seen:
            seen[key] += 1
            key = f"{key}-{seen[key]}"
        else:
            seen[key] = 1
        units.append(Unit(key, label, kind, el))

    def eid_last(el, typ):
        eid = el.get("data-eid") or el.get("data-eId") or el.get("id") or ""
        last = eid.split("__")[-1]
        m = re.match(rf"{typ}_(.+)$", last)
        return m.group(1) if m else last

    def walk(e, prefix, label_prefix):
        k = _kind_of(e)
        if k in BASIC:
            num = eid_last(e, ABBR[k])
            key = prefix + ABBR[k] + "-" + _num_key(num)
            add(key, f"{label_prefix}{k.capitalize()} {num.replace('_', ' ')}", k, e)
            return
        if k == "attachment":
            eid = e.get("data-eid") or e.get("data-eId") or e.get("id") or ""
            if any(_kind_of(d) in BASIC for d in e.iterdescendants()):
                n = re.search(r"att_(\d+)$", eid)
                p = attachment_prefix.get(eid, f"sch-{int(n.group(1)):02d}-" if n else "sch-x-")
                lp = "" if eid in attachment_prefix else f"{heading_of(e) or eid}, "
                for c in e:
                    walk(c, p, lp)
            else:
                n = re.search(r"att_(\d+)$", eid)
                add(f"sch-{int(n.group(1)):02d}" if n else "sch-x", heading_of(e) or "Schedule", "schedule", e)
            return
        if k == "preface":
            add("long-title", "Long title", k, e)
            return
        if k == "preamble":
            add("preamble", "Preamble", k, e)
            return
        # Text that sits in no basic unit (the Constitution of Zambia's Preamble is a subpart of its Schedule; an act
        # with no sections at all): a container with no basic unit inside it but with paragraphs of its own is a unit,
        # keyed by its heading. Nothing with text is dropped; only bare Part/Chapter headings are left out.
        # Consecutive such siblings form ONE unit (Uganda's National Objectives: a heading container followed by
        # paragraphs I to XXIX directly in the body), keyed by the first heading in the run.
        if leftover(e):
            flush([e], prefix, label_prefix)
            return
        run: list = []
        for c in e:
            if heading_only(c):  # a crossheading container starts a new run, and names it
                if run:
                    flush(run, prefix, label_prefix)
                run = [c]
                continue
            if leftover(c):
                run.append(c)
                continue
            if run:
                flush(run, prefix, label_prefix)
                run = []
            walk(c, prefix, label_prefix)
        if run:
            flush(run, prefix, label_prefix)

    def leftover(e) -> bool:
        k = _kind_of(e)
        return bool(k and k not in ("akomaNtoso", "act", "body", "mainBody", "doc", "attachments", "attachment",
                                    "preface", "preamble") + BASIC
                    and not any(_kind_of(d) in BASIC + ("attachment",) for d in e.iterdescendants())
                    and any("akn-p" in _classes(d) for d in e.iterdescendants())
                    and _own_text(e))

    def heading_only(e) -> bool:
        k = _kind_of(e)
        return bool(k in ("hcontainer", "crossHeading") and heading_of(e) and not _own_text(e)
                    and not any(_kind_of(d) in BASIC + ("attachment",) for d in e.iterdescendants()))

    def flush(els: list, prefix: str, label_prefix: str) -> None:
        if not any(_own_text(x) for x in els):
            return  # a heading with nothing under it before the next basic unit: a heading, left out
        head = next((h for h in (heading_of(x) for x in els) if h), "")
        last = (els[0].get("data-eid") or els[0].get("data-eId") or els[0].get("id") or "text").split("__")[-1]
        slug = re.sub(r"[^a-z0-9]+", "-", (head or last).lower()).strip("-")[:40] or "text"
        add(prefix + slug, f"{label_prefix}{head or last}", _kind_of(els[0]), els if len(els) > 1 else els[0])

    walk(root, "", "")
    return units


def fidelity(b: bytes, attachment_prefix: dict | None, units: dict) -> dict:
    """Check one version's units against the page they came from, independently of the line splitting:
    - per unit, the multiset of non-space characters of the source element (without editorial remarks and footnote
      markers) must equal that of the unit's text (without the '# ' heading mark and footnote brackets); a unit that
      kept its remark because it has no other text (repealed, spent) is allowed to differ by exactly that remark;
    - outside the units, only headings may remain: the characters of any other leftover text are reported."""
    import collections  # noqa: PLC0415
    doc = _lxml().fromstring(b.decode("utf-8", "replace"))
    root = doc.xpath('//*[contains(concat(" ", @class, " "), " akn-akomaNtoso ")]')[0]
    found = find_units(root, attachment_prefix)
    bad = []
    for u in found:
        if u.key not in units:
            continue
        els = u.el if isinstance(u.el, list) else [u.el]
        src = collections.Counter()
        rem = collections.Counter()
        for el in els:
            src.update(re.sub(r"\s+", "", norm(el.text_content())))
            for r in el.xpath('.//*[contains(@class,"akn-remark")]'):
                rem.update(re.sub(r"\s+", "", norm(r.text_content())))
            for s in el.iter("sup"):
                if is_note_marker(s):
                    src.subtract(re.sub(r"\s+", "", s.text_content()))
            for n in el.xpath('.//*[contains(@class,"akn-authorialNote--marker")]'):
                src.subtract(re.sub(r"\s+", "", n.text_content()))
        txt = units[u.key]["text"]
        body = re.sub(r"^# ", "", txt)
        body = re.sub(r"\[Footnote (\S+?): ", "", body)
        mine = collections.Counter(re.sub(r"\s+", "", body.replace(" | ", " ")))  # table cells are joined by " | "
        if u.kind == "preface":  # heading added by us: "# Long title"
            mine.subtract("Longtitle")
        elif u.kind == "preamble" and not heading_of(els[0]):  # "# Preamble"
            mine.subtract("Preamble")
        src_no_rem = src.copy()
        src_no_rem.subtract(rem)
        ok = (+mine == +src_no_rem) or (+mine == +src)
        if not ok:
            # the footnote closing bracket and our added heading words for headless units
            diff = (+mine - +src_no_rem) + (+src_no_rem - +mine)
            if sum(diff.values()) > 2 + len(u.label):
                bad.append(u.key)
    for u in found:
        for el in (u.el if isinstance(u.el, list) else [u.el]):
            if el.getparent() is not None:
                el.drop_tree()
    for d in list(root.iterdescendants()):
        if d.getparent() is not None and (d.tag in ("h1", "h2", "h3", "h4", "h5", "h6")
                                          or _classes(d) & {"akn-remark", "akn-heading", "akn-subheading",
                                                            "akn-num"}):
            d.drop_tree()
    left = norm(root.text_content())
    return {"units": len(units), "units_differing": bad, "text_outside_units_chars": len(left),
            "text_outside_units_sample": left[:200]}


REPEAL_RX = re.compile(r"repeal|revoked|deleted|spent|has had its effect|expired|lapsed", re.I)


def units_of(b: bytes, attachment_prefix: dict | None = None) -> tuple[dict, dict]:
    """(units {key: {label, kind, text}}, remark refs {key: [work uris named in its editorial remarks]})."""
    h = _lxml()
    doc = h.fromstring(b.decode("utf-8", "replace"))
    roots = doc.xpath('//*[contains(concat(" ", @class, " "), " akn-akomaNtoso ")]')
    if not roots:
        raise ValueError("no akn-akomaNtoso element")
    out: dict = {}
    refs: dict = {}
    for u in find_units(roots[0], attachment_prefix):
        els = u.el if isinstance(u.el, list) else [u.el]
        lines, remarks, notes = [], [], []
        head = ""
        for el in els:
            if not head and u.kind not in ("preface", "preamble"):
                head = heading_of(el)
            l, r, n = unit_lines(el)
            lines += l
            remarks += r
            notes += n
        rtexts = [norm(r.text_content()) for r in remarks]
        rrefs = sorted({a.get("href") for r in remarks for a in r.xpath(".//a") if a.get("href", "").startswith("/")})
        body = [x for x in lines if x and x != head]
        if not body:
            if not rtexts and not head:
                continue
            body = rtexts  # a repealed or spent provision: its remark is all the LII prints
        text = ([f"# {head}"] if head else [f"# {u.label}"]) + body + [f"[Footnote {n}]" for n in notes if n]
        out[u.key] = {"label": u.label, "kind": {"section": "sec", "article": "art"}.get(u.kind, u.kind),
                      "text": "\n".join(text) + "\n"}
        if rrefs:
            refs[u.key] = rrefs
        out[u.key]["_remarks"] = rtexts
    return out, refs


# ---------------------------------------------------------------- fetch

def fetch(folder: Path) -> dict:
    """Discover every expression of every configured act on the Wayback Machine, download the latest good capture of
    each, plus each amending law's first expression page and the LII's open listing page; write sources.json."""
    folder = Path(folder)
    cfg = load_config(folder)
    lii = cfg["lii"]
    if lii.get("blocked"):
        raise SystemExit(f"{lii['name']}: fetching is blocked: {lii['blocked']}")
    cache = Cache(folder)
    pins: dict = {"lii": lii["name"], "acts": {}, "laws": {}, "listings": {}}
    law_uris: set[str] = set()
    ccx = cc_index(cfg, cache) if cfg.get("common_crawl", True) else {}
    for act in cfg["acts"]:
        work = act["work"]
        wb = captures(cfg, cache, work) if cfg.get("wayback", True) else {}
        cc = ccx.get(work, {})
        caps = {d: True for d in sorted(set(wb) | set(cc))}
        if not caps:
            print(f"{work}: no archived expression pages")
            continue
        # Candidates per expression: anything already cached (free, and keeps earlier pins stable), then Common
        # Crawl captures (fast CDN byte ranges, fetched in parallel), then archive.org captures (one shared,
        # adaptive machine-wide rate), each newest first.
        cands: dict[str, list[dict]] = {}
        for day in caps:
            lst = [{"via": "commoncrawl", "crawl": r["crawl"], "capture": r["timestamp"], "original": r["url"],
                    "url": cc_key(r), "rec": r} for r in cc.get(day, [])]
            lst += [{"via": "wayback", "capture": ts, "original": orig, "url": raw(ts, orig)}
                    for ts, orig in wb.get(day, [])]
            cached = [c for c in lst if cache.has(c["url"])]
            fresh = [c for c in lst if not cache.has(c["url"])]
            cands[day] = cached + [c for c in fresh if c["via"] == "commoncrawl"] + \
                [c for c in fresh if c["via"] == "wayback"][: act.get("max_tries", 10)]
        from concurrent.futures import ThreadPoolExecutor  # noqa: PLC0415
        with ThreadPoolExecutor(12) as pool:  # warm the cache with the first two Common Crawl copies of each
            list(pool.map(lambda c: _wayback().cc_get(c["rec"], cache.dir),
                          [c for lst in cands.values() for c in [x for x in lst if x["via"] == "commoncrawl"][:2]
                           if not cache.has(c["url"])]))
        ex = {}
        for day, lst in cands.items():
            expr_uri = f"{work_uri(cfg, work)}/eng@{day}"
            for c in lst:
                try:
                    if c["via"] == "commoncrawl":
                        b = cache.get(c["url"]) if cache.has(c["url"]) else _wayback().cc_get(c["rec"], cache.dir)
                    else:
                        b = cache.get(c["url"])
                except RuntimeError as e:
                    print("  skip", e)
                    continue
                if b and good_expression_page(b, expr_uri):
                    pin = {k: v for k, v in c.items() if k != "rec"}
                    if c["via"] == "commoncrawl":
                        r = c["rec"]
                        pin.update(filename=r["filename"], offset=r["offset"], length=r["length"],
                                   source_url=f"https://data.commoncrawl.org/{r['filename']}#bytes={r['offset']}-"
                                              f"{int(r['offset']) + int(r['length']) - 1}")
                    else:
                        pin["source_url"] = c["url"]
                    ex[day] = {**pin, "sha256": hashlib.sha256(b).hexdigest()}
                    break
                print("  not an expression page:", c["url"][:150])
        if not ex:
            print(f"{work}: no usable archived page")
            continue
        pins["acts"][work] = {"expressions": ex}
        latest = ex[max(ex)]
        info = page_info(cache.get(latest["url"]))
        for item in info["timeline"]:
            for ev in item["events"]:
                for href, _ in ev["links"]:
                    if href and "/akn/" in href and "@" not in href:
                        law_uris.add(re.sub(r"^/[a-z]{2}(?=/akn/)", "", href))
        # the LII's own listing: current expression date of the work (open page, not behind the challenge)
        year = work.split("/")[-2]
        if lii.get("listing", True) is False:  # e.g. Kenya Law: even the listing is behind its bot challenge
            print(f"{work}: {len(ex)}/{len(caps)} expressions archived and good: {sorted(ex)}")
            continue
        lst_url = f"https://{lii['hosts'][0]}{lii.get('listing_prefix', '')}/legislation/?years={year}"
        try:
            cache.get(lst_url)
            pins["listings"][work] = lst_url
        except RuntimeError as e:
            print("  listing", e)
        print(f"{work}: {len(ex)}/{len(caps)} expressions archived and good: {sorted(ex)}")
    # Amending laws' own pages (assent and publication dates for the commit trailers) cost two CDX queries each and
    # are rarely archived (none of Zambia's 10 were), so they are fetched only when acts.json asks: "law_pages": true.
    # Already-cached ones are always used.
    for uri in sorted(law_uris):
        work = re.sub(rf"^/akn/{lii['cc']}/act/", "", uri)
        if work in pins["acts"]:
            continue
        if not cfg.get("law_pages") and not all(cache.has(cdx_url(f"{h}{p}{uri}/eng@"))
                                                for h in lii["hosts"] for p in lii.get("path_prefixes", [""])):
            continue
        try:
            caps = captures(cfg, cache, work)
        except RuntimeError as e:
            print("  cdx", e)
            continue
        got = None
        for day, lst in caps.items():  # oldest expression first: the law as enacted
            for ts, orig in lst[:3]:
                u = raw(ts, orig)
                try:
                    b = cache.get(u)
                except RuntimeError:
                    continue
                if good_expression_page(b, f"{uri}/eng@{day}"):
                    got = {"expression": day, "capture": ts, "url": u, "sha256": hashlib.sha256(b).hexdigest()}
                    break
            if got:
                break
        pins["laws"][uri] = got
        print(f"law {uri}: {'archived ' + got['expression'] if got else 'no archived page'}")
    pins["retrieved"] = dt.date.today().isoformat() if "retrieved" not in cfg else cfg["retrieved"]
    tmp = folder / "sources.json.tmp"
    tmp.write_text(json.dumps(pins, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(folder / "sources.json")
    return pins


# ---------------------------------------------------------------- parse

def law_meta(info: dict) -> dict:
    """enacted (assent) and commenced/published dates from a law's own coverpage notices."""
    out = {}
    for n in info.get("notices", []):
        t = n["text"]
        if re.search(r"Assented to on", t):
            out["enacted"] = parse_date(t.split("Assented to on", 1)[1])
        if re.search(r"Commenced on", t):
            out["commenced"] = parse_date(t.split("Commenced on", 1)[1])
            out["commenced_text"] = t
        if re.search(r"Published in", t):
            out["published"] = parse_date(t.split(" on ", 1)[1]) if " on " in t else None
            out["published_text"] = t
    return out


def label_from(text: str, uri: str) -> str:
    """'(Act 13 of 2025)' / '(General Notice 2917 of 2024)' / '(Statutory Instrument 5 of 2020)' from an amendment
    list entry; else from the uri."""
    m = re.search(r"\(((?:Act|Act No\.|Statutory Instrument|General Notice|Legal Notice|Ordinance|Decree|Statute|"
                  r"Chapter|Cap\.?)[^()]*)\)", text)
    if m:
        return m.group(1).strip()
    k = law_key(uri).split("-")
    return f"{k[0].capitalize()} {k[-1]} of {k[-2]}" if len(k) >= 3 else uri


def _names_law(remark: str, uri: str, amend_text: str) -> bool:
    """Does an editorial note's plain text name this law? Matches the number and year of the law's own label, in the
    forms LIIs print: "Act No. 19 of 2015", "Act 19 of 2015", "L.N. 61/2008", "Legal Notice 61 of 2008"."""
    k = law_key(uri).split("-")
    if len(k) < 3 or not k[-1].isdigit() or not k[-2].isdigit():
        return False
    sub, year, num = k[0], k[-2], k[-1]
    word = {"act": r"Act(?:\s+No\.?)?", "ln": r"(?:L\.\s?N\.?|Legal\s+Notice)(?:\s+No\.?)?",
            "si": r"(?:S\.\s?I\.?|Statutory\s+Instrument)(?:\s+No\.?)?"}.get(sub)
    if not word:
        return False
    return bool(re.search(rf"{word}\s*{num}\s*(?:of\s+{year}|/\s*{year})", remark))


def kind_of_law(uri: str) -> str:
    sub = law_key(uri).split("-")[0]
    return "law" if sub in ("act", "ord", "statute", "decree", "cap") else "decree"


def parse(folder: Path, docs_date: str | None = None) -> dict:
    folder = Path(folder)
    cfg = load_config(folder)
    pins = json.loads((folder / "sources.json").read_text(encoding="utf-8"))
    cache = Cache(folder, offline=True)
    lii = cfg["lii"]
    laws: dict = {}
    acts = []
    decisions = list(cfg.get("decisions", [])) + [
        f"Version dates are {lii['name']}'s expression dates. Laws.Africa's terminology guide "
        f"(https://docs.laws.africa/getting-started/terminology-guide) says \"Amendments to Principal works come into "
        f"force on the Commencement date of the Amending work\" and that the first point in time is \"the work as "
        f"originally published\"; so an amendment's expression is dated by its commencement (in force), and an act's "
        f"original expression by its publication, which is replaced by the commencement date the page states.",
        f"Credits: a version whose History names exactly one amending law (and no consolidation) between it and the "
        f"previous version is credited to that law for every provision that changed. Otherwise a provision is "
        f"credited only to laws that {lii['name']}'s editorial note inside that provision links to; the rest are "
        f"unexplained (publisher).",
        "Editorial notes (akn-remark) are left out of the text and used only as credit evidence, except where a "
        "provision has no other text (repealed or spent), where the note is the provision's whole printed content.",
        "Part, Chapter and Division headings are left out; each provision file starts with its own number and heading. "
        "Every other text of each version is in a provision file: parse.py checks this per version "
        "(verification.json, fidelity)."]
    report: dict = {"acts": {}}
    titles: dict[str, str] = {}
    law_pages = {uri: (page_info(cache.get(p["url"])) if p else None) for uri, p in pins["laws"].items()}

    def ensure_law(uri: str, title: str, amend_text: str = "") -> str:
        uri = re.sub(r"^/[a-z]{2}(?=/akn/)", "", uri)
        key = law_key(uri)
        if key in laws:
            return key
        pi = law_pages.get(uri)
        meta = law_meta(pi) if pi else {}
        laws[key] = {"label": label_from(amend_text, uri), "title": (pi or {}).get("title") or title or titles.get(uri, ""),
                     "kind": kind_of_law(uri), "enacted": meta.get("enacted"),
                     "published": meta.get("published"),
                     "url": f"https://{lii['hosts'][0]}{uri}", "temporary_until": None, "restores": None,
                     "note": None}
        laws[key]["_commenced"] = meta.get("commenced")
        return key

    for act in cfg["acts"]:
        work = act["work"]
        ex = pins["acts"][work]["expressions"]
        days = sorted(ex)
        latest = page_info(cache.get(ex[days[-1]]["url"]))
        timeline = sorted([t for t in latest["timeline"] if t["date"]], key=lambda t: t["date"])
        listed = [t["date"] for t in timeline if t["read"]] + [days[-1]]
        amend_text = {re.sub(r"^/[a-z]{2}(?=/akn/)", "", a["uri"] or ""): a["text"] for a in latest["amendments"]}
        for t in timeline:  # the LII's own titles for the laws its History names
            for e in t["events"]:
                for href, title in e["links"]:
                    if href and "@" not in href and title:
                        titles.setdefault(re.sub(r"^/[a-z]{2}(?=/akn/)", "", href), title)
        missing = sorted(set(listed) - set(days))
        if missing:
            decisions.append(f"{act['short']}: the LII lists expression(s) {', '.join(missing)}, but the Internet "
                             f"Archive holds no copy, so their changes appear in the next version that is archived.")
        unapplied = [(t["date"], ev) for t in timeline for ev in t["events"] if ev["unapplied"]]
        for d, ev in unapplied:
            decisions.append(f"{act['short']}: the LII lists \"{ev['text']}\" ({d}) as not yet applied to its "
                             f"consolidated text; it is not in this history (no official text-layer wording applied).")
        if latest["unapplied_notice"]:
            decisions.append(f"{act['short']}: the LII's page says: {latest['unapplied_notice'][0]}")
        versions = []
        prev_units: dict = {}
        first_day = days[0]
        for i, day in enumerate(days):
            if docs_date and act.get("skip_future") and day > docs_date:
                continue
            b = cache.get(ex[day]["url"])
            pi = page_info(b)
            units, refs = units_of(b, act.get("attachment_prefix"))
            remarks = {k: u.pop("_remarks") for k, u in units.items()}
            report.setdefault("fidelity", {})[f"{act['slug']}@{day}"] = fidelity(b, act.get("attachment_prefix"), units)
            v = {"from": day, "source_url": ex[day].get("source_url") or ex[day]["url"], "sha256": hashlib.sha256(b).hexdigest()}
            prev_day = days[i - 1] if i else None
            window = [t for t in timeline if (prev_day is None or t["date"] > prev_day) and t["date"] <= day] if i else []
            ev_laws, consolidations, other = [], [], []
            for t in window:
                for e in t["events"]:
                    if e["unapplied"]:
                        continue
                    if e["kind"] in ("amended", "repealed"):
                        for href, title in e["links"]:
                            if href and "/akn/" in href and "@" not in href:
                                u = re.sub(r"^/[a-z]{2}(?=/akn/)", "", href)
                                ev_laws.append((t["date"], u, title))
                    elif e["kind"] == "consolidation":
                        consolidations.append((t["date"], e["text"]))
                    elif e["kind"] != "commenced":
                        other.append((t["date"], e["text"]))
            if i == 0:
                v["units"] = {k: {"label": u["label"], "kind": u["kind"], "text": u["text"]} for k, u in units.items()}
                note = [f"The {lii['name']} version of {day}"]
                cons = [t for t in timeline if t["date"] == day and any(e["kind"] == "consolidation" for e in t["events"])]
                if cons:
                    txt = "; ".join(e["text"] for e in cons[0]["events"])
                    note.append(f"({txt})")
                    v["note"] = " ".join(note) + ": the oldest version the LII publishes."
                else:
                    v["note"] = " ".join(note) + ": the act as published."
            else:
                changes = {}
                for k in sorted(set(prev_units) | set(units)):
                    a = prev_units.get(k)
                    c = units.get(k)
                    if (a and a["text"]) != (c and c["text"]):
                        changes[k] = ({"label": c["label"], "kind": c["kind"], "text": c["text"]} if c else None)
                v["changes"] = changes
                credits = {}
                window_uris = {u for _, u, _ in ev_laws}
                for k in changes:
                    named = [r for r in refs.get(k, []) if re.sub(r"^/[a-z]{2}(?=/akn/)", "", r) in window_uris]
                    # Plain-text notes (Kenya Law: "[Act No. 19 of 2015, s. 143.]") name laws without links.
                    named += [u for u in window_uris
                              if any(_names_law(r, u, amend_text.get(u, "")) for r in remarks.get(k, []))]
                    named = sorted(set(named))
                    if named:
                        credits[k] = sorted({ensure_law(r, "", amend_text.get(r, "")) for r in named})
                    elif len(window_uris) == 1 and not consolidations:
                        (d0, u0, t0), = [x for x in ev_laws if x[1] in window_uris][:1]
                        credits[k] = [ensure_law(u0, t0, amend_text.get(u0, ""))]
                for _, u, t in ev_laws:
                    ensure_law(u, t, amend_text.get(u, ""))
                v["credits"] = credits
                notes = []
                if consolidations:
                    notes.append("This version is a consolidation: " + "; ".join(f"{t} ({d})" for d, t in consolidations) + ".")
                if len(window_uris) > 1 or (window_uris and consolidations):
                    named_laws = ", ".join(f"{laws[law_key(u)]['label']} ({d})" for d, u, _ in ev_laws)
                    notes.append(f"It also takes in {named_laws}; the LII does not say which provision each made "
                                 f"except where its own note does, so the rest is not credited.")
                if other:
                    notes.append("; ".join(f"{t} ({d})" for d, t in other))
                if notes:
                    v["note"] = " ".join(notes)
                if not changes and not credits:
                    v.pop("changes")
            versions.append(v)
            prev_units = units
            report["acts"].setdefault(act["slug"], []).append({"from": day, "units": len(units),
                                                                "changed": len(v.get("changes", {})),
                                                                "credited": len(v.get("credits", {}))})
        # first_law: the act as enacted when the oldest expression is the enactment itself (no consolidation, no
        # amendment on that day); otherwise the oldest version available, credited to the publisher.
        own = work_uri(cfg, work)
        first_events = [e for t in timeline if t["date"] == first_day for e in t["events"]]
        as_enacted = not any(e["kind"] in ("consolidation", "amended") for e in first_events)
        first_law = None
        earlier = []
        if as_enacted:
            first_law = ensure_law(own, latest.get("title", act["title"]), f"({act['label']})")
            meta = law_meta(page_info(cache.get(ex[first_day]["url"])))
            laws[first_law].update(label=act["label"], title=latest.get("title") or act["title"],
                                   enacted=meta.get("enacted"), published=meta.get("published"))
            # The original expression is dated by its Gazette publication; the act took effect on its commencement
            # date, which the LII states on the same page ("Commenced on D [by <order>]"). Date the first version by
            # that, if it falls before the next version.
            com = meta.get("commenced")
            nxt = versions[1]["from"] if len(versions) > 1 else "9999-12-31"
            if com and com != versions[0]["from"] and com < nxt:
                versions[0]["note"] = (f"The {lii['name']} expression of {first_day} (the act as published); in force "
                                       f"from {com}: \"{meta['commenced_text']}\".")
                versions[0]["from"] = com
                decisions.append(f"{act['short']}: the first version is dated {com}, the commencement date "
                                 f"{lii['name']} states (\"{meta['commenced_text']}\"), not {first_day}, the "
                                 f"date of its expression (Gazette publication).")
            elif not com:
                staged = [n["text"] for n in page_info(cache.get(ex[first_day]["url"]))["notices"]
                          if n["text"].startswith(("Commenced", "Note"))]
                decisions.append(f"{act['short']}: {lii['name']} gives no single commencement date "
                                 f"({'; '.join(staged) or 'none stated'}); the first version keeps its expression "
                                 f"date {first_day}, the Gazette publication.")
                report.setdefault("staged_commencement", []).append(act["slug"])
            elif com and com > first_day:
                decisions.append(f"{act['short']}: {lii['name']} gives the commencement as \"{meta['commenced_text']}\", "
                                 f"after the next version; the first version keeps its expression date {first_day}.")
        else:
            for _, u, t in [(t["date"], ln[0], ln[1]) for t in timeline if t["date"] < first_day
                            for e in t["events"] if e["kind"] == "amended" for ln in e["links"]]:
                earlier.append(ensure_law(u, t, amend_text.get(u, "")))
        # Provisions not yet in force: the coverpage says so; such text is in the expression but not law yet.
        for n in latest["notices"]:
            if re.search(r"not yet (commenced|in force)|uncommenced|have not commenced", n["text"], re.I):
                decisions.append(f"{act['short']}: {lii['name']} notes on its current version: {n['text']}")
        acts.append({"slug": act["slug"], "short": act["short"], "title": latest.get("title") or act["title"],
                     "url": f"https://{lii['hosts'][0]}{own}", "first_law": first_law, "earlier_laws": earlier,
                     "versions": versions})
        # check: the LII's own listing names the current expression
        lst = pins["listings"].get(work)
        if lst and cache.has(lst):
            t = cache.get(lst).decode("utf-8", "replace")
            m = re.search(rf'href="(?:/[a-z]{{2}})?{re.escape(own)}/eng@(\d{{4}}-\d{{2}}-\d{{2}})"', t)
            report["acts"][act["slug"] + ":listing"] = {"lii_current": m.group(1) if m else None, "ours": days[-1],
                                                        "ok": bool(m and m.group(1) == days[-1])}
    # check each law's own commencement against the days we date its changes (the expression date)
    used: dict[str, set] = {}
    for a in acts:
        for v in a["versions"]:
            for ks in v.get("credits", {}).values():
                for k in ks:
                    used.setdefault(k, set()).add(v["from"])
    report["law_dates"] = {k: {"commenced": laws[k].get("_commenced"), "dated": sorted(used.get(k, []))}
                           for k in sorted(laws)}
    for k in laws:
        laws[k].pop("_commenced", None)
    corpus = {"country": cfg["country"], "sources": [], "laws": dict(sorted(laws.items())), "acts": acts,
              "applies": [], "decisions": decisions, "ai_use": cfg.get("ai_use", ["none"])}
    n_req = sum(1 for _ in open(folder / ".cache" / "requests.jsonl", encoding="utf-8")) if (folder / ".cache" / "requests.jsonl").exists() else 0
    corpus["sources"] = [{**s, "requests": n_req if s.get("requests") == "count" else s.get("requests")}
                         for s in cfg.get("sources", [])]
    crawls = sorted({e["crawl"] for a in pins["acts"].values() for e in a["expressions"].values()
                     if e.get("via") == "commoncrawl"})
    if crawls:
        corpus["sources"].append({
            "name": "Common Crawl", "url": "https://commoncrawl.org", "retrieved": cfg.get("retrieved"),
            "requests": None, "licence": "Common Crawl terms of use (https://commoncrawl.org/terms-of-use); the "
                                         f"content's licence is {lii['name']}'s",
            "notes": f"Archived copies of {lii['name']} expression pages from crawls {', '.join(crawls)}, read by byte "
                     f"range from the WARC files on data.commoncrawl.org; crawl, file, offset and length are pinned in "
                     f"sources.json. Pages Common Crawl lacks were read from the Internet Archive."})
    return corpus, report


def summary(corpus: dict, report: dict) -> dict:
    out = {}
    for a in corpus["acts"]:
        vs = a["versions"]
        out[a["slug"]] = {"versions": len(vs), "from": [v["from"] for v in vs],
                          "units_first": len(vs[0].get("units", {})),
                          "changed": [len(v.get("changes", {})) for v in vs[1:]],
                          "credited": [len(v.get("credits", {})) for v in vs[1:]],
                          "listing": report["acts"].get(a["slug"] + ":listing")}
    out["laws"] = len(corpus["laws"])
    out["decisions"] = len(corpus["decisions"])
    return out


def _who(corpus: dict, act: dict, i: int) -> str:
    v = act["versions"][i]
    pub = corpus["country"]["publisher"]["name"]
    if i == 0:
        if act.get("first_law"):
            return corpus["laws"][act["first_law"]]["label"] + " (as enacted)"
        return f"publisher ({pub}): oldest version available"
    names = sorted({corpus["laws"][l]["label"] for ls in v.get("credits", {}).values() for l in ls})
    unexpl = [k for k in v.get("changes", {}) if k not in v.get("credits", {})]
    out = ", ".join(names)
    if unexpl:
        out += ("; " if out else "") + f"publisher ({pub}): {len(unexpl)} provision(s) unexplained"
    return out or "no change in words"


def readme(folder: Path, corpus: dict) -> str:
    """repo/README.md in the standard git-for-law shape, generated from corpus.json and acts.json, plus a hand-written
    repo/README.extra.md (country notes) if present."""
    folder = Path(folder)
    cfg = load_config(folder)
    c = corpus["country"]
    lii = cfg["lii"]
    host = lii["hosts"][0]
    a0 = corpus["acts"][0]
    # the example: the provision the first act changed most often, on its first day
    counts: dict[str, int] = {}
    for v in a0["versions"][1:]:
        for k in v.get("changes", {}):
            if k.startswith(("art-", "sec-")):
                counts[k] = counts.get(k, 0) + 1
    unit = max(sorted(counts), key=lambda k: counts[k]) if counts else next(
        (k for k in a0["versions"][0].get("units", {}) if k.startswith(("art-", "sec-"))), "sec-001")
    num = unit
    day = a0["versions"][0]["from"]
    L = [f"# {c['name']}: law history in git", "",
         f"The law of {c['name']} as a git history: one file per provision, one commit per law on the day it took "
         f"effect, and the law that made each change as the commit's author. `git blame` names the law behind every "
         f"paragraph; `git log` lists every change to a provision; `tools/on.py` gives the text in force on any day.",
         "", f"It follows the shared design of [lexifina/global-law](https://github.com/lexifina/global-law), which "
         f"places it at `{c['code'].lower()}/`. Every version is a dated point-in-time version published by "
         f"[{lii['name']}](https://{host}) on the Laws.Africa Peachjam platform.", "",
         "**What is in it now**", "", "| Folder | Act | Versions | History |", "| --- | --- | ---: | --- |"]
    for a in corpus["acts"]:
        vs = a["versions"]
        L.append(f"| `{a['slug']}/` | [{a['title']}]({a['url']}) | {len(vs)} | {vs[0]['from']} to {vs[-1]['from']} |")
    for a in corpus["acts"]:
        L += ["", f"**{a['title']}**", "", "| In force | Author |", "| --- | --- |"]
        for i, v in enumerate(a["versions"]):
            L.append(f"| {v['from']} | {_who(corpus, a, i)} |")
    L += ["", "Each folder's `README.md` lists every provision, how often it changed and when.", "",
          "## A lawyer's questions as git commands", "", "| Question | Command |", "| --- | --- |",
          f"| What did {unit} say on {day}? | `python tools/on.py {day} {a0['slug']} {num}` |",
          f"| The same, with raw git (bash) | `git show $(git rev-list -1 --before=\"{day}T23:59:59Z\" main -- "
          f"{a0['slug']}/{unit}.md):{a0['slug']}/{unit}.md` |",
          f"| The same, in PowerShell | `$r = git rev-list -1 --before=\"{day}T23:59:59Z\" main -- {a0['slug']}/{unit}.md; "
          f"git show \"$($r):{a0['slug']}/{unit}.md\"` |",
          f"| Which law wrote each line? | `git blame {a0['slug']}/{unit}.md` |",
          f"| Every change, word by word | `git log -p --word-diff {a0['slug']}/{unit}.md` |",
          "| Every law in the record, in order | `git log --reverse --format=\"%ad %an\" --date=short main` |",
          "| Everything one law changed | `git show law/<key>` (tags `law/<key>` mark each law's commit) |",
          f"| The whole act on a date | `python tools/on.py {day} {a0['slug']}` |",
          f"| Which law gave a provision its wording on a date | `python tools/on.py --law {day} {a0['slug']} {unit}` |",
          "", "After a rebuild, refresh tags with `git fetch --force --tags`: a plain fetch keeps stale tags.", "",
          "## Dates", "",
          f"- Each commit is dated at **noon, {c['tz']}, on the day the change took effect**. The day is also in the "
          f"`In-force:` trailer, which the tools read; enactment (assent) and Gazette publication dates are trailers "
          f"too, where {lii['name']} states them.",
          f"- **The day is {lii['name']}'s.** Each version is a Laws.Africa expression, and its date is the day the "
          f"amendment it takes in came into force, as the amendment list says (\"[Amended by <Act> on <date>]\"). "
          f"For a consolidation (a revised edition) it is the date the edition is as at. An act's original expression "
          f"is dated by its Gazette publication; where {lii['name']} gives a later commencement date (\"Commenced on "
          f"...\"), the first version is dated by that instead (see REPRODUCE.md, decisions).",
          "- `--before=\"YYYY-MM-DD\"` alone uses your clock's time of day, so a law that took effect that day may be "
          "missed before noon. Use `T23:59:59Z` as above, or the tool.", "",
          "## How it is checked", "",
          "- Every version is read back from git on the day it took effect and on the day before (`tools/check_repo.py`); "
          "both must match `corpus.json`. Results are in `REPRODUCE.md`.",
          f"- **Against {lii['name']} today:** the last version of each act is {lii['name']}'s current expression, as "
          f"named by its own legislation listing on the retrieval day, and is the text of that expression page.",
          f"- **Every version is its own dated expression**: each was parsed from an archived copy of exactly that "
          f"expression's page, whose sha256 is recorded with the version.",
          "- The repository is rebuilt from the same data a second time and must give identical hashes.", "",
          "## What \"author\" means", "",
          f"The author of a commit is the law that made the change, with an e-mail address that cannot exist, so "
          f"`git blame` and `git log --author` name laws. The committer is always Lexifina.", "",
          f"- **Credits come only from {lii['name']}'s own notes.** A version whose History entry names one amending "
          f"Act is credited to it. Where one version takes in several Acts, or a revised edition, a provision is "
          f"credited to an Act only if {lii['name']}'s editorial note in that provision names it "
          f"(\"[section 5 amended by section 2 of Act 3 of 2020]\"); the rest are committed by the publisher and "
          f"labelled \"unexplained\", and the commit message names the Acts the version takes in.",
          "- **The first commit** is the act as enacted where that is the oldest version; otherwise it is the oldest "
          "version available (a consolidation), credited to the publisher.",
          "- Blame credits whole lines (one paragraph per line). Use `git log -p --word-diff` to see exactly which words "
          "each change made.", "",
          "## What it does not show", "",
          f"- **Only the versions {lii['name']} publishes.** Changes before its oldest version are not separate commits.",
          f"- **Editorial notes.** {lii['name']}'s bracketed notes (\"[Act No. 18 of 1996]\", \"[section 5 amended by "
          f"...]\") are left out of the text and used only for credits, except where a provision has no other text "
          f"(repealed or spent), where the note is what {lii['name']} prints and is kept.",
          "- **Headings above the provision** (Part, Chapter, Division) are left out; each file starts with its own "
          "number and heading. Footnotes are kept at the end of the file.",
          "- **Amendments not yet applied.** Where the LII lists an amendment as not yet applied to its consolidated "
          "text, it is not in this history; REPRODUCE.md lists each one.",
          "- **No OCR.** Acts the LII shows only as scanned PDFs are not included.", ""]
    extra = folder / "repo" / "README.extra.md"
    if extra.exists():
        L += [extra.read_text(encoding="utf-8").rstrip(), ""]
    L += ["## How it is built", "",
          f"{lii['name']}'s document pages answer automated clients with a bot challenge, so `tools/fetch.py` reads "
          f"each expression page from its latest Internet Archive capture (the raw `id_` form), found through the "
          f"Wayback CDX index, with curl, cached by the sha256 of the URL; the capture timestamps and hashes are pinned "
          f"in `tools/sources.json`. `tools/parse.py` reads only that cache through `tools/peachjam.py`, the shared "
          f"adapter for every Peachjam LII: it splits the Akoma Ntoso HTML into one file per provision, takes dates "
          f"and credits from the LII's History tab, amendment list and editorial notes, and writes `corpus.json`; "
          f"the shared builder `tools/build.py` turns that into the commits. `REPRODUCE.md` lists every source, "
          f"command, tool version and decision, and the result of the hash-for-hash rebuild.", "",
          "## Sources", "", "| Source | What it gives | Used for |", "| --- | --- | --- |",
          f"| [{lii['name']}](https://{host}) | Dated point-in-time versions (expressions) of each act, its History "
          f"and amendment list, and per-provision editorial notes; its listing page names the current version | "
          f"The text and dates of every version |",
          "| [Internet Archive](https://web.archive.org/) | Archived copies of those expression pages | Reading them |",
          "", "## Licence", "",
          f"See [LICENSE](LICENSE). {c['licence_note']}", "",
          f"{lii['name']}'s terms: {cfg['sources'][0]['licence']}. Lexifina's arrangement, messages, tables and "
          f"tools are CC0.", "",
          f"This repository is not legal advice. {c['name']}'s laws are published in English, so there is no separate "
          f"summary in another language.", ""]
    return "\n".join(L)


def licence(folder: Path) -> str:
    cfg = load_config(folder)
    lii = cfg["lii"]
    host = lii["hosts"][0]
    s = cfg["sources"][0]
    return (f"The legal texts come from {s['name']}:\n\n"
            f"  {lii['name']}, https://{host}, point-in-time versions of each act, read from archived copies of its\n"
            f"  pages on the Internet Archive (https://web.archive.org), retrieved {cfg['retrieved']}.\n\n"
            f"Licence and terms, as {lii['name']} states them: {s['licence']}.\n"
            f"CC BY-NC 4.0: https://creativecommons.org/licenses/by-nc/4.0/legalcode\n\n"
            f"Attribution:\n\n  {cfg['country']['licence_note']}\n\n"
            f"The texts may be used only for non-commercial purposes. This repository is private; whether and how it\n"
            f"may be published is the owner's decision under these terms.\n\n"
            f"Changes made by Lexifina: each version was converted to one Markdown file per provision, one paragraph per\n"
            f"line; spacing, quotes and dashes were normalised; editorial notes, Part and Chapter headings were left out;\n"
            f"and the versions were arranged as git commits credited to the laws {lii['name']} names for each change.\n"
            f"The wording of the law was not changed. Neither {lii['name']} nor Laws.Africa endorses this repository.\n\n"
            f"Lexifina's own contributions (the arrangement of the history, the commit messages, the tables and the\n"
            f"tools) are dedicated to the public domain under CC0 1.0 Universal:\n"
            f"https://creativecommons.org/publicdomain/zero/1.0/legalcode\n")


def write_docs(folder: Path, corpus: dict) -> None:
    """Write repo/README.md, repo/LICENSE and repo/jurisdiction.json's build line (only when they change)."""
    folder = Path(folder)
    repo = folder / "repo"
    repo.mkdir(exist_ok=True)
    files = {"README.md": readme(folder, corpus), "LICENSE": licence(folder)}
    j = repo / "jurisdiction.json"
    if j.exists():
        jd = json.loads(j.read_text(encoding="utf-8"))
        jd["build"] = "built: " + "; ".join(f"{a['title']} ({len(a['versions'])} version{'s' if len(a['versions']) != 1 else ''}, {a['versions'][0]['from']} "
                                           f"to {a['versions'][-1]['from']})" for a in corpus["acts"])
        jd["sources"] = len(corpus["sources"])
        files["jurisdiction.json"] = json.dumps(jd, indent=2, ensure_ascii=False) + "\n"
    for name, text in files.items():
        p = repo / name
        if not p.exists() or p.read_text(encoding="utf-8") != text:
            p.write_text(text, encoding="utf-8", newline="\n")


def write_corpus(folder: Path, corpus: dict) -> None:
    folder = Path(folder)
    tmp = folder / "corpus.json.tmp"
    tmp.write_text(json.dumps(corpus, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, folder / "corpus.json")


def vendor(folder: Path) -> None:
    """Copy this module into the country folder, so the country's repository ships the exact adapter it was built
    with (autopush ships every .py in the folder into tools/)."""
    src = Path(__file__).resolve()
    dst = Path(folder) / "peachjam.py"
    if src != dst.resolve() and (not dst.exists() or dst.read_bytes() != src.read_bytes()):
        dst.write_bytes(src.read_bytes())


if __name__ == "__main__":
    cmd, folder = sys.argv[1], Path(sys.argv[2])
    if cmd == "fetch":
        fetch(folder)
    elif cmd == "parse":
        c, r = parse(folder)
        write_corpus(folder, c)
        print(json.dumps(r, indent=1))
