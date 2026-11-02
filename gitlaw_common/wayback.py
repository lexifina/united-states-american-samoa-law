"""One shared, adaptive client for the Internet Archive, used by every git-for-law agent on this machine.

    import sys; sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common')
    import wayback
    caps = wayback.captures('zambialii.org/akn/zm/act/1965/', match='prefix')   # one CDX request lists them all
    raw  = wayback.get('https://zambialii.org/akn/zm/act/1965/2/eng@2023-12-31', ts='20240101', cache=CACHE_DIR)

Why: all agents share one IP, so archive.org's limit is per machine, not per agent. A fixed delay per agent is
either too slow (most of the time) or too fast (when twenty agents fire at once). This client keeps ONE rate for
every process on the machine, in a small state file guarded by a lock file:
- one request in flight for the whole machine, the next as soon as the previous one answers (no cap of our own);
- an HTTP 429 or 503 (or a connection failure) halves the rate and pauses everyone for a backoff period, and
  Retry-After is always honoured.
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
import threading
import time
from pathlib import Path

STATE = Path(os.environ.get('GITLAW_ARCHIVE_RATE') or Path(tempfile.gettempdir()) / 'gitlaw-wayback-rate.json')
LOCK = STATE.with_suffix('.lock')
# Alan, 2026-11-02 21:50 UTC: no caps of our own. archive.org gets one request in flight machine-wide and the next
# goes out as soon as the previous one answers. A 429/503/connection failure halves the rate (doubles the interval
# from max(current, latency, THROTTLE_FLOOR), at most 1/MIN), pauses everyone for BACKOFF and recovers by STEP
# requests a second per success; Retry-After is always honoured. The per-day counter is kept for reporting only.
STEP, MIN = 0.05, 0.3                                # recovery req/s per success; slowest throttle (requests a second)
THROTTLE_FLOOR = 0.5
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
            st = {'next': 0.0, 'pause_until': 0.0, 'ok': 0, 'throttled': 0}
        out, st = fn(st)
        STATE.write_text(json.dumps(st), encoding='utf-8')
        return out
    finally:
        os.close(fd)
        LOCK.unlink(missing_ok=True)


_ARCHIVE_SLOT_TTL = 240.0   # a slot outlives _curl's 120 s timeout by this much (a crashed holder frees it then)


def _slot() -> str:
    """Wait until no other archive.org request is in flight on the machine (and any pause is over); returns the slot."""
    lease = f'{os.getpid()}:{threading.get_ident()}:{random.random():.12f}'

    def take(st):
        now = _now()
        day = time.strftime('%Y-%m-%d', time.gmtime(now))
        if st.get('day') != day:
            st['day'], st['count'] = day, 0
        slots = {k: v for k, v in (st.get('inflight') or {}).items() if v > now}
        st['inflight'] = slots
        if slots:
            return None, st
        start = max(now, st.get('next', 0.0), st.get('pause_until', 0.0))
        slots[lease] = start + _ARCHIVE_SLOT_TTL
        st['count'] = st.get('count', 0) + 1
        st['next'] = start + float(st.get('throttle_iv') or 0)
        return start - now, st
    while True:
        wait = _locked(take)
        if wait is None:
            time.sleep(0.01 + random.random() * 0.02)
            continue
        if wait > 0:
            _sleep(wait)
        return lease


class ArchiveDailyCap(RuntimeError):
    """No longer raised (the daily cap was removed on 2026-11-02); kept so callers that catch it still import."""


def _report(ok: bool, lease: str | None = None, code: int = 0, hops=(), lat: float = 0.0) -> None:
    def upd(st):
        now = _now()
        if lease:
            (st.get('inflight') or {}).pop(lease, None)
        if code and lat:
            st['lat'] = lat if 'lat' not in st else 0.8 * st['lat'] + 0.2 * lat
        ra = _retry_after(hops, now) if (code >= 300 and code != 304) else None
        if ra:
            st['pause_until'] = max(st.get('pause_until', 0.0), now + ra)
        if ok:
            st['ok'] = st.get('ok', 0) + 1
            if st.get('throttle_iv'):
                iv = 1.0 / (1.0 / st['throttle_iv'] + STEP)
                if iv <= THROTTLE_FLOOR:
                    st.pop('throttle_iv', None)
                else:
                    st['throttle_iv'] = iv
        else:
            cur = max(float(st.get('throttle_iv') or 0), st.get('lat', 0.0), THROTTLE_FLOOR)
            st['throttle_iv'] = min(2 * cur, 1 / MIN)
            st['pause_until'] = max(st.get('pause_until', 0.0), now + BACKOFF)
            st['throttled'] = st.get('throttled', 0) + 1
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
        lease = _slot()
        t0, done = time.time(), False
        try:
            code, body, hops = _curl_h(url, 120)
            pushback = code in (429, 503) or code == 0
            _report(not pushback, lease, code, hops, time.time() - t0)
            done = True
        finally:
            if not done:
                _report(True, lease)
        if pushback:
            continue
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


class CCDisallowed(RuntimeError):
    """data.commoncrawl.org's robots.txt disallows all agents (seen 2026-10-31): no record downloads while the flag file
    gitlaw_common/CC-DATA-DISALLOWED exists. Not a temporary block, so callers must not retry it."""


def _cc_pace() -> None:
    """Wait for this machine's next Common Crawl slot (one fixed rate shared by every process)."""
    if (Path(__file__).resolve().parent / 'CC-DATA-DISALLOWED').exists():
        raise CCDisallowed('data.commoncrawl.org robots.txt disallows all agents; record downloads paused')

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


