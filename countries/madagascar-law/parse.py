"""Madagascar: reads only the CNLEGIS cache (.cache/, see fetch.py) and writes corpus.json (gitlaw_common SCHEMA.md).

    python -X utf8 parse.py

Acts:
  - constitution: the Constitution, 1998 to today. LC 98-001 (record 34738) annexes the whole 1992 Constitution as
    revised in 1995 and 1998 (the oldest version available); LC 2007-001 (39326) annexes the whole revised, renumbered
    text; LC 2009-001 (40058) replaces article 15 (replayed on the 2007 text); the Constitution of 11 December 2010
    (51445) replaces the whole text.
  - loi-2014-006: Loi n° 2014-006 sur la lutte contre la cybercriminalité (43046), as enacted; Loi n° 2016-031 (44983)
    replaces article 20 (replayed).
  - loi-2014-038: Loi n° 2014-038 sur la protection des données à caractère personnel (43521), as enacted (CNLEGIS lists
    no amendment).
Deterministic: the same cache gives the same bytes. No network, no model.
"""
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cnparse as P  # noqa: E402
import fetch as F  # noqa: E402

RETRIEVED = '2026-10-28'
# CNLEGIS searches are POSTs (fetch.py); the URL names the search form, the query and the record id.
REC_URL = 'https://cnlegis.gov.mg/{form}?txt_recherche={query}#id={rid}'
S_CONST = ('mots', 'Constitution de la', '0,300')
S_2009 = ('num', '2009-001', '0,50')
S_2014_006 = ('num', '2014-006', '0,50')
S_2016_031 = ('num', '2016-031', '0,50')
S_2014_038 = ('num', '2014-038', '0,50')
ORD_62_041 = 'https://cnlegis.gov.mg/uploads/O62-041-VF.pdf'

QUOTES = str.maketrans({'’': "'", '‘': "'", '“': '"', '”': '"'})


def norm(s: str) -> str:
    return re.sub(r' {2,}', ' ', s.translate(QUOTES)).strip()


def ymd(d: str) -> str:
    dd, mm, yy = d.split('-')
    return f'{yy}-{mm}-{dd}'


def plus(day: str, n: int) -> str:
    return (dt.date.fromisoformat(day) + dt.timedelta(days=n)).isoformat()


def record(search: tuple, rid: str, want: tuple) -> dict:
    rows = [r for r in F.search(*search, offline=True) if str(r['id']) == rid]
    if len(rows) != 1:
        raise SystemExit(f'record {rid}: {len(rows)} rows')
    r = rows[0]
    got = (re.sub(r'<[^>]+>', '', r['type_txt']).strip(), r['num_txt'], ymd(r['date_txt']), r['num_jo'],
           ymd(r['date_jo']))
    if got != want:
        raise SystemExit(f'record {rid}: CNLEGIS metadata {got} != expected {want}')
    r['_lines'] = [norm(l) for l in P.lines(r['html_fichier_fr'])]
    r['_url'] = REC_URL.format(form=F.KINDS[search[0]][0], query=quote(search[1]), rid=rid)
    r['_sha'] = F.sha256_of(*search)
    return r


def need(lines: list, text: str):
    if not any(text in l for l in lines):
        raise SystemExit(f'expected wording not found: {text[:80]}')


# ---- units -----------------------------------------------------------------------------------------------------------
def art_key(k: str) -> str:
    n, _, sub = k.partition('.')
    return f'art-{int(n):03d}' + (f'-{int(sub)}' if sub else '')


def units_of(parsed: dict, preamble: bool) -> dict:
    u = {}
    if preamble and parsed['preamble']:
        u['preambule'] = {'label': 'Préambule', 'kind': 'preamble', 'text': '\n'.join(parsed['preamble']) + '\n'}
    for key, printed, body in parsed['articles']:
        u[art_key(key)] = {'label': f'Art. {printed}', 'kind': 'art',
                           'text': f'# Article {printed}\n' + ''.join(l + '\n' for l in body)}
    if parsed['structure']:
        u['structure'] = {'label': 'Structure (titres et chapitres)', 'kind': 'structure',
                          'text': ''.join(f'{h} [article {k}]\n' for h, k in parsed['structure'])}
    return u


