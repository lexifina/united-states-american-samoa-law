"""gitlaw-scraper-dell (2026-10-31): parse one Sri Lanka Gazette Extraordinary (Part IV (A), Provincial Councils) PDF,
English text, into the statute it publishes. Private.

    python -X utf8 lk_prov_parse.py <pdf>        # print the units and the furniture left out

Layout (learned from the Uva, Northern and Central PDFs): a masthead on the first page (the Sinhala/Tamil title in a
legacy font, "The Gazette of the Democratic Socialist Republic of Sri Lanka", "EXTRAORDINARY", "No. 1444/20 - THURSDAY,
MAY 11, 2006", "(Published by Authority)", "PART IV (A) - PROVINCIAL COUNCILS", "Provincial Council(s) Notifications");
running heads at the top of later pages (the legacy-font line, "PART IV (A) - GAZETTE EXTRAORDINARY OF THE ...", the page
label "2 A"); footers (job numbers "07-981/1", "PG 3610 - 27 (07/2017)", "This Gazette Extraordinary can be downloaded
from www.documents.gov.lk", "PRINTED AT THE DEPARTMENT OF GOVERNMENT PRINTING"). Marginal notes sit in a narrow column
left or right of the body. Nothing is reworded: spans of a line are joined and spaces collapsed; a line-end hyphen
before a lower-case letter is joined.
"""
from __future__ import annotations

import re
import statistics
import sys
from pathlib import Path

import pymupdf

LEGACY_FONT = re.compile(r'^(MSTT|FM|Bamini|Kaputa|DL-|Thibus|Baamini|Sarukesi|Tharu)', re.I)
RUNNING = re.compile(r'GAZETTE\s+EXTRA\s*ORDINARY\s+OF\s+THE|^PART\s+IV\s*\(\s*A\s*\)|^\d{1,3}\s*[A-Z]$|^[A-Z]\s*\d{1,3}$'
                     r'|downloaded\s+from|PRINTED\s+AT\s+THE|^\d{1,3}\s*A\s*PG\b|\bPG\s+\d{3,5}\b'
                     r'|^\d{2}\s*[-–—]\s*\d{2,5}(/\d+)?$|^\d{1,3}A$', re.I)
MAST = re.compile(r'The\s+Gazette\s+of\s+the\s+Democratic|^EXTRAORDINARY$|^\(Published\s+by\s+Authority\)$'
                  r'|^No\.\s*\d{3,4}\s*/\s*\d{1,3}\b|^PART\s+IV|PROVINCIAL\s+COUNCILS?\s+NOTIFICATIONS?$'
                  r'|^Provincial\s+Councils?\s+Notifications?$', re.I)
HEAD = re.compile(r'^(A\s+)?STATUTE\b|^(THE\s+)?STATUTE\s+(OF|TO|No)\b|STATUTE\s+No\.?\s*\d|^AN?\s+STATUTE', re.I)
ENACT = re.compile(r'\bB\s*E\s+it\s+(?:therefore\s+)?(?:enacted|passed|made|resolved)\b', re.I)
SHORT1 = re.compile(r'^0?1\s*\.\s*(?:\(1\)\s*)?(?:Short\s+title\s*[:.\-–—]\s*)?(?:This|These|The)\b.{0,120}?\b(?:cited|known|defin|called|named|'
                    r'referred|introduced|identified|termed)', re.I)
# A statute whose section 1 is printed "(1) This Statute may be cited as ..." (no "1."); used only when no statute in
# the issue has a "1." short title, so a subsection (1) of another statute never starts a statute of its own.
SHORT1B = re.compile(r'^\(1\)\s*(?:This|These|The)\b.{0,120}?\b(?:cited|known|called|named)', re.I)
NUMONLY = re.compile(r'^(\d{1,3}[A-Z]?\s*\.(?:\s*\(\s*[0-9a-zA-Z]{1,5}\s*\))*|(?:\(\s*[0-9a-zA-Z]{1,5}\s*\)\s*)+|\d+\.\d+)$')
SECNO = re.compile(r'^(\d{1,3}[A-Z]?)\s*\.\s*(?!\d)')
PARA = re.compile(r'^(\(\s*[0-9a-zA-Z]{1,5}\s*\)|\d{1,3}[A-Z]?\s*\.\s|\d+\.\d+\s|[ivx]{1,5}\.\s|[a-z]\.\s|•)')


