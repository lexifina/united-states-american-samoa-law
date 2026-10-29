"""Companies Act 71 of 2008: every version from 1 May 2011, built from the cache only.

Sources:
  enacted   the Act as published in Government Gazette 32121 of 9 April 2009 (gov.za, born-digital text layer)
  dates     the Department of Justice consolidation (justice.gov.za 2008-071.pdf): its commencement table and the
            "(wef <date>)" in each amendment note give the day each change took effect, and the notes name the
            amending Act, so they credit each change
  wordings  after each amendment: LawLibrary point-in-time expressions of the Act, read from pinned Internet Archive
            captures (complete captures exist for 2009-04-09, 2014-05-01, 2023-06-01 and 2024-12-27); lines with the
            same words as the gazette keep the gazette's typography
  check     today's text against the Department of Justice consolidation (verify)
"""
from __future__ import annotations

import collections
import hashlib
import re

import constitution as K
import fetch
import gazette
import htmlblocks

GAZ_URL = 'https://www.gov.za/sites/default/files/gcis_document/201409/321214210.pdf'
DOJ_URL = 'https://www.justice.gov.za/legislation/acts/2008-071.pdf'
LL = 'https://lawlibrary.org.za/akn/za/act/2008/71/eng@'
LL_CAPTURES = {'2009-04-09': '20240217005439', '2014-05-01': '20251126111808', '2023-06-01': '20260123233325',
               '2024-12-27': '20260312164844'}
PLACEHOLDER = K.PLACEHOLDER

# Department of Justice consolidation, "as amended by" table (with effect from)
AMENDING = {
    '3/2011': ('act-2011-3', 'Act 3 of 2011', 'Companies Amendment Act, 2011', '2011-04-20', '2011-04-26',
               'https://www.gov.za/documents/companies-amendment-act'),
    '19/2012': ('act-2012-19', 'Act 19 of 2012', 'Financial Markets Act, 2012', '2013-02-01', '2013-02-01', DOJ_URL),
    '22/2022': ('act-2022-22', 'Act 22 of 2022', 'General Laws (Anti-Money Laundering and Combating Terrorism Financing) '
                'Amendment Act, 2022', '2022-12-29', '2022-12-29', DOJ_URL),
    '23/2021': ('act-2021-23', 'Act 23 of 2021', 'Financial Sector Laws Amendment Act, 2021', None, None, DOJ_URL),
    '16/2024': ('act-2024-16', 'Act 16 of 2024', 'Companies Amendment Act, 2024', None, None, DOJ_URL),
    '17/2024': ('act-2024-17', 'Act 17 of 2024', 'Companies Second Amendment Act, 2024', None, None, DOJ_URL),
}
MONTHS = {m: i for i, m in enumerate(['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
                                      'September', 'October', 'November', 'December'], 1)}


def iso(d: str) -> str:
    m = re.match(r'(\d{1,2}) (\w+) (\d{4})', d)
    return f'{m.group(3)}-{MONTHS[m.group(2)]:02d}-{int(m.group(1)):02d}'


def skey(num: str) -> str:
    return K.skey(num)


# ------------------------------------------------------------------ the gazette (as enacted)

def gazette_units() -> tuple[dict[str, dict], bytes]:
    raw = fetch.fetch(GAZ_URL, offline=True)
    import fitz
    doc = fitz.open(stream=raw, filetype='pdf')
    first = next(i for i in range(len(doc)) if re.search(r'^1\. In this Act', doc[i].get_text(), re.M))
    ls = gazette.lines(raw, first, len(doc))
    units: dict[str, dict] = {}
    heading = None
    cur = None
    sched = None
    for text, l in gazette.paragraphs(ls):
        m = re.match(r'^SCHEDULE (\d+)\b', text)
        if l.bold and m:
            sched = m.group(1)
            cur = {'label': f'Schedule {sched}', 'num': f'Schedule {sched}', 'heading': f'Schedule {sched}',
                   'lines': [], 'notes': []}
            units['schedule-' + sched.zfill(2)] = cur
            continue
        if sched is not None:
            if cur is not None and not cur['lines'] and l.bold and cur['heading'] == f'Schedule {sched}':
                cur['heading'] = f'Schedule {sched}: {K.norm(text).capitalize()}'
                continue
            cur['lines'].append(K.norm(text))
            continue
        m = gazette.SECTION.match(text)
        if l.bold and m and l.x0 > 118:
            num = m.group(1)
            cur = {'label': f's. {num}', 'num': num, 'heading': heading or '', 'lines': [], 'notes': []}
            units[skey(num)] = cur
            rest = K.norm(text[m.end():])
            if rest:
                cur['lines'].append(rest)
            heading = None
            continue
        if l.bold and not text.startswith('‘‘'):
            if re.match(r'^(CHAPTER|Part [A-Z]\b|PART)', text):
                cur = None
                heading = None
                continue
            heading = K.norm(text)
            cur = None
            continue
        if cur is not None:
            cur['lines'].append(K.norm(text))
    return units, raw


