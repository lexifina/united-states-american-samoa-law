"""Batch 6 fetcher (gitlaw-AR-2): caches every page parse_batch6.py reads.

    python -X utf8 batch6/fetch_batch6.py            # InfoLEG pages (fetch.py: curl, sha256(url) cache, requests.jsonl)
    python -X utf8 batch6/fetch_batch6.py archive    # the pinned Wayback Machine captures (gitlaw_common/wayback.py)

InfoLEG serves no text of the Código Procesal Civil y Comercial or of the Código Procesal Penal before today's
consolidated text, so their oldest full text is InfoLEG's own consolidated page as the Internet Archive captured it
(SNAPSHOTS in parse_batch6.py); later captures are read only to check the replay.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
sys.path.insert(0, r"C:/Users/alany/Documents/lexifina/scripts/gitlaw_common")
import fetch as F  # noqa: E402
import htmltext as H  # noqa: E402
import parse as P  # noqa: E402


def candidates(nid: int, since: str) -> list[int]:
    """The norms amenders_of() would consider for act `nid`, without its "already cached" filter."""
    B = P.bulk()
    T = H.lines(F.cached(F.norma_url(nid, "texact.htm")))
    ids = {int(x) for l in T for x in H.LINK_RE.findall(l)} | {m["id"] for m in P.modifiers(nid)}
    plain = [H.strip_links(l) for l in T]
    laws_by_no = {}
    for k, r in B.items():
        if r["tipo_norma"] == "Ley":
            laws_by_no.setdefault(r["numero_norma"], k)
    tail = plain[plain.index("Antecedentes Normativos"):] if "Antecedentes Normativos" in plain else []
    for l in tail + [l for l in plain if l.startswith("(")]:
        for n in re.findall(r"Ley\s*N?[°º]?\s*([\d.]+)", l):
            if n.replace(".", "") in laws_by_no:
                ids.add(laws_by_no[n.replace(".", "")])
    return [i for i in sorted(ids) if i in B and B[i]["tipo_norma"] in ("Ley", "Decreto", "Acordada")
            and (B[i]["fecha_boletin"] or "") > since]


def main(argv: list[str]) -> None:
    import parse_batch6 as B6
    if argv and argv[0] == "archive":
        import wayback
        for slug in B6.SNAPSHOTS:
            for ts, url in B6.SNAPSHOTS[slug] + B6.CHECKS.get(slug, []):
                b = wayback.get(url, ts=ts, cache=F.CACHE)
                print(len(b) if b else None, ts, url, flush=True)
        return
    for a in B6.ACTS:
        for u in (F.norma_url(a["id"]), F.norma_url(a["id"], "texact.htm"), F.vinculos_url(a["id"], 2), F.ficha_url(a["id"])):
            b = F.get(u)
            print(len(b) if b else None, u, flush=True)
    for a in B6.ACTS:
        since = B6.SETUP[a["slug"]]["base_published"]
        for nid in candidates(a["id"], since) + B6.SETUP[a["slug"]].get("extra_ids", []):
            for u in (F.norma_url(nid), F.ficha_url(nid)):
                b = F.get(u)
                print(len(b) if b else None, nid, u, flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
