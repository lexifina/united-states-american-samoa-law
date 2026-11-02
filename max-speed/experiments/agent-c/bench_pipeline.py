"""Pipelined fetch+parse against fetch-then-parse, on a harmless public host (raw.githubusercontent.com, which
serves public git data with no Crawl-delay and has run at host_get's 25/s cap with 0 pushback all day).

Corpus: Justice Canada's consolidated federal Acts (github.com/justicecanada/laws-lois-xml, OGL-Canada), English
Acts under 400 KB. The documents are dealt into three equal, size-balanced sets (one per mode) so no mode reads
another's cache or a warmer CDN. Parse = real work: ElementTree parse, every Section's text, normalised and hashed,
one file written per Act.

Modes:
  serial     one fetch, then its parse, then the next (what an agent does fetching a few files per step)
  batch      fetch all with a 12-thread pool, then parse all (fetch-then-parse)
  pipelined  pipeline.stream(): 12 fetch threads run while the main thread parses whatever has landed
  serve      pipeline.py serve in its own process (12 threads) fed by enqueue(); this process parses ready()
             (uses the serial set; run it without serial, or the cache is cold anyway since each run gets its own)

    python bench_pipeline.py [--per-mode 150]      # writes bench_pipeline.json
"""
from __future__ import annotations

import concurrent.futures as cf
import hashlib
import json
import re
import shutil
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pipeline  # noqa: E402
import wayback  # noqa: E402

REPO = 'justicecanada/laws-lois-xml'
RAW = f'https://raw.githubusercontent.com/{REPO}/main/'


def listing(cache: Path) -> list[tuple[str, int]]:
    raw = wayback.host_get(f'https://api.github.com/repos/{REPO}/git/trees/main?recursive=1', cache)
    tree = json.loads(raw)['tree']
    return [(t['path'], t['size']) for t in tree
            if t['type'] == 'blob' and t['path'].startswith('eng/acts/') and t['path'].endswith('.xml')
            and t.get('size', 0) < 400_000]


WORK = 1   # parse repeats: 1 = this XML parse; higher stands in for heavier parsing (PDF text, HTML clean-up)


def parse(body: bytes, out: Path, name: str) -> int:
    for _ in range(WORK - 1):
        for sec in ET.fromstring(body).iter('Section'):
            re.sub(r'\s+', ' ', ''.join(sec.itertext()))
    root = ET.fromstring(body)
    parts = []
    for sec in root.iter('Section'):
        txt = re.sub(r'\s+', ' ', ''.join(sec.itertext())).strip()
        parts.append(hashlib.sha256(txt.encode('utf-8')).hexdigest()[:12] + ' ' + txt)
    (out / (name.replace('/', '_') + '.txt')).write_text('\n'.join(parts), encoding='utf-8', newline='\n')
    return len(parts)


def run(mode: str, docs: list[tuple[str, int]], threads: int) -> dict:
    cache = Path(tempfile.mkdtemp(prefix=f'pipe-{mode}-'))
    out = Path(tempfile.mkdtemp(prefix=f'pipe-out-{mode}-'))
    urls = [RAW + p for p, _ in docs]
    fetch = lambda u: wayback.host_get(u, cache)  # noqa: E731
    parse_s = 0.0
    sections = 0
    first_parse_at = None
    t0 = time.time()

    def do_parse(u, body):
        nonlocal parse_s, sections, first_parse_at
        if first_parse_at is None:
            first_parse_at = time.time() - t0
        a = time.time()
        sections += parse(body, out, u.rsplit('/', 1)[-1])
        parse_s += time.time() - a

    got = 0
    if mode == 'serial':
        for u in urls:
            b = fetch(u)
            if b:
                got += 1
                do_parse(u, b)
        fetch_done = None
    elif mode == 'batch':
        with cf.ThreadPoolExecutor(threads) as ex:
            bodies = list(ex.map(fetch, urls))
        fetch_done = time.time() - t0
        for u, b in zip(urls, bodies):
            if b:
                got += 1
                do_parse(u, b)
    elif mode == 'serve':
        import subprocess
        proc = subprocess.Popen([sys.executable, '-X', 'utf8', str(HERE / 'pipeline.py'), 'serve', str(cache),
                                 '--threads', str(threads), '--idle-exit', '3'])
        pipeline.enqueue(cache, urls)
        n = 0
        fetch_done = None
        while n < len(urls):
            recs = pipeline.ready(cache, since=n)
            if not recs:
                time.sleep(0.05)
                continue
            n += len(recs)
            for r in recs:
                if r.get('ok'):
                    got += 1
                    do_parse(r['url'], Path(r['path']).read_bytes())
            if n >= len(urls):
                fetch_done = time.time() - t0
        proc.wait(timeout=60)
    else:
        last_fetch = 0.0
        for u, b in pipeline.stream(urls, fetch, threads=threads):
            last_fetch = time.time() - t0
            if b:
                got += 1
                do_parse(u, b)
        fetch_done = last_fetch
    wall = time.time() - t0
    mb = sum(s for _, s in docs) / 1e6
    shutil.rmtree(cache, ignore_errors=True)
    shutil.rmtree(out, ignore_errors=True)
    return {'mode': mode, 'docs': len(docs), 'fetched': got, 'MB': round(mb, 2), 'sections': sections,
            'wall_s': round(wall, 1), 'fetch_done_s': None if fetch_done is None else round(fetch_done, 1),
            'parse_cpu_s': round(parse_s, 1), 'first_parse_at_s': round(first_parse_at or 0, 2),
            'docs_per_min': round(got / wall * 60, 1)}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--per-mode', type=int, default=150)
    ap.add_argument('--threads', type=int, default=12)
    ap.add_argument('--modes', default='batch,pipelined,serial')
    ap.add_argument('--work', type=int, default=1)
    ap.add_argument('--out', default='bench_pipeline.json')
    a = ap.parse_args()
    global WORK
    WORK = a.work
    lcache = Path(tempfile.gettempdir()) / 'agent-c-listing'
    files = sorted(listing(lcache), key=lambda x: x[1])
    modes = a.modes.split(',')
    step = max(1, len(files) // (a.per_mode * 3))
    pick = files[::step][: a.per_mode * 3]
    sets = {m: pick[i::3] for i, m in enumerate(['batch', 'pipelined', 'serial'])}
    sets['serve'] = sets['serial']
    res = {'host': 'raw.githubusercontent.com', 'corpus': REPO, 'threads': a.threads, 'parse_work': a.work,
           'host_state_before': wayback.host_status('raw.githubusercontent.com'), 'runs': []}
    for m in modes:
        r = run(m, sets[m], a.threads)
        res['runs'].append(r)
        print(r, flush=True)
    res['host_state_after'] = wayback.host_status('raw.githubusercontent.com')
    (HERE / a.out).write_text(json.dumps(res, indent=1), encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
