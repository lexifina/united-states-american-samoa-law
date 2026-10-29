"""Downloads Austrian federal law from the RIS OGD API into scripts/austria-law/.cache/.

    python -X utf8 scripts/austria-law/fetch.py [slug ...]      # default: every act in ACTS, in order

The RIS (Rechtsinformationssystem des Bundes, Bundeskanzleramt) publishes the consolidated federal law
("Bundesrecht konsolidiert", application BrKons) through its Open Government Data API, v2.6:

  search pages   https://data.bka.gv.at/ris/api/v2.6/Bundesrecht?Applikation=BrKons&Gesetzesnummer=N
                 &DokumenteProSeite=OneHundred&Seitennummer=P
                 every document of an act: one version of one §, Art. or Anl., with its in-force window
                 (Inkrafttretensdatum, Ausserkrafttretensdatum) and its Kundmachungsorgan, which names the law that
                 last amended that version ("BGBl. I Nr. 165/1999 zuletzt geändert durch BGBl. I Nr. 70/2024").
  one document   https://ris.bka.gv.at/Dokumente/Bundesnormen/<NOR>/<NOR>.xml   (the URL the search page gives)

The RIS OGD terms (FAQ of 28 November 2025) bind this fetch, and are stricter than Lexifina's general speed rule:
one connection, a pause of two seconds after each answer, and requests only between 20:00 and 05:00 Vienna time or
at weekends and on Austrian public holidays. This script enforces all three. Every response is cached under
.cache/<sha256 of the URL>, fetched with curl (Python's TLS fails on this machine), and logged to
.cache/requests.jsonl. Re-running fetches only what is missing. Documents that were never in force (RIS dates their
end before their start) are not fetched.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
API = 'https://data.bka.gv.at/ris/api/v2.6/Bundesrecht'
PAUSE = 2.0

# slug -> RIS Gesetzesnummer, in fetch order (Phase 1 first).
ACTS = {
    'b-vg': '10000138',     # Bundes-Verfassungsgesetz
    'abgb': '10001622',     # Allgemeines bürgerliches Gesetzbuch
    'dsg': '10001597',      # Datenschutzgesetz
    'stgb': '10002296',     # Strafgesetzbuch
}
_last = [0.0]


# ---------------------------------------------------------------- RIS OGD hours (no tz database on this machine)

def last_sunday(year: int, month: int) -> dt.date:
    d = (dt.date(year, month + 1, 1) if month < 12 else dt.date(year + 1, 1, 1)) - dt.timedelta(days=1)
    return d - dt.timedelta(days=(d.weekday() + 1) % 7)


def easter(y: int) -> dt.date:
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    return dt.date(y, month, (h + l - 7 * m + 114) % 31 + 1)


def holiday(d: dt.date) -> bool:
    """Austrian public holidays (Feiertagsruhegesetz 1957, § 1)."""
    e = easter(d.year)
    moving = {e + dt.timedelta(days=n) for n in (1, 39, 50, 60)}
    fixed = {(1, 1), (1, 6), (5, 1), (8, 15), (10, 26), (11, 1), (12, 8), (12, 25), (12, 26)}
    return d in moving or (d.month, d.day) in fixed


def vienna_now() -> dt.datetime:
    utc = dt.datetime.now(dt.timezone.utc)
    y = utc.year
    start = dt.datetime.combine(last_sunday(y, 3), dt.time(1), dt.timezone.utc)
    end = dt.datetime.combine(last_sunday(y, 10), dt.time(1), dt.timezone.utc)
    return (utc + dt.timedelta(hours=2 if start <= utc < end else 1)).replace(tzinfo=None)


def fetch_allowed(now: dt.datetime) -> bool:
    return now.hour >= 20 or now.hour < 5 or now.weekday() >= 5 or holiday(now.date())


# ---------------------------------------------------------------- the cache

def cache_path(url: str) -> Path:
    return CACHE / hashlib.sha256(url.encode()).hexdigest()


def fetch(url: str, offline: bool = False, check: bytes | None = None) -> bytes:
    path = cache_path(url)
    if path.exists():
        return path.read_bytes()
    if offline:
        raise FileNotFoundError(f'not cached: {url}')
    CACHE.mkdir(exist_ok=True)
    gi = CACHE / '.gitignore'
    if not gi.exists():
        gi.write_text('*\n')
    for attempt in range(5):
        while not fetch_allowed(vienna_now()):
            print(f'{vienna_now():%Y-%m-%d %H:%M} Vienna: outside the RIS OGD hours; waiting', flush=True)
            time.sleep(600)
        wait = _last[0] + PAUSE - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        out = subprocess.run(['curl', '-sS', '-L', '--max-redirs', '4', '--compressed', '-A', UA, '-m', '180',
                              '-w', '\n%{http_code}', url], capture_output=True)
        _last[0] = time.monotonic()
        body, _, code = out.stdout.rpartition(b'\n')
        code = code.decode().strip()
        with open(CACHE / 'requests.jsonl', 'a', encoding='utf-8') as log:
            log.write(json.dumps({'url': url, 'status': code, 'bytes': len(body),
                                  'at': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                                  'sha256': hashlib.sha256(body).hexdigest()}) + '\n')
        if out.returncode == 0 and code == '200' and body.strip() and (check is None or check in body):
            tmp = path.with_suffix('.tmp')
            tmp.write_bytes(body)
            tmp.replace(path)
            return body
        if code in ('429', '503'):
            print(f'{code} from RIS: waiting 120 s', flush=True)
            time.sleep(120)
        else:
            time.sleep(10 * (attempt + 1))
    raise RuntimeError(f'{url}: curl {out.returncode} http {code} {out.stderr.decode(errors="replace")[:200]}')


def list_url(nr: str, page: int) -> str:
    return f'{API}?Applikation=BrKons&Gesetzesnummer={nr}&DokumenteProSeite=OneHundred&Seitennummer={page}'


def as_list(x) -> list:
    return x if isinstance(x, list) else ([] if x is None else [x])


def list_pages(nr: str, offline: bool = False) -> list[dict]:
    """The raw OgdDocumentReference records of every document RIS holds for one act."""
    refs, page = [], 1
    while True:
        raw = fetch(list_url(nr, page), offline, check=b'OgdSearchResult')
        res = json.loads(raw.decode('utf-8'))['OgdSearchResult']
        r = res['OgdDocumentResults']
        hits = int(r['Hits']['#text'])
        got = as_list(r.get('OgdDocumentReference'))
        refs += got
        if not got or len(refs) >= hits:
            return refs
        page += 1


def xml_url(ref: dict) -> str | None:
    urls = as_list(ref['Data']['Dokumentliste']['ContentReference']['Urls']['ContentUrl'])
    return next((u['Url'] for u in urls if u['DataType'] == 'Xml'), None)


def in_force_ever(ref: dict) -> bool:
    k = ref['Data']['Metadaten']['Bundesrecht']['BrKons']
    a, b = k.get('Inkrafttretensdatum'), k.get('Ausserkrafttretensdatum')
    return bool(a) and not (b and b < a)


def main(argv: list[str]) -> None:
    slugs = argv or list(ACTS)
    plan = {}
    for slug in slugs:
        refs = list_pages(ACTS[slug])
        todo = [xml_url(r) for r in refs if in_force_ever(r)]
        plan[slug] = todo
        print(f'{slug}: {len(refs)} documents, {len(todo)} ever in force', flush=True)
    for slug in slugs:
        n = 0
        for url in plan[slug]:
            fetch(url, check=b'<risdok')
            n += 1
            if n % 100 == 0:
                print(f'{slug}: {n}/{len(plan[slug])}', flush=True)
        print(f'{slug}: done, {n} documents', flush=True)


if __name__ == '__main__':
    main(sys.argv[1:])