# --- Direct fetching from official sites: one request in flight per host, shared by every process on the machine ----
# Alan, 2026-11-02 21:50 UTC ("clear our own pacing caps", end of scripts/world-law/COVERAGE-WAVE.md): no limits of
# our own. A host gets one request in flight machine-wide (HOST_CONCURRENCY), and the next one goes out as soon as the
# previous one answers. No daily cap and no fixed floor; the per-host request counters remain, for reporting only.
# What still slows a host down is the site's own rules:
#   - tier A: a rate the publisher states (terms, API docs), from host_tiers.json ("interval" s or "rate" req/s);
#   - a robots Crawl-delay (the slower of it and any stated rate wins); host_get reads robots.txt once per ROBOTS_TTL;
#   - Retry-After on any 3xx/4xx/5xx answer, always honoured;
#   - a 429/503/time-out halves the host's rate (doubles its interval from max(current interval, latency,
#     HOST_THROTTLE_FLOOR)), pauses everyone for HOST_BACKOFF and drops it to one request in flight; each clean answer
#     then adds HOST_STEP requests a second back, until the throttle is gone;
#   - a challenge or WAF page in any tier stops the host for good: a stop file in HOST_STOP_DIR (outside the temp
#     folder) makes every later call, in every process, raise HostStopped before any request. Never work round one.
# More than one in flight (2026-11-02, Alan): a host_tiers.json "concurrency" of up to HOST_CONCURRENCY_MAX, only for
# documented public APIs that state no limit and show no bot management. The slots are leases in the host's state
# file, under its cross-process lock (a counting semaphore). Any bot-management sign forces 1 for good, and a
# 429/503/time-out forces 1 until the throttle has recovered.
# Tier labels are now informational: A = publisher-stated rate, C = bot management seen (or set by hand), B = the rest.
# D6: 200 responses keep their ETag/Last-Modified in <cache>/.http-meta/<sha256>.json; host_get(url, cache,
# refresh=True) revalidates with If-None-Match/If-Modified-Since, and a 304 serves the cached body and counts
# HOST_304_COST of a request in the host's counter. Cache entries without metadata still work (refresh = full GET).
HOST_STEP, HOST_MIN, HOST_BACKOFF = 0.02, 0.1, 30.0  # recovery req/s per clean answer; slowest throttle 1 per 10 s
HOST_THROTTLE_FLOOR = 0.5         # s: the first halving starts from at least this interval
HOST_CONCURRENCY, HOST_CONCURRENCY_MAX = 1, 8
HOST_LEASE_SLACK = 60.0           # a slot outlives its request's timeout by this much (a crashed holder frees it then)
HOST_DAILY = float('inf')         # no daily cap since 2026-11-02 21:50 UTC; kept (inert) for code that reads it
HOST_304_COST = 0.25
ROBOTS_TTL = 7 * 86400.0
HOST_DIR = Path(os.environ.get('GITLAW_HOST_RATE_DIR') or Path(tempfile.gettempdir()) / 'gitlaw-host-rate')
HOST_STOP_DIR = Path(os.environ.get('GITLAW_HOST_STOP_DIR')
                     or Path(os.environ.get('LOCALAPPDATA') or Path.home() / '.local' / 'state') / 'gitlaw' / 'host-stops')
