"""Polite curl cache for the Guinea build: sha256(url) file names, requests.jsonl log, resumable.

Direct official sources only (journal-officiel.sgg.gov.gn, sgg.gov.gn). Archive.org and Common Crawl go through
scripts/gitlaw_common/wayback.py.
"""
import hashlib
import json
import os
import subprocess
import threading
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, '.cache')
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
_lock = threading.Lock()
_last = {}
RATE = 1 / 3.0  # SPEED RULE: up to 3 requests a second per direct official host


def path_for(url):
    return os.path.join(CACHE, hashlib.sha256(url.encode('utf-8')).hexdigest())


def cached(url):
    p = path_for(url)
    return p if os.path.exists(p) else None


def read(url):
    p = cached(url)
    if not p:
        raise FileNotFoundError(url)
    with open(p, 'rb') as f:
        return f.read()


def sha256_of(url):
    return hashlib.sha256(read(url)).hexdigest()


def get(url, timeout=180):
    p = path_for(url)
    if os.path.exists(p):
        return p
    os.makedirs(CACHE, exist_ok=True)
    host = url.split('/')[2]
    with _lock:
        wait = _last.get(host, 0) + RATE - time.time()
        if wait > 0:
            time.sleep(wait)
        _last[host] = time.time()
    tmp = p + '.part'
    r = subprocess.run(['curl', '-s', '-L', '--compressed', '-m', str(timeout), '-A', UA, '-o', tmp,
                        '-w', '%{http_code} %{content_type}', url], capture_output=True, text=True)
    status, _, ctype = (r.stdout or '000 ').partition(' ')
    size = os.path.getsize(tmp) if os.path.exists(tmp) else 0
    rec = {'t': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'url': url, 'status': status,
           'type': ctype, 'bytes': size}
    ok = status == '200' and size > 0
    if ok:
        with open(tmp, 'rb') as f:
            rec['sha256'] = hashlib.sha256(f.read()).hexdigest()
        os.replace(tmp, p)
    elif os.path.exists(tmp):
        os.remove(tmp)
    with _lock, open(os.path.join(CACHE, 'requests.jsonl'), 'a', encoding='utf-8') as f:
        f.write(json.dumps(rec) + '\n')
    if not ok:
        raise RuntimeError(f'{status} {url}')
    return p
