"""Read only .cache/ and write corpus.json for Senegal (Phase 1).

Acts built (each one version, as enacted, from its own official text):
- Loi n° 2008-12 du 25 janvier 2008 portant sur la Protection des données à caractère personnel: the Journal officiel's
  web edition (jo.gouv.sn, JO n° 6406 du 3 mai 2008), read from its Internet Archive capture.
- Loi organique n° 2016-23 du 14 juillet 2016 relative au Conseil constitutionnel: the Conseil constitutionnel's own
  page (conseilconstitutionnel.sn), which cites JORS numéro spécial 6946 du 15 juillet 2016.

Each act's text is checked here: the JO text of Loi 2008-12 against the Commission de Protection des Données
Personnelles' PDF of the same law (differences are printed and listed in decisions). No OCR, no model output.

    python -X utf8 scripts/senegal-law/parse.py
"""
from __future__ import annotations

import datetime as dt
import difflib
import hashlib
import html
import json
import re
import sys
from pathlib import Path

import fitz

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fetch  # noqa: E402
import sncache  # noqa: E402

JO_2008_12 = sncache.raw(*fetch.ARCHIVED[0])
JO_6406_TOC = sncache.raw(*fetch.ARCHIVED[1])
CDP_2008_12 = sncache.raw(*fetch.ARCHIVED[2])
CDP_PAGE = sncache.raw(*fetch.ARCHIVED[3])
CC_LO = 'https://conseilconstitutionnel.sn/la-loi-organique/'
VP_70_14 = fetch.DIRECT[5]
VP_2021_21 = fetch.DIRECT[6]
RETRIEVED = '2026-10-29'


def raw(url: str) -> bytes:
    return sncache.get(url, offline=True)


def decode(b: bytes) -> str:
    try:
        return b.decode('utf-8')
    except UnicodeDecodeError:
        return b.decode('cp1252', 'replace')


def norm(s: str) -> str:
    """One form of spaces, apostrophes, quotes and dashes (SCHEMA: normalise publisher typesetting once)."""
    s = s.replace(' ', ' ').replace(' ', ' ').replace(' ', ' ').replace('­', '')
    s = s.replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"')
    s = s.replace('–', '-').replace('—', '-').replace('\t', ' ')
    s = re.sub(r'(?<=\S)«', ' «', s)
    s = re.sub(r'«\s*', '« ', s)
    s = re.sub(r'\s*»', ' »', s)
    return re.sub(r' +', ' ', s).strip()


def paragraphs(fragment: str) -> list[tuple[str, str]]:
    """(kind, text) for each <p>/<li> of an HTML fragment, <br> splitting lines; kind is 'center', 'strong' or 'text'."""
    out = []
    for m in re.finditer(r'<(p|li)\b([^>]*)>(.*?)</\1>', fragment, re.S | re.I):
        attrs, inner = m.group(2), m.group(3)
        for piece in re.split(r'<br\s*/?>', inner, flags=re.I):
            text = norm(html.unescape(re.sub(r'<[^>]+>', ' ', piece)))
            if not text:
                continue
            plain = re.sub(r'<(strong|b|em|i)\b[^>]*>|</(strong|b|em|i)>|\s|&nbsp;', '', piece, flags=re.I)
            kind = 'center' if 'center' in attrs.lower() else 'text'
            if re.fullmatch(r'\s*(<(strong|b)\b[^>]*>.*</(strong|b)>)\s*', piece.strip(), re.S | re.I) and plain:
                kind = 'strong'
            out.append((kind, text))
    return out


def unit(n: int, lines: list[str]) -> dict:
    label = f'Article {n}'
    return {'label': label, 'kind': 'art', 'text': '\n'.join([f'# {label}'] + lines) + '\n'}


# ---------------------------------------------------------------- Loi 2008-12 (JO n° 6406)