# ------------------------------------------------------------------ LawLibrary expressions

def ll_units(day: str) -> dict[str, dict]:
    raw = fetch.fetch(f'https://web.archive.org/web/{LL_CAPTURES[day]}id_/{LL}{day}', offline=True)
    root = htmlblocks.parse(raw.decode('utf-8', 'replace'))
    out: dict[str, dict] = {}
    stack = [root]
    while stack:
        n = stack.pop()
        if isinstance(n, str):
            continue
        i = n.attrs.get('id', '')
        if n.tag == 'section' and 'att_' not in i and re.search(r'(^|__)sec_\d+[A-Z]*$', i):
            num = i.rsplit('sec_', 1)[1]
            lines: list[str] = []
            K._akn_lines(n, lines, [])
            if lines:
                m = re.match(r'^(\d+[A-Z]*)\.\s+(.*)$', lines[0])
                out[skey(num)] = {'label': f's. {num}', 'num': num, 'heading': m.group(2) if m else lines[0],
                                  'lines': lines[1:], 'notes': []}
            continue
        if n.tag == 'div' and re.fullmatch(r'att_\d+', i):
            lines = []
            K._akn_lines(n, lines, [])
            m = re.match(r'^Schedule (\d+)$', lines[0]) if lines else None
            if m:
                out['schedule-' + m.group(1).zfill(2)] = {'label': f'Schedule {m.group(1)}', 'num': f'Schedule {m.group(1)}',
                                                         'heading': f'Schedule {m.group(1)}: {lines[1]}' if len(lines) > 1 else '',
                                                         'lines': lines[2:], 'notes': []}
            continue
        stack.extend(reversed(n.children))
    return {k: K._fix_label_space(u) for k, u in out.items()}


# ------------------------------------------------------------------ the DoJ consolidation: notes and dates

def doj_text() -> str:
    import fitz
    doc = fitz.open(stream=fetch.fetch(DOJ_URL, offline=True), filetype='pdf')
    t = '\n'.join(p.get_text() for p in doc)
    t = re.sub(r'© \d{4} Juta and Company \(Pty\) Ltd\.\nDownloaded:[^\n]*\n', '\n', t)
    return t


