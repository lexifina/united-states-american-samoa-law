"""One fetch scheduler for every git-for-law scraper on this machine (gitlaw-scraper-dell, gitlaw-scraper-hp-omen).

    import sys; sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common')
    import fetch_scheduler as fs
    body = fs.get(url)                                  # bytes, or None on 403/404/410 (like wayback.host_get)
    for url, res in fs.fetch_many(urls): ...             # res is bytes, None or an exception; hosts interleaved
    fs.adopt(H)                                         # route a br_city_get.Host's network requests through here

    python scripts/gitlaw_common/fetch_scheduler.py status [--json | --jsonl] [host ...]

It is the layer above wayback.host_get, which keeps the per-request rules: the per-host pace (a publisher-stated
rate, robots Crawl-delay, halving on 429/503) in its lock-protected per-host state, which every process shares, the
D6 conditional requests, and stop-for-good on a challenge (HostStopped). This module never re-implements those.
Since 2026-11-02 21:50 UTC (COVERAGE-WAVE.md, "Own pacing caps removed") the scheduler sets no limit of its own: no
daily cap, no floor, no ramp, no worker cap. A host gets one request in flight and the next as soon as the last one
answers, unless the site's own rules (robots, stated rate, Retry-After, 429/503, night window) say otherwise.
It adds:
- publisher-night windows: allowed hours per host (WINDOWS below, the registry, or a robots Visit-time). Outside the
  window get() waits, or with wait=False raises NotNow(next_open).
- one shared cache for both scrapers: host_get's URL-keyed cache with ETag/Last-Modified in SHARED_CACHE, each body
  hard-linked to a content-addressed object (objects/<sha256 of the body>), and 404/410 remembered. A URL that either
  scraper fetched is never fetched again; refresh=True revalidates with a conditional request.
- the hosts registry (REGISTRY, JSON): each host's tier, pace, daily cap and the evidence for them (headers and
  bot-management signs seen, a robots.txt excerpt), its window and any block.
- extra stop-for-good rules on top of host_get's challenge markers: a 403 or 429 on robots.txt, a redirect with no
  Location (Sucuri's 307), a small page holding a captcha form, a DDoS-Guard page. Blocked hosts are refused by every
  caller; a block is lifted only when a person writes "lift_note" in the host's registry entry (see README).
- fair queueing: requests in flight per host limited across all processes (leases in host_get's host state),
  different hosts in parallel, round-robin over the hosts that are ready (fetch_many). The number in flight is
  host_get's own (host_tiers.json "concurrency", 1-8, only for documented public APIs that state no limit; host_get
  drops it to 1 on a 429/503/time-out until its throttle recovers, and for good on a bot-management sign). The
  scheduler adds the path scope and the evidence: INFLIGHT below, or the registry field "max_inflight", names a
  host's API paths; anything else on that host (crawled HTML) stays at 1 in flight.
- Retry-After (honoured by host_get, machine-wide): get() retries inside the host's lease only while the pause is at
  most RETRY_AFTER_MAX_WAIT; a longer one returns None at once and the host stays paused for every caller.
- telemetry: one JSON line per request in FEED_DIR/<UTC day>.jsonl, and the status command.
- GITLAW_FETCH_DRY=1: no network. Cached answers are served; anything else raises DryMiss with what would happen.
Standard library only. See README-fetch-scheduler.md for adoption.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import random
import re
import sys
import threading
import time
from collections import deque
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import wayback  # noqa: E402
from wayback import HostDailyCap, HostStopped  # noqa: E402,F401  (re-exported for callers)

_STATE_ROOT = Path(os.environ.get('LOCALAPPDATA') or Path.home() / '.local' / 'state') / 'gitlaw'
SCHED_DIR = Path(os.environ.get('GITLAW_SCHED_DIR') or _STATE_ROOT / 'fetch-scheduler')
SHARED_CACHE = SCHED_DIR / 'cache'          # host_get layout: <sha256(url)>, .http-meta/, requests.jsonl
OBJECTS = SCHED_DIR / 'objects'             # content-addressed bodies: <sha256(body)>
FEED_DIR = Path(os.environ.get('GITLAW_FETCH_FEED') or SCHED_DIR / 'feed')
REGISTRY = Path(os.environ.get('GITLAW_FETCH_REGISTRY') or HERE / 'fetch_hosts.json')
SESSION = os.environ.get('GITLAW_SESSION') or os.environ.get('COMPUTERNAME', 'unknown').lower()
DRY = os.environ.get('GITLAW_FETCH_DRY') == '1'
LEASE_SLACK = 60.0       # a lease outlives its request's timeout by this much (a crashed holder frees it then)
MAX_INFLIGHT_CEILING = 8 # Alan, 2026-11-02: 4-8 in flight, documented public APIs only (host_get's own maximum too)

# Documented public APIs that state no limit (checked 2026-11-02). Keys: host without 'www.'; paths: the API path
# prefixes (other pages on the host, such as crawled HTML, stay at 1). A registry "max_inflight" replaces an entry.
# host_get grants the slots: each of these also needs its host_tiers.json "concurrency" (set to n there).
INFLIGHT = {
    'boe.es': {'n': 4, 'paths': ['/datosabiertos/api/'],
               'evidence': 'BOE open data API, documented at www.boe.es/datosabiertos/api/api.php; the page states no '
                           'rate, quota or concurrency limit (only a results-per-response default of 50); checked '
                           '2026-11-02'},
    'data.sa.gov.au': {'n': 4, 'paths': ['/data/'],
                       'evidence': 'data.sa.gov.au CKAN: the Action API (/data/api/3/action/, the standard documented '
                                   'CKAN API) and its dataset files (/data/dataset/...); no stated rate limit found; '
                                   'checked 2026-11-02'},
    # busquedas.elperuano.pe: not added. No official API documentation found (2026-11-02), only an unofficial MCP
    # project that asks users not to scrape it at scale; it stays at 1 in flight.
}
EVIDENCE_TTL = 7 * 86400.0
RETRY_AFTER_MAX_WAIT = 300.0   # get() waits out a Retry-After up to this long and retries; longer: returns None

# Publisher-night windows from global-law-unblock-report.html (2026-11-02). hours are local "HH:MM-HH:MM" ranges
# (a range may wrap past midnight); all_day names weekdays allowed in full. A registry "window" replaces these.
WINDOWS = {
    'ris.bka.gv.at': {'tz': 'Europe/Vienna', 'hours': ['20:00-05:00'], 'all_day': ['sat', 'sun'],
                      'source': 'RIS terms: mass downloads 20:00-05:00 Vienna, weekends and holidays (holidays not '
                                'modelled); announce to ris.it@bka.gv.at first'},
    'data.bka.gv.at': {'tz': 'Europe/Vienna', 'hours': ['20:00-05:00'], 'all_day': ['sat', 'sun'],
                       'source': 'RIS OGD API, same terms as ris.bka.gv.at'},
    'ogd.ris.bka.gv.at': {'tz': 'Europe/Vienna', 'hours': ['20:00-05:00'], 'all_day': ['sat', 'sun'],
                          'source': 'RIS OGD FAQ (28 Nov 2025): only 20:00-05:00 Vienna, weekends, holidays'},
    'legislation.gov.au': {'tz': 'Etc/GMT-10', 'hours': ['20:00-08:00'],
                           'source': 'Federal Register of Legislation: outside 08:00-20:00 at UTC+10'},
    'api.prod.legislation.gov.au': {'tz': 'Etc/GMT-10', 'hours': ['20:00-08:00'],
                                    'source': 'Federal Register of Legislation API: outside 08:00-20:00 at UTC+10'},
    'consiglioregionale.calabria.it': {'tz': 'UTC', 'hours': ['06:00-08:44'],
                                       'source': 'robots.txt Visit-time 0600-0844 (UTC)'},
}
_DAYS = ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')


class NotNow(RuntimeError):
    """The host is outside its allowed hours (or busy, with wait=False). .at is when to come back (epoch s)."""

    def __init__(self, msg: str, at: float):
        super().__init__(msg)
        self.at = at


class DryMiss(RuntimeError):
    """GITLAW_FETCH_DRY=1 and the URL is not cached: this is what a live run would have done."""


def _now() -> float:
    return wayback._now()


def _sleep(s: float) -> None:
    wayback._sleep(s)


def _iso(t: float | None = None) -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(_now() if t is None else t))


def _host_of(url: str) -> str:
    return wayback._host_of(url)


def _base(host: str) -> str:
    h = host.split(':', 1)[0]
    return h[4:] if h.startswith('www.') else h


# ---------------------------------------------------------------- the registry (fetch_hosts.json)

_REG_LOCK = threading.Lock()
_reg_cache: dict = {'key': None, 'data': None}


def _file_lock(path: Path):
    for _ in range(4000):
        try:
            return os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except (FileExistsError, PermissionError):
            try:
                if time.time() - path.stat().st_mtime > 10:
                    path.unlink(missing_ok=True)
            except OSError:
                pass
            time.sleep(0.003 + random.random() * 0.006)
    raise RuntimeError(f'lock stuck: {path}')


def _replace(src: Path, dst: Path) -> None:
    """os.replace, retried: on Windows it fails with 'Access is denied' while another thread or process has dst open
    (an unlocked reader of the registry, a reader of a cache file)."""
    for i in range(200):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if i == 199:
                raise
            time.sleep(0.005 + random.random() * 0.01)


def _reg_read() -> dict:
    try:
        s = REGISTRY.stat()
        key = (str(REGISTRY), s.st_mtime_ns, s.st_size)
    except OSError:
        return {'hosts': {}}
    if key != _reg_cache['key']:
        try:
            data = json.loads(REGISTRY.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            data = _reg_cache['data'] or {'hosts': {}}   # mid-edit by a person: keep the last good copy
        _reg_cache.update(key=key, data=data)
    return _reg_cache['data']


def _reg_update(host: str, fn) -> dict:
    """Read-modify-write one host's registry entry under the registry lock; returns the new entry."""
    with _REG_LOCK:
        REGISTRY.parent.mkdir(parents=True, exist_ok=True)
        lock = REGISTRY.with_name(REGISTRY.name + '.lock')
        fd = _file_lock(lock)
        try:
            try:
                data = json.loads(REGISTRY.read_text(encoding='utf-8'))
            except FileNotFoundError:
                data = {}
            except ValueError:
                raise RuntimeError(f'{REGISTRY} is not valid JSON (a hand edit?); fix it before fetching')
            data.setdefault('_doc', 'Hosts registry of gitlaw_common/fetch_scheduler.py: tier, pace and '
                                    'their evidence per host, written by the scheduler. People may edit "window" and, '
                                    'to lift a block, "lift_note" (see README-fetch-scheduler.md).')
            hosts = data.setdefault('hosts', {})
            e = hosts.get(host) or {'first_seen': _iso()}
            e = fn(e) or e
            hosts[host] = e
            tmp = REGISTRY.with_name(REGISTRY.name + f'.{os.getpid()}.tmp')
            tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False, sort_keys=True), encoding='utf-8')
            _replace(tmp, REGISTRY)
            return e
        finally:
            os.close(fd)
            lock.unlink(missing_ok=True)