HOST_TIERS = Path(os.environ.get('GITLAW_HOST_TIERS') or Path(__file__).with_name('host_tiers.json'))
_now, _sleep = time.time, time.sleep   # injectable clock for tests

class HostDailyCap(RuntimeError):
    """No longer raised by host_get (daily caps were removed on 2026-11-02); kept for callers that import or catch it."""


class HostStopped(RuntimeError):
    """This host served a challenge or WAF page (or host_tiers.json says stop): no process requests it again."""


HostChallenged = HostStopped


def _hostfile(host: str) -> str:
    return host.replace(':', '_')  # a port's colon is not allowed in Windows file names


def _host_of(url: str) -> str:
    return url.split('://', 1)[-1].split('/', 1)[0].lower()


def _host_locked(host: str, fn):
    HOST_DIR.mkdir(parents=True, exist_ok=True)
    lock, state = HOST_DIR / f'{_hostfile(host)}.lock', HOST_DIR / f'{_hostfile(host)}.json'
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
            st = {'next': 0.0, 'pause_until': 0.0, 'ok': 0, 'throttled': 0}
        out, st = fn(st)
        tmp = state.with_suffix('.tmp')
        tmp.write_text(json.dumps(st), encoding='utf-8')
        os.replace(tmp, state)
        return out
    finally:
        os.close(fd)
        lock.unlink(missing_ok=True)


def host_status(host: str) -> dict:
    return _host_locked(host.lower(), lambda st: (dict(st), st))


# ---- tier config (host_tiers.json) and stops

_cfg_cache: dict = {'key': None, 'hosts': {}}


def _host_cfg(host: str) -> dict:
    """The host_tiers.json entry for host: exact name, then without 'www.', then '*.parent' wildcards. Entries:
    {"tier": "A"|"B"|"C"|"stop", "rate": req/s or "interval": s, "daily": n, "override_bot": bool, "source": str}."""
    try:
        s = HOST_TIERS.stat()
        key = (str(HOST_TIERS), s.st_mtime_ns, s.st_size)
    except OSError:
        key = ('missing', str(HOST_TIERS))
    if key != _cfg_cache['key']:
        hosts = {}
        if key[0] != 'missing':
            try:
                hosts = {k.lower(): v for k, v in json.loads(HOST_TIERS.read_text(encoding='utf-8')).get('hosts', {}).items()
                         if isinstance(v, dict)}
            except (OSError, ValueError, AttributeError):
                hosts = {}
        _cfg_cache.update(key=key, hosts=hosts)
    hosts = _cfg_cache['hosts']
    name = host.split(':', 1)[0]
    for k in (host, name, name[4:] if name.startswith('www.') else None):
        if k and k in hosts:
            return hosts[k]
    parts = name.split('.')
    for i in range(1, len(parts) - 1):
        k = '*.' + '.'.join(parts[i:])
        if k in hosts:
            return hosts[k]
    return {}


def _stop_file(host: str) -> Path:
    return HOST_STOP_DIR / f'{_hostfile(host)}.json'


