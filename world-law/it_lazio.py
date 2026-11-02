"""Lazio (italy-lazio-law) for git-for-law, gitlaw-scraper-dell, 2026-10-30. Private (world-law-ops).

Source: Consiglio regionale del Lazio, "Leggi regionali (testo coordinato)" (www.consiglio.regione.lazio.it,
?vw=leggiregionali&sv=vigente): one HTML page per regional law with its coordinated text and the editor's notes on
each change. The "testo storico" view is the text as published, not dated versions, so the build is current-only.
The Statute (legge statutaria 11 novembre 2004, n. 1) is only a PDF (the Consiglio's consolidated text of October
2013, with the 2012 and 2013 amendments).

    python -X utf8 scripts/world-law/it_lazio.py list            # year listings -> .cache/index.json
    python -X utf8 scripts/world-law/it_lazio.py fetch           # every law page, oldest first
    python -X utf8 scripts/world-law/it_lazio.py parse <docs-date> [part ...]
    python -X utf8 scripts/world-law/it_lazio.py publish <docs-date> [part ...]
    python -X utf8 scripts/world-law/it_lazio.py loop <docs-date>     # parse + publish every complete part
    python -X utf8 scripts/world-law/it_lazio.py letters <part>
"""
from __future__ import annotations

import hashlib
import html as htmlmod
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import it_fetch  # noqa: E402
import it_regions as R  # noqa: E402

SLUG = 'lazio'
HOST = 'www.consiglio.regione.lazio.it'
BASE = f'https://{HOST}/'
STATUTO_PDF = BASE + 'binary/consiglio_regionale/tbl_contenuti/Statuto_Regione_Lazio.pdf'
STATUTO_PAGE = BASE + '?vw=contenutidettaglio&id=7'
PART_SIZE = 50
FIRST_YEAR, LAST_YEAR = 1970, 2026
INDEX = R.folder(SLUG) / '.cache' / 'index.json'

SRC = {
    'host': HOST,
    'publisher': 'Consiglio regionale del Lazio, Leggi regionali (testo coordinato)',
    'short': 'the Consiglio regionale del Lazio',
    'url': BASE + '?vw=leggiregionali',
    'licence': 'L. 633/1941 art. 5: official acts are not protected. Site footer: "Copyright 2016 - Consiglio regionale '
               'del Lazio"; images under CC BY-NC-SA 2.0. No permission requirement for the texts.',
    'licence_note': 'Fonte: Consiglio regionale del Lazio, Leggi regionali (testo coordinato), '
                    'https://www.consiglio.regione.lazio.it/?vw=leggiregionali',
    'source_notes': 'One HTML page per regional law (coordinated text with editor\'s notes); the Statute as the '
                    'Consiglio\'s consolidated PDF (October 2013). Current text only.',
    'in_force_rule': 'Statuto della Regione Lazio, art. 39: a regional law enters into force on the fifteenth day after '
                     'its publication in the Bollettino ufficiale, unless it sets another term. (Not applied here: '
                     'every text is the current one, dated the retrieval day.)',
    'history': 'current-only',
    'in_force_only': False,
    'scope_note': ('Every regional law the database lists is included except those it marks as repealed as a whole or '
                   'whose text it omits ("Omissis"); provisions repealed later are printed in square brackets, as the '
                   'source prints them. Regulations are not included yet.'),
    'history_note': ' (its "testo storico" is the text as first published, with no dated intermediate versions)',
    'source_md': ('The regional-law database of the Consiglio regionale del Lazio, <https://www.consiglio.regione.lazio.it/?vw=leggiregionali>, '
                  '"Leggi regionali (testo coordinato)": one page per regional law with its coordinated text and the editor\'s notes '
                  'naming the law behind each change. The Statute (legge statutaria 11 novembre 2004, n. 1) is taken from the '
                  'Consiglio\'s PDF of its consolidated text (October 2013, with the amendments of 2012 and 2013) on the Statute page, '
                  'reading the PDF\'s text layer, one paragraph per line. Laws whose whole text the database marks as repealed are left out.'),
    'files_md': ('`statuto/art-001.md` is Articolo 1 of the Statute; `lr-2004-008/art-005.md` is Articolo 5 of legge '
                 'regionale 3 agosto 2004, n. 8. `intestazione.md` holds what the page prints before the first article '
                 '(title, summary, preamble); `note.md` the editor\'s notes ("Note:") that the page prints after the text. '
                 'Tables are one cell per line.'),
    'official_md': 'The Consiglio regionale del Lazio states on every page: "Il testo non ha valore legale; rimane, dunque, '
                   'inalterata l\'efficacia degli atti legislativi originari." The texts with legal value are those '
                   'published in the Bollettino ufficiale della Regione Lazio.',
    'terms_md': ('The Consiglio regionale del Lazio\'s site carries "Copyright 2016 - Consiglio regionale del Lazio" and '
                 'releases its images under Creative Commons BY-NC-SA 2.0; it sets no condition on reusing the law texts, '
                 'which are official acts outside copyright under art. 5 above. This repository is free and non-commercial '
                 'and credits the source. No images, marks or logos of the Consiglio are used.'),
}


