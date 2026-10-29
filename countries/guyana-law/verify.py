"""Check each act's latest version in corpus.json against today's official text (L.R.O. 1/2022 PDFs on
mola.gov.gy, cached).

    python -X utf8 verify.py

Word-count check, both ways, over the act's pages of the official PDF (from the Constitution's PREAMBLE heading, or
an Act's long title, to the end of the act):
- every word of the latest version must be printed in the PDF (only the "# Article N" / "# Section N" / "# Preamble"
  heading lines are ours), and
- every word printed in the PDF must be in the latest version, or be one of what parse.py leaves out on purpose:
  running heads and feet, marginal notes, long titles, Part/Chapter/Title headings and repeal-only placeholders.
Reads the cache only.
"""
import collections
import json
import re
import sys
from pathlib import Path

import fitz

import fetch
import layout
import parse

HERE = Path(__file__).resolve().parent
ACTS = {  # slug: (edition, prefix, start marker in the raw PDF text)
    'constitution': (parse.EDITIONS['e2022'], 'art', 'PREAMBLE'),
    'civil-law': (parse.CIVIL_EDITIONS['e2022'], 'sec', r'An\s+Act'),
    'criminal-law-offences': (parse.CRIM_EDITIONS['e2022'], 'sec', r'An\s+Act'),
}


def words(s: str) -> collections.Counter:
    return collections.Counter(re.findall(r'[A-Za-z]+', s))


def check(c: dict, slug: str, ed: str = 'e2022') -> bool:
    act = next(a for a in c['acts'] if a['slug'] == slug)
    (url, first, last, body_min), prefix, marker = ACTS[slug]
    if ed != 'e2022':   # an older edition: its own version, with the 2012 PDF's own pages
        url, first, last, body_min = {'constitution': parse.EDITIONS, 'civil-law': parse.CIVIL_EDITIONS,
                                      'criminal-law-offences': parse.CRIM_EDITIONS}[slug][ed]
    units = next(v for v in act['versions'] if v['source_url'] == url)['units'] if ed != 'e2022' else         act['versions'][-1]['units']
    ours = words(' '.join(u['text'] for u in units.values()))
    ours_heads = words(' '.join(u['text'].split('\n', 1)[0] for k, u in units.items() if not k.startswith('sch-')))
    doc = fitz.open(stream=fetch.cached(url), filetype='pdf')
    raw = ' '.join(doc[i].get_text() for i in range(first, last + 1))
    raw = raw[re.search(marker, raw).start():]
    pdf = words(raw)
    # a word broken at a line end ("composi-" / "tion") is one word in the repository
    for m in re.finditer(r'([A-Za-z]+)-[ \t]*\n\s*([A-Za-z]+)', raw):
        a, b = m.group(1), m.group(2)
        if ours[a + b] > pdf[a + b] and pdf[a] and pdf[b]:
            pdf[a + b] += 1
            pdf[a] -= 1
            pdf[b] -= 1
    added = (ours - ours_heads) - pdf
    paras = layout.read_edition(url, ed, first, last, body_min)
    start = next(i for i, p in enumerate(paras) if (p.text == 'PREAMBLE' if prefix == 'art'
                                                    else parse.LONG_TITLE.match(p.text)))
    left_out = collections.Counter()
    in_title = prefix == 'sec'
    for p in paras[start:]:
        left_out += words(' '.join(p.margin))
        if in_title and parse.ART_RE.match(p.text):
            in_title = False
        if (in_title or p.heading or layout._is_heading(p.text) or p.text in parse.DROPPED
                or parse.PLACEHOLDER.match(p.text)
                or parse.RANGE_RE.match(p.text) or re.match(r'^\d+\s?\.\s*\[', p.text)):
            left_out += words(p.text)
    running = words(f'LAWS OF GUYANA Cap {act["title"]} L.R.O. Constitution of the Co-operative Republic of Guyana')
    for k, n in running.items():
        left_out[k] += n * (last + 1 - first)
    dropped = pdf - ours - left_out
    print(f'{slug} ({ed}): official PDF words {sum(pdf.values())}, latest version words {sum(ours.values())}')
    print(f'  in the repository but not printed in the PDF: {sum(added.values())} {added.most_common(10)}')
    print(f'  printed in the PDF, neither in the repository nor left out on purpose: {sum(dropped.values())} '
          f'{dropped.most_common(12)}')
    return not added and sum(dropped.values()) <= 10


def main() -> int:
    c = json.loads((HERE / 'corpus.json').read_text(encoding='utf-8'))
    parse.civil_law(), parse.criminal_law()   # fills parse.DROPPED (cross-headings left out on purpose)
    ok =[check(c, slug) for slug in ACTS]
    if '--older' in sys.argv:   # the L.R.O. 1/2012 versions too (informational)
        for slug in ACTS:
            check(c, slug, 'e2012')
    return 0 if all(ok) else 1


if __name__ == '__main__':
    sys.exit(main())
