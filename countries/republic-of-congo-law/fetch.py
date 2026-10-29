"""Republic of the Congo: cached fetcher for the SGG (sgg.cg) site and Journal officiel PDFs.

curl subprocess, --compressed, cache named by sha256(url) under .cache/, every request logged
to .cache/requests.jsonl, at most ~3 requests a second (SPEED RULE). Resumable: a cached URL is
never fetched again.

    python -X utf8 fetch.py            # fetch everything parse.py needs
    python -X utf8 fetch.py URL ...    # fetch (and cache) specific URLs
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
_last = [0.0]

# Everything parse.py reads. Keep in step with sources.json.
URLS = [
    'https://sgg.cg/droit-congolais/constitution.html',
    'https://sgg.cg/JO/2015/congo-jo-2015-08-sp.pdf',
    'https://sgg.cg/JO/2022/congo-jo-2022-01-sp.pdf',
]


def path_for(url):
    return os.path.join(CACHE, hashlib.sha256(url.encode('utf-8')).hexdigest())


def get(url, refresh=False):
    """Return the cached bytes for url, fetching once through curl."""
    p = path_for(url)
    if os.path.exists(p) and not refresh:
        with open(p, 'rb') as f:
            return f.read()
    os.makedirs(CACHE, exist_ok=True)
    wait = 0.34 - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()
    tmp = p + '.part'
    r = subprocess.run(['curl', '-sS', '--compressed', '-L', '-m', '180', '-A', UA, '-o', tmp,
                        '-w', '%{http_code} %{content_type} %{size_download}', url],
                       capture_output=True, text=True)
    out = (r.stdout or '').split(' ')
    code = out[0] if out else ''
    rec = {'t': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'url': url, 'status': code,
           'type': out[1] if len(out) > 1 else '', 'bytes': int(out[2]) if len(out) > 2 and out[2].isdigit() else 0,
           'err': r.stderr.strip()[:200]}
    if code == '200' and os.path.exists(tmp):
        with open(tmp, 'rb') as f:
            data = f.read()
        rec['sha256'] = hashlib.sha256(data).hexdigest()
        os.replace(tmp, p)
    else:
        data = None
        if os.path.exists(tmp):
            os.remove(tmp)
    with open(os.path.join(CACHE, 'requests.jsonl'), 'a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    if data is None:
        raise RuntimeError(f'fetch failed {code} {url} {rec["err"]}')
    return data


def main(argv):
    urls = argv or URLS
    for u in urls:
        try:
            b = get(u)
            print(len(b), u)
        except RuntimeError as e:
            print('FAIL', e)


if __name__ == '__main__':
    main(sys.argv[1:])
