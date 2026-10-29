"""Builds scripts/bahamas-law/corpus.json and corpus.d/*.json from the cache only (no network).

    python -X utf8 scripts/bahamas-law/parse.py            # write the corpus
    python -X utf8 scripts/bahamas-law/parse.py --report   # also print every Penal Code change and its credit

Source: laws.bahamas.gov.bs (Bahamas Laws On-line, Government of The Bahamas); see sources.py. Each act's history is
built from the publisher's own dated consolidations (the revised editions it serves as numbered PDFs, and the
point-in-time act index that says which edition was current on which day). Between two editions, a provision whose
marginal note in the later edition names a law that the earlier edition does not list takes its later wording on
that law's commencement date (from the publisher's index); every other difference between the editions is the
publisher's, dated by the day the later edition became current. Text comes from each PDF's own text layer (no OCR).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pdftext  # noqa: E402
import sources as S  # noqa: E402

CACHE = HERE / '.cache'
PLACEHOLDER = '[The source does not give the text in force on this date.]'
LICENCE = ('Government of The Bahamas Copyright; the site may be used for informational non-commercial purposes '
           '(its Copyright page, quoted in licence_note)')


def cached(url: str, data: str | None = None) -> bytes:
    k = url if data is None else url + '\n' + data
    p = CACHE / hashlib.sha256(k.encode('utf-8')).hexdigest()
    if not p.exists():
        raise SystemExit(f'not cached (run fetch.py --plan): {url} {data or ""}')
    return p.read_bytes()


def sha(url: str) -> str:
    return hashlib.sha256(cached(url)).hexdigest()


def day(s: str) -> str:
    """'Thursday, 04 November 2011' -> '2011-11-04'."""
    m = re.search(r'(\d{1,2}) (\w+) (\d{4})', s)
    return dt.datetime.strptime(' '.join(m.groups()), '%d %B %Y').date().isoformat()


# ---------------------------------------------------------------- the publisher's indexes

def index_rows(letter: str, on: str) -> list[dict]:
    """The act index for one letter on one day: principal rows and their 'amended by...' rows."""
    s = cached(*S.INDEX_PAGES[(letter, on)]).decode('utf-8', 'replace')
    head = re.search(r'Legislation for ([^<]*)', s)
    if not head or day(head.group(1)) != on:
        raise SystemExit(f'index page {letter} {on}: unexpected point-in-time heading')
    out = []
    for m in re.finditer(r'<tr class="(row\d|collapse act-collapse\d+)">(.*?)</tr>', s, re.S):
        b = m.group(2)
        num = re.search(r'Legislation Number: ([0-9A-Z-]+)', b)
        a = re.search(r'<a (?:class="npWrap" )?href="([^"]+)"[^>]*>(.*?)&nbsp;', b, re.S)
        c = re.search(r'title="Date Commenced" data-bs-content="([^"]*)"', b)
        if not (num and a):
            continue
        out.append({'principal': m.group(1).startswith('row'), 'number': num.group(1), 'pdf': a.group(1),
                    'title': html.unescape(re.sub('<[^>]+>', '', a.group(2))).strip(),
                    'commenced': day(c.group(1)) if c else None})
    return out


def act_rows(letter: str, on: str, number: str) -> list[list[dict]]:
    """Each listing of the act (one per consolidation current that day) with its amended-by rows."""
    groups, cur = [], None
    for r in index_rows(letter, on):
        if r['principal']:
            cur = [r] if r['number'] == number else None
            if cur:
                groups.append(cur)
        elif cur is not None and r['title'].startswith('amended by'):
            cur.append(r)
    return groups


def year_rows(y: int) -> dict[str, dict]:
    """'Acts by Year': {legislation number: {title, commenced}} for principal and amending acts."""
    s = cached(*S.YEAR_PAGES[y]).decode('utf-8', 'replace')
    out = {}
    for m in re.finditer(r'<tr class="row\d (row\w+)">(.*?)</tr>', s, re.S):
        b = m.group(2)
        n = re.search(r"Legislation Number: ([0-9A-Z-]+)", b)
        a = re.search(r'<a class="npWrap" href="[^"]+"[^>]*>(.*?)</div>', b, re.S)
        c = re.search(r'title="Date Commenced" data-bs-content="([^"]*)"', b)
        if n and a:
            out[n.group(1)] = {'title': html.unescape(a.group(1)).strip(), 'commenced': day(c.group(1)) if c else None}
    return out


def copyright_notice() -> str:
    s = cached(S.COPYRIGHT).decode('utf-8', 'replace')
    m = re.search(r'<div class="desc-article">\s*<p[^>]*>(.*?)</p>', s, re.S)
    return re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]+>', '', m.group(1)))).strip()


# ---------------------------------------------------------------- laws

def law_key(ref: tuple[str, str, str]) -> str:
    kind, y, n = ref
    return f'{kind}-{y}-{int(n):03d}' if kind == 'act' else f'{kind}-{y}-{n}'


def law_label(ref: tuple[str, str, str]) -> str:
    kind, y, n = ref
    return {'act': f'Act {n} of {y}', 'si': f'S.I. {n}/{y}', 'gn': f'G.N. {n}/{y}'}[kind]


def known_laws() -> dict[tuple, dict]:
    """Title and commencement of every law the publisher's year pages and index name, by (kind, year, number)."""
    out = {}
    for y in S.YEAR_PAGES:
        for num, r in year_rows(y).items():
            yy, nn = num.split('-')[:2]
            out[('act', yy, str(int(re.sub(r'\D', '', nn))))] = r
    return out


