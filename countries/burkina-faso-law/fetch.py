"""Burkina Faso: cached curl fetcher (sha256(url) names, requests.jsonl log). Direct official hosts <= 3 req/s."""
import hashlib, json, subprocess, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
_last = {}

def path(url: str) -> Path:
    return CACHE / hashlib.sha256(url.encode()).hexdigest()

def get(url: str, refresh: bool = False) -> bytes | None:
    p = path(url)
    if p.exists() and not refresh:
        return p.read_bytes()
    CACHE.mkdir(exist_ok=True)
    host = url.split('/')[2]
    wait = 0.34 - (time.time() - _last.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    _last[host] = time.time()
    tmp = p.with_suffix('.part')
    r = subprocess.run(['curl', '-s', '--compressed', '-L', '-m', '120', '-A', UA, '-o', str(tmp), '-w', '%{http_code}', url],
                       capture_output=True, text=True)
    code = int(r.stdout.strip() or 0)
    size = tmp.stat().st_size if tmp.exists() else 0
    with open(CACHE / 'requests.jsonl', 'a', encoding='utf8') as f:
        f.write(json.dumps({'t': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'url': url, 'code': code, 'bytes': size}) + '\n')
    if code != 200:
        tmp.unlink(missing_ok=True)
        return None
    tmp.replace(p)
    return p.read_bytes()

# What parse.py reads. With no arguments, fetch.py downloads exactly these.
BUILD_SOURCES = [
    'https://www.legiburkina.gov.bf/documents/b157d74c-23a1-4025-a8d6-0061e83df0c2/download',  # Constitution, 2015
]

if __name__ == '__main__':
    for u in sys.argv[1:] or BUILD_SOURCES:
        b = get(u)
        print(u, None if b is None else len(b), path(u).name)
