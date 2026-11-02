"""Private. One polite GET via br_city_get.Host, cached under .ar-cities/cache/<host>.
    python -X utf8 scripts/world-law/ar_city_get.py <delay> <url> [<url> ...]   (sequential)
Prints status and size; body path."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from br_city_get import Host, Stop
BASE = Path(__file__).resolve().parent / '.ar-cities' / 'cache'
HOSTS = {}
def host(url, delay):
    n = url.split('/')[2]
    if n not in HOSTS:
        HOSTS[n] = Host(BASE / n, n, delay=delay, timeout=60)
    return HOSTS[n]
if __name__ == '__main__':
    d = float(sys.argv[1])
    for u in sys.argv[2:]:
        h = host(u, d)
        try:
            b = h.get(u)
            print(u, 'ok' if b is not None else '404', len(b or b''), h.path(u), flush=True)
        except Stop as e:
            print(u, 'STOP', e, flush=True)