def list_url(year: int, page: int) -> str:
    u = f'{BASE}?vw=leggiregionali&sv=vigente&materia=&numeroLegge=&annoLegge={year}&testo=&invia=+Cerca+'
    return u if page == 1 else f'{BASE}?vw=leggiregionali&sv=vigente&annoLegge={year}&pg={page}'


def law_url(i: int) -> str:
    return f'{BASE}?vw=leggiregionalidettaglio&id={i}&sv=vigente'


def dec(b: bytes) -> str:
    return b.decode('cp1252', 'replace')


MONTHS = {m: i + 1 for i, m in enumerate(['gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio',
                                          'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre'])}


def listing(year: int) -> list[dict]:
    out, page, pages = [], 1, 1
    while page <= pages:
        b = it_fetch.get(list_url(year, page))
        t = dec(b or b'')
        i = t.find('</form>', t.find('formLeggiRegolamenti'))
        seg = t[i:t.find('<footer', i)]
        for m in re.finditer(r"<li>(.*?)<br><a href='\?vw=leggiregionalidettaglio&amp;id=(\d+)&amp;sv=vigente'[^>]*>(.*?)</a>",
                             seg, re.S):
            head = ' '.join(htmlmod.unescape(re.sub(r'<[^>]+>', ' ', m.group(1))).split())
            ttl = ' '.join(htmlmod.unescape(re.sub(r'<[^>]+>', ' ', m.group(3))).split())
            hm = re.search(r'Legge n\D*(\d+)\s+del\s+(\d{1,2})\s+(\w+)\s+(\d{4})', head)
            out.append({'id': int(m.group(2)), 'head': head, 'title': ttl,
                        'n': int(hm.group(1)) if hm else None,
                        'date': (f'{int(hm.group(4)):04d}-{MONTHS.get(hm.group(3).lower(), 0):02d}-{int(hm.group(2)):02d}'
                                 if hm and hm.group(3).lower() in MONTHS else None), 'year': year})
        ps = [int(x) for x in re.findall(r'annoLegge=%d&amp;pg=(\d+)' % year, seg)]
        pages = max([pages] + ps)
        page += 1
    return out


def do_list():
    idx = json.loads(INDEX.read_text(encoding='utf-8')) if INDEX.exists() else {}
    for y in range(FIRST_YEAR, LAST_YEAR + 1):
        if str(y) in idx and y < LAST_YEAR:
            continue
        idx[str(y)] = listing(y)
        R.say(f'{y}: {len(idx[str(y)])} laws')
        INDEX.parent.mkdir(parents=True, exist_ok=True)
        INDEX.write_text(json.dumps(idx, ensure_ascii=False, indent=0), encoding='utf-8')


def entries() -> list[dict]:
    idx = json.loads(INDEX.read_text(encoding='utf-8'))
    seen, out = set(), []
    for y in sorted(idx, key=int):
        for e in sorted(idx[y], key=lambda e: (e['date'] or '', e['n'] or 0, e['id'])):
            if e['id'] in seen:
                continue
            seen.add(e['id'])
            out.append(e)
    return out


def do_fetch():
    R.wait_cpu()
    it_fetch.get(STATUTO_PDF)
    n = 0
    for e in entries():
        if not it_fetch.path_for(law_url(e['id'])).exists():
            it_fetch.get(law_url(e['id']))
            n += 1
            if n % 50 == 0:
                R.say(f'fetched {n} law pages (now {e["year"]})')
                R.wait_cpu()
    R.say(f'fetch done: {n} new pages')


# ---------------------------------------------------------------- parse

