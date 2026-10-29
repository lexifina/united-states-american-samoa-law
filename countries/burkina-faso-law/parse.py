"""Burkina Faso git-for-law: read the cached LegiBurkina PDF of the Constitution (born-digital text layer only) and
write corpus.json in the gitlaw_common SCHEMA.md format. No network; the same cache gives the same bytes.

    python -X utf8 scripts/burkina-faso-law/parse.py

Source: "Constitution du 02 juin 1991, révisée en 2015", the Assemblée nationale's consolidation after Loi
constitutionnelle n°072-2015/CNT du 05 novembre 2015, as published on LegiBurkina (SGG-CM). Body text is 14.3 pt;
footnotes (9.8 pt) and footnote markers (6-9 pt superscripts) are dropped by size. Paragraphs are rebuilt from the
justified layout: a line that stops short of the right margin closes a paragraph, and so does a blank line after a
sentence end (a blank line after a full, unfinished line is a page break inside the paragraph).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from pathlib import Path

import fitz  # PyMuPDF

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
RETRIEVED = '2026-10-29'
LEGI = 'https://www.legiburkina.gov.bf'
C2015 = f'{LEGI}/documents/b157d74c-23a1-4025-a8d6-0061e83df0c2/download'
C2015_PAGE = f'{LEGI}/textesFondamentaux'


def cached(url: str) -> Path:
    return CACHE / hashlib.sha256(url.encode('utf-8')).hexdigest()


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def norm(s: str) -> str:
    s = unicodedata.normalize('NFC', s)
    for a, b in ((' ', ' '), (' ', ' '), (' ', ' '), ('\t', ' '), ('’', "'"), ('‘', "'"), ('ʼ', "'"),
                 ('“', '«'), ('”', '»'), ('—', '–'), ('‑', '-'), ('', '-'), ('', '-'),
                 ('', '-')):
        s = s.replace(a, b)
    s = re.sub(r'«\s*', '« ', s)
    s = re.sub(r'\s*»', ' »', s)
    s = re.sub(r' {2,}', ' ', s)
    return s.strip()


# ------------------------------------------------------------------ PDF -> visual lines

BODY_MIN = 11.0      # body text is 14.3 pt; footnotes 9.8 pt, markers 6-9 pt
RIGHT = 528.0        # right margin of the justified body text


def visual_lines(pdf: Path) -> list[dict]:
    """Body-text lines in reading order. Spans on one baseline are merged; whitespace-only lines become blanks."""
    out = []
    doc = fitz.open(pdf)
    for pno, page in enumerate(doc):
        rows: list[dict] = []
        for b in page.get_text('dict')['blocks']:
            for ln in b.get('lines', []):
                for s in ln['spans']:
                    x0, y0, x1, y1 = s['bbox']
                    # list dashes at the body indent are sometimes set at 9.8 pt: kept (below) if their row has body text
                    dash = s['text'].strip() == '-' and 85 <= x0 <= 100
                    if (s['size'] < BODY_MIN and not dash) or s['flags'] & 1:
                        continue
                    yc = (y0 + y1) / 2
                    row = next((r for r in rows if abs(r['yc'] - yc) < 4), None)
                    if row is None:
                        row = {'yc': yc, 'spans': []}
                        rows.append(row)
                    row['spans'].append((x0, x1, s['text'], bool(s['flags'] & 16), s['size']))
        rows.sort(key=lambda r: r['yc'])
        for r in rows:
            sp = sorted(r['spans'])
            if not any(z >= BODY_MIN and t.strip() for _, _, t, _, z in sp):
                sp = [s for s in sp if s[4] >= BODY_MIN]     # a footnote dash alone, or a blank row
            elif sp[0][4] < BODY_MIN:
                sp[0] = (sp[0][0], sp[0][1], '- ', sp[0][3], BODY_MIN)
            text = ''.join(t for _, _, t, _, _ in sp)
            ink = [(a, b) for a, b, t, _, _ in sp if t.strip()]
            if not ink:
                out.append({'page': pno, 'blank': True})
                continue
            bold = all(bd for _, _, t, bd, _ in sp if t.strip())
            size = max(z for _, _, t, _, z in sp if t.strip())
            out.append({'page': pno, 'blank': False, 'text': norm(text), 'x0': ink[0][0], 'x1': ink[-1][1], 'y': r['yc'],
                        'bold': bold, 'size': size})
    return out


ART_RX = re.compile(r'^Article\s+(\d+|premier)(?:\s*\.\s*(\d+))?\s*(er)?\s*(bis|ter|quater)?\s*:?\s*(.*)$')
HEAD_RX = re.compile(r'^(TITRE|Titre|CHAPITRE|Chapitre|SECTION|Section)\s+([IVXLC]+|\d+|unique|premier|1er)\b')
TERMINAL = ('.', ';', ':', '!', '?', '»')
LINE_GAP = 21.0      # body lines are about 16.7 pt apart; a larger gap separates paragraphs


def join(a: str, b: str) -> str:
    if a.endswith('-') and not a.endswith(' -') and b[:1].islower():
        return a + b      # line-end hyphen in a compound word (no soft hyphens in this file)
    return a + ' ' + b


def paragraphs(lines: list[dict]) -> list[dict]:
    """Visual lines to paragraphs. A paragraph ends at a sentence end that is followed by a vertical gap (a blank
    line or extra leading) or that stops short of the right margin. A line without a sentence end runs on, across a
    page break too. Article and heading lines are paragraphs of their own; a TITRE's caption is its next line."""
    paras: list[dict] = []
    prev = None
    blank = False
    for ln in lines:
        if ln['blank']:
            blank = True
            continue
        t = ln['text']
        # an article heading is bold, except "Article 160.5 :", which stands alone on its line
        is_art = bool(ART_RX.match(t)) and (ln['bold'] or bool(re.fullmatch(r'Article\s+[\d.]+\s*:?', t)))
        is_head = bool(HEAD_RX.match(t)) or t == 'PREAMBULE'
        new = True
        if prev is not None and not (is_art or is_head):
            p = paras[-1]
            gap = blank or (ln['page'] == prev['page'] and ln['y'] - prev['y'] > LINE_GAP)
            prev_short = prev['x1'] < RIGHT - 25
            ends = p['text'].endswith(TERMINAL)
            if p['kind'] == 'art':
                new = True
            elif p['kind'] == 'head':
                new = p['text'] == 'PREAMBULE' or not (ln['bold'] and not re.search(r'[a-zà-ÿ]', t))
            elif t.startswith(('-', '•')):
                new = True
            elif not ends:
                new = False
            else:
                new = gap or prev_short or ln['page'] != prev['page']
        if new:
            paras.append({'kind': 'art' if is_art else 'head' if is_head else 'text', 'text': t, 'page': ln['page']})
        else:
            paras[-1]['text'] = join(paras[-1]['text'], t)
            if paras[-1]['kind'] == 'head':
                paras[-1]['closed'] = True
        prev = ln
        blank = False
    for p in paras:
        p['text'] = norm(p['text'])
    return paras