def norm(s: str) -> str:
    s = s.replace(' ', ' ').replace(' ', ' ').replace(' ', ' ').replace(' ', ' ')
    s = s.replace('­', '')
    return re.sub(r'\s+', ' ', s).strip()


def lines_of(page) -> list[dict]:
    out = []
    for b in page.get_text('dict')['blocks']:
        for l in b.get('lines', []):
            if abs(l['dir'][1]) > 0.1:
                continue
            allspans = [s for s in l['spans'] if s['text'].strip()]
            if not allspans:
                continue
            # one printed line may hold a marginal note and body text: split where spans are far apart
            pieces: list[list[dict]] = [[allspans[0]]]
            for s in allspans[1:]:
                gap_l, gap_r = pieces[-1][-1]['bbox'][2], s['bbox'][0]
                lead = ''.join(x['text'] for x in pieces[-1]).strip()
                small = abs(pieces[-1][-1]['size'] - s['size']) >= 1.5  # a note (8pt) beside body text (10pt)
                if (gap_r - gap_l > 6 and (gap_l < 0.21 * page.rect.width or gap_r > 0.78 * page.rect.width or small)
                        or gap_r - gap_l > 1.5 and small)                         and not NUMONLY.match(lead):
                    pieces.append([s])
                else:
                    pieces[-1].append(s)
            for raw in pieces:
                legacy = any(LEGACY_FONT.match(s['font']) for s in raw)
                spans = [s for s in raw if not LEGACY_FONT.match(s['font'])]
                text = ''
                for j, s in enumerate(spans):
                    if j and s['bbox'][0] - spans[j - 1]['bbox'][2] > 1.0 and not text.endswith(' '):
                        text += ' '
                    text += s['text']
                text = norm(text)
                x0, y0 = min(s['bbox'][0] for s in raw), min(s['bbox'][1] for s in raw)
                x1, y1 = max(s['bbox'][2] for s in raw), max(s['bbox'][3] for s in raw)
                out.append({'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1, 'text': text, 'legacy': legacy or not text,
                            'raw': norm(' '.join(s['text'] for s in raw)),
                            'size': max(s['size'] for s in (spans or raw)),
                            'bold': bool(spans) and all('bold' in s['font'].lower() or s['flags'] & 16 for s in spans)})
    # merge pieces of one printed line (same baseline) left to right
    out.sort(key=lambda l: (round(l['y1']), l['x0']))
    rows: list[dict] = []
    for l in out:
        r = rows[-1] if rows else None
        W = page.rect.width
        gap = l['x0'] - r['x1'] if r else 0
        if r and abs(r['y1'] - l['y1']) < 2.5 and -2 < gap < 25 and not r['legacy'] and not l['legacy']                 and not (gap >= 1.5 and abs(r['size'] - l['size']) >= 1.5)                 and (gap < 6 or (r['x1'] > 0.21 * W and l['x0'] < 0.78 * W) or NUMONLY.match(r['text'])):
            r['text'] = norm(r['text'] + ' ' + l['text'])
            r['x1'] = max(r['x1'], l['x1'])
            r['bold'] = r['bold'] and l['bold']
            continue
        rows.append(dict(l))
    return rows


