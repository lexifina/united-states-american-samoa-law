"""Gate probes for the South American regional units (gitlaw-scraper-dell, coverage wave 2026-10-31).

One request per call, TLS verified, 30 s timeout (a timeout is a fail), at least 3.2 s after the previous request to the
same host (recorded in .sa-cache/last-<host>), challenge / 403 / 429 detection. Response body cached gzipped by URL.
Private (world-law-ops only).

    python -X utf8 scripts/world-law/sa_probe.py <url> [--show N] [--grep REGEX] [--links REGEX]
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.sa-cache'
LOG = HERE / 'logs' / 'sa-regions-requests.jsonl'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'
MIN_PAUSE = 3.2
CHALLENGE = (b'just a moment', b'cf-chl', b'incapsula incident', b'request unsuccessful', b'captcha',
             b'_incapsula_resource', b'challenge-platform', b'attention required', b'access denied',
             b'imunify', b'sucuri website firewall', b'ddos protection')


def cpath(url: str) -> Path:
    host = url.split('/')[2]
    return CACHE / host / (hashlib.sha256(url.encode()).hexdigest()[:40] + '.gz')


def fetch(url: str, refresh: bool = False, timeout: int = 30, delay: float | None = None) -> dict:
    import requests
    CACHE.mkdir(exist_ok=True)
    gi = CACHE / '.gitignore'
    if not gi.exists():
        gi.write_text('*\n', encoding='utf-8')
    p = cpath(url)
    meta = p.with_suffix('.json')
    if p.exists() and meta.exists() and not refresh:
        m = json.loads(meta.read_text(encoding='utf-8'))
        m['body'] = gzip.decompress(p.read_bytes())
        m['cached'] = True
        return m
    host = url.split('/')[2]
    stop = CACHE / f'STOP-{host}'
    if stop.exists():
        return {'status': -1, 'error': 'host stopped: ' + stop.read_text(encoding='utf-8'), 'body': b''}
    _daily_cap(host)
    last = CACHE / f'last-{host}'
    pause = max(MIN_PAUSE, delay or 0)
    if last.exists():
        wait = float(last.read_text()) + pause - time.time()
        if wait > 0:
            time.sleep(wait)
    last.write_text(str(time.time()))
    t0 = time.time()
    rec = {'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'url': url[:300]}
    try:
        r = requests.get(url, timeout=timeout, headers={'User-Agent': UA, 'Accept-Encoding': 'gzip',
                                                         'Accept-Language': 'es,en;q=0.8'})
    except requests.exceptions.SSLError as e:
        # certifi lacks an intermediate some .gov.co hosts do not send: ask Windows (Schannel, which fetches the
        # intermediate itself). Verification stays on.
        r = _curl(url, timeout)
        if r is None:
            rec.update(status=0, err='ssl+curl: ' + str(e)[:150], secs=round(time.time() - t0, 1))
            _log(rec)
            return {'status': 0, 'error': str(e)[:300], 'body': b''}
        rec['via'] = 'curl'
    except requests.RequestException as e:
        rec.update(status=0, err=str(e)[:200], secs=round(time.time() - t0, 1))
        _log(rec)
        return {'status': 0, 'error': str(e)[:300], 'body': b''}
    last.write_text(str(time.time()))
    body = r.content
    rec.update(status=r.status_code, bytes=len(body), secs=round(time.time() - t0, 1), final=r.url[:300])
    _log(rec)
    head = body[:8000].lower()
    chall = [c.decode() for c in CHALLENGE if c in head]
    hard = (b'just a moment', b'cf-chl', b'incapsula incident', b'request unsuccessful', b'_incapsula_resource',
            b'challenge-platform', b'sucuri website firewall', b'ddos protection')
    # (a reCAPTCHA script for a form on a fully served page is not a challenge: 'captcha' alone never stops a host)
    if r.status_code in (403, 429) or (r.status_code != 404 and any(c in head for c in hard)):
        stop.write_text(f'HTTP {r.status_code} {chall} at {url}', encoding='utf-8')
    m = {'status': r.status_code, 'final': r.url, 'ctype': r.headers.get('content-type', ''),
         'headers': {k: v for k, v in r.headers.items() if k.lower() in ('server', 'content-type', 'x-powered-by',
                                                                         'set-cookie', 'location', 'last-modified')},
         'challenge_markers': chall}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(gzip.compress(body, 6, mtime=0))
    meta.write_text(json.dumps(m, ensure_ascii=False), encoding='utf-8')
    m['body'] = body
    return m


DAILY_CAP = 5000  # coordinator rule 2026-11-01: about 5,000 requests per host per UTC day (no stated Crawl-delay)


def _daily_cap(host: str) -> None:
    """Count this request against the host's UTC-day budget; once DAILY_CAP requests were made today, sleep until the
    next UTC day. The count lives in .sa-cache/count-<host>-<YYYYMMDD>; a missing file is seeded from the request log."""
    while True:
        day = time.strftime('%Y%m%d', time.gmtime())
        f = CACHE / f'count-{host}-{day}'
        if f.exists():
            n = int(f.read_text() or 0)
        else:
            n, iso = 0, time.strftime('%Y-%m-%d', time.gmtime())
            if LOG.exists():
                with open(LOG, encoding='utf-8') as fh:
                    for line in fh:
                        if line.startswith('{"at": "' + iso) and f'//{host}/' in line:
                            n += 1
        if n < DAILY_CAP:
            f.write_text(str(n + 1))
            return
        f.write_text(str(n))
        wait = 86400 - (time.time() % 86400) + 5
        print(time.strftime('%H:%M:%S'), f'daily cap: {n} requests to {host} today (UTC); pausing {wait / 3600:.1f} h',
              flush=True)
        time.sleep(wait)


class _R:
    def __init__(self, status, body, url, headers):
        self.status_code, self.content, self.url, self.headers = status, body, url, headers


def _curl(url: str, timeout: int):
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        hf, bf = Path(td) / 'h', Path(td) / 'b'
        p = subprocess.run(['curl', '-sS', '-L', '--compressed', '-m', str(timeout), '-A', UA, '-H',
                            'Accept-Language: es,en;q=0.8', '-D', str(hf), '-o', str(bf), '-w', '%{http_code} %{url_effective}',
                            url], capture_output=True, text=True)
        if p.returncode != 0 or not bf.exists():
            return None
        code, _, final = p.stdout.partition(' ')
        heads = {}
        for ln in hf.read_text(encoding='latin-1').splitlines():
            if ':' in ln:
                k, v = ln.split(':', 1)
                heads[k.strip().lower()] = v.strip()
        return _R(int(code), bf.read_bytes(), final, heads)


def _log(rec):
    LOG.parent.mkdir(exist_ok=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')


def text(b: bytes) -> str:
    for enc in ('utf-8', 'cp1252'):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            pass
    return b.decode('latin-1')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    try:
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception:
        pass
    args = sys.argv[1:]
    url = args[0]
    show = int(args[args.index('--show') + 1]) if '--show' in args else 1500
    m = fetch(url, refresh='--refresh' in args)
    b = m.pop('body')
    print(json.dumps(m, ensure_ascii=False)[:800])
    s = text(b)
    if '--links' in args:
        rx = re.compile(args[args.index('--links') + 1], re.I)
        seen = []
        for h in re.findall(r'href=["\']([^"\']+)', s):
            if rx.search(h) and h not in seen:
                seen.append(h)
        print(len(seen), 'links'); print('\n'.join(seen[:show]))
    elif '--grep' in args:
        rx = re.compile(args[args.index('--grep') + 1], re.I)
        plain = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s))
        for mm in rx.finditer(plain):
            print('...', plain[max(0, mm.start() - 200):mm.end() + 300])
    else:
        print(s[:show])
