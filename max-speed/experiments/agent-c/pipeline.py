"""Fetch continuously, parse what has arrived: a producer/consumer helper over the wayback.py cache (agent C proposal).

Agents lose most of their fetch time between tool calls: fetch a batch, stop, parse it, think, fetch the next batch.
This keeps one fetch queue running in a background thread pool (or a background process) while the parser consumes
results in the order they land.

In one script (the simplest form):

    import sys; sys.path.insert(0, r'<max-speed>/experiments/agent-c'); import pipeline, wayback
    for url, body in pipeline.stream(urls, lambda u: wayback.host_get(u, CACHE), threads=12):
        if body: parse(url, body)          # runs while the other fetches continue

Across tool calls (an agent's one fetch process, started with run_in_background; it exits by itself when idle):

    python pipeline.py serve CACHE                      # fetches every URL appended to CACHE/queue.txt
    pipeline.enqueue(CACHE, more_urls)                  # from any later step, as soon as the URLs are known
    for rec in pipeline.ready(CACHE): parse(rec)        # what has landed so far ({'url','ok','bytes','path'})

The serve process picks the fetcher by host: web.archive.org -> wayback.fetch (the shared archive.org rate),
arquivo.pt -> host_get, everything else -> host_get under its adaptive rate. It reads each host's robots.txt once:
Disallowed URLs are skipped (recorded with ok=false, why='robots'), and a stated Crawl-delay is honoured machine-wide
by one lane with that spacing (host_get alone does not read robots.txt). Cached URLs are reported at once without a
request.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import os
import queue
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Iterable, Iterator

sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common')
import wayback  # noqa: E402


# ------------------------------------------------------------------ in-process: stream()

def stream(items: Iterable, fetch: Callable, threads: int = 12, ahead: int = 0) -> Iterator[tuple]:
    """Yield (item, fetch(item)) as each fetch finishes; the pool keeps fetching while the caller works.

    ahead > 0 caps how many finished-but-unconsumed results are held in memory (fetching pauses at the cap). With the
    default 0 there is no cap: use a fetch that caches and returns something small (a Path, a bool) for big jobs.
    """
    items = list(items)
    out: queue.Queue = queue.Queue()
    room = threading.Semaphore(ahead) if ahead else None
    it = iter(items)
    lock = threading.Lock()

    def worker():
        while True:
            with lock:
                try:
                    item = next(it)
                except StopIteration:
                    return
            if room:
                room.acquire()
            try:
                res = fetch(item)
            except Exception as e:  # noqa: BLE001  a failed fetch is a result, not a crash of the queue
                res = e
            out.put((item, res))

    pool = [threading.Thread(target=worker, daemon=True) for _ in range(max(1, min(threads, len(items))))]
    for t in pool:
        t.start()
    for _ in range(len(items)):
        item, res = out.get()
        if room:
            room.release()
        yield item, (None if isinstance(res, Exception) else res)


# ------------------------------------------------------------------ across tool calls: serve / enqueue / ready

def enqueue(cache: str | Path, urls: Iterable[str]) -> int:
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    urls = [u.strip() for u in urls if u and u.strip()]
    with open(cache / 'queue.txt', 'a', encoding='utf-8', newline='\n') as f:
        f.write(''.join(u + '\n' for u in urls))
    return len(urls)


def ready(cache: str | Path, since: int = 0) -> list[dict]:
    """Records of everything fetched so far (from line `since` of ready.jsonl)."""
    p = Path(cache) / 'ready.jsonl'
    if not p.exists():
        return []
    with open(p, encoding='utf-8') as f:
        lines = f.readlines()[since:]
    return [json.loads(l) for l in lines if l.endswith('\n')]


_robots: dict[str, dict] = {}
_robots_lock = threading.Lock()


def _rules(host: str, cache: Path) -> dict:
    with _robots_lock:
        if host not in _robots:
            try:
                _robots[host] = wayback.robots_rules(host, cache / 'robots')
            except Exception:  # noqa: BLE001  no robots.txt: no rules
                _robots[host] = {'crawl_delay': None, 'disallow': [], 'sitemaps': []}
        return _robots[host]


def _delay_get(url: str, host: str, delay: float, cache: Path) -> bytes | None:
    """One request under a stated Crawl-delay, spaced machine-wide through the host's shared state file."""
    hit = wayback._cached(cache, url)
    if hit is not None and hit.exists():
        return hit.read_bytes()
    for _ in range(4):
        def take(st):
            now = time.time()
            start = max(now, st['next'], st['pause_until'])
            st['next'] = start + delay
            return start - now, st
        wait = wayback._host_locked(host, take)
        if wait > 0:
            time.sleep(wait)
        code, body = wayback._curl(url, timeout=300)
        if code == 200:
            wayback._log(cache, url, code, len(body))
            tmp = hit.with_suffix('.part')
            tmp.write_bytes(body)
            os.replace(tmp, hit)
            return body
        if code in (403, 404, 410):
            wayback._log(cache, url, code, 0)
            return None
        if code in (429, 503):
            wayback._host_locked(host, lambda st: (None, {**st, 'pause_until': time.time() + 60}))
    return None