def margins(rows: list[dict], width: float, cols: set | None = None) -> set[int]:
    """Indexes of rows in a marginal-note column. A narrow row (<= 150pt) in the outer fifth of the page is a note when
    a body row (>= 180pt wide) shares its line and lies wholly on its other side; then narrow rows starting at the same
    x (within 3pt) and within 14pt above or below a note are notes too (the rest of a multi-line note)."""
    narrow = [i for i, r in enumerate(rows) if not r['legacy'] and r['x1'] - r['x0'] <= 150
              and (r['x1'] < 0.30 * width or r['x0'] > 0.70 * width) and not NUMONLY.match(r['text'])]
    body = [r for r in rows if not r['legacy'] and r['x1'] - r['x0'] >= 180]
    out = set()
    for i in narrow:
        r = rows[i]
        for b in body:
            if min(r['y1'], b['y1']) - max(r['y0'], b['y0']) > 2 and (b['x0'] >= r['x1'] + 3 or b['x1'] <= r['x0'] - 3):
                out.add(i)
                break
    # A note whose line holds only short body text (a section number and a few words) is found by its column: the
    # x and the font size of the notes found by the rule above anywhere in the document, when notes are set smaller
    # than the body. The row must still have body text on its line, wholly on its other side.
    for i in narrow:
        r = rows[i]
        if i in out or not cols or not any(abs(r['x0'] - cx) < 3 and abs(r['size'] - cs) < 0.3 for cx, cs in cols):
            continue
        for b in rows:
            if b is r or b['legacy'] or b['size'] - r['size'] < 1.0:
                continue
            if min(r['y1'], b['y1']) - max(r['y0'], b['y0']) > 2 and (b['x0'] >= r['x1'] + 3 or b['x1'] <= r['x0'] - 3)                     and not (b['x1'] < 0.30 * width or b['x0'] > 0.70 * width):
                out.add(i)
                break
    grew = True
    while grew:
        grew = False
        for i in narrow:
            if i in out:
                continue
            r = rows[i]
            for j in list(out):
                q = rows[j]
                # same x, or (notes set centred or flush right in the outer column) the same side and font size
                same_col = abs(q['x0'] - r['x0']) < 3 or (abs(q['size'] - r['size']) < 0.3 and (
                    (q['x0'] > 0.70 * width and r['x0'] > 0.70 * width) or (q['x1'] < 0.30 * width and r['x1'] < 0.30 * width)))
                if same_col and (0 <= r['y0'] - q['y1'] < 14 or 0 <= q['y0'] - r['y1'] < 14):
                    out.add(i)
                    grew = True
                    break
    return out


def parse(pdf: Path) -> tuple[dict, dict]:
    doc = pymupdf.open(pdf)
    body: list[dict] = []
    aside: list[str] = []
    notes: list[dict] = []
    pages = []
    for pno, page in enumerate(doc):
        h, w = page.rect.height, page.rect.width
        rows = lines_of(page)
        keep = []
        for r in rows:
            t = r['text']
            if r['legacy']:
                aside.append(r.get('raw') or t)
                continue
            # small print at the top or bottom of a page is furniture, unless it is a marginal note beside the body
            # (decided after margins() below; notes are set in 8pt like the furniture)
            if r['y0'] < 0.135 * h and (r['size'] <= 9.2 or RUNNING.search(t)) and pno > 0:
                if RUNNING.search(t) or not (r['x1'] < 0.30 * w or r['x0'] > 0.70 * w):
                    aside.append(t)
                    continue
                r = {**r, 'edge': True}
            if r['y0'] > 0.84 * h and (r['size'] <= 8.6 or RUNNING.search(t)):
                if RUNNING.search(t) or not (r['x1'] < 0.30 * w or r['x0'] > 0.70 * w):
                    aside.append(t)
                    continue
                r = {**r, 'edge': True}
            if RUNNING.search(t) and r['size'] <= 10.5 and len(t) < 120:
                aside.append(t)
                continue
            if pno == 0 and (MAST.search(t) or r['size'] >= 13):
                aside.append(t)
                continue
            keep.append(r)
        pages.append((pno, w, keep))
    # the marginal-note columns of the document: (x, font size) of the notes the strict rule finds, when the notes are
    # set at least 1pt smaller than the body text beside them
    cols = set()
    for pno, w, keep in pages:
        for i in margins(keep, w):
            if keep[i]['size'] <= statistics.median([r['size'] for r in keep]) - 1.0:
                cols.add((round(keep[i]['x0'], 1), round(keep[i]['size'], 1)))
    for pno, w, keep in pages:
        marg = margins(keep, w, cols)
        for i, r in enumerate(keep):
            if r.get('edge') and i not in marg:
                aside.append(r['text'])
                continue
            if i in marg:
                notes.append({'page': pno, 'y0': r['y0'], 'y1': r['y1'], 'text': r['text']})
                aside.append(r['text'])
            else:
                body.append({**r, 'page': pno})
    # group marginal note rows into notes (consecutive rows, gap < 4pt)
    grouped: list[dict] = []
    for n in sorted(notes, key=lambda n: (n['page'], n['y0'])):
        g = grouped[-1] if grouped else None
        if g and g['page'] == n['page'] and n['y0'] - g['y1'] < 4.5:
            g['text'] = join(g['text'], n['text'])
            g['y1'] = n['y1']
        else:
            grouped.append(dict(n))
    return assemble(body, grouped, aside, doc)


