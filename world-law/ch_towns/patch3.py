"""Coordinator rule 2026-11-01 (after three late WAF blocks): >= 3 s between requests (or the Crawl-delay if longer),
<= ~5,000 requests per host per day, stop for good on any challenge. All LexWork hosts sit in one provider block
(93.187.192.0/22: <town>.tlex.ch, gesetzessammlung.chur.ch, reglemente.stadt-solothurn.ch and the cantons' hosts),
so they are counted as ONE host."""
from pathlib import Path
p = Path(__file__).resolve().parent.parent / 'ch_cities.py'
s = p.read_text(encoding='utf-8')

anchor = """def host(city: str) -> C.Host:"""
guard = '''# ---------------------------------------------------------------- one LexWork backend: spacing, daily cap, stop
LEXWORK_NET = '93.187.192.0/22'          # every LexWork host seen resolves here: one backend for the cap
DAILY_CAP = 4800                         # coordinator: about 5,000 per host per day; margin for gate probes
GUARD = Path(__file__).resolve().parent / 'ch_towns'
BLOCKED = GUARD / 'LEXWORK-BLOCKED'      # written on any challenge: no LexWork fetch ever again from this code
LAST = GUARD / 'lexwork-last.txt'        # end time of the last request, shared by consecutive fetch processes


def _in_block(hostname: str) -> bool:
    import ipaddress
    import socket
    try:
        return ipaddress.ip_address(socket.gethostbyname(hostname)) in ipaddress.ip_network(LEXWORK_NET)
    except OSError:
        return True   # unknown: count it


def lexwork_today() -> int:
    """Requests sent today (UTC) to the LexWork block, from every request log on this machine."""
    import datetime as _dt
    import glob
    day = _dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%d')
    seen: dict[str, bool] = {}
    n = 0
    logs = set(glob.glob(str(C.ROOT / 'switzerland-*' / '.cache' / 'requests.jsonl')))
    logs.add(str(GUARD / 'probe-cache' / 'requests.jsonl'))
    for f in logs:
        try:
            lines = open(f, encoding='utf-8').read().splitlines()
        except OSError:
            continue
        for line in lines:
            if f'"at": "{day}' not in line:
                continue
            try:
                h = urllib.parse.urlsplit(json.loads(line)['url']).netloc
            except (ValueError, KeyError):
                continue
            if h not in seen:
                seen[h] = _in_block(h)
            n += seen[h]
    return n


_orig_get = C.Host.get


def _guarded_get(self, url):
    if self.host not in _CITY_HOSTS:
        return _orig_get(self, url)
    c = self.cached(url)
    if c is not False:
        return c
    import time as _t
    if BLOCKED.exists():
        raise RuntimeError(f'LexWork blocked earlier ({BLOCKED.read_text(encoding="utf-8").strip()}): no request')
    if not hasattr(self, '_today'):
        self._today = lexwork_today()
    if self._today >= DAILY_CAP:
        raise RuntimeError(f'daily cap: {self._today} LexWork requests today (cap {DAILY_CAP}); resume tomorrow')
    self.pause = max(self.pause, MIN_PAUSE)
    try:
        last = float(LAST.read_text())
    except (OSError, ValueError):
        last = 0.0
    self.last = max(self.last, last)
    wait = self.last + self.pause - _t.time()
    if wait > 0:
        _t.sleep(wait)
    t0 = _t.time()
    r = C.subprocess.run(['curl', '-s', '-m', '60', '--compressed', '-A', C.UA, '-w', '\\n%{http_code}', url],
                         capture_output=True)
    self.last = _t.time()
    LAST.write_text(str(self.last))
    self.count += 1
    self._today += 1
    body, _, code = r.stdout.rpartition(b'\\n')
    code = code.decode().strip()
    with open(self.cache / 'requests.jsonl', 'a', encoding='utf-8') as f:
        f.write(json.dumps({'at': C.dt.datetime.now(C.dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'url': url,
                            'status': code, 'bytes': len(body), 'secs': round(self.last - t0, 2),
                            'curl_rc': r.returncode}) + '\\n')
    if code == '404':
        self.path(url).write_bytes(b'null')
        return None
    if code == '200':
        try:
            d = json.loads(body)
        except ValueError:
            d = None
        if d is not None:
            tmp = self.path(url).with_suffix('.tmp')
            tmp.write_bytes(body)
            C.os.replace(tmp, self.path(url))
            return d
        why = f'{self.host}: HTTP 200 but not JSON (challenge page?) at {url}'
    elif r.returncode:
        why = f'{self.host}: curl error {r.returncode} (timeout or connection) at {url}'
    else:
        why = f'{self.host}: HTTP {code} at {url}'
    # Any challenge, 403, 429, 5xx, timeout or odd answer: stop for good, and stop the chain too. A person decides.
    stamp = C.dt.datetime.now(C.dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    BLOCKED.write_text(f'{stamp} {why}\\n', encoding='utf-8')
    (GUARD / 'STOP').write_text(f'{stamp} {why}\\n', encoding='utf-8')
    raise RuntimeError('stopped for good: ' + why)


C.Host.get = _guarded_get


'''
assert s.count(anchor) == 1
s = s.replace(anchor, guard + anchor)
p.write_bytes(s.encode('utf-8'))
print('patched')