# ------------------------------------------------------------------ paragraphs -> units

def art_key(m: re.Match) -> tuple[str, str]:
    n, sub, er, bis = m.group(1), m.group(2), m.group(3), m.group(4)
    if n == 'premier':
        return 'art-001', 'Article premier'
    key = f'art-{int(n):03d}'
    label = f'Article {int(n)}' + ('er' if er else '')
    if sub:
        key += f'-{int(sub)}'
        label += f'.{int(sub)}'
    if bis:
        key += f'-{bis}'
        label += f' {bis}'
    return key, label


def constitution() -> tuple[dict, list[str]]:
    pdf = cached(C2015)
    paras = paragraphs(visual_lines(pdf))
    start = next(i for i, p in enumerate(paras) if p['text'].upper() == 'PREAMBULE')
    units: dict[str, dict] = {'preambule': {'label': 'Préambule', 'kind': 'preamble', 'lines': ['# Préambule']}}
    cur = 'preambule'
    structure: list[str] = []
    pending: list[str] = []
    problems: list[str] = []
    for p in paras[start + 1:]:
        t = p['text']
        if p['kind'] == 'head':
            m = re.match(r'^(TITRE [IVXLC]+(?: bis| ter| quater)?)\s*:?\s*(.*)$', t)
            t = f'{m.group(1)} | {m.group(2)}' if m else t
            pending.append(re.sub(r'\s*\|\s*$', '', t))
            continue
        if p['kind'] == 'art':
            m = ART_RX.match(t)
            key, label = art_key(m)
            if key in units:
                problems.append(f'duplicate {key}')
            if pending:
                structure.append(' | '.join(pending) + f' | {label}')
                pending = []
            units[key] = {'label': label, 'kind': 'art', 'lines': [f'# {label}']}
            if m.group(5).strip():
                units[key]['lines'].append(m.group(5).strip())
            cur = key
            continue
        if pending:
            problems.append(f'text after a heading with no article: {t[:60]}')
        # art. 101: the consolidation sets the start of the second paragraph on the last line of the first list
        # ("… leurs indemnités ; La loi détermine"); it is split there (layout only, the words are unchanged)
        units[cur]['lines'].extend(re.split(r'(?<=indemnités ;) (?=La loi détermine les principes)', t))
    out = {k: {'label': v['label'], 'kind': v['kind'], 'text': '\n'.join(v['lines']) + '\n'} for k, v in units.items()}
    out['structure'] = {'label': 'Structure (titres et chapitres)', 'kind': 'structure',
                        'text': '# Structure\n' + '\n'.join(structure) + '\n'}
    return out, problems


