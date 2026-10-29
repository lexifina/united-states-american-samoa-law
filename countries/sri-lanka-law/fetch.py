"""Sri Lanka fetcher: curl into .cache/ named by sha256(url), every request logged.

Usage: python -X utf8 fetch.py [url ...]      (no args: the Phase 1 list in sources.json)
Polite: at most 3 requests a second per host (SPEED RULE), resumable (cached files are skipped).
"""
import hashlib, json, os, subprocess, sys, time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, '.cache')
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
_last = {}


def path_for(url):
    return os.path.join(CACHE, hashlib.sha256(url.encode()).hexdigest())


def fetch(url, force=False, timeout=120):
    os.makedirs(CACHE, exist_ok=True)
    p = path_for(url)
    if os.path.exists(p) and not force:
        return p
    host = url.split('/')[2]
    wait = 0.34 - (time.time() - _last.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    _last[host] = time.time()
    tmp = p + '.part'
    r = subprocess.run(['curl', '-s', '-L', '--compressed', '-A', UA, '-m', str(timeout),
                        '-o', tmp, '-w', '%{http_code} %{content_type}', url],
                       capture_output=True, text=True)
    code, _, ctype = (r.stdout or '000 ').partition(' ')
    size = os.path.getsize(tmp) if os.path.exists(tmp) else 0
    ok = code == '200' and size > 0
    sha = hashlib.sha256(open(tmp, 'rb').read()).hexdigest() if size else None
    with open(os.path.join(CACHE, 'requests.jsonl'), 'a', encoding='utf-8') as f:
        f.write(json.dumps({'url': url, 'status': code, 'type': ctype, 'bytes': size, 'sha256': sha,
                            'at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}) + '\n')
    if ok:
        os.replace(tmp, p)
        return p
    if os.path.exists(tmp):
        os.remove(tmp)
    return None


def main(urls):
    if not urls:
        src = json.load(open(os.path.join(HERE, 'sources.json'), encoding='utf-8'))
        urls = [d['url'] for d in src['documents']]
    for u in urls:
        p = fetch(u)
        print(('ok   ' if p else 'FAIL ') + u)


if __name__ == '__main__':
    main(sys.argv[1:])
