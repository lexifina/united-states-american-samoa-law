"""Reads only .cache/ and writes the corpus.d/ parts for the 2024 codes of Suriname (gitlaw-SR).

    python -X utf8 scripts/suriname-law/parse_codes.py

Parts written (each atomically, .tmp then rename):
    corpus.d/20-burgerlijk-wetboek.json      Burgerlijk Wetboek, Boeken 1-8 (S.B. 2024 no. 164)
    corpus.d/30-rechtsvordering.json         Wetboek van Burgerlijke Rechtsvordering (S.B. 2024 no. 170)

Text comes from the official Staatsblad PDFs' own text layer (Word-made PDFs on sris.sr), read with PyMuPDF: no
OCR, no model. Layout: headings and "Artikel N" lines are centred; body lines start at the left margin. A body line
starts a new paragraph when it begins with a list marker ("1.", "a.", "2°") or when its first word would have fitted
at the end of the line before (so that line was a paragraph end). Deterministic: the same cache gives the same bytes.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

import fitz  # PyMuPDF

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import parse as P  # noqa: E402  (norm, cached, sha)

RETRIEVED = '2026-10-29'
SRIS = 'https://www.sris.sr/wp-content/uploads/'
SB_2024_164 = SRIS + '2025/01/S.B-2024-no.-164-Burgerlijk-Wetboek.pdf'
SB_2024_170 = SRIS + '2025/01/S.B.-2024-no.-170-Wetboek-van-Burgerlijke-Rechtsvordering.pdf'
SB_2025_14 = (SRIS + '2025/02/Resolutie-houdende-vaststelling-van-de-inwerkingtreding-van-het-Burgerlijk-Wetboek-'
              'S.B.-2025-no.-14.pdf')
SB_2024_168 = SRIS + '2025/01/S.B.-2024-no.-168-Aanpassingswet-nieuw-Burgerlijk-Wetboek.pdf'
IN_FORCE = '2025-05-01'          # S.B. 2025 no. 14, besluit I
SB_2025_16 = (SRIS + '2025/04/RESOLUTIE-van-6-februari-2025-no.-14.228-24-houdende-plaatsing-staatsblad-republiek-'
              'suriname-thans-geldende-tekst-kiesregeling-S.B.-2025-no.-16.pdf')

TRANS = str.maketrans({'': '°', '˚': '°', '‐': '-', '‑': '-'})
MARKER = re.compile(r'^(\d+[a-z]?\.|\d+[a-z]?°\.?|[a-z]\.|[a-z]\)|\d+[a-z]?\)|[ivx]+\.|-|–|•)(\s|$)')
BARE_MARKER = re.compile(r'^(\d+[a-z]?\.|\d+[a-z]?°\.?|[a-z]\.|[a-z]\)|\d+[a-z]?\))$')
RV_STOP = re.compile(r'^(MEMORIE VAN TOELICHTING|Paramaribo, de \d+)')
ARTIKEL = re.compile(r'^Artikel\s+(\d+|[A-Z])\s*([a-z]{0,3})\.?\s*$')


def norm(s: str) -> str:
    return P.norm(s.translate(TRANS))


# ---------------------------------------------------------------- PDF lines

def body_span(s: dict) -> bool:
    """With footnotes: body text is 12 pt; footnote numbers are 6-8 pt (Courier or Times) and footnotes 9-10 pt.
    Superscript ordinals ("6e februari") are body text."""
    if s['size'] >= 11.5:
        return True
    return bool(s['flags'] & 1) and s['font'].startswith('TimesNewRoman') and s['text'].strip() in ('e', 'ste', 'de')


def page_lines(page, footnotes: bool = False) -> list[dict]:
    """Text lines of one page, top to bottom, with spans on one baseline merged; the running header is dropped.
    footnotes=True drops footnote reference numbers and the footnotes themselves (Kiesregeling)."""
    raw = []
    for b in page.get_text('dict')['blocks']:
        for l in b.get('lines', []):
            spans = [s for s in l['spans'] if s['text'].strip() and (not footnotes or body_span(s))]
            if spans:
                raw.append([l['bbox'][1], spans])
    raw.sort(key=lambda t: (round(t[0], 0), t[1][0]['bbox'][0]))
    merged: list[list] = []
    for y, spans in raw:
        if merged and abs(merged[-1][0] - y) < 3.5:
            merged[-1][1].extend(spans)
        else:
            merged.append([y, list(spans)])
    out = []
    for y, spans in merged:
        spans.sort(key=lambda s: s['bbox'][0])
        text = ''
        prev_x1 = None
        for s in spans:
            if prev_x1 is not None and s['bbox'][0] - prev_x1 > 1.5 and not text.endswith(' '):
                text += ' '
            text += s['text']
            prev_x1 = s['bbox'][2]
        t = norm(text)
        if not t:
            continue
        x0 = min(s['bbox'][0] for s in spans)
        x1 = max(s['bbox'][2] for s in spans)
        bold = all(s['flags'] & 16 for s in spans)
        if y < 50 and re.match(r'^\d{4}\b.*No\.\s*\d+$', t):
            continue                       # running header "2024 -3- No. 164"
        out.append({'page': page.number, 'y': y, 'x0': x0, 'x1': x1, 'text': t, 'bold': bold})
    return out


_MARGINS: dict = {}


def margins(doc) -> dict:
    """Text margins (left, right) per page width: the books are set on Letter and on A4 pages with different
    margins. Left is the most common smallest x0, right the median of the widest line, over pages of 10+ lines."""
    key = doc.name
    if key not in _MARGINS:
        lefts, rights = {}, {}
        for page in doc:
            ls = page_lines(page)
            if len(ls) < 10:
                continue
            w = round(page.rect.width)
            lefts.setdefault(w, []).append(round(min(l['x0'] for l in ls), 1))
            rights.setdefault(w, []).append(max(l['x1'] for l in ls))
        out = {}
        for w in lefts:
            r = sorted(rights[w])
            out[w] = (Counter(lefts[w]).most_common(1)[0][0], r[len(r) // 2])
        _MARGINS[key] = out
    return _MARGINS[key]


def centred(l: dict, m: tuple) -> bool:
    """A centred line: equal gaps to both margins, not a list item."""
    left, right = l['x0'] - m[0], m[1] - l['x1']
    return left > 50 and abs(left - right) < 14 and not MARKER.match(l['text'])


# ---------------------------------------------------------------- hyphenation

def vocabulary(lines: list[dict]) -> Counter:
    """Every word that occurs inside a line (not broken at its end), to decide line-end hyphens."""
    c = Counter()
    for l in lines:
        ws = l['text'].split()
        for w in ws[:-1] if ws and ws[-1].endswith('-') else ws:
            c[re.sub(r'^[^\wÀ-ÿ]+|[^\wÀ-ÿ-]+$', '', w).lower()] += 1
    return c


def join(parts: list[str], vocab: Counter, log: list) -> str:
    out = ''
    for p in parts:
        if not out:
            out = p
            continue
        m = re.search(r'([\wÀ-ÿ-]*[a-zà-ÿ])-$', out)
        if m and re.match(r'^[a-zà-ÿ]', p) and not re.match(r'^(en|of|tot|noch)\b', p):
            head = m.group(1)
            tail = re.match(r'^[\wÀ-ÿ-]+', p).group(0)
            tail_core = re.sub(r'[^\wÀ-ÿ-]+$', '', tail)
            closed = (head + tail_core).lower()
            hyph = (head + '-' + tail_core).lower()
            if vocab[hyph] > vocab[closed]:
                out += p                    # a real hyphen: "procureur-generaal"
                log.append(('keep', head + '-' + tail_core))
            else:
                out = out[:-1] + p          # a word broken at the line end
                log.append(('join', head + tail_core))
        elif out.endswith('-') and re.match(r'^[A-ZÀ-Þ]', p):
            out += p                        # "Nederlands-" / "Antilliaanse"
        elif out.endswith('/'):
            out += p
        else:
            out += ' ' + p
    return out


# ---------------------------------------------------------------- one code

def parse_code(url: str, pages: list[int], key_prefix, label_prefix, vocab: Counter, log: list,
               stop: re.Pattern | None = None, start: re.Pattern | None = None, footnotes: bool = False):
    """Units of one code (or one Book) from the given pages.

    key_prefix/label_prefix: functions of the current book number (or None) giving the unit key prefix and the
    label prefix. Returns (units, structure_lines_by_book, report)."""
    doc = fitz.open(P.cached(url))
    units: dict[str, dict] = {}
    order: list[str] = []
    structure: dict = {}
    report: list[str] = []
    cur = None
    paras: list[list[str]] = []
    prev = None
    book = None

    def flush():
        if cur is None:
            return
        lines = [join(p, vocab, log) for p in paras]
        fixed: list[str] = []
        for l in lines:
            if fixed and BARE_MARKER.match(fixed[-1]):
                fixed[-1] = fixed[-1] + ' ' + l
            else:
                fixed.append(l)
        units[cur]['body'] = fixed

    last_kind = None      # 'heading', 'art' or 'body': the kind of the line before
    last_heading = ''
    for pno in pages:
        page = doc[pno]
        mm = margins(doc)
        m = mm.get(round(page.rect.width)) or mm[min(mm, key=lambda w: abs(w - page.rect.width))]
        right = m[1] + 0.5
        lines = page_lines(page, footnotes)
        title_page = len(lines) < 14 and any(re.match(r'^WET van \d+ \w+ \d{4},?$', x['text']) for x in lines)
        before = None     # the line above on this page
        for l in lines:
            t = l['text']
            gap = l['y'] - before['y'] if before else None
            before = l
            if stop and stop.match(t):
                flush()
                return units, order, structure, report
            mb = re.match(r'^BOEK (\d+)$', t)
            if mb and (l['bold'] or centred(l, m)):
                flush()
                cur = None
                book = int(mb.group(1))
                structure.setdefault(book, [])
                prev, last_kind = None, 'heading'
                continue
            if start is not None and book is None and start.match(t):
                book = 0                    # a code without Books starts at its first chapter heading
            if title_page or book is None:
                continue                    # the enacting formula, and each Book's title page
            ma = ARTIKEL.match(t) if centred(l, m) or l['x0'] - m[0] > 50 else None
            if ma:
                flush()
                num, suf = ma.group(1), ma.group(2)
                if num.isdigit():
                    k = f'{key_prefix(book)}art-{int(num):04d}{suf}'
                else:
                    k = f'{key_prefix(book)}art-{num.lower()}{suf}'
                if k in units:
                    raise SystemExit(f'duplicate article {k} on page {pno}')
                lab = f'{label_prefix(book)}Artikel {num}{suf}'
                units[k] = {'label': lab, 'head': f'# {lab}', 'page': pno}
                order.append(k)
                cur, paras, prev, last_kind = k, [], None, 'art'
                continue
            heading = centred(l, m) or (l['bold'] and l['x0'] > 60) or bool(re.match(r'^§ ?\d+[a-z]?\. ', t))
            if not heading and cur is None and l['x0'] - m[0] > 50 and not MARKER.match(t):
                heading = True              # an off-centre heading line ("Afdeling 1A", Boek 3)
            if heading and cur is not None:
                # inside an article a centred-looking line is a heading only after blank space, never as the first
                # line of the article, and at the top of a page only if it reads like one
                if not paras:
                    heading = False
                elif gap is None:
                    heading = looks_heading(t)
                else:
                    heading = gap > 20 or strong_heading(t)
            if heading:
                flush()
                cur, paras, prev = None, [], None
                if re.search(r'[.;,]$', t) and not looks_heading(t) and last_kind != 'heading':
                    report.append(f'centred line read as heading, page {pno}: {t[:80]}')
                structure.setdefault(book, []).append(t)
                last_heading, last_kind = t, 'heading'
                continue
            if cur is None:
                if last_kind == 'heading' and gap is not None and gap < 20 and not MARKER.match(t):
                    structure.setdefault(book, []).append(t)      # a heading running over two lines
                    last_heading = last_heading + ' ' + t
                    continue
                # text under a heading with no "Artikel": a unit named after the heading
                slug = re.sub(r'[^a-z0-9]+', '-', last_heading.lower()).strip('-')
                k = f'{key_prefix(book)}{slug}'
                if k in units:
                    raise SystemExit(f'duplicate unit {k} on page {pno}')
                lab = f'{label_prefix(book)}{last_heading.capitalize()}'
                units[k] = {'label': lab, 'head': f'# {lab}', 'page': pno}
                order.append(k)
                report.append(f'unit without article number: {k}')
                cur, paras, prev = k, [], None
            new = not paras or prev is None or MARKER.match(t) is not None
            if not new and not prev['text'].endswith('-'):
                first = t.split()[0]
                w = fitz.get_text_length(' ' + first, fontname='tiro', fontsize=12)
                if prev['x1'] + w < right - 2:
                    new = True
            if not new and prev['page'] == l['page'] and l['y'] - prev['y'] > 22:
                new = True
            if new:
                paras.append([t])
            else:
                paras[-1].append(t)
            prev, last_kind = l, 'body'
    flush()
    return units, order, structure, report


def looks_heading(t: str) -> bool:
    return bool(re.match(r'^(Titel|Afdeling|Paragraaf|Onderafdeling|Boek|TITEL|AFDELING|BOEK|HOOFDSTUK)\b', t)
                or re.fullmatch(r'[IVXL]+\.', t) or (t.isupper() and len(t) > 3)
                or not re.search(r'[.;,:]$', t))


def strong_heading(t: str) -> bool:
    """A chapter heading even without blank space above it (the Kiesregeling sets some tight)."""
    return bool(re.match(r'^(HOOFDSTUK|TITEL|AFDELING|BOEK)\b', t)
                or re.fullmatch(r'(Titel|Afdeling|Paragraaf|Onderafdeling) \d+[A-Za-z]*', t)
                or re.match(r'^§ ?\d+[a-z]?\. ', t)
                or (t.isupper() and len(t) > 3 and not re.search(r'[.;,:]$', t)))


def unit_text(u: dict) -> str:
    return '\n'.join([u['head']] + u.get('body', [])) + '\n'


# ---------------------------------------------------------------- Burgerlijk Wetboek

def bw_pages(doc) -> list[int]:
    """Pages holding the law text of Boeken 1-8: from each "BOEK n" title (bold) up to its Memorie van Toelichting."""
    pages, book, inlaw = [], 0, False
    for page in doc:
        if page.number < 2:
            continue
        for l in page_lines(page):
            if l['text'] == 'MEMORIE VAN TOELICHTING':
                inlaw = False
                break
            m = re.match(r'^BOEK (\d+)$', l['text'])
            if m and l['bold'] and int(m.group(1)) == book + 1:
                book += 1
                inlaw = True
        if inlaw or (pages and page.number == pages[-1] + 1 and not inlaw and False):
            pages.append(page.number)
    return pages


def rv_pages(doc) -> list[int]:
    """Pages of the Wetboek van Burgerlijke Rechtsvordering up to its Memorie van Toelichting."""
    pages = []
    for page in doc:
        if any(l['text'] == 'MEMORIE VAN TOELICHTING' for l in page_lines(page)):
            break
        pages.append(page.number)
    return pages


def load_code(which: str):
    """(units in document order, law-text pages, source url) for 'bw', 'rv' or 'kr' (Kiesregeling)."""
    log: list = []
    url = {'bw': SB_2024_164, 'rv': SB_2024_170, 'kr': SB_2025_16}[which]
    doc = fitz.open(P.cached(url))
    if which == 'kr':
        pages = list(range(2, doc.page_count))         # pages 0-1: the Resolutie and a blank page
    else:
        pages = bw_pages(doc) if which == 'bw' else rv_pages(doc)
    vocab = vocabulary([l for p in pages for l in page_lines(doc[p], which == 'kr')])
    if which == 'bw':
        units, order, structure, report = parse_code(url, pages, lambda b: f'boek-{b}-', lambda b: f'Boek {b}, ',
                                                     vocab, log)
    elif which == 'kr':
        units, order, structure, report = parse_code(url, pages, lambda b: '', lambda b: '', vocab, log,
                                                     start=re.compile(r'^HOOFDSTUK\b'), footnotes=True)
    else:
        units, order, structure, report = parse_code(url, pages, lambda b: '', lambda b: '', vocab, log,
                                                     stop=RV_STOP)
    out = {}
    for k in order:
        out[k] = {'label': units[k]['label'], 'kind': 'art', 'text': unit_text(units[k])}
    for b, lines in structure.items():
        if which == 'bw':
            out[f'boek-{b}-indeling'] = {'label': f'Boek {b}: indeling (titels en afdelingen)', 'kind': 'structure',
                                         'text': f'# Boek {b}: indeling\n' + '\n'.join(lines) + '\n'}
        else:
            out.setdefault('indeling', {'label': 'Indeling (boeken, titels en afdelingen)' if which == 'rv' else
                                        'Indeling (hoofdstukken en paragrafen)', 'kind': 'structure',
                                        'text': '# Indeling\n'})
            out['indeling']['text'] += ''.join(l + '\n' for l in ([f'BOEK {b}'] if b else []) + lines)
    load_code.report = report
    load_code.log = log
    return out, pages, url


SRIS_SOURCE = {
    'name': 'Surinaams Rechtsinformatiesysteem (sris.sr)', 'url': 'https://www.sris.sr/',
    'retrieved': RETRIEVED, 'licence': 'Official Staatsblad text; no licence stated',
    'notes': ('Staatsblad PDFs with a born-digital text layer (Microsoft Word). Found through the site\'s WordPress '
              'media listing, https://sris.sr/wp-json/wp/v2/media (1,757 files, read 2026-10-29), which shows no '
              'amending act for either code up to October 2026.')}

COMMON_DECISIONS = [
    'Both 2024 codes took effect on 2025-05-01: Resolutie of 6 February 2025 no. 2909/25 (S.B. 2025 no. 14), '
    'besluit I, fixes that day for S.B. 2024 nos. 164 to 170 (art. 2 lid 3 of the BW wet and art. 1079 lid 3 of the '
    'Rv let the President set it).',
    'No amending act of either code was found in the sris.sr media listing (every Staatsblad PDF the site holds, to '
    'October 2026) or in the DNA lists "Wetten na 2005" and "Wijzigingen na 2005" (read 2026-10-28): each code has '
    'one version, its text as enacted, in force since 2025-05-01. Only bills (ontwerpwetten) are pending, such as '
    'the Ontwerpwet houdende wijziging van het Wetboek van Burgerlijke Rechtsvordering (sris.sr, August 2026).',
    'Paragraphs: the PDFs set every article in lines of about 100 characters. A line starts a new paragraph when it '
    'begins with a list marker ("1.", "a.", "2°") or when its first word would have fitted on the line before; '
    'otherwise lines are joined. A paragraph that ends exactly at the right margin and is followed by an unnumbered '
    'paragraph is therefore joined to it; the words are unaffected.',
    'Line-end hyphens: a word broken at a line end is joined without the hyphen unless the hyphenated form occurs '
    'more often inside lines of the same code than the closed form (kept: "proces-verbaal", "mede-erfgenaam", '
    '"netto-opbrengst", "averij-grosse", "niet-bevrijdende", "aandeelhouder-bestuurde", "rechter-commissaris", '
    '"niet-ontvankelijkheid", "Procureur-generaal").',
    'Headings (Boek, Titel, Afdeling, paragraaf) are kept in indeling units, so article files hold only article '
    'text. The memories van toelichting printed after each Book are not law text and are left out.',
    'Completeness: verify_codes.py reads the law-text pages again with PyMuPDF\'s word extractor and aligns the words '
    'with the units. Every word is in the units in order; the only differences are headings, each Book\'s title '
    'page, the enacting formula and signatures, a line-end join next to a heading, the full stop of the heading '
    '"Artikel 518b." (Boek 8) and the capitalisation of the heading "ALGEMENE SLOTBEPALING" in its unit\'s title.',
]

AI_USE = [
    'Claude Opus 5.5 (claude-opus-5-5, Claude Code) found the sources and wrote fetch.py, parse_codes.py and '
    'verify_codes.py. No legal text in these parts was written, transcribed or OCRed by a model: all text comes from '
    'the PDF text layers via PyMuPDF.',
]


def write_part(name: str, part: dict) -> None:
    d = HERE / 'corpus.d'
    d.mkdir(exist_ok=True)
    tmp = d / (name + '.json.tmp')
    tmp.write_text(json.dumps(part, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    tmp.replace(d / (name + '.json'))


def requests_to(host: str) -> int:
    n = 0
    for line in (P.CACHE / 'requests.jsonl').read_text(encoding='utf-8').splitlines():
        if host in json.loads(line)['url']:
            n += 1
    return n


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    src = dict(SRIS_SOURCE, requests=requests_to('sris.sr'))
    res_sha = P.sha(SB_2025_14)
    # Burgerlijk Wetboek
    units, pages, url = load_code('bw')
    print('bw pages', len(pages), 'units', len(units), load_code.report)
    bw = {
        'laws': {'sb-2024-164': {
            'label': 'S.B. 2024 no. 164',
            'title': 'Wet van 5 december 2024, houdende vaststelling van een nieuw Burgerlijk Wetboek (Burgerlijk Wetboek)',
            'kind': 'law', 'enacted': '2024-12-05', 'published': '2025-01-15', 'url': SB_2024_164,
            'temporary_until': None, 'restores': None, 'note': None}},
        'sources': [src],
        'acts': [{
            'slug': 'burgerlijk-wetboek', 'short': 'BW',
            'title': 'Burgerlijk Wetboek (Boeken 1-8)',
            'url': SB_2024_164, 'first_law': 'sb-2024-164', 'earlier_laws': [],
            'versions': [{
                'from': IN_FORCE, 'source_url': SB_2024_164, 'sha256': P.sha(SB_2024_164), 'units': units,
                'credits': {},
                'note': ('The new Burgerlijk Wetboek, Boeken 1 to 8, as enacted by the Wet van 5 december 2024 '
                         '(S.B. 2024 no. 164, uitgegeven 15 januari 2025), in force on 1 May 2025 by Resolutie '
                         'S.B. 2025 no. 14 (source sha256 ' + res_sha + ').')}],
        }],
        'decisions': [
            'Burgerlijk Wetboek: the act is the new code of 2024, Boeken 1 to 8 (S.B. 2024 no. 164), from the day it '
            'took effect, 2025-05-01. It replaced the code of 1860 (G.B. 1860 no. 4), whose last official '
            'consolidation (dna.sr) runs only to 2005 and whose later amending acts (2016, S.B. 2022 no. 34) are '
            'scans without a text layer, so the old code\'s history is not built.',
            'Burgerlijk Wetboek: Boek 7A is left out. It is what remains of the old code\'s Derde Boek (hire-'
            'purchase, loans and other contracts), renumbered and amended by the Aanpassingswet nieuw Burgerlijk '
            'Wetboek (S.B. 2024 no. 168, art. I), which gives only the changes; its full text would have to be '
            'replayed onto the 2005 consolidation of the old code across the 2016 and 2022 scans.',
            'Burgerlijk Wetboek: each Book numbers its own articles, so unit keys are boek-<n>-art-<number>, zero-'
            'padded to four digits (boek-1-art-0025a). The closing provision of Boek 8, printed under the heading '
            '"ALGEMENE SLOTBEPALING" without an article number, is the unit boek-8-algemene-slotbepaling.',
            'Burgerlijk Wetboek: the enacting wet\'s own articles 1 and 2 (adoption of the Books, citation title, '
            'commencement by presidential decree) are not part of the code text and are left out.',
        ] + COMMON_DECISIONS,
        'ai_use': AI_USE,
    }
    write_part('20-burgerlijk-wetboek', bw)
    # Wetboek van Burgerlijke Rechtsvordering
    units, pages, url = load_code('rv')
    print('rv pages', len(pages), 'units', len(units), load_code.report)
    rv = {
        'laws': {'sb-2024-170': {
            'label': 'S.B. 2024 no. 170',
            'title': ('Wet van 5 december 2024, houdende vaststelling van het nieuwe Wetboek van Burgerlijke '
                      'Rechtsvordering (Wetboek van Burgerlijke Rechtsvordering)'),
            'kind': 'law', 'enacted': '2024-12-05', 'published': '2025-01-13', 'url': SB_2024_170,
            'temporary_until': None, 'restores': None, 'note': None}},
        'sources': [src],
        'acts': [{
            'slug': 'rechtsvordering', 'short': 'Rv',
            'title': 'Wetboek van Burgerlijke Rechtsvordering',
            'url': SB_2024_170, 'first_law': 'sb-2024-170', 'earlier_laws': [],
            'versions': [{
                'from': IN_FORCE, 'source_url': SB_2024_170, 'sha256': P.sha(SB_2024_170), 'units': units,
                'credits': {},
                'note': ('The new Wetboek van Burgerlijke Rechtsvordering as enacted by the Wet van 5 december 2024 '
                         '(S.B. 2024 no. 170, uitgegeven 13 januari 2025), in force on 1 May 2025 by Resolutie '
                         'S.B. 2025 no. 14 (source sha256 ' + res_sha + ').')}],
        }],
        'decisions': [
            'Wetboek van Burgerlijke Rechtsvordering: the act is the new code of 2024 (S.B. 2024 no. 170) from the day '
            'it took effect, 2025-05-01. The code it replaced (G.B. 1935, consolidated by dna.sr to 2005, amended by '
            'S.B. 2008 no. 19 and others) is not built: its amending acts after 2005 were not all found with a text '
            'layer.',
            'Wetboek van Burgerlijke Rechtsvordering: the code numbers its articles straight through its four Books '
            '(Artikel A and B, then 1 to 1079, with gaps where numbers are unused), so unit keys are art-<number> '
            'zero-padded to four digits, and art-a and art-b. Book, title and section headings are in '
            'rechtsvordering/indeling.md.',
        ] + COMMON_DECISIONS,
        'ai_use': AI_USE,
    }
    write_part('30-rechtsvordering', rv)
    # Kiesregeling (official current text, S.B. 2025 no. 16)
    units, pages, url = load_code('kr')
    print('kr pages', len(pages), 'units', len(units), load_code.report)
    kr_laws = {
        'sb-1987-62': ('S.B. 1987 no. 62', 'Wet van 29 september 1987, houdende regels voor de verkiezing van leden '
                       'voor de volksvertegenwoordigende lichamen in Suriname (Kiesregeling)', 'law', '1987-09-29', None),
        'sb-1987-70': ('S.B. 1987 no. 70', 'Decreet van 17 oktober 1987, tot wijziging van de Kiesregeling', 'decree',
                       '1987-10-17', None),
        'sb-1987-71': ('S.B. 1987 no. 71', 'Decreet van 19 oktober 1987, tot wijziging van de Kiesregeling', 'decree',
                       '1987-10-19', None),
        'sb-1987-83': ('S.B. 1987 no. 83', 'Decreet van 23 november 1987, tot wijziging van de Kiesregeling', 'decree',
                       '1987-11-23', None),
        'sb-1987-84': ('S.B. 1987 no. 84', 'Decreet van 23 november 1987, tot wijziging van de Kiesregeling', 'decree',
                       '1987-11-23', None),
        'sb-2005-6': ('S.B. 2005 no. 6', 'Wet van 3 maart 2005, tot wijziging van de Kiesregeling', 'law',
                      '2005-03-03', None),
        'sb-2010-29': ('S.B. 2010 no. 29', 'Wet van 10 maart 2010, tot wijziging van de Kiesregeling', 'law',
                       '2010-03-10', None),
        'sb-2019-55': ('S.B. 2019 no. 55', 'Wet van 23 mei 2019, tot wijziging van de Kiesregeling', 'law',
                       '2019-05-23', None),
        'sb-2023-158': ('S.B. 2023 no. 158', 'Wet van 25 oktober 2023, houdende nadere wijziging van de Kiesregeling',
                        'law', '2023-10-25', None),
        'sb-2024-59': ('S.B. 2024 no. 59', 'Wet van 31 mei 2024, houdende regels ter nadere wijziging van de '
                       'Kiesregeling', 'law', '2024-05-31', '2024-05-31'),
        'sb-2025-8': ('S.B. 2025 no. 8', 'Wet van 15 januari 2025, houdende nadere wijziging van de Kiesregeling',
                      'law', '2025-01-15', '2025-01-20'),
    }
    kr = {
        'laws': {k: {'label': a, 'title': b, 'kind': c, 'enacted': d, 'published': e, 'url': {
                         'sb-2019-55': SRIS + '2019/08/S.B.-2019-no.-55-Wijziging-Kiesregeling.pdf',
                         'sb-2023-158': SRIS + '2023/10/SB-2023-158-nadere-wijziging-van-de-Kiesregeling.pdf',
                         'sb-2024-59': SRIS + '2024/06/S.B.-2024-no.-59-wijziging-van-de-Kiesregeling.pdf',
                         'sb-2025-8': SRIS + '2025/04/S.B.-2025-no.-8-Wet-Kiesregeling-wijziging.pdf'}.get(k),
                     'temporary_until': None, 'restores': None, 'note': None}
                 for k, (a, b, c, d, e) in kr_laws.items()},
        'sources': [src],
        'acts': [{
            'slug': 'kiesregeling', 'short': 'Kiesregeling',
            'title': 'Kiesregeling',
            'url': SB_2025_16, 'first_law': None, 'earlier_laws': list(kr_laws),
            'versions': [{
                'from': '2025-02-07', 'source_url': SB_2025_16, 'sha256': P.sha(SB_2025_16), 'units': units,
                'credits': {},
                'note': ('The official current text placed in the Staatsblad by Resolutie of 6 February 2025 no. '
                         '14.228/24 (S.B. 2025 no. 16, uitgegeven 7 February 2025): the Kiesregeling (S.B. 1987 '
                         'no. 62) as amended by S.B. 1987 nos. 70, 71, 83 and 84, S.B. 2005 no. 6, S.B. 2010 no. 29, '
                         'S.B. 2019 no. 55, S.B. 2023 no. 158, S.B. 2024 no. 59 and S.B. 2025 no. 8.')}],
        }],
        'decisions': [
            'Kiesregeling: one version, the official current text S.B. 2025 no. 16, dated 2025-02-07, the day it was '
            'uitgegeven, and committed by the publisher as the oldest version available. The last amendment it '
            'contains, S.B. 2025 no. 8 (uitgegeven 20 January 2025, in force the next day by its art. II lid 2), '
            'took effect on 2025-01-21; the version is dated from its own source, the republication, rather than '
            'from that day.',
            'Kiesregeling: earlier versions are not built. The amending acts S.B. 2019 no. 55 and S.B. 2023 no. 158 '
            'and the 2005 consolidation exist online only as scans (the sris.sr copies carry an OCR layer made by the '
            'publisher\'s scanner software), and no OCR is used for this record; S.B. 2024 no. 59 and S.B. 2025 '
            'no. 8 have a born-digital text layer, but they give only the changed provisions, not the text before '
            'them.',
            'Kiesregeling: no amending act after S.B. 2025 no. 8 was found: the DNA list "Wijzigingen na 2005" ends '
            'with it (read 2026-10-29) and the sris.sr listing holds only later Kiesbesluit decrees (S.B. 2025 '
            'nos. 25, 26, 38, 39), which are not part of the Kiesregeling.',
            'Kiesregeling: S.B. 2025 no. 16 footnotes each article with the act that inserted or changed it ("Gew. '
            'bij S.B. 2023 no. 158"). The footnotes and their reference numbers are left out of the text (they are '
            'publisher notes, not law), and the opening paragraph that names the act and its amendments is the '
            'act\'s title, not a provision.',
            'Kiesregeling: chapter and paragraph headings are in kiesregeling/indeling.md. Its paragraphs and line-end '
            'hyphens are handled as for the 2024 codes, and verify_codes.py kr finds every 12-point word of the '
            'text in the units, in order, apart from headings and the opening paragraph.',
        ],
        'ai_use': AI_USE,
    }
    write_part('40-kiesregeling', kr)


if __name__ == '__main__':
    main()