def diff_keys(prev: dict, cur: dict) -> list:
    return sorted(k for k in set(prev) | set(cur) if (prev.get(k) or {}).get('text') != (cur.get(k) or {}).get('text'))


def version(day, rec, units, credits=None, note=None):
    v = {'from': day, 'source_url': rec['_url'], 'sha256': rec['_sha'], 'units': units}
    if credits is not None:
        v['credits'] = credits
    if note:
        v['note'] = note
    return v


def replace_article(prev_units: dict, key: str, label: str, body: list) -> dict:
    if key not in prev_units:
        raise SystemExit(f'{key} not in the previous version')
    cur = json.loads(json.dumps(prev_units))
    cur[key] = {'label': label, 'kind': 'art', 'text': f'# {label.replace("Art.", "Article")}\n' +
                ''.join(l + '\n' for l in body)}
    return cur


# ---- the Constitution ------------------------------------------------------------------------------------------------
def constitution(laws: dict, decisions: list) -> dict:
    r98 = record(S_CONST, '34738', ('Loi constitutionnelle', '98-001', '1998-04-08', '2495', '1998-04-08'))
    r07 = record(S_CONST, '39326', ('Loi constitutionnelle', '2007-001', '2007-04-27', '3104', '2007-05-03'))
    r09 = record(S_2009, '40058', ('Loi', '2009-001', '2009-01-19', '3236', '2009-02-19'))
    r10 = record(S_CONST, '51445', ('Constitution', '2010', '2010-12-11', '3350', '2011-01-20'))
    need(r98['_lines'], 'La Constitution du 18 septembre 1992, révisée par la loi constitutionnelle du 13 octobre 1995')
    need(r07['_lines'], "la présente Loi constitutionnelle entre immédiatement en vigueur dès qu'elle aura reçu une "
                        'publication par émission radiodiffusée et télévisée ou affichage')
    need(r09['_lines'], "la présente Loi constitutionnelle entre immédiatement en vigueur dès qu'elle aura reçu une "
                        'publication par émission radiodiffusée et télévisée ou affichage')
    need(r10['_lines'], 'Elle entrera en vigueur dès sa promulgation')

    laws['constitution-1992'] = {'label': 'Constitution du 18 septembre 1992', 'title': 'Constitution de la Troisième '
                                 'République (named by LC 98-001 art. 1; its text is not on CNLEGIS in usable form)',
                                 'kind': 'law', 'enacted': '1992-09-18', 'published': None, 'url': None,
                                 'temporary_until': None, 'restores': None, 'note': None}
    laws['lc-95-001'] = {'label': 'Loi constitutionnelle n° 95-001', 'title': 'Loi constitutionnelle n° 95-001 du 13 '
                         'octobre 1995 (revising arts. 74, 75, 90, 91 and 94; named by LC 98-001 art. 1 and LC 2007-001 '
                         'art. 1; its text is not on CNLEGIS in usable form)', 'kind': 'law', 'enacted': '1995-10-13',
                         'published': None, 'url': None, 'temporary_until': None, 'restores': None, 'note': None}
    for key, rec, label, title in [
        ('lc-98-001', r98, 'Loi constitutionnelle n° 98-001', 'Loi constitutionnelle n° 98-001 du 8 avril 1998 portant '
         'révision de la Constitution'),
        ('lc-2007-001', r07, 'Loi constitutionnelle n° 2007-001', 'Loi constitutionnelle n° 2007-001 du 27 avril 2007 '
         'portant révision de la Constitution'),
        ('lc-2009-001', r09, 'Loi constitutionnelle n° 2009-001', "Loi constitutionnelle n° 2009-001 du 19 janvier 2009 "
         "modifiant les dispositions de l'article 15 de la Constitution"),
        ('constitution-2010', r10, 'Constitution du 11 décembre 2010', 'Constitution de la République de Madagascar du '
         '11 décembre 2010 (Quatrième République)')]:
        laws[key] = {'label': label, 'title': title, 'kind': 'law', 'enacted': ymd(rec['date_txt']),
                     'published': ymd(rec['date_jo']), 'url': rec['_url'], 'temporary_until': None, 'restores': None,
                     'note': None}

    p98 = P.constitution(r98['_lines'], r'PREAMBULE', r'Vu pour être annexé à la loi constitutionnelle n°98-001')
    p07 = P.constitution(r07['_lines'], r'PREAMBULE', r'Vu pour être annexé à la Loi constitutionnelle n°2007-001')
    p10 = P.constitution(r10['_lines'], r'PRÉAMBULE', r'Promulguée à Antananarivo, le 11 décembre 2010')
    u98, u07, u10 = units_of(p98, True), units_of(p07, True), units_of(p10, True)

    # LC 2009-001: the one quoted paragraph replaces article 15 (stops unless the act reads exactly so)
    head = [l for l in r09['_lines'] if l.startswith('Article premier')]
    if head != ["Article premier. Les dispositions de l'article 15 de la Constitution sont modifiées comme suit :"]:
        raise SystemExit(f'LC 2009-001: enacting clause not as read: {head}')
    new = [l for l in r09['_lines'] if l.startswith('Article 15 (nouveau)')]
    body = P.ART.match(new[0]).group(3) if len(new) == 1 else ''
    if not (body.startswith('"') and body.endswith('."')):
        raise SystemExit('LC 2009-001: article 15 is not one quoted paragraph')
    u09 = replace_article(u07, 'art-015', 'Art. 15', [body[1:-1]])
    if diff_keys(u07, u09) != ['art-015']:
        raise SystemExit('LC 2009-001 replay changed more than article 15')

    vs = [
        version('1998-04-10', r98, u98, note=(
            'Oldest version available: the Constitution of 18 September 1992 as revised by LC 95-001 and LC 98-001, '
            'as annexed in full to LC 98-001 (art. 2). Lines are not attributed to 1992, 1995 or 1998.')),
        version('2007-04-27', r07, u07, {k: ['lc-2007-001'] for k in diff_keys(u98, u07)}, note=(
            'LC 2007-001 annexes the whole revised text with new article numbers: from article 57 on, a file holds a '
            'different article before and after this version.')),
        version('2009-01-19', r09, u09, {'art-015': ['lc-2009-001']}, note=(
            'Replayed: the 2007 text with article 15 replaced by the paragraph LC 2009-001 art. 1 quotes.')),
        version('2010-12-11', r10, u10, {k: ['constitution-2010'] for k in diff_keys(u09, u10)}, note=(
            'A new constitution: every file before and after this version holds an article of a different constitution.')),
    ]
    decisions.extend([
        'Constitution: the first version (1998-04-10) is the whole text annexed to LC 98-001, credited to the publisher '
        'as the oldest version available (first_law null), naming the 1992 Constitution, LC 95-001 and LC 98-001: '
        'CNLEGIS has no usable text of the 1992 original (a scanned PDF, not read: no OCR) or of LC 95-001.',
        'Constitution: LC 98-001 has no in-force clause, so the default rule applies (Ordonnance n° 62-041 art. 3: one '
        'clear day after the Journal officiel reaches the sous-préfecture). JO n° 2495 is dated 1998-04-08, so '
        '1998-04-10 is the earliest day (later where the issue arrived later).',
        'Constitution: LC 2007-001 art. 3 and LC 2009-001 art. 2 bring them into force "immédiatement" on radio and '
        'television broadcast or posting (Ordonnance n° 62-041 art. 4), independently of the Journal officiel. The '
        'broadcast day is not printed, so the promulgation day (2007-04-27, 2009-01-19), the earliest possible, is used.',
        'Constitution: the 2010 Constitution art. 164: "Elle entrera en vigueur dès sa promulgation"; promulgated '
        '2010-12-11 (CNLEGIS record 51445).',
        'Constitution: LC 2009-001 is replayed on the 2007 text (article 15 replaced by the quoted paragraph); the parse '
        'stops unless the enacting clause and the quoted paragraph read exactly as expected and only article 15 changes.',
        'Constitution: one folder for every version (as in the earlier CNLEGIS build of this repository), so a file '
        'name holds the article of that number in the text in force; the 2007 renumbering and the 2010 replacement '
        'are labelled in the version notes. Every unit that differs in 2007 and 2010 is credited to that act, which '
        'enacted the whole text.',
        'Constitution: CNLEGIS lists no constitutional act after the 2010 Constitution and shows it "En vigueur" '
        '(searched 2026-10-28). Acts that changed how the Constitution worked without changing its words (Ordonnance '
        'n° 2009-001, the 2009 Charte de la Transition, the events of October 2025) are not shown.',
    ])
    return {'slug': 'constitution', 'short': 'Constitution', 'title': 'Constitution de la République de Madagascar',
            'url': r10['_url'], 'first_law': None, 'earlier_laws': ['constitution-1992', 'lc-95-001', 'lc-98-001'],
            'versions': vs}


