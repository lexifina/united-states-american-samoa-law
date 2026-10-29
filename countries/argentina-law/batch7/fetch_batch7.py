"""Batch 7 fetcher (gitlaw-AR-3): caches every page parse_batch7.py reads.

    python -X utf8 batch7/fetch_batch7.py pin        # pins the archived capture sets (CDX) into batch7/snapshots.json
    python -X utf8 batch7/fetch_batch7.py archive    # the pinned Wayback Machine captures (gitlaw_common/wayback.py)
    python -X utf8 batch7/fetch_batch7.py infoleg    # InfoLEG: today's consolidated sub-pages and the amending norms

The Código Aduanero (Ley 22.415, InfoLEG id 16536) has no original text on InfoLEG (norma.htm is an error page) and
its consolidated text is split over 29 sub-pages listed by texact.htm. Its oldest full text is that set of sub-pages
as the Internet Archive captured it in April 2013; later sets are read only to check the replay.
"""
from __future__ import annotations

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, r"C:/Users/alany/Documents/lexifina/scripts/gitlaw_common")
import fetch as F  # noqa: E402
import htmltext as H  # noqa: E402
import parse as P  # noqa: E402

NID = 16536
SNAP_FILE = HERE / "snapshots.json"
# (host as captured, month): the base set first, then the check sets
SETS = [("www.infoleg.gov.ar", "201304"), ("infoleg.mecon.gov.ar", "201412"), ("servicios.infoleg.gob.ar", "201606"),
        ("servicios.infoleg.gob.ar", "202312"), ("servicios.infoleg.gob.ar", "202409")]


def subpages() -> list[str]:
    s = H.decode(F.cached(F.norma_url(NID, "texact.htm")))
    links = re.findall(r'href="([^"]+\.htm)"', s, re.I)
    return [l for l in sorted(set(links), key=links.index) if "antecedentes" not in l]


def pin() -> None:
    import wayback
    out = []
    for host, month in SETS:
        rows = wayback.captures(f"{host}/infolegInternet/anexos/15000-19999/{NID}/", match="prefix", cache=F.CACHE)
        pages = {}
        for r in sorted(rows, key=lambda r: r["timestamp"]):
            name = r["original"].split("/")[-1].split("?")[0]
            if r["timestamp"].startswith(month) and name in subpages() and name not in pages:
                pages[name] = (r["timestamp"], r["original"])
        out.append({"host": host, "month": month, "pages": {p: pages[p] for p in subpages() if p in pages}})
        print(host, month, len(pages), "of", len(subpages()))
    tmp = SNAP_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    tmp.replace(SNAP_FILE)


def archive() -> None:
    import wayback
    sets = json.loads(SNAP_FILE.read_text(encoding="utf-8"))
    jobs = [(ts, url) for s in sets for ts, url in s["pages"].values()]
    with ThreadPoolExecutor(4) as ex:
        for (ts, url), b in zip(jobs, ex.map(lambda j: wayback.get(j[1], ts=j[0], cache=F.CACHE), jobs)):
            print(len(b) if b else None, ts, url, flush=True)


def infoleg(extra: list[int]) -> None:
    import wayback
    urls = [F.norma_url(NID, "texact.htm"), F.vinculos_url(NID, 2), F.ficha_url(NID)] + [F.norma_url(NID, p) for p in subpages()]
    ids = set(extra)
    for p in subpages():
        ids |= {int(x) for l in H.lines(F.cached(F.norma_url(NID, p))) for x in H.LINK_RE.findall(l)}
    ids |= {m["id"] for m in P.modifiers(NID)}
    B = P.bulk()
    ids = sorted(i for i in ids if i in B and B[i]["tipo_norma"] in ("Ley", "Decreto") and (B[i]["fecha_boletin"] or "") > "2013-04-19")
    urls += [F.norma_url(i) for i in ids] + [F.ficha_url(i) for i in ids]
    todo = [u for u in urls if F.cached(u) is None]
    print(len(ids), "norms,", len(todo), "pages to fetch", flush=True)

    def one(u: str):
        b = wayback.host_get(u, cache=F.CACHE)
        return u, b

    with ThreadPoolExecutor(8) as ex:
        for u, b in ex.map(one, todo):
            print(len(b) if b else None, u, flush=True)


def main(argv: list[str]) -> None:
    if argv and argv[0] == "pin":
        pin()
    elif argv and argv[0] == "archive":
        archive()
    elif argv and argv[0] == "infoleg":
        infoleg([int(x) for x in argv[1:]])


if __name__ == "__main__":
    main(sys.argv[1:])
