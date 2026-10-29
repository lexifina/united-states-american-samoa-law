"""Probe: fetch one archive.org capture (id_) and save a copy under .cache/probe/ for reading."""
import sys, hashlib
from pathlib import Path
sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common')
import wayback

CACHE = Path(r'C:/Users/alany/Documents/lexifina/scripts/ukraine-law/.cache')

ts, url = sys.argv[1], sys.argv[2]
body = wayback.get(url, ts=ts, cache=CACHE)
if body is None:
    print('MISSING'); sys.exit(1)
out = CACHE / 'probe' / (sys.argv[3] if len(sys.argv) > 3 else hashlib.sha1(url.encode()).hexdigest()[:10] + '.html')
out.parent.mkdir(parents=True, exist_ok=True)
out.write_bytes(body)
print(len(body), out)
