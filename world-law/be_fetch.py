"""gitlaw-scraper-dell (2026-10-30): the one polite fetcher for the Belgian federated-entity builds (private; never
published). One request at a time per host across every process (an exclusive lock file per host), at least GAP
seconds apart, cached by sha256 of the URL under scripts/world-law/.be-cache/<host>/, every request logged.
A challenge page, 403 or 5xx stops that host for good (a STOP file); nothing tries to get round one.

    python -X utf8 be_fetch.py <url> [--out file]
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
CACHE = HERE / '.be-cache'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'
# Coordinator rule (2026-11-01, after three late WAF blocks): on a host without a stated Crawl-delay, at most one
# request per 3 s and about 5,000 requests per host per UTC day; stop for good on any challenge.
MIN_GAP = 3.0
GAP = {'default': 3.5, 'codex.opendata.api.vlaanderen.be': 3.0}
DAILY_MAX = 5000
FIVEXX_STOP = 3          # consecutive 5xx answers that stop a host; a single 5xx only fails that URL
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


def path_for(url: str) -> Path:
    return CACHE / _host(url) / hashlib.sha256(url.encode('utf-8')).hexdigest()


def _today() -> str:
    return time.strftime('%Y-%m-%d', time.gmtime())


def day_count(host: str) -> int:
    """Requests sent to the host today (UTC), from its counter file (kept under the host lock)."""
    f = CACHE / host / '.day-count.json'
    try:
        d = json.loads(f.read_text(encoding='utf-8'))
        return d['n'] if d['day'] == _today() else 0
    except (OSError, ValueError, KeyError):
        return 0


def _wait_for_budget(host: str):
    while day_count(host) >= DAILY_MAX:
        now = time.time()
        nxt = (int(now // 86400) + 1) * 86400 + 60     # one minute after the next UTC midnight
        print(f'{host}: {DAILY_MAX} requests today; pausing until the next UTC day', flush=True)
        time.sleep(max(60, nxt - now))


def get(url: str, timeout: int = 120, accept: str | None = None) -> bytes | None:
    """Cached GET. Returns the body for 200, None for 404/410 (cached as a negative answer) and for a URL that
    answered 5xx (marked .err, not retried). Raises Stopped on a challenge, 403, 429 or FIVEXX_STOP 5xx in a row (and
    marks the host stopped). At most one request per GAP (>= 3 s) and DAILY_MAX a UTC day per host."""
    host = _host(url)
    p = path_for(url)
    if p.exists():
        return p.read_bytes()
    neg = p.with_suffix('.404')
    if neg.exists() or p.with_suffix('.err').exists():
        return None
    stop = CACHE / host / 'STOP'
    if stop.exists():
        raise Stopped(f'{host} stopped: {stop.read_text(encoding="utf-8")[:200]}')
    _wait_for_budget(host)
    fd, lock = _lock(host)
    try:
        if day_count(host) >= DAILY_MAX:   # another process used the last of today's budget
            os.close(fd)
            lock.unlink(missing_ok=True)
            fd = None
            return get(url, timeout, accept)
        cnt = CACHE / host / '.day-count.json'
        cnt.write_text(json.dumps({'day': _today(), 'n': day_count(host) + 1}), encoding='utf-8')
        st = CACHE / host / '.last'
        last = float(st.read_text()) if st.exists() else 0.0
        wait = last + max(MIN_GAP, GAP.get(host, GAP['default'])) - time.time()
        if wait > 0:
            time.sleep(wait)
        with tempfile.NamedTemporaryFile(delete=False, dir=CACHE / host) as f:
            tmp = f.name
        cmd = ['curl', '-gsS', '-L', '--compressed', '-A', UA, '--max-time', str(timeout), '-o', tmp,
               '-w', '%{http_code}', url]
        if accept:
            cmd[1:1] = ['-H', f'Accept: {accept}']
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
        if code in (403, 429):
            stop.write_text(f'HTTP {code} at {url}', encoding='utf-8')
            raise Stopped(f'{host}: HTTP {code} at {url}')
        streak = CACHE / host / '.5xx-streak'
        if code >= 500:
            n = (int(streak.read_text()) if streak.exists() else 0) + 1
            streak.write_text(str(n))
            if n >= FIVEXX_STOP:
                stop.write_text(f'{n} HTTP 5xx in a row, last {code} at {url}', encoding='utf-8')
                raise Stopped(f'{host}: {n} HTTP 5xx in a row at {url}')
            p.with_suffix('.err').write_text(str(code))   # this URL failed; the act that needs it is left out
            time.sleep(60)                                # back off before the next request to the host
            return None
        streak.unlink(missing_ok=True)
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
        if fd is not None:
            os.close(fd)
            lock.unlink(missing_ok=True)


if __name__ == '__main__':
    b = get(sys.argv[1])
    if '--out' in sys.argv:
        Path(sys.argv[sys.argv.index('--out') + 1]).write_bytes(b or b'')
    else:
        sys.stdout.buffer.write((b or b'<none>')[:4000])