# ---- statutes --------------------------------------------------------------------------------------------------------
def statute(rec: dict) -> dict:
    parsed = P.constitution(rec['_lines'], r'PROMULGUE LA LOI DONT LA TENEUR SUIT ?:?',
                            r'^(Promulguée à Antananarivo|Antananarivo, le)')
    if parsed['preamble'][1:]:
        raise SystemExit(f'record {rec["id"]}: text before the first article: {parsed["preamble"][1:3]}')
    parsed['preamble'] = []
    return units_of(parsed, False)


def default_in_force(rec: dict) -> str:
    """Ordonnance n° 62-041 art. 3: one clear day after the JO arrives; the earliest day is the JO date + 2."""
    need(rec['_lines'], 'sera publiée au Journal')
    if any('urgence' in l and 'vigueur' in l and 'présente loi' in l.lower() for l in rec['_lines']):
        raise SystemExit(f'record {rec["id"]}: an urgency clause; read it by hand')
    return plus(ymd(rec['date_jo']), 2)


def law_entry(rec: dict, label: str, title: str) -> dict:
    return {'label': label, 'title': title, 'kind': 'law', 'enacted': ymd(rec['date_txt']),
            'published': ymd(rec['date_jo']), 'url': rec['_url'], 'temporary_until': None, 'restores': None,
            'note': None}


