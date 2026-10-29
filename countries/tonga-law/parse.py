"""Tonga: cached AGO Revised Edition PDFs (+ post-2020 amending Acts) -> corpus.json (gitlaw_common SCHEMA.md).

Reads only .cache/ (through fetch.get, which never refetches a cached URL). Deterministic.

Method, per act:
1. Parse each official Revised Edition (1988, 2016, 2020) into provisions (layout.py).
2. The 1988 edition is the oldest text online: it is the first version (first_law null), dated 31 December 1988, the day
   it states it was revised to. Its inline notes name the Acts in each provision; where a note names an Act that came
   into force after that day (the edition printed some later Acts), that provision is held back until the Act's
   commencement (FORK/BRIEF rule "text that appears before its law").
3. Between two editions, a provision whose words changed is dated by the Acts its endnote names that commenced
   between the two editions (commencement dates from the edition's own "Amendments after 1988" table). One such Act:
   the new words on its commencement day, credited to it. Several: the first Act's day gets a placeholder (the source
   gives no intermediate text), the last Act's day gets the new words. None: the change is the publisher's,
   "unexplained", on the edition's day.
4. Amending Acts after the 2020 edition are replayed from their official PDFs (amendments.py), each operation quoting
   the Act's own words.
"""
import hashlib
import json
import os
import re
import sys

import fetch
import layout

HERE = os.path.dirname(os.path.abspath(__file__))
B = 'https://www.ago.gov.to/cms/images/LEGISLATION/PRINCIPAL/'
PLACEHOLDER = '[The source does not give the text in force on this date.]'
MONTHS = {m: i for i, m in enumerate(['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august',
                                      'september', 'october', 'november', 'december'], 1)}

ACTS = [
    {'slug': 'constitution', 'short': 'Constitution', 'title': 'Constitution of Tonga', 'unit': 'cl', 'word': 'Clause',
     'url': 'https://www.ago.gov.to/cms/legislation/current-revised-edition/by-title.html',
     'editions': [
         ('1988-12-31', B + '1988/1988-0002/ActofConstitutionofTonga_1.pdf', '1988 Revised Edition (Cap. 2)'),
         ('2016-12-31', B + '1988/1988-0002/ConstitutionofTonga.pdf_2.pdf', '2016 Revised Edition (Cap. 01.01)'),
         ('2020-12-04', B + '1988/1988-0002/ConstitutionofTonga.pdf_3.pdf', '2020 Revised Edition (Cap. 1.01)'),
     ]},
    {'slug': 'criminal-offences', 'short': 'Criminal Offences Act', 'title': 'Criminal Offences Act', 'unit': 'sec',
     'word': 'Section', 'url': 'https://www.ago.gov.to/cms/legislation/current-revised-edition/by-title.html',
     'editions': [
         ('1988-12-31', B + '1924/1924-0010/CriminalOffencesAct_1.pdf', '1988 Revised Edition (Cap. 18)'),
         ('2016-12-31', B + '1924/1924-0010/CriminalOffencesAct_2.pdf', '2016 Revised Edition (Cap. 10.09)'),
         ('2020-12-04', B + '1924/1924-0010/CriminalOffencesAct_3.pdf', '2020 Revised Edition (Cap. 4.04)'),
     ]},
]


def sha(b):
    return hashlib.sha256(b).hexdigest()


def key_of(prefix, num):
    if num == 'sch':
        return 'sch'
    m = re.fullmatch(r'(\d+)([A-Z]*)', num)
    return f'{prefix}-{int(m.group(1)):03d}{m.group(2).lower()}'


def words(t):
    return re.sub(r'[^a-z0-9]+', ' ', t.lower()).split()


def act_key(n, y):
    return f'act-{int(n)}-{y}'


def parse_date(s):
    m = re.match(r'(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+),?\s+(\d{4})', s.strip())
    if not m or m.group(2).lower() not in MONTHS:
        return None
    return f'{int(m.group(3)):04d}-{MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}'


def commencement_table(endnote1):
    """{act key: ISO date} from an edition's "Amendments after 1988" table (endnote 1)."""
    t = endnote1.split('Amendments after 1988', 1)
    if len(t) < 2:
        return {}
    out = {}
    for m in re.finditer(r'Act\s+(?:No\.\s*)?(\d+)\s+of\s+(\d{4}),?\s+(\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+,?\s+\d{4})', t[1].replace('\n', ' ')):
        d = parse_date(m.group(3))
        if d:
            out[act_key(m.group(1), m.group(2))] = d
    return out


