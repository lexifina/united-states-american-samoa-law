"""One shared, adaptive client for the Internet Archive, used by every git-for-law agent on this machine.

    import sys; sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common')
    import wayback
    caps = wayback.captures('zambialii.org/akn/zm/act/1965/', match='prefix')   # one CDX request lists them all
    raw  = wayback.get('https://zambialii.org/akn/zm/act/1965/2/eng@2023-12-31', ts='20240101', cache=CACHE_DIR)

Why: all agents share one IP, so archive.org's limit is per machine, not per agent. A fixed delay per agent is
either too slow (most of the time) or too fast (when twenty agents fire at once). This client keeps ONE rate for
every process on the machine, in a small state file guarded by a lock file:
- it starts at START requests a second and adds STEP for every success, up to MAX;
- an HTTP 429 or 503 (or a connection failure) halves the rate and pauses everyone for a backoff period.
So the machine runs at whatever archive.org will take, and backs off the moment it complains.

Requests go through curl (Python's TLS fails on this machine) with --compressed. Each response is cached by the
sha256 of its URL in the caller's cache folder and logged to requests.jsonl there, the same layout the country
fetchers use, so parse.py can read it unchanged. Standard library only.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import subprocess
import tempfile
import time
from pathlib import Path

STATE = Path(tempfile.gettempdir()) / 'gitlaw-wayback-rate.json'
LOCK = Path(tempfile.gettempdir()) / 'gitlaw-wayback-rate.lock'
START, STEP, MAX, MIN = 3.0, 0.05, 15.0, 0.3       # requests per second, for the whole machine
BACKOFF = 45.0                                       # seconds everyone waits after a 429/503
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'


# ---------------------------------------------------------------- the shared rate

def _locked(fn):
    """Run fn(state) -> state with an exclusive lock file (O_EXCL works on Windows and POSIX)."""
    for _ in range(2000):
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            try:  # a lock older than 10 s belongs to a crashed process
                if time.time() - LOCK.stat().st_mtime > 10:
                    LOCK.unlink(missing_ok=True)
            except OSError:
                pass
            time.sleep(0.005 + random.random() * 0.01)
    else:
        raise RuntimeError('wayback rate lock stuck')
    try:
        try:
            st = json.loads(STATE.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            st = {'rate': START, 'next': 0.0, 'pause_until': 0.0, 'ok': 0, 'throttled': 0}
        out, st = fn(st)
        STATE.write_text(json.dumps(st), encoding='utf-8')
        return out
    finally:
        os.close(fd)
        LOCK.unlink(missing_ok=True)


def _slot() -> None:
    """Wait for this process's turn under the machine-wide rate."""
    def take(st):
        now = time.time()
        start = max(now, st['next'], st['pause_until'])
        st['next'] = start + 1.0 / st['rate']
        return start - now, st
    wait = _locked(take)
    if wait > 0:
        time.sleep(wait)


def _report(ok: bool) -> None:
    def upd(st):
        if ok:
            st['rate'] = min(MAX, st['rate'] + STEP)
            st['ok'] += 1
        else:
            st['rate'] = max(MIN, st['rate'] / 2)
            st['pause_until'] = time.time() + BACKOFF
            st['throttled'] += 1
        return None, st
    _locked(upd)


def status() -> dict:
    return _locked(lambda st: (dict(st), st))


# ---------------------------------------------------------------- requests

def _curl(url: str, timeout: int = 120) -> tuple[int, bytes]:
    with tempfile.NamedTemporaryFile(delete=False) as f:
        tmp = f.name
    try:
        out = subprocess.run(['curl', '-sS', '-L', '--compressed', '-A', UA, '--max-time', str(timeout),
                              '-o', tmp, '-w', '%{http_code}', url], capture_output=True, text=True)
        code = int(out.stdout.strip() or 0) if out.returncode == 0 else 0
        return code, Path(tmp).read_bytes() if code else b''
    finally:
        Path(tmp).unlink(missing_ok=True)


def _cached(cache: Path | None, url: str) -> Path | None:
    if cache is None:
        return None
    cache.mkdir(parents=True, exist_ok=True)
    return cache / hashlib.sha256(url.encode('utf-8')).hexdigest()