def registry_entry(host: str) -> dict:
    return dict(_reg_read().get('hosts', {}).get(host.lower(), {}))


# ---------------------------------------------------------------- blocks

def _lift_if_noted(host: str, e: dict) -> dict:
    """A person wrote lift_note on a blocked host: clear the block here and in host_get (its stop file and state)."""
    if not (e.get('blocked') and str(e.get('lift_note') or '').strip()):
        return e

    def lift(e):
        if not (e.get('blocked') and str(e.get('lift_note') or '').strip()):
            return e
        e.setdefault('history', []).append({'blocked': e.pop('blocked'), 'lifted': _iso(), 'note': e.pop('lift_note'),
                                            'by': e.pop('lifted_by', None)})
        return e
    e = _reg_update(host, lift)
    sf = wayback._stop_file(host)
    if sf.exists():
        _replace(sf, sf.with_name(sf.name + f'.lifted-{int(time.time())}'))

    def clear(st):
        st.pop('stopped', None)
        return None, st
    wayback._host_locked(host, clear)
    return e


def blocked(host: str) -> dict | None:
    """Why host is refused ({'reason', 'at', ...}) or None: a registry block, a host_get stop file, or tier stop."""
    host = host.lower()
    e = registry_entry(host)
    if e.get('blocked'):
        e = _lift_if_noted(host, e)
        if e.get('blocked'):
            return e['blocked']
    return wayback.host_stopped(host)