def join(a: str, b: str) -> str:
    if re.search(r'[A-Za-z]-$', a) and re.match(r'[a-z]', b):
        return a[:-1] + b
    return a + ' ' + b


def paragraphs(rows: list[dict]) -> list[str]:
    if not rows:
        return []
    xs = [r['x0'] for r in rows]
    right = max(r['x1'] for r in rows)
    out: list[str] = []
    prev = None
    for r in rows:
        t = r['text']
        new = prev is None
        if prev is not None:
            gap = r['y0'] - prev['y1'] if r['page'] == prev['page'] else 0
            short = prev['x1'] < right - 45
            if PARA.match(t) or (gap > 7 and short) or (short and re.search(r'[.;:—-]$', prev['text'])) \
                    or prev['bold'] != r['bold']:
                new = True
        if new:
            out.append(t)
        else:
            out[-1] = join(out[-1], t)
        prev = r
    return out


NOTICE = re.compile(r'^(NOTICE\s+is\s+hereby\s+given|THE\s+above\s+statute|IT\s+is\s+(?:hereby\s+)?notified|THE\s+Statute\s+'
                    r'(?:of|set\s+out)|Notice\s+is\s+hereby)', re.I)
LONGTITLE = re.compile(r'^(A|AN)\s+STATUTE\b', re.I)


def heading_start(body: list[dict], i: int) -> int:
    """Walk up from row i over a contiguous bold heading block."""
    while i > 0 and body[i - 1]['bold'] and (body[i - 1]['page'] != body[i]['page']
                                              or body[i]['y0'] - body[i - 1]['y1'] < 70):
        i -= 1
    return i


def assemble(body: list[dict], notes: list[dict], aside: list[str], doc) -> tuple[list[dict], dict]:
    # each statute is anchored on its section 1 (the short title: "1. This Statute may be cited as ...")
    sec1 = [i for i, r in enumerate(body) if SHORT1.match(r['text'])]         or [i for i, r in enumerate(body) if SHORT1B.match(r['text'])][:1]
    if not sec1:
        raise ValueError('no section 1 (short title) found')
    enacts, starts = [], []
    for s1 in sec1:
        lo = starts[-1] + 1 if starts else 0
        e = next((k for k in range(s1 - 1, max(lo - 1, s1 - 6), -1) if ENACT.search(body[k]['text'])), s1)
        i = e
        # the long title above ("A Statute to provide for ..."), within 15 rows and below any bold heading
        for k in range(e - 1, max(lo - 1, e - 15), -1):
            if body[k]['bold']:
                break
            if LONGTITLE.match(body[k]['text']):
                i = k
                break
        enacts.append(e)
        starts.append(max(lo, heading_start(body, i)))
    # notice blocks (the Council Secretary's publication notice) end the statute before them
    cuts = sorted({heading_start(body, i) for i, r in enumerate(body) if NOTICE.match(r['text'])})
    acts = []
    for n, (st, e) in enumerate(zip(starts, enacts)):
        nxt = starts[n + 1] if n + 1 < len(starts) else len(body)
        end = min([c for c in cuts if st < c <= nxt] + [nxt])
        rows = body[st:end]
        acts.append(one_act(rows, e - st, notes))
    gaps = []
    prev = 0
    for st, a in zip(starts, acts):
        gaps.append(body[prev:st])
        prev = st + a['nrows']
    gaps.append(body[prev:])
    notice = ['\n'.join(paragraphs(g)) for g in gaps if g]
    meta = {'aside': aside, 'notice': notice, 'notes': [n['text'] for n in notes], 'gazette': gazette_of(doc)}
    return acts, meta


