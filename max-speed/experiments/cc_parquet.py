"""Experiment 1: Common Crawl's columnar (Parquet) index, queried with DuckDB over HTTPS range reads.

    python cc_parquet.py footers CC-MAIN-2026-43 [more crawls]   # cache row-group surt ranges per crawl (one-off)
    python cc_parquet.py host malawilii.org 6                      # every capture of a host in the newest 6 crawls
    python cc_parquet.py naive malawilii.org CC-MAIN-2026-43       # let DuckDB scan all 300 files itself
    python cc_parquet.py idx malawilii.org 6                       # the same host through wayback.cc_captures (cluster.idx)

The table is globally sorted by url_surtkey (part-00000 .. part-00299, 4-5 row groups each, ~1.6 M rows per group), so a
host lives in one or two row groups. We read each file's footer once (300 small requests per crawl, cached as JSON in
LAB/ccpq/), then hand DuckDB only the files whose surt range overlaps the host, with a surt range filter so it skips
the other row groups. data.commoncrawl.org is a CDN (CloudFront) and is not under archive.org's rate.
"""
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import duckdb

LAB = Path(__file__).resolve().parent / '.tmp'
CCPQ = LAB / 'ccpq'
DATA = 'https://data.commoncrawl.org/'
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common')
import wayback  # noqa: E402


def con() -> duckdb.DuckDBPyConnection:
    c = duckdb.connect(config={'custom_user_agent': UA})
    c.sql('LOAD httpfs')
    c.sql("SET http_retries=3; SET threads=16; SET enable_progress_bar=false")
    return c


def paths(crawl: str, subset: str = 'warc') -> list[str]:
    import gzip
    import subprocess
    CCPQ.mkdir(parents=True, exist_ok=True)
    p = CCPQ / f'{crawl}.paths'
    if not p.exists():
        r = subprocess.run(['curl', '-gsS', '-A', UA, f'{DATA}crawl-data/{crawl}/cc-index-table.paths.gz'], capture_output=True)
        p.write_text(gzip.decompress(r.stdout).decode(), encoding='utf-8')
    return [l for l in p.read_text(encoding='utf-8').split() if f'/subset={subset}/' in l]


def footers(crawl: str, subset: str = 'warc') -> tuple[list, int, float]:
    """[(url, rg, min, max)] for every row group of the crawl's warc subset; (rows, requests, seconds)."""
    f = CCPQ / f'{crawl}.{subset}.footers.json'
    if f.exists():
        return json.loads(f.read_text(encoding='utf-8')), 0, 0.0
    ps = paths(crawl, subset)
    t = time.time()

    def one(path):
        c = con()
        u = DATA + path
        rows = c.sql(f"select row_group_id, stats_min_value, stats_max_value from parquet_metadata('{u}') "
                     f"where path_in_schema='url_surtkey'").fetchall()
        return [(u, rg, lo, hi) for rg, lo, hi in rows]
    with ThreadPoolExecutor(24) as ex:
        out = [r for rows in ex.map(one, ps) for r in rows]
    f.write_text(json.dumps(out), encoding='utf-8')
    return out, len(ps), time.time() - t


def host_key(host: str) -> str:
    return wayback._surt('http://' + host + '/')[:-1]  # 'org,malawilii)'


def crawls(n: int) -> list[str]:
    return sorted((p.name.split('.')[0] for p in wayback.CC_IDX_DIR.glob('CC-MAIN-*.cluster.idx')), reverse=True)[:n]


def host_query(host: str, crawl: str, c=None, subsets=('warc', 'crawldiagnostics')) -> tuple[list, int, float]:
    c = c or con()
    k = host_key(host)
    lo_k, hi_k = k, k + '\x7f'  # every surt that starts with 'org,malawilii)'
    rows = [r for sub in subsets for r in footers(crawl, sub)[0]]
    files = sorted({u for u, rg, lo, hi in rows if lo <= hi_k and hi >= lo_k})
    t = time.time()
    lst = ', '.join(f"'{u}'" for u in files)
    q = (f"select url, strftime(fetch_time, '%Y%m%d%H%M%S') as ts, fetch_status, content_mime_detected, content_digest, warc_filename, warc_record_offset, "
         f"warc_record_length, content_languages from read_parquet([{lst}]) "
         f"where url_surtkey >= '{lo_k}' and url_surtkey < '{hi_k}'")
    res = c.sql(q).fetchall()
    return res, len(files), time.time() - t


def main(argv):
    cmd = argv[0]
    if cmd == 'footers':
        for cr in argv[1:]:
            rows, n, s = footers(cr)
            print(json.dumps({'crawl': cr, 'row_groups': len(rows), 'requests': n, 'seconds': round(s, 1)}))
    elif cmd == 'host':
        host, n = argv[1], int(argv[2])
        c = con()
        tot, t0 = 0, time.time()
        for cr in crawls(n):
            nreq = fs = 0
            for sub in ('warc', 'crawldiagnostics'):
                _, a, b = footers(cr, sub)
                nreq, fs = nreq + a, fs + b
            res, nf, s = host_query(host, cr, c)
            tot += len(res)
            print(json.dumps({'crawl': cr, 'footer_requests': nreq, 'footer_s': round(fs, 1), 'files': nf,
                              'records': len(res), 'query_s': round(s, 2),
                              'statuses': sorted({r[2] for r in res})[:6]}))
        print(json.dumps({'host': host, 'crawls': n, 'records': tot, 'total_s': round(time.time() - t0, 1)}))
    elif cmd == 'naive':
        host, cr = argv[1], argv[2]
        c = con()
        k = host_key(host)
        t = time.time()
        # data.commoncrawl.org has no S3 listing over HTTPS, so glob is impossible; give DuckDB the 300 explicit URLs.
        lst = ', '.join(f"'{DATA}{p}'" for p in paths(cr))
        res = c.sql(f"select count(*) from read_parquet([{lst}]) where url_surtkey >= '{k}' and url_surtkey < '{k}\x7f'").fetchall()
        print(json.dumps({'crawl': cr, 'records': res[0][0], 'seconds': round(time.time() - t, 1)}))
    elif cmd == 'idx':
        host, n = argv[1], int(argv[2])
        tot, t0 = 0, time.time()
        for cr in crawls(n):
            t = time.time()
            recs = wayback._cc_captures_files('http://' + host + '/', cr, 'prefix') or []
            tot += len(recs)
            print(json.dumps({'crawl': cr, 'records': len(recs), 'seconds': round(time.time() - t, 2)}))
        print(json.dumps({'host': host, 'crawls': n, 'records': tot, 'total_s': round(time.time() - t0, 1)}))


if __name__ == '__main__':
    main(sys.argv[1:])
