"""Read only .cache/ and write corpus.json for Togo (Phase 1).

Acts, each from the born-digital Journal officiel (jo.gouv.tg) text layer:
- Constitution de la République Togolaise (Loi n° 2024-005 du 06/05/2024, JO 2024 n° 42 bis), with its annexed
  Déclaration solennelle des droits et devoirs fondamentaux: one version, as promulgated.
- Loi n° 2019-014 relative à la protection des données à caractère personnel (JO 2019 n° 26 ter): one version.
- Loi n° 2021-012 portant code du travail (JO 2021 n° 26 ter), and its art. 190 as replaced by Loi n° 2022-019 du
  15 novembre 2022 (JO 2022 n° 49 bis): two versions.

Paragraphs come from the PDF layout, not from line ends: the JO sets a blank line (a vertical gap of about two lines)
between paragraphs, and article numbers, titles and chapter headings in bold. Lines are read column by column. A
paragraph that runs over a column or page break is joined unless its last line ends a sentence. Running heads, dates
and page numbers are dropped. No OCR, no model output.

    python -X utf8 scripts/togo-law/parse.py
"""
from __future__ import annotations

import collections
import difflib
import hashlib
import json
import re
import sys
from pathlib import Path

import fitz

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'

JO_2024 = 'https://jo.gouv.tg/sites/default/files/JO/JOS_06_05_2024%20-%2069%20E%20ANNEE%20N%C2%B042%20BIS%20.pdf'
JO_2019 = 'https://jo.gouv.tg/sites/default/files/JO/JOS_29_10_2019-64E%20ANNEE-N%C2%B026%20TER.pdf'
JO_2021 = 'https://jo.gouv.tg/sites/default/files/JO/JOS_18_06_2021%20-66E%20ANNEE%20N%C2%B0%2026%20TER.pdf'
JO_2022 = 'https://jo.gouv.tg/sites/default/files/JO/JOS_15_11_2022-67E%20ANNEE%20N%C2%B049%20BIS.pdf'
AN_2019 = 'https://web.archive.org/web/20230605220852id_/https://assemblee-nationale.tg/wp-content/uploads/2021/10/donnees-perso-LOI-AN.pdf'
AN_2024 = 'https://web.archive.org/web/20240711213129id_/https://assemblee-nationale.tg/wp-content/uploads/2024/05/CONSTITUTION-V-REPUBLIQUE-2024.pdf'
NODES = {'2019-014': JO_2019, '2021-012': 'https://jo.gouv.tg/node/15570', '2022-019': 'https://jo.gouv.tg/node/15631'}
HEAD = re.compile(r'^(Article premier|Art\.\s*(\d+)|Article (\d+))\s*(nouveau)?\s*:\s*')   # CT art. 214: "Article 214 :"
HEADING = re.compile(r'^(TITRE|CHAPITRE|Chapitre|SECTION|Section|SOUS-SECTION|Sous-section|SOUS-TITRE|ANNEXE|Préambule)\b')


def raw(url: str) -> bytes:
    p = CACHE / hashlib.sha256(url.encode('utf-8')).hexdigest()
    if not p.exists():
        raise FileNotFoundError(f'not in cache (run fetch.py): {url}')
    return p.read_bytes()


def norm(s: str) -> str:
    s = re.sub(r'([ﬁﬂ]) (?=[-a-zàâçéèêëîïôûùüœ]|$)', r'\1', s)       # "conﬁ ées" -> "confiées", "conﬁ -" too
    s = s.replace('ﬁ', 'fi').replace('ﬂ', 'fl').replace('ﬀ', 'ff')
    s = s.replace(' ', ' ').replace(' ', ' ').replace('­', '').replace('\t', ' ')
    s = s.replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"')
    s = s.replace('–', '-').replace('—', '-')
    return re.sub(r' +', ' ', s).strip()


# ---------------------------------------------------------------- layout reading

