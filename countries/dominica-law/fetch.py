"""Polite, cached, resumable fetcher for the Dominica law history.

Every request goes through curl (TLS chains fail with urllib on the build machine), is cached under
.cache/ by the sha256 of the request key (the URL, plus the POST body if any), and is logged to
.cache/requests.jsonl. At most 1 request a second per host.

    python -X utf8 fetch.py search <term> [title|year]   # laws portal search (POST), cached
    python -X utf8 fetch.py get <url>                     # any URL, cached
"""
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, '.cache')
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
PORTAL = 'https://dominica.gov.dm/laws-of-dominica?page=1'
_last = {}


def key_of(url, data=None):
    return url if data is None else url + '\n' + data


def path_of(url, data=None):
    return os.path.join(CACHE, hashlib.sha256(key_of(url, data).encode('utf-8')).hexdigest())


def fetch(url, data=None):
    """Return the bytes of url (POSTing data if given), from the cache when present."""
    p = path_of(url, data)
    if os.path.exists(p):
        with open(p, 'rb') as f:
            return f.read()
    os.makedirs(CACHE, exist_ok=True)
    host = urllib.parse.urlsplit(url).netloc
    wait = 1.0 - (time.time() - _last.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    _last[host] = time.time()
    # curl needs spaces and other unsafe characters percent-encoded; the cache key stays the original URL
    curl_url = urllib.parse.quote(url, safe=':/?&=%#,+;@!$\'()*~')
    cmd = ['curl', '-sS', '-L', '--compressed', '-A', UA, '--max-time', '180', '-o', p + '.part',
           '-w', '%{http_code}', curl_url]
    if data is not None:
        cmd[1:1] = ['--data', data]
    r = subprocess.run(cmd, capture_output=True, text=True)
    status = r.stdout.strip()
    ok = r.returncode == 0 and status == '200'
    size = os.path.getsize(p + '.part') if os.path.exists(p + '.part') else 0
    with open(os.path.join(CACHE, 'requests.jsonl'), 'a', encoding='utf-8') as log:
        log.write(json.dumps({'t': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'url': url, 'post': data,
                              'status': status, 'bytes': size, 'cache': os.path.basename(p)}) + '\n')
    if not ok:
        if os.path.exists(p + '.part'):
            os.remove(p + '.part')
        raise RuntimeError(f'{url}: curl {r.returncode} status {status} {r.stderr.strip()}')
    os.replace(p + '.part', p)
    with open(p, 'rb') as f:
        return f.read()


def search(term, field='title', page=1):
    data = urllib.parse.urlencode({'searchname': term, 's': field, 'searchbtn': 'Search'})
    url = PORTAL if page == 1 else PORTAL.replace('page=1', f'page={page}')
    return fetch(url, data).decode('utf-8', 'replace')


def results(html):
    """[(title, url)] from one search result page."""
    import re
    return [(t, u) for u, t in re.findall(r"<li><a href='([^']+)' target='_blank'>([^<]+)</a></li>", html)]


if __name__ == '__main__':
    if sys.argv[1] == 'search':
        for t, u in results(search(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else 'title')):
            print(t, '|', u)
    elif sys.argv[1] == 'get':
        b = fetch(sys.argv[2])
        print(len(b), path_of(sys.argv[2]))
