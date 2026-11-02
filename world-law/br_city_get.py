"""Private (never published). Polite fetcher for the Brazilian municipal builds (gitlaw-scraper-dell, 2026-10-31).

    from br_city_get import Host
    h = Host(cache_dir, 'legislacao.prefeitura.sp.gov.br', delay=3.0)
    b = h.get(url)            # bytes, or None on 404; raises Stop on 403/429/5xx/challenge/timeout

One request at a time per Host, at least `delay` seconds apart (raise it to the site's Crawl-delay), TLS always
verified (curl/Schannel), 60 s timeout = fail. Cache: <cache_dir>/raw/<sha256(url)> (+ .404 marker). Every request is
appended to <cache_dir>/requests.jsonl. A STOP file in cache_dir stops the host for good.

daily_cap=N (2026-11-01 rule: hosts with no stated Crawl-delay get at most 1 request per 3 s and about 5,000 a day):
once N requests to this host have been made in the current UTC day (counted from requests.jsonl), get() sleeps until
the next UTC day before making the next request. Cached answers are not counted and never wait.
"""
import hashlib, json, os, re, subprocess, time
from pathlib import Path

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'
CHALLENGE = re.compile(rb'(?i)just a moment|cf-chl-|cf_chl_|attention required|incapsula|_incap_|awswaf|'
                       rb'captcha-delivery|access denied|request unsuccessful|ddos-guard|challenge-platform')


class Stop(RuntimeError):
    pass


class Host:
    def __init__(self, cache_dir, name, delay=3.0, timeout=60, daily_cap=None):
        self.dir = Path(cache_dir)
        (self.dir / 'raw').mkdir(parents=True, exist_ok=True)
        self.name, self.delay, self.timeout, self.last = name, delay, timeout, 0.0
        self.daily_cap, self.day, self.today_n = daily_cap, None, 0

    def _count_day(self):
        """Requests already made to this host in the current UTC day (from requests.jsonl)."""
        day = time.strftime('%Y-%m-%d', time.gmtime())
        if day != self.day:
            n = 0
            log = self.dir / 'requests.jsonl'
            if log.exists():
                with open(log, encoding='utf-8') as f:
                    n = sum(1 for l in f if f'"at": "{day}T' in l)
            self.day, self.today_n = day, n
        return self.today_n

    def _daily_wait(self):
        while self.daily_cap and self._count_day() >= self.daily_cap:
            now = time.time()
            nxt = (int(now // 86400) + 1) * 86400 + 5
            print(f'{self.name}: {self.today_n} requests on {self.day} (cap {self.daily_cap}); pausing until '
                  f'{time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(nxt))}', flush=True)
            while time.time() < nxt:  # short sleeps, so a machine sleep cannot overshoot by much
                time.sleep(min(300, max(1, nxt - time.time())))

    def path(self, url, data=None):
        key = url if data is None else url + '\0POST\0' + data
        return self.dir / 'raw' / hashlib.sha256(key.encode()).hexdigest()

    def get(self, url, data=None, cached_only=False, headers=()):
        p = self.path(url, data)
        if p.exists():
            return p.read_bytes()
        if Path(str(p) + '.404').exists() or cached_only:
            return None
        if (self.dir / 'STOP').exists():
            raise Stop(f'{self.name} stopped: {(self.dir / "STOP").read_text()[:200]}')
        self._daily_wait()
        w = self.delay - (time.time() - self.last)
        if w > 0:
            time.sleep(w)
        self.last = time.time()
        tmp = str(p) + '.tmp'
        cmd = ['curl', '-sS', '-L', '--compressed', '-m', str(self.timeout), '-A', UA, '-o', tmp, '-w', '%{http_code}']
        for h in headers:
            cmd += ['-H', h]
        if data is not None:
            cmd += ['--data-raw', data]
        r = subprocess.run(cmd + [url], capture_output=True)
        if self.daily_cap:
            self._count_day()
            self.today_n += 1
        code = r.stdout.decode().strip()
        size = os.path.getsize(tmp) if os.path.exists(tmp) else 0
        with open(self.dir / 'requests.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps({'url': url, 'post': data is not None, 'status': code, 'bytes': size,
                                'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                                'err': r.stderr.decode('utf-8', 'replace')[:200]}) + '\n')
        body = Path(tmp).read_bytes() if os.path.exists(tmp) else b''
        if code in ('404', '410'):
            Path(str(p) + '.404').touch()
            os.path.exists(tmp) and os.remove(tmp)
            return None
        if code != '200' or r.returncode:
            (self.dir / 'STOP').write_text(f'{code} rc={r.returncode} on {url} at {time.ctime()}', encoding='utf-8')
            raise Stop(f'{self.name}: HTTP {code} rc={r.returncode} {r.stderr.decode("utf-8", "replace")[:200]}')
        if CHALLENGE.search(body[:20000]) and len(body) < 60000:
            (self.dir / 'STOP').write_text(f'challenge marker on {url} at {time.ctime()}', encoding='utf-8')
            raise Stop(f'{self.name}: challenge page on {url}')
        os.replace(tmp, p)
        return body
