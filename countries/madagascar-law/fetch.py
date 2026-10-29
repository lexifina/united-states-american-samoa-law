"""CNLEGIS (cnlegis.gov.mg, Direction du CNLEGIS, Secrétariat Général du Gouvernement, Primature): fetch layer.

CNLEGIS serves each text's official French HTML (`html_fichier_fr`) inside the JSON of its search endpoints. A search is
two POSTs in one cookie session: the search form (sets the query in the session), then the data endpoint (returns the
`aaData` rows). Each answer is cached under .cache/ named by the sha256 of the request (URL + fields), logged to
.cache/requests.jsonl, through curl, at most one request per second, resumable (a cached answer is never fetched again).

    python -X utf8 fetch.py                 # fetch every search parse.py needs (SEARCHES below)
    python -X utf8 fetch.py mots "Code pénal" 0,100   # one ad hoc search, printed as a table (probing)

robots.txt (checked 2026-10-28): `User-agent: GPTBot / Disallow: /`, `User-agent: * / Disallow:`.
"""
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
BASE = 'https://cnlegis.gov.mg/'
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
KINDS = {  # (form endpoint, data endpoint) per search kind
    'mots': ('page_find_direct_mots/', 'page_data_result_direct_mots/'),
    'num': ('page_num_find_direct/', 'page_num_data_find_direct/'),
}
# Every search the build reads (parse.py imports this list).
SEARCHES = [
    ('mots', 'Constitution de la', '0,300'),   # LC 98-001 (34738), LC 2007-001 (39326), Constitution 2010 (51445)
    ('num', '2009-001', '0,50'),               # LC 2009-001 (40058)
    ('num', '2014-038', '0,50'),               # Loi 2014-038, personal data
    ('num', '2014-006', '0,50'),               # Loi 2014-006, cybercriminalité
    ('num', '2016-031', '0,50'),               # Loi 2016-031, amends Loi 2014-006
    ('mots', 'Code du travail', '0,100'),      # Loi 2003-044 (38022), Loi 2024-014 (55500)
]
_last = [0.0]


def _curl(args: list) -> bytes:
    for attempt in range(4):
        wait = 1.05 - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        r = subprocess.run(['curl', '-sS', '-f', '--compressed', '-m', '180', '-A', UA, *args], capture_output=True)
        _last[0] = time.time()
        if r.returncode == 0:
            return r.stdout
        time.sleep(3 * (attempt + 1))
    raise SystemExit(f'curl failed: {args[-1]}: {r.stderr.decode(errors="replace")}')


def cache_name(kind: str, query: str, limit: str) -> Path:
    form, data = KINDS[kind]
    key = f'POST {BASE + form} txt_recherche={query} | POST {BASE + data} var_pg_limit={limit}'
    return CACHE / (hashlib.sha256(key.encode('utf-8')).hexdigest() + '.json')


def search(kind: str, query: str, limit: str, offline: bool = False) -> list:
    """aaData rows of one CNLEGIS search, cached."""
    f = cache_name(kind, query, limit)
    if not f.exists():
        if offline:
            raise SystemExit(f'offline: search {kind} {query!r} {limit} is not in the cache; run fetch.py')
        CACHE.mkdir(exist_ok=True)
        (CACHE / '.gitignore').write_text('*\n', encoding='utf-8', newline='\n')
        form, data = KINDS[kind]
        with tempfile.TemporaryDirectory() as td:
            jar = str(Path(td) / 'jar.txt')
            _curl(['-c', jar, '-b', jar, '-o', str(Path(td) / 'form.html'), '--data-urlencode',
                   f'txt_recherche={query}', BASE + form])
            body = _curl(['-b', jar, '--data-urlencode', f'var_pg_limit={limit}', BASE + data])
        json.loads(body.decode('utf-8'))  # must be JSON
        tmp = f.with_suffix('.tmp')
        tmp.write_bytes(body)
        tmp.replace(f)
        with (CACHE / 'requests.jsonl').open('a', encoding='utf-8', newline='\n') as fh:
            fh.write(json.dumps({'at': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                                 'kind': kind, 'query': query, 'limit': limit, 'file': f.name, 'requests': 2,
                                 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()},
                                ensure_ascii=False) + '\n')
    return json.loads(f.read_bytes().decode('utf-8'))['aaData']


def get(url: str, offline: bool = False) -> bytes:
    """One GET (a CNLEGIS upload, e.g. a PDF), cached by the sha256 of the URL."""
    f = CACHE / hashlib.sha256(url.encode('utf-8')).hexdigest()
    if not f.exists():
        if offline:
            raise SystemExit(f'offline: {url} is not in the cache; run fetch.py')
        CACHE.mkdir(exist_ok=True)
        body = _curl([url])
        tmp = f.with_suffix('.tmp')
        tmp.write_bytes(body)
        tmp.replace(f)
        with (CACHE / 'requests.jsonl').open('a', encoding='utf-8', newline='\n') as fh:
            fh.write(json.dumps({'at': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                                 'url': url, 'file': f.name, 'requests': 1, 'bytes': len(body),
                                 'sha256': hashlib.sha256(body).hexdigest()}) + '\n')
    return f.read_bytes()


GETS = [
    'https://cnlegis.gov.mg/uploads/O62-041-VF.pdf',   # Ordonnance n° 62-041: the default in-force rule
    'https://cnlegis.gov.mg/uploads/L2024-014-VF.pdf',  # Loi n° 2024-014 portant Code du travail (text layer)
]


def sha256_of(kind: str, query: str, limit: str) -> str:
    return hashlib.sha256(cache_name(kind, query, limit).read_bytes()).hexdigest()


def requests_made() -> int:
    p = CACHE / 'requests.jsonl'
    return sum(json.loads(l)['requests'] for l in p.read_text(encoding='utf-8').splitlines() if l.strip()) \
        if p.exists() else 0


def _clean(s) -> str:
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', str(s or ''))).strip()


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    if len(sys.argv) == 4:
        rows = search(*sys.argv[1:4])
        for r in rows:
            print(r.get('id'), '|', _clean(r.get('type_txt')), _clean(r.get('num_txt')), '|', r.get('date_txt'),
                  '| JO', r.get('num_jo'), r.get('date_jo'), '|', _clean(r.get('objet_txt') or r.get('titre_txt'))[:150],
                  '| html', len(r.get('html_fichier_fr') or ''))
        if rows:
            print('fields:', sorted(rows[0]))
    else:
        for s in SEARCHES:
            print(s, len(search(*s)))
        for u in GETS:
            print(u, len(get(u)))
        print('requests so far:', requests_made())
