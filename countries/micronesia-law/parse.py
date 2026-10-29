"""Federated States of Micronesia: cached sources -> corpus.json (gitlaw_common SCHEMA.md). gitlaw-FM.

Reads only .cache/ (through fetch.get / fetch.wb, which return cached bytes and never refetch). Deterministic.

Acts:
1. The Constitution, from the FSM Legal Information System pages (fsmlaw.org/fsm/constitution/, read through pinned
   Internet Archive captures). One version, the oldest available: the text as the LIS prints it with the four 1990
   Constitutional Convention amendments incorporated. The newest and the oldest capture of every page carry the
   same law text (checked here); the version is dated by the latest of the oldest captures.
2. Title 11 (Crimes) and 3. Title 7 (Citizenship) of the Code of the FSM 2014 Edition (Annotated), from the LIS
   title PDFs. The first version of each is the edition's text (first_law null), dated by the latest public law the
   edition's own "Source:" notes name in that title, whose approval date the FSM Congress index gives. Then every
   later public law that amends the title (found in the Congress index, 17th-24th Congress) is applied from the
   enrolled law on cfsm.gov.fm, on the day the Congress index gives for it, quoting the law's own words.
"""
import hashlib
import json
import os
import re

import fetch
import layout

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = json.load(open(os.path.join(HERE, 'sources.json'), encoding='utf-8'))
LIS = 'FSM Legal Information System (fsmlaw.org)'
UNOFFICIAL = ('unofficial consolidation published by the FSM Legal Information System under the FSM Supreme Court; '
              'not an official publication')

# Public laws applied after the 2014 edition. Each operation names the PL section and what it does:
#   ('chapter', pl_sec, chapter, None)            new chapter; its title is the quoted name in that PL section
#   ('subchapter', pl_sec, chapter, sub)          new subchapter, likewise
#   ('section', pl_sec, None, None)               a section enacted or rewritten "to read as follows", whole
#   ('body', pl_sec, code_sec, None)              the section's text rewritten without a catchline (keeps its heading)
AMEND = {
    11: [
        ('18-02', [('chapter', 1, 13, None)] + [('section', k, None, None) for k in range(2, 15)]),
        ('18-19', [('chapter', 1, 14, None)] + [('section', k, None, None) for k in range(2, 7)]),
        ('18-43', [('subchapter', 1, 6, 3)] + [('section', k, None, None) for k in range(2, 6)] + [('body', 6, 104, None)]),
        ('21-08', [('section', 2, None, None), ('section', 3, None, None)]),
        ('21-149', [('section', 1, None, None)]),
    ],
    7: [
        ('19-91', [('section', 2, None, None)]),
        ('23-140', [('section', k, None, None) for k in range(1, 5)]),
    ],
}
NO_CATCHLINE = {('19-91', 203)}        # PL 19-91 rewrites § 203 as "Section 203. A citizen ..." with no catchline
CUT = {('21-08', 2): '(1) Notwithstanding subsection (2)(c)'}   # printed after the closing quotation mark
TITLES = {
    11: {'slug': 'title-11-crimes', 'short': 'Title 11', 'title': 'Code of the Federated States of Micronesia, Title 11: Crimes'},
    7: {'slug': 'title-07-citizenship', 'short': 'Title 7', 'title': 'Code of the Federated States of Micronesia, Title 7: Citizenship'},
}
ROMAN = {1: 'I', 2: 'II', 3: 'III', 4: 'IV', 5: 'V'}


def sha(b):
    return hashlib.sha256(b).hexdigest()


def iso_mdy(s):
    m, d, y = s.split('.')
    return f'20{y}-{m}-{d}'