# ------------------------------------------------------------------ corpus

COUNTRY = {
    'code': 'BF', 'name': 'Burkina Faso', 'slug': 'burkina-faso', 'lang': 'fr', 'tz': 'Africa/Ouagadougou',
    'future_branch': 'futur',
    'publisher': {'name': 'Secrétariat général du Gouvernement et du Conseil des ministres (LegiBurkina)',
                  'email': 'legiburkina@sggcm.invalid'},
    'default_in_force_rule': {
        'text': 'Not applied as a general rule. The one version is dated by the promulgation decree of the last '
                'revision it contains, Décret n°2015-1396/PRES-TRANS du 26 novembre 2015, as listed on the '
                'consolidation itself; the date of its Journal officiel publication was not found.',
        'source': C2015},
    'licence_note': 'Text: Constitution du Burkina Faso (2 June 1991), as revised up to Loi constitutionnelle '
                    'n°072-2015/CNT du 05 novembre 2015, consolidated by the Assemblée nationale and published on '
                    'LegiBurkina (Secrétariat général du Gouvernement et du Conseil des ministres, SGG-CM/DSI), '
                    'https://www.legiburkina.gov.bf. Official text of Burkina Faso.',
}

REVISIONS = [  # (key, label, title, enacted, promulgated) as printed on the consolidation's cover page
    ('constitution-1991', 'Constitution du 2 juin 1991', 'Constitution du Burkina Faso, adoptée par le référendum '
     'du 2 juin 1991 (Kiti n°AN-VIII-330/FP/PRES du 11 juin 1991)', '1991-06-02', '1991-06-11'),
    ('loi-002-97-adp', 'Loi n°002/97/ADP', 'Loi constitutionnelle n°002/97/ADP du 27 janvier 1997 (Décret '
     'n°97-063/PRES du 14 février 1997)', '1997-01-27', '1997-02-14'),
    ('loi-003-2000-an', 'Loi n°003-2000/AN', 'Loi constitutionnelle n°003-2000/AN du 11 avril 2000 (Décret '
     'n°2000-151/PRES du 25 avril 2000)', '2000-04-11', '2000-04-25'),
    ('loi-001-2002-an', 'Loi n°001-2002/AN', 'Loi constitutionnelle n°001-2002/AN du 22 janvier 2002 (Décret '
     'n°2002-038/PRES du 05 février 2002)', '2002-01-22', '2002-02-05'),
    ('loi-015-2009-an', 'Loi n°015-2009/AN', 'Loi constitutionnelle n°015-2009/AN du 30 avril 2009 (Décret '
     'n°2009-438/PRES du 30 juin 2009)', '2009-04-30', '2009-06-30'),
    ('loi-023-2012-an', 'Loi n°023-2012/AN', 'Loi constitutionnelle n°023-2012/AN du 18 mai 2012 (Décret '
     'n°2012-428/PRES du 23 mai 2012)', '2012-05-18', '2012-05-23'),
    ('loi-033-2012-an', 'Loi n°033-2012/AN', 'Loi constitutionnelle n°033-2012/AN du 11 juin 2012 (Décret '
     'n°2012-616/PRES du 20 juillet 2012)', '2012-06-11', '2012-07-20'),
    ('loi-035-2013-an', 'Loi n°035-2013/AN', 'Loi constitutionnelle n°035-2013/AN du 12 novembre 2013 (Décret '
     'n°2013-1176/PRES du 19 décembre 2013)', '2013-11-12', '2013-12-19'),
    ('loi-072-2015-cnt', 'Loi n°072-2015/CNT', 'Loi constitutionnelle n°072-2015/CNT du 05 novembre 2015 (Décret '
     'n°2015-1396/PRES-TRANS du 26 novembre 2015)', '2015-11-05', '2015-11-26'),
]


