"""Sardinia (lexifina/italy-sardinia-law), gitlaw-scraper-dell, 2026-10-30. Private: never published.

Source: the Regione Autonoma della Sardegna's "Banca dati giuridica" (leggiregionali.regione.sardegna.it), "banca dati
delle versioni vigenti delle leggi regionali": every regional law since 1949 (2,607), each as one born-digital PDF of
its current text with the editor's notes at the end. JSON catalogue at /regional-laws/front-office/search, PDF at
/regional-laws/front-office/<id>/files/pdf. robots.txt: none (the SPA answers with its HTML). Terms
(www.regione.sardegna.it/note-legali): non-commercial use, cite "Regione Sardegna"; texts are not official (BURAS is).

    python -X utf8 scripts/world-law/it_sardinia.py fetch            # catalogue + every PDF, oldest first
    python -X utf8 scripts/world-law/it_sardinia.py parse <docs-date> [part ...]
    python -X utf8 scripts/world-law/it_sardinia.py publish <docs-date> [part ...]
    python -X utf8 scripts/world-law/it_sardinia.py loop <docs-date>  # parse + publish each part once all its PDFs are cached
    python -X utf8 scripts/world-law/it_sardinia.py letters <part>
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import it_fetch  # noqa: E402
import it_regions as R  # noqa: E402

SLUG = 'sardinia'
HOST = 'leggiregionali.regione.sardegna.it'
BASE = f'https://{HOST}/'
API = f'{BASE}regional-laws/front-office'
PART_SIZE = 50
CAT = it_fetch.CACHE / 'sardinia-catalogue.json'

SRC = {
    'host': HOST,
    'publisher': 'Regione Autonoma della Sardegna, Banca dati giuridica delle leggi regionali',
    'short': 'the Banca dati giuridica of the Regione Autonoma della Sardegna',
    'url': BASE,
    'licence': 'Legge 633/1941, art. 5 (official acts are not protected); site terms (www.regione.sardegna.it/'
               'note-legali): use for non-commercial purposes with the source "Regione Sardegna" and its URL cited.',
    'licence_note': 'Fonte: Regione Autonoma della Sardegna, Banca dati giuridica delle leggi regionali, '
                    'https://leggiregionali.regione.sardegna.it/',
    'source_notes': 'The current text of every regional law in the database, one PDF each, read from the PDF\'s text '
                    'layer.',
    'in_force_rule': 'Statuto speciale per la Sardegna (legge costituzionale 26 febbraio 1948, n. 3), art. 33: a '
                     'regional law enters into force on the fifteenth day after its publication in the Bollettino '
                     'Ufficiale, unless the law sets another term.',
    'in_force_source': 'https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge.costituzionale:1948-02-26;3',
    'history': 'current-only',
    'history_note': ' (the database holds only the version in force, "versione vigente", with editor\'s notes on '
                    'past changes)',
    'in_force_only': False,
    'no_statute': True,
    'scope_note': ('The Statute of Autonomy (Statuto speciale per la Sardegna, legge costituzionale 26 febbraio 1948, '
                   'n. 3) is a constitutional law of the Italian State and is not published in this database, so it '
                   'is not included here. Laws the database marks as repealed in full are left out, and so, for now, '
                   'are the 308 laws whose PDF prints the editor notes inside the text (mostly of the 1990s), and the '
                   'few laws whose text a second, independent reader of the PDF could not confirm line by line; '
                   'regulations are not included.'),
    'source_md': ('The Banca dati giuridica of the Regione Autonoma della Sardegna, <https://leggiregionali.regione.sardegna.it/>, '
                  '"the database of the versions in force of the regional laws". For each regional law since 1949 it '
                  'publishes one PDF of its current text, with the editor\'s notes on each change at the end. Each '
                  'act here is the text of that PDF, read from its text layer; the editor\'s notes and their markers '
                  'are left out.'),
    'files_md': ('`lr-1977-001/art-005.md` is Articolo 5 of legge regionale n. 1 of 1977; `art-005-bis.md` Articolo '
                 '5 bis; `intestazione.md` holds the title, the publication line and the promulgation formula. '
                 'Headings of titles and chapters stand in the file of the article that follows them.'),
    'official_md': ('The database says its texts have documentary value only ("I testi pubblicati hanno solo valore di '
                    'documentazione"); the official texts are those published in the Bollettino Ufficiale della '
                    'Regione Autonoma della Sardegna (BURAS).'),
    'terms_md': ('The Region\'s legal notes (https://www.regione.sardegna.it/note-legali) allow its content to be '
                 'downloaded and used for non-commercial purposes, with the source "Regione Sardegna" and its URL '
                 'cited, and say that nothing may be reproduced for profit. This repository is free and '
                 'non-commercial, and cites the source.'),
}

DECISIONS = [
    'Current-only: each act is the current text the Banca dati giuridica publishes for the law, as one "oldest '
    'version available" commit dated the retrieval day (the database has no dated past versions).',
    'Text is read from each PDF\'s text layer (PyMuPDF): lines of the body font are joined into paragraphs by their '
    'vertical spacing; across a page break a line ending in ".", ";" or ":" ends its paragraph. Superscript note '
    'markers and the editor\'s notes after the body are left out.',
    'Units: intestazione (title, publication line, promulgation formula) and one file per "Art." heading; other '
    'centred headings (Titolo, Capo, the article\'s rubric) go in the file of the article they stand in or before. '
    'A repeated article number gets the suffix -dupN.',
    'Laws the database marks as repealed in full ("* Legge abrogata ..." under the title) are left out; every other '
    'law in the database is included, budget and accounts laws too, except the 308 laws whose PDF the database '
    'generates from older XML/SGML records (catalogue fileType other than "AKN"): those print the editor notes '
    'inline in the body font and are left out until a reader separates them.',
]
AI_USE = ['A model (Claude) wrote the fetch and parse code and chose the layout; it wrote no law text. Every word of '
          'law comes from the Region\'s PDFs.']


# ---------------------------------------------------------------- fetch

def catalogue(fetch: bool = False) -> list[dict]:
    if fetch or not CAT.exists():
        out = []
        for p in range(100):
            s = json.loads(it_fetch.get(f'{API}/search?page={p}&size=200'))
            out += s['content']
            if s['last']:
                break
        CAT.write_text(json.dumps(out, ensure_ascii=False), encoding='utf-8')
    cat = json.loads(CAT.read_text(encoding='utf-8'))
    return sorted(cat, key=lambda x: (tuple(x['date']), int(re.sub(r'\D', '', x['number']) or 0), x['number']))


def pdf_url(e: dict) -> str:
    return f'{API}/{e["id"]}/files/pdf'


def cached(url: str) -> bytes | None:
    p = it_fetch.path_for(url)
    return p.read_bytes() if p.exists() else None


def fetch():
    cat = catalogue(fetch=True)
    R.say('catalogue', len(cat))
    n = 0
    for e in cat:
        if cached(pdf_url(e)) is not None:
            continue
        R.wait_cpu()
        it_fetch.get(pdf_url(e), timeout=180)
        n += 1
        if n % 50 == 0:
            R.say('fetched', n)
    R.say('done', n)


# ---------------------------------------------------------------- parse (PyMuPDF)

ART = re.compile(r'^Art\.\s*(\d+)\s*(bis|ter|quater|quinquies|sexies|septies|octies|novies|nonies|decies|undecies|'
                 r'duodecies|terdecies|quaterdecies)?\s*\.?\s*(\d+)?\s*$', re.I)
BODY_MIN = 10.0   # body font is ~11.9 pt; note markers 9.5, note numbers 8.3


def spans_of(b: bytes) -> list[tuple]:
    """(page, y0, x0, size, text) for every span, plus the notes start (page, y) or None."""
    import pymupdf
    d = pymupdf.open(stream=b, filetype='pdf')
    out = []
    for pn, pg in enumerate(d):
        for blk in pg.get_text('dict')['blocks']:
            for ln in blk.get('lines', []):
                for s in ln['spans']:
                    if s['text'].strip():
                        out.append((pn, round(s['bbox'][1], 1), round(s['bbox'][0], 1), s['size'], s['text'],
                                    round(s['bbox'][3], 1), round(pg.rect.width, 1)))
    notes = [(p, y) for p, y, x, sz, t, *_ in out if sz < 9 and x < 85 and t.strip().isdigit()]
    return out, (min(notes) if notes else None)


def parse_pdf(b: bytes) -> dict | None:
    sp, notes = spans_of(b)
    body = [s for s in sp if s[3] >= BODY_MIN and (notes is None or (s[0], s[1]) < (notes[0], notes[1] - 2))]
    # group spans into lines: same page and (nearly) same baseline
    body.sort(key=lambda s: (s[0], s[5], s[2]))
    lines = []
    for s in body:
        if lines and lines[-1]['page'] == s[0] and abs(lines[-1]['y1'] - s[5]) < 3:
            lines[-1]['text'] += s[4]
            lines[-1]['x1max'] = max(lines[-1]['x1max'], s[2])
        else:
            lines.append({'page': s[0], 'y0': s[1], 'y1': s[5], 'x': s[2], 'x1max': s[2], 'text': s[4], 'w': s[6]})
    for ln in lines:
        ln['text'] = R.clean_line(ln['text'])
    lines = [ln for ln in lines if ln['text']]
    if not lines:
        return None
    # centred lines: start well right of the body margin
    margin = min(ln['x'] for ln in lines)
    for ln in lines:
        ln['centred'] = ln['x'] > margin + 60
    # paragraphs
    paras = []
    prev = None
    for ln in lines:
        new = True
        if prev is not None and ln['centred'] and prev['centred'] and prev['page'] == ln['page'] \
                and not ART.match(prev['text']) and not ART.match(ln['text']):
            new = ln['y0'] - prev['y1'] > 6          # a centred title wrapped over two lines
        elif prev is not None and not ln['centred'] and not prev['centred']:
            if prev['page'] == ln['page']:
                new = ln['y0'] - prev['y1'] > 6
            else:
                new = bool(re.search(r'[.;:]$', prev['text']))
        if new:
            paras.append({'text': ln['text'], 'centred': ln['centred']})
        else:
            paras[-1]['text'] += ' ' + ln['text']
        prev = ln
    units, order = {}, []
    cur, seen = 'intestazione', Counter()
    units[cur] = {'label': 'Intestazione', 'kind': 'preamble', 'lines': []}
    order.append(cur)
    pending = []   # centred headings before the next article
    for p in paras:
        t = re.sub(r' {2,}', ' ', p['text']).strip()
        if p['centred'] and re.fullmatch(r'Articolo unico\.?', t, re.I):
            cur = 'art-unico'
            units[cur] = {'label': 'Articolo unico', 'kind': 'art', 'lines': pending + [t]}
            order.append(cur)
            pending = []
            continue
        m = ART.match(t) if p['centred'] else None
        if m:
            num, suf, sub = m.group(1), (m.group(2) or '').lower(), m.group(3)
            key = f'art-{int(num):03d}' + (f'-{suf}' if suf else '') + (f'-{int(sub)}' if sub else '')
            seen[key] += 1
            if seen[key] > 1:
                key += f'-dup{seen[key]}'
            label = f'Art. {num}' + (f' {suf}' if suf else '') + (f'.{sub}' if sub else '')
            cur = key
            units[cur] = {'label': label, 'kind': 'art', 'lines': pending + [t]}
            order.append(cur)
            pending = []
            continue
        if p['centred'] and cur != 'intestazione' and not units[cur]['lines'][1:]:
            units[cur]['lines'].append(t)          # rubric right under the heading
        elif p['centred'] and cur != 'intestazione':
            pending.append(t)                        # heading of the next title/chapter
        else:
            if pending:
                units[cur]['lines'] += pending
                pending = []
            units[cur]['lines'].append(t)
    if pending:
        units[cur]['lines'] += pending
    out = {}
    for k in order:
        u = units[k]
        if u['lines']:
            out[k] = {'label': u['label'], 'kind': u['kind'], 'text': '\n'.join(u['lines']) + '\n'}
    if not any(k.startswith('art-') for k in out):
        # a law printed without "Art." headings (articolo unico or a table law): one unit for the whole body
        pass
    return {'units': out}


# ---------------------------------------------------------------- parts

MONTHS = ['gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio', 'agosto', 'settembre', 'ottobre',
          'novembre', 'dicembre']


REPEALED = re.compile(r'^\* *Legge (?:interamente )?abrogata', re.M | re.I)


def plan() -> list[tuple[str, list]]:
    cat = catalogue()
    return [(f'30-leggi-{i // PART_SIZE + 1:02d}', cat[i:i + PART_SIZE]) for i in range(0, len(cat), PART_SIZE)]


def act_slug(e: dict, used: set) -> str:
    y = e['date'][0]
    n = re.sub(r'[^0-9a-z]+', '-', e['number'].lower()).strip('-') or '0'
    n = re.sub(r'^\d+', lambda m: m.group().zfill(3), n)
    s, k = f'lr-{y}-{n}', 2
    while s in used:
        s, k = f'lr-{y}-{n}-{k}', k + 1
    used.add(s)
    return s


def build_part(name: str, members: list, docs_date: str) -> dict | None:
    used, _ = R.used_slugs(SLUG, name)
    acts, laws = [], {}
    for e in members:
        b = cached(pdf_url(e))
        if b is None:
            return None
        if e['fileType'] != 'AKN':
            continue        # older XML/SGML-sourced PDFs print the editor's notes inline: not read yet
        p = parse_pdf(b)
        if p is None or not p['units']:
            continue
        if REPEALED.search(p['units'].get('intestazione', {}).get('text', '')):
            continue        # repealed in full: the database marks it "* Legge abrogata ..." under the title
        y, m, d = e['date']
        iso = f'{y:04d}-{m:02d}-{d:02d}'
        slug = act_slug(e, used)
        t = re.sub(r'\s+', ' ', e['title'] or '').strip()
        title = f'Legge regionale {d} {MONTHS[m - 1]} {y}, n. {e["number"]}' + (f' - {t}' if t else '')
        url = f'{BASE}{iso}/{e["number"]}'
        laws[slug] = {'label': f'L.R. {e["number"]}/{y} (Sardegna)', 'title': title, 'kind': 'law', 'enacted': iso,
                      'published': None, 'url': url, 'temporary_until': None, 'restores': None, 'note': None}
        acts.append({'slug': slug, 'short': f'L.R. {e["number"]}/{y}', 'title': title, 'url': url,
                     'first_law': None, 'earlier_laws': [slug],
                     'versions': [{'from': docs_date, 'source_url': pdf_url(e),
                                   'sha256': hashlib.sha256(b).hexdigest(), 'units': p['units'], 'credits': {},
                                   'note': 'Current text in the Banca dati giuridica on the retrieval day (oldest '
                                           'version available here).'}]})
    if not acts:
        return {'country': R.country_block(SLUG, SRC), 'laws': {}, 'acts': []}
    part = {'country': R.country_block(SLUG, SRC), 'laws': laws, 'acts': acts}
    if R.is_first_part(SLUG, name):
        part.update(sources=[R.source_block(SRC, docs_date)], decisions=DECISIONS, ai_use=AI_USE)
    return part


# ---------------------------------------------------------------- independent letters check (pypdf)

def source_letters(b: bytes) -> str:
    """pypdf, not PyMuPDF: the text drawn in the body font (effective size >= 10 pt), up to the first note number
    (a digit run drawn under 9 pt in the left margin), in content-stream order per page."""
    import pypdf
    r = pypdf.PdfReader(io.BytesIO(b))
    chunks = []   # (page, y, text, size, x)
    for pn, pg in enumerate(r.pages):
        def vis(text, cm, tm, font, size, pn=pn):
            if not text.strip():
                return
            eff = abs(size * tm[3] * cm[3]) or abs(size * tm[0] * cm[0])
            x = tm[4] * cm[0] + cm[4]
            y = tm[5] * cm[3] + cm[5]
            chunks.append((pn, y, text, eff, x))
        pg.extract_text(visitor_text=vis)
    h = float(r.pages[0].mediabox.height) if r.pages else 842.0
    notes = [(c[0], h - c[1]) for c in chunks if c[3] < 9 and c[4] < 85 and c[2].strip().isdigit()]
    start = min(notes) if notes else None
    out, heads = [], []
    for c in chunks:
        if c[3] < 10:
            continue
        if start is not None and (c[0], h - c[1]) >= (start[0], start[1] - 12):
            continue
        # centred article headings sit in their own text objects, out of reading order in the stream: kept apart
        (heads if ART.match(c[2].strip()) or re.fullmatch(r'Articolo unico\.?', c[2].strip(), re.I) else out).append(c[2])
    return R.letters(''.join(out)), R.letters(''.join(heads))


def letters_check(slug: str, part_name: str) -> list[str]:
    part = json.loads((R.folder(slug) / 'corpus.d' / f'{part_name}.json').read_text(encoding='utf-8'))
    probs = []
    for act in part['acts']:
        v = act['versions'][0]
        b = cached(v['source_url'])
        if b is None or hashlib.sha256(b).hexdigest() != v['sha256']:
            probs.append(f'{act["slug"]}: source missing or sha256 differs')
            continue
        src, heads = source_letters(b)
        lm = R.letters(''.join(u['text'] for u in v['units'].values()))
        if Counter(src + heads) != Counter(lm):
            ca, cb = Counter(src), Counter(lm)
            probs.append(f'{act["slug"]}: source-only {dict((ca - cb).most_common(6))} corpus-only '
                         f'{dict((cb - ca).most_common(6))}')
            continue
        pos = 0
        for k, un in v['units'].items():
            for line in un['text'].splitlines():
                if ART.match(line) or re.fullmatch(r'Articolo unico\.?', line, re.I):
                    continue
                t = R.letters(line)
                if not t:
                    continue
                i = src.find(t, pos)
                if i < 0:
                    i = src.find(t)
                if i < 0:
                    probs.append(f'{act["slug"]} {k}: a line not found in the source')
                    break
                pos = i + len(t)
    return probs


def _find_pieces(src: str, t: str, pos: int, max_pieces: int = 4, min_piece: int = 12) -> int:
    """End position in src of line t found as at most max_pieces contiguous pieces, each after the previous one
    (pypdf's content stream sometimes puts a heading or a page's next block inside a paragraph). -1 if not."""
    start = pos
    for _ in range(max_pieces):
        i = src.find(t, start)
        if i >= 0:
            return i + len(t)
        lo, hi, at = min_piece, len(t), -1
        while lo <= hi:        # longest prefix of t (>= min_piece letters) found after start
            mid = (lo + hi) // 2
            j = src.find(t[:mid], start)
            if j >= 0:
                lo, at = mid + 1, j
            else:
                hi = mid - 1
        if at < 0:
            return -1
        n = lo - 1
        start, t = at + n, t[n:]
    return -1


def letters_check_pieces(slug: str, part_name: str) -> list[str]:
    """As letters_check (same pypdf reader, same exact letters-and-digits multiset per act), but each line may be
    found in the source in up to 4 in-order pieces of >= 12 letters instead of one run."""
    part = json.loads((R.folder(slug) / 'corpus.d' / f'{part_name}.json').read_text(encoding='utf-8'))
    probs = []
    for act in part['acts']:
        v = act['versions'][0]
        b = cached(v['source_url'])
        if b is None or hashlib.sha256(b).hexdigest() != v['sha256']:
            probs.append(f'{act["slug"]}: source missing or sha256 differs')
            continue
        src, heads = source_letters(b)
        lm = R.letters(''.join(u['text'] for u in v['units'].values()))
        if Counter(src + heads) != Counter(lm):
            probs.append(f'{act["slug"]}: letters differ')
            continue
        pos = 0
        for k, un in v['units'].items():
            for line in un['text'].splitlines():
                if ART.match(line) or re.fullmatch(r'Articolo unico\.?', line, re.I):
                    continue
                t = R.letters(line)
                if not t:
                    continue
                e = _find_pieces(src, t, pos)
                if e < 0:
                    e = _find_pieces(src, t, 0)
                if e < 0:
                    probs.append(f'{act["slug"]} {k}: a line not found in the source in up to 4 pieces')
                    break
                pos = e
    return probs


def readd(dd: str, size: int = 8):
    """Acts left out of the published parts because a line was not found in one run: rebuilt and checked with
    letters_check_pieces, as new parts 40-leggi-NN (the published parts are not touched)."""
    d = R.folder(SLUG) / 'corpus.d'
    left = []
    for ln in (R.folder(SLUG) / 'PROGRESS.md').read_text(encoding='utf-8').splitlines():
        m = re.search(r'(30-leggi-\d+): left out \(letters check disagrees\): (.*)$', ln)
        if m:
            left += [(m.group(1), s.strip()) for s in m.group(2).split(',')]
    used, _ = R.used_slugs(SLUG, '')
    want = {}
    for pname, s in left:
        if s not in used:
            want.setdefault(pname, set()).add(s)
    acts, laws = [], {}
    for pname, members in plan():
        if pname not in want:
            continue
        part = build_part('zz-scratch', members, dd)     # same slugs: the left-out ones are free again
        for a in part['acts']:
            if a['slug'] in want[pname] and a['slug'] not in {x['slug'] for x in acts}:
                acts.append(a)
                laws[a['slug']] = part['laws'][a['slug']]
    R.say('left out', len(left), 'to re-check', len(acts))
    names = []
    for i in range(0, len(acts), PART_SIZE):
        name = f'40-leggi-{i // PART_SIZE + 1:02d}'
        if (d / f'{name}.PUBLISH').exists():
            continue
        chunk = acts[i:i + PART_SIZE]
        R.write_part(SLUG, name, {'country': R.country_block(SLUG, SRC),
                                  'laws': {a['slug']: laws[a['slug']] for a in chunk}, 'acts': chunk})
        names.append(name)
    for i in range(0, len(names), size):
        res = R.publish_batch(SLUG, SRC, names[i:i + size], dd, letters_check_pieces,
                              reader='independent pypdf reader; each line found in order in at most 4 pieces')
        print(res[:400], flush=True)


def part_ready(members: list) -> bool:
    return all(cached(pdf_url(e)) is not None for e in members)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    R.below_normal()
    cmd = sys.argv[1]
    if cmd == 'fetch':
        fetch()
    elif cmd in ('parse', 'publish', 'loop'):
        dd = sys.argv[2]
        only = set(sys.argv[3:])
        while True:
            pending = 0
            for name, members in plan():
                if only and name not in only:
                    continue
                pub = R.folder(SLUG) / 'corpus.d' / f'{name}.PUBLISH'
                if pub.exists() or pub.with_suffix('.EMPTY').exists():
                    continue
                if not part_ready(members):
                    pending += 1
                    if cmd == 'loop':
                        break      # parts publish strictly in order (all are dated the same day)
                    continue
                if cmd in ('parse', 'loop') or not (R.folder(SLUG) / 'corpus.d' / f'{name}.json').exists():
                    part = build_part(name, members, dd)
                    if not part['acts']:
                        (R.folder(SLUG) / 'corpus.d').mkdir(parents=True, exist_ok=True)
                        pub.with_suffix('.EMPTY').write_text('every law of this part is repealed in full\n')
                        R.say(name, 'empty: every law repealed in full')
                        continue
                    R.write_part(SLUG, name, part)
                    R.say(name, 'parsed', len(part['acts']))
                if cmd in ('publish', 'loop'):
                    R.wait_cpu()
                    res = R.publish(SLUG, SRC, name, dd, letters_check)
                    print(name, res[:500], flush=True)
                    if not res.startswith('PUBLISH') and cmd == 'loop' and 'letters check' in res:
                        # leave out the acts the independent reader disagrees with, record them, verify again
                        bad = sorted({p_.split(' ')[0].rstrip(':') for p_ in letters_check(SLUG, name)})
                        pj = json.loads((R.folder(SLUG) / 'corpus.d' / f'{name}.json').read_text(encoding='utf-8'))
                        pj['acts'] = [a for a in pj['acts'] if a['slug'] not in bad]
                        for b_ in bad:
                            pj['laws'].pop(b_, None)
                        R.progress(SLUG, f'{name}: left out (letters check disagrees): {", ".join(bad)}')
                        if pj['acts']:
                            R.write_part(SLUG, name, pj)
                            res = R.publish(SLUG, SRC, name, dd, letters_check)
                            print(name, 'retry', res[:300], flush=True)
                        else:
                            (R.folder(SLUG) / 'corpus.d' / f'{name}.json').unlink()
                            pub.with_suffix('.EMPTY').write_text('every act left out\n')
                            res = 'PUBLISH (empty)'
                    if not res.startswith('PUBLISH'):
                        if cmd == 'loop':
                            raise SystemExit(f'{name} not verified: stopping the loop')
            if cmd != 'loop' or pending == 0:
                break
            time.sleep(120)
    elif cmd == 'readd':      # readd <docs-date>: left-out acts, line-in-pieces check, new parts 40-leggi-NN
        readd(sys.argv[2])
    elif cmd == 'batch':      # batch <docs-date> [size]: every ready unpublished part, verified 8 at a time
        dd = sys.argv[2]
        size = int(sys.argv[3]) if sys.argv[3:] else 8
        todo = []
        for name, members in plan():
            pub = R.folder(SLUG) / 'corpus.d' / f'{name}.PUBLISH'
            if pub.exists() or pub.with_suffix('.EMPTY').exists():
                continue
            if not part_ready(members):
                R.say(name, 'not fetched yet: stop here (parts publish in order)')
                break
            part = build_part(name, members, dd)
            if not part['acts']:
                pub.with_suffix('.EMPTY').write_text('every law of this part is repealed in full\n')
                continue
            R.write_part(SLUG, name, part)
            todo.append(name)
        R.say('to publish', todo)
        for i in range(0, len(todo), size):
            res = R.publish_batch(SLUG, SRC, todo[i:i + size], dd, letters_check)
            print(res[:400], flush=True)
            if not res.startswith(('PUBLISH', 'nothing')):
                raise SystemExit('batch not verified: stopping')
    elif cmd == 'letters':
        pr = letters_check(SLUG, sys.argv[2])
        print('\n'.join(pr[:40]) or 'letters check: clean')
        print(f'{len(pr)} problems')