def earlier_acts(endnote1):
    head = endnote1.split('Amendments after 1988', 1)[0].replace('\n', ' ')
    out = []
    for m in re.finditer(r'(?:(?:Acts?|Laws?|Nos?\.)\s*)?(\d+)\s+of\s+(\d{4})', head):
        k = act_key(m.group(1), m.group(2))
        if k not in out:
            out.append(k)
    return out


def named_acts(texts):
    out = []
    for t in texts:
        for m in re.finditer(r'(\d+)\s+of\s+((?:18|19|20)\d\d)', t.replace('I 9', '19')):
            k = act_key(m.group(1), m.group(2))
            if k not in out:
                out.append(k)
    return out


def unit_text(act, u):
    title = u['title']
    if u['num'] == 'sch':
        head = '# Schedule'
        body = [title] + u['paras'] if title != 'SCHEDULE' else u['paras']
    else:
        if re.match(r'^\(?\s*Repealed', title):
            head = f"# {act['word']} {u['num']}"
            body = [title.strip('() ').rstrip('.').strip()]
        else:
            head = f"# {act['word']} {u['num']}. {title}"
            body = u['paras']
    return '\n'.join([head] + body) + '\n'


def placeholder(act, num):
    return f"# {act['word']} {num}\n{PLACEHOLDER}\n"


def outline_text(outline):
    return '# Parts\n' + ''.join(f'{t} [before {b}]\n' for t, b in outline if b)


