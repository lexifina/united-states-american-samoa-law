import sys, json
sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common'); import wayback
from pathlib import Path
CACHE = Path(__file__).parent / '.cache'
mode = sys.argv[1]
for host in sys.argv[2:]:
    if mode == 'ia':
        caps = wayback.captures(host, match='prefix', cache=CACHE)
    else:
        caps = wayback.cc_captures(host, match='prefix', crawls=wayback.cc_crawls(CACHE)[:int(mode)], cache=CACHE)
    print(host, len(caps))
    for c in caps[:8]: print('  ', c)
