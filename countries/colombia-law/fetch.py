"""Fetch Colombian law sources into .cache/ (curl, polite, resumable).

Source: Secretaría General del Senado, "basedoc" (Leyes desde 1992 - Vigencia
expresa y control de constitucionalidad, compiled by Avance Jurídico).
A basedoc document is a base page `<name>.html`, its continuation pages
`<name>_prNNN.html`, and one JavaScript file per page (`js/<page>.js`) that
holds the note boxes (Notas de Vigencia, Jurisprudencia Vigencia,
Legislación Anterior ...).

Usage:
    python -X utf8 fetch.py doc constitucion_politica_1991 [more names...]
    python -X utf8 fetch.py url <url> [...]
    python -X utf8 fetch.py all          # every document listed in DOCS
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, ".cache")
LOG = os.path.join(CACHE, "requests.jsonl")
UA = "lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)"
BASE = "http://www.secretariasenado.gov.co/senado/basedoc/"

# Documents used by parse.py (basedoc names).
DOCS = [
    "constitucion_politica_1991",
    "codigo_civil",
    "ley_1581_2012",
]

# Registraduría Nacional del Estado Civil pages that date the elections some Actos Legislativos take effect on
# (Wayback captures are pinned by timestamp so parse.py stays reproducible).
ELECTION_SOURCES = [
    "https://www.registraduria.gov.co/Calendario-Electoral-2006-2010.html",
    "https://web.archive.org/web/20070930160642id_/http://www.registraduria.gov.co/",
    "https://web.archive.org/web/20110726040247id_/http://www.registraduria.gov.co/ESTA-LISTO-EL-PRE-CALENDARIO.html",
]

_last: dict[str, float] = {}


def cache_path(url: str) -> str:
    return os.path.join(CACHE, hashlib.sha256(url.encode("utf-8")).hexdigest())


def cached(url: str) -> bytes | None:
    p = cache_path(url)
    if os.path.exists(p):
        with open(p, "rb") as f:
            return f.read()
    return None


def get(url: str, force: bool = False) -> bytes | None:
    """Return the bytes for url, from the cache or by one curl request."""
    os.makedirs(CACHE, exist_ok=True)
    p = cache_path(url)
    if not force and os.path.exists(p):
        with open(p, "rb") as f:
            return f.read()
    host = urlparse(url).netloc
    wait = 1.05 - (time.time() - _last.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    tmp = p + ".part"
    for attempt in range(4):
        _last[host] = time.time()
        r = subprocess.run(
            ["curl", "-sS", "-L", "--compressed", "--max-time", "120", "-A", UA,
             "-o", tmp, "-w", "%{http_code} %{content_type} %{size_download}", url],
            capture_output=True, text=True)
        out = (r.stdout or "").split(" ")
        status = int(out[0]) if out and out[0].isdigit() else 0
        rec = {"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "url": url, "status": status,
               "type": out[1] if len(out) > 1 else "", "bytes": int(out[2]) if len(out) > 2 and out[2].isdigit() else 0,
               "err": r.stderr.strip()[:200]}
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if status == 200:
            os.replace(tmp, p)
            with open(p, "rb") as f:
                return f.read()
        if status == 404:
            break
        time.sleep(3 * (attempt + 1))
    if os.path.exists(tmp):
        os.remove(tmp)
    return None


def fetch_doc(name: str) -> list[str]:
    """Fetch a basedoc document: base page, its prNNN pages and their JS files."""
    urls = []
    base = BASE + name + ".html"
    raw = get(base)
    if raw is None:
        print("missing", base)
        return urls
    urls.append(base)
    text = raw.decode("latin-1")
    pages = sorted(set(re.findall(r'value="_pr(\d{3})', text)) |
                   set(re.findall(re.escape(name) + r"_pr(\d{3})\.html", text)))
    names = [name] + [f"{name}_pr{n}" for n in pages]
    for n in names[1:]:
        u = BASE + n + ".html"
        if get(u) is not None:
            urls.append(u)
    for n in names:
        u = BASE + "js/" + n + ".js"
        page = cached(BASE + n + ".html") or b""
        if b"js/" + n.encode() + b".js" in page and get(u) is not None:
            urls.append(u)
    return urls


def main(argv: list[str]) -> None:
    if not argv:
        print(__doc__)
        return
    cmd, rest = argv[0], argv[1:]
    if cmd == "doc":
        for n in rest:
            print(n, len(fetch_doc(n)))
    elif cmd == "url":
        for u in rest:
            b = get(u)
            print(u, None if b is None else len(b))
    elif cmd == "all":
        for n in DOCS:
            print(n, len(fetch_doc(n)))
        for u in ELECTION_SOURCES:
            b = get(u)
            print(u, None if b is None else len(b))
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
