"""Checks corpus.json against the Journal officiel's other expressions. Reads only the cache.

    python -X utf8 scripts/guinea-law/verify.py

1. The Charte de la Transition against the site's own HTML copy (journal-officiel.sgg.gov.gn, "Textes de droit
   guinéen: Charte de la transition"): word for word, once headings and article labels are set aside. The site's
   copy is edited (lists run inline, "(15)" style numbers dropped, two slips of the printed JO corrected); every
   remaining difference is printed.
2. Every JO issue in sources.json published after the Constitution of 26 September 2025 is searched for a revision
   of the Constitution or an amendment or repeal of the Charte.
"""
import difflib
import html
import json
import os
import re

import fitz

import gncache as c

HERE = os.path.dirname(os.path.abspath(__file__))
SITE_CHARTE = 'https://journal-officiel.sgg.gov.gn/fr/textes-officiels/constitution.html'
CHANGE = re.compile(r'(?i)(r[ée]vision de la constitution|loi constitutionnelle|modifiant la constitution|'
                    r'rectificatif[^\n]{0,60}constitution|charte de la transition[^\n]{0,60}(modifi|r[ée]vis|abrog))')


def words(text):
    text = text.replace('’', "'").replace('‘', "'").replace('œ', 'oe')
    text = re.sub(r'Art(icle)?\.?\s*(\d+|premier|1er)\s*(\.-|:)', ' ', text)
    text = re.sub(r'(Titre|Chapitre|Section)\s+[\dIVX]+\s*-[^.;:]*?(?=Art\.|$)', ' ', text)
    return re.findall(r'\w+', text.lower())


def charte_vs_site(corpus):
    page = open(c.cached(SITE_CHARTE), encoding='utf-8', errors='replace').read()
    page = re.sub(r'<script.*?</script>|<style.*?</style>', '', page, flags=re.S)
    s = html.unescape(re.sub(r'<[^>]+>', ' ', page))
    i = s.find('Nous, Membres des Forces')
    site = words(s[i:s.find('Conakry, le 27', i)])
    u = next(a for a in corpus['acts'] if a['slug'] == 'charte-de-la-transition')['versions'][-1]['units']
    order = ['preambule'] + sorted(k for k in u if k.startswith('art-'))
    ours = words('\n'.join('\n'.join(u[k]['text'].splitlines()[1:]) for k in order))
    sm = difflib.SequenceMatcher(None, ours, site, autojunk=False)
    print(f'Charte: {len(ours)} words in the corpus, {len(site)} on the site; differences other than headings:')
    for op, a, b, x, y in sm.get_opcodes():
        if op == 'equal':
            continue
        jo, web = ' '.join(ours[a:b]), ' '.join(site[x:y])
        if op == 'insert' and re.match(r'(titre|chapitre|section) ', web):
            continue
        print(f'   {op:7} JO: {jo[:80]!r:40} site: {web[:80]!r}')


def later_issues():
    with open(os.path.join(HERE, 'sources.json'), encoding='utf-8') as f:
        files = [s for s in json.load(f)['files'] if s.get('role') == 'later-issue']
    found = 0
    for s in files:
        d = fitz.open(c.cached(s['url']))
        text = ''.join(p.get_text() for p in d)
        hits = sorted({m.group(0) for m in CHANGE.finditer(text)})
        found += len(hits)
        print(f'   {s["url"].rsplit("/", 1)[1]:32} {d.page_count:3} pages, {len(text):7} chars of text layer, {hits or "no change"}')
    print(f'Later issues: {len(files)} searched, {found} mentions of a change')


def main():
    with open(os.path.join(HERE, 'corpus.json'), encoding='utf-8') as f:
        corpus = json.load(f)
    charte_vs_site(corpus)
    later_issues()


if __name__ == '__main__':
    main()