def jo_lines(pdf: bytes) -> list[dict]:
    """Every text line of a JO PDF in reading order: page, column (left/right half), then top to bottom."""
    out = []
    for pno, page in enumerate(fitz.open(stream=pdf, filetype='pdf')):
        mid = page.rect.width / 2
        rows: dict[tuple, list] = collections.defaultdict(list)
        for b in page.get_text('dict')['blocks']:
            for ln in b.get('lines', []):
                x0, y0 = ln['bbox'][0], ln['bbox'][1]
                for sp in ln['spans']:
                    if sp['text'] == '':
                        continue
                    col = 0 if x0 < mid - 10 else 1
                    rows[(col, round(y0))].append((sp['bbox'][0], sp['text'], bool(sp['flags'] & 16)))
        merged: dict[tuple, list] = {}
        for (col, y) in sorted(rows):                 # spans of one line can sit 1 pt apart
            key = next((k for k in merged if k[0] == col and abs(k[1] - y) <= 2), (col, y))
            merged.setdefault(key, []).extend(rows[(col, y)])
        for (col, y), spans in sorted(merged.items()):
            spans.sort()
            text = norm(''.join(t for _, t, _ in spans))
            if not text:
                continue
            visible = [(t, b) for _, t, b in spans if t.strip('  :.,')]
            out.append({'p': pno, 'col': col, 'y': y, 'text': text,
                        'bold_all': bool(visible) and all(b for _, b in visible),
                        'bold_first': bool(visible) and visible[0][1]})
    return [ln for ln in out if not furniture(ln['text'])]


def furniture(t: str) -> bool:
    return ('JOURNAL OFFICIEL DE LA REPUBLIQUE TOGOLAISE' in t or re.fullmatch(r'\d{1,3}', t) is not None
            or re.fullmatch(r'\d{1,2} +\w+ +\d{4}', t) is not None or t in ('Imp. Editogo',)
            or re.match(r'Dépôt +légal\b', t) is not None)


def segment(lines: list[dict], title: str) -> list[dict]:
    """The lines of one law: from its bold title line (not the table of contents) to its "Fait à Lomé"."""
    i = next(k for k, ln in enumerate(lines) if ln['bold_all'] and ln['text'].upper().startswith(title.upper()))
    j = next(k for k in range(i, len(lines)) if lines[k]['text'].startswith('Fait à Lomé'))
    return lines[i:j + 1]


def join(a: str, b: str, vocab: collections.Counter) -> str:
    """Join two lines of one paragraph, undoing end-of-line hyphenation where the document supports it."""
    m = re.search(r'(\w+)-$', a)
    if m and b[:1].islower():
        w1, w2 = m.group(1), re.match(r'\w+', b).group(0) if re.match(r'\w+', b) else ''
        hyph, joined = vocab[(w1 + '-' + w2).lower()], vocab[(w1 + w2).lower()]
        numbers = ('dix', 'vingt', 'trente', 'quarante', 'cinquante', 'soixante', 'quatre')
        if hyph > joined or (joined == 0 and (w2.lower() in ('ci', 'là', 'delà', 'même', 'mêmes')
                                               or (w1.lower() in numbers and w2.lower() in numbers + ('un', 'deux', 'trois', 'cinq', 'six', 'sept', 'huit', 'neuf', 'onze', 'douze'))
                                               or (vocab[w1.lower()] and vocab[w2.lower()]))):
            return a + b                                  # a real compound broken at its hyphen
        return a[:-1] + b
    return a + ' ' + b


def heading_like(t: str) -> bool:
    """Titre/Chapitre/Section lines and all-capital lines; other bold text (defined terms) is law text."""
    return bool(HEADING.match(t)) or (t.upper() == t and re.search(r'[A-ZÉÈ]{3}', t) is not None)


