"""Fetch Ukraine's acts from archived copies of zakon.rada.gov.ua (Verkhovna Rada, "Законодавство України").

zakon.rada.gov.ua and data.rada.gov.ua refuse connections from outside Ukraine (TCP timeout from this machine,
2026-10-28), and Common Crawl's index server was unreachable the same day, so every page is read from the Internet
Archive's raw `id_` captures through the shared client scripts/gitlaw_common/wayback.py (one adaptive rate for the
whole machine; every request is logged to .cache/requests.jsonl; every body is cached by the sha256 of its URL).

    python -X utf8 fetch.py                 # every act in ACTS
    python -X utf8 fetch.py constitution    # one act

Per act it reads
  1. the CDX list of captures of the act's current page and its print page, and takes the newest complete capture:
     its edition selector lists every edition ("редакція") Rada dates, newest last;
  2. one CDX listing (filtered server-side to captures of 10 kB or more) of every `.../edYYYYMMDD` and
     `.../edYYYYMMDD/print` URL;
  3. for each edition date, the captures of that edition, tried newest first until one is complete
     (the page names that edition and holds the act's closing words).
It writes .cache/<slug>.plan.json: the edition list and, per edition, the capture used (or none).
"""
import json
import re
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common')
import wayback  # noqa: E402

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
HOST = 'zakon.rada.gov.ua/laws/show/'

# slug -> (Rada document code, a phrase that only a complete text contains near its end)
ACTS = {
    'konstytutsiia': ('254к/96-вр', 'Конституція України'),
    'tsyvilnyi-kodeks': ('435-15', 'Цивільний кодекс України'),
    'kryminalnyi-kodeks': ('2341-14', 'Кримінальний кодекс України'),
}


def q(code: str) -> str:
    return urllib.parse.quote(code, safe='/')


def decode(body: bytes) -> str:
    head = body[:3000].lower()
    if b'windows-1251' in head or b'charset=cp1251' in head:
        return body.decode('cp1251', 'replace')
    try:
        return body.decode('utf-8')
    except UnicodeDecodeError:
        return body.decode('cp1251', 'replace')


def cdx(url: str, match: str, extra: list[str]) -> list[dict]:
    qs = [f'url={url}', 'output=json', f'matchType={match}',
          'fl=timestamp,original,mimetype,statuscode,digest,length', 'filter=statuscode:200'] + extra
    # wayback._curl does not pass --globoff, so [] and {} must be percent-encoded or curl expands them into
    # several requests (ISSUES.md)
    query = '&'.join(qs).replace('[', '%5B').replace(']', '%5D').replace('{', '%7B').replace('}', '%7D')
    raw = wayback.fetch('https://web.archive.org/cdx/search/cdx?' + query, CACHE)
    if not raw:
        return []
    rows = json.loads(raw.decode('utf-8') or '[]')
    return [dict(zip(rows[0], r)) for r in rows[1:]] if rows else []


def editions_of(text: str) -> list[str]:
    """Edition dates from the page's edition selector (the <option>s whose value ends in edYYYYMMDD)."""
    eds = []
    for m in re.finditer(r'<option[^>]*value="[^"]*/ed(\d{8})"', text):
        if m.group(1) not in eds:
            eds.append(m.group(1))
    return eds


def is_complete(text: str, ed: str | None) -> bool:
    if 'id="article"' not in text and "id='article'" not in text:
        return False
    if ed and f'ed{ed}' not in text:
        return False
    # the edition banner: "Редакція від DD.MM.YYYY" / "Прийняття від" for the edition shown
    return len(text) > 60000


def fetch_act(slug: str) -> dict:
    code, _ = ACTS[slug]
    base = HOST + q(code)
    # 1. the current page and print page
    cur = []
    for suffix in ('', '/print'):
        for c in cdx(base + suffix, 'exact', ['filter=length:[0-9]{5,}', 'collapse=digest']):
            c['suffix'] = suffix
            cur.append(c)
    cur.sort(key=lambda c: c['timestamp'], reverse=True)
    current = None
    for c in cur[:12]:
        body = wayback.get(c['original'], ts=c['timestamp'], cache=CACHE)
        if not body:
            continue
        t = decode(body)
        eds = editions_of(t)
        if eds and is_complete(t, None):
            current = {'timestamp': c['timestamp'], 'url': c['original'], 'editions': eds}
            break
    if not current:
        raise SystemExit(f'{slug}: no complete current capture')
    # 2. every capture of every edition page
    rows = cdx(base + '/ed', 'prefix', ['filter=length:[0-9]{5,}'])
    by_ed: dict[str, list[dict]] = {}
    for r in rows:
        u = urllib.parse.unquote(r['original'])
        m = re.search(r'/ed(\d{8})(/print)?$', u)
        if m:
            r['print'] = bool(m.group(2))
            by_ed.setdefault(m.group(1), []).append(r)
    # 3. one complete capture per edition (newest first; print pages before full pages)
    plan = {'slug': slug, 'code': code, 'current': current, 'editions': {}}

    def pick(ed: str):
        caps = sorted(by_ed.get(ed, []), key=lambda r: (r['timestamp'], r['print']), reverse=True)
        tried = 0
        for c in caps:
            if tried >= 6:
                break
            tried += 1
            body = wayback.get(c['original'], ts=c['timestamp'], cache=CACHE)
            if body and is_complete(decode(body), ed):
                return ed, {'timestamp': c['timestamp'], 'url': c['original'], 'tried': tried}
        return ed, {'timestamp': None, 'captures': len(caps), 'tried': tried}

    with ThreadPoolExecutor(4) as ex:
        for ed, got in ex.map(pick, current['editions']):
            plan['editions'][ed] = got
    have = sum(1 for v in plan['editions'].values() if v.get('timestamp'))
    print(f'{slug}: {len(current["editions"])} editions, {have} archived complete', flush=True)
    out = CACHE / f'{slug}.plan.json'
    tmp = out.with_suffix('.tmp')
    tmp.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding='utf-8')
    tmp.replace(out)
    return plan


if __name__ == '__main__':
    for s in (sys.argv[1:] or list(ACTS)):
        fetch_act(s)