def _record_block(host: str, url: str, reason: str, status: int | None = None) -> None:
    def mark(e):
        if not e.get('blocked'):
            e['blocked'] = {'at': _iso(), 'reason': reason, 'url': url, 'status': status, 'session': SESSION}
        e['tier'] = 'stop'
        return e
    _reg_update(host, mark)
    _feed({'host': host, 'url': url, 'event': 'blocked', 'reason': reason, 'status': status})


# ---------------------------------------------------------------- the response observer (status, headers, extra stops)

_tls = threading.local()   # .active (inside a scheduler call), .last = (url, code, hops, bytes, ms)
_orig_curl_h = wayback._curl_h
_CAPTCHA_FORM = re.compile(rb'(?is)<form[^>]*>.{0,4000}?captcha')


def _extra_challenge(url: str, code: int, hops, body: bytes) -> str | None:
    path = url.split('://', 1)[-1].partition('/')[2].split('?', 1)[0]
    if path == 'robots.txt' and code in (403, 429):
        return f'HTTP {code} on robots.txt'
    for c, hdrs in hops:
        if 300 <= c < 400 and c != 304 and not any(k == 'location' for k, _ in hdrs):
            return f'HTTP {c} redirect with no Location (Sucuri/Cloudproxy style)'
    srv = ' '.join(v.lower() for _, h in hops for k, v in h if k == 'server')
    low = body[:65536].lower()
    if 'ddos-guard' in srv and code in (403, 429, 503):
        return f'HTTP {code} from DDoS-Guard'
    if b'ddos-guard' in low and (code in (403, 429, 503) or len(body) < 32768):
        return f'HTTP {code} DDoS-Guard page'
    if len(body) < 32768 and _CAPTCHA_FORM.search(body[:32768]):
        return f'HTTP {code} page with a captcha form'
    return None


def _observed_curl_h(url: str, timeout: int, headers=()):
    t0 = time.time()
    code, body, hops = _orig_curl_h(url, timeout, headers)
    if getattr(_tls, 'active', False):
        _tls.last = (url, code, hops, len(body), int((time.time() - t0) * 1000))
        why = _extra_challenge(url, code, hops, body)
        if why:
            host = _host_of(url)
            wayback._stop_host(host, url, code, why)
            raise HostStopped(f'{host}: {why} at {url}; stopped for good (never retry, never work round it)')
    return code, body, hops


wayback._curl_h = _observed_curl_h


def last_status() -> int | None:
    """HTTP status of this thread's last network response through the scheduler (None if it was a cache hit)."""
    last = getattr(_tls, 'last', None)
    return last[1] if last else None


# ---------------------------------------------------------------- windows

def _zone(name: str):
    if name in ('UTC', 'Z'):
        return _dt.timezone.utc
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except Exception:
        m = re.fullmatch(r'UTC([+-])(\d{1,2})(?::?(\d\d))?', name)
        if not m:
            raise
        off = int(m.group(2)) * 60 + int(m.group(3) or 0)
        return _dt.timezone(_dt.timedelta(minutes=off if m.group(1) == '+' else -off))


def window_of(host: str) -> dict | None:
    """The allowed-hours spec for host: registry 'window' (people), then WINDOWS, then a robots Visit-time."""
    host = host.lower()
    e = registry_entry(host)
    if e.get('window') is not None:
        return e['window'] or None   # an empty {} in the registry means "no window"
    for k in (host, host.split(':', 1)[0], _base(host)):
        if k in WINDOWS:
            return WINDOWS[k]
    return e.get('robots_window')


def _hm(s: str) -> int:
    h, m = s.strip().split(':')
    return int(h) * 60 + int(m)