def cyber(laws: dict, decisions: list) -> dict:
    r14 = record(S_2014_006, '43046', ('Loi', '2014-006', '2014-07-17', '3574', '2014-09-08'))
    r16 = record(S_2016_031, '44983', ('Loi', '2016-031', '2016-08-23', '3746', '2017-04-17'))
    laws['loi-2014-006'] = law_entry(r14, 'Loi n° 2014-006', 'Loi n° 2014-006 du 17 juillet 2014 sur la lutte contre '
                                     'la cybercriminalité')
    laws['loi-2016-031'] = law_entry(r16, 'Loi n° 2016-031', 'Loi n° 2016-031 du 23 août 2016 modifiant et complétant '
                                     'certaines dispositions de la loi n° 2014-006 sur la lutte contre la cybercriminalité')
    u14 = statute(r14)
    # Loi 2016-031 art. 1: "« Article 20 (nouveau). ..." up to the closing "»"
    ls = r16['_lines']
    i = [k for k, l in enumerate(ls) if l.startswith('« Article 20 (nouveau).')]
    if len(i) != 1 or not ls[i[0] - 1].startswith('Article premier. La présente loi a pour objet de modifier et de '
                                                  "compléter les dispositions de l'article 20 de la Loi n° 2014-006"):
        raise SystemExit('Loi 2016-031: article 1 not as read')
    j = next(k for k in range(i[0], len(ls)) if ls[k].endswith('»'))
    if not ls[j + 1].startswith('Article 2.'):
        raise SystemExit('Loi 2016-031: more than article 20 replaced?')
    body = ls[i[0]:j + 1]
    body[0] = body[0][len('« Article 20 (nouveau).'):].strip()
    body[-1] = body[-1][:-1].rstrip()
    u16 = replace_article(u14, 'art-020', 'Art. 20', body)
    if diff_keys(u14, u16) != ['art-020']:
        raise SystemExit('Loi 2016-031 replay changed more than article 20')
    d14, d16 = default_in_force(r14), default_in_force(r16)
    decisions.extend([
        f'Loi n° 2014-006: no in-force clause; Ordonnance n° 62-041 art. 3 (one clear day after the JO arrives). JO n° '
        f'3574 is dated {ymd(r14["date_jo"])}, so {d14} is the earliest day.',
        f'Loi n° 2016-031: no in-force clause; JO n° 3746 is dated {ymd(r16["date_jo"])}, so {d16} is the earliest day '
        '(Ordonnance n° 62-041 art. 3).',
        'Loi n° 2014-006: today\'s text is replayed: the 2014 text with article 20 replaced by the four paragraphs Loi '
        'n° 2016-031 art. 1 quotes ("Article 20 (nouveau)"). CNLEGIS notes for Loi 2014-006 name only Loi 2016-031 as '
        'amending it, and publishes no consolidated text; the parse stops unless only article 20 changes.',
        'Loi n° 2014-006: HCC décision n° 12-HCC/D3 du 16 juillet 2014 reviewed the law before promulgation; the '
        'promulgated text already reflects it, so it is not a change to the text.',
    ])
    return {'slug': 'loi-2014-006', 'short': 'Loi 2014-006', 'title': laws['loi-2014-006']['title'],
            'url': r14['_url'], 'first_law': 'loi-2014-006', 'earlier_laws': [],
            'versions': [version(d14, r14, u14),
                         version(d16, r16, u16, {'art-020': ['loi-2016-031']}, note=(
                             'Replayed: the 2014 text with article 20 replaced by the text Loi n° 2016-031 art. 1 '
                             'quotes.'))]}


