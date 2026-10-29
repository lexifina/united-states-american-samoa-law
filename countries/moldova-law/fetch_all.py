"""Fill .cache/ with every source parse.py reads (resumable: cached files are not fetched again).

    python -X utf8 fetch_all.py
Internet Archive captures go through the shared client scripts/gitlaw_common/wayback.py (one machine-wide rate),
pinned by timestamp in parse.SOURCES; the Moldpres PDF and the Presidency page through fetch.py (curl).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "gitlaw_common"))
import wayback  # noqa: E402
import fetch  # noqa: E402
import parse  # noqa: E402

for ts, url in parse.SOURCES:
    b = wayback.get(url, ts=ts, cache=parse.CACHE)
    print("ok" if b else "MISSING", ts, url)
for url in (parse.MOLDPRES_2024, parse.PRES_PAGE):
    print(fetch.get(url), url)