def window_next_open(spec: dict | None, now: float | None = None) -> float:
    """0 if spec allows a request at `now`, else the epoch second the next allowed period starts."""
    if not spec:
        return 0.0
    now = _now() if now is None else now
    tz = _zone(spec.get('tz', 'UTC'))
    local = _dt.datetime.fromtimestamp(now, tz)
    spans = []
    for d in range(-1, 9):
        day = (local + _dt.timedelta(days=d)).date()
        midnight = _dt.datetime(day.year, day.month, day.day, tzinfo=tz)
        if _DAYS[day.weekday()] in [x.lower()[:3] for x in spec.get('all_day', [])]:
            spans.append((midnight, midnight + _dt.timedelta(days=1)))
        for r in spec.get('hours', []):
            a, b = (_hm(x) for x in r.split('-'))
            start = midnight + _dt.timedelta(minutes=a)
            end = midnight + _dt.timedelta(minutes=b + (1440 if b <= a else 0))
            spans.append((start, end))
    best = None
    for s, e in spans:
        s, e = s.timestamp(), e.timestamp()
        if s <= now < e:
            return 0.0
        if s > now and (best is None or s < best):
            best = s
    return best if best is not None else now + 86400


# ---------------------------------------------------------------- robots + evidence

def _parse_robots_extra(text: str) -> dict:
    """Visit-time and Request-rate from the groups that bind us (wayback.ROBOTS_BINDING), plus an excerpt."""
    out, agents, in_rules, mine, lines = {'visit_time': None, 'request_rate': None}, [], False, False, []
    for raw in text.splitlines():
        line = raw.split('#', 1)[0].strip()
        if ':' not in line:
            continue
        k, v = (s.strip() for s in line.split(':', 1))
        k = k.lower()
        if k == 'user-agent':
            if in_rules:
                agents, in_rules = [], False
            agents.append(v.lower())
            mine = any(a == '*' or any(t in a for t in wayback.ROBOTS_BINDING) for a in agents)
            if mine:
                lines.append(line)
            continue
        in_rules = True
        if not mine:
            continue
        if len(lines) < 40:
            lines.append(line)
        if k == 'visit-time':
            m = re.fullmatch(r'(\d\d):?(\d\d)\s*-\s*(\d\d):?(\d\d)', v)
            if m:
                out['visit_time'] = f'{m.group(1)}:{m.group(2)}-{m.group(3)}:{m.group(4)}'
        elif k == 'request-rate':
            m = re.match(r'(\d+)\s*/\s*(\d+)\s*([smh]?)', v)
            if m and int(m.group(1)):
                secs = int(m.group(2)) * {'': 1, 's': 1, 'm': 60, 'h': 3600}[m.group(3)]
                out['request_rate'] = secs / int(m.group(1))
    out['excerpt'] = '\n'.join(lines)[:2000]
    return out


def _evidence_headers(hops) -> dict:
    keep = ('server', 'via', 'x-powered-by', 'x-cdn', 'x-cache', 'cf-ray', 'x-iinfo', 'x-sucuri-id', 'x-amz-cf-id',
            'x-akamai-transformed', 'retry-after', 'x-ratelimit-limit', 'ratelimit-policy')
    out = {}
    for _, hdrs in hops:
        for k, v in hdrs:
            if k in keep:
                out[k] = v[:200]
            elif k == 'set-cookie':
                out.setdefault('set-cookie names', [])
                name = v.split('=', 1)[0].strip()
                if name not in out['set-cookie names']:
                    out['set-cookie names'].append(name)
    return out


def _ensure_robots(host: str, scheme: str) -> None:
    """Read host's robots.txt once a week through host_get (paced, cached), keep an excerpt in the registry and tell
    host_get its Crawl-delay (or a slower Request-rate), so host_get does not read it a second time."""
    e = registry_entry(host)
    r = e.get('robots') or {}
    if r.get('at_epoch', 0) > _now() - wayback.ROBOTS_TTL:
        return
    url = f'{scheme}://{host}/robots.txt'
    _tls.last = None
    t0 = _now()
    body = wayback.host_get(url, SHARED_CACHE, tries=2, timeout=30, refresh=True)
    code = last_status()
    _feed_last(host, 'robots')
    text = (body or b'').decode('utf-8', 'replace') if code in (200, 304) else ''
    if '<html' in text[:500].lower():
        text = ''
    rules = wayback._parse_robots(text)
    extra = _parse_robots_extra(text)
    cd = max(rules['crawl_delay'] or 0, extra['request_rate'] or 0) or None
    wayback._note_robots(host, 200 if code == 304 else code, cd)
    if cd:   # the robots request itself was booked at the pace known before; the next request waits the full delay
        def push(st):
            st['next'] = max(st.get('next', 0.0), t0 + cd)
            return None, st
        wayback._host_locked(host, push)

    def upd(e):
        ok = code in (200, 304, 404, 410)   # a failed read is tried again in a day, as host_get does
        e['robots'] = {'status': code, 'at': _iso(),
                       'at_epoch': _now() if ok else _now() - wayback.ROBOTS_TTL + 86400,
                       'crawl_delay': rules['crawl_delay'],
                       'request_rate_interval': extra['request_rate'], 'visit_time': extra['visit_time'],
                       'excerpt': extra['excerpt']}
        if extra['visit_time']:
            e['robots_window'] = {'tz': 'UTC', 'hours': [extra['visit_time']], 'source': 'robots.txt Visit-time'}
        else:
            e.pop('robots_window', None)
        return e
    _reg_update(host, upd)


