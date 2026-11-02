"""Tests for fetch_scheduler (the layer above wayback.host_get).

Everything runs against stub HTTP servers on 127.0.0.1; no real network requests. All state (host_get's rate and
stop folders, host_tiers.json, the scheduler's registry, cache and feed) is pointed at a temporary folder. Most tests
inject a clock (wayback._now/_sleep) so they take no wall time; the cross-process and fair-queue tests use real time.

    python -m unittest scripts/gitlaw_common/test_fetch_scheduler.py -v
"""
from __future__ import annotations

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
sys.path.insert(0, str(HERE.parent / 'world-law'))
import wayback  # noqa: E402
import fetch_scheduler as fs  # noqa: E402

CLOCK: list = [0.0]          # the injected clock (when a test uses it); the server stamps hits with it


class Stub(BaseHTTPRequestHandler):
    routes: dict = {}
    seen: list = []          # (port, path, headers, fake time, real time)

    def log_message(self, *a):
        pass

    def do_GET(self):
        Stub.seen.append((self.server.server_address[1], self.path, dict(self.headers), CLOCK[0], time.time()))
        r = Stub.routes.get((self.server.server_address[1], self.path), Stub.routes.get(self.path))
        if callable(r):
            r = r(self)
        if r is None:
            r = (404, {}, b'not found')
        code, headers, body = r
        self.send_response(code)
        for k, v in headers.items():
            self.send_header(k, v)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def etag_route(handler):
    if handler.headers.get('If-None-Match') == '"v1"':
        return 304, {'ETag': '"v1"'}, b''
    return 200, {'ETag': '"v1"', 'Last-Modified': 'Mon, 02 Nov 2026 10:00:00 GMT'}, b'versioned body'


PATHS = ('HOST_DIR', 'HOST_STOP_DIR', 'HOST_TIERS', '_now', '_sleep')
FSPATHS = ('SCHED_DIR', 'SHARED_CACHE', 'OBJECTS', 'FEED_DIR', 'REGISTRY', 'DRY', 'INFLIGHT')


class SchedulerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.servers = []
        for _ in range(2):
            s = ThreadingHTTPServer(('127.0.0.1', 0), Stub)
            threading.Thread(target=s.serve_forever, daemon=True).start()
            cls.servers.append(s)
        cls.port, cls.port2 = (s.server_address[1] for s in cls.servers)
        cls.host, cls.host2 = f'127.0.0.1:{cls.port}', f'127.0.0.1:{cls.port2}'
        cls.base, cls.base2 = f'http://{cls.host}', f'http://{cls.host2}'

    @classmethod
    def tearDownClass(cls):
        for s in cls.servers:
            s.shutdown()
            s.server_close()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.t = Path(self.tmp.name)
        self.saved = {k: getattr(wayback, k) for k in PATHS}
        self.fsaved = {k: getattr(fs, k) for k in FSPATHS}
        wayback.HOST_DIR, wayback.HOST_STOP_DIR, wayback.HOST_TIERS = t / 'rate', t / 'stops', t / 'host_tiers.json'
        fs.SCHED_DIR = t / 'sched'
        fs.SHARED_CACHE, fs.OBJECTS, fs.FEED_DIR = t / 'sched/cache', t / 'sched/objects', t / 'sched/feed'
        fs.REGISTRY, fs.DRY = t / 'fetch_hosts.json', False
        fs.INFLIGHT = dict(fs.INFLIGHT)
        self.saved['HOST_DAILY'] = wayback.HOST_DAILY
        fs._reg_cache.update(key=None, data=None)
        Stub.routes, Stub.seen = {'/robots.txt': (404, {}, b'')}, []
        self.tiers({'tier': 'A', 'interval': 2, 'source': 'test'})

    def tearDown(self):
        for k, v in self.saved.items():
            setattr(wayback, k, v)
        for k, v in self.fsaved.items():
            setattr(fs, k, v)
        self.tmp.cleanup()

    def tiers(self, entry):
        wayback.HOST_TIERS.write_text(json.dumps({'hosts': {'127.0.0.1': entry}}), encoding='utf-8')
        wayback._cfg_cache['key'] = None

    def fake_clock(self, start=None):
        CLOCK[0] = start if start is not None else time.time()
        self.sleeps = []

        def sleep(s):
            self.sleeps.append(s)
            CLOCK[0] += max(s, 0)
        wayback._now, wayback._sleep = (lambda: CLOCK[0]), sleep

    def hits(self, port=None, path=None):
        return [h for h in Stub.seen if (port is None or h[0] == port) and (path is None or h[1] == path)]

    # ---------------------------------------------------------------- bucket
    def test_bucket_paces_the_host(self):
        self.fake_clock()
        Stub.routes['/a'] = Stub.routes['/b'] = (200, {}, b'x' * 10)
        self.assertEqual(fs.get(self.base + '/a'), b'x' * 10)
        self.assertEqual(fs.get(self.base + '/b'), b'x' * 10)
        times = [h[3] for h in Stub.seen]
        self.assertEqual([h[1] for h in Stub.seen], ['/robots.txt', '/a', '/b'])
        gaps = [b - a for a, b in zip(times, times[1:])]
        self.assertTrue(all(g >= 2 - 1e-6 for g in gaps), gaps)
        rep = fs.host_report(self.host)
        self.assertEqual(rep['tier'], 'A')
        self.assertEqual(rep['requests_today'], 3)
        self.assertEqual(fs.registry_entry(self.host)['tier'], 'A')
        self.assertEqual(fs.registry_entry(self.host)['robots']['status'], 404)

    def test_robots_crawl_delay_request_rate_and_visit_time(self):
        self.fake_clock()
        Stub.routes['/robots.txt'] = (200, {}, b'User-agent: GPTBot\nDisallow: /\n\nUser-agent: *\nCrawl-delay: 4\n'
                                               b'Request-rate: 1/7\nVisit-time: 0000-2359\n')
        Stub.routes['/a'] = Stub.routes['/b'] = (200, {}, b'ok')
        self.tiers({'tier': 'C', 'source': 'test'})
        fs.get(self.base + '/a')
        fs.get(self.base + '/b')
        t = [h[3] for h in self.hits(path='/robots.txt') + self.hits(path='/a') + self.hits(path='/b')]
        self.assertGreaterEqual(t[1] - t[0], 7 - 1e-6)          # the first page waits the delay after robots.txt
        t = t[1:]
        self.assertGreaterEqual(t[1] - t[0], 7 - 1e-6)          # Request-rate 1/7 is slower than Crawl-delay 4
        e = fs.registry_entry(self.host)
        self.assertEqual(e['robots']['visit_time'], '00:00-23:59')
        self.assertIn('Crawl-delay: 4', e['robots']['excerpt'])
        self.assertNotIn('GPTBot', e['robots']['excerpt'])
        self.assertEqual(len(self.hits(path='/robots.txt')), 1)  # host_get does not read it a second time

    # ---------------------------------------------------------------- no cap of our own (2026-11-02 21:50 UTC)
    def test_scheduler_adds_no_cap(self):
        """The scheduler has no daily cap, no machine share and no worker clamp; only host_get's own cap (being
        removed there) could still refuse a host, and host_get's cap lifted means no refusal at any count."""
        self.fake_clock()
        self.assertFalse(hasattr(fs, 'CAP_SHARE'))
        Stub.routes['/a'] = Stub.routes['/b'] = (200, {}, b'ok')
        fs.get(self.base + '/a')
        day = time.strftime('%Y-%m-%d', time.gmtime(CLOCK[0]))

        def busy_day(st):
            st.update(day=day, count=50000)   # far past the old 5,000 and 20,000 caps
            return None, st
        wayback._host_locked(self.host, busy_day)
        self.assertEqual(fs.check(self.host) - CLOCK[0] <= 2 + 1e-6, True)   # the scheduler itself never refuses
        wayback.HOST_DAILY = float('inf')                                  # host_get without its cap (hp-omen)
        self.assertEqual(fs.get(self.base + '/b'), b'ok')
        rep = fs.host_report(self.host)
        self.assertNotEqual(rep['status'], 'capped')
        self.assertNotIn('daily', fs.registry_entry(self.host))

    def test_fetch_many_default_workers_one_per_host(self):
        import inspect
        self.assertIsNone(inspect.signature(fs.fetch_many).parameters['workers'].default)
        self.assertNotIn('min(int(workers), 2)', inspect.getsource(fs.fetch_many))

    # ---------------------------------------------------------------- back-off and Retry-After (the site's rules)
    def test_retry_after_pauses_host_and_retries(self):
        self.fake_clock()
        calls = []

        def flaky(handler):
            calls.append(1)
            return (429, {'Retry-After': '120'}, b'slow down') if len(calls) == 1 else (200, {}, b'done')
        Stub.routes['/r'] = flaky
        self.assertEqual(fs.get(self.base + '/r', tries=3), b'done')
        t = [h[3] for h in self.hits(path='/r')]
        self.assertEqual(len(t), 2)
        self.assertGreaterEqual(t[1] - t[0], 120 - 1e-6)                 # Retry-After obeyed
        self.assertEqual(wayback.host_status(self.host)['throttled'], 1)  # host_get's halving (throttle_iv)
        feed = [json.loads(l) for f in fs.FEED_DIR.glob('*.jsonl') for l in f.read_text(encoding='utf-8').splitlines()]
        self.assertIn(120.0, [r.get('retry_after') for r in feed])

    def test_long_retry_after_pauses_every_caller(self):
        self.fake_clock()
        Stub.routes['/r'] = (503, {'Retry-After': '1000'}, b'maintenance')
        Stub.routes['/other'] = (200, {}, b'x')
        self.assertIsNone(fs.get(self.base + '/r', tries=3))            # longer than RETRY_AFTER_MAX_WAIT: no retry
        self.assertEqual(len(self.hits(path='/r')), 1)
        with self.assertRaises(fs.NotNow) as cm:
            fs.get(self.base + '/other', wait=False)
        self.assertGreaterEqual(cm.exception.at, CLOCK[0] + 1000 - 5)
        self.assertIsNotNone(fs.host_report(self.host)['paused_until'])

    def test_503_without_retry_after_backs_off_and_halves(self):
        self.fake_clock()
        calls = []

        def flaky(handler):
            calls.append(1)
            return (503, {}, b'busy') if len(calls) == 1 else (200, {}, b'back')
        Stub.routes['/b'] = flaky
        self.assertEqual(fs.get(self.base + '/b', tries=2), b'back')
        t = [h[3] for h in self.hits(path='/b')]
        self.assertGreaterEqual(t[1] - t[0], wayback.HOST_BACKOFF - 1e-6)
        self.assertEqual(wayback.host_status(self.host)['throttled'], 1)

    # ---------------------------------------------------------------- window
    def test_night_window_waits_or_says_not_now(self):
        start = (int(time.time() // 86400) + 1) * 86400 + 12 * 3600     # tomorrow 12:00 UTC
        self.fake_clock(start)
        fs._reg_update(self.host, lambda e: e.update(window={'tz': 'UTC', 'hours': ['14:00-15:00']}) or e)
        Stub.routes['/n'] = (200, {}, b'night')
        with self.assertRaises(fs.NotNow) as cm:
            fs.get(self.base + '/n', wait=False)
        self.assertEqual(cm.exception.at, start + 2 * 3600)
        self.assertEqual(Stub.seen, [])
        self.assertEqual(fs.host_report(self.host)['status'], 'closed')
        self.assertEqual(fs.get(self.base + '/n'), b'night')      # waits for 14:00
        self.assertGreaterEqual(self.hits(path='/n')[0][3], start + 2 * 3600)
        self.assertLess(self.hits(path='/n')[0][3], start + 3 * 3600)

    def test_window_math(self):
        vienna = fs.WINDOWS['ris.bka.gv.at']
        # Tue 2026-11-03 12:00 UTC = 13:00 Vienna: closed, opens 20:00 Vienna = 19:00 UTC
        tue = 1793707200.0
        self.assertEqual(time.strftime('%a %H:%M', time.gmtime(tue)), 'Tue 12:00')
        self.assertEqual(fs.window_next_open(vienna, tue), tue + 7 * 3600)
        self.assertEqual(fs.window_next_open(vienna, tue + 7 * 3600 + 60), 0.0)      # 20:01 Vienna
        self.assertEqual(fs.window_next_open(vienna, tue + 15 * 3600), 0.0)          # 04:00 Vienna Wed
        self.assertEqual(fs.window_next_open(vienna, tue + 4 * 86400), 0.0)          # Saturday noon
        fr = fs.WINDOWS['legislation.gov.au']                                         # open 10:00-22:00 UTC
        self.assertEqual(fs.window_next_open(fr, tue), 0.0)
        self.assertEqual(fs.window_next_open(fr, tue - 3 * 3600), tue - 2 * 3600)
        self.assertEqual(fs.window_of('www.consiglioregionale.calabria.it')['hours'], ['06:00-08:44'])

    # ---------------------------------------------------------------- 304 + shared cache
    def test_304_costs_a_quarter_and_cache_is_shared(self):
        self.fake_clock()
        Stub.routes['/e'] = etag_route
        url = self.base + '/e'
        mine, theirs = self.t / 'mine', self.t / 'theirs'
        self.assertEqual(fs.get(url, mine), b'versioned body')
        self.assertEqual(fs.get(url, theirs), b'versioned body')   # the other scraper: no request
        self.assertEqual(len(self.hits(path='/e')), 1)
        self.assertTrue(wayback._cached(theirs, url).exists())
        self.assertEqual(fs.get(url, theirs, refresh=True), b'versioned body')
        e = self.hits(path='/e')
        self.assertEqual(len(e), 2)
        self.assertEqual(e[1][2].get('If-None-Match'), '"v1"')
        self.assertEqual(fs.last_status(), 304)
        self.assertAlmostEqual(fs.host_report(self.host)['requests_today'], 2.25)   # robots + 1 + 0.25
        feed = [json.loads(l) for f in fs.FEED_DIR.glob('*.jsonl') for l in f.read_text(encoding='utf-8').splitlines()]
        self.assertEqual([(r['status'], r['cost']) for r in feed if r['event'] == 'get'], [(200, 1), (304, 0.25)])
        self.assertEqual(len(list(fs.OBJECTS.iterdir())), 1)       # content-addressed copy

    def test_identical_bodies_share_one_object_and_404_is_remembered(self):
        self.fake_clock()
        Stub.routes['/x'] = Stub.routes['/y'] = (200, {}, b'same')
        fs.get(self.base + '/x')
        fs.get(self.base + '/y')
        self.assertEqual(len(list(fs.OBJECTS.iterdir())), 1)
        self.assertIsNone(fs.get(self.base + '/missing'))
        self.assertIsNone(fs.get(self.base + '/missing'))
        self.assertEqual(len(self.hits(path='/missing')), 1)

    # ---------------------------------------------------------------- stops
    def test_challenge_stops_for_good_and_a_noted_lift_clears_it(self):
        self.fake_clock()
        Stub.routes['/cf'] = (403, {'cf-ray': 'x'}, b'<html><title>Just a moment...</title>cf-chl-bypass</html>')
        Stub.routes['/ok'] = (200, {}, b'fine')
        with self.assertRaises(fs.HostStopped):
            fs.get(self.base + '/cf')
        n = len(Stub.seen)
        with self.assertRaises(fs.HostStopped):
            fs.get(self.base + '/ok')
        self.assertEqual(len(Stub.seen), n)                         # refused before any request
        e = fs.registry_entry(self.host)
        self.assertEqual(e['tier'], 'stop')
        self.assertIn('challenge', e['blocked']['reason'])
        self.assertEqual(fs.host_report(self.host)['status'], 'blocked')
        fs._reg_update(self.host, lambda e: e.update(lifted_by='test') or e)   # no note: still blocked
        with self.assertRaises(fs.HostStopped):
            fs.get(self.base + '/ok')
        fs._reg_update(self.host, lambda e: e.update(lift_note='publisher allowlisted us (test)') or e)
        self.assertEqual(fs.get(self.base + '/ok'), b'fine')
        self.assertEqual(fs.registry_entry(self.host)['history'][0]['note'], 'publisher allowlisted us (test)')

    def test_redirect_without_location_stops(self):
        self.fake_clock()
        Stub.routes['/s'] = (307, {'Server': 'Sucuri/Cloudproxy'}, b'')
        with self.assertRaises(fs.HostStopped):
            fs.get(self.base + '/s')
        self.assertIn('no Location', fs.blocked(self.host)['reason'])
        self.assertTrue(wayback.host_stopped(self.host))           # host_get refuses it too

    def test_robots_403_or_429_stops(self):
        self.fake_clock()
        Stub.routes['/robots.txt'] = (403, {}, b'Forbidden')
        Stub.routes['/p'] = (200, {}, b'page')
        with self.assertRaises(fs.HostStopped):
            fs.get(self.base + '/p')
        self.assertEqual(self.hits(path='/p'), [])
        self.assertIn('robots.txt', fs.blocked(self.host)['reason'])

    def test_captcha_form_stops(self):
        self.fake_clock()
        Stub.routes['/c'] = (200, {}, b'<html><form action="/v"><img src="/captcha.png"><input name="captcha">'
                                      b'</form></html>')
        with self.assertRaises(fs.HostStopped):
            fs.get(self.base + '/c')

    # ---------------------------------------------------------------- dry
    def test_dry_mode_makes_no_requests(self):
        self.fake_clock()
        Stub.routes['/d'] = (200, {}, b'dry')
        fs.get(self.base + '/d')
        n = len(Stub.seen)
        fs.DRY = True
        self.assertEqual(fs.get(self.base + '/d'), b'dry')
        with self.assertRaises(fs.DryMiss):
            fs.get(self.base + '/new')
        self.assertEqual(len(Stub.seen), n)

    # ---------------------------------------------------------------- adapter
    def test_adopt_br_city_get_host(self):
        self.fake_clock()
        from br_city_get import Host, Stop
        Stub.routes['/law'] = (200, {}, b'lei')
        Stub.routes['/boom'] = (500, {}, b'err')
        H = fs.adopt(Host(self.t / 'city', self.host, delay=0))
        self.assertEqual(H.get(self.base + '/law'), b'lei')
        self.assertTrue(H.path(self.base + '/law').exists())
        self.assertIsNone(H.get(self.base + '/gone'))
        self.assertTrue(Path(str(H.path(self.base + '/gone')) + '.404').exists())
        log = [json.loads(l) for l in (H.dir / 'requests.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual([r['status'] for r in log], ['200', '404'])
        with self.assertRaises(Stop):
            H.get(self.base + '/boom')
        self.assertTrue((H.dir / 'STOP').exists())

    def test_registry_survives_concurrent_readers_and_writers(self):
        errors = []

        def write(h):
            try:
                for i in range(150):
                    fs._reg_update(h, lambda e: e.update(n=e.get('n', 0) + 1) or e)
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        def read():
            try:
                for _ in range(600):
                    fs._reg_cache['key'] = None
                    fs.registry_entry('a')
            except Exception as e:  # noqa: BLE001
                errors.append(e)
        ts = [threading.Thread(target=write, args=(h,)) for h in ('a', 'b')] + [threading.Thread(target=read)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        self.assertEqual(errors, [])
        self.assertEqual((fs.registry_entry('a')['n'], fs.registry_entry('b')['n']), (150, 150))

    # ---------------------------------------------------------------- requests in flight per host
    def slow_routes(self, prefix, n, delay=0.6):
        state = {'now': 0, 'max': 0}
        lk = threading.Lock()

        def slow(handler):
            with lk:
                state['now'] += 1
                state['max'] = max(state['max'], state['now'])
            time.sleep(delay)
            with lk:
                state['now'] -= 1
            return 200, {}, handler.path.encode()
        for i in range(n):
            Stub.routes[f'{prefix}{i}'] = slow
        return state

    def test_listed_api_paths_get_several_in_flight_html_stays_at_one(self):
        self.tiers({'tier': 'A', 'rate': 1000, 'concurrency': 4, 'source': 'test: stated no limit'})
        fs.INFLIGHT['127.0.0.1'] = {'n': 4, 'paths': ['/api/'], 'evidence': 'test API'}
        api = self.slow_routes('/api/', 8)
        got = list(fs.fetch_many([f'{self.base}/api/{i}' for i in range(8)], workers=6))
        self.assertTrue(all(isinstance(r, bytes) for _, r in got), got)
        self.assertGreaterEqual(api['max'], 2)                       # several at once ...
        self.assertLessEqual(api['max'], 4)                          # ... never more than max_inflight
        html = self.slow_routes('/page/', 4, 0.3)
        got = list(fs.fetch_many([f'{self.base}/page/{i}' for i in range(4)], workers=4))
        self.assertTrue(all(isinstance(r, bytes) for _, r in got), got)
        self.assertEqual(html['max'], 1)                             # crawled HTML: one in flight
        e = fs.registry_entry(self.host)                              # the registry records it, with evidence
        self.assertEqual((e['max_inflight']['from'], e['max_inflight']['evidence']), ('seed', 'test API'))
        self.assertIn('n', e['inflight_now'])

    def test_unlisted_host_one_in_flight_machine_wide(self):
        self.tiers({'tier': 'A', 'rate': 1000, 'source': 'test'})
        res = []

        def claim():
            res.append(fs._claim(self.host, 60, self.base + '/api/x')[0])
        ts = [threading.Thread(target=claim) for _ in range(5)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        self.assertEqual(res.count('go'), 1)
        self.tiers({'tier': 'A', 'rate': 1000, 'concurrency': 4, 'source': 'test'})
        fs.INFLIGHT['127.0.0.1'] = {'n': 4, 'paths': ['/api/'], 'evidence': 'test API'}
        res.clear()
        ts = [threading.Thread(target=claim) for _ in range(6)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        self.assertEqual(res.count('go'), 3)                         # 4 in flight, one lease already held

    def test_429_drops_to_one_in_flight_until_host_get_recovers(self):
        self.fake_clock()
        self.tiers({'tier': 'A', 'rate': 1000, 'concurrency': 4, 'source': 'test'})
        fs.INFLIGHT['127.0.0.1'] = {'n': 4, 'paths': ['/api/'], 'evidence': 'test API'}
        api = self.base + '/api/1'
        self.assertEqual(fs.inflight_limit(self.host, api, wayback.host_status(self.host))[0], 4)
        Stub.routes['/api/1'] = (429, {}, b'too many')
        self.assertIsNone(fs.get(api, tries=1))
        st = wayback.host_status(self.host)
        self.assertTrue(st.get('throttle_iv'))                                     # host_get halved the rate
        self.assertEqual(fs.inflight_limit(self.host, api, st)[0], 1)              # and dropped to 1 in flight
        Stub.routes['/api/1'] = (200, {}, b'ok')
        CLOCK[0] = st['pause_until'] + 1
        for i in range(400):                                                       # clean answers: it recovers
            if not wayback.host_status(self.host).get('throttle_iv'):
                break
            Stub.routes[f'/api/r{i}'] = (200, {}, b'ok')
            fs.get(f'{self.base}/api/r{i}')
        self.assertFalse(wayback.host_status(self.host).get('throttle_iv'))
        self.assertEqual(fs.inflight_limit(self.host, api, wayback.host_status(self.host))[0], 4)

    def test_bot_sign_keeps_one_in_flight_and_ceiling_is_8(self):
        fs.INFLIGHT['127.0.0.1'] = {'n': 50, 'paths': ['/api/'], 'evidence': 'test API'}
        self.tiers({'tier': 'A', 'rate': 1000, 'concurrency': 50, 'source': 'test'})
        api = self.base + '/api/1'
        self.assertEqual(fs.inflight_limit(self.host, api, {})[0], 8)              # Alan: 4-8, never more
        self.assertEqual(fs.inflight_limit(self.host, api, {'bot': 'cloudflare (cookie __cf_bm)'})[0], 1)
        fs._reg_update(self.host, lambda e: e.update(max_inflight={}) or e)        # a person turned the scope off:
        self.assertEqual(fs.inflight_limit(self.host, api, {})[0], 8)              # host_get's own value applies
        self.tiers({'tier': 'A', 'rate': 1000, 'source': 'test'})                  # no concurrency in host_tiers
        fs.INFLIGHT['127.0.0.1'] = {'n': 4, 'paths': ['/api/'], 'evidence': 'test API'}
        fs._reg_update(self.host, lambda e: e.pop('max_inflight', None) and e or e)
        self.assertEqual(fs.inflight_limit(self.host, api, {})[0], 1)              # host_get grants the slots

    def test_seeded_public_apis(self):
        self.assertEqual(fs.inflight_spec('www.boe.es')['paths'], ['/datosabiertos/api/'])
        self.assertEqual(fs.inflight_spec('data.sa.gov.au')['paths'], ['/data/'])   # CKAN API and data files
        self.assertIsNone(fs.inflight_spec('busquedas.elperuano.pe'))   # not documented as an API
        self.assertEqual(fs.inflight_limit('www.boe.es', 'https://www.boe.es/buscar/act.php?id=1', {})[0], 1)

    # ---------------------------------------------------------------- real time: fair queue + two processes
    def test_fair_queue_interleaves_hosts(self):
        self.tiers({'tier': 'A', 'interval': 0.5, 'source': 'test'})
        for p in ('/1', '/2', '/3'):
            Stub.routes[p] = (200, {}, p.encode())
        urls = [self.base + p for p in ('/1', '/2', '/3')] + [self.base2 + p for p in ('/1', '/2', '/3')]
        got = list(fs.fetch_many(urls, workers=2))
        self.assertEqual(sorted(u for u, _ in got), sorted(urls))
        self.assertTrue(all(isinstance(r, bytes) for _, r in got), got)
        ports = [h[0] for h in Stub.seen if h[1] != '/robots.txt']
        self.assertEqual(set(ports[:3]), {self.port, self.port2}, ports)
        # the two hosts run side by side, not one host after the other: their request spans overlap
        # (wall-clock bounds are not asserted: under load a curl start can take seconds)
        a, b = ([h[4] for h in self.hits(port=p)] for p in (self.port, self.port2))
        self.assertLess(max(a[0], b[0]), min(a[-1], b[-1]), (a, b))
        for port in (self.port, self.port2):
            t = [h[4] for h in self.hits(port=port)]
            self.assertTrue(all(b - a >= 0.45 for a, b in zip(t, t[1:])), t)

    def test_two_processes_share_bucket_and_cache(self):
        self.tiers({'tier': 'A', 'interval': 1.0, 'source': 'test'})
        urls = [f'{self.base}/p{i}' for i in range(4)]
        for i in range(4):
            Stub.routes[f'/p{i}'] = (200, {}, f'page {i}'.encode())
        env = dict(os.environ, GITLAW_HOST_RATE_DIR=str(wayback.HOST_DIR), GITLAW_HOST_STOP_DIR=str(wayback.HOST_STOP_DIR),
                   GITLAW_HOST_TIERS=str(wayback.HOST_TIERS), GITLAW_SCHED_DIR=str(fs.SCHED_DIR),
                   GITLAW_FETCH_REGISTRY=str(fs.REGISTRY))
        code = ('import sys, json; sys.path.insert(0, sys.argv[1]); import fetch_scheduler as fs; '
                'print(json.dumps([fs.get(u).decode() for u in sys.argv[2:]]))')
        procs = [subprocess.Popen([sys.executable, '-c', code, str(HERE), *(urls if k == 0 else urls[::-1])], env=env,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for k in range(2)]
        outs = [p.communicate(timeout=60) for p in procs]
        for p, (out, err) in zip(procs, outs):
            self.assertEqual(p.returncode, 0, err)
            self.assertEqual(sorted(json.loads(out)), [f'page {i}' for i in range(4)])
        pages = [h for h in Stub.seen if h[1] != '/robots.txt']
        self.assertEqual(sorted(h[1] for h in pages), [f'/p{i}' for i in range(4)])   # each URL fetched once
        self.assertEqual(len(self.hits(path='/robots.txt')), 1)
        # one bucket for both processes: slots start >= 1 s apart; arrival times add curl start-up jitter, so
        # check the span (5 requests: >= 4 s) and that no two arrive together
        t = sorted(h[4] for h in Stub.seen)
        self.assertGreaterEqual(t[-1] - t[0], 3.8, t)
        self.assertTrue(all(b - a >= 0.4 for a, b in zip(t, t[1:])), t)
        slots = [json.loads(l) for f in fs.FEED_DIR.glob('*.jsonl') for l in f.read_text(encoding='utf-8').splitlines()]
        self.assertEqual(len(slots), 5)                                            # every request in the feed


if __name__ == '__main__':
    unittest.main()
