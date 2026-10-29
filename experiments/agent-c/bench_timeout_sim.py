"""Does host_get's timeout handling halve the rate of a slow-but-healthy host? Local simulation, no network.

A local HTTP server shares a fixed bandwidth (like the Greek FEK blob store, ~0.5 MB/s for the whole machine) between
all open downloads and never answers 429/503: it is healthy, just slow. We fetch a mix of big and small files with
16 threads, once through wayback.host_get (current: pushback on code 0, fixed --max-time) and once through
hostget2.host_get2 (proposed: stall timeout, pushback only on 429/503/refused/reset). Times are scaled down 4.5x
from production (90 s max-time -> 20 s; 60 s stall -> 13 s) so a run takes minutes. Both runs use a private
rate-state folder, so the machine's real per-host state is untouched.

A second scenario ('overloaded') makes the server answer 429 when more than 4 downloads are open, to check that the
proposed policy still backs off on real pushback.

    python bench_timeout_sim.py            # writes bench_timeout_sim.json
"""
from __future__ import annotations

import concurrent.futures as cf
import http.server
import json
import random
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hostget2  # noqa: E402
import wayback  # noqa: E402  (hostget2 put gitlaw_common on sys.path)

BANDWIDTH = 2_000_000          # bytes/s shared by every open download
SIZES = [4_000_000] * 10 + [150_000] * 22     # 10 big, 22 small (Greek mix: most ~0.5 MB, some 2-11 MB)
THREADS = 16
CUR_TIMEOUT = 20               # production 90 s
NEW_STALL, NEW_CEILING = 13, 600


class Bucket:
    def __init__(self, rate):
        self.rate, self.lock, self.t, self.sent = rate, threading.Lock(), time.time(), 0

    def take(self, n):
        while True:
            with self.lock:
                now = time.time()
                allowed = (now - self.t) * self.rate
                if allowed >= n:
                    self.t += n / self.rate
                    if self.t < now - 0.2:
                        self.t = now - 0.2
                    self.sent += n
                    return
                need = (n - allowed) / self.rate
            time.sleep(min(need, 0.05))


class State:
    bucket = Bucket(BANDWIDTH)
    open_now = 0
    lock = threading.Lock()
    limit_open = None          # int -> 429 above this many open downloads
    n429 = 0


class H(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *a):
        pass

    def do_GET(self):
        size = int(self.path.rsplit('/', 1)[-1].split('-')[0])
        with State.lock:
            if State.limit_open is not None and State.open_now >= State.limit_open:
                State.n429 += 1
                self.send_response(429)
                self.send_header('Retry-After', '2')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            State.open_now += 1
        try:
            self.send_response(200)
            self.send_header('Content-Type', 'application/pdf')
            self.send_header('Content-Length', str(size))
            self.end_headers()
            chunk = b'x' * 16384
            left = size
            while left > 0:
                n = min(16384, left)
                State.bucket.take(n)
                self.wfile.write(chunk[:n])
                left -= n
        except (ConnectionError, OSError):
            pass
        finally:
            with State.lock:
                State.open_now -= 1


def run(policy: str, port: int, scenario: str) -> dict:
    state_dir = Path(tempfile.mkdtemp(prefix=f'hostrate-{policy}-'))
    cache = Path(tempfile.mkdtemp(prefix=f'cache-{policy}-'))
    wayback.HOST_DIR = state_dir
    orig = wayback._host_locked.__wrapped__ if hasattr(wayback._host_locked, '__wrapped__') else wayback._host_locked

    def safe(host, fn):                      # 'localhost:port' is not a valid Windows file name
        return orig(host.replace(':', '_'), fn)
    safe.__wrapped__ = orig
    wayback._host_locked = safe
    hostget2.LOG.clear()
    State.bucket = Bucket(BANDWIDTH)
    State.n429 = 0
    State.limit_open = 4 if scenario == 'overloaded' else None
    tries = {'n': 0}
    orig_curl = wayback._curl

    def counting_curl(url, timeout=120):
        tries['n'] += 1
        return orig_curl(url, timeout)
    wayback._curl = counting_curl
    urls = [f'http://127.0.0.1:{port}/{s}-{policy}-{i}' for i, s in enumerate(SIZES)]
    random.Random(7).shuffle(urls)
    rates = []
    stop = threading.Event()

    def sample():
        t0 = time.time()
        while not stop.is_set():
            try:
                st = json.loads((state_dir / f'127.0.0.1_{port}.json').read_text())
                rates.append((round(time.time() - t0, 1), round(st['rate'], 2), st['throttled'],
                              round(max(0, st['pause_until'] - time.time()), 1)))
            except (OSError, ValueError):
                pass
            stop.wait(1.0)
    threading.Thread(target=sample, daemon=True).start()
    t0 = time.time()
    ok_bytes = 0
    done = 0
    with cf.ThreadPoolExecutor(THREADS) as ex:
        if policy == 'current':
            futs = [ex.submit(wayback.host_get, u, cache, 5, CUR_TIMEOUT) for u in urls]
        else:
            futs = [ex.submit(hostget2.host_get2, u, cache, 5, NEW_STALL, NEW_CEILING) for u in urls]
        for f in cf.as_completed(futs):
            b = f.result()
            if b:
                done += 1
                ok_bytes += len(b)
    wall = time.time() - t0
    stop.set()
    wayback._curl = orig_curl
    st = json.loads((state_dir / f'127.0.0.1_{port}.json').read_text())
    shutil.rmtree(cache, ignore_errors=True)
    shutil.rmtree(state_dir, ignore_errors=True)
    return {'policy': policy, 'scenario': scenario, 'files': len(urls), 'completed': done,
            'wall_s': round(wall, 1), 'useful_MB': round(ok_bytes / 1e6, 2),
            'useful_MBps': round(ok_bytes / 1e6 / wall, 3), 'server_sent_MB': round(State.bucket.sent / 1e6, 2),
            'wasted_MB': round((State.bucket.sent - ok_bytes) / 1e6, 2), 'curl_tries': tries['n'] or len(hostget2.LOG),
            'final_rate': round(st['rate'], 2), 'throttled': st['throttled'], 'server_429s': State.n429,
            'rate_trace': rates[::5]}


def main():
    import argparse
    global BANDWIDTH, SIZES
    ap = argparse.ArgumentParser()
    ap.add_argument('--bandwidth', type=int, default=BANDWIDTH)
    ap.add_argument('--big', type=int, default=10, help='number of big files')
    ap.add_argument('--big-size', type=int, default=4_000_000)
    ap.add_argument('--small', type=int, default=22)
    ap.add_argument('--scenarios', default='healthy,overloaded')
    ap.add_argument('--out', default='bench_timeout_sim.json')
    a = ap.parse_args()
    BANDWIDTH, SIZES = a.bandwidth, [a.big_size] * a.big + [150_000] * a.small
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H)
    srv.daemon_threads = True
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    out = {'bandwidth_Bps': BANDWIDTH, 'sizes': SIZES, 'threads': THREADS, 'current_max_time_s': CUR_TIMEOUT,
           'new_stall_s': NEW_STALL, 'runs': []}
    for scenario in a.scenarios.split(','):
        for policy in ('current', 'proposed'):
            r = run(policy, port, scenario)
            out['runs'].append(r)
            print({k: v for k, v in r.items() if k != 'rate_trace'}, flush=True)
    (HERE / a.out).write_text(json.dumps(out, indent=1), encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
