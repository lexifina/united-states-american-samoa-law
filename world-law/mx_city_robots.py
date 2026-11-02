"""Private. robots.txt of candidate official Mexican municipal hosts, one request per host, in sequence (3 s apart).
    python -X utf8 scripts/world-law/mx_city_robots.py host1 host2 ...
Results: scripts/world-law/.mx-cities/robots/<host>.txt (or .ERR)."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from br_city_get import Host, Stop
out = Path(__file__).resolve().parent / '.mx-cities' / 'robots'
out.mkdir(parents=True, exist_ok=True)
for host in sys.argv[1:]:
    h = Host(out / 'cache' / host.replace(':', '_'), host, timeout=30)
    try:
        b = h.get(f'https://{host}/robots.txt')
        (out / f"{host.replace(':', '_')}.txt").write_bytes(b if b is not None else b'(404)')
        print(host, 'ok' if b is not None else '404', (b or b'')[:300].decode('utf-8','replace').replace('\n',' | '), flush=True)
    except Stop as e:
        (out / f'{host}.ERR').write_text(str(e), encoding='utf-8')
        print(host, 'ERR', str(e)[:160], flush=True)
    time.sleep(3)