def loi_2008_12() -> tuple[dict, list[str]]:
    s = decode(raw(JO_2008_12))
    # The page prints the law twice (page body and a second, identical block); read the first, check the second.
    starts = [m.start() for m in re.finditer('promulgue la loi', s)]
    assert len(starts) == 2, starts
    copies = [s[i:s.find('Fait &agrave; Dakar', i)] for i in starts]
    assert copies[0] == copies[1] and len(copies[0]) > 50000
    body = copies[0] + '<p>Fait à Dakar</p>'
    paras = paragraphs(body)
    arts: dict[int, list[str]] = {}
    cur = None
    for kind, t in paras[1:]:
        m = re.fullmatch(r'Article\s+(Premier|\d+)(\s*[.:])*', t, re.I)   # "Article 14 :." and "Article 74 :" too
        if m:
            cur = 1 if m.group(1).lower() == 'premier' else int(m.group(1))
            assert cur not in arts, cur
            arts[cur] = []
            continue
        if t.startswith('Fait à Dakar'):
            break
        if kind == 'strong' or cur is None:          # chapter and section headings
            continue
        arts[cur].append(t)
    assert sorted(arts) == list(range(1, 79)), sorted(arts)
    assert all(arts.values())
    for n, (old, new) in SLIPS.items():               # web-edition slips, corrected from the CDP's copy
        hits = [k for k, ln in enumerate(arts[n]) if old in ln]
        assert len(hits) == 1, (n, old)
        arts[n][hits[0]] = arts[n][hits[0]].replace(old, new, 1)
    units = {f'art-{n:03d}': unit(n, ls) for n, ls in sorted(arts.items())}
    return units, compare_cdp(arts)


# Transcription slips in the JO web edition of Loi 2008-12, read correctly in the CDP's PDF (listed in decisions).
SLIPS = {16: (') elle reçoit les formalités', 'a) elle reçoit les formalités'),
         57: ('taritements', 'traitements')}


def compare_cdp(jo: dict[int, list[str]]) -> list[str]:
    """Word-level comparison of each article with the CDP's PDF of the law; returns one line per differing article."""
    doc = fitz.open(stream=raw(CDP_2008_12), filetype='pdf')
    text = norm(' '.join(p.get_text() for p in doc).replace('\n', ' '))
    i = text.find('promulgue la loi')
    parts = re.split(r'\bArticle (premier|\d+)\s*[.:]\s', text[i:], flags=re.I)
    cdp = {}
    for k in range(1, len(parts) - 1, 2):
        n = 1 if parts[k].lower() == 'premier' else int(parts[k])
        cdp.setdefault(n, parts[k + 1])
    out = []
    for n, lines in sorted(jo.items()):
        a = re.sub(r'(Chapitre|Section) [IVXLC]+.*$|Chapitre premier.*$', '', ' '.join(lines)).split()
        b = re.sub(r'\s(Chapitre|CHAPITRE|Section|SECTION) [IVXLC0-9]+\b.*$|\sChapitre premier.*$', '',
                   cdp.get(n, '')).split()
        if a != b:
            sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
            ops = [(' '.join(a[i1:i2]), ' '.join(b[j1:j2])) for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != 'equal']
            out.append(f'art. {n}: ' + '; '.join(f'JO "{x}" / CDP "{y}"' for x, y in ops[:4]))
    return out


# ---------------------------------------------------------------- Loi organique 2016-23 (Conseil constitutionnel)

