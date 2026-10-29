"""Survey candidate TanzLII works: archived expressions (archive.org CDX through the shared gitlaw_common/wayback.py
client) and, from the newest good capture, the title and the expressions the LII itself lists (History tab).

    python -X utf8 scripts/tanzania-law/survey.py 2011/4 1994/7 ...    -> .tmp/survey.jsonl
"""
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "africa-law"))
sys.path.insert(0, str(HERE.parent / "gitlaw_common"))
import peachjam  # noqa: E402
import wayback  # noqa: E402

CACHE = HERE / ".cache"
PREFIXES = ["tanzlii.org/akn/tz/act/", "tanzlii.org/en/akn/tz/act/"]


def expr_captures(work: str) -> dict:
    out: dict = {}
    for pre in PREFIXES:
        for r in wayback.captures(f"{pre}{work}/eng@", match="prefix", cache=CACHE, collapse=None):
            o = r["original"].replace("%40", "@")
            m = re.search(r"/eng@(\d{4}-\d{2}-\d{2})/?$", o)
            if m and "?" not in o and "html" in r["mimetype"]:
                out.setdefault(m.group(1), []).append((r["timestamp"], r["original"], int(r["length"] or 0)))
    for d in out:
        lst = sorted(set(out[d]), reverse=True)
        big = max(x[2] for x in lst)
        out[d] = [x for x in lst if x[2] >= big / 2] + [x for x in lst if x[2] < big / 2]
    return dict(sorted(out.items()))


def one(work: str) -> dict:
    caps = expr_captures(work)
    if not caps:
        return {"work": work, "archived": []}
    day = max(caps)
    for ts, orig, _ in caps[day][:4]:
        b = wayback.get(orig, ts=ts, cache=CACHE)
        if b and peachjam.good_expression_page(b, f"/akn/tz/act/{work}/eng@{day}"):
            info = peachjam.page_info(b)
            return {"work": work, "title": info.get("title"), "archived": sorted(caps),
                    "lii_listed": sorted({t["date"] for t in info["timeline"] if t["read"]} | {day}),
                    "timeline": [(t["date"], [e["kind"] + ": " + e["text"][:100] for e in t["events"]])
                                 for t in info["timeline"]],
                    "notices": [n["text"][:200] for n in info["notices"]], "unapplied": info["unapplied_notice"]}
    return {"work": work, "archived": sorted(caps), "error": "no good page for " + day}


if __name__ == "__main__":
    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(one, sys.argv[1:]))
    with open(HERE / ".tmp" / "survey.jsonl", "a", encoding="utf-8") as f:
        for r in res:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    for r in res:
        print(r["work"], r.get("title"), "archived", r["archived"], "listed", r.get("lii_listed"), r.get("error", ""))
