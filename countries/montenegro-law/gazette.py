"""Readers for the Official Gazette of Montenegro (sluzbenilist.me) act pages and their PDFs (cache only).

Act page  https://www.sluzbenilist.me/propisi/<id>           -> meta(id): title, issue, dates, amending acts
Act PDF   https://www.sluzbenilist.me/propisi/<id>/download  -> pdf_lines(id): text lines from the PDF text layer
No OCR: only the text layer the publisher embedded is read.
"""
import hashlib, html, os, re
import fitz  # PyMuPDF

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, ".cache")
BASE = "https://www.sluzbenilist.me/propisi/"


def cpath(url):
    return os.path.join(CACHE, hashlib.sha256(url.encode("utf-8")).hexdigest())


def page_url(i):
    return f"{BASE}{i}"


def pdf_url(i):
    return f"{BASE}{i}/download"


def sha(i):
    return hashlib.sha256(open(cpath(pdf_url(i)), "rb").read()).hexdigest()


def _dmy(s):
    d, m, y = s.strip(" .").split(".")
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"


def meta(i):
    s = open(cpath(page_url(i)), encoding="utf-8").read()
    s = re.sub(r"data:[a-z]+/[a-z]+;base64,[^\"]+", "", s)
    s = re.sub(r"<script.*?</script>", "", s, flags=re.S)
    t = re.sub(r'<a [^>]*href="https://www.sluzbenilist.me/propisi/(\d+)"[^>]*>', r" [[\1]] ", s)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"\s+", " ", html.unescape(t))
    out = {"id": i}
    m = re.search(r"\(PIS\) Objavljeno: [\d.]+ (.*?) Status: (\S+) Izdanje: (.*?) Registarski broj", t)
    out["title"], out["status"], out["issue"] = m.group(1).strip(), m.group(2), m.group(3).strip()
    for key, lab in (("published", "Datum objavljivanja"), ("in_force", "Datum stupanja na snagu"),
                     ("applies", "Datum početka primjene")):
        m = re.search(lab + r": (\d{1,2}\.\d{1,2}\.\d{4})", t)
        out[key] = _dmy(m.group(1)) if m else None
    m = re.search(r"Izmjene i/ili dopune (.*?)(?:Donesen na osnovu|Početak)", t)
    out["amended_by"] = re.findall(r"\[\[(\d+)\]\] ([^\[]+)", m.group(1)) if m else []
    out["amended_by"] = [(int(a), b.strip()) for a, b in out["amended_by"]]
    return out


def pdf_lines(i):
    """Text lines of the act PDF in reading order: list of (page, x0, text, bold, size)."""
    d = fitz.open(cpath(pdf_url(i)))
    out = []
    for pn, p in enumerate(d):
        for b in p.get_text("dict")["blocks"]:
            for ln in b.get("lines", []):
                spans = [sp for sp in ln["spans"] if sp["text"].strip()]
                if not spans:
                    continue
                txt = "".join(sp["text"] for sp in ln["spans"])
                bold = all("Bold" in sp["font"] or sp["flags"] & 16 for sp in spans)
                out.append((pn, round(ln["bbox"][0], 1), txt, bold, round(spans[0]["size"], 1)))
    return out