def paragraphs(lines: list[dict]) -> list[dict]:
    # Vocabulary of whole words: the pieces either side of a line-end hyphen are left out of it.
    toks = []
    for k, ln in enumerate(lines):
        t = ln['text']
        if t.endswith('-'):
            t = re.sub(r'\S+$', '', t)
        if k and lines[k - 1]['text'].endswith('-'):
            t = re.sub(r'^\S+', '', t)
        toks += re.findall(r"\w+(?:-\w+)*", t)
    vocab = collections.Counter(w.lower() for w in toks)
    paras: list[dict] = []
    prev = None
    for ln in lines:
        new = prev is None
        if prev is not None:
            moved = (ln['p'], ln['col']) != (prev['p'], prev['col'])
            if moved:
                new = bool(re.search(r'[.;:!?»]$', prev['text']))
            else:
                new = ln['y'] - prev['y'] > 19
            if HEAD.match(ln['text']) and ln['bold_first'] or ln['text'].startswith('Fait à Lomé'):
                new = True
            if ln['bold_all'] and heading_like(ln['text']) and not paras[-1]['heading']:
                new = True                                # a heading starts
            if paras[-1]['heading'] and not ln['bold_all']:
                new = True                                # a heading ends
        if new:
            paras.append({'text': ln['text'], 'bold_all': ln['bold_all'],
                          'heading': ln['bold_all'] and heading_like(ln['text']),
                          'head': bool(HEAD.match(ln['text']) and ln['bold_first'])})
        else:
            paras[-1]['text'] = join(paras[-1]['text'], ln['text'], vocab)
            paras[-1]['bold_all'] = paras[-1]['bold_all'] and ln['bold_all']
        prev = ln
    for p in paras:
        p['text'] = re.sub(r' +', ' ', p['text']).strip()
    return paras


def articles(paras: list[dict], stop: str = 'Fait à Lomé') -> tuple[dict, list[str], list[str]]:
    """(number -> lines, lines before the first article, headings dropped)."""
    arts: dict[int, list[str]] = {}
    before: list[str] = []
    headings: list[str] = []
    cur = None
    for p in paras:
        t = p['text']
        if t.startswith(stop):
            break
        m = HEAD.match(t)
        n = (1 if m.group(1) == 'Article premier' else int(m.group(2) or m.group(3))) if m else None
        if m and (p['head'] or n == (cur or 0) + 1):     # a few heads (2019-014 arts. 30, 56) are not set in bold
            cur = n
            assert cur not in arts, cur
            rest = t[m.end():].strip()
            arts[cur] = [rest] if rest else []
        elif p['heading'] or HEADING.match(t):
            headings.append(t)
        elif cur is None:
            before.append(t)
        else:
            arts[cur].append(t)
    return arts, before, headings


def unit(label: str, lines: list[str], kind: str = 'art') -> dict:
    assert lines, label
    return {'label': label, 'kind': kind, 'text': '\n'.join([f'# {label}'] + lines) + '\n'}


# ---------------------------------------------------------------- the acts

def constitution() -> tuple[dict, list[str]]:
    lines = segment(jo_lines(raw(JO_2024)), 'LOI N° 2024-005')
    paras = paragraphs(lines)
    k = next(i for i, p in enumerate(paras) if p['text'] == 'Préambule')
    a = next(i for i, p in enumerate(paras) if p['text'].startswith('ANNEXE'))
    arts, pre, h1 = articles(paras[k + 1:a])
    darts, dpre, h2 = articles(paras[a + 1:])
    assert sorted(arts) == list(range(1, 101)), sorted(arts)
    assert sorted(darts) == list(range(1, 26)), sorted(darts)
    units = {'preambule': unit('Préambule', pre, 'preamble')}
    units.update({f'art-{n:03d}': unit(f'Article {n}', ls) for n, ls in sorted(arts.items())})
    units['declaration-preambule'] = unit('Déclaration, préambule', dpre, 'preamble')
    units.update({f'declaration-art-{n:03d}': unit(f'Déclaration, article {n}', ls) for n, ls in sorted(darts.items())})
    return units, h1 + h2


def donnees_personnelles() -> tuple[dict, list[str]]:
    paras = paragraphs(segment(jo_lines(raw(JO_2019)), 'LOI N° 2019-014'))
    arts, before, headings = articles(paras)
    assert sorted(arts) == list(range(1, 98)), sorted(arts)
    return {f'art-{n:03d}': unit(f'Article {n}', ls) for n, ls in sorted(arts.items())}, headings


def code_du_travail() -> tuple[dict, dict, list[str]]:
    paras = paragraphs(segment(jo_lines(raw(JO_2021)), 'LOI N° 2021-012'))
    arts, before, headings = articles(paras)
    assert sorted(arts) == list(range(1, 379)), sorted(set(range(1, 379)) ^ set(arts))
    units = {f'art-{n:03d}': unit(f'Article {n}', ls) for n, ls in sorted(arts.items())}
    am = paragraphs(segment(jo_lines(raw(JO_2022)), 'LOI N° 2022-019'))
    aarts, _, _ = articles(am)
    assert sorted(aarts) == [1, 2, 190], sorted(aarts)   # art. 1 (the amending clause) holds "Art. 190 nouveau"
    return units, {'art-190': unit('Article 190', aarts[190])}, headings


