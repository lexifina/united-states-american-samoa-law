"""host_get vs host_get2 on a real slow-but-healthy host: the Greek FEK PDF store (Azure blob, ~0.5 MB/s for the
whole machine, never answers 429; the earlier lab saw 16 threads "throttle" 25 times there, all 90 s timeouts).

Production settings: host_get timeout 90 s; host_get2 stall 60 s. 16 threads each. Disjoint sets of 2020 ΦΕΚ A'
issues (odd numbers for one policy, even for the other). Each policy gets a private rate-state folder, so the
machine's shared state for this host is not changed by the test.

    python bench_timeout_real.py [--n 40]       # writes bench_timeout_real.json
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hostget2  # noqa: E402
import wayback  # noqa: E402

HOST = 'ia37rg02wpsa01.blob.core.windows.net'
URL = 'https://' + HOST + '/fek/01/2020/202001{:05d}.pdf'


def run(policy: str, nums: list[int], threads: int) -> dict:
    state_dir = Path(tempfile.mkdtemp(prefix=f'hostrate-real-{policy}-'))
    cache = Path(tempfile.mkdtemp(prefix=f'cache-real-{policy}-'))
    wayback.HOST_DIR = state_dir
    tries = {'n': 0, 'fail': 0}
    orig = wayback._curl

    def counting(url, timeout=120):
        tries['n'] += 1
        code, body = orig(url, timeout)
        if code == 0:
            tries['fail'] += 1
        return code, body
    wayback._curl = counting
    hostget2.LOG.clear()
    trace = []
    stop = threading.Event()

    def sample():
        t0 = time.time()
        while not stop.is_set():
            try:
                st = json.loads((state_dir / f'{HOST}.json').read_text())
                trace.append((round(time.time() - t0), round(st['rate'], 2), st['throttled']))
            except (OSError, ValueError):
                pass
            stop.wait(10)
    threading.Thread(target=sample, daemon=True).start()
    t0 = time.time()
    got, nbytes = 0, 0
    with cf.ThreadPoolExecutor(threads) as ex:
        if policy == 'current':
            futs = [ex.submit(wayback.host_get, URL.format(n), cache, 5, 90) for n in nums]
        else:
            futs = [ex.submit(hostget2.host_get2, URL.format(n), cache, 5, 60, 1800) for n in nums]
        for f in cf.as_completed(futs):
            b = f.result()
            if b:
                got += 1
                nbytes += len(b)
    wall = time.time() - t0
    stop.set()
    wayback._curl = orig
    st = json.loads((state_dir / f'{HOST}.json').read_text())
    kinds = {}
    for r in hostget2.LOG:
        kinds[r['kind']] = kinds.get(r['kind'], 0) + 1
    shutil.rmtree(cache, ignore_errors=True)
    shutil.rmtree(state_dir, ignore_errors=True)
    return {'policy': policy, 'files': len(nums), 'completed': got, 'MB': round(nbytes / 1e6, 1),
            'wall_s': round(wall, 1), 'MBps': round(nbytes / 1e6 / wall, 3), 'files_per_min': round(got / wall * 60, 1),
            'curl_tries': tries['n'] if policy == 'current' else len(hostget2.LOG),
            'curl_failures_code0': tries['fail'], 'outcomes': kinds, 'final_rate': round(st['rate'], 2),
            'throttled': st['throttled'], 'trace': trace}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=40)
    ap.add_argument('--threads', type=int, default=16)
    ap.add_argument('--start', type=int, default=1)
    a = ap.parse_args()
    nums = list(range(a.start, a.start + 2 * a.n))
    res = {'host': HOST, 'threads': a.threads, 'runs': []}
    for policy, sub in (('proposed', nums[1::2]), ('current', nums[0::2])):
        r = run(policy, sub, a.threads)
        res['runs'].append(r)
        print({k: v for k, v in r.items() if k != 'trace'}, flush=True)
    (HERE / 'bench_timeout_real.json').write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding='utf-8',
                                                  newline='\n')


if __name__ == '__main__':
    main()