BLOCK = re.compile(r'(?i)<br\s*/?>|</?(p|div|tr|li|h[1-6]|table|tbody|ul|ol)\b[^>]*>|</td>')


def content_html(t: str) -> str | None:
    k = t.find("<div id='contenuto_legge'>")
    if k < 0:
        return None
    e = t.find("<p id='firma_legge'>", k)
    if e < 0:
        e = t.find('</page>', k)
    return t[k + len("<div id='contenuto_legge'>"):e]


def html_lines(h: str) -> list[str]:
    # the pages print quoted words as raw "<<Omissis>>" / "<< parole >>" (not entities), and a bare "<" before a space
    # or digit: text, not markup (fixed 2026-10-30 evening)
    h = re.sub(r'<<([^<>]{0,200})>>', lambda m: '&lt;&lt;' + m.group(1) + '&gt;&gt;', h)
    h = re.sub(r'<(?=[\s<=\d])', '&lt;', h)
    h = re.sub(r'(?s)<(script|style)\b.*?</\1>', ' ', h)
    h = re.sub(r'(?s)<!--.*?-->', ' ', h)
    h = BLOCK.sub('\n', h)
    h = re.sub(r'<[^>]+>', '', h)
    h = htmlmod.unescape(h)
    return [x for x in (R.clean_line(x) for x in h.split('\n')) if x]


ART = re.compile(r'(?i)^\[?\s*art(?:icolo|\.)?\s*(\d+)\s*[-.]?\s*(bis|ter|quater|quinquies|sexies|septies|octies|novies|'
                 r'nonies|decies|undecies|duodecies|terdecies|quaterdecies|quinquiesdecies|sexiesdecies)?\s*\.?'
                 r'(?:\s*\(\d+[a-z]?\))*\s*\]?$')   # "[Art. 1" (repealed, in brackets), "Art. 2 (2)" (with note marks)
ART_UNICO = re.compile(r'(?i)^articolo\s+unico\.?$')


def split_units(lines: list[str]) -> dict:
    units: dict[str, dict] = {}
    cur_k, cur_lab, cur = 'intestazione', 'Intestazione', []
    seen = Counter()

    def put():
        if cur:
            k = cur_k
            if k in units:
                seen[k] += 1
                k = f'{k}-dup{seen[k] + 1}'
            units[k] = {'label': cur_lab, 'kind': {'intestazione': 'preamble', 'note': 'other'}.get(cur_k, 'art'),
                        'text': '\n'.join(cur) + '\n'}
    for ln in lines:
        m = ART.match(ln)
        if (m or ART_UNICO.match(ln)) and cur_k != 'note':
            put()
            if m:
                suf = (m.group(2) or '').lower()
                cur_k = f'art-{int(m.group(1)):03d}' + (f'-{suf}' if suf else '')
                cur_lab = f'Articolo {int(m.group(1))}' + (f' {suf}' if suf else '')
            else:
                cur_k, cur_lab = 'art-001-unico', 'Articolo unico'
            cur = [ln]
            continue
        if re.match(r'(?i)^note\s*:?$', ln) and cur_k != 'note':
            put()
            cur_k, cur_lab, cur = 'note', 'Note', [ln]
            continue
        cur.append(ln)
    put()
    return units


def parse_law(b: bytes) -> dict | None:
    t = dec(b)
    h = content_html(t)
    if h is None:
        return None
    lines = html_lines(h)
    if not lines:
        return None
    units = split_units(lines)
    if not any(u['kind'] == 'art' for u in units.values()):
        units = {'testo': {'label': 'Testo', 'kind': 'art', 'text': '\n'.join(lines) + '\n'}}
    title = ''
    m = re.search(r"<h4 id='titolo_contenuto'>(.*?)</h4>", t, re.S)
    if m:
        title = R.clean_line(htmlmod.unescape(re.sub(r'<[^>]+>', ' ', m.group(1))))
    bur = re.search(r'Data BUR</strong>:\s*(\d\d)/(\d\d)/(\d{4})', t)
    nbur = re.search(r'Numero BUR</strong>:\s*([^<]+)<', t)
    body = ' '.join(lines[:8] + [u['text'] for u in units.values() if u['kind'] == 'art'][:1])
    return {'units': units, 'title': title,
            'bur': f'{bur.group(3)}-{bur.group(2)}-{bur.group(1)}' if bur else None,
            'bur_n': R.clean_line(nbur.group(1)) if nbur else None,
            # left out: a law the page says is repealed as a whole, or whose text the page omits ("Omissis")
            'repealed': (bool(re.search(r'(?i)\b(l\s?egge|testo)\s+(interamente\s+)?abrogat[ao]\b', ' '.join(lines[:6])))
                         and sum(1 for u in units.values() if u['kind'] == 'art') <= 1)
            or ('testo' in units and len(units['testo']['text']) < 1500
                and bool(re.search(r'(?i)omissis|abrogat', units['testo']['text']))), '_': body[:0]}