def one_act(rows: list[dict], enact: int, notes: list[dict]) -> dict:
    k = enact + 1
    while k < len(rows) and not SECNO.match(rows[k]['text']) and not re.search(r'[:\-—.]$', rows[k - 1]['text']):
        k += 1
    title_rows, rest = rows[:k], rows[k:]
    # sections: rows starting "N." with N the next number, each level with a marginal note's first row
    secs: list[tuple[str, int]] = []
    want = 1
    for i, r in enumerate(rest):
        m = SECNO.match(r['text'])
        if m and m.group(1).lstrip('0') == str(want) and any(n['page'] == r['page'] and abs(n['y0'] - r['y0']) < 8 for n in notes):
            secs.append((m.group(1), i))
            want += 1
    units: dict[str, dict] = {}
    used_notes: list[str] = []
    tparas = paragraphs(title_rows)
    # A section the note rule missed (its note not found) would leave its text inside the section before it: when a
    # later row starts with the next number at the x where the found sections start, keep the statute in one file.
    sx = [rest[i]['x0'] for _, i in secs]
    loose = re.compile(r'^0*(\d{1,3})[A-Z]?\s*(?:\.|\()')  # "4." or "3 (1)", printed without its full stop
    missed = secs and any(loose.match(r['text']) and loose.match(r['text']).group(1) == str(want)
                          and any(abs(r['x0'] - x) < 3 for x in sx) for r in rest[secs[-1][1] + 1:])
    if len(secs) >= 2 and secs[0][1] == 0 and not missed:
        units['000-title'] = {'label': 'Title', 'kind': 'title', 'text': '# Title\n' + '\n'.join(tparas) + '\n'}
        bounds = [i for _, i in secs] + [len(rest)]
        for j, (no, i) in enumerate(secs):
            chunk = rest[i:bounds[j + 1]]
            r0 = chunk[0]
            note = next((n for n in notes if n['page'] == r0['page'] and abs(n['y0'] - r0['y0']) < 8), None)
            head = [note['text']] if note else []
            used_notes += head
            units[f'sec-{int(no):03d}'] = {'label': f'Section {int(no)}', 'kind': 'section',
                                           'text': f'# Section {int(no)}\n' + '\n'.join(head + paragraphs(chunk)) + '\n'}
    else:
        units['000-text'] = {'label': 'Text', 'kind': 'text',
                             'text': '# Text\n' + '\n'.join(paragraphs(title_rows + rest)) + '\n'}
    heading = ' '.join(r['text'] for r in title_rows if r['bold'])
    return {'units': units, 'used_notes': used_notes, 'heading': heading, 'nrows': len(rows),
            'first_page': rows[0]['page'], 'last_page': rows[-1]['page'], 'sections': len(secs)}


MONTHS = {m: i for i, m in enumerate(['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august',
                                      'september', 'october', 'november', 'december'], 1)}


def gazette_of(doc) -> dict:
    """The issue number and date from the first page's masthead ("No. 1444/20 - THURSDAY, MAY 11, 2006")."""
    t = norm(doc[0].get_text())
    m = re.search(r'No\.\s*(\d{3,4})\s*/\s*(\d{1,3})\s*[-–—_]*\s*(?:MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY|'
                  r'SATURDAY|SUNDAY)\s*,?\s*([A-Z]+)\s*,?\s+(\d{1,2})\s*,?\s*(\d{4})', t, re.I)
    if not m or m.group(3).lower() not in MONTHS:
        return {}
    return {'no': f'{m.group(1)}/{m.group(2)}',
            'date': f'{int(m.group(5)):04d}-{MONTHS[m.group(3).lower()]:02d}-{int(m.group(4)):02d}'}


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    acts, meta = parse(Path(sys.argv[1]))
    for a in acts:
        print('=== ACT', a['heading'][:150], '| sections', a['sections'], '| pages', a['first_page'], a['last_page'])
        for k, u in a['units'].items():
            print(u['text'][:int(sys.argv[2]) if len(sys.argv) > 2 else 100000])
    print('META', meta['gazette'], 'NOTICE', [n[:200] for n in meta['notice']])
    print('ASIDE', meta['aside'][:40])
    print('NOTES', meta['notes'][:40])