def data_protection(laws: dict, decisions: list) -> dict:
    r = record(S_2014_038, '43521', ('Loi', '2014-038', '2015-01-09', '3630', '2015-07-20'))
    laws['loi-2014-038'] = law_entry(r, 'Loi n° 2014-038', 'Loi n° 2014-038 du 9 janvier 2015 sur la protection des '
                                     'données à caractère personnel')
    d = default_in_force(r)
    decisions.extend([
        f'Loi n° 2014-038: no in-force clause; JO n° 3630 is dated {ymd(r["date_jo"])}, so {d} is the earliest day '
        '(Ordonnance n° 62-041 art. 3). CNLEGIS prints the promulgation as "Antananarivo, le 09 janvier 2015".',
        'Loi n° 2014-038: CNLEGIS shows it "En vigueur" and its notes name only the implementing Décret n° 2023-1541; '
        'searches for "2014-038" list no amending law (2026-10-28), so the act has one version, as enacted.',
    ])
    return {'slug': 'loi-2014-038', 'short': 'Loi 2014-038', 'title': laws['loi-2014-038']['title'],
            'url': r['_url'], 'first_law': 'loi-2014-038', 'earlier_laws': [], 'versions': [version(d, r, statute(r))]}


CT_2024_PDF = 'https://cnlegis.gov.mg/uploads/L2024-014-VF.pdf'
S_CT = ('mots', 'Code du travail', '0,100')
CT_START, CT_STOP = r'PROMULGUE LA LOI DONT LA TENEUR SUIT ?:?', r'^(Promulguée à Antananarivo|Antananarivo, le)'


