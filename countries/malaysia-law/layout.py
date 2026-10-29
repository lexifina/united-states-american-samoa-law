"""Laws of Malaysia reprint PDFs (Attorney General's Chambers) -> provisions. gitlaw-MY.

The reprints are typeset alike (Times; PyMuPDF reads their text layer):
- running heads (act title and page number in the top 60 pt; "[Article 3]" / "[Second Schedule]" in 10 pt small
  capitals) are dropped;
- NOTES pages (the editor's amendment notes, headed "NOTES") are skipped;
- footnotes ("*This Part has been amended by ... not yet in force") are set in 8 pt or less: dropped, and so are
  the asterisk markers that point to them (page_footnotes() returns them for review);
- small capitals are a font "...-SC700" whose lower-case letters are set smaller: those letters are read as
  capitals ("160a" -> "160A");
- a provision starts at a bold number at the start of a line ("49a." -> 49A), with its bold heading on the
  line(s) before; PART and CHAPTER headings are centred lines;
- the schedules start at a 24 pt "SCHEDULES" page; each starts at a bold small-capital line "First Schedule"
  etc. and is one unit;
- a paragraph starts with a tab or a label, after a vertical gap wider than 1.45 lines, or when a line starts
  left of the paragraph's first line (measured from each page's own left margin); other lines are joined to it
  with one space. A label at the top of a page continues the paragraph when the line before ends in a word that
  needs a reference after it ("paragraph" + "(b) or paragraph (c)").
"""
import re
import unicodedata

import fitz

SC = 'SC700'
ORD = ['first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh', 'eighth', 'ninth', 'tenth', 'eleventh',
       'twelfth', 'thirteenth', 'fourteenth']
ROMAN = {'I': 1, 'V': 5, 'X': 10, 'L': 50}
XH_SKIP = re.compile(r'^(ILLUSTRATIONS?|Illustrations?|EXPLANATIONS?|Explanations?|EXCEPTIONS?|Exceptions?)')
ART_RE = re.compile(r'^[\s*]*(\d+[A-Z]*)\.(?=\s|$)')
LABEL_RE = re.compile(r'^\s*(\(\w{1,5}\)|\d+[A-Z]*\.)(\s|$)')
REF_END = re.compile(r'\b(paragraphs?|subparagraphs?|Clauses?|sections?|subsections?|Articles?)$')


def roman(s):
    n = 0
    for a, b in zip(s, s[1:] + ' '):
        v = ROMAN[a]
        n += -v if ROMAN.get(b, 0) > v else v
    return n


def span_text(s, full):
    t = s['text']
    if SC in s['font'] and s['size'] < full - 1.5:
        t = t.upper()
    return t


def norm(t):
    t = t.replace(' ', ' ').replace(' ', '\t').replace(' ', '\t').replace(' ', ' ')
    t = t.replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"')
    t = t.replace('–', '-').replace('', '')
    return unicodedata.normalize('NFC', t)


def clean(t):
    t = re.sub(r'(?<=[\w\)\]\.,;:"])\*+', '', t)           # footnote markers after a word
    t = re.sub(r'(^|(?<=[\s\(\["]))\*+(?=\S)', '', t)        # markers before a word
    return re.sub(r'[ \t]+', ' ', t).strip()


def visible(spans):
    return [s for s in spans if s['text'].strip().strip('*').strip()]


def is_running_head(spans, size, y):
    vis = [x for x in spans if x['text'].strip()]
    if not vis or y < 60:
        return True                                      # act title and page number band
    t = ''.join(x['text'] for x in vis).strip()
    return SC in vis[0]['font'] and size <= 10.5 and ('[' in t or ']' in t)


def page_footnotes(page):
    """Footnote lines (8 pt and smaller) of a provisions page, joined, for review and for decisions."""
    out = []
    for bl in page.get_text('dict')['blocks']:
        for l in bl.get('lines', []):
            spans = [x for x in l['spans'] if x['text']]
            if spans and max(x['size'] for x in spans) <= 8.6 and l['bbox'][1] > 70:
                out.append(norm(''.join(span_text(x, max(y['size'] for y in spans)) for x in spans)))
    return ' '.join(' '.join(out).split())


