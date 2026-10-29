"""Fetch the latest (or earliest with --first) archive.org capture of each PacLII path from a CDX listing.
Usage: grab.py CDXJSON REGEX [--first]   prints ts, url, cache path, size"""
import json, re, sys, os
from concurrent.futures import ThreadPoolExecutor
import fetch  # noqa
sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common')
import wayback
from pathlib import Path
CACHE = Path(fetch.CACHE)
rows = json.load(open(sys.argv[1]))
rx = re.compile(sys.argv[2])
first = '--first' in sys.argv
best = {}
for r in rows:
    p = re.sub(r'^https?://[^/]+', '', r['original']).rstrip('/')
    p = re.sub(r'/index\.html$', '', p)
    if not rx.search(p) or '?' in p:
        continue
    k = p
    if k not in best or (r['timestamp'] < best[k]['timestamp'] if first else r['timestamp'] > best[k]['timestamp']):
        best[k] = r
def go(k):
    r = best[k]
    b = fetch.ia(r['timestamp'], r['original'])
    return r['timestamp'], r['original'], wayback._cached(CACHE, fetch.ia_key(r['timestamp'], r['original'])), len(b) if b else None
with ThreadPoolExecutor(6) as ex:
    for res in ex.map(go, sorted(best)):
        print(*res)
