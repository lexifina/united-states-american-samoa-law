"""Polite, resumable, cached fetcher for the Federated States of Micronesia (gitlaw-FM).

Cache: .cache/<sha256(url)>, one file per URL, plus .cache/requests.jsonl (one line per network request).

- cfsm.gov.fm (FSM Congress, official public laws): direct, with curl, at most 3 requests a second (SPEED RULE);
  robots.txt allows everything but /wp-admin/.
- fsmlaw.org (FSM Legal Information System): robots.txt sets Crawl-delay: 30, so it is read only through Internet
  Archive `id_` captures (scripts/gitlaw_common/wayback.py, the machine-wide shared rate), pinned by timestamp.
  This fetcher never requests fsmlaw.org itself. fsmsupremecourt.org (Cloudflare challenge) is never touched.

Usage:
  python -X utf8 fetch.py            fetch every source parse.py reads (sources.json)
  python -X utf8 fetch.py URL ...    fetch URLs directly (cfsm.gov.fm only)
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
sys.path.insert(0, os.path.join(HERE, '..', 'gitlaw_common'))
_last = {}


def path_for(url):
    return os.path.join(CACHE, hashlib.sha256(url.encode('utf-8')).hexdigest())


def get(url, refresh=False):
    """Cached bytes of a direct (non-archive) URL, fetched once with curl."""
    if 'fsmlaw.org' in url.split('/')[2] or 'fsmsupremecourt' in url:
        raise RuntimeError('fsmlaw.org is read through archive.org only: use wb()')
    os.makedirs(CACHE, exist_ok=True)
    p = path_for(url)
    if os.path.exists(p) and not refresh:
        with open(p, 'rb') as f:
            return f.read()
    host = url.split('/')[2]
    wait = 0.34 - (time.time() - _last.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    _last[host] = time.time()
    tmp = p + '.part'
    r = subprocess.run(['curl', '-sS', '--compressed', '-L', '-A', UA, '-m', '180', '-o', tmp,
                        '-w', '%{http_code} %{content_type}', url], capture_output=True, text=True)
    code, _, ctype = r.stdout.partition(' ')
    size = os.path.getsize(tmp) if os.path.exists(tmp) else 0
    with open(os.path.join(CACHE, 'requests.jsonl'), 'a', encoding='utf-8') as f:
        f.write(json.dumps({'t': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'url': url,
                            'status': code, 'type': ctype, 'bytes': size}) + '\n')
    if r.returncode != 0 or code != '200':
        if os.path.exists(tmp):
            os.remove(tmp)
        raise RuntimeError(f'fetch failed {code} {r.stderr.strip()} {url}')
    os.replace(tmp, p)
    with open(p, 'rb') as f:
        return f.read()


def wb(url, ts):
    """Raw bytes of an Internet Archive capture of url at timestamp ts (cached; shared machine-wide rate)."""
    import wayback
    b = wayback.get(url, ts=ts, cache=CACHE)
    if not b:
        raise RuntimeError(f'no capture {ts} {url}')
    return b


def main():
    with open(os.path.join(HERE, 'sources.json'), encoding='utf-8') as f:
        src = json.load(f)
    for item in src['archive']:
        wb(item['url'], item['ts'])
    for url in src['direct']:
        get(url)
    print('ok', len(src['archive']), 'archived,', len(src['direct']), 'direct')


if __name__ == '__main__':
    if len(sys.argv) > 1:
        for u in sys.argv[1:]:
            get(u)
            print(path_for(u), u)
    else:
        main()