def _note_evidence(host: str) -> None:
    """After a live response: record headers, bot-management sign and the tier/pace/cap host_get now applies."""
    last = getattr(_tls, 'last', None)
    if not last:
        return
    _, code, hops, _, _ = last
    sig = wayback._bot_signal(hops)
    pol = wayback.host_policy(host)
    e = registry_entry(host)
    ev = e.get('evidence') or {}
    if (e.get('tier') == pol['tier'] and e.get('interval') == pol['interval'] and (not sig or ev.get('bot'))
            and ev.get('at_epoch', 0) > _now() - EVIDENCE_TTL):
        return

    def upd(e):
        e.pop('daily', None)   # no daily cap of ours since 2026-11-02 21:50 UTC
        e.update(tier=pol['tier'], interval=pol['interval'], tier_reason=pol['reason'])
        seed = INFLIGHT.get(_base(host))
        if seed and (e.get('max_inflight') is None or (e.get('max_inflight') or {}).get('from') == 'seed'):
            e['max_inflight'] = {**seed, 'from': 'seed'}
        spec = inflight_spec(host)
        lim = inflight_limit(host, f'https://{host}{(spec.get("paths") or ["/"])[0]}' if spec else None,
                             wayback.host_status(host))
        cfg = wayback._host_cfg(host)
        e['inflight_now'] = {'n': lim[0], 'reason': lim[1],
                             'host_tiers_concurrency': cfg.get('concurrency'), 'host_tiers_source': cfg.get('source')}
        old = e.get('evidence') or {}
        e['evidence'] = {'headers': _evidence_headers(hops), 'status': code, 'at': _iso(), 'at_epoch': _now(),
                         'bot': sig or old.get('bot'), 'bot_at': old.get('bot_at') or (_iso() if sig else None)}
        return e
    _reg_update(host, upd)


# ---------------------------------------------------------------- telemetry

def _feed(rec: dict) -> None:
    FEED_DIR.mkdir(parents=True, exist_ok=True)
    rec = {'at': _iso(), 'session': SESSION, 'pid': os.getpid(), **rec}
    line = (json.dumps(rec, ensure_ascii=False) + '\n').encode('utf-8')
    fd = os.open(FEED_DIR / (time.strftime('%Y-%m-%d', time.gmtime()) + '.jsonl'),
                 os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, 'O_BINARY', 0))
    try:
        os.write(fd, line)
    finally:
        os.close(fd)


def _feed_last(host: str, kind: str, caller: str | None = None, retry_after: float | None = None) -> None:
    last = getattr(_tls, 'last', None)
    if not last:
        return
    url, code, _, size, ms = last
    rec = {'host': host, 'url': url, 'event': kind, 'status': code, 'bytes': size, 'ms': ms, 'caller': caller,
           'cost': wayback.HOST_304_COST if code == 304 else 1}   # a 304 is a quarter of a full request (D6)
    if retry_after is not None:
        rec['retry_after'] = retry_after
    _feed(rec)


# ---------------------------------------------------------------- shared cache

def _sha_url(url: str) -> str:
    return hashlib.sha256(url.encode('utf-8')).hexdigest()


def _gone(url: str) -> Path:
    return SHARED_CACHE / '.gone' / _sha_url(url)


def cached(url: str) -> bytes | None:
    """The shared cache's body for url, or None."""
    p = SHARED_CACHE / _sha_url(url)
    try:
        return p.read_bytes()
    except OSError:
        return None


def _to_object(url: str) -> None:
    """Hard-link the URL's cache file to objects/<sha256(body)> so identical bodies are stored once."""
    p = SHARED_CACHE / _sha_url(url)
    try:
        data = p.read_bytes()
    except OSError:
        return
    obj = OBJECTS / hashlib.sha256(data).hexdigest()
    try:
        OBJECTS.mkdir(parents=True, exist_ok=True)
        if not obj.exists():
            os.link(p, obj)
        elif not os.path.samefile(p, obj):
            tmp = p.with_suffix('.link')
            os.link(obj, tmp)
            _replace(tmp, p)
    except OSError:
        pass


def _copy_to(cache: Path | None, url: str, body: bytes) -> None:
    """Also give the caller its own copy (host_get layout), so callers that read their cache folder keep working."""
    if cache is None:
        return
    hit = wayback._cached(cache, url)
    if hit is None or hit.exists():
        return
    src = SHARED_CACHE / _sha_url(url)
    tmp = hit.with_suffix('.part')
    try:
        os.link(src, tmp)
    except OSError:
        tmp.write_bytes(body)
    _replace(tmp, hit)
    meta = wayback._meta_file(SHARED_CACHE, url)
    if meta.exists():
        dst = wayback._meta_file(cache, url)
        dst.parent.mkdir(exist_ok=True)
        dst.write_bytes(meta.read_bytes())


# ---------------------------------------------------------------- per-host leases (requests in flight)

def _me() -> str:
    return f'{SESSION}:{os.getpid()}:{threading.get_ident()}'


def inflight_spec(host: str) -> dict | None:
    """The max_inflight entry for host ({'n', 'paths', 'evidence'}): the registry's, else INFLIGHT's, else None."""
    host = host.lower()
    e = registry_entry(host)
    if e.get('max_inflight') is not None and (e['max_inflight'] or {}).get('from') != 'seed':
        return e['max_inflight'] or None    # set by a person ({} = none)
    return INFLIGHT.get(_base(host))


def _path(url: str) -> str:
    return '/' + url.split('://', 1)[-1].partition('/')[2]


