"""Republic of the Congo: build corpus.json from the cache only (no network).

Acts (Phase 1):
  - constitution: Constitution du 25 octobre 2015 (JO 2015 édition spéciale n° 8, 6 November 2015),
    revised by Loi constitutionnelle n° 2-2022 (art. 157; JO 2022 édition spéciale n° 1, 10 January 2022).
  - loi-2019-29: Loi n° 29-2019 du 10 octobre 2019 portant protection des données à caractère personnel
    (JO 2019 n° 45, 7 November 2019). SGG lists no amendment.

Text comes only from the JO PDFs' text layer (jo_text.py). The SGG HTML consolidation of the
Constitution is used as a cross-check in verify.py, never as text.
"""
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fetch  # noqa: E402
import jo_text  # noqa: E402

RETRIEVED = '2026-10-28'
SGG = 'Secrétariat général du gouvernement (SGG), République du Congo'

JO2015 = 'https://sgg.cg/JO/2015/congo-jo-2015-08-sp.pdf'
JO2022 = 'https://sgg.cg/JO/2022/congo-jo-2022-01-sp.pdf'
JO2019 = 'https://sgg.cg/JO/2019/congo-jo-2019-45.pdf'
HTML_CONST = 'https://sgg.cg/droit-congolais/constitution.html'

ROMAN = None