def doj_sections() -> dict[str, dict]:
    """{unit key: {'words': [...], 'notes': [...], 'events': {(act, day)}}} from the DoJ text."""
    t = doj_text()
    body = t[t.index('CHAPTER 1\nINTERPRETATION, PURPOSE AND APPLICATION (ss'):]
    out: dict[str, dict] = {}
    cur = None
    last = 0
    for line in body.split('\n'):
        m = re.match(r'^(\d+[A-Z]*)  (\S.*)$', line)
        if m and int(re.match(r'\d+', m.group(1)).group()) in (last, last + 1, last + 2, last + 3):
            last = int(re.match(r'\d+', m.group(1)).group())
            cur = out.setdefault(skey(m.group(1)), {'lines': [m.group(2)], 'notes_raw': []})
            continue
        m = re.match(r'^Schedule (\d+)\s*$', line.strip())
        if m:
            cur = out.setdefault('schedule-' + m.group(1).zfill(2), {'lines': [], 'notes_raw': []})
            continue
        if cur is not None:
            cur['lines'].append(line)
    for k, u in out.items():
        txt = re.sub(r'\s+', ' ', '\n'.join(u['lines']))
        notes = re.findall(r'\[(?!NB)[^\[\]]*\]', txt)
        u['notes'] = [n for n in notes if re.search(r'(amended|substituted|inserted|added|deleted|repealed|renumbered)', n)]
        u['pending'] = re.findall(r'\[NB:[^\[\]]*\]', txt)
        evs = set()
        for n in u['notes']:
            for m in re.finditer(r'Act (\d+) of (\d{4})(?: \(wef ([^)]+)\))?', n):
                key = f'{m.group(1)}/{m.group(2)}'
                if key in AMENDING and m.group(3):
                    for d in re.findall(r'\d{1,2} (?:' + '|'.join(MONTHS) + r') \d{4}', m.group(3)):
                        evs.add((AMENDING[key][0], iso(d)))
        u['events'] = evs
        body_txt = re.sub(r'\[[^\[\]]*\]', ' ', txt)
        u['text'] = body_txt
    return out


# ------------------------------------------------------------------ history

def tkey(line: str) -> str:
    """Two lines are the same if they differ only in quotes, dashes, spaces and "Act No." house style."""
    s = line.replace('Act No. ', 'Act ')
    s = re.sub(r'[“”"‘’\']', '"', s)
    s = re.sub(r'[—–-]', '-', s)
    return re.sub(r'\s+', '', s).lower()


def ll_typography(s: str) -> str:
    s = re.sub(r'"([^"]+)"', r'“\1”', s)
    return s.replace("'", '’')


OCR_PAIRS = {('live', 'five'), ('line', 'fine'), ('held', 'field'), ('fillfil', 'fulfil'), ('notice', 'notices')}


def _near(a: tuple, b: tuple) -> bool:
    """LawLibrary's text of the Act was made by OCR from the gazette scan: the same line with one known misreading."""
    if len(a) != len(b):
        return ''.join(a) == ''.join(b)          # only spaces differ ("holdersof", "91within")
    diff = [(x, y) for x, y in zip(a, b) if x != y]
    return len(diff) == 1 and (diff[0] in OCR_PAIRS or diff[0][::-1] in OCR_PAIRS)


