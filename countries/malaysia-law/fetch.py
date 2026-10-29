"""Polite, resumable, cached fetcher for Malaysia (gitlaw-MY).

Source: lom.agc.gov.my, the Attorney General's Chambers' Laws of Malaysia portal, read directly with curl
(it answers normally; there is no bot challenge), at most 3 requests a second (SPEED RULE).

Cache: .cache/<sha256(key)>, where key is the URL, or "URL POST <body>" for a POST; every network request is
logged to .cache/requests.jsonl.

The portal's list tables (amendments, reprints) are served by POST endpoints whose JSON body is AES-256-GCM
encoded with a key the page itself publishes to every browser (SEARCH_RESPONSE_KEY in federal-constitution.php,
decoded by js/responseCrypto.js). decode() does the same as that page script: iv = bytes 0..12, tag = 12..28,
ciphertext = 28.., then JSON. The cache keeps the bytes exactly as served.

Usage:
  python -X utf8 fetch.py            fetch every source listed in sources.json
  python -X utf8 fetch.py URL ...    fetch URLs
"""
import base64
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
BASE = 'https://lom.agc.gov.my/'
_last = {}
_lock = __import__('threading').Lock()


def key_of(url, data=None):
    return url if data is None else url + ' POST ' + data


def path_for(url, data=None):
    return os.path.join(CACHE, hashlib.sha256(key_of(url, data).encode('utf-8')).hexdigest())


def cached(url, data=None):
    p = path_for(url, data)
    if os.path.exists(p):
        with open(p, 'rb') as f:
            return f.read()
    return None


def get(url, data=None, refresh=False, offline=False):
    """Cached bytes of url (POST with form body `data` when given), fetched once with curl."""
    os.makedirs(CACHE, exist_ok=True)
    p = path_for(url, data)
    if os.path.exists(p) and not refresh:
        with open(p, 'rb') as f:
            return f.read()
    if offline:
        raise RuntimeError(f'not in cache: {key_of(url, data)}')
    host = url.split('/')[2]
    with _lock:                                      # at most 3 request starts a second per host, across threads
        now = time.time()
        start = max(now, _last.get(host, 0) + 0.34)
        _last[host] = start
    if start > now:
        time.sleep(start - now)
    tmp = p + '.part'
    cmd = ['curl', '-sS', '--compressed', '-L', '-A', UA, '-m', '300', '-o', tmp,
           '-w', '%{http_code} %{content_type}']
    if data is not None:
        cmd += ['-H', 'X-Requested-With: XMLHttpRequest', '--data-raw', data]
    cmd.append(urllib.parse.quote(url, safe=":/?&=%#()[],;+@!$'*~"))
    r = subprocess.run(cmd, capture_output=True, text=True)
    code, _, ctype = r.stdout.partition(' ')
    size = os.path.getsize(tmp) if os.path.exists(tmp) else 0
    with open(os.path.join(CACHE, 'requests.jsonl'), 'a', encoding='utf-8') as f:
        f.write(json.dumps({'t': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'url': url,
                            'post': data, 'status': code, 'type': ctype, 'bytes': size}) + '\n')
    if r.returncode != 0 or code != '200':
        if os.path.exists(tmp):
            os.remove(tmp)
        raise RuntimeError(f'fetch failed {code} {r.stderr.strip()} {url}')
    os.replace(tmp, p)
    with open(p, 'rb') as f:
        return f.read()


def page_key(html):
    import re
    m = re.search(rb"SEARCH_RESPONSE_KEY\s*=\s*'([0-9a-f]{64})'", html)
    return m.group(1).decode() if m else None


def decode(body, key_hex):
    """The portal's list JSON, decoded exactly as js/responseCrypto.js does in the browser."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    j = json.loads(body)
    enc = None
    if isinstance(j, dict):
        for k in ('data', 'payload', 'encrypted', 'response'):
            if isinstance(j.get(k), str):
                enc = j[k]
                break
        if enc is None and 'records' in j:
            return j
    elif isinstance(j, str):
        enc = j
    raw = base64.b64decode(enc)
    iv, tag, ct = raw[:12], raw[12:28], raw[28:]
    out = AESGCM(bytes.fromhex(key_hex)).decrypt(iv, ct + tag, None)
    return json.loads(out.decode('utf-8'))


def dt_body(draw=1, start=0, length=500, ncols=6, extra=None):
    """A DataTables server-side request body like the page sends."""
    q = [('draw', str(draw))]
    for i in range(ncols):
        q += [(f'columns[{i}][data]', ''), (f'columns[{i}][name]', ''), (f'columns[{i}][searchable]', 'true'),
              (f'columns[{i}][orderable]', 'true'), (f'columns[{i}][search][value]', ''),
              (f'columns[{i}][search][regex]', 'false')]
    q += [('order[0][column]', '0'), ('order[0][dir]', 'desc'), ('start', str(start)), ('length', str(length)),
          ('search[value]', ''), ('search[regex]', 'false')]
    for k, v in (extra or {}).items():
        q.append((k, v))
    return urllib.parse.urlencode(q)


def main():
    """Fetch every source in sources.json at once: a pool of 3 threads, at most 3 requests a second per host."""
    from concurrent.futures import ThreadPoolExecutor
    with open(os.path.join(HERE, 'sources.json'), encoding='utf-8') as f:
        src = json.load(f)
    items = [(i, None) if isinstance(i, str) else (i['url'], i.get('post')) for i in src.get('direct', [])]
    todo = [it for it in items if cached(*it) is None]

    def one(it):
        try:
            get(*it)
            return 'ok'
        except Exception as e:                      # keep going; report at the end
            return f'FAIL {e}'
    with ThreadPoolExecutor(3) as ex:
        res = list(ex.map(one, todo))
    for it, r in zip(todo, res):
        print(r, it[0][-80:], flush=True)
    print('done', len(items), 'sources,', len(todo), 'fetched now,', sum(r != 'ok' for r in res), 'failed', flush=True)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        for u in sys.argv[1:]:
            get(u)
            print(path_for(u), u)
    else:
        main()
