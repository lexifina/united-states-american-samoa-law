"""Downloads the Official Gazette PDFs that Rwanda's corpus is built from, into .cache/ (resumable, polite).

    python -X utf8 fetch.py            # every file listed in acts.json
    python -X utf8 fetch.py 4119 4115  # only these file ids

Source: the Rwanda Law Reform Commission's open API behind amategeko.gov.rw (robots.txt 2026-10-28: "User-agent: *",
empty "Disallow:").
    https://apis.amategeko.gov.rw/v1/site/documents-files/<file id>  -> JSON metadata with a signed `file_url`
    the signed URL (valid about one hour)                              -> the Gazette PDF, trilingual (rw | en | fr)

Cache files are named by the sha256 of a stable URL:
    meta: sha256(API URL).json, with the signed `file_url` removed (it changes on every call), so the cache is stable;
    pdf:  sha256(the signed URL without its query string).pdf
Every request is logged to .cache/requests.jsonl. curl only (Python TLS fails on this machine), --compressed,
at most 1 request per second per host, with the lexifina-watch User-Agent.
"""
import datetime as dt
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
API = 'https://apis.amategeko.gov.rw/v1/site/documents-files/'
_last: dict = {}


def key(url: str) -> str:
    return hashlib.sha256(url.encode('utf-8')).hexdigest()


def curl(url: str) -> bytes:
    host = urlsplit(url).netloc
    wait = 1.05 - (time.monotonic() - _last.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    for attempt in range(4):
        _last[host] = time.monotonic()
        p = subprocess.run(['curl', '-sS', '-f', '-L', '--compressed', '-m', '300', '-A', UA, url],
                           capture_output=True)
        log = {'at': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
               'url': url.split('?', 1)[0], 'rc': p.returncode, 'bytes': len(p.stdout),
               'sha256': hashlib.sha256(p.stdout).hexdigest() if p.returncode == 0 else None}
        with open(CACHE / 'requests.jsonl', 'a', encoding='utf-8', newline='\n') as f:
            f.write(json.dumps(log) + '\n')
        if p.returncode == 0:
            return p.stdout
        time.sleep(3 * (attempt + 1))
    raise SystemExit(f'cannot fetch {url}: {p.stderr.decode(errors="replace")[:300]}')


def meta_path(file_id: int) -> Path:
    return CACHE / (key(API + str(file_id)) + '.json')


def pdf_path(meta: dict) -> Path:
    return CACHE / (key(meta['file_url_path']) + '.pdf')


def fetch(file_id: int) -> dict:
    mp = meta_path(file_id)
    if mp.exists():
        meta = json.loads(mp.read_text(encoding='utf-8'))
        if pdf_path(meta).exists():
            return meta
    d = json.loads(curl(API + str(file_id)))['data']
    signed = d.pop('file_url')
    d['file_url_path'] = signed.split('?', 1)[0]
    pp = pdf_path(d)
    if not pp.exists():
        b = curl(signed)
        if not b.startswith(b'%PDF'):
            raise SystemExit(f'file {file_id}: not a PDF')
        tmp = pp.with_suffix('.tmp')
        tmp.write_bytes(b)
        tmp.replace(pp)
    d['pdf_sha256'] = hashlib.sha256(pp.read_bytes()).hexdigest()
    d['retrieved'] = dt.date.today().isoformat()
    mp.write_text(json.dumps(d, ensure_ascii=False, indent=1, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    return d


def main():
    CACHE.mkdir(exist_ok=True)
    (CACHE / '.gitignore').write_text('*\n', encoding='utf-8', newline='\n')
    ids = [int(a) for a in sys.argv[1:]]
    if not ids:
        acts = json.loads((HERE / 'acts.json').read_text(encoding='utf-8'))
        for a in acts['acts']:
            ids += [v['file'] for v in a['texts']]
    for i in ids:
        m = fetch(i)
        print(i, m['pdf_sha256'][:12], m['file_name'])


if __name__ == '__main__':
    main()