def host_stopped(host: str) -> dict | None:
    """Why host is stopped for good ({'reason', 'at', 'url', ...}), or None."""
    host = host.lower()
    if _host_cfg(host).get('tier') == 'stop':
        return {'host': host, 'reason': 'host_tiers.json: ' + str(_host_cfg(host).get('source', 'stop'))}
    try:
        return json.loads(_stop_file(host).read_text(encoding='utf-8'))
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        return {'host': host, 'reason': 'stop file present (unreadable)'}


def _check_stop(host: str) -> None:
    why = host_stopped(host)
    if why:
        raise HostStopped(f'{host}: stopped for good ({why.get("reason")}); never request it again, ask the publisher')


def _stop_host(host: str, url: str, code: int, reason: str) -> None:
    HOST_STOP_DIR.mkdir(parents=True, exist_ok=True)
    rec = {'host': host, 'url': url, 'status': code, 'reason': reason,
           'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'pid': os.getpid()}
    try:
        fd = os.open(_stop_file(host), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(json.dumps(rec))
    except FileExistsError:
        pass

    def mark(st):
        st['stopped'] = rec
        return None, st
    _host_locked(host, mark)


# ---- what a response says about the host

_BOT_COOKIES = (('__cf_bm', 'cloudflare'), ('cf_clearance', 'cloudflare'), ('_abck', 'akamai'), ('bm_sz', 'akamai'),
                ('ak_bmsc', 'akamai'), ('bm_sv', 'akamai'), ('incap_ses', 'imperva'), ('visid_incap', 'imperva'),
                ('nlbi_', 'imperva'), ('reese84', 'imperva'), ('datadome', 'datadome'), ('_px', 'perimeterx'),
                ('aws-waf-token', 'aws-waf'))
_CHALLENGE_STRONG = ('_incapsula_resource', 'incapsula incident id', 'request unsuccessful. incapsula', 'cf-chl-',
                     'cf_chl_opt', '/cdn-cgi/challenge-platform', 'captcha-delivery.com', 'px-captcha',
                     'awswafintegration', 'sucuri_cloudproxy_js', 'sucuri website firewall', 'pardon our interruption',
                     'bm-verify', 'sec-if-cpt', 'kpsdk', 'attention required! | cloudflare',
                     'the requested url was rejected. please consult with your administrator')
_CHALLENGE_WEAK = ('just a moment...', 'checking your browser', 'verify you are human', 'are you a robot', 'g-recaptcha',
                   'hcaptcha.com', 'h-captcha', 'you have been blocked', 'web application firewall',
                   'errors.edgesuite.net', 'datadome')


def _parse_headers(raw: bytes) -> list[tuple[int, list[tuple[str, str]]]]:
    """curl -D output (one block per hop with -L) -> [(status, [(lower name, value)])]."""
    hops = []
    for line in raw.decode('latin-1', 'replace').splitlines():
        line = line.rstrip('\r')
        if line.startswith('HTTP/'):
            try:
                hops.append((int(line.split()[1]), []))
            except (IndexError, ValueError):
                hops.append((0, []))
        elif ':' in line and hops:
            k, v = line.split(':', 1)
            hops[-1][1].append((k.strip().lower(), v.strip()))
    return hops


def _bot_signal(hops) -> str | None:
    """The bot-management product a response shows in any hop's headers or cookies, or None."""
    for _, hdrs in hops:
        names = {k for k, _ in hdrs}
        cookies = [v.split('=', 1)[0].strip().lower() for k, v in hdrs if k == 'set-cookie']
        val = {k: v.lower() for k, v in hdrs}
        if 'cf-mitigated' in names:
            return 'cloudflare (cf-mitigated)'
        for c in cookies:
            for prefix, who in _BOT_COOKIES:
                if c.startswith(prefix) and (who != 'cloudflare' or 'cf-ray' in names or c == 'cf_clearance'):
                    return f'{who} (cookie {c})'
            if len(c) >= 8 and c[:2] == 'ts' and all(ch in '0123456789abcdef' for ch in c[2:]):
                return f'f5 (cookie {c})'
        if 'x-iinfo' in names or 'incapsula' in val.get('x-cdn', '') or 'imperva' in val.get('x-cdn', ''):
            return 'imperva (header)'
        if 'x-datadome' in names or 'x-dd-b' in names:
            return 'datadome (header)'
        if 'x-amzn-waf-action' in names:
            return 'aws-waf (header)'
        if 'x-sucuri-id' in names or 'x-sucuri-cache' in names or 'sucuri' in val.get('server', ''):
            return 'sucuri (header)'
        if any(n.startswith('x-kpsdk') for n in names):
            return 'kasada (header)'
    return None


def _challenge(code: int, hops, body: bytes) -> str | None:
    """Why this response is a challenge or WAF page, or None. 200s are judged by vendor-specific markers only."""
    for _, hdrs in hops:
        for k, v in hdrs:
            if k == 'cf-mitigated' and 'challenge' in v.lower():
                return 'cf-mitigated: challenge'
            if k == 'x-amzn-waf-action' and v.lower() in ('challenge', 'captcha', 'block'):
                return f'x-amzn-waf-action: {v}'
    text = body[:65536].decode('utf-8', 'replace').lower()
    if code == 202 and not body.strip() and _bot_signal(hops):
        return f'HTTP 202 with an empty body from {_bot_signal(hops)}'
    if code >= 400 and 'web page blocked' in text and 'attack id' in text:  # FortiWeb block page (seen as HTTP 500)
        return f'HTTP {code} challenge page (FortiWeb "web page blocked")'
    if code in (403, 429, 503):
        for m in _CHALLENGE_STRONG + _CHALLENGE_WEAK:
            if m in text:
                return f'HTTP {code} challenge page ({m!r})'
    elif code >= 400:
        for m in _CHALLENGE_STRONG:
            if m in text:
                return f'HTTP {code} challenge page ({m!r})'
    elif 200 <= code < 300 and len(body) < 65536:
        for m in _CHALLENGE_STRONG:
            if m in text:
                return f'HTTP {code} challenge page ({m!r})'
        if 'just a moment...' in text and 'cloudflare' in text:
            return f'HTTP {code} challenge page (cloudflare "just a moment")'
    return None


# ---- pacing

def _stated(entry: dict) -> float | None:
    if entry.get('interval'):
        return float(entry['interval'])
    if entry.get('rate'):
        return 1.0 / float(entry['rate'])
    return None


def _policy(host: str, st: dict, now: float) -> dict:
    """{'tier', 'interval' (s between request starts), 'concurrency' (requests in flight), 'daily' (always inf: no
    cap), 'base' (the interval before any throttle), 'reason'} for host given its state at time now."""
    c = _host_cfg(host)
    t = str(c.get('tier', '')).upper()
    if t == 'STOP' or st.get('stopped'):
        return {'tier': 'stop', 'interval': float('inf'), 'concurrency': 0, 'daily': 0, 'base': float('inf'),
                'reason': 'stopped'}
    cd = float(st.get('crawl_delay') or 0)
    bot = st.get('bot')
    if t == 'A' and _stated(c):
        tier, base, why = 'A', _stated(c), 'host_tiers.json: ' + str(c.get('source', 'stated rate'))
    elif bot:
        tier, base, why = 'C', 0.0, f'bot management seen: {bot}'
    elif t == 'C':
        tier, base, why = 'C', 0.0, 'host_tiers.json: ' + str(c.get('source', 'tier C'))
    else:
        tier, base, why = 'B', 0.0, 'no stated rate'
    if cd > base:
        base, why = cd, why + f'; robots Crawl-delay {cd:g}'
    throttle = float(st.get('throttle_iv') or 0)
    conc = HOST_CONCURRENCY
    try:
        conc = max(1, min(HOST_CONCURRENCY_MAX, int(c.get('concurrency') or HOST_CONCURRENCY)))
    except (TypeError, ValueError):
        pass
    if bot:
        conc = 1
    elif throttle or now < float(st.get('pause_until', 0.0)):
        conc = 1
        why += '; throttled after 429/503/time-out'
    return {'tier': tier, 'interval': max(base, throttle), 'concurrency': conc, 'daily': float('inf'),
            'base': base, 'reason': why}


def host_policy(host: str, now: float | None = None) -> dict:
    """The tier, pace and slots host_get applies to host now (for status pages and checks)."""
    host = host.lower()
    st = host_status(host)
    out = _policy(host, st, _now() if now is None else now)
    if host_stopped(host):
        out.update(tier='stop', reason=host_stopped(host).get('reason'))
    return out


def _retry_after(hops, now: float) -> float | None:
    """Seconds a Retry-After header (in seconds or as an HTTP date) asks us to wait, or None."""
    for _, hdrs in reversed(hops):
        for k, v in hdrs:
            if k == 'retry-after':
                v = v.strip()
                try:
                    return max(0.0, float(v))
                except ValueError:
                    pass
                try:
                    from email.utils import parsedate_to_datetime
                    return max(0.0, parsedate_to_datetime(v).timestamp() - now)
                except (TypeError, ValueError, IndexError, OverflowError):
                    return None
    return None


def _note_robots(host: str, code: int | None, crawl_delay: float | None) -> None:
    def upd(st):
        if crawl_delay:
            st['crawl_delay'] = max(float(crawl_delay), 0.0)
        if code is not None:
            now = _now()
            ok = code in (200, 404, 410)
            st['robots_status'] = code
            st['robots_ok'] = ok or st.get('robots_ok', False)
            st['robots_at'] = now if ok else now - ROBOTS_TTL + 86400   # a failed read is retried in a day
            if ok:
                st['crawl_delay'] = float(crawl_delay or 0)
        return None, st
    _host_locked(host, upd)


def _maybe_robots(host: str, url: str) -> None:
    """Read host's robots.txt (fresh, under the host's pace) when it has not been read for ROBOTS_TTL."""
    if url.split('://', 1)[-1].partition('/')[2].split('?', 1)[0] == 'robots.txt':
        return

    def claim(st):
        now = _now()
        if now - st.get('robots_at', 0) < ROBOTS_TTL or now - st.get('robots_claim', 0) < 300:
            return False, st
        st['robots_claim'] = now
        return True, st
    if not _host_locked(host, claim):
        return
    scheme = url.split('://', 1)[0] if '://' in url else 'https'
    code, body, _ = _host_fetch(f'{scheme}://{host}/robots.txt', host, None, 2, 30)
    text = body.decode('utf-8', 'replace') if code == 200 else ''
    if '<html' in text[:500].lower():
        text = ''
    _note_robots(host, code, _parse_robots(text)['crawl_delay'] if code == 200 else None)


def _curl_h(url: str, timeout: int, headers: list[str] = ()) -> tuple[int, bytes, list]:
    """Like _curl, plus request headers in and every hop's response headers out."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        tmp = f.name
    hdr = tmp + '.h'
    try:
        cmd = ['curl', '-gsS', '-L', '--compressed', '-A', UA, '--max-time', str(timeout), '-D', hdr, '-o', tmp,
               '-w', '%{http_code}']
        for h in headers:
            cmd += ['-H', h]
        out = subprocess.run(cmd + [url], capture_output=True, text=True)
        code = int(out.stdout.strip() or 0) if out.returncode == 0 else 0
        try:
            hops = _parse_headers(Path(hdr).read_bytes())
        except OSError:
            hops = []
        return code, (Path(tmp).read_bytes() if code else b''), hops
    finally:
        Path(tmp).unlink(missing_ok=True)
        Path(hdr).unlink(missing_ok=True)


def _host_fetch(url: str, host: str, cache: Path | None, tries: int, timeout: int,
                cond: list[str] = ()) -> tuple[int, bytes, list]:
    """One request under host's slots and pace (retried, as before, on anything but 200/304/403/404/410).
    Raises HostStopped. The per-day counter is kept for reporting and never blocks."""
    code, body, hops = 0, b'', []
    lease = f'{os.getpid()}:{threading.get_ident()}:{random.random():.12f}'
    attempt = 0
    while attempt < tries:
        _check_stop(host)
        _maybe_robots(host, url)

        def take(st):
            now = _now()
            day = time.strftime('%Y-%m-%d', time.gmtime(now))
            if st.get('day') != day:
                st['day'], st['count'] = day, 0
            pol = _policy(host, st, now)
            if pol['tier'] == 'stop':
                return ('stop', 0.0), st
            slots = {k: v for k, v in (st.get('inflight') or {}).items() if v > now}
            if len(slots) >= pol['concurrency']:
                st['inflight'] = slots
                return ('busy', 0.0), st
            start = max(now, st.get('next', 0.0), st.get('pause_until', 0.0))
            slots[lease] = start + timeout + HOST_LEASE_SLACK
            st['inflight'] = slots
            st['count'] = st.get('count', 0) + 1
            st['next'] = start + pol['interval']
            st['tier'] = pol['tier']
            return ('go', start - now), st
        how, wait = _host_locked(host, take)
        if how == 'stop':
            _check_stop(host)
            raise HostStopped(f'{host}: stopped for good')
        if how == 'busy':   # every slot is in use (another thread or process): wait for an answer, in real time
            time.sleep(0.01 + random.random() * 0.02)
            continue
        attempt += 1
        released = False

        def release(st):
            (st.get('inflight') or {}).pop(lease, None)
            return None, st
        try:
            if wait > 0:
                _sleep(wait)
            _check_stop(host)   # another process may have met a challenge while we waited
            t0 = time.time()
            code, body, hops = _curl_h(url, timeout, cond)
            lat = time.time() - t0
            why = _challenge(code, hops, body)
            if why:
                _stop_host(host, url, code, why)
                _log(cache, url, code, 0)
                raise HostStopped(f'{host}: {why} at {url}; stopped for good (never retry, never work round it)')
            signal = _bot_signal(hops)
            pushback = code in (429, 503) or code == 0

            def upd(st):
                now = _now()
                (st.get('inflight') or {}).pop(lease, None)
                if signal:
                    st.setdefault('bot', signal)
                    st.setdefault('bot_at', time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
                if code:
                    st['lat'] = lat if 'lat' not in st else 0.8 * st['lat'] + 0.2 * lat
                ra = _retry_after(hops, now) if (code >= 300 and code != 304) else None
                if ra:
                    st['pause_until'] = max(st.get('pause_until', 0.0), now + ra)
                    st['retry_after'] = ra
                if pushback:
                    base = _policy(host, st, now)['base']
                    cur = max(float(st.get('throttle_iv') or 0), base, st.get('lat', 0.0), HOST_THROTTLE_FLOOR)
                    st['throttle_iv'] = min(2 * cur, max(1 / HOST_MIN, 4 * base))
                    st['pause_until'] = max(st.get('pause_until', 0.0), now + HOST_BACKOFF)
                    st['throttled'] = st.get('throttled', 0) + 1
                else:
                    st['ok'] = st.get('ok', 0) + 1
                    if st.get('throttle_iv'):   # recovery: HOST_STEP requests a second back per clean answer
                        iv = 1.0 / (1.0 / st['throttle_iv'] + HOST_STEP)
                        if iv <= max(HOST_THROTTLE_FLOOR, _policy(host, st, now)['base']):
                            st.pop('throttle_iv', None)
                        else:
                            st['throttle_iv'] = iv
                    if code == 304:
                        st['count'] = max(0.0, st['count'] - (1 - HOST_304_COST))
                        st['not_modified'] = st.get('not_modified', 0) + 1
                return None, st
            _host_locked(host, upd)
            released = True
        finally:
            if not released:
                _host_locked(host, release)
        if code in (200, 304, 403, 404, 410):
            return code, body, hops
    return code, body, hops


def _meta_file(cache: Path, url: str) -> Path:
    return cache / '.http-meta' / (hashlib.sha256(url.encode('utf-8')).hexdigest() + '.json')


def _validators(hops) -> dict:
    hdrs = dict(hops[-1][1]) if hops else {}
    return {k: hdrs[h] for k, h in (('etag', 'etag'), ('last_modified', 'last-modified')) if hdrs.get(h)}


def host_get(url: str, cache: Path | str | None = None, tries: int = 5, timeout: int = 90, *,
             refresh: bool = False) -> bytes | None:
    """GET from an official site under its machine-wide tiered pace (see above). Cached and logged like fetch().

    A cached copy is returned without a request, as before. With refresh=True a cached copy is revalidated: with its
    stored ETag/Last-Modified the request is conditional and a 304 returns the cached body (0.25 of a request against
    the host's counter); an old entry without them is fetched in full. Returns None on 403/404/410 or after `tries`.
    Raises HostStopped for a host that has served a challenge (now or ever). There is no daily cap."""
    host = _host_of(url)
    cache = Path(cache) if cache else None
    hit = _cached(cache, url)
    have = hit is not None and hit.exists()
    if have and not refresh:
        return hit.read_bytes()
    cond, meta_path = [], _meta_file(cache, url) if cache is not None else None
    if have and meta_path is not None:
        try:
            meta = json.loads(meta_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            meta = {}
        if meta.get('etag'):
            cond.append(f'If-None-Match: {meta["etag"]}')
        if meta.get('last_modified'):
            cond.append(f'If-Modified-Since: {meta["last_modified"]}')
    code, body, hops = _host_fetch(url, host, cache, tries, timeout, cond)
    if code == 304 and have:
        _log(cache, url, 304, 0)
        return hit.read_bytes()
    if code == 200:
        _log(cache, url, code, len(body))
        if hit is not None:
            tmp = hit.with_suffix('.part')
            tmp.write_bytes(body)
            os.replace(tmp, hit)
            val = _validators(hops)
            if val:
                meta_path.parent.mkdir(exist_ok=True)
                tmp = meta_path.with_suffix('.part')
                tmp.write_text(json.dumps({'url': url, **val}), encoding='utf-8')
                os.replace(tmp, meta_path)
            else:
                meta_path.unlink(missing_ok=True)
        return body
    if code in (403, 404, 410):
        _log(cache, url, code, 0)
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


# D7 (2026-11-02): a robots.txt group binds us when it names `*`, one of Anthropic's crawlers or our own user agent.
# Groups naming only other vendors' crawlers (GPTBot, CCBot, Google-Extended, ...) do not.
ROBOTS_BINDING = ('claudebot', 'anthropic-ai', 'claude-web', 'lexifina')


def _parse_robots(text: str) -> dict:
    """{'crawl_delay': slowest binding Crawl-delay or None, 'disallow': binding Disallow paths, 'sitemaps': [urls]}."""
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
            mine = any(a == '*' or any(t in a for t in ROBOTS_BINDING) for a in agents)
        elif mine:
            in_rules = True
            if k == 'disallow' and v:
                if v not in rules['disallow']:
                    rules['disallow'].append(v)
            elif k == 'crawl-delay':
                try:
                    cd = float(v)
                except ValueError:
                    continue
                rules['crawl_delay'] = cd if rules['crawl_delay'] is None else max(rules['crawl_delay'], cd)
        else:
            in_rules = True
    return rules


def robots_rules(host: str, cache: Path | str | None = None) -> dict:
    """robots.txt of host for the groups that bind us (`*`, ClaudeBot, anthropic-ai, Claude-Web; see ROBOTS_BINDING):
    {'crawl_delay': float | None, 'disallow': [paths], 'sitemaps': [urls]}. A missing robots.txt (or an HTML page in
    its place) gives no rules. A stated Crawl-delay is also recorded for host_get's pacing."""
    raw = host_get(f'https://{host}/robots.txt', cache, tries=2, timeout=30) or b''
    text = raw.decode('utf-8', 'replace')
    if '<html' in text[:500].lower():
        text = ''
    rules = _parse_robots(text)
    if rules['crawl_delay']:
        _note_robots(host.lower(), None, rules['crawl_delay'])
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
