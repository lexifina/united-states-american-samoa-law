"""List Common Crawl captures under a URL prefix (gitlaw-SB probe). Usage: probe_cc.py PREFIX [NCRAWLS]"""
import json, sys, os
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common')
import wayback
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.cache')
prefix = sys.argv[1]; n = int(sys.argv[2]) if len(sys.argv) > 2 else 12
crawls = wayback.cc_crawls(CACHE)[:n]
with ThreadPoolExecutor(6) as ex:
    res = list(ex.map(lambda c: wayback.cc_captures(prefix, crawls=[c], match='prefix', cache=CACHE), crawls))
recs = [r for rs in res for r in rs]
out = os.path.join(CACHE, 'cc-' + prefix.replace('/', '_').replace(':', '') + f'-{n}.json')
json.dump(recs, open(out, 'w'), indent=0)
print(len(recs), out)
