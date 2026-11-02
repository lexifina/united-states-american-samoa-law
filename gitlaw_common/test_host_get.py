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
    routes: dict = {}
    seen: list = []

    def log_message(self, *a):
        pass

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


def max_overlap(spans) -> int:
    ev = sorted([(a, 1) for a, _ in spans] + [(b, -1) for _, b in spans], key=lambda e: (e[0], e[1]))
    cur = best = 0
    for _, d in ev:
        cur += d
        best = max(best, cur)
    return best


class HostGetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Stub)
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
                                                       '_curl_h', 'STATE', 'LOCK')}
        wayback.HOST_DIR, wayback.HOST_STOP_DIR, wayback.HOST_TIERS = t / 'rate', t / 'stops', t / 'host_tiers.json'
        wayback.STATE, wayback.LOCK = t / 'archive.json', t / 'archive.lock'
        wayback._cfg_cache['key'] = None
        self.fake_clock()
        Stub.seen.clear()
        _active[:] = [0, 0]
        Stub.routes = {'/robots.txt': (200, {}, b'User-agent: *\nDisallow: /private/\n'),
                       '/page/1': (200, {}, b'one'), '/page/2': (200, {}, b'two'), '/page/3': (200, {}, b'three'),
                       '/etag': etag_route, '/slow': slow_route}
        self.cache = t / 'cache'

    def tearDown(self):
        for k, v in self.saved.items():
            setattr(wayback, k, v)
        wayback._cfg_cache['key'] = None
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


if __name__ == '__main__':
    unittest.main()
