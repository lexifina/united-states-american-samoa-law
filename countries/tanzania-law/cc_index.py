"""List every Common Crawl capture of TanzLII act pages (/akn/tz/act/...) in the recent crawls; writes
.cache/cc_index.json (records with crawl, timestamp, url, status, WARC filename/offset/length).

    python -X utf8 scripts/tanzania-law/cc_index.py [n_crawls]
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "gitlaw_common"))
import wayback  # noqa: E402

CACHE = HERE / ".cache"
n = int(sys.argv[1]) if len(sys.argv) > 1 else 16
crawls = wayback.cc_crawls(CACHE)[:n]
with ThreadPoolExecutor(4) as ex:
    parts = list(ex.map(lambda c: wayback.cc_captures("tanzlii.org/akn/tz/act/", crawls=[c], match="prefix",
                                                      cache=CACHE), crawls))
recs = [r for p in parts for r in p]
(CACHE / "cc_index.json").write_text(json.dumps({"crawls": crawls, "records": recs}, indent=0), encoding="utf-8")
print(len(crawls), "crawls", len(recs), "records")