# Statute: the PDF's text blocks, one paragraph each

STRUCT_LINE = re.compile(r'^(TITOLO|CAPO|SEZIONE|S O M M A R I O|SOMMARIO)')
FOOTNOTE = re.compile(r'^\d{1,2}\s+(Comma|Articolo|Lettera|Legge|Parol|Rubrica|Capo|Titolo|Periodo|Alinea)')


def statuto_paragraphs(b: bytes) -> list[str]:
    """The PDF's text lines joined into paragraphs: a new paragraph at an article heading, a heading in parentheses,
    a comma or letter number, a structural heading, a footnote, or after a line ending a sentence."""
    import pymupdf
    d = pymupdf.open(stream=b, filetype='pdf')
    lines = []
    for page in d:
        for ln in page.get_text().splitlines():
            x = R.clean_line(ln)
            if not x or x == str(page.number + 1):
                continue   # blank lines and the page number
            m = re.match(r'^(Art\.\s*\d+(?:\s*(?:bis|ter|quater))?)\s+(\(.*)$', x)
            if m:
                lines += [m.group(1), m.group(2)]
            else:
                lines.append(x)
    out = []
    for x in lines:
        prev = out[-1] if out else None
        new = (prev is None or ART.match(x) or x.startswith('(') or re.match(r'^\d+\.(\s|$)', x)
               or re.match(r'^[a-z]\)\s', x) or STRUCT_LINE.match(x) or FOOTNOTE.match(x)
               or re.match(r'^Art\.\s*\d+\s', x) or ART.match(prev) or prev.endswith((')', ':', ';', '.'))
               or prev.isupper())
        if prev is not None and re.fullmatch(r'\d+\.', prev):
            new = False   # a comma number alone on its line joins its text
        if new:
            out.append(x)
        else:
            out[-1] = prev + ' ' + x
    return out


def statuto_units(b: bytes) -> dict:
    return split_units(statuto_paragraphs(b))


def act_slug(e: dict) -> str:
    return f'lr-{e["year"]}-{(e["n"] or 0):03d}'


def iso(d):
    return d if d and re.fullmatch(r'\d{4}-\d\d-\d\d', d) else None


def live_entries() -> list[dict]:
    out = []
    for e in entries():
        p = it_fetch.path_for(law_url(e['id']))
        if not p.exists():
            out.append({**e, 'pending': True})
            continue
        r = parse_law(p.read_bytes())
        if r is None or r['repealed']:
            continue
        out.append(e)
    return out


def plan() -> list[tuple[str, list]]:
    """Published parts keep their members; every other live law fills the unpublished part names in order, 50 each
    (so a parser fix never moves a law into a second part)."""
    live = live_entries()
    d = R.folder(SLUG) / 'corpus.d'
    taken, pub = set(), set()
    for q in sorted(d.glob('30-leggi-*.PUBLISH')):
        pub.add(q.stem)
        for a in json.loads(q.with_suffix('.json').read_text(encoding='utf-8'))['acts']:
            taken.add(int(re.search(r'[?&]id=(\d+)', a['url']).group(1)))
    rest = [e for e in live if e['id'] not in taken]
    parts = [('10-statuto', ['statuto'])] + [(n, []) for n in sorted(pub)]
    k = 0
    for i in range(0, len(rest), PART_SIZE):
        while True:
            k += 1
            if f'30-leggi-{k:02d}' not in pub:
                break
        parts.append((f'30-leggi-{k:02d}', rest[i:i + PART_SIZE]))
    return parts


