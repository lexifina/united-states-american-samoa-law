"""gitlaw-scraper-dell (2026-10-30): the one polite fetcher for the Pakistan provinces and Malaysian states (private; never
published). One request at a time per host across every process (an exclusive lock file per host), at least GAP
seconds apart, cached by sha256 of the URL under scripts/world-law/.pkmy-cache/<host>/, every request logged.
A challenge page, 403 or 5xx stops that host for good (a STOP file); nothing tries to get round one.

    python -X utf8 pkmy_fetch.py <url> [--out file]
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.pkmy-cache'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'
GAP = {'default': 3.2}   # per host; raised to a stated Crawl-delay via set_gap()
CHALLENGE = (b'Just a moment', b'cf-chl', b'Attention Required', b'Requ\xc3\xaate non autoris\xc3\xa9e',
             b'ID de support : bot-', b'captcha', b'Incapsula', b'_Incapsula_')


class Stopped(Exception):
    pass


def _host(url: str) -> str:
    return url.split('://', 1)[-1].split('/', 1)[0].lower()


def _lock(host: str):
    d = CACHE / host
    d.mkdir(parents=True, exist_ok=True)
    lock = d / '.lock'
    while True:
        try:
            return os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY), lock
        except (FileExistsError, PermissionError):
            try:
                if time.time() - lock.stat().st_mtime > 300:
                    lock.unlink(missing_ok=True)
            except OSError:
                pass
            time.sleep(0.2)


def set_gap(host: str, seconds: float) -> None:
    (CACHE / host).mkdir(parents=True, exist_ok=True)
    (CACHE / host / 'GAP').write_text(str(seconds))


def path_for(url: str) -> Path:
    return CACHE / _host(url) / hashlib.sha256(url.encode('utf-8')).hexdigest()


def get(url: str, timeout: int = 120, accept: str | None = None, data: str | None = None) -> bytes | None:
    """Cached GET. Returns the body for 200, None for 404/410 (cached as a negative answer). Raises Stopped on a
    challenge, 403, 429 or 5xx (and marks the host stopped)."""
    host = _host(url)
    p = path_for(url if data is None else url + '|POST|' + data)
    if p.exists():
        return p.read_bytes()
    neg = p.with_suffix('.404')
    if neg.exists():
        return None
    stop = CACHE / host / 'STOP'
    if stop.exists():
        raise Stopped(f'{host} stopped: {stop.read_text(encoding="utf-8")[:200]}')
    fd, lock = _lock(host)
    try:
        st = CACHE / host / '.last'
        last = float(st.read_text()) if st.exists() else 0.0
        gf = CACHE / host / 'GAP'
        gap = max(GAP['default'], float(gf.read_text()) if gf.exists() else 0.0)
        wait = last + gap - time.time()
        if wait > 0:
            time.sleep(wait)
        with tempfile.NamedTemporaryFile(delete=False, dir=CACHE / host) as f:
            tmp = f.name
        cmd = ['curl', '-gsS', '-L', '--compressed', '-A', UA, '--max-time', str(timeout), '-o', tmp,
               '-w', '%{http_code}', url]
        if accept:
            cmd[1:1] = ['-H', f'Accept: {accept}']
        if data is not None:   # a form POST (urlencoded string), cached under url + body
            cmd[1:1] = ['--data', data]
        out = subprocess.run(cmd, capture_output=True, text=True)
        if out.returncode and 'timed out' not in out.stderr:   # a transient connect failure: once more, later
            time.sleep(10)
            out = subprocess.run(cmd, capture_output=True, text=True)
        st.write_text(str(time.time()))
        code = int(out.stdout.strip() or 0) if out.returncode == 0 else 0
        body = Path(tmp).read_bytes() if Path(tmp).exists() else b''
        Path(tmp).unlink(missing_ok=True)
        with open(CACHE / host / 'requests.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps({'url': url, 'status': code, 'bytes': len(body),
                                'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}) + '\n')
        head = body[:20000]
        if code == 200 and any(c in head for c in CHALLENGE):
            stop.write_text(f'challenge page at {url}', encoding='utf-8')
            raise Stopped(f'{host}: challenge page at {url}')
        if code in (403, 429) or code >= 500:
            stop.write_text(f'HTTP {code} at {url}', encoding='utf-8')
            raise Stopped(f'{host}: HTTP {code} at {url}')
        if code in (404, 410):
            neg.write_text(str(code))
            return None
        if code != 200:
            return None   # timeouts etc.: not cached, retried by a later call
        part = p.with_suffix('.part')
        part.write_bytes(body)
        os.replace(part, p)
        return body
    finally:
        os.close(fd)
        lock.unlink(missing_ok=True)


if __name__ == '__main__':
    b = get(sys.argv[1])
    if '--out' in sys.argv:
        Path(sys.argv[sys.argv.index('--out') + 1]).write_bytes(b or b'')
    else:
        sys.stdout.buffer.write((b or b'<none>')[:4000])