def inflight_limit(host: str, url: str | None, st: dict, now: float | None = None) -> tuple[int, str]:
    """(requests allowed in flight for url on host, why). host_get's own concurrency (host_tiers.json, already 1 after
    a 429/503/time-out or a bot-management sign), capped by the host's max_inflight entry, and 1 off its API paths."""
    now = _now() if now is None else now
    pol = wayback._policy(host, st, now)
    conc = int(pol.get('concurrency', 1) or 0)
    if conc <= 0:
        return 1, 'stopped'
    spec = inflight_spec(host)
    if spec:
        if url is not None and not any(_path(url).startswith(p) for p in spec.get('paths') or ['/']):
            return 1, 'one in flight (not an API path of this host)'
        conc = min(conc, max(1, int(spec.get('n') or 1)))
    conc = max(1, min(conc, MAX_INFLIGHT_CEILING))
    bot = st.get('bot') or (registry_entry(host).get('evidence') or {}).get('bot')
    if bot:
        return 1, f'one in flight (bot management seen: {bot})'
    if conc == 1:
        return 1, 'one in flight' + ('' if 'throttled' not in pol['reason'] else ' (throttled after 429/503/time-out)')
    return conc, f'{conc} in flight (documented public API: {(spec or {}).get("evidence") or pol["reason"]})'[:200]


def _live_leases(st: dict, now: float) -> dict:
    """Leases still running: {holder: until}. Includes the single 'sched_lease' of older scheduler versions."""
    live = {k: v for k, v in (st.get('sched_leases') or {}).items() if v > now}
    old = st.get('sched_lease')
    if old and old.get('until', 0) > now:
        live.setdefault(old.get('by', 'old'), old['until'])
    return live


def _claim(host: str, timeout: float, url: str | None = None) -> tuple[str, float]:
    """('go', 0) and a lease, or ('busy'|'wait', when) without one. At most inflight_limit() leases per host,
    machine-wide (one, for every host but a listed public API)."""
    me = _me()

    def f(st):
        now = _now()
        live = _live_leases(st, now)
        live.pop(me, None)
        limit, _ = inflight_limit(host, url, st, now)
        if len(live) >= limit:
            return ('busy', min(live.values())), st
        ready = max(st.get('next', 0.0), st.get('pause_until', 0.0))
        if ready > now + 0.05:
            return ('wait', ready), st
        live = {k: v for k, v in (st.get('sched_leases') or {}).items() if v > now}
        live[me] = now + timeout + LEASE_SLACK
        st['sched_leases'] = live
        return ('go', 0.0), st
    return wayback._host_locked(host, f)


def _release(host: str) -> None:
    me = _me()

    def f(st):
        (st.get('sched_leases') or {}).pop(me, None)
        if (st.get('sched_lease') or {}).get('by') == me:
            st.pop('sched_lease', None)
        return None, st
    wayback._host_locked(host, f)


def _today_cost(st: dict) -> float:
    return float(st.get('count', 0)) if st.get('day') == time.strftime('%Y-%m-%d', time.gmtime(_now())) else 0.0


