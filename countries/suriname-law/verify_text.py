"""python -X utf8 scripts/suriname-law/verify_text.py 25   (or: dna)

Independent completeness check: every body word in the PDF appears in the parsed units and vice versa
(as a sequence, with headings and line-break hyphenation the only allowed differences)."""
import sys, re, difflib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding='utf-8')
import parse as P

which = sys.argv[1]
url, first = {'25': (P.SB_2025_15, 2), 'dna': (P.DNA_GW_1992, 0)}[which]
rows, _ = P.pdf_rows(P.cached(url))
pdf = []
started = False
for r in rows:
    if r['page'] < first:
        continue
    t = P.norm(r['text'])
    if re.match(r'^\d{4} -\s*\d+\s*- No\. \d+$', t) or re.fullmatch(r'-?\s*\d+\s*-?', t):
        continue
    if t.startswith('Preambule'):
        started = True
    if not started:
        continue
    if t.startswith('Gegeven te Paramaribo') or t.startswith('MEMORIE VAN TOELICHTING'):
        break
    pdf.extend(t.split())
units, _, heads = P.grondwet(url, first, P.FOOTNOTE_LAW)
ours = []
order = ['preambule'] + sorted(k for k in units if k.startswith('art-'))
for k in order:
    lines = units[k]['text'].splitlines()
    ours.extend(['Preambule'] if k == 'preambule' else lines[0][2:].split())
    for l in lines[1:]:
        ours.extend(l.split())
headwords = set(w for h in heads for w in h.split())
bad = 0
for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, pdf, ours, autojunk=False).get_opcodes():
    if tag == 'equal':
        continue
    a, b = pdf[i1:i2], ours[j1:j2]
    if tag == 'delete' and all(w in headwords for w in a):
        continue
    if ''.join(a).replace('-', '') == ''.join(b).replace('-', ''):
        continue  # line-end hyphenation joined
    bad += 1
    print(tag, a[:30], '|', b[:30])
print('words pdf', len(pdf), 'ours', len(ours), 'unexplained', bad)