def build_part(name: str, members: list, docs_date: str) -> dict | None:
    acts, laws = [], {}
    used = set(R.used_slugs(SLUG, name)[0])
    for m in members:
        if m == 'statuto':
            b = it_fetch.path_for(STATUTO_PDF).read_bytes()
            units = statuto_units(b)
            key = 'ls-2004-001'
            laws[key] = {'label': 'Legge statutaria 11 novembre 2004, n. 1', 'title': 'Nuovo Statuto della Regione Lazio',
                         'kind': 'law', 'enacted': '2004-11-11', 'published': '2004-11-11', 'url': STATUTO_PAGE,
                         'temporary_until': None, 'restores': None, 'note': None}
            acts.append({'slug': 'statuto', 'short': 'Statuto', 'title': 'Statuto della Regione Lazio (legge statutaria '
                         '11 novembre 2004, n. 1, "Nuovo Statuto della Regione Lazio")', 'url': STATUTO_PAGE,
                         'first_law': None, 'earlier_laws': [key],
                         'versions': [{'from': docs_date, 'source_url': STATUTO_PDF,
                                       'sha256': hashlib.sha256(b).hexdigest(), 'units': units, 'credits': {},
                                       'note': 'The Consiglio\'s consolidated text (PDF of October 2013, with the 2012 '
                                               'and 2013 amendments), read on the retrieval day.'}]})
            continue
        if m.get('pending'):
            return None
        b = it_fetch.path_for(law_url(m['id'])).read_bytes()
        r = parse_law(b)
        slug = act_slug(m)
        k = 2
        while slug in used:
            slug, k = f'{act_slug(m)}-{k}', k + 1
        used.add(slug)
        n, d = m['n'], m['date']
        dd = f'{int(d[8:10])} {list(MONTHS)[int(d[5:7]) - 1]} {d[:4]}' if iso(d) else str(m['year'])
        label = f'Legge regionale {dd}, n. {n}'
        laws[slug] = {'label': label, 'title': r['title'] or label, 'kind': 'law', 'enacted': iso(d),
                      'published': iso(r['bur']), 'url': law_url(m['id']), 'temporary_until': None,
                      'restores': None, 'note': None}
        acts.append({'slug': slug, 'short': f'l.r. {n}/{m["year"]}', 'title': label + (f' - {r["title"]}' if r['title'] else ''),
                     'url': law_url(m['id']), 'first_law': None, 'earlier_laws': [slug],
                     'versions': [{'from': docs_date, 'source_url': law_url(m['id']),
                                   'sha256': hashlib.sha256(b).hexdigest(), 'units': r['units'], 'credits': {},
                                   'note': 'Coordinated text on the retrieval day (oldest version available here).'}]})
    part = {'country': R.country_block(SLUG, SRC), 'laws': laws, 'acts': acts}
    if R.is_first_part(SLUG, name):
        part.update(sources=[R.source_block(SRC, docs_date)], decisions=DECISIONS, ai_use=AI_USE)
    return part


DECISIONS = [
    'Current-only: each act is the coordinated text the Consiglio regionale del Lazio publishes on the retrieval day, '
    'as one "oldest version available" commit dated that day, naming the act itself as the earlier law.',
    'Units: intestazione (everything the page prints before the first article heading, including its summary), one '
    'file per article (from its "Art. N" heading), and note (the editor\'s notes printed after the text). Tables are one '
    'cell per line. The closing line "Il testo non ha valore legale ..." is left out where the page sets it apart (newer pages); on older pages it stays at the end of the text.',
    'Laws whose page says the whole law is repealed ("legge abrogata"), and laws whose text the page omits ("Omissis", mostly old budget laws), are left out.',
    'Statute: the Consiglio\'s consolidated PDF (October 2013), its text lines joined into paragraphs; page numbers are '
    'left out, footnotes stay where the PDF prints them.',
]
AI_USE = ['A model (Claude) wrote the fetch and parse code and chose the layout; it wrote no law text. Every word of '
          'law comes from the Consiglio regionale del Lazio\'s pages and PDF.']


# ---------------------------------------------------------------- independent letters check

def source_letters(url: str, b: bytes) -> str:
    if url.endswith('.pdf'):
        import io
        from pypdf import PdfReader
        txt = []
        for no, pg in enumerate(PdfReader(io.BytesIO(b)).pages, 1):
            for ln in (pg.extract_text() or '').split('\n'):
                if ln.strip() != str(no):
                    txt.append(ln)
        return R.letters(' '.join(txt))
    import lxml.html
    t = dec(b).replace('<<', '«').replace('>>', '»')   # raw quote marks in the pages, read as text
    k = t.find("<div id='contenuto_legge'>")
    e = t.find("<p id='firma_legge'>", k)
    if e < 0:
        e = t.find('</page>', k)
    frag = lxml.html.fromstring('<div>' + t[k + len("<div id='contenuto_legge'>"):e] + '</div>')
    for bad in frag.xpath('//script|//style'):
        bad.drop_tree()
    return R.letters(frag.text_content())


