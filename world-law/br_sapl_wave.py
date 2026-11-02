"""Private (never published). The one fetcher of the SAPL municipal wave (gitlaw-scraper-dell, 2026-11-01, municipal
tier via global-law-main-composer).

    python -u -X utf8 scripts/world-law/br_sapl_wave.py [--laws N] [--laws-max M] <sapl host>=<city folder> ...

One process, one request at a time overall (>= 3.2 s between any two requests), round-robin over the hosts; each host
>= 61 s between its own requests (Interlegis SAPL robots: Crawl-delay 60). Per host: first the Lei Orgânica records
and Texto Articulado views (br_sapl_multi.work), then the municipal laws newest-first: the API lists of the "Lei" and
"Lei Complementar" types (page_size 100) and the texto_integral file of each of the newest N records, then
N+50, ... up to M (one more part of about 50 records per round).
Writes <folder>/.cache/sapl/laws-index.json. Cache and request log as br_city_get.

Stop: create scripts/world-law/.br-cities/STOP-wave (the driver exits before its next request). A host stops for
good on 403/429/5xx/challenge/timeout (STOP file in its cache, br_city_get). Waits while cpu5 > 90 or ram > 85.
Daily cap: at most DAILY_MAX (5,000) requests per host per UTC day (counted from its requests.jsonl); a host that
reaches it is paused until the next UTC day.
"""
import json, os, re, sys, time
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from br_city_get import Stop  # noqa: E402
from br_sapl_multi import work  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'gitlaw_common'))
import fetch_scheduler  # noqa: E402  (2026-11-02: shared scheduler, cache, registry and feed)

SCRIPTS = Path(__file__).resolve().parents[1]
STOPF = Path(__file__).resolve().parent / '.br-cities' / 'STOP-wave'
CPU = Path(os.environ.get('LOCALAPPDATA', '')) / 'gitlaw-cpu.log'
GAP = 3.2
DAILY_MAX = 5000  # coordinator rule 2026-11-01: about 5,000 requests per host per UTC day, then pause to the next day


def today_count(H):
    """Network requests this host made today (UTC), from its request log (every request is logged by br_city_get)."""
    day = time.strftime('%Y-%m-%d', time.gmtime())
    try:
        with open(H.dir / 'requests.jsonl', encoding='utf-8') as f:
            return sum(1 for l in f if f'"at": "{day}T' in l)
    except OSError:
        return 0


def next_utc_day():
    t = time.gmtime()
    return time.mktime((t.tm_year, t.tm_mon, t.tm_mday + 1, 0, 0, 5, 0, 0, 0)) - time.mktime(time.gmtime(0))


def busy():
    try:
        l = CPU.read_text(encoding='utf-8', errors='replace').strip().splitlines()[-1]
        c = int(re.search(r'cpu5=(\d+)', l).group(1))
        r = int(re.search(r'ram=(\d+)', l).group(1))
        return c > 90 or r > 85
    except Exception:
        return False


def type_ids(tipos):
    lei = lc = None
    for t in tipos:
        lex = (t.get('equivalente_lexml') or '').strip().lower()
        sig = (t.get('sigla') or '').strip().upper()
        desc = (t.get('descricao') or '').strip().lower()
        if lei is None and (lex == 'lei' or sig == 'LEI'
                            or desc in ('lei', 'lei ordinária', 'lei ordinaria', 'lei municipal')):
            lei = t['id']
        if lc is None and (lex == 'lei.complementar' or desc in ('lei complementar', 'lei complementar municipal')):
            lc = t['id']
    return [x for x in (lei, lc) if x is not None]


def key(r):
    return (r.get('data') or f"{r.get('ano') or 0}-00-00", int(r.get('ano') or 0),
            int(re.sub(r'\D', '', str(r.get('numero') or '')) or 0))


