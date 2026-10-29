"""python -X utf8 scripts/suriname-law/verify_codes.py bw|rv

Independent completeness check for the 2024 codes: the words of the law-text pages, read with PyMuPDF's own word
extraction (page.get_text('words'), not the line reader parse_codes.py uses), must appear in the parsed units in the
same order. Allowed differences: headings (kept in the indeling units), running headers, the Books' title pages,
and words joined across a line-end hyphen. Prints every other difference and the count."""
import difflib
import re
import sys
from pathlib import Path

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
import parse_codes as C  # noqa: E402

which = sys.argv[1]
units, pages, url = C.load_code(which)
doc = fitz.open(C.P.cached(url))
pdf = []
for p in pages:
    page = doc[p]
    words = page.get_text('words', sort=True)
    lines = C.page_lines(page)
    if len(lines) < 14 and any(re.match(r'^WET van \d+ \w+ \d{4},?$', x['text']) for x in lines):
        pdf.extend(w for x in lines if re.match(r'^BOEK \d+$', x['text']) for w in x['text'].split())
        continue
    if which == 'kr':
        # footnotes and their reference numbers are left out of the text: keep 12 pt spans only
        for b in page.get_text('dict')['blocks']:
            for l in b.get('lines', []):
                if l['bbox'][1] < 50:
                    continue
                for s in l['spans']:
                    if C.body_span(s):
                        pdf.extend(C.norm(x) for x in s['text'].split())
        continue
    for w in words:
        if w[1] < 50:          # running header band
            continue
        pdf.append(C.norm(w[4]))
pdf = [w for w in pdf if w]
ours, heads = [], set()
for k, u in units.items():
    lines = u['text'].splitlines()
    if u['kind'] == 'structure':
        heads.update(w for l in lines[1:] for w in l.split())
        continue
    ours.extend(lines[0][2:].split()[2 if lines[0].startswith('# Boek') else 0:])
    for l in lines[1:]:
        ours.extend(l.split())
heads.update(['BOEK'] + [str(i) for i in range(1, 9)] + ['Artikel'])
bad = 0
# align in windows of 2000 PDF words (a whole-text SequenceMatcher is quadratic on 500k words)
i = j = 0
W = 2000
while i < len(pdf):
    a_all = pdf[i:i + W]
    b_all = ours[j:j + W + 400]
    ops = difflib.SequenceMatcher(None, a_all, b_all, autojunk=False).get_opcodes()
    last = i + W >= len(pdf)
    # keep the ops up to the last 'equal' block that ends inside this window, then resume from there
    cut = None
    for n, op in enumerate(ops):
        if op[0] == 'equal':
            cut = n
    if not last and cut is not None:
        ops = ops[:cut + 1]
    for tag, i1, i2, j1, j2 in ops:
        if tag == 'equal':
            continue
        a, b = a_all[i1:i2], b_all[j1:j2]
        if tag == 'delete' and all(w in heads for w in a):
            continue
        if ''.join(a).replace('-', '') == ''.join(b).replace('-', ''):
            continue
        bad += 1
        if bad <= 60:
            print(tag, a[:20], '|', b[:20])
    if last or cut is None:
        if not last:
            print('lost alignment at pdf word', i)
            bad += 1
        break
    i += ops[-1][2]
    j += ops[-1][4]
else:
    pass
if j < len(ours) and i >= len(pdf):
    pass
print('words pdf', len(pdf), 'ours', len(ours), 'unexplained', bad)
# a heading swallowed by the article before it would pass the word check: look for heading-shaped lines in articles
swallowed = 0
for k, u in units.items():
    if u['kind'] != 'art':
        continue
    for l in u['text'].splitlines()[1:]:
        if C.strong_heading(l):
            swallowed += 1
            print('heading-like line in', k, repr(l[:80]))
print('heading-like lines inside articles', swallowed)