def fetch_one(url: str, cache: Path) -> dict:
    host = url.split('://', 1)[-1].split('/', 1)[0].lower()
    hit = wayback._cached(cache, url)
    if hit.exists():
        return {'url': url, 'ok': True, 'bytes': hit.stat().st_size, 'path': str(hit), 'cached': True}
    if host == 'web.archive.org':
        body = wayback.fetch(url, cache)
    else:
        r = _rules(host, cache)
        if not wayback.robots_allows(url, r.get('disallow') or []):
            return {'url': url, 'ok': False, 'why': 'robots'}
        delay = r.get('crawl_delay')
        body = _delay_get(url, host, float(delay), cache) if delay else wayback.host_get(url, cache)
    return {'url': url, 'ok': body is not None, 'bytes': len(body or b''), 'path': str(hit)}


def serve(cache: str | Path, threads: int = 12, idle_exit: float = 600.0) -> None:
    """Fetch every URL in CACHE/queue.txt (including lines appended later); exit after idle_exit s with nothing new."""
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    qf, rf = cache / 'queue.txt', cache / 'ready.jsonl'
    qf.touch()
    seen = {r['url'] for r in ready(cache)}
    out_lock = threading.Lock()
    delay_lanes: dict[str, threading.Lock] = {}

    def run(url):
        host = url.split('://', 1)[-1].split('/', 1)[0].lower()
        lane = None
        if host != 'web.archive.org' and (_rules(host, cache).get('crawl_delay')):
            lane = delay_lanes.setdefault(host, threading.Lock())  # one thread per Crawl-delay host
        if lane:
            with lane:
                rec = fetch_one(url, cache)
        else:
            rec = fetch_one(url, cache)
        with out_lock, open(rf, 'a', encoding='utf-8', newline='\n') as f:
            f.write(json.dumps(rec) + '\n')

    pos, last_new = 0, time.time()
    with cf.ThreadPoolExecutor(threads) as ex:
        pending: set = set()
        while True:
            with open(qf, encoding='utf-8') as f:
                f.seek(pos)
                chunk = f.read()
            complete = chunk[:chunk.rfind('\n') + 1] if '\n' in chunk else ''
            pos += len(complete.encode('utf-8'))
            new = [u for u in complete.splitlines() if u.strip() and u not in seen]
            for u in new:
                seen.add(u)
                pending.add(ex.submit(run, u))
            if new:
                last_new = time.time()
            pending = {p for p in pending if not p.done()}
            if not pending and time.time() - last_new > idle_exit:
                break
            time.sleep(0.5 if pending or new else 2.0)
    (cache / 'pipeline.exited').write_text(time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), encoding='utf-8')


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['serve'])
    ap.add_argument('cache')
    ap.add_argument('--threads', type=int, default=12)
    ap.add_argument('--idle-exit', type=float, default=600.0)
    a = ap.parse_args()
    serve(a.cache, a.threads, a.idle_exit)