def history():
    gaz, raw = gazette_units()
    ll = {d: ll_units(d) for d in LL_CAPTURES}
    doj = doj_sections()
    final = doj_units()
    s1_events = s1_definition_events()
    keys = sorted(set(gaz) | set(final))
    hist: dict[str, list] = {}
    gaps: list[str] = []
    obs_days = sorted(d for d in LL_CAPTURES if '2011-05-01' < d < '2024-12-27')
    for k in keys:
        evs = sorted(doj.get(k, {}).get('events', set()), key=lambda x: x[1])
        dates = sorted({d for _, d in evs})
        base = gaz.get(k)
        fin = final.get(k)
        refs = {}
        for src in ([base] if base else []) + ([fin] if fin else []):
            for l in src['lines']:
                refs.setdefault(tkey(l), l)

        def tidy(u):
            if u is None:
                return None
            lines = []
            for l in u['lines']:
                if tkey(l) in refs:
                    lines.append(refs[tkey(l)])
                    continue
                w = K.wkey(l)
                near = next((r for r in refs.values() if _near(w, K.wkey(r))), None)
                lines.append(near or ll_typography(l))
            head = u['heading']
            for src in (base, fin):
                if src is not None and K.wkey(src['heading']) == K.wkey(head):
                    head = src['heading']
            return {**u, 'lines': lines, 'heading': head}

        fin_t = None
        if fin is not None:
            # today's words (DoJ), with the gazette's typography for lines whose words did not change
            gl = {tkey(l): l for l in (base['lines'] if base else [])}
            fin_t = {**fin, 'lines': [gl.get(tkey(l), l) for l in fin['lines']],
                     'heading': base['heading'] if base and K.wkey(base['heading']) == K.wkey(fin['heading']) else fin['heading']}
        h = []
        if base is not None:
            if not dates and fin_t is not None:
                b = fin_t if [w for l in base['lines'] for w in K.wkey(l)] == [w for l in fin['lines'] for w in K.wkey(l)] else base
            else:
                b = base
            if k == 'section-011':
                b = drop_lines(b, ['(ii) ', '(iii) '], within='(a) ')
            h.append(('2011-05-01', b, [], 'Government Gazette 32121 (as enacted)'))
        prev = h[-1][1] if h else None
        for i, d in enumerate(dates):
            group = sorted({a for a, dd in evs if dd == d})
            nxt = dates[i + 1] if i + 1 < len(dates) else None
            if nxt is None:
                cand, how = fin_t, 'Department of Justice consolidation (today)'
            elif k == 'section-011' and d == '2011-05-01' and nxt == '2014-05-01':
                cand = drop_lines(fin_t, ['(ii) ', '(iii) '], within='(a) ')
                how = 'Department of Justice consolidation without s. 11(1)(a)(ii) and (iii), which commence 1 May 2014'
            elif k == 'section-001':
                cand, missing = s1_state(d, fin_t, ll, tidy, s1_events)
                how = ('Department of Justice consolidation, each definition changed later set back to its LawLibrary '
                       'wording on this day' + (f'; not given: {", ".join(missing)}' if missing else ''))
                if missing:
                    gaps.append(f'section-001 from {d} to {nxt}: definitions {", ".join(missing)}')
            else:
                o = next((od for od in obs_days if d <= od < nxt), None)
                if o is not None and k in ll[o]:
                    cand, how = tidy(ll[o][k]), f'LawLibrary @{o} (Wayback {LL_CAPTURES[o]})'
                else:
                    o2 = next((od for od in obs_days if od >= nxt), None)
                    later = {a for a, dd in evs if nxt <= dd <= (o2 or '9999')}
                    notes = [n for n in doj[k]['notes'] if any(AMENDING[x][1].split()[1] + ' of ' + AMENDING[x][1].split()[3]
                                                               in n for x in AMENDING if AMENDING[x][0] in later)]
                    defs = [re.match(r"\[Definition of '([^']+)' substituted", n) for n in notes]
                    if o2 and k in ll[o2] and notes and all(defs) and all(
                            not re.search(rf"by s\. [^\]]*of Act (\d+) of (\d{{4}}) \(wef ([^)]+)\)", n) or True for n in notes):
                        terms = {m.group(1) for m in defs}
                        src = tidy(ll[o2][k])
                        lines = []
                        skip = False
                        for l in src['lines']:
                            mt = re.match(r'^[“"‘]+([^”"’]+)[”"’]+', l)
                            if mt:
                                skip = mt.group(1) in terms
                                if skip:
                                    lines.append(f'“{mt.group(1)}” {PLACEHOLDER}')
                                    continue
                            if skip and re.match(r'^\(', l):
                                continue
                            skip = False if mt else skip
                            lines.append(l)
                        cand = {**src, 'lines': lines}
                        how = (f'LawLibrary @{o2} with the definitions changed later ({", ".join(sorted(terms))}) '
                               'shown as not given')
                        gaps.append(f'{k} from {d} to {nxt}: definitions {", ".join(sorted(terms))}')
                    else:
                        tmpl = prev or fin_t
                        cand = {**tmpl, 'lines': [PLACEHOLDER]}
                        how = 'no text source'
                        gaps.append(f'{k} from {d} to {nxt}')
            h.append((d, cand, group, how))
            prev = cand
        if not dates and base is None and fin_t is not None:
            gaps.append(f'{k}: in today\'s text but not in the gazette, and no note names a law')
            h.append(('2011-05-01', fin_t, [], 'Department of Justice consolidation'))
        hist[k] = h
    return hist, gaps, raw, doj, gaz, final


def drop_lines(u: dict, prefixes: list[str], within: str) -> dict:
    """Leave out the sub-paragraphs `prefixes` of the first paragraph starting with `within` (not yet in force)."""
    out, inside, done = [], False, False
    for l in u['lines']:
        if l.startswith(within) and not done:
            inside, done = True, True
        elif re.match(r'^\((?!i\)|ii\)|iii\)|iv\)|v\))[a-z]{1,2}\) ', l) or re.match(r'^\(\d+\) ', l):
            inside = False
        if inside and any(l.startswith(p) for p in prefixes):
            continue
        out.append(l)
    return {**u, 'lines': out}


