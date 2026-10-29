"""List Common Crawl captures under a URL prefix: python cc_probe.py <prefix> [ncrawls]"""
import sys
sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common'); import wayback
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
CACHE = Path(__file__).parent / '.cache'
crawls = wayback.cc_crawls(CACHE)
pref = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 12
def one(c):
    try: return wayback.cc_captures(pref, match='prefix', crawls=[c], cache=CACHE)
    except Exception: return []
with ThreadPoolExecutor(6) as ex:
    res = [r for rs in ex.map(one, crawls[:n]) for r in rs]
urls = {}
for r in res:
    urls.setdefault(r['url'], []).append((r['timestamp'], r['status'], r['crawl']))
for u in sorted(urls): print(u, len(urls[u]), sorted(urls[u])[-1])
