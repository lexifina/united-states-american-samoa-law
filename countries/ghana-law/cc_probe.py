"""Probe Common Crawl for every archived GhaLII /akn/gh/act/ page: which works and expressions exist, per crawl.

    python -X utf8 scripts/ghana-law/cc_probe.py [n_crawls]

Writes .tmp/cc_index.json: {work: {expression date: [records...]}}.
"""
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "gitlaw_common"))
import wayback  # noqa: E402

CACHE = HERE / ".cache"
n = int(sys.argv[1]) if len(sys.argv) > 1 else 16
crawls = wayback.cc_crawls(CACHE)[:n]


def one(crawl):
    return wayback.cc_captures("ghalii.org/akn/gh/act/", crawls=[crawl], match="prefix", cache=CACHE)


with ThreadPoolExecutor(4) as ex:
    recs = [r for rs in ex.map(one, crawls) for r in rs]
out: dict = {}
for r in recs:
    m = re.search(r"/akn/gh/act/(.+?)/eng@(\d{4}-\d{2}-\d{2})/?$", r["url"].split("?")[0])
    if m and str(r.get("status")) == "200" and "html" in r.get("mime", ""):
        out.setdefault(m.group(1), {}).setdefault(m.group(2), []).append(r)
(HERE / ".tmp").mkdir(exist_ok=True)
(HERE / ".tmp" / "cc_index.json").write_text(json.dumps(out, indent=0, sort_keys=True), encoding="utf-8")
print(len(recs), "records;", len(out), "works;", sum(len(v) for v in out.values()), "expressions; crawls", crawls)
for w, d in sorted(out.items(), key=lambda x: -len(x[1]))[:25]:
    print(w, sorted(d))
for w in sorted(out):
    if "constitution" in w or w.startswith("1992") or w in ("1960/29", "2012/843", "2003/651", "2019/992", "1996/527"):
        print("**", w, {k: len(v) for k, v in sorted(out[w].items())})