def code_du_travail_2024_lines() -> list:
    """Loi 2024-014: CNLEGIS's HTML is a cover with a link to the official PDF (text layer), read with pdftotext."""
    return [norm(l) for l in P.pdf_lines(P.pdf_text(F.CACHE / hashlib.sha256(CT_2024_PDF.encode()).hexdigest()))]


def code_du_travail(laws: dict, decisions: list) -> dict:
    r04 = record(S_CT, '38022', ('Loi', '2003-044', '2004-07-28', '2956', '2005-02-21'))
    r24 = record(S_CT, '55500', ('Loi', '2024-014', '2024-08-14', '4237', '2024-11-04'))
    F.get(CT_2024_PDF, offline=True)
    if CT_2024_PDF not in r24['html_fichier_fr']:
        raise SystemExit('Loi 2024-014: the CNLEGIS record no longer links the PDF read here')
    r24['_lines'] = code_du_travail_2024_lines()
    r24['_url'] = CT_2024_PDF
    r24['_sha'] = hashlib.sha256(F.get(CT_2024_PDF, offline=True)).hexdigest()
    laws['loi-2003-044'] = law_entry(r04, 'Loi n° 2003-044', 'Loi n° 2003-044 du 28 juillet 2004 portant Code du travail')
    laws['loi-2024-014'] = law_entry(r24, 'Loi n° 2024-014', 'Loi n° 2024-014 du 14 août 2024 portant Code du travail')
    laws['loi-2024-014']['url'] = CT_2024_PDF
    u04 = statute(r04)
    p24 = P.constitution(r24['_lines'], CT_START, CT_STOP)
    if p24['preamble'][1:]:
        raise SystemExit(f'Loi 2024-014: text before article 1: {p24["preamble"][1:3]}')
    p24['preamble'] = []
    nums = [a[0] for a in p24['articles']]
    if nums != ['1'] + [str(n) for n in range(2, 396)]:
        raise SystemExit('Loi 2024-014: articles are not exactly 1 to 395')
    need(r24['_lines'], 'Sont et demeurent abrogées toutes dispositions antérieures contraires au présent Code, '
                        'notamment celles de la Loi n° 2003-044')
    u24 = units_of(p24, False)
    d04, d24 = default_in_force(r04), default_in_force(r24)
    decisions.extend([
        f'Code du travail: Loi n° 2003-044 (promulgated 2004-07-28, JO n° 2956 of {ymd(r04["date_jo"])}) has no in-force '
        f'clause, so {d04} is the earliest day (Ordonnance n° 62-041 art. 3). CNLEGIS notes name no amending law, only '
        'implementing texts.',
        f'Code du travail: Loi n° 2024-014 (promulgated 2024-08-14, JO n° 4237 of {ymd(r24["date_jo"])}) replaces it '
        f'(art. 394 repeals Loi 2003-044); no in-force clause, so {d24} is the earliest day. Its 395 articles share '
        'the folder with the 2003 code, so before and after this version a file holds an article of a different code; '
        'every unit that differs is credited to Loi 2024-014, which enacted the whole text.',
        'Code du travail 2024: CNLEGIS gives only a cover page in HTML and links the official PDF (L2024-014-VF.pdf, '
        'text layer, no OCR), read with pdftotext 4.00 (poppler): page numbers dropped; a paragraph cut by a page break '
        'is joined when the line before it does not end a sentence or the next starts in lower case; headings and '
        'articles that pdftotext runs into one line are split; the one article printed "Art. 40." is read as '
        '"Article 40". Paragraph breaks are as pdftotext gives them; the words are checked by verify.py.',
    ])
    return {'slug': 'code-du-travail', 'short': 'Code du travail', 'title': 'Code du travail',
            'url': CT_2024_PDF, 'first_law': 'loi-2003-044', 'earlier_laws': [],
            'versions': [version(d04, r04, u04),
                         version(d24, r24, u24, {k: ['loi-2024-014'] for k in diff_keys(u04, u24)}, note=(
                             'A new Code du travail (Loi n° 2024-014) replaces the 2004 code: every file before and '
                             'after this version holds an article of a different code.'))]}


