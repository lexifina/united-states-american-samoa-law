"""Layout-aware statute parser (PDF text layer -> article units). No network, deterministic.

Reads PyMuPDF line dicts, so it can tell article headings (bold "Article N"), structural headings (bold or larger
type), running heads and page numbers (small type at the page edge) and paragraph starts (first-line indent) apart.
"""
import re
import pymupdf

NL = chr(10)
ART = re.compile(r'^\s*(?:Article|ARTICLE|Art\.)\s*(premier|1er|1\s?er|\d+)\s*(bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies)?\s*(?:\(nouveau\))?\s*(?:[.:\-–—]+)?\s*(.*)$', re.I)
SEP = re.compile(r'^\s*(?:Article|ARTICLE|Art\.)\s*\w+\s*(?:bis|ter|quater)?\s*(?:\(nouveau\))?\s*[:.\-–—]')
HEADWORD = re.compile(r'^\s*(LIVRE|TITRE|CHAPITRE|SECTION|SOUS-SECTION|SOUS SECTION|PARAGRAPHE|PARTIE|DISPOSITIONS?)\b', re.I)


def norm(s):
    s = s.replace(' ', ' ').replace('’', "'").replace('‘', "'").replace('–', '-').replace('—', '-')
    s = s.replace('‐', '-').replace('‑', '-').replace('−', '-').replace('­', '').replace('﻿', '')
    s = s.replace('“', '"').replace('”', '"').replace('« ', '«').replace(' »', '»')
    return re.sub(r'\s{2,}', ' ', s).strip()


def lines_of(pdf, first_page=0, last_page=None, small=9.5):
    """[(page, x0, text, bold, size)] for body lines; lines in type smaller than `small` (running heads, page numbers,
    footnotes) are dropped."""
    out = []
    d = pymupdf.open(pdf)
    for p in list(d)[first_page:last_page]:
        page = []
        for b in p.get_text('dict')['blocks']:
            for l in b.get('lines', []):
                spans = [s for s in l['spans'] if s['text'].strip()]
                if not spans:
                    continue
                size = max(s['size'] for s in spans)
                if size < small:
                    continue
                text = norm(''.join(s['text'] for s in l['spans']))
                if not text:
                    continue
                bold = all(('Bold' in s['font'] or s['flags'] & 16) for s in spans)
                page.append((round(l['bbox'][1] / 3), l['bbox'][0], (p.number, l['bbox'][0], text, bold, size)))
        # reading order: top to bottom, then left to right (some layouts store page-top headings last)
        out += [x[2] for x in sorted(page, key=lambda x: (x[0], x[1]))]
    return out


def dehyphenate(paras):
    """Join words broken at a line end ("indi-" + "viduelles"). The hyphen is kept when the hyphenated form occurs
    unbroken elsewhere in the text and the closed form does not; otherwise it is dropped."""
    # the text with every broken word cut out: what the document prints unbroken
    unbroken = ' '.join(re.sub(r"[\w']*-\u0001[\w']*", ' ', p) for p in paras)
    closed_unbroken = set(re.findall(r"\w+", unbroken))

    def fix(m):
        a, b = m.group(1), m.group(2)
        hy, cl = f'{a}-{b}', f'{a}{b}'
        hy_seen = re.search(r'(?<![\w-])' + re.escape(hy) + r'(?!\w)', unbroken) is not None
        return hy if hy_seen and cl not in closed_unbroken else cl

    return [re.sub(r"([\w']+)-\u0001([\w']+)", fix, p).replace('-\u0001', '-') for p in paras]


def structural_line(text, bold, size, head_size):
    return (bold and size > head_size) or (HEADWORD.match(text) is not None and text.upper() == text)


