"""Proposal: host_get with pushback counted only when the host pushes back (agent C, 2026-10-29).

wayback.host_get halves a host's machine-wide rate and pauses everyone for 30 s on 429, 503 OR any curl failure
(code 0), and curl runs with a fixed --max-time 90. On a slow-but-healthy host serving big files (Greek FEK PDFs,
2-11 MB at ~0.5 MB/s for the whole machine) 16 threads split the bandwidth 16 ways, every download passes 90 s, curl
kills it (the bytes are thrown away), host_get calls that pushback, halves, pauses, and retries the same download.

This version changes three things and nothing else (same state files, same cache and log layout):
1. curl aborts on a STALL, not on total time: --speed-limit 1024 --speed-time STALL_S (default 60 s) plus a
   --connect-timeout 30 and a generous --max-time ceiling (default 1800 s). A 10 MB file at 30 KB/s completes.
2. Pushback is only what a host says or does to refuse us: HTTP 429 / 503 (honouring Retry-After), a refused or
   reset connection (curl 7, 52, 55, 56), a TLS handshake drop (35), or no first byte before the stall limit. A
   transfer that was receiving bytes and then ran past the ceiling is "slow", not pushback: no halving, no pause.
3. The rate still climbs only on success, and each success is credited once (not once per try).

Use exactly like host_get:  body = host_get2(url, cache)
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common')
import wayback  # noqa: E402

STALL_S, CONNECT_S, CEILING_S = 60, 30, 1800
PUSHBACK_EXIT = {7, 35, 52, 55, 56}   # refused, TLS drop, empty reply, send fail, reset
LOG: list[dict] = []                  # per-try outcomes, for the experiments


def _curl2(url: str, stall: int = STALL_S, ceiling: int = CEILING_S) -> dict:
    fd, tmp = tempfile.mkstemp()
    os.close(fd)
    hdr = tmp + '.h'
    try:
        out = subprocess.run(['curl', '-gsS', '-L', '--compressed', '-A', wayback.UA,
                              '--connect-timeout', str(CONNECT_S), '--speed-limit', '1024', '--speed-time', str(stall),
                              '--max-time', str(ceiling), '-D', hdr, '-o', tmp,
                              '-w', '%{http_code} %{size_download} %{time_starttransfer} %{time_total}', url],
                             capture_output=True, text=True)
        parts = (out.stdout.strip() or '0 0 0 0').split()
        code, size, ttfb, total = int(parts[0]), int(parts[1]), float(parts[2]), float(parts[3])
        retry_after = 0.0
        try:
            for line in Path(hdr).read_text(encoding='latin-1').splitlines():
                if line.lower().startswith('retry-after:'):
                    v = line.split(':', 1)[1].strip()
                    retry_after = float(v) if v.isdigit() else 60.0
        except OSError:
            pass
        body = Path(tmp).read_bytes() if out.returncode == 0 and code else b''
        return {'code': code if out.returncode == 0 else 0, 'exit': out.returncode, 'size': size, 'ttfb': ttfb,
                'total': total, 'retry_after': retry_after, 'body': body}
    finally:
        Path(tmp).unlink(missing_ok=True)
        Path(hdr).unlink(missing_ok=True)


def classify(r: dict) -> str:
    """'ok', 'gone' (403/404/410), 'pushback', 'slow' (bytes were arriving; no halving) or 'error'."""
    if r['exit'] == 0 and r['code'] == 200:
        return 'ok'
    if r['exit'] == 0 and r['code'] in (403, 404, 410):
        return 'gone'
    if r['exit'] == 0 and r['code'] in (429, 503):
        return 'pushback'
    if r['exit'] in PUSHBACK_EXIT:
        return 'pushback'
    if r['exit'] == 28:                       # stall limit or ceiling
        return 'slow' if r['size'] > 0 else 'pushback'
    return 'error'                            # DNS, 5xx other than 503, ...: retry without touching the rate


def host_get2(url: str, cache: Path | str | None = None, tries: int = 5, stall: int = STALL_S,
              ceiling: int = CEILING_S) -> bytes | None:
    host = url.split('://', 1)[-1].split('/', 1)[0].lower()
    cache = Path(cache) if cache else None
    hit = wayback._cached(cache, url)
    if hit is not None and hit.exists():
        return hit.read_bytes()
    for _ in range(tries):
        def take(st):
            now = time.time()
            start = max(now, st['next'], st['pause_until'])
            st['next'] = start + 1.0 / st['rate']
            return start - now, st
        wait = wayback._host_locked(host, take)
        if wait > 0:
            time.sleep(wait)
        r = _curl2(url, stall, ceiling)
        kind = classify(r)
        LOG.append({'url': url, 'kind': kind, 'code': r['code'], 'exit': r['exit'], 'size': r['size'],
                    'total': round(r['total'], 2), 't': time.time()})

        def upd(st):
            if kind == 'pushback':
                st['rate'] = max(wayback.HOST_MIN, st['rate'] / 2)
                st['pause_until'] = time.time() + max(wayback.HOST_BACKOFF, r['retry_after'])
                st['throttled'] += 1
            elif kind in ('ok', 'gone'):
                st['rate'] = min(wayback.HOST_MAX, st['rate'] + wayback.HOST_STEP)
                st['ok'] += 1
            return None, st
        if kind != 'slow' and kind != 'error':
            wayback._host_locked(host, upd)
        if kind == 'ok':
            wayback._log(cache, url, 200, len(r['body']))
            if hit is not None:
                tmp = hit.with_suffix('.part')
                tmp.write_bytes(r['body'])
                os.replace(tmp, hit)
            return r['body']
        if kind == 'gone':
            wayback._log(cache, url, r['code'], 0)
            return None
    return None
