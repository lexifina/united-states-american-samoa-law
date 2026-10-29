"""Checks the latest Constitution version in corpus.json against the Journal officiel's own site text.

    python -X utf8 scripts/dr-congo-law/verify_jo.py

Reads only the cache (journalofficiel.cd/textes-phares/constitution, fetched with fetch.py). The page embeds the
coordinated text of 5 February 2011 in its Inertia page data (publication "description", legal_status "in_force").
Every paragraph of the corpus's last version must appear in that text, once the site's own formatting is set aside:
its editorial notes "(modifié par l'article ...)", list numbers written without a full stop ("23 l'..."), and
spacing. Paragraphs that still do not match are printed for review, together with the same count for the Leganet
reprint that is not used (constitution.SRC_2011_REPRINT).
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

import constitution as c
from fetch import cache_path
from textlib import flat, norm_chars

HERE = Path(__file__).resolve().parent


def norm(s: str) -> str:
    s = flat(norm_chars(s))
    s = re.sub(r'(\w)- (\w)', r'\1\2', s)
    s = re.sub(r'(?:(?<=^)|(?<=\s))(\d+)[.]? (?=\w)', r'\1 ', s)  # "23. l'..." and "23 l'..." alike
    s = s.replace('«', '"').replace('»', '"')
    return re.sub(r'\s+', ' ', s).replace(' ;', ';').replace(' :', ':').replace(' "', '"').replace('" ', '"')


def site_text() -> tuple[dict, str]:
    page = cache_path(c.JO_SITE).read_text(encoding='utf-8')
    data = json.loads(html.unescape(re.search(r'data-page="([^"]*)"', page).group(1)))
    pub = data['props']['publications']['data'][0]
    text = re.sub(r'\(modifiée? par l[’\']article.*?\)', '', pub['description'], flags=re.S)
    return pub, norm(text)


def unmatched(units: dict, site: str) -> list[tuple[str, str]]:
    out = []
    for k, u in sorted(units.items()):
        if k == 'structure':
            continue
        for p in u['text'].splitlines()[1:]:
            if norm(p) not in site:
                out.append((k, p))
    return out


def main() -> int:
    pub, site = site_text()
    print('site:', {k: pub.get(k) for k in ('published_at', 'signature_date', 'journal_number', 'legal_status')})
    corpus = json.loads((HERE / 'corpus.json').read_text(encoding='utf-8'))
    act = next(a for a in corpus['acts'] if a['slug'] == 'constitution')
    last = act['versions'][-1]
    miss = unmatched(last['units'], site)
    total = sum(len(u['text'].splitlines()) - 1 for k, u in last['units'].items() if k != 'structure')
    print(f'corpus {last["from"]} ({last["source_url"]}): {total - len(miss)}/{total} paragraphs found verbatim')
    for k, p in miss:
        print('   ', k, p[:200])
    reprint = unmatched(c.parse(c.SRC_2011_REPRINT), site) if cache_path(c.SRC_2011_REPRINT).exists() else None
    if reprint is not None:
        print(f'unused reprint {c.SRC_2011_REPRINT}: {len(reprint)} paragraphs not found')
    return 0


if __name__ == '__main__':
    sys.exit(main())
