"""Fetch Romania's Phase 1 acts from the Portal Legislativ (legislatie.just.ro) through Internet Archive captures.

legislatie.just.ro closes every TLS connection from this machine after the request (curl: schannel "server closed
abruptly"; OpenSSL: close_notify before any response), so the portal and its SOAP service cannot be read directly.
The Internet Archive holds `id_` captures of its pages. On the portal every consolidated form ("forma consolidată")
of an act is its own document, /Public/DetaliiDocument/<id>, and each act page lists all of its forms with their
dates under "istoric consolidări". So:

  1. read the latest capture of each act's root page and its list of forms;
  2. for every form, list its captures (one CDX request) and read the newest complete capture;
  3. write forms.json, pinning every form's document id, date and capture timestamp, for parse.py.

Common Crawl (the shared client's first choice) was unreachable from this machine on 2026-10-28
(index.commoncrawl.org: connect timeout), so this uses archive.org through the shared adaptive client only.

    python -X utf8 scripts/romania-law/fetch.py            # resumable: everything is cached by URL
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common')
import wayback  # noqa: E402

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
PORTAL = 'https://legislatie.just.ro/Public/DetaliiDocument/'
BASE_PAGE = 'https://legislatie.just.ro/Public/DetaliiDocumentAfis/'

# act slug -> root document id (the page that lists the act's forms) and the base form ("forma de bază") id
ACTS = {
    'constitutia': {'root': '47355', 'base': '1413'},
    # 109884 is the civil code's own page, but its newest capture did not come back; 175630 (the form of 04.02.2016)
    # lists every form of the act just the same.
    'codul-civil': {'root': '175630', 'base': '109884'},
    'codul-penal': {'root': '109855', 'base': '109855'},
}
MIN_BYTES = 100_000  # a complete act page; error pages and challenge pages are a few kB

# Pinned by hand on 2026-10-29 (see PROGRESS.md):
# - the Civil Code's newest form (03.05.2026, id 309285) has no capture of its own, but the act page 109884 shows
#   the newest form, and its capture of 25 June 2026 lists 03.05.2026 as the form shown;
# - the newest capture of the Civil Code's base text (20251206132336) is cut off at exactly 5 MiB, so the newest
#   complete one (20250413082055, 6.9 MB, ends in </html>) is used.
PINS = {'codul-civil': {'309285': {'page': '109884', 'capture': '20260625171643'}}}
BASE_CAPTURE = {'codul-civil': '20250413082055'}

# Phase 2 (gitlaw-RO-2, 2026-10-29). These are read Common Crawl first: index.commoncrawl.org is down, but
# wayback._cc_captures_files reads each crawl's index from the data host, and ONE prefix query per crawl lists every
# legislatie.just.ro/Public/DetaliiDocument[Afis]/ capture (1-3 index blocks). A capture counts only if it is complete
# (not truncated, ends in </html>, holds articles) and shows the form its id stands for; archive.org fills the rest.
ACTS2 = {
    # 140271 is the republication of 2012 (in force 15.02.2013) and lists every form; 120650 is the 2010 law as published
    'codul-procedura-civila': {'root': '140271', 'base': '120650'},
    'codul-procedura-penala': {'root': '120611', 'base': '120611'},
    'codul-muncii': {'root': '41627', 'base': '41627'},
    'legea-190-2018': {'root': '203151', 'base': '203151'},
}
CC_PREFIX = 'legislatie.just.ro/Public/DetaliiDocument'   # also matches DetaliiDocumentAfis/
CC_CRAWLS = 40                                            # back to 2022; older crawls cut pages at 1 MB
DOC_RE = re.compile(r'^https?://(?:www\.)?legislatie\.just\.ro/Public/(DetaliiDocument|DetaliiDocumentAfis)/(\d+)$', re.I)


def log(*a):
    print(*a, flush=True)


def best_capture(doc_id: str) -> dict | None:
    caps = wayback.captures(f'legislatie.just.ro/Public/DetaliiDocument/{doc_id}', match='exact', cache=CACHE,
                            status='200', collapse=None)
    caps = [c for c in caps if c.get('length', '0').isdigit() and int(c['length']) * 3 >= MIN_BYTES]
    return caps[-1] if caps else None


def page(doc_id: str, ts: str) -> bytes | None:
    return wayback.get(PORTAL + doc_id, ts=ts, cache=CACHE)


def forms_listed(body: bytes) -> tuple[str | None, list[dict]]:
    """(the date of the form this page shows, [{'date','id','kind'}]) from the 'istoric consolidări' list."""
    s = body.decode('utf-8', 'replace')
    i, j = s.find('istoric_fa'), s.find('Formadebaza')
    seg = s[i:j] if i >= 0 and j > i else ''
    shown, out = None, []
    for attrs, label in re.findall(r'<a ([^>]*)>([^<]*)</a>', seg):
        t = re.search(r"title='(Consolidarea|Republicarea) din (\d\d)\.(\d\d)\.(\d{4})'", attrs)
        if not t:
            continue
        date = f'{t.group(4)}-{t.group(3)}-{t.group(2)}'
        h = re.search(r"href='[^']*/DetaliiDocument/(\d+)(\?[^']*)?'", attrs)
        kind = 'republicare' if t.group(1) == 'Republicarea' else 'consolidare'
        if h:
            out.append({'date': date, 'id': h.group(1), 'kind': kind})
        else:
            shown = date
            out.append({'date': date, 'id': None, 'kind': kind})
    return shown, out


def load_manifest() -> dict:
    p = HERE / 'forms.json'
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}


def save_manifest(manifest: dict) -> None:
    order = list(ACTS) + list(ACTS2)
    manifest = {k: manifest[k] for k in sorted(manifest, key=lambda k: order.index(k) if k in order else len(order))}
    tmp = HERE / 'forms.json.tmp'
    tmp.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    os.replace(tmp, HERE / 'forms.json')


# ------------------------------------------------------------------ Phase 2: Common Crawl first

def cc_listing() -> dict:
    """{('DetaliiDocument'|'DetaliiDocumentAfis', id): [record, newest first]} over the newest CC_CRAWLS crawls.
    Cached in .cache/cc-listing.json so a rerun reads the same records."""
    p = CACHE / 'cc-listing.json'
    if p.exists():
        recs = json.loads(p.read_text(encoding='utf-8'))
    else:
        crawls = wayback.cc_crawls(CACHE)[:CC_CRAWLS]

        def one(crawl):
            for _ in range(6):
                try:
                    got = wayback._cc_captures_files(CC_PREFIX, crawl, 'prefix')
                    if got is not None:
                        return got
                except Exception as e:  # a transient error page from the data host
                    log('  cc retry', crawl, type(e).__name__)
                import time
                time.sleep(5)
            raise SystemExit(f'Common Crawl index unreadable for {crawl}')

        with ThreadPoolExecutor(8) as ex:
            recs = [r for rs in ex.map(one, crawls) for r in rs]
        keep = ('url', 'timestamp', 'crawl', 'status', 'mime', 'digest', 'length', 'offset', 'filename', 'truncated')
        recs = [{k: r[k] for k in keep if k in r} for r in recs]
        recs.sort(key=lambda r: (r['url'], r['timestamp'], r['filename']))
        tmp = p.with_suffix('.tmp')
        tmp.write_text(json.dumps(recs, indent=0) + '\n', encoding='utf-8')
        os.replace(tmp, p)
    out = {}
    for r in recs:
        m = DOC_RE.match(r['url'])
        if m and r.get('status') == '200' and not r.get('truncated'):
            out.setdefault((m.group(1).lower(), m.group(2)), []).append(r)
    for v in out.values():
        v.sort(key=lambda r: r['timestamp'], reverse=True)
    return out


def complete(body: bytes | None) -> bool:
    return bool(body) and len(body) >= 20_000 and b'S_ART' in body and body.rstrip()[-7:].lower() == b'</html>'


def form_ok(body: bytes, want: str | None, nxt_info: tuple | None) -> bool:
    """Whether a page shows the form dated `want`. The act's current page marks its own form in "istoric
    consolidări" (no link); a past form's page lists only the forms after it, so there the next form's date (`nxt`)
    must be listed and nothing on or before `want`. A page lists the later forms only up to the next republication,
    so the last form before one (nxt is a republication, `nxt_rep`) may list none. A page showing some other form (as
    130143 did) fails."""
    if want is None:
        return True
    nxt, nxt_rep = nxt_info or (None, False)
    shown, listed = forms_listed(body)
    if shown is not None:
        return shown == want
    dates = {f['date'] for f in listed}
    if not dates:
        return nxt_rep
    return min(dates) > want and (nxt in dates or nxt_rep)


def cc_body(r: dict) -> bytes | None:
    """wayback.cc_get, retrying when the data host answers with an error page instead of the gzip member."""
    import time
    for i in range(6):
        try:
            return wayback.cc_get(r, cache=CACHE)
        except Exception as e:
            log('  cc_get retry', r['timestamp'], type(e).__name__)
            time.sleep(3 * (i + 1))
    return None


def cc_pick(listing: dict, kind: str, doc_id: str, want: str | None, nxt: str | None = None) -> dict | None:
    """The newest complete Common Crawl capture of the page that shows the form dated `want` (if given)."""
    for r in listing.get((kind, doc_id), []):
        b = cc_body(r)
        if complete(b) and form_ok(b, want, nxt):
            return {k: r[k] for k in ('crawl', 'timestamp', 'filename', 'offset', 'length', 'url')}
    return None


def ia_pick(doc_id: str, want: str | None, nxt: str | None = None, afis: bool = False) -> str | None:
    """The newest complete archive.org capture (timestamp) of the page that shows the form dated `want` (if given)."""
    path = 'DetaliiDocumentAfis' if afis else 'DetaliiDocument'
    caps = wayback.captures(f'legislatie.just.ro/Public/{path}/{doc_id}', match='exact', cache=CACHE, status='200',
                            collapse=None)
    caps = [c for c in caps if c.get('length', '0').isdigit() and int(c['length']) >= 5_000]
    for c in reversed(caps[-4:]):
        b = wayback.get((BASE_PAGE if afis else PORTAL) + doc_id, ts=c['timestamp'], cache=CACHE)
        if complete(b) and form_ok(b, want, nxt):
            return c['timestamp']
    return None


def phase2(slugs: list[str]) -> None:
    listing = cc_listing()
    log('cc listing:', sum(len(v) for v in listing.values()), 'complete-looking records,', len(listing), 'pages')
    manifest = load_manifest()
    for slug in slugs:
        a = ACTS2[slug]
        # the root page: the newest complete capture in either archive, for the longest list of forms
        best = None
        for r in listing.get(('detaliidocument', a['root']), []):
            b = cc_body(r)
            if complete(b):
                best = ('cc', r, b)
                break
        ia_caps = wayback.captures(f'legislatie.just.ro/Public/DetaliiDocument/{a["root"]}', match='exact',
                                   cache=CACHE, status='200', collapse=None)
        for c in reversed(ia_caps[-3:]):
            if best and best[1]['timestamp'] >= c['timestamp']:
                break
            b = page(a['root'], c['timestamp'])
            if complete(b):
                best = ('ia', c, b)
                break
        if not best:
            log(slug, 'no complete root capture')
            continue
        src, rec, body = best
        shown, forms = forms_listed(body)
        for f in forms:
            if f['id'] is None:
                f['id'] = a['root']
        m = {'root': a['root'], 'root_capture': rec['timestamp'], 'root_source': src, 'base': a['base'],
             'forms': forms, 'captures': {}, 'cc': {}}
        if src == 'cc':
            m['cc'][a['root']] = {k: rec[k] for k in ('crawl', 'timestamp', 'filename', 'offset', 'length', 'url')}
        log(slug, 'root', src, rec['timestamp'], 'shows', shown, 'forms', len(forms))
        want = {f['id']: f['date'] for f in forms}
        dates = sorted({f['date'] for f in forms})
        reps = {f['date'] for f in forms if f['kind'] == 'republicare'}
        nxt = {}
        for i, w in want.items():
            d = next((d for d in dates if d > w), None)
            nxt[i] = (d, d in reps)

        def one(doc_id):
            if doc_id == a['root'] and doc_id in m['cc']:
                return doc_id, 'cc', m['cc'][doc_id]
            if doc_id == a['root'] and src == 'ia':
                return doc_id, 'ia', rec['timestamp']
            got = cc_pick(listing, 'detaliidocument', doc_id, want[doc_id], nxt[doc_id])
            if got:
                return doc_id, 'cc', got
            ts = ia_pick(doc_id, want[doc_id], nxt[doc_id])
            return doc_id, ('ia' if ts else None), ts

        with ThreadPoolExecutor(12) as ex:
            for doc_id, how, got in ex.map(one, sorted(want, key=int)):
                log(' ', slug, doc_id, want[doc_id], how, got if how != 'cc' else got['timestamp'])
                if how == 'cc':
                    m['cc'][doc_id] = got
                elif how == 'ia':
                    m['captures'][doc_id] = got
        # the base form ("forma de bază"): DetaliiDocumentAfis/<base>
        got = cc_pick(listing, 'detaliidocumentafis', a['base'], None)
        if got:
            m['base_cc'] = got
            m['base_capture'] = got['timestamp']
        else:
            ts = ia_pick(a['base'], None, None, afis=True)
            if ts:
                m['base_capture'] = ts
        log(' ', slug, 'base', a['base'], 'cc' if got else 'ia', m.get('base_capture'))
        # A republication's own page shows the newest form (as 130143 did), but its DetaliiDocumentAfis page is the
        # republished text as printed in the Monitorul Oficial, which is that form: read it there.
        m['afis'] = {}
        for f in forms:
            if f['kind'] == 'republicare' and f['id'] not in m['cc'] and f['id'] not in m['captures']:
                got = cc_pick(listing, 'detaliidocumentafis', f['id'], None)
                if got:
                    m['afis'][f['id']] = got
                    log(' ', slug, f['id'], f['date'], 'republished text from DetaliiDocumentAfis', got['timestamp'])
        # A form that was once the newest may never have been captured under its own id, but the act page showed it
        # then: read the act page's capture from the days it was the newest (its "istoric" marks the form shown).
        m['pins'] = {}
        for f in forms:
            fid = f['id']
            if fid in m['cc'] or fid in m['captures'] or fid in m['afis'] or fid == a['root']:
                continue
            nd = nxt[fid][0] or '9999'
            lo, hi = f['date'].replace('-', ''), nd.replace('-', '') + '999999'
            for r in listing.get(('detaliidocument', a['root']), []):
                if lo <= r['timestamp'] <= hi:
                    b = cc_body(r)
                    if complete(b) and forms_listed(b)[0] == f['date']:
                        m['cc'][fid] = {k: r[k] for k in ('crawl', 'timestamp', 'filename', 'offset', 'length', 'url')}
                        log(' ', slug, fid, f['date'], 'from the act page in Common Crawl', r['timestamp'])
                        break
            if fid in m['cc']:
                continue
            for c in reversed([c for c in ia_caps if lo <= c['timestamp'] <= hi]):
                b = page(a['root'], c['timestamp'])
                if complete(b) and forms_listed(b)[0] == f['date']:
                    m['pins'][fid] = {'page': a['root'], 'capture': c['timestamp']}
                    log(' ', slug, fid, f['date'], 'from the act page in the Internet Archive', c['timestamp'])
                    break
        missing = sorted(set(want) - set(m['cc']) - set(m['captures']) - set(m['afis']) - set(m['pins']), key=int)
        m['missing'] = missing
        log(' ', slug, 'missing', missing)
        manifest[slug] = m
        save_manifest(manifest)
    log('done')


def main():
    CACHE.mkdir(exist_ok=True)
    manifest = load_manifest()
    for slug, a in ACTS.items():
        cap = best_capture(a['root'])
        if not cap:
            log(slug, 'no capture of root', a['root'])
            continue
        body = page(a['root'], cap['timestamp'])
        shown, forms = forms_listed(body or b'')
        log(slug, 'root', a['root'], cap['timestamp'], len(body or b''), 'shows', shown, 'forms', len(forms))
        for f in forms:
            if f['id'] is None:
                f['id'] = a['root']
        ids = {f['id'] for f in forms}
        manifest[slug] = {'root': a['root'], 'root_capture': cap['timestamp'], 'base': a['base'], 'forms': forms,
                          'captures': {}}

        def one(doc_id):
            c = best_capture(doc_id)
            if not c:
                return doc_id, None, None
            b = page(doc_id, c['timestamp'])
            return doc_id, c['timestamp'], (len(b) if b else None)

        with ThreadPoolExecutor(4) as ex:
            for doc_id, ts, n in ex.map(one, sorted(ids, key=int)):
                log(' ', slug, doc_id, ts, n)
                if ts and n and n >= MIN_BYTES:
                    manifest[slug]['captures'][doc_id] = ts
        # the base form ("forma de bază", the act as published) is DetaliiDocumentAfis/<base>
        caps = wayback.captures(f'legislatie.just.ro/Public/DetaliiDocumentAfis/{a["base"]}', match='exact', cache=CACHE,
                                status='200', collapse=None)
        caps = [c for c in caps if c.get('length', '0').isdigit() and int(c['length']) * 3 >= MIN_BYTES]
        if caps:
            ts = BASE_CAPTURE.get(slug, caps[-1]['timestamp'])
            b = wayback.get(BASE_PAGE + a['base'], ts=ts, cache=CACHE)
            log(' ', slug, 'base', a['base'], ts, len(b or b''))
            if b and len(b) >= MIN_BYTES:
                manifest[slug]['base_capture'] = ts
        for doc_id, pin in PINS.get(slug, {}).items():
            b = page(pin['page'], pin['capture'])
            log(' ', slug, 'pin', doc_id, pin, len(b or b''))
            if b and len(b) >= MIN_BYTES:
                manifest[slug].setdefault('pins', {})[doc_id] = pin
        save_manifest(manifest)
    log('done')


if __name__ == '__main__':
    if sys.argv[1:]:          # python fetch.py <phase 2 slug> ...   (or 'phase2' for all of ACTS2)
        phase2(list(ACTS2) if sys.argv[1:] == ['phase2'] else sys.argv[1:])
    else:
        main()
