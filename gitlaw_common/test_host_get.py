"""Tests for wayback.host_get's tiered pacing (D5), conditional requests (D6) and robots groups (D7).

Everything runs against a stub HTTP server on 127.0.0.1; no real network requests. State, stop and config paths are
pointed at a temporary folder, and the clock is injected, so the pacing checks take no wall time.

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


class Stub(BaseHTTPRequestHandler):
    routes: dict = {}
    seen: list = []

    def log_message(self, *a):
        pass

    def do_GET(self):
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


def etag_route(handler):
    if handler.headers.get('If-None-Match') == '"v1"':
        return 304, {'ETag': '"v1"'}, b''
    return 200, {'ETag': '"v1"', 'Last-Modified': 'Mon, 02 Nov 2026 10:00:00 GMT'}, b'versioned body'


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
        t = Path(self.tmp.name)
        self.saved = {k: getattr(wayback, k) for k in ('HOST_DIR', 'HOST_STOP_DIR', 'HOST_TIERS', '_now', '_sleep',
                                                       'HOST_QUALIFY')}
        wayback.HOST_DIR, wayback.HOST_STOP_DIR, wayback.HOST_TIERS = t / 'rate', t / 'stops', t / 'host_tiers.json'
        self.clock = [time.time()]
        self.sleeps = []

        def sleep(s):
            self.sleeps.append(round(s, 6))
            self.clock[0] += s
        wayback._now, wayback._sleep = (lambda: self.clock[0]), sleep
        Stub.seen.clear()
        Stub.routes = {'/robots.txt': (200, {}, b'User-agent: *\nDisallow: /private/\n'),
                       '/page/1': (200, {}, b'one'), '/page/2': (200, {}, b'two'), '/page/3': (200, {}, b'three'),
                       '/etag': etag_route}
        self.cache = t / 'cache'

    def tearDown(self):
        for k, v in self.saved.items():
            setattr(wayback, k, v)
        self.tmp.cleanup()

    def config(self, hosts: dict):
        wayback.HOST_TIERS.write_text(json.dumps({'hosts': hosts}), encoding='utf-8')

    def paths(self):
        return [p for p, _ in Stub.seen]

    # ---- D5

    def test_unknown_host_is_paced_like_tier_c(self):
        for i in (1, 2, 3):
            self.assertEqual(wayback.host_get(f'{self.base}/page/{i}'), [b'one', b'two', b'three'][i - 1])
        # robots.txt first (no wait), then each page 3 s after the previous request start
        self.assertEqual(self.paths(), ['/robots.txt', '/page/1', '/page/2', '/page/3'])
        self.assertEqual(self.sleeps, [3.0, 3.0, 3.0])
        pol = wayback.host_policy(self.host, now=self.clock[0])
        self.assertEqual((pol['tier'], pol['interval'], pol['daily']), ('C', 3.0, 5000))
        self.assertIn('unqualified', pol['reason'])
        self.assertEqual(wayback.host_status(self.host)['count'], 4)

    def test_daily_cap_kept(self):
        wayback.host_get(f'{self.base}/page/1')

        def full(st):
            st['count'] = wayback.HOST_DAILY
            return None, st
        wayback._host_locked(self.host, full)
        with self.assertRaises(wayback.HostDailyCap):
            wayback.host_get(f'{self.base}/page/2')
        self.assertNotIn('/page/2', self.paths())

    def test_bot_management_cookie_makes_tier_c_for_good(self):
        wayback.HOST_QUALIFY = 2
        Stub.routes['/page/1'] = (200, {'CF-RAY': '8abc-LHR', 'Set-Cookie': '__cf_bm=xyz; path=/'}, b'one')
        for i in (1, 2, 3):
            wayback.host_get(f'{self.base}/page/{i}')
        st = wayback.host_status(self.host)
        self.assertTrue(st['bot'].startswith('cloudflare'))
        pol = wayback.host_policy(self.host, now=self.clock[0] + 10 * 86400)
        self.assertEqual((pol['tier'], pol['interval']), ('C', 3.0))
        # cf-ray alone (CDN, no bot-management cookie) is not a signal
        self.assertIsNone(wayback._bot_signal([(200, [('cf-ray', 'x'), ('server', 'cloudflare')])]))
        for hdrs, who in (([('set-cookie', '_abck=1')], 'akamai'), ([('set-cookie', 'incap_ses_1=2')], 'imperva'),
                          ([('set-cookie', 'datadome=1')], 'datadome'), ([('set-cookie', '_pxhd=1')], 'perimeterx'),
                          ([('set-cookie', 'aws-waf-token=1')], 'aws-waf'), ([('server', 'Sucuri/Cloudproxy')], 'sucuri')):
            self.assertTrue(wayback._bot_signal([(200, hdrs)]).startswith(who), who)

    def test_tier_b_ramp_math(self):
        t0 = 1_800_000_000.0
        st = {'rate': wayback.HOST_START, 'clean': wayback.HOST_QUALIFY, 'robots_ok': True, 'b_since': t0}
        day = 86400.0
        for dt, interval in ((0, 3.0), (0.75 * day, 2.0), (1.5 * day, 1.5), (3 * day, 1.0), (30 * day, 1.0)):
            pol = wayback._policy(self.host, st, t0 + dt)
            self.assertEqual(pol['tier'], 'B')
            self.assertAlmostEqual(pol['interval'], interval, places=6)
        # not yet qualified: C pace
        self.assertEqual(wayback._policy(self.host, {**st, 'clean': 3}, t0 + 3 * day)['interval'], 3.0)
        self.assertEqual(wayback._policy(self.host, {**st, 'robots_ok': False}, t0 + 3 * day)['tier'], 'C')
        # a slower robots Crawl-delay wins over the ramp (and makes the host tier A at that rate)
        pol = wayback._policy(self.host, {**st, 'crawl_delay': 4}, t0 + 3 * day)
        self.assertEqual((pol['tier'], pol['interval']), ('A', 4.0))
        # an earlier 429/503 halving still slows everything down
        self.assertAlmostEqual(wayback._policy(self.host, {**st, 'rate': wayback.HOST_START / 2}, t0 + 3 * day)['interval'], 2.0)
        # an old state file with a faster rate is no faster than today
        self.assertEqual(wayback._policy(self.host, {'rate': 0.5}, t0)['interval'], 3.0)

    def test_tier_b_qualifies_and_ramps_with_injected_clock(self):
        wayback.HOST_QUALIFY = 3
        for i in (1, 2, 3):
            wayback.host_get(f'{self.base}/page/{i}')   # robots + 3 clean responses
        self.assertEqual(self.sleeps, [3.0, 3.0, 3.0])
        Stub.routes['/page/4'] = (200, {}, b'four')
        Stub.routes['/page/5'] = (200, {}, b'five')
        wayback.host_get(f'{self.base}/page/4')     # first B request: ramp starts here (3 s)
        st = wayback.host_status(self.host)
        self.assertEqual(st['tier'], 'B')
        self.clock[0] = st['b_since'] + 1.5 * 86400
        self.sleeps.clear()
        wayback.host_get(f'{self.base}/page/5')
        self.assertEqual(wayback.host_status(self.host)['next'], self.clock[0] + 1.5)
        # a 429 restarts the ramp
        Stub.routes['/page/6'] = (429, {}, b'slow down')
        wayback.host_get(f'{self.base}/page/6', tries=1)
        st = wayback.host_status(self.host)
        self.assertNotIn('b_since', st)
        self.assertEqual(st['clean'], 0)

    def test_tier_a_stated_rate_and_slower_crawl_delay(self):
        self.config({self.host: {'tier': 'A', 'interval': 7, 'source': 'API docs'}})
        for i in (1, 2):
            wayback.host_get(f'{self.base}/page/{i}')
        self.assertEqual(self.sleeps, [7.0, 7.0])
        pol = wayback.host_policy(self.host, now=self.clock[0])
        self.assertEqual((pol['tier'], pol['interval']), ('A', 7.0))
        # a fast stated rate is used as stated
        self.config({self.host: {'tier': 'A', 'rate': 2}})
        self.assertEqual(wayback.host_policy(self.host, now=self.clock[0])['interval'], 0.5)
        # robots Crawl-delay 9 is slower than the stated 7 s, so it wins
        self.config({self.host: {'tier': 'A', 'interval': 7}})
        Stub.routes['/robots.txt'] = (200, {}, b'User-agent: *\nCrawl-delay: 9\n')
        wayback._note_robots(self.host, 200, 9)
        self.assertEqual(wayback.host_policy(self.host, now=self.clock[0])['interval'], 9.0)
        # config tier C and www/wildcard lookups
        self.config({'*.example.org': {'tier': 'C'}, 'example.net': {'tier': 'A', 'interval': 4}})
        self.assertEqual(wayback._host_cfg('a.b.example.org')['tier'], 'C')
        self.assertEqual(wayback._host_cfg('www.example.net')['interval'], 4)

    def test_robots_crawl_delay_read_by_host_get(self):
        Stub.routes['/robots.txt'] = (200, {}, b'User-agent: GPTBot\nCrawl-delay: 60\n\nUser-agent: *\nCrawl-delay: 6\n')
        for i in (1, 2):
            wayback.host_get(f'{self.base}/page/{i}')
        self.assertEqual(wayback.host_status(self.host)['crawl_delay'], 6.0)
        self.assertEqual(self.sleeps, [3.0, 6.0])   # page 1 was booked 3 s after robots.txt; page 2 6 s after page 1
        # robots is read once per ROBOTS_TTL
        wayback.host_get(f'{self.base}/page/3')
        self.assertEqual(self.paths().count('/robots.txt'), 1)

    def test_challenge_stops_host_for_good_across_processes(self):
        Stub.routes['/page/2'] = (403, {'cf-mitigated': 'challenge', 'Server': 'cloudflare'},
                                  b'<html><title>Just a moment...</title><script src="/cdn-cgi/challenge-platform/x"></script>')
        wayback.host_get(f'{self.base}/page/1')
        with self.assertRaises(wayback.HostStopped):
            wayback.host_get(f'{self.base}/page/2')
        stop = wayback.HOST_STOP_DIR / f'127.0.0.1_{self.port}.json'
        self.assertTrue(stop.exists())
        self.assertEqual(json.loads(stop.read_text(encoding='utf-8'))['status'], 403)
        before = len(Stub.seen)
        with self.assertRaises(wayback.HostStopped):
            wayback.host_get(f'{self.base}/page/3')
        self.assertEqual(wayback.host_policy(self.host)['tier'], 'stop')
        # a fresh process sees the stop and makes no request
        env = {**os.environ, 'GITLAW_HOST_RATE_DIR': str(wayback.HOST_DIR),
               'GITLAW_HOST_STOP_DIR': str(wayback.HOST_STOP_DIR), 'GITLAW_HOST_TIERS': str(wayback.HOST_TIERS)}
        code = ('import sys; sys.path.insert(0, sys.argv[1]); import wayback\n'
                'try:\n    wayback.host_get(sys.argv[2])\nexcept wayback.HostStopped as e:\n    print("STOPPED", e); sys.exit(7)\n'
                'sys.exit(0)')
        out = subprocess.run([sys.executable, '-c', code, str(HERE), f'{self.base}/page/1'], env=env,
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 7, out.stdout + out.stderr)
        self.assertEqual(len(Stub.seen), before)
        # cached copies are still served (no request to the host)
        self.cache.mkdir(parents=True)
        url = f'{self.base}/page/9'
        (self.cache / hashlib.sha256(url.encode()).hexdigest()).write_bytes(b'kept')
        self.assertEqual(wayback.host_get(url, self.cache), b'kept')
        self.assertEqual(len(Stub.seen), before)

    def test_challenge_detection(self):
        incap = b'<html><head><META NAME="robots" CONTENT="noindex,nofollow"><script src="/_Incapsula_Resource?SWJIYLWA=5074a7"></script></head></html>'
        self.assertTrue(wayback._challenge(200, [], incap))                      # Queensland: 200 + 212-byte JS
        self.assertTrue(wayback._challenge(429, [], b'<p>verify you are human</p>'))
        self.assertTrue(wayback._challenge(202, [(202, [('x-amzn-waf-action', 'challenge')])], b''))
        self.assertIsNone(wayback._challenge(403, [], b'<h1>403 Forbidden</h1>'))  # a plain 403 stays a plain 403
        self.assertIsNone(wayback._challenge(200, [], b'<html>law text mentioning g-recaptcha forms</html>'))
        self.assertIsNone(wayback._challenge(202, [], b''))                         # no bot sign: not a challenge

    def test_config_stop(self):
        self.config({self.host: {'tier': 'stop', 'source': 'challenged before'}})
        with self.assertRaises(wayback.HostStopped):
            wayback.host_get(f'{self.base}/page/1')
        self.assertEqual(Stub.seen, [])

    # ---- D6

    def test_304_serves_cache_and_costs_a_quarter(self):
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
        # the cache layout is unchanged: <sha256 of url> holds the body
        self.assertEqual((self.cache / hashlib.sha256(url.encode()).hexdigest()).read_bytes(), b'versioned body')

    def test_old_cache_entry_without_metadata(self):
        url = f'{self.base}/page/1'
        self.cache.mkdir(parents=True)
        (self.cache / hashlib.sha256(url.encode()).hexdigest()).write_bytes(b'old copy')
        self.assertEqual(wayback.host_get(url, self.cache), b'old copy')
        self.assertEqual(Stub.seen, [])
        # refresh of an entry with no validators: a full, unconditional GET that replaces it
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


if __name__ == '__main__':
    unittest.main()