def page_lines(page):
    """Lines of one page in reading order (lines at one height merged), running heads and footnotes dropped."""
    raw = []
    for bl in page.get_text('dict')['blocks']:
        for l in bl.get('lines', []):
            spans = [s for s in l['spans'] if s['text']]
            if not spans:
                continue
            size = max(s['size'] for s in (visible(spans) or spans))
            y = l['bbox'][1]
            if y < 70 and is_running_head(spans, size, y):
                continue
            vis = [s for s in spans if s['text'].strip()]
            if vis and SC in vis[0]['font'] and size <= 10.5 and vis[0]['text'].strip().startswith('[') \
                    and ''.join(s['text'] for s in vis).strip().endswith(']'):
                continue                                 # running reference "[Article 38]" lower on a page
            raw.append([l['bbox'][0], y, size, spans])
    raw.sort(key=lambda r: (round(r[1] / 3), r[0]))
    merged = []
    for r in raw:
        if merged and abs(merged[-1][1] - r[1]) < 3:
            merged[-1][3] = merged[-1][3] + r[3]
            merged[-1][2] = max(merged[-1][2], r[2])
        else:
            merged.append(r)
    out = []
    for x, y, size, spans in merged:
        if size <= 8.6:
            continue                                     # footnotes
        txt = norm(''.join(span_text(s, size) for s in spans))
        if not txt.strip():
            continue
        vis = visible(spans) or [s for s in spans if s['text'].strip()]
        first = vis[0]
        out.append({'x': next(s for s in spans if s['text'].strip())['bbox'][0], 'y': y, 'size': size,
                    'x1': max(s['bbox'][2] for s in spans if s['text'].strip()),
                    'bold': 'Bold' in first['font'], 'allbold': all('Bold' in s['font'] for s in vis),
                    'allital': all('Italic' in s['font'] for s in vis),
                    'sc': SC in first['font'], 'lead_tab': txt[:1] == '\t', 'text': txt})
    return out


def is_notes_page(page):
    for bl in page.get_text('dict')['blocks']:
        for l in bl.get('lines', []):
            t = ''.join(s['text'] for s in l['spans']).strip()
            if 60 < l['bbox'][1] < 110 and t == 'NOTES':
                return True
    return False


def body_pages(doc):
    """Page indexes of the provisions: from the page with the first bold "1." to the LIST OF AMENDMENTS."""
    start = None
    for i in range(4, doc.page_count):
        if any(ln['bold'] and re.match(r'^1\.(\s|$)', ln['text'].strip()) for ln in page_lines(doc[i])):
            start = i
            break
    for i in range(start + 1, doc.page_count):
        if re.search(r'^\s*LIST OF AMENDMENTS\s*$', doc[i].get_text(), re.M):
            return start, i
    return start, doc.page_count


UNIT = {'art': ('art', 'Art. ', 'Article'), 'sec': ('sec', 's. ', 'Section')}


