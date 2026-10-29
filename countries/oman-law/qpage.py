"""Parse a Qanoon.om page (cached HTML) into the decree's issuance part and the law's articles. No network."""
import html, re

AR = '٠١٢٣٤٥٦٧٨٩'
TO_AR = str.maketrans('0123456789', AR)
TO_EN = str.maketrans(AR, '0123456789')
ORD = ['الأولى', 'الثانية', 'الثالثة', 'الرابعة', 'الخامسة', 'السادسة', 'السابعة', 'الثامنة', 'التاسعة', 'العاشرة',
       'الحادية عشرة', 'الثانية عشرة', 'الثالثة عشرة', 'الرابعة عشرة', 'الخامسة عشرة']
STRUCT = re.compile(r'^(الكتاب|الباب|الفصل|الفرع|القسم|الجزء)\b')
ART = re.compile(r'^(?:ال)?مادة\s*\(\s*([0-9]+)\s*(?:(مكرر[اًً]*)\s*([0-9]+)?\s*)?\)\s*(?:(مكرر[اًً]*)\s*(?:\(\s*([0-9]+)\s*\))?)?\s*(.*)$')
ISDAR = re.compile(r'^المادة\s+(' + '|'.join(sorted(ORD, key=len, reverse=True)) + r')\s*$')


def clean_line(s):
    """Typesetting only: NBSP, RLM/LRM, tatweel, curly quotes, dashes, spaces, digit forms. Words untouched."""
    s = s.replace('\xa0', ' ').replace('‏', '').replace('‎', '').replace('​', '').replace('ـ', '')
    s = s.replace('“', '"').replace('”', '"').replace('″', '"').replace('–', '-').replace('—', '-').replace('ـ', '')
    s = s.translate(TO_AR)
    s = re.sub(r'\s+', ' ', s).strip()
    s = re.sub(r' +([،؛:.)\]])', r'\1', s)
    s = re.sub(r'([(\[]) +', r'\1', s)
    return s


def body(raw):
    m = re.search(r'<div class="entry-content">(.*?)<!-- \.entry-content', raw, re.S)
    return m.group(1)


FN_REF = re.compile(r'(?:<sup>)?\s*<a href="#_ftn(\d+)"[^>]*>.*?</a>\s*(?:</sup>)?', re.S)


def blocks(raw):
    """[(kind, [lines], [footnote numbers])] for each top-level p / h3; kind 'h' (heading) or 'p'. Stops at the footnote rule."""
    b = body(raw)
    out, notes = [], {}
    parts = re.split(r'<hr\s*/?>', b)
    main = parts[0]
    for tail in parts[1:]:
        for n, txt in re.findall(r'<a href="#_ftnref(\d+)"[^>]*>.*?</a>(.*?)</p>', tail, re.S):
            notes[int(n)] = clean_line(html.unescape(re.sub(r'<[^>]+>', '', txt)))
    for m in re.finditer(r'<(p|h3|h2|h4)([^>]*)>(.*?)</\1>', main, re.S):
        tag, attrs, inner = m.groups()
        fns = [int(x) for x in re.findall(r'href="#_ftn(\d+)"', inner)]
        inner = FN_REF.sub('', inner)
        if 'pdf-link' in inner or re.search(r'id="more-\d+"', inner):
            continue
        centered = 'text-align: center' in attrs
        txt = html.unescape(re.sub(r'<[^>]+>', '', re.sub(r'(?i)<br\s*/?>', '\n', inner)))
        lines = [clean_line(x) for x in txt.split('\n')]
        lines = [x for x in lines if x and not re.match(r'^[0-9٠-٩/ ]+$', x)]   # drop the site's hidden search-tag line
        if not lines:
            continue
        kind = 'h' if tag != 'p' or (centered and '<strong>' in inner) else 'p'
        if kind == 'p' and centered and lines[0] == 'رسمنا بما هو آت':
            kind = 'h'
        out.append((kind, lines, fns))
    return out, notes


def art_key(n, bis, k):
    key = 'art-%03d' % int(n)
    label = 'المادة (%s)' % str(int(n)).translate(TO_AR)
    if bis:
        key += '-bis' + ('-%02d' % int(k) if k else '')
        label += ' مكررا' + (' (%s)' % str(int(k)).translate(TO_AR) if k else '')
    return key, label


def parse(raw, act_title, title_heads=(), law_only=False):
    """Return (preamble lines, [issuance units], [articles], footnotes, meta).
    Each unit: dict(key, label, lines, fns). The law part starts at the first heading equal to act_title (or one of title_heads)."""
    bl, notes = blocks(raw)
    pre, isdar, arts, meta = [], [], [], {'sig': []}
    stage = 'law' if law_only else 'pre'
    sfns = []
    cur = None
    for kind, lines, fns in bl:
        head = lines[0].translate(TO_EN)
        if kind == 'h' and stage != 'law' and (lines[0] == act_title or lines[0] in title_heads):
            stage, cur = 'law', None
            continue
        if stage == 'pre':
            if kind == 'h' and lines[0] == 'رسمنا بما هو آت':
                pre.append(lines[0])
                stage = 'isdar'
                continue
            pre.extend(lines)
            continue
        if stage == 'tail':
            continue
        if stage == 'isdar':
            if meta['sig'] and kind == 'h':      # after the signature: an annex that is not the law asked for
                stage = 'tail'
                continue
            m = ISDAR.match(lines[0]) if kind == 'h' else None
            m2 = ART.match(head) if kind == 'h' else None
            if m2 and not m and int(m2.group(1)) != len(isdar) + 1:
                m2 = None                       # a quoted article of the amended law inside a decree article
            if m or m2:
                n = ORD.index(m.group(1)) + 1 if m else int(m2.group(1))
                cur = {'key': 'isdar-%02d' % n, 'label': 'المادة %s (من مرسوم الإصدار)' % (ORD[n - 1]), 'lines': [], 'fns': fns}
                isdar.append(cur)
                continue
            if kind == 'p' and re.match(r'^(صدر في|الموافق|نشر هذا المرسوم|نشر في)', lines[0]) or (cur and cur.get('sig')):
                meta['sig'].extend(lines)
                if cur:
                    cur['sig'] = True
                continue
            if cur is None:
                pre.extend(lines)
            else:
                cur['lines'].extend(lines)
                cur['fns'] += fns
            continue
        # law part
        if kind == 'h':
            m = ART.match(head)
            if m:
                n, bis1, k1, bis2, k2, rest = m.groups()
                key, label = art_key(n, bis1 or bis2, k1 or k2)
                cur = {'key': key, 'label': label, 'lines': [], 'fns': list(fns), 'sfns': list(sfns),
                       'title': lines[1:] + ([clean_line(rest)] if rest else [])}
                cur['lines'].extend(cur['title'])
                arts.append(cur)
                continue
            # any other heading in the law (book, part, chapter, section, or an unnumbered sub-heading) is structure
            sfns = list(fns)
            meta.setdefault('dropped_heads', []).append((lines, fns))
            cur = None
            continue
        if cur is None:
            meta.setdefault('orphan', []).append(lines)
            continue
        cur['lines'].extend(lines)
        cur['fns'] += fns
    return pre, isdar, arts, notes, meta
