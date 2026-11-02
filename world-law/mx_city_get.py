"""Private. One cached GET through br_city_get.Host (3 s apart per process, challenge/403 stop, TLS verified).
    python -X utf8 scripts/world-law/mx_city_get.py <url> [delay]   -> prints status, size, cache path"""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from br_city_get import Host, Stop
C = Path(__file__).resolve().parent / '.mx-cities' / 'cache'

def host(url, delay=3.0):
    h = url.split('/')[2]
    return Host(C / h.replace(':', '_'), h, delay=delay, timeout=90)

if __name__ == '__main__':
    for u in sys.argv[1:]:
        h = host(u)
        try:
            b = h.get(u)
            print('OK' if b is not None else '404', len(b or b''), h.path(u), flush=True)
        except Stop as e:
            print('STOP', e, flush=True)
        time.sleep(3)