def laws(H, host, folder, n):
    """Generator: yields after each network request."""
    cache = SCRIPTS / folder / '.cache' / 'sapl'
    base = f'https://{host}'
    seen = [H.last]

    def fresh():
        f = H.last != seen[0]
        seen[0] = H.last
        return f

    tipos = json.loads(H.get(f'{base}/api/norma/tiponormajuridica/?page_size=100'))['results']
    ids = type_ids(tipos)
    lists = {}  # tipo -> {'pages': fetched count, 'total': total_pages, 'recs': [...]}
    for t in ids:
        b = H.get(f'{base}/api/norma/normajuridica/?tipo={t}&page_size=100&page=1')
        if fresh():
            yield
        d = json.loads(b)
        lists[t] = {'pages': 1, 'total': d['pagination']['total_pages'], 'recs': d['results']}
        ds = [r.get('data') or '' for r in d['results'] if r.get('data')]
        if ds and ds != sorted(ds, reverse=True):
            print(host, 'tipo', t, 'list is not newest-first', ds[:3], ds[-3:], flush=True)
    while True:
        allr = sorted((r for v in lists.values() for r in v['recs']), key=key, reverse=True)
        cut = key(allr[n - 1]) if len(allr) >= n else None
        more = [t for t, v in lists.items() if v['pages'] < v['total'] and (cut is None or key(v['recs'][-1]) >= cut)]
        if not more:
            break
        t = more[0]
        v = lists[t]
        b = H.get(f'{base}/api/norma/normajuridica/?tipo={t}&page_size=100&page={v["pages"] + 1}')
        if fresh():
            yield
        v['recs'] += json.loads(b)['results']
        v['pages'] += 1
    top = allr[:n]
    idx = {'host': host, 'types': ids, 'n': n, 'records': top,
           'totals': {str(t): v['total'] for t, v in lists.items()}}
    (cache / 'laws-index.json').write_text(json.dumps(idx, ensure_ascii=False, indent=0), encoding='utf-8')
    got = 0
    for r in top:
        u = r.get('texto_integral')
        if not u:
            continue
        if not u.startswith('http'):
            u = base + u
        u = u.replace('http://', 'https://', 1)
        if urlparse(u).netloc != host:
            print(host, 'texto_integral on another host, not fetched:', u, flush=True)
            continue
        try:
            H.get(u)
        except Stop:
            raise
        got += 1
        if fresh():
            yield
    print(host, 'laws done', len(top), 'records,', got, 'files', flush=True)


def city(host, folder, n, do_lom, nmax):
    g = work(host, folder)
    H = next(g)
    fetch_scheduler.adopt(H, caller='br_sapl_wave')
    yield H
    if do_lom:
        for _ in g:
            yield H
    for k in range(n, max(n, nmax) + 1, 50):  # the newest 50, then 50 more each round, up to nmax
        for _ in laws(H, host, folder, k):
            yield H


def main():
    args = sys.argv[1:]
    n, do_lom, nmax = 50, True, 0
    if args[:1] == ['--laws']:
        n, args = int(args[1]), args[2:]
    if args[:1] == ['--laws-max']:
        nmax, args = int(args[1]), args[2:]
    if args[:1] == ['--no-lom']:
        do_lom, args = False, args[1:]
    jobs = []
    for a in args:
        host, folder = a.split('=')
        g = city(host, folder, n, do_lom, nmax)
        jobs.append([host, g, next(g)])
    last = 0.0
    while jobs:
        if STOPF.exists():
            print('STOP-wave file found: exiting', flush=True)
            return
        while busy():
            time.sleep(60)
        jobs.sort(key=lambda j: j[2].last + j[2].delay)
        j = jobs[0]
        wait = max(j[2].last + j[2].delay - time.time(), last + GAP - time.time())
        if wait > 0:
            time.sleep(min(wait, 60))  # in steps, so STOP-wave is seen within a minute
            if wait > 60:
                continue
        n_today = today_count(j[2])
        if n_today >= DAILY_MAX:
            nxt = next_utc_day()
            print(j[0], f'daily cap {DAILY_MAX} reached ({n_today} requests today): paused until '
                        f'{time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(nxt))}', flush=True)
            j[2].last = nxt - j[2].delay  # the host's next turn is the next UTC day
            continue
        try:
            next(j[1])
        except StopIteration:
            jobs.remove(j)
        except (Stop, Exception) as e:
            print(j[0], 'STOP', type(e).__name__, str(e)[:200], flush=True)
            jobs.remove(j)
        last = time.time()
    print('all hosts done', flush=True)


if __name__ == '__main__':
    main()