# ---------------------------------------------------------------- provisions

class Edition:
    def __init__(self, url: str, **kw):
        self.url = url
        self.sha = sha(url)
        self.units, self.front = pdftext.units(cached(url), **kw)
        self.list = pdftext.lawrefs(self.front)


def unit_texts(ed: Edition, vocab, label_word: str) -> dict[str, dict]:
    out = {}
    for k, u in ed.units.items():
        paras = [pdftext.join_lines(p['lines'], vocab) for p in u['paras']]
        if u['kind'] == 'schedule':
            text = '\n'.join(paras)
        else:
            num = u['label'].split()[-1]
            head = pdftext.join_lines(u['heading'], vocab).rstrip('.') if u['heading'] else ''
            text = '\n'.join([f'# {num}. {head}'.rstrip() if u['kind'] != 'preamble' else '# Preamble'] + paras)
        out[k] = {'label': u['label'], 'kind': u['kind'], 'text': text + '\n'}
    return out


def same_words(a: str, b: str) -> bool:
    return re.sub(r'\s+', '', a) == re.sub(r'\s+', '', b)


# ---------------------------------------------------------------- the acts

def build(report: bool = False):
    known = known_laws()
    eds = {
        'constitution': [Edition(S.PDFS['constitution'][0], prefix='art', label='Art.', preamble=r'^WHEREAS')],
        'penal-code': [Edition(u) for u in S.PDFS['penal-code']],
        'data-protection': [Edition(S.PDFS['data-protection'][0])],
    }
    vocab = pdftext.vocabulary([p['lines'] for es in eds.values() for e in es for u in e.units.values()
                                for p in u['paras']]
                               + [u['heading'] for es in eds.values() for e in es for u in e.units.values()
                                  if u['heading']])
    texts = {slug: [unit_texts(e, vocab, '') for e in es] for slug, es in eds.items()}

    # The publisher's index on the retrieval day: which edition is current, and what has amended it since.
    cur = {}
    for slug, letter, number in (('constitution', 'T', '1973-1080'), ('penal-code', 'P', '1873-0015'),
                                 ('data-protection', 'D', '2003-0003')):
        g = act_rows(letter, S.RETRIEVED, number)
        if len(g) != 1:
            raise SystemExit(f'{slug}: expected one current listing, got {len(g)}')
        cur[slug] = g[0]
        if not S.SITE + g[0][0]['pdf'] == S.PDFS[slug][-1]:
            raise SystemExit(f'{slug}: the current edition is {g[0][0]["pdf"]}, not the last one parsed')
    # The Penal Code's editions in the point-in-time index: the 2010 edition is listed (beside the 2017 one) up to
    # 30 December 2016 and is gone on 31 December 2016.
    before, after = act_rows('P', '2016-12-30', '1873-0015'), act_rows('P', '2016-12-31', '1873-0015')
    pdfs_before = {S.SITE + g[0]['pdf'] for g in before}
    pdfs_after = {S.SITE + g[0]['pdf'] for g in after}
    pc1, pc2 = S.PDFS['penal-code']
    if not (pc1 in pdfs_before and pc1 not in pdfs_after and pdfs_after == {pc2}):
        raise SystemExit('penal-code: the index no longer switches editions on 2016-12-31')
    switch = '2016-12-31'
    amended_2010_ed = [r for g in before if S.SITE + g[0]['pdf'] == pc1 for r in g[1:]]

    notice = copyright_notice()
    parts = {}

    # ---- The Constitution: one edition (LRO 1/2006), which states that the 1973 text has not been amended.
    con = eds['constitution'][0]
    con_units = texts['constitution'][0]
    con_amend = cur['constitution'][1:]
    con_laws = {
        'si-1973-1080': {'label': 'S.I. 1973 No. 1080', 'kind': 'decree',
                         'title': 'The Bahamas Independence Order 1973 (the Constitution is its Schedule)',
                         'url': S.PDFS['constitution'][0]},
    }
    parts['10-constitution'] = {
        'acts': [{
            'slug': 'constitution', 'short': 'Constitution',
            'title': 'The Constitution of the Commonwealth of The Bahamas',
            'url': S.PDFS['constitution'][0], 'first_law': 'si-1973-1080', 'earlier_laws': [],
            'versions': [{
                'from': '1973-07-10', 'source_url': con.url, 'sha256': con.sha, 'units': con_units,
                'note': ('The text of the 1973 Constitution as printed in the revised edition LRO 1/2006, which '
                         'notes that "to date [it] has not been amended". The publisher\'s index (retrieved '
                         f'{S.RETRIEVED}) still serves this edition as current.'),
            }],
        }],
        'laws': con_laws,
        'sources': [{'name': 'Bahamas Laws On-line: The Constitution, revised edition LRO 1/2006 (PDF)',
                     'url': con.url, 'sha256': con.sha, 'retrieved': S.RETRIEVED, 'requests': 1,
                     'licence': LICENCE,
                     'notes': 'Text layer read directly (no OCR). The only consolidation the site serves (_2 answers 403).'}],
        'decisions': [
            'Constitution: one version, the 1973 text as printed in LRO 1/2006 (the publisher\'s only consolidation, '
            'still current in its index on the retrieval day), whose footnote states the Constitution "to date has '
            'not been amended"; credited to The Bahamas Independence Order 1973 (S.I. 1973 No. 1080) and dated '
            '10 July 1973, the commencement date the index gives.',
        ] + [
            f'Constitution: {r["title"].replace("amended by... ", "")} (No. {r["number"]}, commenced {r["commenced"]} '
            'per the index) is left out: the site serves it only as a scanned image with no text layer (no OCR), '
            'and the current consolidation does not include it.'
            for r in con_amend
        ],
    }
    con_scan_chars = None
    try:
        import fitz
        d = fitz.open(stream=cached(S.AMENDING_PDF), filetype='pdf')
        con_scan_chars = sum(len(p.get_text().strip()) for p in d)
    except Exception:  # noqa: BLE001
        pass
    if con_amend and (con_scan_chars is None or con_scan_chars > 50):
        raise SystemExit('constitution: the 2017 amending act now has a text layer; revisit')

    # ---- The Data Protection Act: one edition (LRO 1/2008); the index lists no amending act.
    dpa = eds['data-protection'][0]
    if len(cur['data-protection']) != 1:
        raise SystemExit('data-protection: the index now lists an amending act')
    dpa_row = cur['data-protection'][0]
    dpa_refs = [r for u in dpa.units.values() for r in pdftext.lawrefs(u['notes'])]
    parts['30-data-protection'] = {
        'acts': [{
            'slug': 'data-protection', 'short': 'Data Protection Act',
            'title': 'Data Protection (Privacy of Personal Information) Act (Ch. 324A)',
            'url': dpa.url, 'first_law': 'act-2003-003', 'earlier_laws': [],
            'versions': [{
                'from': dpa_row['commenced'], 'source_url': dpa.url, 'sha256': dpa.sha,
                'units': texts['data-protection'][0],
                'note': ('The Act as printed in the revised edition LRO 1/2008, the publisher\'s only consolidation; '
                         'its list of laws names only the Act itself (No. 3 of 2003) and its commencement order '
                         '(S.I. 25/2007), and no provision carries an amendment note.'),
            }],
        }],
        'laws': {'act-2003-003': {'label': 'Act 3 of 2003', 'kind': 'law',
                                  'title': 'Data Protection (Privacy of Personal Information) Act, 2003',
                                  'url': dpa.url}},
        'sources': [{'name': 'Bahamas Laws On-line: Data Protection (Privacy of Personal Information) Act, Ch. 324A, '
                             'revised edition LRO 1/2008 (PDF)',
                     'url': dpa.url, 'sha256': dpa.sha, 'retrieved': S.RETRIEVED, 'requests': 1, 'licence': LICENCE,
                     'notes': 'Text layer read directly (no OCR). The only consolidation the site serves (_2 answers 403).'}],
        'decisions': [
            'Data Protection Act: one version, the revised edition LRO 1/2008, dated by the commencement the index '
            f'gives ({dpa_row["commenced"]}) and credited to the Act itself (No. 3 of 2003): the index lists no '
            'amending act on any day checked, the edition\'s list of laws names only the Act and its commencement '
            f'order, and no provision carries an amendment note (notes naming laws: {len(dpa_refs)}).',
        ],
    }
    if dpa_refs:
        raise SystemExit('data-protection: a provision now carries an amendment note; revisit')

    # ---- The Penal Code: the 2010 edition (LRO 1/2010), then the 2017 edition (LRO 1/2017), current from 2016-12-31.
    e1, e2 = eds['penal-code']
    t1, t2 = texts['penal-code']
    post = [r for r in e2.list if r not in e1.list]  # notes naming other laws are cross-references
    index_dates = {}
    for r in amended_2010_ed:
        y, n = r['number'].split('-')
        index_dates[('act', y, str(int(n)))] = (r['commenced'], r['title'].replace('amended by... ', ''))
    pc_laws, when = {}, {}
    for r in post:
        title, commenced = None, None
        if r in index_dates:
            commenced, title = index_dates[r]
        elif r in known:
            commenced, title = known[r]['commenced'], known[r]['title']
        note = None
        if not commenced:
            note = (f'The publisher gives no commencement date for {law_label(r)}, and it is not in its index or '
                    f'its Acts by Year list; its changes are dated by the first consolidation that shows them '
                    f'(LRO 1/2017, current from {switch}). It took effect earlier.')
        when[r] = commenced or switch
        e = {'label': law_label(r), 'kind': 'law'}
        if title:
            e['title'] = title
        if note:
            e['note'] = note
        pc_laws[law_key(r)] = e
    earlier = []
    for r in e1.list:
        k = law_key(r)
        if k not in pc_laws:
            pc_laws[k] = {'label': law_label(r), 'kind': 'law' if r[0] == 'act' else 'decree'}
        earlier.append(k)
    first_day = known[e1.list[-1]]['commenced'] if e1.list[-1] in known else None
    if not first_day:
        raise SystemExit('penal-code: no commencement date for the last law the 2010 edition lists')

    # Per provision: who changed it between the editions, and on which day.
    keys = list(t2) + [k for k in t1 if k not in t2]
    events: dict[str, dict[str, object]] = {}  # day -> {unit key: (unit or None, [law keys])}
    log = []
    v1_units = {}
    for k in keys:
        a, b = t1.get(k), t2.get(k)
        if a and b and same_words(a['text'], b['text']):
            v1_units[k] = b  # the same words; the 2017 edition's line breaks are kept throughout
            continue
        if a:
            v1_units[k] = a
        refs = [r for r in pdftext.lawrefs(e2.units[k]['notes'] if k in e2.units else []) if r in post]
        refs.sort(key=lambda r: when[r])
        if not refs:
            events.setdefault(switch, {})[k] = (b, [])
            log.append((k, 'publisher', switch))
            continue
        # Several new laws on one provision: its wording between them is not in either edition.
        for r in refs[:-1]:
            if when[r] != when[refs[-1]]:
                events.setdefault(when[r], {})[k] = (dict(b or a, text=(b or a)['text'].split('\n')[0] + '\n'
                                                          + PLACEHOLDER + '\n'), [law_key(r)])
        events.setdefault(when[refs[-1]], {})[k] = (b, [law_key(r) for r in refs if when[r] == when[refs[-1]]])
        log.append((k, ', '.join(law_label(r) for r in refs), when[refs[-1]]))

    versions = [{
        'from': first_day, 'source_url': e1.url, 'sha256': e1.sha, 'units': v1_units,
        'note': ('The revised edition LRO 1/2010, whose list of laws ends with Act 1 of 2007 (the Child Protection '
                 f'Act, commenced {first_day}); dated by that commencement. The publisher\'s index lists this '
                 'edition as current until 30 December 2016, with Acts 34 of 2011 and 15 of 2014 as amending it.'),
    }]
    for d in sorted(events):
        changes = {k: v[0] for k, v in sorted(events[d].items())}
        credits = {k: v[1] for k, v in sorted(events[d].items()) if v[1]}
        unexplained = sorted(k for k, v in events[d].items() if not v[1])
        note = ('Reconstructed from the 2017 revised edition (LRO 1/2017): each provision whose marginal note there '
                'names a law the 2010 edition does not list takes its 2017 wording on that law\'s commencement date.')
        if unexplained:
            note += (f' On {switch} the 2017 edition became current in the publisher\'s index; its other differences '
                     f'from the 2010 edition ({len(unexplained)} provisions) carry no note and are the publisher\'s.')
        versions.append({'from': d, 'source_url': e2.url, 'sha256': e2.sha, 'changes': changes, 'credits': credits,
                         'note': note})
    # The last version must be the 2017 edition exactly.
    state = dict(versions[0]['units'])
    for v in versions[1:]:
        for k, u in v['changes'].items():
            if u is None:
                state.pop(k, None)
            else:
                state[k] = u
    if state != t2:
        bad = [k for k in set(state) | set(t2) if state.get(k) != t2.get(k)]
        raise SystemExit(f'penal-code: the rebuilt last version differs from the 2017 edition in {bad[:10]}')

    later = cur['penal-code'][1:]
    parts['20-penal-code'] = {
        'acts': [{
            'slug': 'penal-code', 'short': 'Penal Code', 'title': 'Penal Code (Ch. 84)', 'url': e2.url,
            'first_law': None, 'earlier_laws': earlier, 'versions': versions,
        }],
        'laws': pc_laws,
        'sources': [
            {'name': 'Bahamas Laws On-line: Penal Code, Ch. 84, revised edition LRO 1/2010 (PDF)', 'url': e1.url,
             'sha256': e1.sha, 'retrieved': S.RETRIEVED, 'requests': 1, 'licence': LICENCE,
             'notes': 'Text layer read directly (no OCR). Current in the point-in-time index up to 2016-12-30.'},
            {'name': 'Bahamas Laws On-line: Penal Code, Ch. 84, revised edition LRO 1/2017 (PDF)', 'url': e2.url,
             'sha256': e2.sha, 'retrieved': S.RETRIEVED, 'requests': 1, 'licence': LICENCE,
             'notes': 'Text layer read directly (no OCR). Current in the point-in-time index from 2016-12-31 to the '
                      'retrieval day; _3 answers 403.'},
        ],
        'decisions': [
            f'Penal Code: two dated consolidations from the publisher\'s point-in-time index: LRO 1/2010 (listed up to '
            f'2016-12-30) and LRO 1/2017 (listed from 2016-12-31). The first is dated {first_day}, the commencement '
            'of the last law in its list of laws (Act 1 of 2007, the Child Protection Act), and credited to the '
            'publisher as the oldest version available.',
            'Penal Code: a provision whose words differ between the editions and whose marginal note in LRO 1/2017 '
            'names a law not in LRO 1/2010\'s list of laws takes its LRO 1/2017 wording on that law\'s commencement '
            'date (from the index\'s "amended by" rows, else its Acts by Year page), credited to that law. '
            f'{sum(1 for x in log if x[1] != "publisher")} provisions are credited this way.',
            f'Penal Code: the other {sum(1 for x in log if x[1] == "publisher")} provisions whose words differ carry '
            'no such note (corrected cross-references, removed short-title years, punctuation and the typesetting of '
            'each edition); they are committed by the publisher as unexplained on 2016-12-31.',
            'Penal Code: provisions with the same words in both editions keep the 2017 edition\'s paragraph breaks in '
            'every version, so only wording changes show in the history.',
            'Penal Code: the 2010 edition prints the law "29 of 1953" as "29 or 1953"; it is read as Act 29 of 1953.',
        ] + [
            f'Penal Code: {law_label(r)} ({pc_laws[law_key(r)].get("title", "title not given")}) has no commencement '
            f'date on the site; its {sum(1 for x in log if law_label(r) in x[1])} provisions are dated {switch}, '
            'the day the first consolidation containing them became current, and its commit says so.'
            for r in post if when[r] == switch and r not in index_dates and r not in known
        ] + [
            f'Penal Code: {r["title"].replace("amended by... ", "")} (No. {r["number"]}, commenced {r["commenced"]}) '
            'is not in any consolidation the site serves (the current one is LRO 1/2017), so it is not in this '
            'history; today\'s official consolidation is the 2017 edition.'
            for r in later
        ],
    }
    if report:
        for x in log:
            print(*x)
    return parts, notice


