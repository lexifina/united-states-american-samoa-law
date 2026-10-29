"""Fetch Togo sources into .cache/ (sha256 of the URL), logging every request to .cache/requests.jsonl.

Direct source: jo.gouv.tg (Journal Officiel de la République togolaise). Its robots.txt asks for
`Crawl-delay: 10`, so direct requests are spaced 10 s apart (the stated crawl delay overrides the
3 req/s speed rule, as with IMPO). Archive.org and Common Crawl go through scripts/gitlaw_common/wayback.py.

    python -X utf8 fetch.py <url> [<url> ...]      # fetch (or reuse) each URL
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
DELAY = {'jo.gouv.tg': 10.0}
_last: dict[str, float] = {}


def path_for(url: str) -> Path:
    return CACHE / hashlib.sha256(url.encode('utf-8')).hexdigest()


def get(url: str, refresh: bool = False) -> bytes | None:
    """The bytes of url, from cache or by curl; None on a non-200."""
    CACHE.mkdir(exist_ok=True)
    p = path_for(url)
    if p.exists() and not refresh:
        return p.read_bytes()
    host = url.split('/')[2]
    gap = DELAY.get(host, 0.34)
    wait = _last.get(host, 0) + gap - time.time()
    if wait > 0:
        time.sleep(wait)
    tmp = p.with_suffix('.part')
    r = subprocess.run(['curl', '-sS', '--compressed', '-L', '-m', '300', '-A', UA, '-o', str(tmp),
                        '-w', '%{http_code}', url], capture_output=True, text=True)
    _last[host] = time.time()
    code = int(r.stdout.strip() or 0)
    size = tmp.stat().st_size if tmp.exists() else 0
    with open(CACHE / 'requests.jsonl', 'a', encoding='utf-8') as f:
        f.write(json.dumps({'t': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'url': url,
                            'status': code, 'bytes': size, 'file': p.name}) + '\n')
    if code != 200:
        tmp.unlink(missing_ok=True)
        return None
    tmp.replace(p)
    return p.read_bytes()


def parse_sources() -> None:
    """Fetch (or reuse) every file parse.py reads: JO PDFs directly, Assemblée nationale copies via the Internet Archive."""
    sys.path.insert(0, str(HERE))
    sys.path.insert(0, str(HERE.parent / 'gitlaw_common'))
    import parse
    import wayback
    for u in (parse.JO_2024, parse.JO_2019, parse.JO_2021, parse.JO_2022, *parse.NODES.values()):
        b = get(u)
        print(u, None if b is None else len(b))
    for u in (parse.AN_2019, parse.AN_2024):
        b = wayback.fetch(u, CACHE)
        print(u, None if b is None else len(b))


if __name__ == '__main__':
    if len(sys.argv) == 1:
        parse_sources()
    for u in sys.argv[1:]:
        b = get(u)
        print(u, None if b is None else len(b), path_for(u).name)