# ---------------------------------------------------------------- checks

def word_diff(a: str, b: str, limit: int = 12) -> list[str]:
    wa, wb = a.split(), b.split()
    sm = difflib.SequenceMatcher(None, wa, wb, autojunk=False)
    return [f'"{" ".join(wa[i1:i2])}" / "{" ".join(wb[j1:j2])}"' for tag, i1, i2, j1, j2 in sm.get_opcodes()
            if tag != 'equal'][:limit]


def an_2019_check(units: dict) -> list[str]:
    """Compare Loi 2019-014 (JO) article by article with the Assemblée nationale's text as adopted in plenary on
    23 October 2019. Returns one line per article whose words differ (letter case and spacing aside)."""
    doc = fitz.open(stream=raw(AN_2019), filetype='pdf')
    lines = [norm(ln) for p in doc for ln in p.get_text().split('\n')]
    t = ' '.join(ln for ln in lines if ln and not re.fullmatch(r'\d{1,3}', ln))
    t = re.sub(r'(\w)- (\w)', r'\1-\2', t)                        # "celui- ci" -> "celui-ci"
    parts = re.split(r'\bArticle (premier|\d+) ?: ?', t[t.find('Article premier'):])
    an = {}
    for k in range(1, len(parts) - 1, 2):
        body = re.split(r'\s(CHAPITRE [IVX]+\b|Section \d|Fait à Lomé|LE PRESIDENT)', parts[k + 1])[0]
        an.setdefault(1 if parts[k] == 'premier' else int(parts[k]), body)
    out = []
    for key, u in units.items():
        n = int(key.split('-')[1])
        jo = re.sub(r'^# .*\n', '', u['text']).replace('\n', ' ')
        d = word_diff(re.sub(r'\(0(\d)\)', r'(\1)', jo).lower(), re.sub(r'\(0(\d)\)', r'(\1)', an.get(n, '')).lower(), 3)
        if d:
            out.append(f'art. {n}: ' + '; '.join(d))
    return out


def dropped(paras: list[dict], units: dict, headings: list[str]) -> collections.Counter:
    """Words of the law's paragraphs (title to signature) in no unit and no heading: must be only the title, the
    enacting formula, article numbers and the signature."""
    src = ' '.join(p['text'] for p in paras)
    have = ' '.join(re.sub(r'^# .*\n', '', u['text']) for u in units.values()) + ' ' + ' '.join(headings)
    return collections.Counter(re.findall(r'\w+', src.lower())) - collections.Counter(re.findall(r'\w+', have.lower()))


def text_of(url: str) -> str:
    return re.sub(r'\s+', ' ', ' '.join(p.get_text() for p in fitz.open(stream=raw(url), filetype='pdf')))


