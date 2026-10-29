"""Reads only .cache/ and writes corpus.json for DR Congo (gitlaw_common/SCHEMA.md).

    python -X utf8 scripts/dr-congo-law/parse.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import constitution

HERE = Path(__file__).resolve().parent
RETRIEVED = '2026-10-28'


def main() -> None:
    corpus = {
        'country': {
            'code': 'CD', 'name': 'DR Congo', 'slug': 'dr-congo', 'lang': 'fr', 'tz': 'Africa/Kinshasa',
            'future_branch': 'futur',
            'publisher': {'name': 'Journal officiel de la République démocratique du Congo', 'email': 'jo@journalofficiel.invalid'},
            'default_in_force_rule': {
                'text': 'No general rule is used: each act here states its own entry into force (Constitution art. 229; '
                        'Loi n° 11/002 art. 3: on promulgation).',
                'source': constitution.SRC_2006},
            'licence_note': 'Texts: Journal officiel de la République démocratique du Congo (official texts), '
                            'copies hosted by Leganet (PPDS), www.leganet.be.',
        },
        'sources': [{'name': 'Journal officiel PDFs hosted by Leganet (leganet.be, formerly leganet.cd)',
                     'url': 'https://www.leganet.be/JO.htm', 'retrieved': RETRIEVED, 'requests': 6,
                     'licence': 'Official texts; Leganet states no licence; robots.txt absent (404).',
                     'notes': 'Text-layer PDFs; journalofficiel.cd itself sells the PDFs.'},
                    {'name': 'Journal officiel de la RDC (journalofficiel.cd), Textes phares: Constitution',
                     'url': constitution.JO_SITE, 'retrieved': '2026-10-29', 'requests': 1,
                     'licence': 'Official text; the site states no licence.',
                     'notes': 'Used only to verify the latest version (verify_jo.py): the page embeds the coordinated '
                              'text of 5 February 2011 with legal_status "in_force".'}],
        'laws': {
            'constitution-2006': {'label': 'Constitution du 18 février 2006', 'kind': 'referendum',
                                  'title': 'Constitution de la République Démocratique du Congo',
                                  'enacted': '2006-02-18', 'published': '2006-02-18', 'url': constitution.SRC_2006,
                                  'temporary_until': None, 'restores': None,
                                  'note': None},
            'loi-11-002': {'label': 'Loi n° 11/002', 'kind': 'law',
                           'title': 'Loi n° 11/002 du 20 janvier 2011 portant révision de certains articles de la '
                                    'Constitution de la République Démocratique du Congo du 18 février 2006',
                           'enacted': '2011-01-20', 'published': '2011-02-01', 'url': constitution.SRC_LAW_11_002,
                           'temporary_until': None, 'restores': None, 'note': None},
        },
        'acts': [{
            'slug': 'constitution', 'short': 'Constitution',
            'title': 'Constitution de la République Démocratique du Congo du 18 février 2006',
            'url': constitution.SRC_2011, 'first_law': 'constitution-2006', 'earlier_laws': [],
            'versions': constitution.versions(),
        }],
        'applies': [],
        'decisions': [
            'Constitution in force on 2006-02-18: art. 229, "entre en vigueur dès sa promulgation"; promulgated 18 February 2006 (JO numéro spécial).',
            'Loi n° 11/002 in force on 2011-01-20: its art. 3, "entre en vigueur à la date de sa promulgation"; signed 20 January 2011.',
            'The 2011-01-20 version is the 2006 text with the eight articles of Loi 11/002 art. 1er and the § 5 heading of art. 2 replaced by the law\'s own wording (JO 1 February 2011).',
            'The JO coordinated text of 5 February 2011 differs editorially from the promulgated wording; those differences are a separate publisher commit labelled unexplained, not credited to Loi 11/002.',
            'The 2011-02-05 version is read from Leganet\'s Droit Public/Constitution.2011.pdf, not from its JO/2011/JOS.05.02.2011.pdf: both carry the header of the JO numéro spécial of 5 February 2011 but differ in 83 units, and the Journal officiel\'s own site text agrees with the first in 78 of them and with the second (a 2012 reprint) in none.',
            'Checked against the Journal officiel\'s site text (verify_jo.py): 901 of 906 paragraphs of the 2011-02-05 version appear verbatim; the other 5 differ only where the site\'s own text is broken (a final full stop missing before the next article, or another article\'s text spliced in).',
            'A paragraph or heading that ends on a word such as "à", "de", "les", "au" or "cette" continues on the next line, across a blank line or page break (Constitution art. 119, 153, 200 heading, § 3 heading).',
            'Units whose wording is identical apart from line breaks keep the earlier version\'s lines.',
            'Structural headings (titres, chapitres, sections, paragraphes) are kept in one unit, constitution/structure.',
            'The garbled exposé des motifs on page 1 of the JO of 1 February 2011 (broken font encoding) is not used; only the operative articles are.',
        ],
        'ai_use': ['none: no model output at data-build time; parsing is rule-based (Claude Opus 5.5 wrote the scripts).'],
    }
    tmp = HERE / 'corpus.json.tmp'
    tmp.write_text(json.dumps(corpus, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    os.replace(tmp, HERE / 'corpus.json')
    print('versions', [v['from'] for v in corpus['acts'][0]['versions']])


if __name__ == '__main__':
    main()
