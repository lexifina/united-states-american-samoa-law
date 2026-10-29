import sys, json; sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common'); import wayback
from pathlib import Path
C = Path(__file__).parent / '.cache'
for u in sys.argv[1:]:
    m = 'prefix' if u.endswith('*') else 'exact'
    caps = wayback.captures(u.rstrip('*'), match=m, cache=C)
    print('##', u, len(caps), flush=True)
    for c in caps: print(' ', c['timestamp'], c['original'], c['mimetype'], c['length'], c['digest'][:8], flush=True)
