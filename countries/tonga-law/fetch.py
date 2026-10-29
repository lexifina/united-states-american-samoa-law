"""Polite, resumable, cached fetcher for Tonga sources (gitlaw-TO).

Cache: .cache/<sha256(url)>, one file per URL, plus .cache/requests.jsonl.
Direct official sites (ago.gov.to) at most 3 requests a second (SPEED RULE).
PacLII sits behind a bot challenge, so it is read only through Common Crawl
or archive.org via scripts/gitlaw_common/wayback.py.

Usage: python -X utf8 fetch.py URL [URL ...]   (prints cache path per URL)
"""
import hashlib
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, '.cache')
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
_last = {}


def path_for(url):
    return os.path.join(CACHE, hashlib.sha256(url.encode('utf-8')).hexdigest())


def get(url, refresh=False, data=None):
    """Return the cached bytes for url (POST form `data` if given), fetching once with curl."""
    os.makedirs(CACHE, exist_ok=True)
    key = url if data is None else url + ' POST ' + data
    p = path_for(key)
    if os.path.exists(p) and not refresh:
        with open(p, 'rb') as f:
            return f.read()
    host = url.split('/')[2]
    wait = 0.34 - (time.time() - _last.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    _last[host] = time.time()
    tmp = p + '.part'
    extra = [] if data is None else ['--data', data]
    r = subprocess.run(['curl', '-sS', '--compressed', '-L', '-A', UA, '-m', '180'] + extra + [
                        '-o', tmp, '-w', '%{http_code} %{content_type}', url.replace(' ', '%20')],
                       capture_output=True, text=True)
    code, _, ctype = r.stdout.partition(' ')
    size = os.path.getsize(tmp) if os.path.exists(tmp) else 0
    with open(os.path.join(CACHE, 'requests.jsonl'), 'a', encoding='utf-8') as f:
        f.write(json.dumps({'t': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'url': key,
                            'status': code, 'type': ctype, 'bytes': size}) + '\n')
    if r.returncode != 0 or code != '200':
        if os.path.exists(tmp):
            os.remove(tmp)
        raise RuntimeError(f'fetch failed {code} {r.stderr.strip()} {url}')
    os.replace(tmp, p)
    with open(p, 'rb') as f:
        return f.read()


if __name__ == '__main__':
    for u in sys.argv[1:]:
        get(u)
        print(path_for(u), u)