def _log(cache: Path | None, url: str, code: int, size: int) -> None:
    if cache is None:
        return
    rec = json.dumps({'url': url, 'status': code, 'bytes': size, 'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                      'via': 'gitlaw_common/wayback.py'})
    lock = cache / '.requests.lock'
    for _ in range(500):
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            time.sleep(0.01)
    else:
        fd = None
    try:
        with open(cache / 'requests.jsonl', 'a', encoding='utf-8') as f:
            f.write(rec + '\n')
    finally:
        if fd is not None:
            os.close(fd)
            lock.unlink(missing_ok=True)


def fetch(url: str, cache: Path | str | None = None, tries: int = 6) -> bytes | None:
    """GET any archive.org URL under the shared rate; None if it does not exist (404) after the capture lookup."""
    cache = Path(cache) if cache else None
    hit = _cached(cache, url)
    if hit is not None and hit.exists():
        return hit.read_bytes()
    for attempt in range(tries):
        _slot()
        code, body = _curl(url)
        if code in (429, 503) or code == 0:
            _report(False)
            continue
        _report(True)
        _log(cache, url, code, len(body))
        if code == 404:
            return None
        if code != 200:
            if attempt + 1 < tries and code >= 500:
                continue
            return None
        if hit is not None:
            tmp = hit.with_suffix('.part')
            tmp.write_bytes(body)
            os.replace(tmp, hit)
        return body
    return None


def get(page_url: str, ts: str = '2', cache: Path | str | None = None) -> bytes | None:
    """The raw archived bytes of page_url at (or nearest after) timestamp ts, via the `id_` form (no Wayback banner)."""
    return fetch(f'https://web.archive.org/web/{ts}id_/{page_url}', cache)


def captures(url: str, match: str = 'exact', cache: Path | str | None = None, status: str = '200',
             since: str | None = None, until: str | None = None, collapse: str | None = 'digest') -> list[dict]:
    """Every capture of url (or every URL under it with match='prefix') in ONE CDX request:
    [{'timestamp','original','mimetype','statuscode','digest','length'}]. collapse='digest' drops identical copies."""
    q = [f'url={url}', 'output=json', f'matchType={match}', 'fl=timestamp,original,mimetype,statuscode,digest,length']
    if status:
        q.append(f'filter=statuscode:{status}')
    if since:
        q.append(f'from={since}')
    if until:
        q.append(f'to={until}')
    if collapse:
        q.append(f'collapse={collapse}')
    raw = fetch('https://web.archive.org/cdx/search/cdx?' + '&'.join(q), cache)
    if not raw:
        return []
    rows = json.loads(raw.decode('utf-8') or '[]')
    if not rows:
        return []
    head = rows[0]
    return [dict(zip(head, r)) for r in rows[1:]]


# ---------------------------------------------------------------- Common Crawl: the second archive

CC_INDEX = 'https://index.commoncrawl.org'
CC_DATA = 'https://data.commoncrawl.org/'


def cc_crawls(cache: Path | str | None = None) -> list[str]:
    """Every Common Crawl crawl id, newest first (CC-MAIN-2026-43, …). About four a year since 2013."""
    raw = fetch_direct(f'{CC_INDEX}/collinfo.json', cache)
    return [c['id'] for c in json.loads(raw.decode('utf-8'))] if raw else []


def cc_captures(url: str, crawls: list[str] | None = None, match: str = 'exact', cache: Path | str | None = None,
                limit_crawls: int | None = None) -> list[dict]:
    """Every capture of url (or every URL under it with match='prefix') across Common Crawl crawls:
    [{'timestamp','url','status','mime','digest','filename','offset','length','crawl'}]. Index servers have their own
    limits, so this keeps to the shared rate too; the page bytes themselves come from the CDN (cc_get), which does not.
    """
    crawls = crawls or cc_crawls(cache)
    if limit_crawls:
        crawls = crawls[:limit_crawls]
    out = []
    for crawl in crawls:
        page = 0
        while True:
            q = f'{CC_INDEX}/{crawl}-index?url={url}&matchType={match}&output=json&page={page}'
            raw = fetch_direct(q, cache)
            if not raw:
                break
            lines = [l for l in raw.decode('utf-8', 'replace').splitlines() if l.startswith('{')]
            for l in lines:
                r = json.loads(l)
                r['crawl'] = crawl
                out.append(r)
            if len(lines) < 15000:  # the index pages at 15,000 records
                break
            page += 1
    return out


def cc_get(rec: dict, cache: Path | str | None = None) -> bytes | None:
    """The HTTP body of one Common Crawl capture, read by byte range from the WARC file on the CDN."""
    import gzip
    cache = Path(cache) if cache else None
    key = f'cc:{rec["filename"]}:{rec["offset"]}:{rec["length"]}'
    hit = _cached(cache, key)
    if hit is not None and hit.exists():
        return hit.read_bytes()
    start, end = int(rec['offset']), int(rec['offset']) + int(rec['length']) - 1
    for _ in range(4):
        out = subprocess.run(['curl', '-sS', '--max-time', '120', '-A', UA, '-r', f'{start}-{end}', CC_DATA + rec['filename']],
                             capture_output=True)
        if out.returncode == 0 and out.stdout:
            break
        time.sleep(2)
    else:
        return None
    warc = gzip.decompress(out.stdout)
    # WARC header, blank line, HTTP header, blank line, body
    parts = warc.split(b'\r\n\r\n', 2)
    if len(parts) < 3:
        return None
    http_head, body = parts[1], parts[2]
    if b'transfer-encoding: chunked' in http_head.lower():
        pass  # Common Crawl stores bodies de-chunked
    body = body.rstrip(b'\r\n')
    _log(cache, key, int(rec.get('status') or 200), len(body))
    if hit is not None:
        tmp = hit.with_suffix('.part')
        tmp.write_bytes(body)
        os.replace(tmp, hit)
    return body


def fetch_direct(url: str, cache: Path | str | None = None, tries: int = 4) -> bytes | None:
    """GET a non-archive.org URL (Common Crawl's index) with caching and retries; it does not use archive.org's rate."""
    cache = Path(cache) if cache else None
    hit = _cached(cache, url)
    if hit is not None and hit.exists():
        return hit.read_bytes()
    for attempt in range(tries):
        code, body = _curl(url)
        if code == 200:
            _log(cache, url, code, len(body))
            if hit is not None:
                tmp = hit.with_suffix('.part')
                tmp.write_bytes(body)
                os.replace(tmp, hit)
            return body
        if code == 404:
            return None
        time.sleep(2 * (attempt + 1))
    return None


if __name__ == '__main__':
    import sys
    if sys.argv[1:] == ['status']:
        print(json.dumps(status(), indent=1))
    else:
        print(__doc__)