# ------------------------------------------------------------------ the DoJ consolidation as text (today's words)

DOJ_LABEL = re.compile(r'^\s+\((\d+[A-Z]*|[a-zA-Z]{1,4}|[ivxl]+)\)\s+')


def doj_units() -> dict[str, dict]:
    t = doj_text()
    t = re.sub(r'\n +\d+ +[^\n]*\n(?:[^\n]*\(Proc[^\n]*\)\n)?', '\n', t)       # Juta footnotes
    body = t[t.index('CHAPTER 1\nINTERPRETATION, PURPOSE AND APPLICATION (ss'):]
    units: dict[str, dict] = {}
    cur = None
    para: list[str] | None = None
    in_note = False
    last = 0
    pending_sched = None

    def close():
        nonlocal para
        if para and cur is not None:
            cur['lines'].append(K.norm(' '.join(p.strip() for p in para)))
        para = None

    for raw_line in body.split('\n'):
        line = raw_line.rstrip()
        s = line.strip()
        if not s or re.fullmatch(r'\d+', s):
            continue
        if in_note or s.startswith('['):
            close()
            in_note = not s.endswith(']') and not s.endswith('].')
            if cur is not None and s.startswith('['):
                cur['notes'].append(s)
            continue
        m = re.match(r'^(\d+[A-Z]*)  (\S.*)$', line)
        if m and int(re.match(r'\d+', m.group(1)).group()) in (last, last + 1, last + 2, last + 3) and pending_sched is None:
            close()
            last = int(re.match(r'\d+', m.group(1)).group())
            cur = {'label': f's. {m.group(1)}', 'num': m.group(1), 'heading': K.norm(m.group(2)), 'lines': [], 'notes': []}
            units[skey(m.group(1))] = cur
            continue
        m = re.match(r'^Schedule (\d+)$', s)
        if m:
            close()
            pending_sched = m.group(1)
            cur = {'label': f'Schedule {m.group(1)}', 'num': f'Schedule {m.group(1)}', 'heading': f'Schedule {m.group(1)}',
                   'lines': [], 'notes': []}
            units['schedule-' + m.group(1).zfill(2)] = cur
            continue
        if pending_sched is not None and cur is not None and cur['heading'] == f'Schedule {pending_sched}' and not cur['lines'] and para is None:
            cur['heading'] = f'Schedule {pending_sched}: {K.norm(s).capitalize()}'
            continue
        if re.match(r'^(CHAPTER \d+|Part [A-Z]+)\s*$', s) or re.search(r'\((?:ss|items?) [\d\w]+-[\d\w]+\)\s*$', s):
            close()
            continue
        if cur is None:
            continue
        prev_end = para[-1].rstrip() if para else ''
        new = (para is None or DOJ_LABEL.match(line)
               or (re.match(r'^\((\d+[A-Z]*|[a-z]{1,3})\)\s', s) and re.search(r'([.;:\-—]|\bor|\band)$', prev_end))
               or (s.startswith("'") and re.search(r'([.;:\-—]|\bor|\band)$', prev_end))
               or (re.match(r'^\d+[A-Z]*\s{2,}\S', line) and pending_sched is not None))
        if new:
            close()
            para = [s]
        else:
            para.append(s)
    close()
    for u in units.values():
        u['lines'] = [juta_typography(l) for l in u['lines']
                      if not re.search(r'\((?:ss?|items?) \d+[A-Z]*(?:-\d+[A-Z]*)?\)$', l)]   # Part titles
        u['heading'] = juta_typography(u['heading'])
    return units


