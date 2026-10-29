"""Fetch Korean statutes, every in-force version, from the National Law Information Center Open API.

Source: law.go.kr DRF Open API (open.law.go.kr), Ministry of Government Legislation.
  - lawSearch.do?target=eflaw&query=<name>   lists every version of a law by in-force date
    (법령일련번호 MST, 시행일자 efYd, 공포일자, 공포번호, 제개정구분)
  - lawService.do?target=eflaw&MST=<mst>&efYd=<yyyymmdd>&type=XML   the full text in force from that date

Everything is cached under .cache/ by the sha256 of the URL, fetched with curl (Python TLS fails on
this machine), at most 3 requests a second, and logged to .cache/requests.jsonl. Resumable.

    python -X utf8 fetch.py            # every act in acts.json
    python -X utf8 fetch.py minbeop    # one act
"""
import hashlib, json, os, subprocess, sys, threading, time, urllib.parse
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, '.cache')
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
BASE = 'https://www.law.go.kr/DRF/'
OC = 'test'   # the API's public demonstration user id
_lock = threading.Lock()
_last = [0.0]
RATE = 1 / 3.0


def path_for(url):
    return os.path.join(CACHE, hashlib.sha256(url.encode()).hexdigest() + '.bin')


def get(url, check=None):
    p = path_for(url)
    if os.path.exists(p) and os.path.getsize(p) > 0:
        return open(p, 'rb').read()
    for attempt in range(5):
        with _lock:
            wait = _last[0] + RATE - time.time()
            if wait > 0:
                time.sleep(wait)
            _last[0] = time.time()
        t0 = time.time()
        r = subprocess.run(['curl', '-sS', '--compressed', '-A', UA, '-m', '180', '-w', '%{http_code}', '-o', p + '.part', url],
                           capture_output=True, text=True)
        code = r.stdout.strip()
        size = os.path.getsize(p + '.part') if os.path.exists(p + '.part') else 0
        with _lock:
            with open(os.path.join(CACHE, 'requests.jsonl'), 'a', encoding='utf-8') as f:
                f.write(json.dumps({'url': url, 'status': code, 'bytes': size, 'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                                    'secs': round(time.time() - t0, 2), 'file': os.path.basename(p)}) + '\n')
        if code == '200' and size > 0:
            body = open(p + '.part', 'rb').read()
            if check is None or check(body):
                os.replace(p + '.part', p)
                return body
        if code in ('429', '503'):
            time.sleep(60)
        else:
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f'failed: {url} ({code})')


def search_url(query, page):
    q = urllib.parse.urlencode({'OC': OC, 'target': 'eflaw', 'type': 'JSON', 'query': query, 'display': 100, 'page': page})
    return BASE + 'lawSearch.do?' + q


def version_url(mst, efyd):
    return BASE + f'lawService.do?OC={OC}&target=eflaw&MST={mst}&efYd={efyd}&type=XML'


def resolve_id(act):
    """The 법령ID of the law whose current name is exactly act['name'] (spaces ignored)."""
    if act.get('id'):
        return act['id']
    d = json.loads(get(search_url(act['query'], 1), check=lambda b: b.lstrip().startswith(b'{')))['LawSearch']
    laws = d.get('law') or []
    if isinstance(laws, dict):
        laws = [laws]
    ids = sorted({l['법령ID'] for l in laws if l['법령명한글'].replace(' ', '') == act['name'].replace(' ', '')})
    if len(ids) != 1:
        raise RuntimeError(f"{act['slug']}: {len(ids)} ids for {act['name']}: {ids}")
    act['id'] = ids[0]
    return ids[0]


def listing(act):
    """Every version of one act (matched by 법령ID) from the eflaw search, all pages."""
    resolve_id(act)
    out, page = [], 1
    while True:
        d = json.loads(get(search_url(act['query'], page), check=lambda b: b.lstrip().startswith(b'{')))['LawSearch']
        laws = d.get('law') or []
        if isinstance(laws, dict):
            laws = [laws]
        out += [l for l in laws if l['법령ID'] == act['id']]
        if page * 100 >= int(d['totalCnt']):
            return out
        page += 1


def ok_xml(b):
    return b'<\xec\xa1\xb0\xeb\xac\xb8' in b[:200000] or '<기본정보>'.encode() in b[:5000]


def fetch_act(act):
    vs = listing(act)
    jobs = sorted({(v['법령일련번호'], v['시행일자']) for v in vs}, key=lambda x: x[1])
    with ThreadPoolExecutor(3) as ex:
        list(ex.map(lambda j: get(version_url(*j), check=ok_xml), jobs))
    print(f"{act['slug']}: {len(jobs)} versions", flush=True)
    return vs


def main():
    os.makedirs(CACHE, exist_ok=True)
    acts = json.load(open(os.path.join(HERE, 'acts.json'), encoding='utf-8'))
    want = set(sys.argv[1:])
    for act in acts:
        if want and act['slug'] not in want:
            continue
        try:
            fetch_act(act)
        except Exception as e:  # keep going: one act failing must not stop the rest
            print(f"{act['slug']}: FAILED {e}", flush=True)


if __name__ == '__main__':
    main()