def parse(pdf_bytes, unit='art', chapters=False):
    """Ordered list of units {key, label, kind, heading, text} from a reprint; unit 'art' (the Constitution's
    Articles) or 'sec' (an Act's sections). In 'sec' mode an editorial "*NOTE—" set smaller than the text (an Act
    reprint quoting a saving provision of an amending Act) is dropped up to the next full-size line. chapters=True
    (the Penal Code, an Act without Parts) reads "CHAPTER XVI" headings and centred cross-headings before a
    section's bold heading ("Mischief") as units chapter-16 and xh-425."""
    kp, lp, hp = UNIT[unit]
    doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    start, end = body_pages(doc)
    units = []
    st = {'cur': None, 'para': None}
    pending_heading = []
    pending_cross = []
    part = None
    in_schedules = False
    centre_block = None

    def close_para():
        if st['para'] is not None and st['cur'] is not None:
            st['cur']['lines'].append(clean(st['para']['text']))
        st['para'] = None

    def new_unit(key, label, kind, heading=None):
        close_para()
        st['cur'] = {'key': key, 'label': label, 'kind': kind, 'heading': heading, 'lines': []}
        units.append(st['cur'])

    pages = {}
    mins = {0: {}, 1: {}}
    for pi in range(start, end):
        if not is_notes_page(doc[pi]):
            pages[pi] = page_lines(doc[pi])
            if pages[pi]:
                m = round(min(ln['x'] for ln in pages[pi]))
                mins[pi % 2][m] = mins[pi % 2].get(m, 0) + 1
    # the left margin by page parity (recto/verso): the most common smallest x
    margins = {p: max(sorted(c), key=lambda m: c[m]) if c else 0 for p, c in mins.items()}
    maxs = {0: {}, 1: {}}
    for pi, ls in pages.items():
        if ls:
            m = round(max(ln['x1'] for ln in ls))
            maxs[pi % 2][m] = maxs[pi % 2].get(m, 0) + 1
    rights = {p: max(sorted(c), key=lambda m: c[m]) if c else 0 for p, c in maxs.items()}

    for pi in sorted(pages):
        lines = pages[pi]
        if not lines:
            continue
        margin = margins[pi % 2]
        last_y = None
        for li, ln in enumerate(lines):
            t = ln['text']
            ts = clean(t)
            if unit == 'sec' and ts.startswith('NOTE—') and ln['size'] < 11:
                st['note'] = True
            elif ln['size'] >= 11:
                st['note'] = False
            if st.get('note'):
                continue
            if not ts or ts == 'Section Subject Matter':
                continue                                  # the Eleventh Schedule's table head, repeated per page
            rx = ln['x'] - margin
            ln['centred'] = rx > 20 and abs(rx - (rights[pi % 2] - ln['x1'])) < 14
            gap = (ln['y'] - last_y) if last_y is not None else None
            is_centre = rx > 25 and len(ts) < 75 and not ln['lead_tab']
            para = st['para']
            if not in_schedules and ts == 'SCHEDULES' and ln['size'] > 13:
                close_para()
                in_schedules = True
                st['cur'] = None
                last_y = ln['y']
                continue
            if in_schedules and ts == 'SCHEDULES':
                last_y = ln['y']
                continue
            m_sch = re.match(r'^(\w+) Schedule$', ts, re.I)
            if in_schedules and m_sch and m_sch.group(1).lower() in ORD and ln['bold'] and ln['sc']:
                n = ORD.index(m_sch.group(1).lower()) + 1
                name = m_sch.group(1).capitalize() + ' Schedule'
                new_unit(f'sch-{n:02d}', name, 'schedule')
                st['cur']['lines'].append('# ' + name)
                last_y = ln['y']
                continue
            up = ts.upper()
            m_part = re.match(r'^PART ([IVXL]+)$', up)
            m_ch = re.match(r'^CHAPTER (\d+)\s*[-—]\s*(.*)$', up)
            m_div = re.match(r'^DIVISION (\d+)([A-Z]?)$', up)
            if not in_schedules and is_centre and m_div:
                d = f'{int(m_div.group(1)):02d}{m_div.group(2).lower()}'
                new_unit(f'part-{part:02d}-division-{d}', f'Part {part}, Division {m_div.group(1)}{m_div.group(2)}',
                         'division')
                st['cur']['lines'].append(f'# Division {m_div.group(1)}{m_div.group(2)}')
                centre_block = st['cur']
                last_y = ln['y']
                continue
            if not in_schedules and is_centre and (m_part or m_ch):
                if m_part:
                    part = roman(m_part.group(1))
                    new_unit(f'part-{part:02d}', f'Part {m_part.group(1)}', 'part')
                    st['cur']['lines'].append(f'# Part {m_part.group(1)}')
                else:
                    c = int(m_ch.group(1))
                    new_unit(f'part-{part:02d}-chapter-{c:02d}', f'Part {part}, Chapter {c}', 'chapter')
                    st['cur']['lines'].append('# ' + ts)
                centre_block = st['cur']
                last_y = ln['y']
                continue
            if not in_schedules and centre_block is not None and st['cur'] is centre_block and is_centre \
                    and not ln['bold']:
                if para is not None and gap is not None and gap < 1.45 * ln['size']:
                    para['text'] += ' ' + ts
                else:
                    close_para()
                    st['para'] = {'rx': rx, 'text': ts}
                last_y = ln['y']
                continue
            if chapters and not in_schedules:
                # an Act without Parts (the Penal Code): "CHAPTER XVI" and its title, and centred cross-headings
                # ("Mischief") between sections, kept as their own units xh-<next section>
                m_pc = re.match(r'^CHAPTER ([IVXL]+)([A-Z]?)$', up)
                if m_pc and (is_centre or ln['centred']):
                    c = f'{roman(m_pc.group(1)):02d}{m_pc.group(2).lower()}'
                    new_unit(f'chapter-{c}', f'Chapter {m_pc.group(1)}{m_pc.group(2)}', 'chapter')
                    st['cur']['lines'].append(f'# Chapter {m_pc.group(1)}{m_pc.group(2)}')
                    centre_block = st['cur']
                    pending_heading = []
                    last_y = ln['y']
                    continue
                if centre_block is not None and st['cur'] is centre_block and ln['centred']:
                    if para is not None and gap is not None and gap < 1.45 * ln['size']:
                        para['text'] += ' ' + ts
                    else:
                        close_para()
                        st['para'] = {'rx': rx, 'text': ts}
                    last_y = ln['y']
                    continue
                nxt = lines[li + 1] if li + 1 < len(lines) else None
                if ln['centred'] and not ln['bold'] and nxt is not None and nxt['bold'] \
                        and not LABEL_RE.match(t) and not XH_SKIP.match(ts) and st['cur'] is not None \
                        and ts[:1].isupper() and not ts.endswith(('.', ';', ',', ':')) \
                        and st['cur']['kind'] == 'sec':
                    close_para()
                    if pending_cross and gap is not None and gap < 1.45 * ln['size']:
                        pending_cross[-1] += ' ' + ts
                    else:
                        pending_cross.append(ts)
                    last_y = ln['y']
                    continue
            if not in_schedules and ln['allbold'] and not ART_RE.match(t):
                close_para()                              # an article heading (may run over two lines)
                if pending_heading and gap is not None and gap < 1.45 * ln['size']:
                    pending_heading[-1] += ' ' + ts
                else:
                    pending_heading = [ts]
                centre_block = None
                last_y = ln['y']
                continue
            m_art = ART_RE.match(t) if (not in_schedules and ln['bold']) else None
            if m_art:
                num = m_art.group(1)
                mm = re.match(r'^(\d+)([A-Z]*)$', num)
                key = f'{kp}-{int(mm.group(1)):03d}{mm.group(2).lower()}'
                head = ' '.join(pending_heading) if pending_heading else None
                pending_heading = []
                if pending_cross:
                    new_unit('xh-' + key[len(kp) + 1:], f'Heading before {lp}{num}', 'heading')
                    st['cur']['lines'] += ['# ' + x for x in pending_cross]
                    pending_cross.clear()
                new_unit(key, f'{lp}{num}', kp, head)
                st['cur']['lines'].append(f'# {hp} {num}' + (f'. {head}' if head else ''))
                centre_block = None
                st['para'] = {'rx': rx, 'text': f'{num}. ' + clean(t[m_art.end():])}
                last_y = ln['y']
                continue
            if st['cur'] is None:
                last_y = ln['y']
                continue
            label = LABEL_RE.match(t)
            if label and gap is not None and not ln['lead_tab']:
                label = None                              # mid-page, a new item has a tab or a gap before it
            if label and para is not None and not ln['lead_tab'] and REF_END.search(para['text']):
                label = None
            starts = label or ln['allbold'] or (in_schedules and (ln['bold'] or ln['centred'] or ln['allital']))
            # a line left of the paragraph's earlier continuation lines starts a new paragraph (same page only)
            new = (para is None or starts or (gap is not None and gap > 1.45 * ln['size'])
                   or (gap is not None and para.get('cx') is not None and rx < para['cx'] - 2))
            if new:
                close_para()
                st['para'] = {'rx': rx, 'text': ts}
            else:
                if gap is not None and para.get('cx') is None:
                    para['cx'] = rx
                para['text'] += ts if para['text'].endswith(('-', '—')) else ' ' + ts
            last_y = ln['y']
    close_para()
    for u in units:
        u['text'] = '\n'.join(l for l in u['lines'] if l) + '\n'
    return units