def country(notice: str) -> dict:
    return {
        'country': {
            'code': 'BS', 'name': 'The Bahamas', 'slug': 'bahamas', 'lang': 'en', 'tz': 'America/Nassau',
            'future_branch': 'future',
            'publisher': {'name': 'Government of The Bahamas, Bahamas Laws On-line (Statute Law of The Bahamas)',
                          'email': 'publisher@laws-bahamas-gov-bs.invalid'},
            'default_in_force_rule': {
                'text': ('Each law is dated by the "Date Commenced" the publisher\'s act index or its Acts by Year '
                         'list gives for it; no date is derived from publication.'),
                'source': S.INDEX},
            'licence_note': (f'Bahamas Laws On-line, Government of The Bahamas: "{notice}" '
                             '(the site\'s Copyright page; its page metadata names the Isle of Man Attorney General\'s '
                             'Chambers, a leftover from the iLAWSSYNC software). This repository is private.'),
        },
        'sources': [
            {'name': 'Bahamas Laws On-line: act index by letter, point in time', 'url': S.INDEX,
             'retrieved': S.RETRIEVED, 'requests': len(S.INDEX_PAGES), 'licence': LICENCE,
             'notes': ('POST pointintime_post=YYYY-MM-DD and submit4=<letter>; lists the consolidation current on '
                       'that day and the amending acts made since, with commencement dates. Pages read: '
                       + ', '.join(f'{l} on {d}' for l, d in S.INDEX_PAGES) + '.')},
            {'name': 'Bahamas Laws On-line: Acts by Year', 'url': S.YEARS, 'retrieved': S.RETRIEVED,
             'requests': len(S.YEAR_PAGES), 'licence': LICENCE,
             'notes': 'POST year=YYYY; titles and commencement dates. Years read: '
                      + ', '.join(str(y) for y in S.YEAR_PAGES) + '.'},
            {'name': 'Bahamas Laws On-line: Copyright', 'url': S.COPYRIGHT, 'retrieved': S.RETRIEVED, 'requests': 1,
             'licence': LICENCE, 'notes': 'The site\'s copyright statement, quoted in the README and licence note.'},
            {'name': 'Bahamas Laws On-line: Constitution (Amendment) Act, 2017 (PDF)', 'url': S.AMENDING_PDF,
             'sha256': sha(S.AMENDING_PDF), 'retrieved': S.RETRIEVED, 'requests': 1, 'licence': LICENCE,
             'notes': 'A scanned image with no text layer; not read (no OCR).'},
        ],
        'decisions': [
            'Sources: only laws.bahamas.gov.bs, read directly (it answers without a bot challenge, and its robots.txt '
            'allows /cms/images/LEGISLATION/); at most 3 requests a second.',
            'Text: each consolidation PDF\'s own text layer; running heads, page feet, footnotes and footnote markers, '
            'and Part, Book and Title headings are dropped; marginal headings become each provision\'s first line; '
            'quotes and dashes are normalised to ASCII; end-of-line hyphens are removed when the joined word occurs '
            'elsewhere in these texts and kept when the hyphenated form does, or either half is capitalised.',
            'Every date is a commencement date from the publisher\'s own index; no publication date is used.',
        ],
        'ai_use': ['none: no model wrote or changed any legal text, date or credit; parsing is deterministic code.'],
    }


def write_json(path: Path, obj) -> None:
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=False) + '\n', encoding='utf-8',
                   newline='\n')
    tmp.replace(path)


def main(argv: list[str]) -> None:
    parts, notice = build(report='--report' in argv)
    (HERE / 'corpus.d').mkdir(exist_ok=True)
    write_json(HERE / 'corpus.json', country(notice))
    for name, part in parts.items():
        write_json(HERE / 'corpus.d' / f'{name}.json', part)
    for name, part in parts.items():
        for a in part['acts']:
            print(name, a['slug'], len(a['versions']), 'versions', [v['from'] for v in a['versions']])


if __name__ == '__main__':
    main(sys.argv[1:])