def build_act(act, laws, decisions):
    eds = []
    for date, url, label in act['editions']:
        raw = fetch.get(url)
        d = layout.read(raw, inline_notes=date.startswith('1988'))
        d.update(date=date, url=url, label=label, sha=sha(raw))
        eds.append(d)
    table = {}
    for e in eds[1:]:
        table.update(commencement_table(e['endnotes'].get(1, '')))
    earlier = earlier_acts(eds[-1]['endnotes'].get(1, ''))
    for k in earlier + list(table):
        n, y = k.split('-')[1:]
        laws.setdefault(k, {'label': f'Act {n} of {y}', 'title': f'Act No. {n} of {y}', 'kind': 'law',
                            'enacted': None, 'published': None, 'url': None, 'temporary_until': None,
                            'restores': None, 'note': None})
    events = []  # (date, key, text or None, [law keys], source edition index)

    # 1988 base, holding back provisions whose inline note names an Act in force only after 31 Dec 1988.
    e0 = eds[0]
    state = {}
    for u in e0['units']:
        k = key_of(act['unit'], u['num'])
        txt = unit_text(act, u)
        late = sorted({a for a in named_acts(u['inline'] + [u['title']]) if a in table and table[a] > e0['date']},
                      key=lambda a: (table[a], a))
        if not late:
            state[k] = txt
            continue
        whole_added = len(u['inline']) == 1 and re.match(r'^\(\s*(Added|Inserted)', u['inline'][0])
        if not whole_added:
            state[k] = placeholder(act, u['num'])
        for i, a in enumerate(late):
            last = i == len(late) - 1
            events.append((table[a], k, txt if last else placeholder(act, u['num']), [a], 0))
        decisions.append(f"{act['short']}, {act['word'].lower()} {u['num']}: the 1988 Revised Edition prints it as amended by "
                         f"{', '.join(laws[a]['label'] for a in late)} (in force {', '.join(table[a] for a in late)}), so "
                         f"before then it {'is absent (inserted by that Act)' if whole_added else 'reads as a placeholder'} "
                         f"and the printed words arrive on {table[late[-1]]}.")
    if e0['outline']:
        state['parts'] = outline_text(e0['outline'])
    versions = [{'from': e0['date'], 'source_url': e0['url'], 'sha256': e0['sha'], 'units': dict(state),
                 'credits': {}, 'note': f"{e0['label']}: the oldest text published by the Attorney General's Office, "
                                        f"revised to 31 December 1988."}]

    # later editions
    prev = {key_of(act['unit'], u['num']): u for u in e0['units']}
    prev_text = {key_of(act['unit'], u['num']): unit_text(act, u) for u in e0['units']}
    prev_text['parts'] = state.get('parts')
    prev_inline = {key_of(act['unit'], u['num']): named_acts(u['inline']) for u in e0['units']}
    for ei in range(1, len(eds)):
        e, p = eds[ei], eds[ei - 1]
        cur = {key_of(act['unit'], u['num']): u for u in e['units']}
        cur_text = {k: unit_text(act, u) for k, u in cur.items()}
        if e['outline']:
            cur_text['parts'] = outline_text(e['outline'])
        for k in sorted(set(prev_text) | set(cur_text)):
            a, b = prev_text.get(k), cur_text.get(k)
            if a is not None and b is not None and words(a) == words(b):
                cur_text[k] = a  # same words, only layout differs: keep the earlier text
                continue
            if a == b:
                continue
            acts = []
            if b is not None and k in cur:
                u = cur[k]
                notes = [e['endnotes'].get(int(n), '') for n in u['notes'] if n.isdigit()]
                acts = [x for x in named_acts(notes + [u['title']])
                        if x in table and p['date'] < table[x] <= e['date'] and x not in prev_inline.get(k, [])]
            acts = sorted(set(acts), key=lambda x: (table[x], x))
            if not acts:
                events.append((e['date'], k, b, [], ei))
                continue
            num = cur[k]['num']
            for i, x in enumerate(acts):
                last = i == len(acts) - 1
                events.append((table[x], k, b if last else placeholder(act, num), [x], ei))
            if len(acts) > 1:
                decisions.append(f"{act['short']}, {act['word'].lower()} {num}: changed by "
                                 f"{', '.join(laws[x]['label'] for x in acts)} between the {p['label']} and the "
                                 f"{e['label']}; the source gives no text between them, so it reads as a placeholder from "
                                 f"{table[acts[0]]} and the {e['label']} words arrive on {table[acts[-1]]}.")
        prev_text = cur_text
        prev_inline = {}
        # every edition also gets a version on its own day, so the edition's words are checked on that day
        events.append((e['date'], None, None, [], ei))

    # fold events into versions
    by_date = {}
    for ev in events:
        by_date.setdefault(ev[0], []).append(ev)
    last_state = dict(versions[0]['units'])
    for date in sorted(by_date):
        evs = by_date[date]
        changes, credits = {}, {}
        src = max(ev[4] for ev in evs)
        for d, k, txt, cr, ei in evs:
            if k is None:
                continue
            changes[k] = txt
            if cr:
                credits.setdefault(k, [])
                for c in cr:
                    if c not in credits[k]:
                        credits[k].append(c)
            elif k in credits and not cr:
                pass
        changes = {k: v for k, v in changes.items() if last_state.get(k) != v}
        credits = {k: v for k, v in credits.items() if k in changes}
        for k, v in changes.items():
            if v is None:
                last_state.pop(k, None)
            else:
                last_state[k] = v
        if not changes and not any(ev[1] is None for ev in evs):
            continue
        e = eds[src]
        if date == versions[-1]['from']:
            # same day as the previous version: merge
            versions[-1].setdefault('changes', {}).update(changes)
            versions[-1]['credits'].update(credits)
            continue
        v = {'from': date, 'source_url': e['url'], 'sha256': e['sha'], 'changes': changes, 'credits': credits}
        if any(ev[1] is None for ev in evs):
            v['note'] = f"{e['label']} (Attorney General's Office), dated by the AGO's legislation history table."
        else:
            v['note'] = (f"Words as printed in the {e['label']}; dated by the commencement of the Act(s) named in its notes "
                         f"(the edition's \"Amendments after 1988\" table).")
        versions.append(v)
    return {'slug': act['slug'], 'short': act['short'], 'title': act['title'], 'url': act['url'],
            'first_law': None, 'earlier_laws': [k for k in earlier if k in laws], 'versions': versions}, last_state


def unit_obj(k, t):
    if k == 'parts':
        return {'label': 'Parts', 'kind': 'outline', 'text': t}
    if k == 'sch':
        return {'label': 'Schedule', 'kind': 'schedule', 'text': t}
    p, n = k.split('-', 1)
    n = n.lstrip('0').upper() or '0'
    return {'label': ('Cl. ' if p == 'cl' else 's. ') + n, 'kind': 'clause' if p == 'cl' else 'sec', 'text': t}