def main() -> None:
    sys.stdout.reconfigure(encoding='utf-8')
    c_units, c_head = constitution()
    d_units, d_head = donnees_personnelles()
    t_units, t_190, t_head = code_du_travail()
    an_diffs = an_2019_check(d_units)
    an24 = word_diff(text_of(AN_2024), text_of(JO_2024))
    assert an24 == ['"des ministres" / ""'], an24          # the only difference: art. 60, second sentence
    for name, url, title, units, head in [('constitution', JO_2024, 'LOI N° 2024-005', c_units, c_head),
                                          ('donnees-personnelles', JO_2019, 'LOI N° 2019-014', d_units, d_head),
                                          ('code-du-travail', JO_2021, 'LOI N° 2021-012', t_units, t_head)]:
        paras = paragraphs(segment(jo_lines(raw(url)), title))
        print(name, len(units), 'units; words in no unit or heading:', dict(dropped(paras, units, head)))
    print('AN 2019 vs JO differences:', len(an_diffs))
    for d in an_diffs:
        print('  ', d)

    req = sum(1 for _ in open(CACHE / 'requests.jsonl', encoding='utf-8'))
    law = lambda label, title, enacted, published, url, note=None: {  # noqa: E731
        'label': label, 'title': title, 'kind': 'law', 'enacted': enacted, 'published': published, 'url': url,
        'temporary_until': None, 'restores': None, 'note': note}
    corpus = {
        'country': {'code': 'TG', 'name': 'Togo', 'slug': 'togo', 'lang': 'fr', 'tz': 'Africa/Lome', 'future_branch': 'futur',
                    'publisher': {'name': 'Journal Officiel de la République togolaise', 'email': 'jo@jo.gouv.tg.invalid'},
                    'default_in_force_rule': {
                        'text': ('Constitution du 6 mai 2024, art. 33: « Les lois entrent en vigueur dès leur '
                                 'promulgation. » Before it, no general rule on the entry into force of laws was found; '
                                 'each law ends « sera exécutée comme loi de l\'Etat » and is dated here by its '
                                 'promulgation, the date of its « Fait à Lomé » line.'),
                        'source': JO_2024},
                    'licence_note': 'Source: Journal Officiel de la République togolaise (jo.gouv.tg).'},
        'sources': [
            {'name': 'Journal Officiel de la République togolaise', 'url': 'https://jo.gouv.tg', 'retrieved': '2026-10-29',
             'requests': req, 'licence': 'Official legislation; no licence stated on jo.gouv.tg',
             'notes': ('JO issue PDFs with a born-digital text layer (doPDF); robots.txt Crawl-delay 10 honoured. The '
                       'site\'s search (recherche) and node pages were used to find the texts and any later amendment.')},
            {'name': 'Assemblée nationale du Togo (assemblee-nationale.tg), via the Internet Archive',
             'url': 'https://assemblee-nationale.tg/wp-content/uploads/2021/10/donnees-perso-LOI-AN.pdf',
             'retrieved': '2026-10-28', 'requests': 2, 'licence': 'Official; no licence stated',
             'notes': ('Used only to check: the data protection law as adopted in plenary on 23 October 2019 (capture '
                       '2023-06-05), and the Assembly\'s copy of the 2024 Constitution (capture 2024-07-11, the JO file).')},
        ],
        'laws': {
            'loi-2024-005': law('Loi n° 2024-005', 'Loi n° 2024-005 du 06/05/2024 portant Constitution de la République Togolaise',
                                '2024-05-06', '2024-05-06', JO_2024),
            'loi-2019-014': law('Loi n° 2019-014', 'Loi n° 2019-014 du 29 octobre 2019 relative à la protection des données à caractère personnel',
                                '2019-10-30', '2019-10-29', NODES['2019-014']),
            'loi-2021-012': law('Loi n° 2021-012', 'Loi n° 2021-012 du 18 juin 2021 portant code du travail',
                                '2021-06-18', '2021-06-18', NODES['2021-012']),
            'loi-2022-019': law('Loi n° 2022-019', 'Loi n° 2022-019 du 15 novembre 2022 portant modification de la loi n° 2021-012 du 18 juin 2021 portant code du travail',
                                '2022-11-15', '2022-11-15', NODES['2022-019']),
        },
        'acts': [
            {'slug': 'constitution', 'short': 'Const.', 'title': 'Constitution de la République Togolaise',
             'url': JO_2024, 'first_law': 'loi-2024-005', 'earlier_laws': [],
             'versions': [{'from': '2024-05-06', 'source_url': JO_2024, 'sha256': hashlib.sha256(raw(JO_2024)).hexdigest(),
                           'units': c_units, 'credits': {}}]},
            {'slug': 'donnees-personnelles', 'short': 'LPDCP',
             'title': 'Loi n° 2019-014 relative à la protection des données à caractère personnel',
             'url': JO_2019, 'first_law': 'loi-2019-014', 'earlier_laws': [],
             'versions': [{'from': '2019-10-30', 'source_url': JO_2019, 'sha256': hashlib.sha256(raw(JO_2019)).hexdigest(),
                           'units': d_units, 'credits': {}}]},
            {'slug': 'code-du-travail', 'short': 'CT', 'title': 'Code du travail (Loi n° 2021-012 du 18 juin 2021)',
             'url': JO_2021, 'first_law': 'loi-2021-012', 'earlier_laws': [],
             'versions': [{'from': '2021-06-18', 'source_url': JO_2021, 'sha256': hashlib.sha256(raw(JO_2021)).hexdigest(),
                           'units': t_units, 'credits': {}},
                          {'from': '2022-11-15', 'source_url': JO_2022, 'sha256': hashlib.sha256(raw(JO_2022)).hexdigest(),
                           'changes': t_190, 'credits': {'art-190': ['loi-2022-019']}}]},
        ],
        'applies': [],
        'decisions': [
            ('Phase 1 is the 2024 Constitution, Loi 2019-014 (data protection) and the Code du travail of 2021: each has a '
             'born-digital text in the Journal officiel. The Code pénal (Loi 2015-010) is published only as a scan with '
             'a poor OCR layer, so it is left out (no OCR). The 1992 Constitution and its revisions (2002, 2005, 2007, '
             '2019) are a separate, repealed act and are not built yet; their JO texts are cached.'),
            ('The 2024 Constitution took effect on promulgation, 6 May 2024 (art. 33; art. 100), the day of JO 2024 n° 42 '
             'bis. Its annexed Déclaration solennelle des droits et devoirs fondamentaux is part of the law and is kept '
             'as declaration-* units, with its own opening sentence as declaration-preambule.'),
            ('Laws before 2024: no general rule on entry into force was found (the 1992 Constitution has none for laws). '
             'Each law ends « sera exécutée comme loi de l\'Etat » and is dated by its promulgation, the date of its '
             '« Fait à Lomé » line: Loi 2021-012 on 18 June 2021 and Loi 2022-019 on 15 November 2022 (each published '
             'in the JO that day).'),
            ('Loi 2019-014 is titled « du 29 octobre 2019 » and printed in the JO of 29 October 2019, but signed « Fait '
             'à Lomé, le 30 octobre 2019 ». It cannot take effect before it is signed, so it is dated 30 October 2019; '
             'enacted is the signature date and published the JO date.'),
            ('Loi 2019-014 was compared word for word with the Assemblée nationale\'s text as adopted in plenary on 23 '
             f'October 2019 (headings and article numbers aside): {len(an_diffs)} differences' +
             (': ' + ' | '.join(an_diffs) if an_diffs else '') + '. The JO text is kept.'),
            ('Code du travail: Loi 2022-019 (JO 2022 n° 49 bis) replaces art. 190 only; that is version 2, credited to it. '
             'The JO search (by title, reference and body text, 2026-10-29) shows no other law amending the Code du '
             'travail, Loi 2019-014 or the 2024 Constitution. The newest issue on jo.gouv.tg (home page, 2026-10-29) '
             'is n° 98 bis of 23 October 2025.'),
            ('Paragraphs follow the JO layout (a blank line between paragraphs, bold heads); a line-end hyphen is removed '
             'unless the hyphenated form occurs more often than the joined form elsewhere in the same issue, or, when '
             'neither occurs, the two parts are both words of the issue, the second is ci/là/delà/même(s), or both '
             'are number words (au-delà, celle-ci, quatre-vingt-dix, sous-traite). The '
             'running heads, page numbers, chapter and section headings, the enacting formula and the signatures are '
             'left out; each article file starts « # Article N » and the article number is not repeated in the text.'),
            ('The Assemblée nationale also published the 2024 Constitution as a JO-styled PDF (uploaded May 2024, '
             'Internet Archive capture of 11 July 2024). Its text is the JO\'s word for word except art. 60, where it '
             'reads « nommés par le Président du Conseil des ministres sur proposition du garde des Sceaux » and the JO '
             'file on jo.gouv.tg reads « nommés par le Président du Conseil sur proposition du garde des Sceaux ». The '
             'Journal officiel is the official publication, and its wording is kept.'),
            ('The earlier first cut (preview a33a6c3) of the Constitution dropped the preamble\'s opening sentence and '
             'let six heading fragments into articles; this parser replaces it.'),
        ],
        'ai_use': ['none: no model wrote or transcribed legal text; parsing is rule-based (parse.py).'],
    }
    tmp = HERE / 'corpus.json.tmp'
    tmp.write_text(json.dumps(corpus, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    tmp.replace(HERE / 'corpus.json')
    print('AN copy of the 2024 Constitution vs JO:', an24)


if __name__ == '__main__':
    main()