def main():
    laws, decisions = {}, []
    acts = [constitution(laws, decisions), cyber(laws, decisions), data_protection(laws, decisions),
            code_du_travail(laws, decisions)]
    ord_sha = hashlib.sha256(F.get(ORD_62_041, offline=True)).hexdigest()
    decisions += [
        'Code pénal (Phase 1 spec) not built: CNLEGIS holds no text of the Code pénal itself, only amending laws, and '
        'those before 1998 have no text; no official consolidated Code pénal with a text layer was found. Loi n° '
        '2014-006 (cybercrime, a penal statute with an amendment CNLEGIS publishes) was taken instead.',
        'Text normalisation (parse.py): curly single and double quotes become straight ones; runs of spaces collapse; '
        'NBSP, soft hyphens and zero-width characters are removed (cnparse.lines). CNLEGIS typing errors are kept.',
        'All texts are the French HTML CNLEGIS serves (html_fichier_fr). The Malagasy text, also official, is not used.',
    ]
    corpus = {
        'country': {
            'code': 'MG', 'name': 'Madagascar', 'slug': 'madagascar', 'lang': 'fr', 'tz': 'Indian/Antananarivo',
            'future_branch': 'futur',
            'publisher': {'name': 'CNLEGIS (Secrétariat Général du Gouvernement, Primature)',
                          'email': 'cnlegis@cnlegis.invalid'},
            'default_in_force_rule': {
                'text': ("Ordonnance n° 62-041 du 19 septembre 1962 art. 3: \"Les lois ne deviennent obligatoires, qu'un "
                         "jour franc après l'arrivée du Journal officiel, constatée à la sous-préfecture par l'apposition "
                         "d'un timbre à date\" (art. 4: immediately on posting, in case of declared urgency). The "
                         'earliest day, the JO date + 2, is used.'),
                'source': ORD_62_041},
            'licence_note': ('Source: CNLEGIS (cnlegis.gov.mg), the official legal database of the Primature. CNLEGIS '
                             'publishes no terms of use; reuse terms are unclear and the repository is private.'),
        },
        'sources': [
            {'name': 'CNLEGIS (cnlegis.gov.mg)', 'url': 'https://cnlegis.gov.mg/', 'retrieved': RETRIEVED,
             'requests': F.requests_made(),
             'licence': 'No terms of use published. robots.txt (2026-10-28): GPTBot disallowed, all others allowed.',
             'notes': ('Official French HTML of each text inside the JSON of the search endpoints (two POSTs per '
                       'search: page_find_direct_mots/ or page_num_find_direct/, then the data endpoint). Searches: '
                       + '; '.join(f'{k} "{q}" ({l}) sha256 {F.sha256_of(k, q, l)}' for k, q, l in F.SEARCHES)
                       + f'. Ordonnance n° 62-041 PDF (text layer) sha256 {ord_sha}.')},
        ],
        'laws': dict(sorted(laws.items())),
        'acts': acts,
        'applies': [],
        'decisions': decisions,
        'ai_use': ['none at data-build time: no model read, wrote or summarised legal text. parse.py and fetch.py were '
                   'written by Claude Code (Claude Opus 5.5, claude-opus-5-5); the act choice and in-force readings were '
                   'made by that agent from the cached official texts and are listed in decisions.'],
    }
    out = HERE / 'corpus.json'
    tmp = out.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(corpus, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    tmp.replace(out)
    for a in acts:
        print(a['slug'], [(v['from'], len(v['units'])) for v in a['versions']])


if __name__ == '__main__':
    main()