def letters_check(slug: str, part_name: str) -> list[str]:
    part = json.loads((R.folder(slug) / 'corpus.d' / f'{part_name}.json').read_text(encoding='utf-8'))
    probs = []
    for act in part['acts']:
        v = act['versions'][0]
        b = it_fetch.path_for(v['source_url']).read_bytes()
        if hashlib.sha256(b).hexdigest() != v['sha256']:
            probs.append(f'{act["slug"]}: sha256 differs')
            continue
        src = source_letters(v['source_url'], b)
        lm = R.letters(''.join(u['text'] for u in v['units'].values()))
        if Counter(src) != Counter(lm):
            ca, cb = Counter(src), Counter(lm)
            probs.append(f'{act["slug"]}: source-only {dict((ca - cb).most_common(6))} corpus-only '
                         f'{dict((cb - ca).most_common(6))}')
            continue
        pos = 0
        for k, un in v['units'].items():
            t = R.letters(un['text'])
            i = src.find(t, pos)
            if i < 0:
                probs.append(f'{act["slug"]} {k}: text not found in order in the source')
                break
            pos = i + len(t)
    return probs


def parse_and_publish(dd: str, only=()):
    for name, members in plan():
        if only and name not in only:
            continue
        if (R.folder(SLUG) / 'corpus.d' / f'{name}.PUBLISH').exists():
            continue
        if name != '10-statuto' and len(members) < PART_SIZE and any(m.get('pending') for m in members):
            continue
        part = build_part(name, members, dd)
        if part is None:
            continue
        R.write_part(SLUG, name, part)
        R.wait_cpu()
        print(name, R.publish(SLUG, SRC, name, dd, letters_check)[:300], flush=True)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    R.below_normal()
    cmd = sys.argv[1]
    if cmd == 'list':
        do_list()
    elif cmd == 'fetch':
        do_fetch()
    elif cmd == 'parse':
        dd = sys.argv[2]
        for name, members in plan():
            if sys.argv[3:] and name not in sys.argv[3:]:
                continue
            part = build_part(name, members, dd)
            if part:
                R.write_part(SLUG, name, part)
                R.say(name, len(members))
    elif cmd == 'publish':
        dd = sys.argv[2]
        for name in sys.argv[3:] or R.part_names(SLUG):
            if not (R.folder(SLUG) / 'corpus.d' / f'{name}.PUBLISH').exists():
                print(name, R.publish(SLUG, SRC, name, dd, letters_check)[:400], flush=True)
    elif cmd == 'loop':
        dd = sys.argv[2]
        while True:
            parse_and_publish(dd)
            if all(not m.get('pending') for _, ms in plan()[1:] for m in ms) and INDEX.exists():
                parse_and_publish(dd)
                break
            time.sleep(120)
    elif cmd == 'batch':      # batch <docs-date> [size]: parse every unpublished part, then publish 8 at a time
        dd = sys.argv[2]
        size = int(sys.argv[3]) if sys.argv[3:] else 8
        pl = plan()
        for q in (R.folder(SLUG) / 'corpus.d').glob('30-leggi-*.json'):
            if not q.with_suffix('.PUBLISH').exists():
                q.unlink()      # unpublished parts are rebuilt from the plan (no stale slugs in used_slugs)
        todo = []
        for name, members in pl:
            if (R.folder(SLUG) / 'corpus.d' / f'{name}.PUBLISH').exists() or not members:
                continue
            part = build_part(name, members, dd)
            if part and part['acts']:
                R.write_part(SLUG, name, part)
                todo.append(name)
        R.say('to publish', todo)
        for i in range(0, len(todo), size):
            print(R.publish_batch(SLUG, SRC, todo[i:i + size], dd, letters_check)[:400], flush=True)
    elif cmd == 'letters':
        pr = letters_check(SLUG, sys.argv[2])
        print('\n'.join(pr[:40]) or 'letters check: clean')
        print(f'{len(pr)} problems')
