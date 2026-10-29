import sys, json
sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common'); import wayback
CACHE = r'C:/Users/alany/Documents/lexifina/scripts/burkina-faso-law/.cache'
url = sys.argv[1]; n = int(sys.argv[2]) if len(sys.argv) > 2 else 12
which = sys.argv[3] if len(sys.argv) > 3 else 'cc'
if which == 'cc':
    recs = wayback.cc_captures(url, match='prefix', crawls=wayback.cc_crawls(CACHE)[:n], cache=CACHE)
else:
    recs = wayback.captures(url, match='prefix', cache=CACHE)
print(len(recs))
seen = {}
for r in recs:
    u = r.get('url') or r.get('original')
    seen.setdefault(u, []).append(r.get('timestamp'))
for u, ts in sorted(seen.items()):
    print(u, len(ts), min(ts), max(ts), r.get('mime') or r.get('mimetype'))
