"""Builds scripts/cote-divoire-law/corpus.json from the cache alone (no network). See gitlaw_common/SCHEMA.md.

    python -X utf8 scripts/cote-divoire-law/parse.py

The Constitution of 8 November 2016 in two versions:
- 2016-11-08: the Assemblée nationale's PDF of Loi n° 2016-886 (the text as promulgated), credited to that law.
- 2020-03-19: WIPO Lex's consolidation "telle que modifiée par la loi constitutionnelle n°2020-348 du 19 mars 2020".
  Only the articles WIPO marks "Nouveau" take WIPO's text, credited to Loi constitutionnelle n° 2020-348; every
  other article must agree word for word with the 2016 text (checked here, the build stops otherwise).
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import constitution as C  # noqa: E402
from fetch import CACHE, fetch  # noqa: E402

RETRIEVED = '2026-10-28'

# Articles the 2020 law left alone where WIPO's transcription differs from the 2016 text only by typesetting slips.
# The 2016 wording is kept (no change); each is listed in decisions.
NOISE = {
    26: 'WIPO prints "dévelop pement"',
    51: 'WIPO prints "présidentielles" for "présidentielle"',
    97: 'WIPO prints "huis clos" / "compterendu" for "huis-clos" / "compte rendu"',
    125: 'WIPO prints "environnementet" for "environnement et"',
    152: 'WIPO prints "béné ficiant"',
}


def unit(label: str, kind: str, paras: list[str]) -> dict:
    return {'label': label, 'kind': kind, 'text': f'# {label}\n' + ''.join(p + '\n' for p in paras)}


def art_key(n: int) -> str:
    return f'art-{n:03d}'


def requests_count() -> int:
    with open(CACHE / 'requests.jsonl', encoding='utf-8') as f:
        return sum(1 for _ in f)


def main() -> None:
    d = C.load()
    a16, a20, new20 = d['a16'], d['a20'], d['new20']
    assert sorted(a16) == list(range(1, 185)), 'the 2016 text must have articles 1-184'
    assert sorted(a20) == list(range(1, 185)), 'the 2020 text must have articles 1-184'
    assert C.words(d['pre16']) == C.words(d['pre20']), 'the preamble differs between 2016 and 2020'
    for n in range(1, 185):
        if not new20[n]:
            same = C.words(' '.join(a16[n])) == C.words(' '.join(a20[n]))
            assert same or n in NOISE, f'art. {n} is not marked "Nouveau" but differs from 2016'
            assert not same or n not in NOISE, f'art. {n} is listed as noise but agrees'
    v2_arts, v2_log = C.v2_articles(d)
    marked = sorted(v2_arts)

    units1 = {'preambule': unit('Préambule', 'preamble', d['pre16'].split('\n'))}
    for n in range(1, 185):
        units1[art_key(n)] = unit(f'Article {n}', 'art', a16[n])
    changes = {}
    for n in marked:
        u = unit(f'Article {n}', 'art', v2_arts[n])
        if u['text'] != units1[art_key(n)]['text']:
            changes[art_key(n)] = u
    unchanged_marked = [n for n in marked if art_key(n) not in changes]

    an_sha = hashlib.sha256(d['an_bytes']).hexdigest()
    wipo_sha = hashlib.sha256(d['wipo_bytes']).hexdigest()

    country = {
        'code': 'CI', 'name': 'Côte d’Ivoire', 'slug': 'cote-divoire', 'lang': 'fr', 'tz': 'Africa/Abidjan',
        'future_branch': 'futur',
        'publisher': {'name': 'Assemblée nationale de Côte d’Ivoire', 'email': 'assnat@assnat.invalid'},
        'default_in_force_rule': {
            'text': ('Not applied as a general rule. The Constitution fixes its own entry into force, art. 184: '
                     '"La présente Constitution entre en vigueur à compter du jour de sa promulgation par le Président '
                     'de la République"; each version is dated by the promulgation of the law that made it.'),
            'source': C.AN_2016},
        'licence_note': ('Texts: Assemblée nationale de Côte d’Ivoire (https://www.assnat.ci), Loi n° 2016-886 du 8 '
                         'novembre 2016 portant Constitution; WIPO Lex record CI023 (https://www.wipo.int/wipolex/fr/'
                         'legislation/details/22491), the Constitution as amended by Loi constitutionnelle n° '
                         '2020-348 du 19 mars 2020. Official texts of the Republic of Côte d’Ivoire.'),
    }
    sources = [
        {'name': 'Assemblée nationale de Côte d’Ivoire', 'url': 'https://www.assnat.ci/?-la-constitution-',
         'retrieved': RETRIEVED, 'requests': None,
         'licence': 'Official text of the law. The site footer reads "Copyright ©2019 assnat.ci - Tous droits '
                    'resevés"; it states no licence for the legal texts it publishes.',
         'notes': f'PDF of Loi n° 2016-886 du 08 novembre 2016 portant Constitution (born-digital, text layer), '
                  f'{C.AN_2016}, sha256 {an_sha}. The text as promulgated, signed "Fait à Abidjan, le 08 novembre '
                  f'2016".'},
        {'name': 'WIPO Lex (World Intellectual Property Organization)', 'url': C.WIPO_RECORD,
         'retrieved': RETRIEVED, 'requests': None,
         'licence': 'WIPO Lex reproduces national legislation for information; the text is the official text of '
                    'Côte d’Ivoire. WIPO\'s general terms of use apply to the site.',
         'notes': f'Record CI023 "Loi n° 2016-886 du 08 novembre 2016 portant constitution de la République de Côte '
                  f'd’Ivoire, telle que modifiée par la loi constitutionnelle n°2020-348 du 19 mars 2020" ("Modifié '
                  f'jusqu’à: 19 mars 2020"). Its PDF (text layer, served through a signed link printed on the record '
                  f'page; sha256 {wipo_sha}) gives the words; the HTML rendering on the record page is used only as a '
                  f'witness for paragraph breaks.'},
        {'name': 'All requests', 'url': 'https://www.assnat.ci', 'retrieved': RETRIEVED,
         'requests': requests_count(),
         'licence': 'n/a',
         'notes': 'Every request made while probing and fetching (both sites above, conseil-constitutionnel.ci, '
                  'artci.ci, primature.ci, the Internet Archive CDX index and the Common Crawl index), logged in '
                  '.cache/requests.jsonl; only the three files named above are read by parse.py.'},
    ]
    laws = {
        'loi-2016-886': {
            'label': 'Loi n° 2016-886', 'kind': 'law',
            'title': 'Loi n° 2016-886 du 8 novembre 2016 portant Constitution de la République de Côte d’Ivoire',
            'enacted': '2016-11-08', 'published': None, 'url': C.AN_2016,
            'temporary_until': None, 'restores': None, 'note': None},
        'lc-2020-348': {
            'label': 'Loi constitutionnelle n° 2020-348', 'kind': 'law',
            'title': 'Loi constitutionnelle n° 2020-348 du 19 mars 2020 (révision de la Constitution)',
            'enacted': '2020-03-19', 'published': None, 'url': C.WIPO_RECORD,
            'temporary_until': None, 'restores': None, 'note': None},
    }
    act = {
        'slug': 'constitution', 'short': 'Constitution',
        'title': 'Constitution de la République de Côte d’Ivoire (loi n° 2016-886 du 8 novembre 2016)',
        'url': C.AN_2016, 'first_law': 'loi-2016-886', 'earlier_laws': [],
        'versions': [
            {'from': '2016-11-08', 'source_url': C.AN_2016, 'sha256': an_sha, 'units': units1, 'credits': {},
             'note': 'The text as promulgated (Assemblée nationale PDF, signed "Fait à Abidjan, le 08 novembre 2016"); '
                     'in force from promulgation (art. 184).'},
            {'from': '2020-03-19', 'source_url': C.WIPO_RECORD, 'sha256': wipo_sha, 'changes': changes,
             'credits': {art_key(n): ['lc-2020-348'] for n in marked},
             'note': ('The consolidation published by WIPO Lex, which marks each article rewritten by Loi '
                      'constitutionnelle n° 2020-348 "Nouveau"; only those articles changed.')},
        ],
    }
    decisions = [
        'Acts: the Constitution only. The Code pénal of 2019 (Assemblée nationale PDF, text layer) is cached but its '
        'in-force date has no source yet (the Journal officiel is unreachable and CIVLII was not read), so it is not '
        'built. Loi n° 2013-450 (data protection) is published by ARTCI only as an image scan: left out (no OCR).',
        'Version 1 (2016-11-08) is the Assemblée nationale PDF of Loi n° 2016-886, signed "Fait à Abidjan, le 08 '
        'novembre 2016", dated by art. 184 (in force from promulgation) and credited to that law as enacted.',
        'The Conseil constitutionnel\'s constitution_2016.pdf (Word 2010, May 2017) differs from both the Assemblée '
        'nationale and WIPO texts in 16 articles (2, 21, 27, 31, 33, 78-81, 87, 90, 93, 117, 135, 147, 175), and the '
        'Assemblée nationale text agrees with WIPO on all of them, so it looks like a pre-adoption draft and is not '
        'used.',
        'Version 2 (2020-03-19) is dated by the promulgation of Loi constitutionnelle n° 2020-348: WIPO Lex gives '
        '"Modifié jusqu’à: 19 mars 2020" and its consolidated text is signed "Fait à Abidjan, le 19 mars 2020". The '
        'Journal officiel text of the 2020 law itself, with any entry-into-force clause of its own, was not found; '
        'art. 184 (unchanged) puts the Constitution in force on promulgation.',
        f'Credits for version 2 come only from WIPO\'s own "Nouveau" markers: articles {", ".join(map(str, marked))} '
        f'({len(marked)} articles) are credited to Loi constitutionnelle n° 2020-348. Of these, '
        f'{len(changes)} changed words; '
        + (f'articles {", ".join(map(str, unchanged_marked))} are marked "Nouveau" but read word for word as in 2016, '
           'so they are credited without a change of wording. ' if unchanged_marked else '')
        + 'WIPO also marks the heading "CHAPITRE 4 NOUVEAU"; headings are not units.',
        'Every article not marked "Nouveau" was compared word for word (case, accents, punctuation and line-break '
        'hyphens ignored) with the 2016 text: all agree, except WIPO typesetting slips in articles '
        + '; '.join(f'{n} ({v})' for n, v in NOISE.items()) + '. Those keep the 2016 wording. The preamble agrees too.',
        'Within a "Nouveau" article, a paragraph whose words equal a 2016 paragraph of the same article keeps the 2016 '
        'typesetting (apostrophes, accents on capitals), so only reworded paragraphs show as changed lines.',
        'WIPO\'s PDF reflows the text and runs some paragraphs together (in 10 unchanged articles it merges two 2016 '
        'paragraphs). A "Nouveau" article\'s paragraph is split after a sentence end where the 2016 text or WIPO\'s '
        'HTML rendering of the same record breaks a paragraph at exactly that point (6 words either side): art. 56 '
        '(last paragraph, "La convocation des électeurs…", as in 2016) and art. 137 (third paragraph, "Une disposition '
        'déclarée inconstitutionnelle…", as in the HTML).',
        'Art. 177, last paragraph: WIPO prints "Journal official" (in both its PDF and HTML); the paragraph is '
        'otherwise word for word the 2016 paragraph, which reads "Journal officiel", so "officiel" is kept.',
        'WIPO\'s HTML drops spaces between some words ("cettefin", "dela", "auxlois", "leurconformite" in arts. 62, '
        '134, 177, 181), so it is never the source of words.',
        'Two fixes to the 2016 parse: art. 165 shares a PDF text block with the heading line before it ("DE LA '
        'REPUBLIQUE Article 165") and is split off; WIPO spaces out its preamble heading ("P R É A M B U L E").',
        'Typesetting is normalised once: NBSP to space, one apostrophe (’) and one quotation form (« »), French spacing '
        'before ; : ! ?, list markers (-, •, the Symbol-font bullet) to "— ", column hyphenation joined only where the '
        'whole word is printed somewhere in the sources. The Assemblée nationale PDF breaks list items across text '
        'blocks; a block that does not end in . ; : ! ? » runs on into the next, and items are split at "; -".',
        'Title, chapter and section headings are not units; each file starts with "# Article N". The preamble is one '
        'unit. The promulgation formula and the signature lines are left out.',
        'All dates are promulgation dates; the Journal officiel publication dates were not available, so `published` '
        'is empty.',
    ]
    ai_use = ['Claude Code (Claude Opus 5.5, claude-opus-5-5) wrote fetch.py, pdftext.py, constitution.py and this '
              'parse.py, chose the sources and wrote the decisions. No model wrote, summarised or transformed legal '
              'text: parse.py is deterministic code over the cached PDFs.']
    corpus = {'country': country, 'sources': sources, 'laws': laws, 'acts': [act], 'applies': [],
              'decisions': decisions, 'ai_use': ai_use}
    out = HERE / 'corpus.json'
    tmp = out.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(corpus, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    os.replace(tmp, out)
    print(f'corpus.json: {len(units1)} units; 2020: {len(marked)} marked, {len(changes)} changed; '
          + '; '.join(v2_log))


if __name__ == '__main__':
    main()
