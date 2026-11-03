"""Tests for wayback.host_get and wayback.fetch after the 2026-11-02 21:50 UTC decision (no pacing caps of our own).

What they show: one request in flight per host and the next as soon as the previous one answers; no daily cap;
a publisher-stated rate (tier A) and a robots Crawl-delay still honoured (the slower wins); Retry-After honoured;
halving with a pause on 429/503 and recovery; up to "concurrency" slots for configured hosts, correct across
processes, dropping to 1 after a 429 and for good on a bot-management sign; the permanent stop on a challenge;
D6 conditional requests and D7 robots groups.

Everything runs against a stub HTTP server on 127.0.0.1 (or a stubbed _curl_h); no real network requests. State,
stop and config paths point at a temporary folder; most tests inject the clock, so pacing takes no wall time.

    python -m unittest scripts/gitlaw_common/test_host_get.py -v
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import wayback  # noqa: E402

_active = [0, 0]   # [requests being served now, the most at once]
_active_lock = threading.Lock()


class Stub(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'   # keep-alive, so connection reuse can be counted
    routes: dict = {}
    seen: list = []
    connections = [0]

    def log_message(self, *a):
        pass

    def setup(self):
        with _active_lock:
            Stub.connections[0] += 1
        super().setup()

    def do_GET(self):
        with _active_lock:
            _active[0] += 1
            _active[1] = max(_active[1], _active[0])
        try:
            Stub.seen.append((self.path, dict(self.headers)))
            r = Stub.routes.get(self.path)
            if callable(r):
                r = r(self)
            if r is None:
                r = (404, {}, b'not found')
            code, headers, body = r
            self.send_response(code)
            for k, v in headers.items():
                for one in (v if isinstance(v, list) else [v]):
                    self.send_header(k, one)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        finally:
            with _active_lock:
                _active[0] -= 1


def etag_route(handler):
    if handler.headers.get('If-None-Match') == '"v1"':
        return 304, {'ETag': '"v1"'}, b''
    return 200, {'ETag': '"v1"', 'Last-Modified': 'Mon, 02 Nov 2026 10:00:00 GMT'}, b'versioned body'


def slow_route(handler):
    time.sleep(0.25)
    return 200, {}, b'slow'


# A worker for the cross-process slot test: _curl_h is replaced by a 0.3 s sleep that logs its interval, so the test
# needs no network and no curl processes. argv: here, host, n_threads, requests_per_thread, out_file
_SLOT_WORKER = r'''
import json, sys, threading, time
sys.path.insert(0, sys.argv[1])
import wayback
host, nt, nr, out = sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
spans, lock = [], threading.Lock()
def fake(url, timeout, headers=()):
    t0 = time.time(); time.sleep(0.3); t1 = time.time()
    with lock:
        spans.append((t0, t1))
    return 200, b'ok', [(200, [])]
wayback._curl_h = fake
def run():
    for i in range(nr):
        wayback._host_fetch(f'http://{host}/x', host, None, 1, 30)
ts = [threading.Thread(target=run) for _ in range(nt)]
[t.start() for t in ts]; [t.join() for t in ts]
open(out, 'w').write(json.dumps(spans))
'''


def drop_pools() -> None:
    with wayback._POOL_LOCK:
        for conns in wayback._POOLS.values():
            for c in conns:
                c.close()
        wayback._POOLS.clear()
    wayback._CURL_HOSTS.clear()


def max_overlap(spans) -> int:
    ev = sorted([(a, 1) for a, _ in spans] + [(b, -1) for _, b in spans], key=lambda e: (e[0], e[1]))
    cur = best = 0
    for _, d in ev:
        cur += d
        best = max(best, cur)
    return best


class HostGetCases:
    transport = 'auto'

    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Stub)
        cls.server.handle_error = lambda request, client_address: None   # aborted on purpose by time-out tests
        cls.port = cls.server.server_address[1]
        cls.host = f'127.0.0.1:{cls.port}'
        cls.base = f'http://{cls.host}'
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.t = Path(self.tmp.name)
        self.saved = {k: getattr(wayback, k) for k in ('HOST_DIR', 'HOST_STOP_DIR', 'HOST_TIERS', '_now', '_sleep',
                                                       '_curl_h', '_curl_proc', '_py_get', 'STATE', 'LOCK',
                                                       'TRANSPORT')}
        wayback.TRANSPORT = self.transport
        drop_pools()
        wayback.HOST_DIR, wayback.HOST_STOP_DIR, wayback.HOST_TIERS = t / 'rate', t / 'stops', t / 'host_tiers.json'
        wayback.STATE, wayback.LOCK = t / 'archive.json', t / 'archive.lock'
        wayback._cfg_cache['key'] = None
        self.fake_clock()
        Stub.seen.clear()
        _active[:] = [0, 0]
        Stub.connections[0] = 0
        Stub.routes = {'/robots.txt': (200, {}, b'User-agent: *\nDisallow: /private/\n'),
                       '/page/1': (200, {}, b'one'), '/page/2': (200, {}, b'two'), '/page/3': (200, {}, b'three'),
                       '/etag': etag_route, '/slow': slow_route}
        self.cache = t / 'cache'

    def tearDown(self):
        for k, v in self.saved.items():
            setattr(wayback, k, v)
        wayback._cfg_cache['key'] = None
        drop_pools()
        self.tmp.cleanup()

    def fake_clock(self):
        self.clock = [time.time()]
        self.sleeps = []

        def sleep(s):
            self.sleeps.append(round(s, 6))
            self.clock[0] += s
        wayback._now, wayback._sleep = (lambda: self.clock[0]), sleep

    def config(self, hosts: dict):
        wayback.HOST_TIERS.write_text(json.dumps({'hosts': hosts}), encoding='utf-8')
        wayback._cfg_cache['key'] = None

    def paths(self):
        return [p for p, _ in Stub.seen]

    def state(self, **kw):
        def f(st):
            st.update(kw)
            return None, st
        wayback._host_locked(self.host, f)

    # ---- one in flight, back to back, no cap

    def test_back_to_back_with_no_wait(self):
        for i in (1, 2, 3):
            self.assertEqual(wayback.host_get(f'{self.base}/page/{i}'), [b'one', b'two', b'three'][i - 1])
        self.assertEqual(self.paths(), ['/robots.txt', '/page/1', '/page/2', '/page/3'])
        self.assertEqual(self.sleeps, [])                       # no artificial wait between answers
        pol = wayback.host_policy(self.host, now=self.clock[0])
        self.assertEqual((pol['tier'], pol['interval'], pol['concurrency'], pol['daily']), ('B', 0.0, 1, float('inf')))
        self.assertEqual(wayback.host_status(self.host)['count'], 4)   # the counter is kept, for reporting

    def test_one_request_in_flight_per_host(self):
        wayback._now, wayback._sleep = time.time, time.sleep
        wayback.host_get(f'{self.base}/page/1')                 # robots.txt read first
        _active[:] = [0, 0]
        ts = [threading.Thread(target=wayback.host_get, args=(f'{self.base}/slow',)) for _ in range(4)]
        t0 = time.time()
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(self.paths().count('/slow'), 4)
        self.assertEqual(_active[1], 1)                         # never two at once
        self.assertGreaterEqual(time.time() - t0, 4 * 0.25)
        self.assertEqual(wayback.host_status(self.host).get('inflight'), {})

    def test_no_daily_cap(self):
        wayback.host_get(f'{self.base}/page/1')
        self.state(count=50000)                                  # far past the old 5,000 and 20,000
        self.assertEqual(wayback.host_get(f'{self.base}/page/2'), b'two')
        self.assertEqual(wayback.host_status(self.host)['count'], 50001)
        self.config({self.host: {'tier': 'A', 'interval': 1, 'daily': 3}})   # "daily" is inert
        self.assertEqual(wayback.host_get(f'{self.base}/page/3'), b'three')
        self.assertEqual(wayback.host_policy(self.host)['daily'], float('inf'))
        for name in ('ARCHIVE_DAILY', 'HOST_B_RAMP', 'HOST_QUALIFY'):
            self.assertFalse(hasattr(wayback, name), name)

    def test_bot_management_sign_is_tier_c_without_a_floor(self):
        Stub.routes['/page/1'] = (200, {'CF-RAY': '8abc-LHR', 'Set-Cookie': '__cf_bm=xyz; path=/'}, b'one')
        for i in (1, 2, 3):
            wayback.host_get(f'{self.base}/page/{i}')
        st = wayback.host_status(self.host)
        self.assertTrue(st['bot'].startswith('cloudflare'))
        pol = wayback.host_policy(self.host, now=self.clock[0])
        self.assertEqual((pol['tier'], pol['interval'], pol['concurrency']), ('C', 0.0, 1))
        self.assertEqual(self.sleeps, [])
        self.assertIsNone(wayback._bot_signal([(200, [('cf-ray', 'x'), ('server', 'cloudflare')])]))
        for hdrs, who in (([('set-cookie', '_abck=1')], 'akamai'), ([('set-cookie', 'incap_ses_1=2')], 'imperva'),
                          ([('set-cookie', 'datadome=1')], 'datadome'), ([('set-cookie', '_pxhd=1')], 'perimeterx'),
                          ([('set-cookie', 'aws-waf-token=1')], 'aws-waf'), ([('server', 'Sucuri/Cloudproxy')], 'sucuri')):
            self.assertTrue(wayback._bot_signal([(200, hdrs)]).startswith(who), who)

    # ---- the site's own rules still apply

    def test_tier_a_stated_rate(self):
        self.config({self.host: {'tier': 'A', 'interval': 7, 'source': 'API docs'}})
        for i in (1, 2):
            wayback.host_get(f'{self.base}/page/{i}')
        self.assertEqual(self.sleeps, [7.0, 7.0])                # robots.txt, then each page 7 s after the last
        self.config({self.host: {'tier': 'A', 'rate': 2}})
        self.assertEqual(wayback.host_policy(self.host, now=self.clock[0])['interval'], 0.5)

    def test_robots_crawl_delay_and_the_slower_wins(self):
        Stub.routes['/robots.txt'] = (200, {}, b'User-agent: GPTBot\nCrawl-delay: 60\n\nUser-agent: *\nCrawl-delay: 6\n')
        for i in (1, 2):
            wayback.host_get(f'{self.base}/page/{i}')
        self.assertEqual(wayback.host_status(self.host)['crawl_delay'], 6.0)
        self.assertEqual(self.sleeps, [6.0])   # page 1 right after robots.txt (booked before it was read), page 2 6 s on
        wayback.host_get(f'{self.base}/page/3')
        self.assertEqual(self.paths().count('/robots.txt'), 1)  # read once per ROBOTS_TTL
        self.config({self.host: {'tier': 'A', 'interval': 4}})  # Crawl-delay 6 is slower than the stated 4 s
        self.assertEqual(wayback.host_policy(self.host, now=self.clock[0])['interval'], 6.0)
        self.config({self.host: {'tier': 'A', 'interval': 9}})  # the stated 9 s is slower than Crawl-delay 6
        self.assertEqual(wayback.host_policy(self.host, now=self.clock[0])['interval'], 9.0)
        self.config({'*.example.org': {'tier': 'C'}, 'example.net': {'tier': 'A', 'interval': 4}})
        self.assertEqual(wayback._host_cfg('a.b.example.org')['tier'], 'C')
        self.assertEqual(wayback._host_cfg('www.example.net')['interval'], 4)

    def test_retry_after_is_honoured(self):
        wayback.host_get(f'{self.base}/page/1')
        Stub.routes['/busy'] = (429, {'Retry-After': '120'}, b'slow down')
        self.assertIsNone(wayback.host_get(f'{self.base}/busy', tries=1))
        st = wayback.host_status(self.host)
        self.assertAlmostEqual(st['pause_until'], self.clock[0] + 120, places=3)   # longer than the 30 s back-off
        wayback.host_get(f'{self.base}/page/2')
        self.assertAlmostEqual(self.sleeps[-1], 120, places=3)
        # an HTTP date works too, and a 503 with a short Retry-After still gets the 30 s back-off
        date = time.strftime('%a, %d %b %Y %H:%M:%S GMT', time.gmtime(self.clock[0] + 600))
        self.assertAlmostEqual(wayback._retry_after([(503, [('retry-after', date)])], self.clock[0]), 600, delta=1)
        Stub.routes['/unavail'] = (503, {'Retry-After': '5'}, b'')
        wayback.host_get(f'{self.base}/unavail', tries=1)
        self.assertAlmostEqual(wayback.host_status(self.host)['pause_until'], self.clock[0] + 30, places=3)

    def test_429_halves_the_rate_pauses_and_recovers(self):
        wayback.host_get(f'{self.base}/page/1')
        Stub.routes['/busy'] = (429, {}, b'')
        wayback.host_get(f'{self.base}/busy', tries=1)
        st = wayback.host_status(self.host)
        first = st['throttle_iv']
        cap = 1 / wayback.HOST_MIN                               # the slowest a throttle goes (base interval 0)
        self.assertAlmostEqual(first, min(2 * max(st['lat'], wayback.HOST_THROTTLE_FLOOR), cap), places=6)
        self.assertAlmostEqual(st['pause_until'], self.clock[0] + wayback.HOST_BACKOFF, places=3)
        self.assertEqual(st['throttled'], 1)
        wayback.host_get(f'{self.base}/busy', tries=1)         # waits the pause, then halves again
        self.assertGreaterEqual(self.sleeps[-1], wayback.HOST_BACKOFF - 1e-6)
        st = wayback.host_status(self.host)
        self.assertAlmostEqual(st['throttle_iv'], min(2 * max(first, st['lat']), cap), places=6)
        # each clean answer gives HOST_STEP requests a second back; at the floor the throttle is gone
        iv = st['throttle_iv']
        wayback.host_get(f'{self.base}/page/2')
        self.assertAlmostEqual(wayback.host_status(self.host)['throttle_iv'], 1 / (1 / iv + wayback.HOST_STEP), places=6)
        self.state(throttle_iv=wayback.HOST_THROTTLE_FLOOR + 0.005)
        wayback.host_get(f'{self.base}/page/3')
        self.assertNotIn('throttle_iv', wayback.host_status(self.host))
        self.assertEqual(wayback.host_policy(self.host, now=self.clock[0])['interval'], 0.0)

    # ---- more than one in flight for configured APIs

    def test_slots_hold_across_processes(self):
        wayback._now, wayback._sleep = time.time, time.sleep
        host = 'api.example.test'
        self.config({host: {'concurrency': 3, 'source': 'test'}})
        self.assertEqual(wayback._policy(host, {}, time.time())['concurrency'], 3)
        wayback._host_locked(host, lambda st: (None, {**st, 'robots_at': time.time() + 1e6}))  # no robots read
        env = {**os.environ, 'GITLAW_HOST_RATE_DIR': str(wayback.HOST_DIR),
               'GITLAW_HOST_STOP_DIR': str(wayback.HOST_STOP_DIR), 'GITLAW_HOST_TIERS': str(wayback.HOST_TIERS)}
        out = self.t / 'child.json'
        # two processes (this one and a child), three threads each, competing for 3 slots
        child = subprocess.Popen([sys.executable, '-c', _SLOT_WORKER, str(HERE), host, '3', '4', str(out)], env=env)
        spans, lock = [], threading.Lock()

        def fake(url, timeout, headers=()):
            t0 = time.time()
            time.sleep(0.3)
            with lock:
                spans.append((t0, time.time()))
            return 200, b'ok', [(200, [])]
        wayback._curl_h = fake

        def run():
            for _ in range(4):
                wayback._host_fetch(f'http://{host}/x', host, None, 1, 30)
        ts = [threading.Thread(target=run) for _ in range(3)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(child.wait(timeout=120), 0)
        spans += [tuple(s) for s in json.loads(out.read_text())]
        self.assertEqual(len(spans), 24)
        self.assertLessEqual(max_overlap(spans), 3)              # never more than the slots
        self.assertGreaterEqual(max_overlap(spans), 2)           # and they are really used in parallel
        self.assertEqual(wayback.host_status(host).get('inflight'), {})
        # an unconfigured host keeps one slot under the same load
        spans.clear()
        host = 'plain.example.test'
        wayback._host_locked(host, lambda st: (None, {**st, 'robots_at': time.time() + 1e6}))
        ts = [threading.Thread(target=lambda: wayback._host_fetch(f'http://{host}/x', host, None, 1, 30))
              for _ in range(4)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(max_overlap(spans), 1)

    def test_429_drops_slots_to_one_until_recovered(self):
        self.config({self.host: {'concurrency': 6}})
        wayback.host_get(f'{self.base}/page/1')
        self.assertEqual(wayback.host_policy(self.host, now=self.clock[0])['concurrency'], 6)
        Stub.routes['/busy'] = (429, {}, b'')
        wayback.host_get(f'{self.base}/busy', tries=1)
        self.assertEqual(wayback.host_policy(self.host, now=self.clock[0])['concurrency'], 1)
        self.clock[0] += 3600                                     # the pause is over, the throttle is not
        self.assertEqual(wayback.host_policy(self.host, now=self.clock[0])['concurrency'], 1)
        self.state(throttle_iv=wayback.HOST_THROTTLE_FLOOR + 0.005)
        wayback.host_get(f'{self.base}/page/2')                  # recovered
        self.assertEqual(wayback.host_policy(self.host, now=self.clock[0])['concurrency'], 6)
        self.config({self.host: {'concurrency': 50}})            # never more than HOST_CONCURRENCY_MAX
        self.assertEqual(wayback.host_policy(self.host, now=self.clock[0])['concurrency'], 8)

    def test_bot_sign_forces_one_slot_for_good(self):
        self.config({self.host: {'concurrency': 6}})
        Stub.routes['/page/1'] = (200, {'Set-Cookie': 'incap_ses_9=abc'}, b'one')
        wayback.host_get(f'{self.base}/page/1')
        for dt in (0, 86400, 365 * 86400):
            self.assertEqual(wayback.host_policy(self.host, now=self.clock[0] + dt)['concurrency'], 1)
        self.config({self.host: {'tier': 'A', 'interval': 2, 'concurrency': 6}})
        self.assertEqual(wayback.host_policy(self.host, now=self.clock[0])['concurrency'], 1)

    # ---- stop for good

    def test_challenge_stops_host_for_good_across_processes(self):
        Stub.routes['/page/2'] = (403, {'cf-mitigated': 'challenge', 'Server': 'cloudflare'},
                                  b'<html><title>Just a moment...</title><script src="/cdn-cgi/challenge-platform/x"></script>')
        wayback.host_get(f'{self.base}/page/1')
        with self.assertRaises(wayback.HostStopped):
            wayback.host_get(f'{self.base}/page/2')
        stop = wayback.HOST_STOP_DIR / f'127.0.0.1_{self.port}.json'
        self.assertEqual(json.loads(stop.read_text(encoding='utf-8'))['status'], 403)
        before = len(Stub.seen)
        with self.assertRaises(wayback.HostStopped):
            wayback.host_get(f'{self.base}/page/3')
        self.assertEqual(wayback.host_policy(self.host)['tier'], 'stop')
        env = {**os.environ, 'GITLAW_HOST_RATE_DIR': str(wayback.HOST_DIR),
               'GITLAW_HOST_STOP_DIR': str(wayback.HOST_STOP_DIR), 'GITLAW_HOST_TIERS': str(wayback.HOST_TIERS)}
        code = ('import sys; sys.path.insert(0, sys.argv[1]); import wayback\n'
                'try:\n    wayback.host_get(sys.argv[2])\nexcept wayback.HostStopped as e:\n    print("STOPPED", e); sys.exit(7)\n'
                'sys.exit(0)')
        out = subprocess.run([sys.executable, '-c', code, str(HERE), f'{self.base}/page/1'], env=env,
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 7, out.stdout + out.stderr)
        self.assertEqual(len(Stub.seen), before)                  # a fresh process makes no request
        self.cache.mkdir(parents=True)
        url = f'{self.base}/page/9'
        (self.cache / hashlib.sha256(url.encode()).hexdigest()).write_bytes(b'kept')
        self.assertEqual(wayback.host_get(url, self.cache), b'kept')   # cached copies are still served
        self.assertEqual(len(Stub.seen), before)

    def test_challenge_detection(self):
        incap = b'<html><head><META NAME="robots" CONTENT="noindex,nofollow"><script src="/_Incapsula_Resource?SWJIYLWA=5074a7"></script></head></html>'
        self.assertTrue(wayback._challenge(200, [], incap))                      # Queensland: 200 + 212-byte JS
        self.assertTrue(wayback._challenge(429, [], b'<p>verify you are human</p>'))
        self.assertTrue(wayback._challenge(202, [(202, [('x-amzn-waf-action', 'challenge')])], b''))
        self.assertTrue(wayback._challenge(500, [], b'<h1>Web Page Blocked</h1><p>Attack ID: 20000051</p>'))  # FortiWeb
        self.assertIsNone(wayback._challenge(403, [], b'<h1>403 Forbidden</h1>'))  # a plain 403 stays a plain 403
        self.assertIsNone(wayback._challenge(200, [], b'<html>law text mentioning g-recaptcha forms</html>'))
        self.assertIsNone(wayback._challenge(202, [], b''))

    def test_config_stop(self):
        self.config({self.host: {'tier': 'stop', 'source': 'challenged before'}})
        with self.assertRaises(wayback.HostStopped):
            wayback.host_get(f'{self.base}/page/1')
        self.assertEqual(Stub.seen, [])

    # ---- archive.org's client: one in flight, no cap, Retry-After

    def test_archive_fetch_one_in_flight_no_cap(self):
        for i in (1, 2, 3):
            self.assertEqual(wayback.fetch(f'{self.base}/page/{i}'), [b'one', b'two', b'three'][i - 1])
        self.assertEqual(self.sleeps, [])
        self.assertEqual(wayback.status()['count'], 3)
        self.assertEqual(wayback.status()['inflight'], {})
        Stub.routes['/busy'] = (429, {'Retry-After': '90'}, b'')
        self.assertIsNone(wayback.fetch(f'{self.base}/busy', tries=1))
        st = wayback.status()
        self.assertAlmostEqual(st['pause_until'], self.clock[0] + 90, places=3)
        self.assertTrue(st['throttle_iv'] > 0)
        wayback.fetch(f'{self.base}/page/1', tries=1)
        self.assertAlmostEqual(self.sleeps[-1], 90, places=3)

    # ---- D6

    def test_304_serves_cache_and_counts_a_quarter(self):
        url = f'{self.base}/etag'
        self.assertEqual(wayback.host_get(url, self.cache), b'versioned body')
        meta = json.loads(wayback._meta_file(self.cache, url).read_text(encoding='utf-8'))
        self.assertEqual(meta['etag'], '"v1"')
        self.assertEqual(wayback.host_status(self.host)['count'], 2)          # robots + page
        self.assertEqual(wayback.host_get(url, self.cache), b'versioned body')  # plain cache hit: no request
        self.assertEqual(self.paths(), ['/robots.txt', '/etag'])
        self.assertEqual(wayback.host_get(url, self.cache, refresh=True), b'versioned body')
        last = Stub.seen[-1][1]
        self.assertEqual(last.get('If-None-Match'), '"v1"')
        self.assertEqual(last.get('If-Modified-Since'), 'Mon, 02 Nov 2026 10:00:00 GMT')
        st = wayback.host_status(self.host)
        self.assertEqual(st['count'], 2.25)
        self.assertEqual(st['not_modified'], 1)
        log = [json.loads(x) for x in (self.cache / 'requests.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual([r['status'] for r in log], [200, 304])
        self.assertEqual((self.cache / hashlib.sha256(url.encode()).hexdigest()).read_bytes(), b'versioned body')

    def test_old_cache_entry_without_metadata(self):
        url = f'{self.base}/page/1'
        self.cache.mkdir(parents=True)
        (self.cache / hashlib.sha256(url.encode()).hexdigest()).write_bytes(b'old copy')
        self.assertEqual(wayback.host_get(url, self.cache), b'old copy')
        self.assertEqual(Stub.seen, [])
        self.assertEqual(wayback.host_get(url, self.cache, refresh=True), b'one')
        last = Stub.seen[-1][1]
        self.assertNotIn('If-None-Match', last)
        self.assertNotIn('If-Modified-Since', last)
        self.assertEqual(wayback.host_get(url, self.cache), b'one')

    def test_return_values_unchanged(self):
        self.assertIsNone(wayback.host_get(f'{self.base}/missing'))        # 404 -> None
        Stub.routes['/gone'] = (410, {}, b'')
        self.assertIsNone(wayback.host_get(f'{self.base}/gone'))

    # ---- D7

    def test_robots_groups(self):
        text = ('User-agent: GPTBot\nUser-agent: CCBot\nDisallow: /\nCrawl-delay: 99\n\n'
                'User-agent: Google-Extended\nDisallow: /\n\n'
                'User-agent: ClaudeBot\nDisallow: /claude-only/\nCrawl-delay: 12\n\n'
                'User-agent: *\nDisallow: /search\nCrawl-delay: 5\n\nSitemap: https://x/sitemap.xml\n')
        r = wayback._parse_robots(text)
        self.assertEqual(r['disallow'], ['/claude-only/', '/search'])
        self.assertEqual(r['crawl_delay'], 12.0)
        self.assertEqual(r['sitemaps'], ['https://x/sitemap.xml'])
        self.assertEqual(wayback._parse_robots('User-agent: GPTBot\nDisallow: /\n')['disallow'], [])
        self.assertEqual(wayback._parse_robots('User-agent: anthropic-ai\nDisallow: /\n')['disallow'], ['/'])
        self.assertEqual(wayback._parse_robots('User-agent: Claude-Web\nUser-agent: GPTBot\nDisallow: /x\n')['disallow'], ['/x'])
        self.assertFalse(wayback.robots_allows('https://h/search?q=1', r['disallow']))
        self.assertTrue(wayback.robots_allows('https://h/act/1', r['disallow']))


class HostGetCurl(HostGetCases, unittest.TestCase):
    """Every case through a curl process per request (the old path; hosts flagged 'transport': 'curl')."""
    transport = 'curl'


class HostGetInProcess(HostGetCases, unittest.TestCase):
    """Every case through the in-process keep-alive path."""
    transport = 'python'


def gzip_route(handler):
    import gzip
    body = ('Gesetz ' * 4000).encode('utf-8')
    if 'gzip' in (handler.headers.get('Accept-Encoding') or ''):
        return 200, {'Content-Encoding': 'gzip', 'Vary': 'Accept-Encoding'}, gzip.compress(body)
    return 200, {}, body


def sleep_route(handler):
    time.sleep(3)
    return 200, {}, b'late'


class TransportTest(unittest.TestCase):
    """The in-process path against curl: same status, body and headers; connections reused; SSL failure -> curl."""

    @classmethod
    def setUpClass(cls):
        HostGetCases.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        HostGetCases.tearDownClass.__func__(cls)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = {k: getattr(wayback, k) for k in ('HOST_DIR', 'TRANSPORT', '_curl_proc', '_py_get')}
        wayback.HOST_DIR = Path(self.tmp.name) / 'rate'
        wayback.TRANSPORT = 'auto'
        drop_pools()
        Stub.seen.clear()
        Stub.connections[0] = 0
        Stub.routes = {
            '/plain': (200, {'X-Thing': 'v1', 'Set-Cookie': ['a=1; path=/', '__utm=2; path=/']},
                       b'plain body \x00\xff bytes'),
            '/gz': gzip_route,
            '/r1': (302, {'Location': '/r2'}, b'moved'),
            '/r2': (301, {'Location': f'http://{self.host}/plain'}, b'moved again'),
            '/loop': (302, {'Location': '/loop'}, b''),
            '/nolocation': (307, {}, b'no location'),
            '/etag': etag_route,
            '/missing': (404, {}, b'not here'),
            '/err': (500, {}, b'<h1>Web Page Blocked</h1>'),
            '/sleep': sleep_route,
            '/slow': slow_route,
        }

    def tearDown(self):
        for k, v in self.saved.items():
            setattr(wayback, k, v)
        drop_pools()
        self.tmp.cleanup()

    @staticmethod
    def norm(hops):
        return [(c, [(k, v) for k, v in h if k not in ('date', 'connection', 'keep-alive')]) for c, h in hops]

    def test_same_status_body_and_headers_on_both_paths(self):
        for path, hdrs in (('/plain', []), ('/gz', []), ('/r1', []), ('/nolocation', []), ('/missing', []),
                           ('/err', []), ('/etag', []), ('/etag', ['If-None-Match: "v1"'])):
            url = self.base + path
            a = wayback._curl_proc(url, 30, hdrs)
            b = wayback._py_get(url, 30, hdrs)
            self.assertEqual(a[0], b[0], path)
            self.assertEqual(a[1], b[1], path)                   # byte-identical bodies
            self.assertEqual(self.norm(a[2]), self.norm(b[2]), path)
        code, body, hops = wayback._py_get(self.base + '/r1', 30)
        self.assertEqual((code, body, [c for c, _ in hops]), (200, b'plain body \x00\xff bytes', [302, 301, 200]))
        self.assertEqual([v for k, v in hops[-1][1] if k == 'set-cookie'], ['a=1; path=/', '__utm=2; path=/'])
        self.assertEqual(wayback._py_get(self.base + '/gz', 30)[1], ('Gesetz ' * 4000).encode())
        self.assertEqual(wayback._curl_proc(self.base + '/loop', 30)[0], 0)   # too many redirects: status 0
        self.assertEqual(wayback._py_get(self.base + '/loop', 30)[0], 0)
        # the same request headers reach the server, also after a redirect
        Stub.seen.clear()
        wayback._curl_proc(self.base + '/r1', 30, ['If-None-Match: "x"'])
        wayback._py_get(self.base + '/r1', 30, ['If-None-Match: "x"'])
        self.assertEqual(len(Stub.seen), 6)
        for (p1, h1), (p2, h2) in zip(Stub.seen[:3], Stub.seen[3:]):
            self.assertEqual(p1, p2)
            for k in ('User-Agent', 'Accept', 'If-None-Match'):
                self.assertEqual(h1.get(k), h2.get(k), k)
        self.assertEqual(Stub.seen[-1][1]['User-Agent'], wayback.UA)
        # an HTTP/1.0 server that closes every connection gives the same answers too
        Stub.protocol_version = 'HTTP/1.0'
        try:
            for path in ('/plain', '/gz', '/r1', '/missing'):
                a, b = wayback._curl_proc(self.base + path, 30), wayback._py_get(self.base + path, 30)
                self.assertEqual((a[0], a[1], self.norm(a[2])), (b[0], b[1], self.norm(b[2])), path)
        finally:
            Stub.protocol_version = 'HTTP/1.1'

    def test_timeout_and_refused_give_status_0(self):
        for get in (wayback._curl_proc, wayback._py_get):
            self.assertEqual(get(self.base + '/sleep', 1)[:2], (0, b''))
        import socket
        s = socket.socket()
        s.bind(('127.0.0.1', 0))
        dead = s.getsockname()[1]
        s.close()
        for get in (wayback._curl_proc, wayback._py_get):
            self.assertEqual(get(f'http://127.0.0.1:{dead}/x', 5)[:2], (0, b''))

    def test_keep_alive_connection_is_reused(self):
        for _ in range(6):
            self.assertEqual(wayback._curl_h(self.base + '/plain', 30)[0], 200)
        self.assertEqual(Stub.connections[0], 1)                 # six requests, one connection
        drop_pools()
        Stub.connections[0] = 0
        for _ in range(3):
            wayback._curl_proc(self.base + '/plain', 30)
        self.assertEqual(Stub.connections[0], 3)                 # curl: one per request
        # two requests in flight at once each get their own connection, and both are reused afterwards
        drop_pools()
        Stub.connections[0] = 0
        for _ in range(3):
            ts = [threading.Thread(target=wayback._curl_h, args=(self.base + '/slow', 30)) for _ in range(2)]
            [t.start() for t in ts]
            [t.join() for t in ts]
        self.assertEqual(Stub.connections[0], 2)

    def test_ssl_failure_flips_the_host_to_curl(self):
        calls = {'py': 0, 'curl': 0}
        py, curl = wayback._py_get, wayback._curl_proc

        def py_(*a, **k):
            calls['py'] += 1
            return py(*a, **k)

        def curl_(*a, **k):
            calls['curl'] += 1
            return curl(*a, **k)
        wayback._py_get, wayback._curl_proc = py_, curl_
        url = f'https://{self.host}/plain'                       # TLS to a plain-HTTP server: the handshake fails
        self.assertEqual(wayback._curl_h(url, 10)[0], 0)
        self.assertEqual(calls, {'py': 1, 'curl': 1})            # that request is retried through curl at once
        st = json.loads((wayback.HOST_DIR / f'127.0.0.1_{self.port}.json').read_text(encoding='utf-8'))
        self.assertEqual(st['transport'], 'curl')
        self.assertIn('SSL', st['transport_reason'])
        self.assertEqual(wayback._curl_h(self.base + '/plain', 10)[0], 200)
        self.assertEqual(calls, {'py': 1, 'curl': 2})            # the flag holds for the host from now on
        wayback._CURL_HOSTS.clear()                              # and for a fresh process (it is in the state file)
        wayback._curl_h(self.base + '/plain', 10)
        self.assertEqual(calls, {'py': 1, 'curl': 3})


if __name__ == '__main__':
    unittest.main()
