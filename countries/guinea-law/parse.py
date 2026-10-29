"""Guinea: cache -> corpus.json. Reads only .cache (gncache). Journal officiel PDFs with their own text layer (no OCR).

    python -X utf8 scripts/guinea-law/parse.py

Both texts are set in two columns. lines() reads each page's text lines with their boxes and orders them left column,
then right column, within bands cut by full-width lines. paragraphs() joins lines into paragraphs: a paragraph ends
where a line stops short of the column's right edge or where a wider gap opens above the next line, unless the line
breaks off mid-sentence (no closing punctuation, and the next line starts in lower case or with "("). Line-end
hyphens are removed when they split a word (the Charte uses ordinary hyphens, the Constitution soft hyphens), and kept
where the hyphenated word is written that way elsewhere in the same text or is a compound such as "bien-être".
"""
import json
import os
import re
import fitz
import gncache as c

HERE = os.path.dirname(os.path.abspath(__file__))
JO = 'https://journal-officiel.sgg.gov.gn/JO/'
SRC = {
    'constitution': JO + '2025/guinee-jo-2025-12-sp-3.pdf',
    'charte': JO + '2021/guinee-jo-2021-11.pdf',
}
HEADER = re.compile(r'JOURNAL OFFICIEL DE LA REPUBLIQUE')
HEADING = re.compile(r'^(PREMI[ÈE]RE|DEUXI[ÈE]ME|TROISI[ÈE]ME|I+[- ]|[\d.]+\s*(TITRE|SOUS|CHAPITRE)|TITRE|SOUS-TITRE|CHAPITRE|SECTION|LIVRE)\b')
ART = re.compile(r'^Article\s*(premier|1er|\d+)\s*(bis|ter)?\s*[:.]\s*')
SOFT = '\xad'
END = re.compile(r'[.;:!?»]$')
CONTINUES = re.compile(r'[a-zà-ÿœ(]')
PARA_GAP = 13.5  # points: lines are 10-12 pt apart, paragraphs 14 pt or more
# left halves of compounds that keep their hyphen at a line end
COMPOUND = {'bien', 'soixante', 'quatre', 'vingt', 'dix', 'vice', 'sous', 'peut', 'lui', 'elle', 'eux', 'elles',
            'c’est', 'est', 'non', 'ex', 'chef', 'quatre-vingt', 'avant', 'après', 'arrière', 'demi', 'semi'}


def lines(pdf, pages):
    d = fitz.open(pdf)
    out = []
    for i in pages:
        p = d[i]
        w = p.rect.width
        ls = []
        for b in p.get_text('dict')['blocks']:
            for l in b.get('lines', []):
                t = ''.join(s['text'] for s in l['spans'])
                if not t.strip():
                    continue
                x0, y0, x1, y1 = l['bbox']
                if HEADER.search(t) and (y0 < 32 or y0 > p.rect.height - 40):
                    continue
                col = 1 if x0 >= w * 0.48 else (0 if x1 <= w * 0.53 else 2)
                ls.append((y0, x0, x1, col, t))
        ls.sort()
        right = {k: max([x1 for _, _, x1, cc, _ in ls if cc == k] or [0]) for k in (0, 1, 2)}
        band = []

        def flush():
            for k in (0, 1):
                out.extend(sorted([l for l in band if l[3] == k]))
            band.clear()
        for l in ls:
            if l[3] == 2:
                flush()
                out.append(l)
            else:
                band.append(l)
        flush()
        out = [(y, x0, x1, cc, t, right[cc]) if len(o) == 5 else o for o in out
               for (y, x0, x1, cc, t) in [o[:5]]]
    return out


def _clean(t):
    return t.replace('\xa0', ' ').replace('\t', ' ').strip()


def hyphen_words(ls):
    """Hyphenated words written mid-line anywhere in the text, so a line-end break of the same word keeps its hyphen."""
    words = set()
    for l in ls:
        for m in re.finditer(r'(\w+)-(\w+)', _clean(l[4])):
            words.add((m.group(1).lower(), m.group(2).lower()))
    return words