def _next_utc_day(now: float) -> float:
    return (int(now // 86400) + 1) * 86400 + 5


def _pause_left(host: str) -> float:
    """Seconds until host_get's pause (Retry-After, or its back-off after a 429/503/time-out) ends."""
    return max(0.0, float(wayback.host_status(host).get('pause_until', 0.0)) - _now())


def _retry_after_seen() -> float | None:
    last = getattr(_tls, 'last', None)
    return wayback._retry_after(last[2], _now()) if last and last[1] >= 300 and last[1] != 304 else None


def _extend_lease(host: str, timeout: float) -> None:
    me = _me()

    def f(st):
        if me in (st.get('sched_leases') or {}):
            st['sched_leases'][me] = max(st.get('pause_until', 0.0), _now()) + timeout + LEASE_SLACK
        return None, st
    wayback._host_locked(host, f)


# ---------------------------------------------------------------- get

def check(host: str, url: str | None = None) -> float:
    """Raise HostStopped for host, else 0 if a request may start now or the epoch second it may (the site's pace,
    a Retry-After or 429/503 pause, another caller's request in flight, or the night window). No cap of our own."""
    host = host.lower()
    why = blocked(host)
    if why:
        raise HostStopped(f'{host}: stopped for good ({why.get("reason")}); never request it again, ask the publisher')
    st = wayback.host_status(host)
    t = window_next_open(window_of(host))
    ready = max(st.get('next', 0.0), st.get('pause_until', 0.0))
    live = _live_leases(st, _now())
    live.pop(_me(), None)
    if len(live) >= inflight_limit(host, url, st)[0]:
        ready = max(ready, min(min(live.values()), _now() + 2))
    return max(t, ready if ready > _now() else 0.0)


def get(url: str, cache: Path | str | None = None, tries: int = 5, timeout: int = 90, *, refresh: bool = False,
        wait: bool = True, caller: str | None = None) -> bytes | None:
    """Drop-in for wayback.host_get (same arguments and returns) under the scheduler. Shared cache first; then the
    host's block, Retry-After pause and window; then one request through host_get while holding the host's lease.
    wait=False raises NotNow(at) instead of sleeping for a window or a busy host."""
    cache = Path(cache) if cache else None
    host = _host_of(url)
    _tls.last = None
    if cache is not None and not refresh:
        hit = wayback._cached(cache, url)
        if hit.exists():
            return hit.read_bytes()
    if not refresh:
        body = cached(url)
        if body is not None:
            _copy_to(cache, url, body)
            return body
        if _gone(url).exists():
            return None
    if DRY:
        raise DryMiss(f'dry run: would fetch {url} (host {host}, next allowed in {max(0, check(host) - _now()):.0f} s, '
                      f'policy {wayback.host_policy(host)})')
    scheme = url.split('://', 1)[0] if '://' in url else 'https'
    while True:
        at = check(host, url)
        if at > _now():
            if not wait:
                raise NotNow(f'{host}: next allowed {_iso(at)}', at)
            _sleep(min(at - _now(), 60))
            continue
        iv = wayback._policy(host, wayback.host_status(host), _now())['interval']
        how, at = _claim(host, timeout + 30 + 2 * min(iv, 600), url)
        if how != 'go':
            if not wait and at - _now() > 2:
                raise NotNow(f'{host}: {how} until {_iso(at)}', at)
            _sleep(max(0.05, min(at - _now(), 5)))
            continue
        try:
            if not refresh and cached(url) is not None:   # another process fetched it while we waited
                body = cached(url)
                _copy_to(cache, url, body)
                return body
            _tls.active = True
            try:
                _ensure_robots(host, scheme)
                for attempt in range(max(1, tries)):
                    _tls.last = None
                    body = wayback.host_get(url, SHARED_CACHE, 1, timeout, refresh=refresh)
                    code = last_status()
                    _feed_last(host, 'get', caller, retry_after=_retry_after_seen())
                    if body is not None or code in (304, 403, 404, 410) or attempt + 1 >= tries:
                        break
                    if _pause_left(host) > RETRY_AFTER_MAX_WAIT:
                        break                       # paused for everyone; this caller gets None now
                    _extend_lease(host, timeout)    # host_get waits for the pause itself on the next attempt
            finally:
                _tls.active = False
            _note_evidence(host)
        except HostStopped as e:
            _feed_last(host, 'get', caller)
            _record_block(host, url, str(e)[:300], last_status())
            raise
        finally:
            _release(host)
        if body is not None:
            _to_object(url)
            _copy_to(cache, url, body)
        elif code in (404, 410):
            _gone(url).parent.mkdir(parents=True, exist_ok=True)
            _gone(url).write_text(str(code), encoding='utf-8')
        return body


# ---------------------------------------------------------------- fair queueing

def fetch_many(urls, cache: Path | str | None = None, workers: int | None = None, *, refresh: bool = False,
               caller: str | None = None, timeout: int = 90):
    """Fetch many URLs over many hosts, yielding (url, bytes | None | Exception) as each finishes.

    Per host one request at a time (here and across processes, by the lease); the workers take whichever host is
    ready next, round-robin, so hosts run side by side. A host that is stopped or capped fails its remaining URLs
    with that exception; a host outside its window waits for it. workers defaults to one per allowed in-flight
    request per host (up to 32): fetching is network-bound, and the leases keep each host to its in-flight limit."""
    import queue
    pending: dict[str, deque] = {}
    for u in urls:
        pending.setdefault(_host_of(u), deque()).append(u)
    def cap_of(h):
        spec = inflight_spec(h)
        return max(1, min(int((spec or {}).get('n') or 1), MAX_INFLIGHT_CEILING))
    workers = max(1, int(workers) if workers else min(sum(cap_of(h) for h in pending), 32))
    order = deque(pending)                   # round-robin order of hosts
    busy: dict[str, int] = {}
    until: dict[str, float] = {}
    lock = threading.Lock()
    out: queue.Queue = queue.Queue()
    left = [sum(len(q) for q in pending.values())]

    def pick():
        with lock:
            now, best = _now(), None
            for h in list(order):
                if not pending.get(h):
                    continue
                if busy.get(h, 0) and busy[h] >= inflight_limit(h, pending[h][0], wayback.host_status(h))[0]:
                    continue
                t = until.get(h, 0.0)
                if t <= now:
                    order.remove(h)
                    order.append(h)
                    busy[h] = busy.get(h, 0) + 1
                    return h, pending[h].popleft(), 0.0
                best = t if best is None else min(best, t)
            return None, None, (best - now if best is not None else 0.2)

    def fail_host(h, exc):
        with lock:
            rest = list(pending.get(h) or [])
            pending[h] = deque()
        for u in rest:
            out.put((u, exc))

    def worker():
        while True:
            with lock:
                if left[0] <= 0:
                    return
            h, u, nap = pick()
            if h is None:
                if not any(pending.values()) and not any(busy.values()):
                    return
                _sleep(max(0.02, min(nap, 1.0)))
                continue
            try:
                try:
                    res = get(u, cache, timeout=timeout, refresh=refresh, wait=False, caller=caller)
                except NotNow as e:
                    with lock:
                        pending[h].appendleft(u)
                        until[h] = e.at
                    continue
                except (HostStopped, HostDailyCap) as e:
                    out.put((u, e))
                    fail_host(h, e)
                    continue
                except Exception as e:  # noqa: BLE001
                    res = e
                out.put((u, res))
            finally:
                with lock:
                    busy[h] -= 1

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(workers)]
    for t in threads:
        t.start()
    while left[0] > 0:
        try:
            item = out.get(timeout=1)
        except queue.Empty:
            if not any(t.is_alive() for t in threads) and out.empty():
                break
            continue
        with lock:
            left[0] -= 1
        yield item
    for t in threads:
        t.join(timeout=1)


# ---------------------------------------------------------------- adapter for br_city_get.Host fetchers

def adopt(H, caller: str | None = None, tries: int = 1):
    """Route a br_city_get.Host's network GETs through the scheduler, keeping its cache, request log, STOP file and
    error rules: a non-200 answer other than 404/410 (or HostStopped) writes its STOP file and raises its Stop.
    POSTs and requests with extra headers keep the Host's own path. Waits (pace, window) sleep. (HostDailyCap is
    no longer raised by host_get, which has no daily cap since 2026-11-02; it is still slept out if it ever is.)"""
    import importlib
    Stop = importlib.import_module(type(H).__module__).Stop
    orig = H.get
    caller = caller or type(H).__module__

    def log(url, code, size):
        with open(H.dir / 'requests.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps({'url': url, 'post': False, 'status': str(code), 'bytes': size,
                                'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'err': '',
                                'via': 'fetch_scheduler'}) + '\n')

    def get_(url, data=None, cached_only=False, headers=()):
        p = H.path(url, data)
        if p.exists():
            return p.read_bytes()
        if Path(str(p) + '.404').exists() or cached_only:
            return None
        if data is not None or headers:
            return orig(url, data, cached_only, headers)
        if (H.dir / 'STOP').exists():
            raise Stop(f'{H.name} stopped: {(H.dir / "STOP").read_text()[:200]}')
        while True:
            try:
                body = get(url, tries=tries, timeout=H.timeout, caller=caller)
                break
            except HostDailyCap as e:
                nxt = _next_utc_day(_now())
                print(f'{H.name}: {e}; pausing until {_iso(nxt)}', flush=True)
                while _now() < nxt:
                    _sleep(min(300, max(1, nxt - _now())))
            except HostStopped as e:
                (H.dir / 'STOP').write_text(f'fetch_scheduler: {e} at {time.ctime()}', encoding='utf-8')
                raise Stop(str(e)) from e
        code = last_status()
        if code is not None:       # a live request (not the shared cache)
            H.last = time.time()
            log(url, code, len(body or b''))
        if body is None:
            if code in (None, 404, 410):
                Path(str(p) + '.404').touch()
                return None
            (H.dir / 'STOP').write_text(f'{code} on {url} at {time.ctime()} (fetch_scheduler)', encoding='utf-8')
            raise Stop(f'{H.name}: HTTP {code} on {url}')
        tmp = Path(str(p) + '.tmp')
        tmp.write_bytes(body)
        _replace(tmp, p)
        return body

    H.get = get_
    H.scheduler = True
    return H


