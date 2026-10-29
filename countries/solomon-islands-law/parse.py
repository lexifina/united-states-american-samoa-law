"""Parse cached PacLII captures into corpus.json (gitlaw-SB). Reads only .cache/; no network.

Phase 1 (partial): the Constitution of Solomon Islands as made, from the Schedule to the
Solomon Islands Independence Order 1978 (S.I. 1978/783), PacLII consol_act/c1978167 (archive.org capture 20230620190023).
"""
import hashlib
import html
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, '.cache')
CONST_TS = '20230620190023'
CONST_URL = 'http://www.paclii.org/sb/legis/consol_act/c1978167/'


def cpath(key):
    return os.path.join(CACHE, hashlib.sha256(key.encode('utf-8')).hexdigest())


def ia_key(ts, url):
    return f'https://web.archive.org/web/{ts}id_/{url}'


def norm(s):
    s = s.replace(' ', ' ').replace('’', "'").replace('‘', "'")
    s = s.replace('“', '"').replace('”', '"').replace('–', '-').replace('—', '-')
    return re.sub(r'[ \t]+', ' ', s).strip()


def lines_of(raw):
    s = raw.decode('utf-8', 'replace')
    s = re.sub(r'<script.*?</script>|<style.*?</style>', '', s, flags=re.S | re.I)
    s = s.replace('\r', ' ').replace('\n', ' ')
    s = re.sub(r"<span[^>]*font-weight: bold[^>]*>(.*?)</span>", lambda m: '\x01' + m.group(1) + '\x02', s, flags=re.S)
    s = re.sub(r'<b>(.*?)</b>', lambda m: '\x01' + m.group(1) + '\x02', s, flags=re.S)
    s = re.sub(r'<br\s*/?>|</?p[^>]*>|</?blockquote[^>]*>', '\n', s, flags=re.I)
    s = html.unescape(re.sub(r'<[^>]+>', '', s))
    out = []
    for l in s.split('\n'):
        l = norm(l)
        if l:
            out.append(l)
    return out


SEC = re.compile(r'^\x01?(\d+[A-Z]?)\x02?\s*\.\s*(?:-\s*)?\x02?\s*(.*)$')


def constitution_units(lines):
    # the Constitution is the Schedule: from the preamble ("We the people") to the end of Schedule 3
    start = next(i for i, l in enumerate(lines) if l.startswith('We the people of Solomon Islands'))
    end = next(i for i, l in enumerate(lines) if l.startswith('PacLII:'))
    body = lines[start:end]
    units, cur, key, label = {}, [], 'preamble', 'Preamble'

    def flush():
        txt = [re.sub('[\x01\x02]', '', x) for x in cur]
        txt = [x for x in txt if x and not re.fullmatch(r'_+', x)]
        if txt:
            units[key] = {'label': label, 'kind': 'sched' if key.startswith('sched') else ('preamble' if key == 'preamble' else 'sec'),
                          'text': f'# {label}\n' + '\n'.join(txt) + '\n'}

    pending_head = None
    i = 0
    while i < len(body):
        l = body[i]
        bold_only = l.startswith('\x01') and l.endswith('\x02') and '\x02' not in l[:-1].replace('\x02\x01', '')
        plain = re.sub('[\x01\x02]', '', l)
        m_sched = re.match(r'^SCHEDULE (\d) TO THE CONSTITUTION$', plain)
        if m_sched:
            flush()
            key, label, cur = f'sched-{m_sched.group(1)}', f'Schedule {m_sched.group(1)}', []
            pending_head = None
            i += 1
            continue
        if re.match(r'^(CHAPTER [IVXL]+|PART [IVXL]+)$', plain) or (bold_only and plain.isupper() and not key.startswith('sched')):
            i += 1
            continue
        m = SEC.match(l)
        if m and pending_head is not None and not key.startswith('sched'):
            flush()
            num = m.group(1)
            n = re.match(r'(\d+)([A-Z]?)', num)
            key = f's-{int(n.group(1)):03d}' + (f'-{n.group(2).lower()}' if n.group(2) else '')
            label = f's. {num} {pending_head}'
            cur = [norm(re.sub('[\x01\x02]', '', l))]
            pending_head = None
            i += 1
            continue
        if bold_only and not key.startswith('sched'):
            if pending_head is not None:
                cur.append(pending_head)
            pending_head = plain
            i += 1
            continue
        if pending_head is not None:
            cur.append(pending_head)
            pending_head = None
        cur.append(plain)
        i += 1
    flush()
    return units


def main():
    raw = open(cpath(ia_key(CONST_TS, CONST_URL)), 'rb').read()
    units = constitution_units(lines_of(raw))
    corpus = {
        'country': {
            'code': 'SB', 'name': 'Solomon Islands', 'slug': 'solomon-islands', 'lang': 'en',
            'tz': 'Pacific/Guadalcanal', 'future_branch': 'future',
            'publisher': {'name': 'Pacific Islands Legal Information Institute (PacLII)', 'email': 'publisher@paclii.org.invalid'},
            'default_in_force_rule': {
                'text': 'Solomon Islands Independence Order 1978 s. 1(2) and s. 2(1): the Constitution came into operation on the appointed day, 7 July 1978',
                'source': CONST_URL},
            'licence_note': 'Text from PacLII (Pacific Islands Legal Information Institute), read via Internet Archive captures; see PacLII copyright policy.',
        },
        'sources': [
            {'name': 'PacLII Solomon Islands Consolidated Legislation, via Internet Archive id_ captures',
             'url': 'http://www.paclii.org/sb/legis/consol_act/', 'retrieved': '2026-10-28', 'requests': None,
             'licence': 'PacLII copyright policy (free access to law); Internet Archive Wayback Machine',
             'notes': f'Constitution: {CONST_URL} capture {CONST_TS}. PacLII itself is behind a bot challenge and was not fetched directly.'},
        ],
        'laws': {
            'si-1978-783': {'label': 'S.I. 1978/783', 'title': 'The Solomon Islands Independence Order 1978', 'kind': 'law',
                            'enacted': '1978-05-31', 'published': '1978-05-31', 'url': CONST_URL,
                            'temporary_until': None, 'restores': None, 'note': None},
        },
        'acts': [{
            'slug': 'constitution', 'short': 'Constitution',
            'title': 'The Constitution of Solomon Islands',
            'url': CONST_URL, 'first_law': 'si-1978-783', 'earlier_laws': [],
            'versions': [{
                'from': '1978-07-07', 'source_url': ia_key(CONST_TS, CONST_URL),
                'sha256': hashlib.sha256(raw).hexdigest(), 'units': units, 'credits': {},
                'note': 'The Constitution as made (Schedule to S.I. 1978/783). Later amendments are not yet applied in this build.',
            }],
        }],
        'applies': [],
        'decisions': [
            'Phase 1 is partial: only the Constitution as made (7 July 1978, the appointed day under s. 2(1) of the Independence Order) is built; amendment Acts are not yet replayed.',
            'The sections of the Independence Order itself (ss. 1-14) are left out; only its Schedule (the Constitution) is built.',
            'Chapter and Part headings are dropped; each section file starts with its marginal heading.',
        ],
        'ai_use': ['Claude Code with Claude Opus 5.5 (claude-opus-5-5) wrote the fetch and parse scripts. No model wrote or altered legal text.'],
    }
    tmp = os.path.join(HERE, 'corpus.json.tmp')
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(corpus, f, ensure_ascii=False, indent=1, sort_keys=False)
        f.write('\n')
    os.replace(tmp, os.path.join(HERE, 'corpus.json'))
    print(len(units), 'units')


if __name__ == '__main__':
    main()
