"""Probe Common Crawl for a URL prefix across the newest crawls: python -X utf8 cc_probe.py PREFIX [ncrawls]."""
import collections
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "gitlaw_common"))
import wayback  # noqa: E402

CACHE = Path(__file__).resolve().parent / ".cache"
n = int(sys.argv[2]) if len(sys.argv) > 2 else 12
crawls = wayback.cc_crawls(CACHE)[:n]
with ThreadPoolExecutor(6) as ex:
    res = list(ex.map(lambda c: wayback.cc_captures(sys.argv[1], crawls=[c], match="prefix", cache=CACHE), crawls))
recs = [r for rr in res for r in rr]
out = Path(__file__).resolve().parent / ".tmp" / "cc_probe.json"
out.write_text(json.dumps(recs), encoding="utf-8")
urls = collections.Counter(r["url"].split("?")[0] for r in recs if r.get("status") == "200")
print(len(recs), "records,", len(urls), "distinct 200 urls")
for u, c in sorted(urls.items()):
    print(c, u)