def lo_2016_23() -> dict:
    s = decode(raw(CC_LO))
    body = s[s.find('promulgue la loi dont la teneur suit'):s.find('.entry-content')]
    arts: dict[int, list[str]] = {}
    cur = None
    for kind, t in paragraphs(body)[1:]:
        if t.startswith('Fait à Dakar'):
            break
        if re.match(r'(TITRE|Chapitre|CHAPITRE|Section)\b', t):
            continue
        m = re.match(r'(Article premier|Art\. ?(\d+))\.? ?- ?(.*)$', t)
        if m:
            cur = 1 if m.group(1) == 'Article premier' else int(m.group(2))
            assert cur not in arts, cur
            arts[cur] = [m.group(3).strip()] if m.group(3).strip() else []
            continue
        if t == "La présente loi organique sera exécutée comme loi de l'État.":
            continue                                   # executory formula, not part of art. 27
        if cur is not None:
            arts[cur].append(t)
    assert sorted(arts) == list(range(1, 28)), sorted(arts)
    return {f'art-{n:03d}': unit(n, ls) for n, ls in sorted(arts.items())}


# ---------------------------------------------------------------- dates

def in_force_70_14(deposit: dt.date) -> dt.date:
    """Loi n° 70-14, art. 2: executory in the Cap-Vert region (Dakar) on the 3rd day after the JO's deposit, the
    delay extended by each Sunday among the days before that 3rd day (public holidays are not modelled)."""
    day = deposit + dt.timedelta(days=3)
    extra = sum(1 for k in (1, 2) if (deposit + dt.timedelta(days=k)).weekday() == 6)
    return day + dt.timedelta(days=extra)