def main():
    laws, decisions = {}, []
    acts = []
    for act in ACTS:
        a, final = build_act(act, laws, decisions)
        acts.append(a)
    try:
        import amendments
        amendments.apply(acts, laws, decisions)
    except ImportError:
        pass
    for a in acts:  # units as SCHEMA objects {label, kind, text}
        for v in a['versions']:
            for field in ('units', 'changes'):
                if field in v:
                    v[field] = {k: (None if t is None else unit_obj(k, t)) for k, t in v[field].items()}
    reqs = 0
    with open(os.path.join(fetch.CACHE, 'requests.jsonl'), encoding='utf-8') as f:
        reqs = sum(1 for _ in f)
    corpus = {
        'country': {
            'code': 'TO', 'name': 'Tonga', 'slug': 'tonga', 'lang': 'en', 'tz': 'Pacific/Tongatapu',
            'future_branch': 'future',
            'publisher': {'name': "Attorney General's Office of Tonga (Tongan Legislation)", 'email': 'ago@ago.gov.to.invalid'},
            'default_in_force_rule': {
                'text': "Interpretation Act (Cap. 1.02), s. 3(1): \"An Act to which His Majesty's Assent has been given shall "
                        "come into operation on the day of publication in the Gazette, unless the contrary intention appears\"; "
                        "proviso: Acts pursuant to clause 79 of the Constitution come into operation on the day signed by His Majesty.",
                'source': B + '1903/1903-0006/InterpretationAct_3.pdf'},
            'licence_note': "Laws of Tonga, Attorney General's Office, Kingdom of Tonga (ago.gov.to). The site states: "
                            "\"Legislation can be downloaded and printed for private use. Any commercial entity is required "
                            "to obtain permission to reuse the data.\"",
        },
        'sources': [
            {'name': "Tongan Legislation, Attorney General's Office (Current Revised Edition, legislation history tables)",
             'url': 'https://www.ago.gov.to/cms/legislation/current-revised-edition/by-title.html',
             'retrieved': '2026-10-28', 'requests': reqs,
             'licence': 'private use; commercial reuse needs permission (site meta "rights")',
             'notes': '1988, 2016 and 2020 Revised Editions as PDFs with a text layer; amending Acts since 2020 as PDFs'},
        ],
        'laws': dict(sorted(laws.items())),
        'acts': acts,
        'applies': [],
        'decisions': [
            "English text is built. The AGO also publishes each Revised Edition in Tongan; by the Interpretation Act "
            "(Cap. 1.02) s. 21 the Tongan version of a law takes precedence, so the English text is the official English "
            "version, not the controlling one.",
            "Each act starts at the 1988 Revised Edition, the oldest text the AGO publishes (first_law null): the 1875 "
            "Constitution as granted and the earlier Acts are not online in an official text. The 1988 edition is dated "
            "31 December 1988, the day it states it was revised to; the 2016 and 2020 editions take the 'Date Commenced' "
            "of the AGO legislation history table (31 December 2016; 4 December 2020).",
            "Provision wording is compared word for word between editions after normalising quotes, dashes and spaces; "
            "where only the layout differs, the earlier text is kept so no false change appears.",
            "History notes are not law text: the 1988 edition's inline italic notes (\"(Amended by Act 3 of 1976.)\") and "
            "the endnote markers of 2016/2020 are removed from the text and used only to date and credit changes.",
            "Part headings are kept in one 'parts' file per act; the long title, enacting words and the edition's "
            "revision statement are left out.",
            "The Constitution's 2016 Revised Edition is not listed in the AGO history table but is still published at "
            "ConstitutionofTonga.pdf_2.pdf (also captured by the Internet Archive on 2020-11-04); it is used as version 2.",
        ] + decisions,
        'ai_use': ["Claude Code with Claude Opus 5.5 (claude-opus-5-5) wrote fetch.py, sources.py, layout.py, parse.py "
                   "and amendments.py and chose the sources and editions; it did not write or alter any legal text. "
                   "parse.py is deterministic and runs no model; every line of law comes from an official PDF in the cache."],
    }
    out = os.path.join(HERE, 'corpus.json')
    with open(out + '.tmp', 'w', encoding='utf-8', newline='\n') as f:
        json.dump(corpus, f, ensure_ascii=False, indent=1, sort_keys=False)
        f.write('\n')
    os.replace(out + '.tmp', out)
    for a in acts:
        print(a['slug'], len(a['versions']), 'versions', [v['from'] for v in a['versions']])


if __name__ == '__main__':
    main()
