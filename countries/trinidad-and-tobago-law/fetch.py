"""Polite, resumable fetcher for laws.gov.tt (Trinidad and Tobago Digital Legislative Library).

Cache: .cache/<sha256(url)>.<ext>, every request logged to .cache/requests.jsonl.
curl only (Python TLS fails on this machine); at most 3 requests a second to the official site.

    python -X utf8 fetch.py            # fetch the act pages and every PDF the Phase 1 acts need
"""
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, '.cache')
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
BASE = 'https://laws.gov.tt'
_last = [0.0]

# Phase 1 acts: slug -> laws.gov.tt "currentid"
ACTS = {
    'constitution': 530,      # Constitution of the Republic of Trinidad and Tobago, Chap. 1:01
    'data-protection': 80855, # Data Protection, Chap. 22:04
    'criminal-offences': 472, # Criminal Offences, Chap. 11:01
    'companies': 608,         # Companies, Chap. 81:01
}


def act_page_url(cid):
    return f'{BASE}/ttdll-web/revision/list?offset=0&q=&currentid={cid}'


def path_for(url, ext):
    return os.path.join(CACHE, hashlib.sha256(url.encode()).hexdigest() + ext)


def get(url, ext='.html', min_gap=0.34):
    p = path_for(url, ext)
    if os.path.exists(p) and os.path.getsize(p) > 0:
        return p
    os.makedirs(CACHE, exist_ok=True)
    wait = _last[0] + min_gap - time.time()
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()
    tmp = p + '.part'
    r = subprocess.run(['curl', '-s', '-L', '--compressed', '--max-time', '180', '-A', UA,
                        '-o', tmp, '-w', '%{http_code} %{size_download} %{content_type}', url],
                       capture_output=True, text=True)
    code, size, ctype = (r.stdout.split(' ', 2) + ['', '', ''])[:3]
    with open(os.path.join(CACHE, 'requests.jsonl'), 'a', encoding='utf-8') as f:
        f.write(json.dumps({'t': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'url': url,
                            'status': code, 'bytes': size, 'type': ctype, 'file': os.path.basename(p)}) + '\n')
    if code != '200' or not os.path.exists(tmp) or os.path.getsize(tmp) == 0:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise RuntimeError(f'{url}: HTTP {code}')
    os.replace(tmp, p)
    return p


def main():
    sys.path.insert(0, HERE)
    import sources
    for slug, cid in ACTS.items():
        page = get(act_page_url(cid))
        info = sources.act_page(page)
        for v in info['versions']:
            get(BASE + v['href'], '.pdf')
        print(slug, len(info['versions']), 'versions', len(info['amendments']), 'amendments')


if __name__ == '__main__':
    main()