# ---------------------------------------------------------------- status

def known_hosts() -> list[str]:
    hosts = set(_reg_read().get('hosts', {}))
    if wayback.HOST_DIR.exists():
        for p in wayback.HOST_DIR.glob('*.json'):
            hosts.add(p.stem.replace('_', ':') if re.search(r'_\d+$', p.stem) else p.stem)
    return sorted(hosts)


def host_report(host: str) -> dict:
    host = host.lower()
    st = wayback.host_status(host)
    now = _now()
    pol = wayback._policy(host, st, now)
    e = registry_entry(host)
    why = blocked(host)
    win = window_of(host)
    today = _today_cost(st)
    try:
        at = check(host)
        status = 'ready' if at <= now else ('closed' if window_next_open(win, now) > now else 'pacing')
    except HostStopped:
        at, status = None, 'blocked'
    live = _live_leases(st, now)
    spec = inflight_spec(host)
    api_url = f'https://{host}{(spec.get("paths") or ["/"])[0]}' if spec else None
    lim, lim_why = inflight_limit(host, api_url, st, now)
    return {'host': host, 'status': status, 'tier': 'stop' if why else pol['tier'],
            'interval_s': None if why else round(pol['interval'], 3),
            'requests_today': today, 'in_flight': len(live), 'max_inflight': lim, 'max_inflight_reason': lim_why,
            'paused_until': _iso(st['pause_until']) if st.get('pause_until', 0) > now else None,
            'not_modified_total': st.get('not_modified', 0),
            'next_allowed': _iso(at) if at else (None if status == 'blocked' else _iso(now)),
            'window': win, 'blocked': why, 'reason': pol['reason'],
            'bot': (e.get('evidence') or {}).get('bot') or st.get('bot'),
            'robots_status': (e.get('robots') or {}).get('status', st.get('robots_status')),
            'crawl_delay': st.get('crawl_delay'), 'at': _iso(now), 'session': SESSION}


def status(hosts: list[str] | None = None) -> list[dict]:
    return [host_report(h) for h in (hosts or known_hosts())]


def _main(argv: list[str]) -> int:
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    if argv[0] == 'status':
        fmt = 'table'
        rest = []
        for a in argv[1:]:
            if a in ('--json', '--jsonl'):
                fmt = a[2:]
            else:
                rest.append(a)
        rows = status(rest or None)
        if fmt == 'json':
            print(json.dumps(rows, indent=1, ensure_ascii=False))
        elif fmt == 'jsonl':
            for r in rows:
                print(json.dumps(r, ensure_ascii=False))
        else:
            print(f'{"host":44} {"status":8} {"tier":4} {"every":>7} {"today":>8}  next allowed')
            for r in rows:
                iv = '-' if r['interval_s'] is None else f'{r["interval_s"]:g}s'
                print(f'{r["host"][:44]:44} {r["status"]:8} {r["tier"]:4} {iv:>7} {r["requests_today"]:>8g}  '
                      f'{r["next_allowed"] or "never"}')
            print(f'feed: {FEED_DIR}  registry: {REGISTRY}  cache: {SHARED_CACHE}')
        return 0
    if argv[0] == 'blocks':
        for r in status():
            if r['blocked']:
                print(r['host'], '-', r['blocked'].get('reason'))
        return 0
    print(f'unknown command {argv[0]!r}; try: status [--json|--jsonl] [host ...], blocks')
    return 2


if __name__ == '__main__':
    sys.exit(_main(sys.argv[1:]))