def juta_typography(s: str) -> str:
    """The consolidation's house style, set to the gazette's: quotes, closing dashes, "section 118(3)"."""
    s = re.sub(r"(^|[\s(])'([A-Za-z0-9][^']{0,120}?)'(?=[\s,;:.)\-]|$)", r'\1“\2”', s)
    s = s.replace("'", '’')
    s = re.sub(r'\s*-$', '—', s)
    m = re.match(r'^(?:\(\w{1,4}\) )+', s)            # the labels that open the line keep their spaces
    head, rest = (s[:m.end()], s[m.end():]) if m else ('', s)
    for _ in range(3):
        rest = re.sub(r'(\b(?:section|sections|subsection|subsections|item|items|regulation|paragraph)\s+\d+[A-Z]*'
                      r'|\(\w{1,4}\))'
                      r' (?=\(\w{1,4}\))', r'\1', rest)
    return head + rest


# ------------------------------------------------------------------ s. 1, definition by definition

TERM = re.compile(r'^[“"‘]+([^”"’]+)[”"’]+')


def s1_definition_events() -> dict[str, list[tuple[str, str, str]]]:
    """{term: [(action, law key, day)]} from the DoJ notes, each note read under the definition it follows."""
    t = doj_text()
    i = t.index('\n1  Definitions\n')
    j = t.index('\n2  Related and inter-related persons', i)
    out: dict[str, list] = collections.defaultdict(list)
    cur = None
    buf = ''
    for line in t[i:j].split('\n'):
        s = line.strip()
        m = re.match(r"^'([^']+)'", s)
        if m and not buf:
            cur = m.group(1)
        if s.startswith('[') or buf:
            buf += ' ' + s
            if s.endswith(']') or s.endswith('].'):
                note = re.sub(r'\s+', ' ', buf).strip()
                buf = ''
                if note.startswith('[NB'):
                    continue
                mt = re.match(r"\[Definition of '([^']+)'", note)
                term = mt.group(1) if mt else cur
                action = 'amended'
                for m2 in re.finditer(r'(inserted|substituted|amended|deleted|added)|Act (\d+) of (\d{4}) \(wef ([^)]+)\)',
                                      note):
                    if m2.group(1):
                        action = m2.group(1)
                        continue
                    key = f'{m2.group(2)}/{m2.group(3)}'
                    if key in AMENDING:
                        for d in re.findall(r'\d{1,2} (?:' + '|'.join(MONTHS) + r') \d{4}', m2.group(4)):
                            out[term].append((action, AMENDING[key][0], iso(d)))
    return out


def definition_blocks(lines: list[str]) -> tuple[list[str], list[tuple[str, list[str]]]]:
    head, blocks = [], []
    for l in lines:
        m = TERM.match(l)
        if m:
            blocks.append((m.group(1).strip().lower(), [l]))
        elif blocks:
            blocks[-1][1].append(l)
        else:
            head.append(l)
    return head, blocks


def s1_state(day: str, fin_t: dict, ll: dict, tidy, events: dict) -> tuple[dict, list[str]]:
    """Section 1 as in force on `day`: today's definitions, with each definition changed after `day` set back to
    its wording in the LawLibrary expression in force on `day`, left out if inserted later, or shown as not given."""
    head, blocks = definition_blocks(fin_t['lines'])
    ev = {t.lower(): v for t, v in events.items()}
    obs = sorted(d for d in LL_CAPTURES if '2011-05-01' < d < '2024-12-27')
    lines, missing = list(head), []
    for term, blk in blocks:
        later = [e for e in ev.get(term, []) if e[2] > day]
        if not later:
            lines += blk
            continue
        if any(a in ('inserted', 'added') for a, _, d in later) and not any(d <= day for _, _, d in ev.get(term, [])
                                                                              if _ in ('inserted', 'added')):
            continue                                   # inserted after `day`
        first_later = min(d for _, _, d in later)
        o = next((od for od in obs if day <= od < first_later), None)
        got = None
        if o is not None and 'section-001' in ll[o]:
            _, lb = definition_blocks(tidy(ll[o]['section-001'])['lines'])
            got = next((b for t2, b in lb if t2 == term), None)
        if got is None:
            lines.append(f'“{blk[0][1:].split("”")[0]}” {PLACEHOLDER}')
            missing.append(term)
        else:
            lines += got
    return {**fin_t, 'lines': lines}, missing