def congress_index():
    """{'18-43': {'date': 'YYYY-MM-DD', 'title': ..., 'pdf': ..., 'without_signature': bool}} from cfsm.gov.fm."""
    import html
    out = {}
    for p in SRC['index']:
        b = fetch.get(f'https://www.cfsm.gov.fm/{p}/').decode('utf-8', 'replace')
        for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', b, re.S):
            cells = [re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', c))).strip()
                     for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', tr, re.S)]
            if len(cells) < 3 or not re.fullmatch(r'\d{1,2}-\d{1,3}', cells[0]) or not re.fullmatch(r'\d\d\.\d\d\.\d\d', cells[1]):
                continue
            href = re.search(r'href="([^"]+\.pdf)"', tr, re.I)
            out.setdefault(cells[0], {'date': iso_mdy(cells[1]), 'title': cells[2], 'pdf': href.group(1) if href else None,
                                      'without_signature': 'without signature' in cells[2].lower()})
    return out


def pl_key(n):
    c, s = n.split('-')
    return f'pl-{int(c):02d}-{int(s):03d}'


def law_entry(n, idx, url=None):
    i = idx.get(n)
    title = i['title'] if i else f'Public Law No. {n}'
    title = re.sub(r'\s*\[[^\]]*\]\s*(Law without signature)?\s*$', '', title).strip()
    return {'label': f'PL {n}', 'title': title, 'kind': 'law', 'enacted': i['date'] if i else None,
            'published': None, 'url': url or (i['pdf'] if i else None), 'temporary_until': None, 'restores': None,
            'note': None}


# ---------------------------------------------------------------- Constitution

def constitution(decisions):
    units, raws, oldest = {}, [], []
    for page, c in SRC['constitution'].items():
        new_raw = fetch.wb(c['newest']['url'], c['newest']['ts'])
        old_raw = fetch.wb(c['oldest']['url'], c['oldest']['ts'])
        new = layout.constitution_units(page, layout.constitution_page(new_raw))
        old = layout.constitution_units(page, layout.constitution_page(old_raw))
        if [(u['key'], u['paras']) for u in new] != [(u['key'], u['paras']) for u in old]:
            raise SystemExit(f'Constitution {page}: law text differs between captures {c["oldest"]["ts"]} and {c["newest"]["ts"]}')
        raws.append(new_raw)
        oldest.append(c['oldest']['ts'])
        for u in new:
            paras = list(u['paras'])
            if u['kind'] == 'section':
                paras[0] = re.sub(r'^Section\s+\d+\s*\.\s*', '', paras[0])
                if not paras[0]:
                    paras = paras[1:]
            units[u['key']] = {'label': u['label'], 'kind': u['kind'],
                               'text': '\n'.join([f"# {u['heading']}"] + paras) + '\n'}
    frm = max(oldest)
    frm = f'{frm[:4]}-{frm[4:6]}-{frm[6:8]}'
    decisions.append(
        'Constitution: one version, the oldest available (first_law null), credited to the FSM Legal Information '
        f'System: {UNOFFICIAL}. It is the text the LIS prints with the four amendments of the 1990 Constitutional '
        'Convention (Proposals 90-13, 90-19, 90-23 and 90-25, ratified by the voters in 1991) incorporated, as the '
        "LIS index page says. The LIS gives no ratification date, so the version is dated "
        f"{frm}: by that day the Internet Archive had captured every page of it, and the newest captures "
        f"(2023-2024) carry the same words.")
    decisions.append(
        'Constitution: the amendments put to the July 2023 referendum (eight from the 4th Constitutional Convention and '
        'one from the 22nd Congress, among them dual citizenship in Article III) are NOT applied. The LIS pages captured '
        'up to 2024 do not incorporate them, the convention site (constitution.gov.fm) no longer serves its adopted '
        'proposals, and no official certified text with its ratification date was found. Public Law 23-140 (2024) '
        'refers to "the dual citizenship constitutional amendment", so Article III as built is out of date after 2023.')
    decisions.append('Constitution: case annotations and cross references (set in a smaller font by the LIS) are left '
                     'out; one file per section, plus one per article heading and the preamble.')
    return {'slug': 'constitution', 'short': 'Constitution', 'title': 'Constitution of the Federated States of Micronesia',
            'url': 'https://www.fsmlaw.org/fsm/constitution/index.htm', 'first_law': None, 'earlier_laws': [],
            'publisher': {'name': 'FSM Legal Information System (unofficial)', 'email': 'lis@fsmlaw.org.invalid'},
            'versions': [{'from': frm, 'source_url': 'https://www.fsmlaw.org/fsm/constitution/index.htm',
                          'sha256': sha(b''.join(raws)), 'units': units, 'credits': {},
                          'note': ('Oldest version available: the Constitution as printed by the FSM Legal Information '
                                   'System, with the 1990 Constitutional Convention amendments incorporated; ' + UNOFFICIAL +
                                   '. sha256 is of the 17 archived pages concatenated in order. The July 2023 '
                                   'referendum amendments are not applied.')}]}


# ---------------------------------------------------------------- Code titles

def code_unit_text(u):
    if u['kind'] == 'sec':
        return '\n'.join([f"# {u['heading']}"] + layout.reflow(u['lines'])) + '\n'
    return '\n'.join([f"# {u['heading']}", u['title']]) + '\n'


def unit_obj(key, text):
    if key.startswith('sec-'):
        n = key[4:].lstrip('0').upper()
        return {'label': f'§ {n}', 'kind': 'sec', 'text': text}
    if '-part-' in key:
        return {'label': 'Part ' + str(int(key.split('-part-')[1])), 'kind': 'part', 'text': text}
    if '-sub-' in key:
        c, s = key[3:].split('-sub-')
        return {'label': f'Chapter {int(c)}, Subchapter {ROMAN[int(s)]}', 'kind': 'subchapter', 'text': text}
    return {'label': f'Chapter {int(key[3:])}', 'kind': 'chapter', 'text': text}


def quoted(lines):
    """The lines of a PL section after its "to read as follows:" (or "entitled") -> joined text."""
    return ' '.join(lines)


def pl_section_text(n, k, lines):
    """Quoted code text of PL n, section k -> (code section number or None, heading or None, [paragraphs])."""
    j = next((i for i, t in enumerate(lines) if re.match(r'^["“”]\s*Section\s+\d+', t)), None)
    if j is None:
        j = next(i for i, t in enumerate(lines) if t.rstrip().endswith('follows:')) + 1
    block = lines[j:]
    block[0] = re.sub(r'^["“”]\s*', '', block[0])
    text = '\n'.join(block)
    if (n, k) in CUT:
        text = text.split(CUT[(n, k)])[0].rstrip()
    text = re.sub(r'["“”]\s*$', '', text.rstrip())
    rows = [(0, layout.norm(t)) for t in text.split('\n')]
    paras = layout.reflow(rows)
    m = re.match(r'^Section\s+(\d+)\.\s*(.*)$', paras[0])
    if not m:
        return None, None, paras
    num, rest = int(m.group(1)), m.group(2)
    if (n, num) in NO_CATCHLINE:
        return num, f'§ {num}.', [rest] + paras[1:]
    h = re.match(r'^(.+?\.)(?:\s+(.*))?$', rest)
    head, body0 = h.group(1), h.group(2)
    return num, f'§ {num}. {head}', ([body0] if body0 else []) + paras[1:]


def entitled(lines):
    m = re.search(r'entitled:?\s*["“”](.+?)["“”]', ' '.join(lines))
    return layout.norm(m.group(1)).rstrip('.')


def code_title(tn, idx, laws, decisions):
    spec = TITLES[tn]
    t = SRC['titles'][str(tn)]
    path = fetch.path_for(f"https://web.archive.org/web/{t['ts']}id_/{t['url']}")
    raw = fetch.wb(t['url'], t['ts'])
    named = [f'{c}-{s}' for c, s in layout.source_laws(path)]
    dated = [(idx[n]['date'], n) for n in named if n in idx]
    frm, last = max(dated)
    units = {}
    for u in layout.code_title(path, tn):
        units[u['key']] = unit_obj(u['key'], code_unit_text(u))
    for n in named:
        laws.setdefault(pl_key(n), law_entry(n, idx))
    versions = [{'from': frm, 'source_url': f"https://web.archive.org/web/{t['ts']}/{t['url']}", 'sha256': sha(raw),
                 'units': units, 'credits': {},
                 'note': (f"Oldest version available: Code of the FSM 2014 Edition (Annotated), title {tn}, as published "
                          f"by the FSM Legal Information System ({UNOFFICIAL}). Dated by PL {last}, the latest public law "
                          f"its notes name in this title.")}]
    decisions.append(
        f"{spec['short']}: the first version is the 2014 Edition text ({UNOFFICIAL}), first_law null. The edition states "
        f"no cut-off date, so it is dated {frm}, the day PL {last} became law (FSM Congress index), PL {last} being "
        f"the latest public law named in the edition's Source notes for this title; no public law amending the title "
        f"between that day and the next one applied here appears in the Congress index.")
    state = {k: v['text'] for k, v in units.items()}
    for n, ops in AMEND[tn]:
        i = idx[n]
        url = i['pdf']
        pdf = fetch.get(url)
        pl = layout.public_law(fetch.path_for(url))
        laws[pl_key(n)] = law_entry(n, idx, url)
        if i['without_signature']:
            laws[pl_key(n)]['note'] = None
        changes, credits = {}, {}
        for op, k, a, b in ops:
            lines = pl['sections'][k]
            if op == 'chapter':
                key, text = f'ch-{a:02d}', f'# Chapter {a}\n{entitled(lines)}\n'
            elif op == 'subchapter':
                key, text = f'ch-{a:02d}-sub-{b:02d}', f'# Subchapter {ROMAN[b]}\n{entitled(lines)}\n'
            else:
                num, head, paras = pl_section_text(n, k, lines)
                if op == 'body':
                    num = a
                    head = state[f'sec-{a:04d}'].split('\n', 1)[0][2:]
                key = f'sec-{num:04d}'
                text = '\n'.join([f'# {head}'] + paras) + '\n'
            if state.get(key) == text:
                continue
            changes[key] = unit_obj(key, text)
            credits[key] = [pl_key(n)]
            state[key] = text
        versions.append({'from': i['date'], 'source_url': url, 'sha256': sha(pdf), 'changes': changes,
                         'credits': credits,
                         'note': f'PL {n}, applied from the enrolled law published by the FSM Congress (cfsm.gov.fm); '
                                 f'in force on {i["date"]}, the date the Congress index gives for it.'})
    return {'slug': spec['slug'], 'short': spec['short'], 'title': spec['title'],
            'url': 'https://www.fsmlaw.org/fsm/code/indexcode2014.html', 'first_law': None,
            'earlier_laws': [pl_key(n) for n in named],
            'publisher': {'name': 'FSM Legal Information System (unofficial)', 'email': 'lis@fsmlaw.org.invalid'},
            'versions': versions}


def requests_count():
    with open(os.path.join(fetch.CACHE, 'requests.jsonl'), encoding='utf-8') as f:
        rows = [json.loads(x) for x in f if x.strip()]
    ia = sum(1 for r in rows if 'archive.org' in r['url'])
    return ia, len(rows) - ia


def main():
    idx = congress_index()
    laws, decisions = {}, []
    acts = [constitution(decisions), code_title(11, idx, laws, decisions), code_title(7, idx, laws, decisions)]
    ia, direct = requests_count()
    corpus = {
        'country': {
            'code': 'FM', 'name': 'Micronesia', 'slug': 'micronesia', 'lang': 'en', 'tz': 'Pacific/Pohnpei',
            'future_branch': 'future',
            'publisher': {'name': 'FSM Legal Information System (unofficial)', 'email': 'lis@fsmlaw.org.invalid'},
            'default_in_force_rule': {
                'text': 'Every public law applied here ends "This act shall become law upon approval by the President of '
                        'the Federated States of Micronesia or upon its becoming law without such approval" '
                        '(Constitution art. IX, sec. 22); it is dated by the day the FSM Congress public-law index gives '
                        'for it, which is the approval day printed on the law, or the day it became law without signature.',
                'source': 'https://www.cfsm.gov.fm/fsm-congress-public-laws/'},
            'licence_note': ('Constitution and Code of the FSM 2014 Edition (Annotated): FSM Legal Information System '
                             '(fsmlaw.org), a project coordinated by the FSM Supreme Court; its disclaimer says the copies '
                             '"are not to be construed as an official publication". Public laws: Congress of the Federated '
                             'States of Micronesia (cfsm.gov.fm). Read through Internet Archive captures (fsmlaw.org) and '
                             'directly (cfsm.gov.fm).'),
        },
        'sources': [
            {'name': 'FSM Legal Information System: Constitution pages and Code of the FSM 2014 Edition (Annotated) title PDFs',
             'url': 'https://www.fsmlaw.org/fsm/code/indexcode2014.html', 'retrieved': '2026-10-29',
             'requests': ia, 'licence': 'no licence stated; ' + UNOFFICIAL,
             'notes': ('Read only through Internet Archive id_ captures, pinned in sources.json (robots.txt sets '
                       'Crawl-delay: 30; fsmlaw.org itself was never requested). Requests counted are archive.org ones.')},
            {'name': 'Congress of the Federated States of Micronesia: public laws (17th-24th Congress indexes and enrolled PDFs)',
             'url': 'https://www.cfsm.gov.fm/fsm-congress-public-laws/', 'retrieved': '2026-10-29', 'requests': direct,
             'licence': 'official public laws of the FSM; no licence stated',
             'notes': 'Enrolled public laws with a text layer; the index gives each law\'s date and title.'},
        ],
        'laws': dict(sorted(laws.items())),
        'acts': acts,
        'applies': [],
        'decisions': [
            'The user decided (2026-10-29) to build from the FSM Legal Information System even though it is an '
            f'{UNOFFICIAL}. No official current consolidation of the FSM Code or Constitution is online: the Congress '
            'publishes public laws only, and fsmsupremecourt.org serves a bot challenge that was never touched.',
            'English is the language of the FSM Code and Constitution; the text is built in English.',
            'Code of the FSM 2014 Edition: the edition sets statutory text in 12 pt and every annotation (Source notes, '
            "editor's notes, cross references, case annotations) in 10 pt; only 12 pt text is kept (PyMuPDF). The "
            'Source notes are used only to date the first version and to list earlier laws.',
            'Unit files: one per section (sec-NNNN, the code section number), one per chapter, subchapter and part '
            'heading; text is one paragraph per line, with quotes, dashes and spaces normalised.',
            'Public laws are read with pdftotext 4.00 (poppler) -layout; printed line numbers, page headers and bill '
            'draft marks are removed, and the quoted text after "to read as follows:" becomes the section, whole. '
            'Their "Section N." headings are written in the Code\'s "§ N." form.',
            'PL 18-43 section 3 says it inserts "a new section 631" but quotes "Section 632. Definition."; it is applied '
            'as section 632, as quoted. Its section 6 rewrites section 104 without repeating the catchline, so the '
            'catchline "Definitions." is kept.',
            'PL 18-43 prints no approval date (it became law without the President\'s signature); its date, 7 March '
            '2014, is the FSM Congress index\'s.',
            'PL 21-08 section 2 quotes a new section 1141 that ends at the closing quotation mark after subsection (2)(d); '
            'a further paragraph "(1) Notwithstanding subsection (2)(c) ..." printed after the closing quotation mark is '
            'not applied, and the duplicated sentence and stray quotation mark inside the quoted text are kept as printed.',
            'PL 19-91 rewrites section 203 of title 7 as "Section 203. A citizen ..." with no catchline, so the file '
            'heading reads "§ 203." with no catchline until PL 23-140 gives it one.',
            'Unnumbered paragraphs inside a public law\'s quoted section are joined into one line: the enrolled PDFs do '
            'not mark paragraph breaks other than by enumerators.',
        ] + decisions,
        'ai_use': ['Claude Code with Claude Opus 5.5 (claude-opus-5-5) wrote discover.py, fetch.py, layout.py and parse.py '
                   'and chose the sources and acts; it did not write or alter any legal text. parse.py is deterministic '
                   'and runs no model; every line of law comes from a cached source file.'],
    }
    out = os.path.join(HERE, 'corpus.json')
    with open(out + '.tmp', 'w', encoding='utf-8', newline='\n') as f:
        json.dump(corpus, f, ensure_ascii=False, indent=1)
        f.write('\n')
    os.replace(out + '.tmp', out)
    for a in acts:
        print(a['slug'], len(a['versions']), 'versions', [v['from'] for v in a['versions']],
              len(a['versions'][0]['units']), 'units')


if __name__ == '__main__':
    main()