def sha(url):
    with open(fetch.path_for(url), 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


ART_RE = re.compile(r'^Articles?\s+(premier|\d+)(\s+(?:bis|ter|nouveau))?\s*:\s*(.*)$')


def heading_label(num, suffix):
    return 'Article premier' if num == 'premier' else f'Article {num}{suffix or ""}'


def split_articles(paras, preamble_from=None):
    """Group paragraphs into units: an optional preamble, then one unit per article.

    Headings (TITRE / SOUS-TITRE / CHAPITRE / SECTION lines, in capitals or not) end an article and
    are not part of any unit. Returns an ordered dict key -> (label, kind, [paragraphs]).
    """
    units = {}
    cur = None
    in_pre = False
    for p in paras:
        m = ART_RE.match(p)
        if m:
            num = m.group(1)
            n = 1 if num == 'premier' else int(num)
            suf = (m.group(2) or '').strip()
            key = f'art-{n:03d}' + (f'-{suf}' if suf and suf != 'nouveau' else '')
            if key in units:
                raise SystemExit(f'duplicate article {key}: {p[:80]}')
            label = heading_label(num, (' ' + suf) if suf and suf != 'nouveau' else '')
            units[key] = [label, 'art', [m.group(3).strip()] if m.group(3).strip() else []]
            cur = key
            in_pre = False
            continue
        if re.match(r'^(TITRE|SOUS-TITRE|CHAPITRE|SECTION|Titre|Sous-titre|Chapitre|Section)\b', p) or jo_text.is_caps(p):
            if preamble_from and p.startswith(preamble_from):
                units['preambule'] = ['Préambule', 'preamble', []]
                cur = 'preambule'
                in_pre = True
                continue
            cur = None
            continue
        if cur is None:
            continue
        units[cur][2].append(p)
    return units


def to_units(units):
    out = {}
    for key, (label, kind, paras) in units.items():
        text = f'# {label}\n' + ''.join(p + '\n' for p in paras)
        out[key] = {'label': label, 'kind': kind, 'text': text}
    return out


def constitution_2015():
    paras = jo_text.paragraphs(fetch.path_for(JO2015), r'^CONSTITUTION DE LA REPUBLIQUE',
                               r'^Constitution de la République du Congo\.$', first_page=2)
    # The preamble heading line is printed in capitals; split it off its first paragraph if joined.
    units = split_articles(paras, preamble_from='PREAMBULE')
    return to_units(units)


def lc_2022_art157():
    paras = jo_text.paragraphs(fetch.path_for(JO2022), r'^Article premier : L’article 157',
                               r'^Fait à Brazzaville', include_end=False)
    body = []
    on = False
    for p in paras:
        if p.startswith('Article 157 nouveau'):
            on = True
            body.append(re.sub(r'^Article 157 nouveau\s*:\s*', '', p))
            continue
        if on and p.startswith('Article 2'):
            break
        if on:
            body.append(p)
    return {'label': 'Article 157', 'kind': 'art', 'text': '# Article 157\n' + ''.join(p + '\n' for p in body)}


def loi_2019_29():
    paras = jo_text.paragraphs(fetch.path_for(JO2019), r'^Loi n° 29-2019 du 10 octobre 2019 portant',
                               r'^Fait à Brazzaville', first_page=1, include_end=False)
    return to_units(split_articles(paras))


def main():
    c15 = constitution_2015()
    a157 = lc_2022_art157()
    c22 = dict(c15)
    c22['art-157'] = a157
    dp = loi_2019_29()

    corpus = {
        'country': {
            'code': 'CG', 'name': 'Republic of the Congo', 'slug': 'republic-of-congo', 'lang': 'fr',
            'tz': 'Africa/Brazzaville', 'future_branch': 'futur',
            'publisher': {'name': SGG, 'email': 'sgg@sgg.invalid'},
            'default_in_force_rule': {
                'text': ('No general Congolese statute fixing when laws take effect was found on the SGG site. '
                         'Laws end "sera publiée au Journal officiel et exécutée comme loi de l’Etat"; where a '
                         'law names no date of its own, this build dates it by its publication in the Journal '
                         'officiel. The Constitution of 2015 takes effect on promulgation (art. 246).'),
                'source': JO2015,
            },
            'licence_note': ('Official texts of the Republic of the Congo, from the Journal officiel published by '
                             'the Secrétariat général du gouvernement (sgg.cg). Official texts are not protected '
                             'by copyright; no licence is stated on sgg.cg.'),
        },
        'sources': [
            {'name': 'Journal officiel de la République du Congo (SGG, sgg.cg)', 'url': 'https://sgg.cg',
             'retrieved': RETRIEVED, 'requests': count_requests(),
             'licence': 'Official texts; no licence stated on sgg.cg (Mentions légales checked).',
             'notes': ('JO PDFs with a text layer: édition spéciale n° 8 of 6 November 2015 (Constitution), '
                       'édition spéciale n° 1 of 10 January 2022 (Loi constitutionnelle n° 2-2022), n° 45 of '
                       '7 November 2019 (Loi n° 29-2019). The SGG HTML consolidation of the Constitution and '
                       'its search results (amendment lists) were read as cross-checks only.')},
        ],
        'laws': {
            'constitution-2015': {
                'label': 'Constitution du 25 octobre 2015',
                'title': 'Constitution de la République du Congo, adoptée par référendum le 25 octobre 2015',
                'kind': 'referendum', 'enacted': '2015-10-25', 'published': '2015-11-06', 'url': JO2015,
                'temporary_until': None, 'restores': None, 'note': None},
            'lc-2022-2': {
                'label': 'Loi constitutionnelle n° 2-2022',
                'title': 'Loi constitutionnelle n° 2-2022 du 7 janvier 2022 portant révision de l’article 157 '
                         'de la Constitution du 25 octobre 2015',
                'kind': 'law', 'enacted': '2022-01-07', 'published': '2022-01-10', 'url': JO2022,
                'temporary_until': None, 'restores': None, 'note': None},
            'loi-2019-29': {
                'label': 'Loi n° 29-2019',
                'title': 'Loi n° 29-2019 du 10 octobre 2019 portant protection des données à caractère personnel',
                'kind': 'law', 'enacted': '2019-10-10', 'published': '2019-11-07', 'url': JO2019,
                'temporary_until': None, 'restores': None, 'note': None},
        },
        'acts': [
            {'slug': 'constitution', 'short': 'Constitution',
             'title': 'Constitution de la République du Congo du 25 octobre 2015',
             'url': 'https://sgg.cg/droit-congolais/constitution.html',
             'first_law': 'constitution-2015', 'earlier_laws': [],
             'versions': [
                 {'from': '2015-11-06', 'source_url': JO2015, 'sha256': sha(JO2015), 'units': c15, 'credits': {},
                  'note': 'As promulgated (JO édition spéciale n° 8 of 6 November 2015).'},
                 {'from': '2022-01-10', 'source_url': JO2022, 'sha256': sha(JO2022), 'units': c22,
                  'credits': {'art-157': ['lc-2022-2']},
                  'note': 'Article 157 as revised by Loi constitutionnelle n° 2-2022 (JO édition spéciale n° 1 of 10 January 2022).'},
             ]},
            {'slug': 'donnees-personnelles', 'short': 'Loi 29-2019',
             'title': 'Loi n° 29-2019 du 10 octobre 2019 portant protection des données à caractère personnel',
             'url': JO2019, 'first_law': 'loi-2019-29', 'earlier_laws': [],
             'versions': [
                 {'from': '2019-11-07', 'source_url': JO2019, 'sha256': sha(JO2019), 'units': dp, 'credits': {},
                  'note': 'As enacted (JO n° 45 of 7 November 2019). SGG lists no amending law.'},
             ]},
        ],
        'applies': [],
        'decisions': [
            'Text is read only from the Journal officiel PDFs’ text layer; the SGG HTML consolidation of the Constitution differs from the JO in small editorial ways (it drops some figures in brackets such as "(90)" and recases words), so it is used only as a cross-check.',
            'Constitution in force 2015-11-06: art. 246 puts it in force on promulgation; the JO édition spéciale n° 8 that prints "Le Président de la République promulgue la Constitution" is dated vendredi 6 novembre 2015, and no other promulgation date is printed.',
            'Loi constitutionnelle n° 2-2022 dated 2022-01-10 and Loi n° 29-2019 dated 2019-11-07: neither names its own commencement day, so each is dated by its JO issue (default rule above).',
            'Loi n° 29-2019 art. 100 gives existing processing one or two years from entry into force to comply; this is a compliance period, not a commencement, so it is not encoded in applies.',
            'Words hyphenated at a JO line end are rejoined without the hyphen unless one side is a known compound part (quatre-vingt, celui-ci, peut-être and the like); see jo_text.KEEP_HYPHEN_LEFT/RIGHT.',
            'Titles, sub-titles and chapter headings are not units; each unit is the preamble or one article, one paragraph or list item per line.',
            'JO 2015 prints "Articles 194 :" (a typo for Article 194); the parser reads it as Article 194.',
            'Code pénal not built: SGG lists the Code pénal du Congo as the French code applied by arrêté of 13 February 1882, not published in the JO and with no text on sgg.cg; amendments are scattered ordinances (e.g. Ord. 62-13). Skipped under the 45-minute rule.',
            'Code de la famille (1984) not built: the SGG PDF is a scan with no text layer (no OCR by rule).',
        ],
        'ai_use': ['none: no model produced or edited any text or date at data-build time. The parser and checks were written by Claude Code (claude-opus-5-5).'],
    }
    tmp = os.path.join(HERE, 'corpus.json.tmp')
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(corpus, f, ensure_ascii=False, indent=1, sort_keys=False)
        f.write('\n')
    os.replace(tmp, os.path.join(HERE, 'corpus.json'))
    for a in corpus['acts']:
        print(a['slug'], [(v['from'], len(v['units'])) for v in a['versions']])


def count_requests():
    p = os.path.join(fetch.CACHE, 'requests.jsonl')
    if not os.path.exists(p):
        return 0
    with open(p, encoding='utf-8') as f:
        return sum(1 for line in f if line.strip())


if __name__ == '__main__':
    main()
