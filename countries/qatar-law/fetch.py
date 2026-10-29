"""Fetch Qatar acts from Al Meezan's public API (api.moj.gov.qa/api/v1), the API behind almeezan.qa.

Cache: .cache/<sha256(url)> via curl, logged to .cache/requests.jsonl. Resumable; at most 3 requests a second.
Usage: python -X utf8 fetch.py            (fetches every act in acts.json, every article history, every amending law)
"""
import hashlib, json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, '.cache')
API = 'https://api.moj.gov.qa/api/v1'
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
_last = [0.0]


def path_for(url):
    return os.path.join(CACHE, hashlib.sha256(url.encode()).hexdigest())


def get(url, lang='ar', offline=False):
    """Return cached bytes for url (Accept-Language: lang is part of the cache key when not 'ar')."""
    key = url if lang == 'ar' else url + '#lang=' + lang
    p = path_for(key)
    if os.path.exists(p):
        return open(p, 'rb').read()
    if offline:
        raise FileNotFoundError(url)
    os.makedirs(CACHE, exist_ok=True)
    wait = _last[0] + 0.34 - time.time()
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()
    for attempt in range(4):
        r = subprocess.run(['curl', '-sS', '--compressed', '-f', '-A', UA, '-H', 'Accept-Language: ' + lang,
                            '-H', 'Accept: application/json', '-o', p + '.part', '-w', '%{http_code}', url],
                           capture_output=True, text=True)
        code = r.stdout.strip()
        if r.returncode == 0:
            break
        if code in ('429', '503'):
            time.sleep(60)
        else:
            time.sleep(3)
    with open(os.path.join(CACHE, 'requests.jsonl'), 'a', encoding='utf-8') as f:
        f.write(json.dumps({'url': url, 'lang': lang, 'status': code, 'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}) + '\n')
    if r.returncode != 0:
        raise RuntimeError(f'{url}: {code} {r.stderr.strip()}')
    os.replace(p + '.part', p)
    return open(p, 'rb').read()


def api(path, offline=False):
    return json.loads(get(API + path, offline=offline))['data']


def detail_by_key(typ, year, number, offline=False):
    return api(f'/Legislation/details-by-key?number={number}&year={year}&typeCode={typ}&sourceCode=general', offline)


def detail(lid, offline=False):
    return api(f'/Legislation/{lid}', offline)


def mada(lid, mid, offline=False):
    return api(f'/Legislation/{lid}/mada/{mid}', offline)


def articles(d):
    out = []
    def walk(secs, path):
        for s in secs:
            for a in s.get('almawad') or []:
                out.append((path + [s['title']], a))
            walk(s.get('sections') or [], path + [s['title']])
    walk(d['sections'], [])
    return out


def lookup(lid, offline=False):
    return api(f'/Legislation/{lid}/almawad-lookup?pageNumber=1&pageSize=1000', offline)['data']


def all_articles(d, offline=False):
    """Every published article: the tree's own, plus any the tree omits (fetched one by one, path unknown)."""
    arts = articles(d)
    have = {a['id'] for _, a in arts}
    for x in lookup(d['id'], offline):
        if x['id'] not in have:
            arts.append((None, mada(d['id'], x['id'], offline)))
    return arts


def act_detail(act, offline=False):
    if act.get('id'):
        return detail(act['id'], offline)
    return detail_by_key(act['type'], act['year'], act['number'], offline)


def main():
    acts = json.load(open(os.path.join(HERE, 'acts.json'), encoding='utf-8'))
    for act in acts:
        d = act_detail(act)
        arts = all_articles(d)
        hist = [a for _, a in arts if a.get('hasHistory') or a.get('hasPreviousVersion')]
        print(act['slug'], d['title'], len(arts), 'articles,', len(hist), 'with history', flush=True)
        for sub in ('related-legislations-subsequent', 'related-legislations-previous'):
            try:
                api(f"/Legislation/{d['id']}/{sub}")
            except Exception as e:
                print('  warn', sub, e)
        with ThreadPoolExecutor(3) as ex:
            chains = list(ex.map(lambda a: mada(d['id'], a['id']), hist))
        laws = set()
        for c in chains:
            for r in c.get('relatedAlmawad') or []:
                for k in ('toLegislationId', 'parentLegislationId'):
                    if r.get(k):
                        laws.add(r[k])
        for lid in sorted(laws):
            detail(lid)
        print('  amending laws:', len(laws), flush=True)


if __name__ == '__main__':
    main()