def paragraphs(ls):
    keep = hyphen_words(ls)
    paras, cur, pending = [], '', False
    prev = None
    for line in ls:
        (y, x0, x1, col, t, right) = line
        s = _clean(t)
        gap = prev is not None and prev[3] == col and y - prev[0] >= PARA_GAP
        prev = line
        if s == '•':
            if cur:
                paras.append(cur)
            cur, pending = '• ', False
            continue
        if cur and not cur.endswith('• '):
            mid_sentence = not END.search(cur.rstrip(SOFT + '-')) and CONTINUES.match(s) and not ART.match(s)
            if (pending or (gap and END.search(cur))) and not mid_sentence:
                paras.append(cur)
                cur = ''
        pending = False
        if cur.endswith(SOFT):
            cur = cur[:-1] + s
        elif cur and not cur.endswith('• ') and (ART.match(s) or HEADING.match(s)):
            paras.append(cur)
            cur = s
        elif re.search(r'\w-$', cur) and CONTINUES.match(s):
            left = re.search(r'([\w’]+)-$', cur).group(1)
            right_part = re.match(r'[\w’]+', s).group(0) if re.match(r'[\w’]+', s) else ''
            if (left.lower(), right_part.lower()) in keep or left.lower() in COMPOUND:
                cur = cur + s
            else:
                cur = cur[:-1] + s
        else:
            cur = (cur + ' ' + s) if cur and not cur.endswith('• ') else cur + s
        if x1 < right - 15 and not s.endswith(SOFT):
            pending = True
    if cur:
        paras.append(cur)
    return [re.sub(r'\s+', ' ', p.replace(SOFT, '')).strip() for p in paras if p.strip()]


def units(paras, start, stop):
    """Articles from the paragraph equal to `start` (the body's PRÉAMBULE, not the sommaire's dotted line) to the
    signature line `stop`, which may sit inside the last article's paragraph. Headings, including a heading's second
    line in capitals, are dropped. An article that the Journal officiel runs on inside the previous paragraph
    ("... de ses biens. Article 61. Les écarts ...") is split out."""
    u, key, seen, num = {}, None, False, 0
    pre = []
    after_heading = False
    flat = []
    for p in paras:
        if not seen:
            if p == start:
                seen = True
            continue
        if stop in p:
            head = p[:p.index(stop)].strip()
            if head:
                flat.append(head)
            break
        flat.append(p)
    expanded = []
    for p in flat:
        parts = re.split(r'(?<=[.;:] )(?=Article\s*\d+\s*[.:]\s)', p)
        expanded.extend(x.strip() for x in parts if x.strip())
    for p in expanded:
        m = ART.match(p)
        if m:
            n = 1 if m.group(1) in ('premier', '1er') else int(m.group(1))
            if n != num + 1:
                raise ValueError(f'article {n} after {num}: {p[:80]}')
            num = n
            key = f'art-{n:03d}'
            u[key] = {'label': f'Article {m.group(1)}', 'kind': 'art', 'lines': [f'# Article {m.group(1)}', p[m.end():]]}
            after_heading = False
        elif HEADING.match(p) and p.upper() == p:
            after_heading = True
            continue
        elif after_heading and p.upper() == p and len(p) < 80:
            continue  # the second line of a heading ("TITRE III: ... ET DE" / "SÉCURITÉ")
        elif key:
            u[key]['lines'].append(p)
            after_heading = False
        else:
            pre.append(p)
            after_heading = False
    res = {}
    if pre:
        res['preambule'] = {'label': 'Préambule', 'kind': 'preamble', 'text': '# Préambule\n' + '\n'.join(pre) + '\n'}
    for k, v in u.items():
        res[k] = {'label': v['label'], 'kind': 'art', 'text': '\n'.join(v['lines']) + '\n'}
    return res


CONSTITUTION_PAGES = range(1, 19)
CHARTE_PAGES = range(4, 9)  # JO n° 2021-11, pp. 532-536