def main() -> None:
    sys.stdout.reconfigure(encoding='utf-8')
    toc = decode(raw(JO_6406_TOC))
    assert re.search(r'6406 du Samedi\s+3 mai\s+2008', toc) and 'article6663' in toc
    dp_units, dp_diffs = loi_2008_12()
    lo_units = lo_2016_23()
    lo_html = decode(raw(CC_LO))
    assert 'JORS NS 6946 du 15 juillet 2016' in lo_html

    dp_from = in_force_70_14(dt.date(2008, 5, 3)).isoformat()
    lo_from = in_force_70_14(dt.date(2016, 7, 15)).isoformat()
    assert (dp_from, lo_from) == ('2008-05-07', '2016-07-19'), (dp_from, lo_from)

    req = sum(1 for _ in open(HERE / '.cache' / 'requests.jsonl', encoding='utf-8'))
    corpus = {
        'country': {
            'code': 'SN', 'name': 'Senegal', 'slug': 'senegal', 'lang': 'fr', 'tz': 'Africa/Dakar',
            'future_branch': 'futur',
            'publisher': {'name': 'Journal officiel de la République du Sénégal', 'email': 'jo@jo.gouv.sn.invalid'},
            'default_in_force_rule': {
                'text': ("Loi n° 70-14 du 6 février 1970, art. 2: laws become executory in the Cap-Vert region (Dakar) on "
                         "the 3rd day after the Journal officiel that prints them is deposited with the Secrétariat "
                         "général de la Présidence, extended by any Sunday or public holiday before that day. Replaced "
                         "for laws published from 20 March 2021 by Loi n° 2021-21 du 2 mars 2021, art. 10: in force "
                         "« un jour franc à compter de leur publication au Journal officiel »."),
                'source': VP_70_14},
            'licence_note': ('Texts: Journal officiel de la République du Sénégal (jo.gouv.sn, Internet Archive copy) and '
                             'Conseil constitutionnel du Sénégal (conseilconstitutionnel.sn), official texts of the '
                             'Republic of Senegal.'),
        },
        'sources': [
            {'name': 'Journal officiel de la République du Sénégal (jo.gouv.sn), via the Internet Archive',
             'url': 'http://www.jo.gouv.sn/spip.php?article6663', 'retrieved': '2026-10-28', 'requests': req,
             'licence': 'Official legislation; the site read "© Copyrights Gouvernement du Sénégal" and states no licence',
             'notes': ('jo.gouv.sn no longer answers; read from Wayback id_ captures pinned in fetch.py '
                       '(article6663 captured 2015-06-09 21:49:03 UTC; rubrique437 = JO n° 6406 captured 2015-06-09).')},
            {'name': 'Conseil constitutionnel du Sénégal', 'url': CC_LO, 'retrieved': '2026-10-28', 'requests': 1,
             'licence': 'Official legislation; the site reads "© Copyright 2026. tous droits réservés"',
             'notes': 'Loi organique n° 2016-23 as published in JORS NS 6946 du 15 juillet 2016, pp. 927-930.'},
            {'name': 'Commission de Protection des Données Personnelles (cdp.sn), via the Internet Archive',
             'url': 'http://www.cdp.sn/sites/default/files/protection.pdf', 'retrieved': '2026-10-29', 'requests': 2,
             'licence': 'Official authority; no licence stated',
             'notes': ('Used only to check Loi 2008-12: its PDF (a 2013 Word export, sha256 of the cached bytes in '
                       'decisions) and its law page, captured 2025-01-24, which still links that PDF as the law.')},
            {'name': 'Vie Publique Sénégal (www.vie-publique.sn)', 'url': 'https://www.vie-publique.sn',
             'retrieved': '2026-10-29', 'requests': 20,
             'licence': 'Civic publisher; robots.txt "Allow: /", Content-Signal use=reference',
             'notes': ('Used for the texts fixing the default in-force rule (Loi 70-14 scan with its publisher text '
                       'layer; Loi 2021-21 in JO n° 7409 du 20 mars 2021) and to check that no later law replaced the '
                       'acts built. No legal text in the record comes from it.')},
        ],
        'laws': {
            'loi-2008-12': {'label': 'Loi n° 2008-12',
                            'title': 'Loi n° 2008-12 du 25 janvier 2008 portant sur la Protection des données à caractère personnel',
                            'kind': 'law', 'enacted': '2008-01-25', 'published': '2008-05-03',
                            'url': 'http://www.jo.gouv.sn/spip.php?article6663',
                            'temporary_until': None, 'restores': None, 'note': None},
            'lo-2016-23': {'label': 'Loi organique n° 2016-23',
                           'title': 'Loi organique n° 2016-23 du 14 juillet 2016 relative au Conseil constitutionnel',
                           'kind': 'law', 'enacted': '2016-07-14', 'published': '2016-07-15', 'url': CC_LO,
                           'temporary_until': None, 'restores': None, 'note': None},
        },
        'acts': [
            {'slug': 'donnees-personnelles', 'short': 'LDCP',
             'title': 'Loi n° 2008-12 du 25 janvier 2008 portant sur la Protection des données à caractère personnel',
             'url': 'http://www.jo.gouv.sn/spip.php?article6663', 'first_law': 'loi-2008-12', 'earlier_laws': [],
             'versions': [{'from': dp_from, 'source_url': JO_2008_12,
                           'sha256': hashlib.sha256(raw(JO_2008_12)).hexdigest(), 'units': dp_units, 'credits': {}}]},
            {'slug': 'conseil-constitutionnel', 'short': 'LOCC',
             'title': 'Loi organique n° 2016-23 du 14 juillet 2016 relative au Conseil constitutionnel',
             'url': CC_LO, 'first_law': 'lo-2016-23', 'earlier_laws': [],
             'publisher': {'name': 'Conseil constitutionnel du Sénégal', 'email': 'cc@conseilconstitutionnel.sn.invalid'},
             'versions': [{'from': lo_from, 'source_url': CC_LO,
                           'sha256': hashlib.sha256(raw(CC_LO)).hexdigest(), 'units': lo_units, 'credits': {}}]},
        ],
        'applies': [],
        'decisions': [
            ('Phase 1 is Loi 2008-12 (data protection) and Loi organique 2016-23 (Conseil constitutionnel): the two '
             'core texts with a complete official text layer. The Code pénal (Loi 65-60) is only available as image '
             'scans (cdp.sn code_penal.pdf, vie-publique), so it is left out (no OCR).'),
            ('The Constitution of 2001 is not built yet. Its only consolidation (Conseil constitutionnel, la-constitution, '
             'à jour of Loi constitutionnelle 2018-14) interleaves about 100 editorial notes and « » change markers inside '
             'the paragraphs of the text, with no clean copy to check a de-annotation against; LC 2019-10 (JO 7181) and '
             'LC 2021-41 (JO 7483) are cached. Vie-publique.sn also lists a "Loi n° 11/2024 portant révision de la '
             'Constitution" (14 décembre 2024) published only as a 2-page image scan, whose status could not be settled.'),
            ('Loi 2008-12 is taken from the Journal officiel web edition (JO n° 6406 du samedi 3 mai 2008, '
             'spip.php?article6663), the official publication. Its text was compared article by article with the CDP\'s '
             'PDF (protection.pdf, the same file vie-publique serves): ' +
             (f'{len(dp_diffs)} articles differ: ' + ' | '.join(dp_diffs) if dp_diffs else 'all 78 articles agree word for word') +
             '. The JO wording is kept (the CDP PDF lacks the last sentence of art. 78 and splits two words at line '
             'ends), except two transcription slips of the web edition, corrected from the CDP copy: ' +
             '; '.join(f'art. {n}: "{a}" read as "{b}"' for n, (a, b) in SLIPS.items()) + '.'),
            ('Loi organique 2016-23 is taken from the Conseil constitutionnel\'s own page, which gives the law as '
             'promulgated (JORS NS 6946 du 15 juillet 2016, pp. 927-930) with no later amendment noted.'),
            ('In-force dates follow Loi n° 70-14 art. 2 (both acts were published before Loi 2021-21 took over): the 3rd '
             'day after the JO\'s deposit at the Secrétariat général de la Présidence, plus one day for each Sunday before '
             'it. The deposit receipts for JO 6406 and JORS 6946 were not found, so the deposit is taken to be the issue '
             f'date: Loi 2008-12 (JO 3 May 2008, a Saturday) is dated {dp_from}; LO 2016-23 (JORS 15 July 2016, a '
             f'Friday) is dated {lo_from}. Public holidays are not modelled; none fell in those windows that we know of. '
             'Loi 70-14 was amended by Loi 71-07 (21 January 1971), which was not available to check.'),
            ('Loi 70-14 is read from the text layer the publisher (Direction des relations avec les institutions, via '
             'vie-publique.sn) put on its scan; it is cited only for the rule and no legal text in the record comes '
             'from it.'),
            ('The exposé des motifs, chapter and section headings, the enacting formula, the executory formula '
             '("sera exécutée comme loi de l\'État") and the signatures are left out; each article is one file, '
             'one paragraph or list item per line.'),
            ('Today\'s text: no amending law to either act was found. The CDP\'s law page (captured 2025-01-24) and '
             'vie-publique.sn (retrieved 2026-10-29) still give Loi 2008-12 as the data protection law; the Conseil '
             'constitutionnel still publishes Loi organique 2016-23 unamended (retrieved 2026-10-28). A 2026 '
             'constitutional revision (loi n° 18/2026) that would have replaced the Conseil by a Cour constitutionnelle '
             'was declared unconstitutional (décision n° 6/C/2026 du 9 juillet 2026) and never took effect.'),
            'Common Crawl\'s index (index.commoncrawl.org) timed out on 2026-10-28 and again on 2026-10-29, so only the Internet Archive was used.',
        ],
        'ai_use': ['none: no model wrote or transcribed legal text; parsing is rule-based (parse.py).'],
    }
    tmp = HERE / 'corpus.json.tmp'
    tmp.write_text(json.dumps(corpus, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    tmp.replace(HERE / 'corpus.json')
    print('donnees-personnelles', len(dp_units), 'units, from', dp_from)
    print('conseil-constitutionnel', len(lo_units), 'units, from', lo_from)
    print('JO vs CDP differences:', len(dp_diffs))
    for d in dp_diffs:
        print('  ', d)


if __name__ == '__main__':
    main()
