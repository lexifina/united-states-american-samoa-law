"""Cached, polite curl fetcher for Palau sources (official hosts only).

    python -X utf8 scripts/palau-law/fetch.py            # fetch every source in sources.json
    import fetch; fetch.get(url) -> bytes                # from other scripts

Cache: .cache/<sha256(url)>, log .cache/requests.jsonl. At most 1 request a second. curl, never urllib (TLS).
Google Drive folders are listed through drive.google.com/embeddedfolderview?id=<id>; files are downloaded through
drive.google.com/uc?export=download&id=<id> (with the confirm token for large files).
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
_last = [0.0]


def path(url: str) -> Path:
    return CACHE / hashlib.sha256(url.encode('utf-8')).hexdigest()


def get(url: str, refresh: bool = False) -> bytes | None:
    p = path(url)
    if p.exists() and not refresh:
        return p.read_bytes()
    CACHE.mkdir(exist_ok=True)
    wait = 1.0 - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    tmp = p.with_suffix('.part')
    r = subprocess.run(['curl', '-s', '-L', '--compressed', '-m', '300', '-A', UA, '-o', str(tmp),
                        '-w', '%{http_code}', url], capture_output=True, text=True)
    _last[0] = time.time()
    code = int(r.stdout.strip() or 0)
    size = tmp.stat().st_size if tmp.exists() else 0
    with open(CACHE / 'requests.jsonl', 'a', encoding='utf-8') as f:
        f.write(json.dumps({'url': url, 'status': code, 'bytes': size,
                            'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'via': 'palau-law/fetch.py'}) + '\n')
    if code != 200:
        tmp.unlink(missing_ok=True)
        return None
    tmp.replace(p)
    return p.read_bytes()


def drive_folder(folder_id: str) -> list[dict]:
    """[{'name','url','id','kind'}] for one public Drive folder (kind 'folder' or 'file')."""
    raw = get(f'https://drive.google.com/embeddedfolderview?id={folder_id}')
    out = []
    if not raw:
        return out
    t = raw.decode('utf-8', 'replace')
    for m in re.finditer(r'<a href="([^"]+)"[^>]*>.*?<div class="flip-entry-title">(.*?)</div>', t, re.S):
        url, name = m.group(1), m.group(2).replace('&quot;', '"').replace('&amp;', '&').replace('&#39;', "'").strip()
        fm = re.search(r'/folders/([\w-]+)', url)
        dm = re.search(r'/d/([\w-]+)', url)
        out.append({'name': name, 'url': url, 'id': (fm or dm).group(1) if (fm or dm) else None,
                    'kind': 'folder' if fm else 'file'})
    return out


def drive_file(file_id: str) -> bytes | None:
    url = f'https://drive.google.com/uc?export=download&id={file_id}'
    b = get(url)
    if b and b[:200].lstrip().lower().startswith((b'<!doctype html', b'<html')):
        # large-file interstitial: follow the confirm form once
        t = b.decode('utf-8', 'replace')
        m = re.search(r'action="([^"]+)"', t)
        params = dict(re.findall(r'name="(\w+)" value="([^"]*)"', t))
        if m and params:
            q = '&'.join(f'{k}={v}' for k, v in params.items())
            b = get(m.group(1).replace('&amp;', '&') + ('&' if '?' in m.group(1) else '?') + q)
    return b


ROOT = '1o9b7uIAaNl7qj_yfILpbgstBp6nW90Ox'          # Code Commission / PALAU Office public Drive
PNC = '1bXnjD2gLKQTu8ci3IKu7-JfHBxmx1B2S'           # Palau National Code (PNC), current titles
FORMER = '1rMt1d-5bhBuuoDB7VbYxSX8ZEeNLKzqM'        # Archives / Former Supplements


def drive_index() -> dict:
    """Write .cache/drive/index.json: {'current': {name: id}, 'supplements': {folder: {name: id}}}."""
    supps = {e['name']: {f['name']: f['id'] for f in drive_folder(e['id'])} for e in drive_folder(FORMER)}
    cur = {f['name']: f['id'] for f in drive_folder(PNC)}
    idx = {'current': cur, 'supplements': supps}
    (CACHE / 'drive').mkdir(parents=True, exist_ok=True)
    (CACHE / 'drive' / 'index.json').write_text(json.dumps(idx, indent=1, ensure_ascii=False), encoding='utf-8')
    return idx


if __name__ == '__main__':
    src = json.loads((HERE / 'sources.json').read_text(encoding='utf-8'))
    for s in src['files']:
        b = drive_file(s['id']) if s.get('drive') else get(s['url'])
        print(s.get('name'), len(b) if b else None)
    drive_index()
    import pnc  # the editions and titles parse.py builds
    for t in pnc.TITLES:
        for folder, _date, pat, _lay in pnc.EDITIONS:
            fid = pnc.IDX['supplements'][folder].get(pat.format(n=t['n']))
            if fid:
                print(folder, t['n'], len(drive_file(fid) or b''))
        print('current', t['n'], len(drive_file(pnc.IDX['current'][t['current']]) or b''))
    sys.exit(0)