def articles(lines, indent=55.0, stop=None, head_size=10.5):
    """Split body lines into articles. Returns [(num, suffix, title, [paragraphs])] in document order.
    A paragraph starts at an indented line (x0 > indent) or after a line ending a list item; a line ending in '-' is
    joined to the next with a soft-hyphen marker resolved by dehyphenate()."""
    arts, cur, in_title = [], None, False
    last = 0
    for page, x0, text, bold, size in lines:
        if stop and stop(text, last):
            break
        m = ART.match(text)
        if m and not bold:
            # an article heading set in roman type by mistake: accepted only with a separator, at the margin, in sequence
            g = m.group(1).replace(' ', '').lower()
            n = 1 if g in ('premier', '1er') else int(g)
            if not (x0 <= indent and n == last + 1 and SEP.match(text)):
                m = None
        if m:
            g = m.group(1).replace(' ', '').lower()
            n = 1 if g in ('premier', '1er') else int(g)
            cur = [n, (m.group(2) or '').lower(), m.group(3).strip(' :.'), []]
            arts.append(cur); in_title = True; last = n
            continue
        if cur is None:
            if arts and not bold and not structural_line(text, bold, size, head_size):
                # unnumbered text between a heading and the next article: kept as its own unit
                cur = [arts[-1][0], 'texte', '', []]
                arts.append(cur); in_title = False
            else:
                continue
        structural = structural_line(text, bold, size, head_size)
        if bold and not structural and in_title:
            cur[2] = (cur[2] + ' ' + text).strip() if not cur[2].endswith('-') else cur[2][:-1] + text
            continue
        if structural:
            # a structural heading: it closes the article until the next article heading
            cur = None
            continue
        in_title = False
        ps = cur[3]
        if not ps or x0 > indent or re.match(r'^(\d+°\)?|[a-z]\)|-|•|\d+[.)]\s)', text):
            if ps and ps[-1].endswith('-\u0001'):
                ps[-1] = ps[-1] + text  # a broken word continues even on an indented line
            else:
                ps.append(text)
        else:
            ps[-1] = ps[-1] + ('' if ps[-1].endswith('-\u0001') else ' ') + text
        if ps[-1].endswith('-') and not ps[-1].endswith(' -'):
            ps[-1] = ps[-1] + '\u0001'
    return arts


def units(arts):
    allp = [p for a in arts for p in a[3]]
    fixed = iter(dehyphenate(allp))
    out, dup = {}, []
    for n, suf, title, ps in arts:
        key = f'art-{n:03d}' + (f'-{suf}' if suf else '')
        label = f'Art. {n}' + (f' {suf}' if suf else '')
        if suf == 'texte':
            label = f'Unnumbered text after Art. {n}'
        body = [next(fixed) for _ in ps]
        if key in out:
            # a number printed twice: kept as printed, the repeat under a -dupN key
            k = 2
            while f'{key}-dup{k}' in out:
                k += 1
            key, label = f'{key}-dup{k}', f'{label} (printed again, no. {k})'
            dup.append(key)
        head = f'# Article {"1er" if n == 1 and not suf else n}' + (f' {suf}' if suf else '')
        if suf == 'texte':
            head = f'# {label}'
        lines = [head] + ([title] if title else []) + [re.sub(r'\s{2,}', ' ', b).strip() for b in body]
        out[key] = {'label': label, 'kind': 'art', 'text': NL.join(lines) + NL}
    return out, dup


def gaps(arts):
    nums = sorted({a[0] for a in arts})
    return [x for x in range(nums[0], nums[-1] + 1) if x not in set(nums)]


def _squash(s):
    return re.sub(r'[\W_]+', '', norm(s)).lower()


def verify(units_, lines):
    """Check every unit against the source: each paragraph (hyphens, spaces and punctuation ignored) must occur in the
    source's body lines in order, and the units together must cover every non-heading body line.
    Returns (missing paragraphs [(key, text)], uncovered source lines [text])."""
    src = _squash(''.join(t for _, _, t, b, _ in lines))
    missing, pos = [], 0
    for key, u in units_.items():
        for para in u['text'].split(NL)[1:]:
            q = _squash(para)
            if not q:
                continue
            i = src.find(q, pos)
            if i < 0:
                i = src.find(q)
            if i < 0:
                missing.append((key, para))
            else:
                pos = i
    allu = _squash(''.join(u['text'] for u in units_.values()))
    uncovered = [t for _, _, t, b, _ in lines if not b and len(_squash(t)) > 12 and _squash(t)[:-1].rstrip() not in allu]
    return missing, uncovered