def main():
    cu = units(paragraphs(lines(c.cached(SRC['constitution']), CONSTITUTION_PAGES)), 'PRÉAMBULE',
               'Conakry, le 26 septembre 2025')
    ch = units(paragraphs(lines(c.cached(SRC['charte']), CHARTE_PAGES)), 'PREAMBULE', 'Conakry, le 27 Septembre 2021')
    corpus = {
        'country': {'code': 'GN', 'name': 'Guinea', 'slug': 'guinea', 'lang': 'fr', 'tz': 'Africa/Conakry',
                    'future_branch': 'futur',
                    'publisher': {'name': 'Journal officiel de la République de Guinée (SGG)', 'email': 'jo@sgg.gov.gn.invalid'},
                    'default_in_force_rule': {'text': 'Each text here states its own commencement (Constitution 2025 art. 199: from promulgation; Charte art. 84: from signature).',
                                              'source': SRC['constitution']},
                    'licence_note': 'Journal officiel de la République de Guinée, Secrétariat général du Gouvernement.'},
        'sources': [{'name': 'Journal officiel de la République de Guinée', 'url': 'https://journal-officiel.sgg.gov.gn',
                     'retrieved': '2026-10-28', 'requests': sum(1 for _ in open(os.path.join(c.CACHE, 'requests.jsonl'))),
                     'licence': 'Official texts; robots.txt allows all.',
                     'notes': 'PDF issues with publisher text layer (born-digital InDesign files, no scans). The JO '
                              'index, the site\'s HTML copy of the Charte and the issues published after the '
                              'Constitution (to n° 2026-07, 15 April 2026) were fetched on 2026-10-28/29 for '
                              'verify.py only.'}],
        'laws': {
            'constitution-2025': {'label': 'Constitution du 26 septembre 2025', 'title': 'Constitution de la République de Guinée adoptée par référendum du 21 septembre 2025, promulguée par décret D/2025/176/PRG/CNRD/SGG',
                                  'kind': 'referendum', 'enacted': '2025-09-26', 'published': '2025-09-26', 'url': SRC['constitution'],
                                  'temporary_until': None, 'restores': None, 'note': None},
            'charte-2021': {'label': 'Charte de la Transition du 27 septembre 2021', 'title': 'Charte de la Transition', 'kind': 'law',
                            'enacted': '2021-09-27', 'published': '2021-12-24', 'url': SRC['charte'],
                            'temporary_until': None, 'restores': None, 'note': None},
        },
        'acts': [
            {'slug': 'constitution', 'short': 'Constitution', 'title': 'Constitution de la République de Guinée (2025)', 'url': SRC['constitution'],
             'first_law': 'constitution-2025', 'earlier_laws': [],
             'versions': [{'from': '2025-09-26', 'source_url': SRC['constitution'], 'sha256': c.sha256_of(SRC['constitution']), 'units': cu, 'credits': {}}]},
            {'slug': 'charte-de-la-transition', 'short': 'Charte', 'title': 'Charte de la Transition', 'url': SRC['charte'],
             'first_law': 'charte-2021', 'earlier_laws': [],
             'versions': [{'from': '2021-09-27', 'source_url': SRC['charte'], 'sha256': c.sha256_of(SRC['charte']), 'units': ch, 'credits': {}}]},
        ],
        'applies': [],
        'decisions': ['Constitution 2025 in force 2025-09-26 (art. 199 and promulgation decree D/2025/176 of that day).',
                      'Charte de la Transition in force 2021-09-27 (its art. 84); text from JO n°2021-11 pp. 532-536. Its end is not dated: Constitution art. 196 keeps the transition organs until the new institutions are installed.',
                      'Structural headings (Titre, Chapitre...) are not kept in article files.',
                      'The 2020 Constitution is left out: no JO issue with a text layer containing it was found (2020 ordinary issues are scans).',
                      'Paragraphs are rebuilt from the two-column layout by line geometry (see parse.py); a line that stops short or is followed by a wider gap ends a paragraph unless it breaks off mid-sentence.',
                      'Line-end hyphens that split a word are removed (the Charte prints ordinary hyphens there); hyphens of compounds written so elsewhere in the text, or in a short list (bien-être, soixante-douze ...), are kept.',
                      'Constitution art. 61 is printed by the JO inside the paragraph of art. 60 ("... de ses biens. Article 61. Les écarts ..."); it is split out as its own article without changing a word.',
                      'Each text ends at its signature line ("Conakry, le ..."); the decrees that follow in the same JO issue are not part of it.',
                      'The JO text is kept as printed, including two slips in the Charte ("I ‘Etat" for "l’Etat", "gouvemance"); the PDFs are born-digital, so these are the printed words, not a reading error.',
                      'Checked (verify.py): the Charte equals the site\'s own HTML copy word for word apart from headings, those two slips and three numbers in brackets the site omits; no JO issue published after the Constitution, up to n° 2026-07 of 15 April 2026, revises the Constitution or amends or repeals the Charte.',
                      'The Charte has no end commit: Constitution art. 196 keeps the transition organs and their Charte powers until the new institutions are installed, and no JO text found dates that.'],
        'ai_use': ['Claude Code (claude-opus-5-5) wrote the fetch/parse scripts; no model wrote or edited legal text.'],
    }
    tmp = os.path.join(HERE, 'corpus.json.tmp')
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(corpus, f, ensure_ascii=False, indent=1)
    os.replace(tmp, os.path.join(HERE, 'corpus.json'))
    print('constitution units', len(cu), 'charte units', len(ch))


if __name__ == '__main__':
    main()
