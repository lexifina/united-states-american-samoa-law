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
        except (FileExistsError, PermissionError):  # Windows: PermissionError while another process deletes the lock
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
        out = subprocess.run(['curl', '-gsS', '-L', '--compressed', '-A', UA, '--max-time', str(timeout),
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
        except (FileExistsError, PermissionError):
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


_CC_UP: list = []  # [checked_at, up]


def _cc_server_up() -> bool:
    """Whether index.commoncrawl.org answers (15 s probe, remembered for 10 minutes)."""
    if _CC_UP and time.time() - _CC_UP[0] < 600:
        return _CC_UP[1]
    code, _ = _curl(f'{CC_INDEX}/collinfo.json', timeout=15)
    _CC_UP[:] = [time.time(), code == 200]
    return _CC_UP[1]


def cc_crawls(cache: Path | str | None = None) -> list[str]:
    """Every Common Crawl crawl id, newest first (CC-MAIN-2026-43, …). About four a year since 2013. Falls back to the
    data host's own listing when the index server does not answer (it timed out from this machine for days)."""
    raw = fetch_direct(f'{CC_INDEX}/collinfo.json', cache) if _cc_server_up() else None
    if raw:
        return [c['id'] for c in json.loads(raw.decode('utf-8'))]
    import re
    out = subprocess.run(['curl', '-gsS', '--max-time', '60', '-A', UA, CC_DATA + 'cc-index/collections/index.html'],
                         capture_output=True)
    ids = set(re.findall(rb'CC-MAIN-\d{4}-\d{2}', out.stdout))
    return sorted((i.decode() for i in ids), reverse=True)


# --- Common Crawl's own index files, read directly from the data host ------------------------------------------------
# When index.commoncrawl.org does not answer, the same CDX index is on data.commoncrawl.org as files: cluster.idx (one
# line per ~3,000 records: SURT key, timestamp, cdx file, offset, length) and cdx-*.gz (gzip members). cluster.idx is
# fetched once per crawl (~120 MB, shared by every agent on the machine) and binary-searched on disk; only the matching
# blocks of cdx-*.gz are then read by byte range.
CC_IDX_DIR = Path(tempfile.gettempdir()) / 'gitlaw-cc-index'


def _surt(url: str) -> str:
    """Common Crawl's SURT key: host reversed and comma-separated, 'www.' dropped, then ')' and the path; lowercased."""
    u = url.split('://', 1)[-1]
    host, _, rest = u.partition('/')
    host = host.lower().split(':')[0]
    if host.startswith('www.'):
        host = host[4:]
    return ','.join(reversed(host.split('.'))) + ')/' + rest.lower()


def _cluster_idx(crawl: str) -> Path | None:
    CC_IDX_DIR.mkdir(exist_ok=True)
    p = CC_IDX_DIR / f'{crawl}.cluster.idx'
    if p.exists() and p.stat().st_size > 1_000_000:
        return p
    lock = p.with_suffix('.lock')
    for _ in range(3600):  # another process may be downloading it
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except (FileExistsError, PermissionError):
            if p.exists() and p.stat().st_size > 1_000_000:
                return p
            try:
                if time.time() - lock.stat().st_mtime > 900:
                    lock.unlink(missing_ok=True)
            except OSError:
                pass
            time.sleep(1)
    else:
        return None
    try:
        tmp = p.with_suffix('.part')
        out = subprocess.run(['curl', '-gsS', '--max-time', '1200', '-A', UA, '-o', str(tmp),
                              f'{CC_DATA}cc-index/collections/{crawl}/indexes/cluster.idx'], capture_output=True)
        if out.returncode or not tmp.exists() or tmp.stat().st_size < 1_000_000:
            tmp.unlink(missing_ok=True)
            return None
        os.replace(tmp, p)
        return p
    finally:
        os.close(fd)
        lock.unlink(missing_ok=True)


def _idx_line(f, pos: int) -> tuple[int, bytes]:
    """The first whole line starting at or after byte pos: (its start, the line)."""
    if pos:
        f.seek(pos - 1)
        f.readline()
    start = f.tell()
    return start, f.readline()


def _blocks(idx: Path, key: str, prefix: bool) -> list[tuple[str, int, int]]:
    """The cdx blocks that can hold `key` (or every key starting with it): [(cdx file, offset, length)]."""
    k = key.encode()
    with open(idx, 'rb') as f:
        lo, hi = 0, idx.stat().st_size
        while hi - lo > 1:  # last line whose key is < k
            mid = (lo + hi) // 2
            start, line = _idx_line(f, mid)
            if line and line.split(b' ', 1)[0] < k:
                lo = mid
            else:
                hi = mid
        _, line = _idx_line(f, lo)
        if line and line.split(b' ', 1)[0] >= k:
            f.seek(0)
            line = f.readline()
        out = []
        while line:
            surt = line.split(b' ', 1)[0]
            if out and (surt > k and not (prefix and surt.startswith(k))):
                break
            parts = line.rstrip(b'\n').split(b'\t')
            out.append((parts[1].decode(), int(parts[2]), int(parts[3])))
            if len(out) > 2000:
                break
            line = f.readline()
    return out


class CCBlocked(RuntimeError):
    """data.commoncrawl.org is refusing this machine (403 "Request blocked" after too many requests). Wait a few
    minutes and retry: an empty result while blocked would wrongly read as "no captures"."""


CC_RATE = 20.0  # requests a second to data.commoncrawl.org for the whole machine; ~130/s got it blocked (2026-10-29)


def _cc_pace() -> None:
    """Wait for this machine's next Common Crawl slot (one fixed rate shared by every process)."""
    def take(st):
        now = time.time()
        start = max(now, st['next'], st['pause_until'])
        st['next'] = start + 1.0 / CC_RATE
        return start - now, st
    wait = _host_locked('data.commoncrawl.org', take)
    if wait > 0:
        time.sleep(wait)


def _cc_check_blocked() -> None:
    if not cc_ok():
        raise CCBlocked('data.commoncrawl.org is blocking this machine; retry in a few minutes')


def _cc_captures_files(url: str, crawl: str, match: str) -> list[dict] | None:
    import gzip
    idx = _cluster_idx(crawl)
    if not idx:
        return None
    key, prefix = _surt(url), match == 'prefix'
    out = []
    for cdx, off, length in _blocks(idx, key, prefix):
        _cc_pace()
        r = subprocess.run(['curl', '-gsS', '--max-time', '120', '-A', UA, '-r', f'{off}-{off + length - 1}',
                            f'{CC_DATA}cc-index/collections/{crawl}/indexes/{cdx}'], capture_output=True)
        if r.returncode or not r.stdout:
            _cc_check_blocked()
            return None
        try:
            text = gzip.decompress(r.stdout).decode('utf-8', 'replace')
        except (OSError, EOFError):
            # An XML error page instead of index data: older crawls have some (skip the block), but so does a block on
            # this machine, which must not pass for "no captures".
            _cc_check_blocked()
            continue
        for line in text.splitlines():
            if line.count(' ') < 2:
                continue
            surt, ts, js = line.split(' ', 2)
            if surt == key or (prefix and surt.startswith(key)):
                rec = json.loads(js)
                rec.update(timestamp=ts, crawl=crawl)
                out.append(rec)
    return out


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
    server_up = _cc_server_up()
    for crawl in crawls:
        if not server_up:
            # The index server is down: read the crawl's index files from the data host instead (same records).
            out.extend(_cc_captures_files(url, crawl, match) or [])
            continue
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
        _cc_pace()
        out = subprocess.run(['curl', '-gsS', '--max-time', '120', '-A', UA, '-r', f'{start}-{end}', CC_DATA + rec['filename']],
                             capture_output=True)
        if out.returncode == 0 and out.stdout:
            break
        time.sleep(2)
    else:
        _cc_check_blocked()
        return None
    try:
        warc = gzip.decompress(out.stdout)
    except (OSError, EOFError):
        _cc_check_blocked()  # a 403 page in place of the record: raise rather than pass for a missing capture
        return None
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


# --- Fast direct fetching from official sites: one adaptive rate per host, shared by every process on the machine -----
# Starts at HOST_START requests a second, climbs with every success up to HOST_MAX, and halves (with a pause for
# everyone) only when the host itself pushes back: 429, 503 or a timeout. This replaces fixed per-agent sleeps
# (3 a second, IMPO's 10 s crawl delay), which left most of the time idle. Use host_get(url, cache) from a thread pool.
HOST_START, HOST_STEP, HOST_MAX, HOST_MIN, HOST_BACKOFF = 4.0, 0.25, 25.0, 0.5, 30.0
HOST_DIR = Path(tempfile.gettempdir()) / 'gitlaw-host-rate'


def _host_locked(host: str, fn):
    HOST_DIR.mkdir(exist_ok=True)
    lock, state = HOST_DIR / f'{host}.lock', HOST_DIR / f'{host}.json'
    for _ in range(4000):
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except (FileExistsError, PermissionError):
            try:
                if time.time() - lock.stat().st_mtime > 10:
                    lock.unlink(missing_ok=True)
            except OSError:
                pass
            time.sleep(0.003 + random.random() * 0.006)
    else:
        raise RuntimeError(f'host rate lock stuck for {host}')
    try:
        try:
            st = json.loads(state.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            st = {'rate': HOST_START, 'next': 0.0, 'pause_until': 0.0, 'ok': 0, 'throttled': 0}
        out, st = fn(st)
        state.write_text(json.dumps(st), encoding='utf-8')
        return out
    finally:
        os.close(fd)
        lock.unlink(missing_ok=True)


def host_status(host: str) -> dict:
    return _host_locked(host, lambda st: (dict(st), st))


def host_get(url: str, cache: Path | str | None = None, tries: int = 5, timeout: int = 90) -> bytes | None:
    """GET from an official site under its machine-wide adaptive rate (see above). Cached and logged like fetch()."""
    host = url.split('://', 1)[-1].split('/', 1)[0].lower()
    cache = Path(cache) if cache else None
    hit = _cached(cache, url)
    if hit is not None and hit.exists():
        return hit.read_bytes()
    for _ in range(tries):
        def take(st):
            now = time.time()
            start = max(now, st['next'], st['pause_until'])
            st['next'] = start + 1.0 / st['rate']
            return start - now, st
        wait = _host_locked(host, take)
        if wait > 0:
            time.sleep(wait)
        code, body = _curl(url, timeout=timeout)
        pushback = code in (429, 503) or code == 0

        def upd(st):
            if pushback:
                st['rate'] = max(HOST_MIN, st['rate'] / 2)
                st['pause_until'] = time.time() + HOST_BACKOFF
                st['throttled'] += 1
            else:
                st['rate'] = min(HOST_MAX, st['rate'] + HOST_STEP)
                st['ok'] += 1
            return None, st
        _host_locked(host, upd)
        if code == 200:
            _log(cache, url, code, len(body))
            if hit is not None:
                tmp = hit.with_suffix('.part')
                tmp.write_bytes(body)
                os.replace(tmp, hit)
            return body
        if code in (403, 404, 410):
            _log(cache, url, code, 0)
            return None
    return None


# --- Arquivo.pt (Portuguese public web archive): open CDX + raw replay --------------------------------------------------
# Approved by the user 2026-10-29 ("yes, do the thing that gives us max speed") although its robots.txt disallows
# /wayback and asks 1 request per 5 s: it goes through host_get's adaptive per-host rate, which backs off on any
# 429/503/timeout. Strong for Lusophone and Latin American official sites (Planalto, IMPO, ...) captured since ~2008.
PT_ARCHIVE = 'https://arquivo.pt/wayback'


def pt_captures(url: str, match: str = 'exact', cache: Path | str | None = None, status: str = '200',
                limit: int = 100000) -> list[dict]:
    """Every Arquivo.pt capture of url (or under it with match='prefix'): [{'timestamp','url','status','digest',...}]."""
    from urllib.parse import quote
    q = f'{PT_ARCHIVE}/cdx?url={quote(url, safe=":/")}&matchType={match}&output=json&limit={limit}'
    if status:
        q += f'&filter=status:{status}'
    raw = host_get(q, cache)
    if not raw:
        return []
    out = []
    for line in raw.decode('utf-8', 'replace').splitlines():
        if line.startswith('{'):
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def pt_get(rec_or_url, ts: str | None = None, cache: Path | str | None = None) -> bytes | None:
    """The raw archived body of one Arquivo.pt capture (a pt_captures record, or url + ts)."""
    if isinstance(rec_or_url, dict):
        url, ts = rec_or_url['url'], rec_or_url['timestamp']
    else:
        url = rec_or_url
    return host_get(f'{PT_ARCHIVE}/{ts}id_/{url}', cache)


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


# --- Added 2026-10-29 by the scraping experiments (scripts/world-law/experiments/SCRAPING-LOG.md) ------------------------

def cc_ok() -> bool:
    """Whether data.commoncrawl.org is serving this machine right now (one HEAD request, about 0.1 s).

    On 2026-10-29 CloudFront answered every request from this machine with 403 "Request blocked" for about three
    minutes after bursts of ~130 range requests a second. While that lasts, cc_captures() silently returns [] (the
    403 page is skipped like a bad gzip block) and cc_get() fails, so call this before believing an empty Common Crawl
    result. Keep the whole machine to about 25 Common Crawl requests a second.
    """
    out = subprocess.run(['curl', '-gsS', '-I', '-A', UA, '--max-time', '20', '-o', os.devnull, '-w', '%{http_code}',
                          CC_DATA + 'cc-index/collections/index.html'], capture_output=True, text=True)
    return out.stdout.strip() == '200'


def robots_rules(host: str, cache: Path | str | None = None) -> dict:
    """robots.txt of host for `User-agent: *`: {'crawl_delay': float | None, 'disallow': [paths], 'sitemaps': [urls]}.
    A missing robots.txt (or an HTML page in its place) gives no rules."""
    raw = host_get(f'https://{host}/robots.txt', cache, tries=2, timeout=30) or b''
    text = raw.decode('utf-8', 'replace')
    if '<html' in text[:500].lower():
        text = ''
    rules = {'crawl_delay': None, 'disallow': [], 'sitemaps': []}
    agents, in_rules, mine = [], False, False
    for line in text.splitlines():
        line = line.split('#', 1)[0].strip()
        if ':' not in line:
            continue
        k, v = (s.strip() for s in line.split(':', 1))
        k = k.lower()
        if k == 'sitemap':
            rules['sitemaps'].append(v)
        elif k == 'user-agent':
            if in_rules:  # a new group starts
                agents, in_rules = [], False
            agents.append(v.lower())
            mine = '*' in agents
        elif mine:
            in_rules = True
            if k == 'disallow' and v:
                rules['disallow'].append(v)
            elif k == 'crawl-delay':
                try:
                    rules['crawl_delay'] = float(v)
                except ValueError:
                    pass
        else:
            in_rules = True
    return rules


def robots_allows(url: str, disallow: list[str]) -> bool:
    """Whether url's path is outside every Disallow rule (with robots.txt's '*' and '$' wildcards)."""
    import re
    path = '/' + url.split('://', 1)[-1].partition('/')[2]
    for rule in disallow:
        pat = '^' + re.escape(rule).replace(r'\*', '.*')
        if pat.endswith(r'\$'):
            pat = pat[:-2] + '$'
        if re.match(pat, path):
            return False
    return True


def sitemap_urls(root: str, cache: Path | str | None = None, threads: int = 8, with_lastmod: bool = False,
                 obey_robots: bool = True, max_files: int = 20000) -> list:
    """Every page URL a site lists in its sitemaps, walking sitemap indexes (and .xml.gz files) to the end.

    root is a host ('www.fedlex.admin.ch': its robots.txt Sitemap lines, else /sitemap.xml) or a sitemap URL.
    Measured 2026-10-29: Fedlex 384,305 URLs in 41 requests (14 s), Finlex 369,848 in 94 (32 s), Retsinformation
    200,007 in 22 (9 s), Legilux 100,132 in 12 (10 s), wetten.overheid.nl 47,172 in one request. Requests go through
    host_get's adaptive per-host rate; a robots.txt Crawl-delay is obeyed (one request at a time, that far apart),
    and with obey_robots the returned URLs exclude Disallowed paths. Returns [url] or, with with_lastmod,
    [(url, lastmod or '')]. Sitemaps tell you what exists, not what changed: lastmod is often missing or wrong.
    """
    import gzip
    import re
    from concurrent.futures import ThreadPoolExecutor
    host = root.split('://', 1)[-1].split('/', 1)[0].lower()
    rules = robots_rules(host, cache) if (obey_robots or '://' not in root) else {'crawl_delay': None, 'disallow': [],
                                                                                    'sitemaps': []}
    if '://' in root:
        todo = [root]
    else:
        todo = rules['sitemaps'] or [f'https://{host}/sitemap.xml']
    delay = rules['crawl_delay']

    def one(url: str) -> str:
        if delay:
            time.sleep(delay)
        raw = host_get(url, cache, tries=3, timeout=120) or b''
        if raw[:2] == b'\x1f\x8b':
            try:
                raw = gzip.decompress(raw)
            except (OSError, EOFError):
                return ''
        return raw.decode('utf-8', 'replace')

    seen, out = set(), []
    entry = re.compile(r'<(sitemap|url)>(.*?)</\1>', re.S)
    loc = re.compile(r'<loc>\s*(.*?)\s*</loc>', re.S)
    mod = re.compile(r'<lastmod>\s*(.*?)\s*</lastmod>', re.S)
    while todo and len(seen) < max_files:
        batch = [u for u in dict.fromkeys(todo) if u not in seen][:max_files - len(seen)]
        seen.update(batch)
        todo = []
        with ThreadPoolExecutor(1 if delay else threads) as ex:
            for text in ex.map(one, batch):
                for kind, body in entry.findall(text):
                    m = loc.search(body)
                    if not m:
                        continue
                    u = m.group(1).replace('&amp;', '&')
                    if kind == 'sitemap':
                        todo.append(u)
                    elif not obey_robots or robots_allows(u, rules['disallow']):
                        if with_lastmod:
                            lm = mod.search(body)
                            out.append((u, lm.group(1) if lm else ''))
                        else:
                            out.append(u)
    return out


def cc_table_query(prefix: str, crawls: list[str], where: str = '', columns: str | None = None,
                   subset: str = 'warc', threads: int = 8) -> list[dict]:
    """Query Common Crawl's columnar index (Parquet) for every capture under a SURT prefix, with any SQL filter.

    For discovery across a whole TLD or set of hosts, which the cluster.idx route (cc_captures) cannot do: on
    2026-10-29, `cc_table_query('br,gov,', two crawls, "content_mime_detected='application/pdf' and fetch_status=200")`
    found 329,619 PDF captures over 4,814 government hosts in 84 s. For ONE host, cc_captures is ~100x faster.
    prefix is a SURT ('br,gov,' or 'br,gov,planalto)/ccivil_03') or a URL/host (converted with _surt). where is extra
    SQL over the table's columns (content_mime_detected, fetch_status, content_languages, url_host_name, ...).
    Needs the duckdb package (pip install duckdb); not stdlib, so imported here only. Each crawl's row-group ranges
    are read once (300 footer requests, ~20 s) and cached in CC_IDX_DIR for every agent on the machine.
    Returns dicts with url, timestamp, status, mime, digest, filename, offset, length, crawl (cc_get-ready).
    """
    import duckdb  # noqa: PLC0415
    from concurrent.futures import ThreadPoolExecutor
    if '://' in prefix or (',' not in prefix and '.' in prefix):
        prefix = _surt(prefix if '://' in prefix else 'http://' + prefix)
    hi = prefix + '\x7f'
    CC_IDX_DIR.mkdir(exist_ok=True)

    def connect():
        c = duckdb.connect(config={'custom_user_agent': UA})
        c.sql('LOAD httpfs')
        c.sql(f'SET http_retries=3; SET threads={threads}; SET enable_progress_bar=false; '
              'SET enable_http_metadata_cache=true')
        return c

    def row_groups(crawl: str) -> list:
        f = CC_IDX_DIR / f'{crawl}.{subset}.rowgroups.json'
        if f.exists():
            return json.loads(f.read_text(encoding='utf-8'))
        import gzip
        r = subprocess.run(['curl', '-gsS', '--max-time', '120', '-A', UA,
                            f'{CC_DATA}crawl-data/{crawl}/cc-index-table.paths.gz'], capture_output=True)
        paths = [p for p in gzip.decompress(r.stdout).decode().split() if f'/subset={subset}/' in p]

        def footer(p):
            u = CC_DATA + p
            c = connect()
            try:
                return [(u, lo, hi_) for lo, hi_ in c.sql(
                    f"select stats_min_value, stats_max_value from parquet_metadata('{u}') "
                    f"where path_in_schema='url_surtkey'").fetchall()]
            finally:
                c.close()
        with ThreadPoolExecutor(threads) as ex:
            rows = [x for part in ex.map(footer, paths) for x in part]
        tmp = f.with_suffix('.part')
        tmp.write_text(json.dumps(rows), encoding='utf-8')
        os.replace(tmp, f)
        return rows

    cols = columns or ("url, strftime(fetch_time, '%Y%m%d%H%M%S') as timestamp, fetch_status as status, "
                       "content_mime_detected as mime, content_digest as digest, warc_filename as filename, "
                       "warc_record_offset as offset, warc_record_length as length")
    out, c = [], connect()
    try:
        for crawl in crawls:
            files = sorted({u for u, lo, h in row_groups(crawl) if lo <= hi and h >= prefix})
            if not files:
                continue
            lst = ', '.join(f"'{u}'" for u in files)
            q = (f"select {cols} from read_parquet([{lst}]) where url_surtkey >= '{prefix}' and url_surtkey < '{hi}'"
                 + (f' and ({where})' if where else ''))
            rel = c.sql(q)
            names = rel.columns
            for row in rel.fetchall():
                rec = dict(zip(names, row))
                rec['crawl'] = crawl
                out.append(rec)
    finally:
        c.close()
    return out


if __name__ == '__main__':
    import sys
    if sys.argv[1:] == ['status']:
        print(json.dumps(status(), indent=1))
    else:
        print(__doc__)