def main() -> None:
    pdf = cached(C2015)
    units, problems = constitution()
    if problems:
        raise SystemExit('parse problems:\n' + '\n'.join(problems))
    laws = {k: {'label': lab, 'title': title, 'kind': 'referendum' if k == 'constitution-1991' else 'law',
                'enacted': en, 'published': None, 'url': C2015, 'temporary_until': None, 'restores': None,
                'note': None}
            for k, lab, title, en, _ in REVISIONS}
    reqs = sum(1 for line in (CACHE / 'requests.jsonl').read_text(encoding='utf-8').splitlines()
               if '"url": "https://www.legiburkina.gov.bf' in line)
    corpus = {
        'country': COUNTRY,
        'sources': [{
            'name': 'LegiBurkina (Secrétariat général du Gouvernement et du Conseil des ministres, SGG-CM/DSI)',
            'url': C2015_PAGE, 'retrieved': RETRIEVED, 'requests': reqs,
            'licence': 'Official text. The portal states "SGGCM/DSI @2025 - Tous droits réservés" for the site and '
                       'no licence for the legal texts.',
            'notes': 'Textes fondamentaux: "Constitution du 02 juin 1991, révisée en 2015", file '
                     '"CONSTITUTION_1991_Constitution du Burkina Faso_Révisée de 2015_.pdf" (59 pages, Word 2010, '
                     'PDF title "Constitution consolidée après la relecture du 05 nov 2015-VF"): the Assemblée '
                     'nationale\'s consolidation, read from its text layer.'}],
        'laws': laws,
        'acts': [{
            'slug': 'constitution',
            'short': 'Constitution',
            'title': 'Constitution du Burkina Faso',
            'url': C2015_PAGE,
            'first_law': None,
            'earlier_laws': [k for k, *_ in REVISIONS],
            'versions': [{
                'from': '2015-11-26',
                'source_url': C2015,
                'sha256': sha(pdf),
                'units': dict(sorted(units.items())),
                'credits': {},
                'note': 'The Assemblée nationale\'s consolidation after Loi constitutionnelle n°072-2015/CNT du 05 '
                        'novembre 2015, promulgated by Décret n°2015-1396/PRES-TRANS du 26 novembre 2015. Its '
                        'footnotes, which say which revision changed each provision and how, are left out of the '
                        'text. Later revisions are not applied (see the README).',
            }],
        }],
        'applies': [],
        'decisions': [
            'Only the Constitution is built, on the preview branch: its current text cannot be shown. Loi '
            'constitutionnelle n°045-2023/ALT (Assemblée législative de transition, text layer) has no sourced '
            'promulgation date (the Assemblée\'s list says 01/01/1900); n°033-2024/ALT (promulgated 21/11/2024 per '
            'the Assemblée\'s list) and n°004-2026/ALT du 20 janvier 2026 are published only as scans, and scans '
            'are not transcribed (no OCR).',
            'One version, from 2015-11-26: the promulgation of the last revision the consolidation contains '
            '(Décret n°2015-1396/PRES-TRANS), as listed on its cover. It is credited to the publisher as the oldest '
            'version available, naming the 1991 Constitution and the eight revision laws the cover lists.',
            'Footnotes (9.8 pt) and footnote markers (6-9 pt superscripts) are left out; the cover page (revision '
            'and decree lists) is not law text and is left out.',
            'Paragraphs are rebuilt from the justified layout: a sentence end followed by a vertical gap, or by a '
            'line short of the right margin, ends a paragraph; a line without a sentence end runs on, also across '
            'a page break. In art. 101 the consolidation prints the start of the second paragraph ("La loi '
            'détermine les principes fondamentaux :") on the last line of the first list; it is split into its '
            'own paragraph (layout only, the words are unchanged). List dashes set in a smaller size at the body '
            'indent are kept.',
            'Unit layout: one file per article (art-NNN; art-NNN-N for the dotted articles such as 13.1 and '
            '160.1), the preamble, and one structure file naming the article each title and chapter heading '
            'precedes.',
            'Typesetting is normalised once: NBSP to space, curly apostrophes to straight ones, curly double '
            'quotes to « », em dashes to en dashes, runs of spaces collapsed.',
        ],
        'ai_use': ['Claude Code (Claude Opus 5.5, claude-opus-5-5) wrote fetch.py and parse.py, chose the sources '
                   'and wrote the decisions. No model wrote, summarised or transformed legal text: parse.py is '
                   'deterministic code over the cached PDF.'],
    }
    tmp = HERE / 'corpus.json.tmp'
    tmp.write_text(json.dumps(corpus, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    os.replace(tmp, HERE / 'corpus.json')
    print('constitution units:', len(units))


if __name__ == '__main__':
    main()
