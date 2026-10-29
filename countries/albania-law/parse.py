"""Builds Albania's Constitution history from the cache into scripts/albania-law/corpus.d/10-kushtetuta.json.

    python -X utf8 scripts/albania-law/parse.py           # writes the part and prints the verification report

Reads only .cache/ (fill it with fetch.py). No network.

Sources (all official, all with a text layer; no OCR):
- The 1998 text as enacted: the Assembly's (Kuvendi i Shqipërisë) own PDF "Kushtetuta e RSH.pdf" (a Word export,
  1 Jan 2006), read from an Internet Archive capture of 25 May 2006, before the first amendment of 13 Jan 2007.
- The seven amending laws: the .docx of each, from qbz.gov.al (Qendra e Botimeve Zyrtare, the official publisher).
- QBZ's consolidated editions of the Constitution: 2008, 2012, 2015 and 2016 (Internet Archive captures of
  qbz.gov.al) and today's edition (qbz.gov.al/api/v1/publications?type=kushtetuta).

Method. Each amending law is replayed on the text before it, instruction by instruction ("Neni 64 ndryshohet si
më poshtë", "Pas nenit 6 shtohet neni 6/1", "Pika 1 e nenit 109 ...", ...). The words of each version then come
from the official consolidated edition for that state wherever one exists, and from the replay otherwise:
- a provision that no later law changes reads as in today's QBZ edition;
- otherwise as in the QBZ edition of that state (2008, 2012, 2015, 2016), if there is one;
- otherwise as replayed (the 1998 text for provisions later amended, and the states after laws 9675/2007 and
  115/2020, which no edition shows).
Every replayed provision is compared with the edition of its state, and every difference is reported (verify()).
Credits come from the laws' own instructions and are cross-checked against QBZ's notes in today's edition
("(Ndryshuar me ligjin nr. 9904, datë 21.4.2008)").
"""
from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fetch    # noqa: E402  (cache paths and URLs only; parse never fetches)
import qbzpdf   # noqa: E402

CACHE = HERE / '.cache'
OUT = HERE / 'corpus.d' / '10-kushtetuta.json'
RETRIEVED = '2026-10-29'

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

# Internet Archive captures (timestamp, original URL); read through gitlaw_common/wayback.py's cache key.
ARCHIVE = {
    'k1998': ('20060525195849', 'http://parlamenti.albaniaonline.net:80/menu/foto/Kushtetuta%20e%20RSH.pdf'),
    'q2008': ('20160828082331', 'http://qbz.gov.al/Kushtetuta-2008.pdf'),
    'q2012': ('20150514023034', 'http://qbz.gov.al:80/Kushtetuta%202012.pdf'),
    'q2015': ('20160828081555', 'http://qbz.gov.al/Kushtetuta%202015.pdf'),
    'q2016': ('20161231232216', 'http://qbz.gov.al/kushtetuta%20me%20pjese/Kushtetuta%202016.pdf'),
}


def wb_url(name: str) -> str:
    ts, url = ARCHIVE[name]
    return f'https://web.archive.org/web/{ts}id_/{url}'


def cached(url: str) -> bytes:
    p = CACHE / hashlib.sha256(url.encode('utf-8')).hexdigest()
    if not p.exists():
        raise SystemExit(f'not cached (run fetch.py): {url}')
    return p.read_bytes()


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ------------------------------------------------------------------ the laws

# key, qbz act id, in-force rule: '+15' = the law's own "hyn në fuqi 15 ditë pas botimit"; 'now' = "hyn në fuqi
# menjëherë" (in force on publication in the Fletorja Zyrtare).
LAWS = [
    ('ligji-9675-2007', 5051, 'now'),
    ('ligji-9904-2008', 6511, '+15'),
    ('ligji-88-2012', 8604, '+15'),
    ('ligji-137-2015', 12702, 'now'),
    ('ligji-76-2016', 15530, '+15'),
    ('ligji-115-2020', 22000, '+15'),
    ('ligji-16-2022', 24124, '+15'),
]
BASE_LAW = 'ligji-8417-1998'
# The QBZ edition showing the state right after each law (None: no edition of that state survives).
EDITION_AFTER = {
    'ligji-9675-2007': None, 'ligji-9904-2008': 'q2008', 'ligji-88-2012': 'q2012', 'ligji-137-2015': 'q2015',
    'ligji-76-2016': 'q2016', 'ligji-115-2020': None, 'ligji-16-2022': 'q2026',
}


def docx_paras(b: bytes) -> list[str]:
    z = zipfile.ZipFile(io.BytesIO(b))
    x = ET.fromstring(z.read('word/document.xml'))
    out = []
    for p in x.iter(W + 'p'):
        t = ''.join((n.text or '') if n.tag == W + 't' else (' ' if n.tag == W + 'tab' else '') for n in p.iter())
        out.append(qbzpdf.norm(t))
    return out


def dmy(s: str) -> str:
    d, m, y = (int(x) for x in re.split(r'[.\s]+', s.strip().rstrip('.'))[:3])
    return f'{y:04d}-{m:02d}-{d:02d}'


MUAJT = ['janar', 'shkurt', 'mars', 'prill', 'maj', 'qershor', 'korrik', 'gusht', 'shtator', 'tetor', 'nëntor', 'dhjetor']


def masthead_date(pdf: bytes) -> str:
    """The issue date printed on the first page of a Fletorja Zyrtare issue ("27 korrik 2016")."""
    import fitz
    t = fitz.open(stream=pdf, filetype='pdf')[0].get_text()
    m = re.search(r'(\d{1,2})\s+(' + '|'.join(MUAJT) + r')\s+(20\d\d)', t, re.I)
    return f'{int(m.group(3)):04d}-{MUAJT.index(m.group(2).lower()) + 1:02d}-{int(m.group(1)):02d}'


def load_laws() -> dict:
    laws = {}
    for key, act_id, rule in LAWS:
        a = fetch.act(act_id, offline=True)
        paras = docx_paras(fetch.act_docx(act_id, offline=True))
        text = '\n'.join(paras)
        m = re.search(r'Miratuar në datën\s+(\d{1,2}\.\s*\d{1,2}\.\s*\d{4})', text) \
            or re.search(r'Nr\.\s*\d+[^\n]*?datë\s+(\d{1,2}\.\d{1,2}\.\d{4})', text)
        enacted = dmy(m.group(1))
        g = fetch.gazette(a['gazette']['year'], a['gazette']['number'], offline=True)
        published = g['publishDate']
        assert masthead_date(fetch.fetch(fetch.SITE + g['pdf']['url'], offline=True)) == published, key
        clause = re.search(r'Ky ligj hyn në fuqi ([^.\n]*)', text).group(1)
        if rule == '+15':
            assert '15 ditë pas botimit' in clause, (key, clause)
            in_force = (dt.date.fromisoformat(published) + dt.timedelta(days=15)).isoformat()
        else:
            assert clause.startswith('menjëherë'), (key, clause)
            in_force = published
        num = a['number'].split('-')[0]
        title = qbzpdf.norm(re.sub(r'\s+', ' ', a['title'])).rstrip('.')
        if title.isupper():
            title = title[:1] + title[1:].lower()
        title = re.sub(r'[“”]kushtetuta e republikës së shqipërisë[“”]', '“Kushtetuta e Republikës së Shqipërisë”',
                       title, flags=re.I)
        title = re.sub(r'nr\.(?=\d)', 'nr. ', title)
        laws[key] = {
            'label': f'Ligji nr. {num}/{enacted[:4]}' if int(enacted[:4]) >= 2009 else f'Ligji nr. {num}',
            'title': title,
            'kind': 'law', 'enacted': enacted, 'published': published,
            'url': f'https://qbz.gov.al{a["eliPath"]}' if a.get('eliPath') else None,
            'temporary_until': None, 'restores': None, 'note': None,
            '_in_force': in_force, '_paras': paras, '_docx_url': fetch.SITE + a['word']['url'],
            '_docx_sha': sha(fetch.act_docx(act_id, offline=True)), '_gazette': f'{a["gazette"]["number"]}/{a["gazette"]["year"]}',
            '_clause': f'Ky ligj hyn në fuqi {clause}.',
        }
    return laws


# ------------------------------------------------------------------ replaying an amending law

RE_LAW_ART = re.compile(r'^Neni \d+$')
QUOTE_LOG: set[str] = set()


def law_articles(paras: list[str]) -> list[list[str]]:
    """The operative articles of an amending law, each as its lines (heading dropped), up to the in-force article."""
    arts, cur = [], None
    for p in paras:
        if RE_LAW_ART.match(p):
            cur = []
            arts.append(cur)
            continue
        if cur is not None and p:
            cur.append(p)
    return arts


def quotes(lines: list[str]) -> list[list[str]]:
    """The quoted blocks “…”. in an article of an amending law, each as its lines without the quote marks."""
    out, cur, depth = [], None, 0
    for l in lines:
        if cur is None and out and re.match(r'^\d+(/\d+)?\.\s', l) and re.search(r'”\s*\.\s*$', l):
            # 76/2016 art. 20 (art. 141) closes its quote after paragraph 1 by mistake; paragraph 2 follows it
            # outside the quote, itself ending in ”. — it belongs to the same quote.
            QUOTE_LOG.add(f'A stray closing quote ends the quoted text early before “{l[:40]}…”; that paragraph was kept '
                          f'in the quoted provision.')
            out[-1].append(re.sub(r'”\s*\.\s*$', '', l).strip())
            continue
        if cur is None and l.startswith('“'):
            cur, depth = [], 1
            l = l[1:]
        if cur is None:
            continue
        # the quote closes at the ” that balances its opening “ (quoted terms inside it nest)
        end = None
        for i, ch in enumerate(l):
            depth += (ch == '“') - (ch == '”')
            if depth == 0:
                end = i
                break
        if end is not None:
            assert re.match(r'^\s*[.;]?\s*$', l[end + 1:]), l
            cur.append(l[:end].strip())
            out.append([x for x in cur if x])
            cur = None
        else:
            cur.append(l.strip())
    if cur is not None:   # 137/2015 never closes the quote of its art. 179/1: it runs to the end of the article
        out.append([x for x in cur if x])
    return out


def art_key(ref: str) -> str:
    """'64' -> neni-064, '6/1' -> neni-006-01, '147/ç' -> neni-147-c-ced."""
    m = re.match(r'^(\d+)\s*(?:/\s*(\S+))?$', ref.strip())
    return qbzpdf.neni_key(m.group(1), m.group(2), None)[0]


def article_unit(block: list[str], ref: str) -> tuple[str, str]:
    """A quoted whole article ('Neni 64', paragraphs...) as (key, unit text). Some quotes (76/2016, art. 1) give
    only the paragraphs; the article is then the one the instruction names (`ref`)."""
    m = re.match(r'^Neni\s+(\d+(?:\s*/\s*\S+)?)$', block[0])
    if m:
        ref, block = m.group(1), block[1:]
    key, label = qbzpdf.neni_key(*re.match(r'(\d+)(?:\s*/\s*(\S+))?', ref.strip()).groups(), None)
    return key, '\n'.join([f'# {label}'] + block) + '\n'


def para_span(lines: list[str], num: str) -> tuple[int, int]:
    """Lines [i, j) of paragraph `num` ('1', '2/1') of a unit: from its numbered line up to the next numbered one."""
    pat = re.compile(rf'^{re.escape(num)}\.\s')
    i = next(k for k, l in enumerate(lines) if pat.match(l))
    j = i + 1
    while j < len(lines) and not re.match(r'^\d+(/\d+)?\.\s', lines[j]):
        j += 1
    return i, j


def letter_span(lines: list[str], letter: str) -> int:
    pat = re.compile(rf'^{re.escape(letter)}\)\s')
    return next(k for k, l in enumerate(lines) if pat.match(l))


def set_lines(units: dict, key: str, lines: list[str]) -> None:
    units[key] = {**units[key], 'text': '\n'.join(lines) + '\n'}


def replay(key: str, law: dict, before: dict) -> tuple[dict, set[str], list[str]]:
    """Apply one amending law to `before` ({key: unit}); returns (after, keys it touched, log)."""
    units = {k: dict(v) for k, v in before.items()}
    touched: list[str] = []
    log: list[str] = []
    order = list(units)

    def put(k, text, after=None):
        nonlocal order
        if k not in units:
            i = order.index(after) + 1 if after else len(order)
            order.insert(i, k)
        label = re.match(r'^# (.*)$', text, re.M).group(1)
        units[k] = {'label': label, 'kind': 'art', 'text': text}
        touched.append(k)

    def lines_of(k):
        return units[k]['text'].rstrip('\n').split('\n')

    def drop(k):
        units.pop(k)
        order.remove(k)
        touched.append(k)

    def phrase(k, old, new):
        t = units[k]['text']
        assert t.count(old) == 1, (k, old)
        set_lines(units, k, t.replace(old, new).rstrip('\n').split('\n'))
        touched.append(k)

    for art in law_articles(law['_paras']):
        head = art[0]
        if re.match(r'^(Hyrja në fuqi|Ky ligj hyn në fuqi)', head):
            break
        q = quotes(art)
        if m := re.match(r'^Neni (\d+(?:\s*/\s*\S+)?),? ndryshohet si (?:vijon|më poshtë):', head):
            k, text = article_unit(q[0], m.group(1))
            assert k == art_key(m.group(1)) and k in units, (key, head)
            put(k, text)
        elif m := re.match(r'^Pas nenit (\d+(?:\s*/\s*\S+)?) shtohet neni (\d+(?:\s*/\s*\S+)?) me këtë përmbajtje:', head):
            k, text = article_unit(q[0], m.group(2))
            assert k == art_key(m.group(2)) and k not in units, (key, head)
            prev = art_key(m.group(1))
            if prev not in units:   # 76/2016 adds 179/b "after 179/a", which does not exist; 179/1 precedes it
                prev = max(x for x in order if x.startswith(prev[:9]) and x < k)
                log.append(f'{key}: "{head}" — there is no article {m.group(1)}; {k} was placed after {prev}')
            put(k, text, after=prev)
        elif m := re.match(r'^Neni (\d+(?:\s*/\s*\S+)?) shfuqizohet\.$', head):
            drop(art_key(m.group(1)))
        elif m := re.match(r'^Pika (\d+),? e nenit (\d+),? ndryshohet si më poshtë:', head) \
                or re.match(r'^Në nenin (\d+), (?:paragraf(?:i)?|pika) (\d+),? ndryshohet si (?:vijon|më poshtë):', head):
            n, a = (m.group(1), m.group(2)) if head.startswith('Pika') else (m.group(2), m.group(1))
            k = art_key(a)
            ls = lines_of(k)
            i, j = para_span(ls, n)
            set_lines(units, k, ls[:i] + q[0] + ls[j:])
            touched.append(k)
        elif m := re.match(r'^Në nenin (\d+), shkronja “(\S+)” ndryshohet si më poshtë:', head):
            k = art_key(m.group(1))
            ls = lines_of(k)
            i = letter_span(ls, m.group(2))
            set_lines(units, k, ls[:i] + q[0] + ls[i + 1:])
            touched.append(k)
        elif m := re.match(r'^Në nenin (\d+) bëhen (?:këto ndryshime|ndryshimet e mëposhtme):', head):
            k = art_key(m.group(1))
            qi = 0
            for sub in art[1:]:
                if sub.startswith('“'):
                    continue
                ls = lines_of(k)
                if s := re.match(r'^(?:[a-z]\) )?Pika (\d+) (?:riformulohet|ndryshohet) si më poshtë:', sub):
                    i, j = para_span(ls, s.group(1))
                    set_lines(units, k, ls[:i] + q[qi] + ls[j:])
                    qi += 1
                elif s := re.match(r'^(?:[a-z]\) )?Pas pikës (\d+) shtohet pika (\S+) me këtë përmbajtje:', sub):
                    i, j = para_span(ls, s.group(1))
                    set_lines(units, k, ls[:j] + q[qi] + ls[j:])
                    qi += 1
                elif s := re.match(r'^Në pikën (\d+), togfjalëshi “([^”]+)” shfuqizohet\.$', sub):
                    i, j = para_span(ls, s.group(1))
                    seg = '\n'.join(ls[i:j])
                    assert seg.count(s.group(2)) == 1, (k, sub)
                    seg = re.sub(r'\s*' + re.escape(s.group(2)), '', seg)
                    set_lines(units, k, ls[:i] + seg.split('\n') + ls[j:])
                elif s := re.match(r'^\d+\. Nënparagrafi\s+“(\S+)” ndryshohet si vijon:', sub):
                    i = letter_span(ls, s.group(1))
                    set_lines(units, k, ls[:i] + q[qi] + ls[i + 1:])
                    qi += 1
                elif s := re.match(r'^\d+\. Shtohet paragrafi (\d+) me këtë përmbajtje:', sub):
                    set_lines(units, k, ls + q[qi])
                    qi += 1
                else:
                    raise SystemExit(f'{key}: unknown instruction in nenin {m.group(1)}: {sub}')
            assert qi == len(q), (key, head)
            touched.append(k)
        elif m := re.match(r'^Në nenin (\d+(?:\s*/\s*\S+)?), pika (\d+), në fjalinë e parë togfjalëshi “([^”]+)”,? '
                           r'zëvendësohet me togfjalëshin “([^”]+)”\.$', head):
            k = art_key(m.group(1))
            ls = lines_of(k)
            i, j = para_span(ls, m.group(2))
            seg = '\n'.join(ls[i:j])
            old = m.group(3)
            if seg.count(old) != 1:
                # The law may quote the old words slightly off; allow its "të" particles to be absent, and say so.
                pat = r'\s+'.join(r'(?:të\s+)?' if w == 'të' else re.escape(w) for w in old.split()).replace(r'(?:të\s+)?\s+', r'(?:të\s+)?')
                found = re.findall(pat, seg)
                assert len(found) == 1, (k, head)
                log.append(f'{key}: replaces “{old}” in {k} point {m.group(2)}, but the text reads “{found[0]}”; '
                           f'that phrase was replaced.')
                old = found[0]
            set_lines(units, k, ls[:i] + seg.replace(old, m.group(4)).split('\n') + ls[j:])
            touched.append(k)
        elif re.match(r'^Pjesa e Dymbëdhjetë e Kushtetutës “Komisioni Qendror i Zgjedhjeve” shfuqizohet\.$', head):
            for k in [k for k in order if k == 'pjesa-12' or k in ('neni-153', 'neni-154')]:
                drop(k)
        elif head == 'Dispozitë kalimtare' and key == 'ligji-9675-2007':
            k = 'kalimtare-ligji-9675'
            put(k, '\n'.join(['# Dispozita kalimtare të parashikuara me ligjin nr. 9675, datë 13.1.2007'] + art[1:]) + '\n',
                after='neni-183')
            units[k]['kind'] = 'transitional'
            units[k]['label'] = 'Dispozita kalimtare (ligji nr. 9675)'
        else:
            raise SystemExit(f'{key}: unknown instruction: {head}')
    if key == 'ligji-76-2016':
        # The annex ("ANEKS"), set after the law's signature.
        ps = law['_paras']
        i = ps.index('ANEKS')
        k = 'aneks'
        put(k, '\n'.join(['# ANEKS', ps[i + 1]]) + '\n', after='miratimi')
        units[k].update(kind='annex', label='Aneks')
        prev = k
        cur = None
        for p in ps[i + 2:]:
            if not p:
                continue
            if m := re.match(r'^Neni ([A-ZÇË]{1,2})$', p):
                k, label = qbzpdf.neni_key(None, None, m.group(1))
                cur = [f'# {label}']
                put(k, '# x\n', after=prev)
                units[k]['label'] = label
                prev = k
                continue
            cur.append(p)
            units[k]['text'] = '\n'.join(cur) + '\n'
    return {k: units[k] for k in order}, set(touched), log


# ------------------------------------------------------------------ comparing texts

def flat(text: str) -> str:
    """For comparing two copies of one provision: whitespace dropped, typographic hyphens (word-di-vision) joined."""
    t = re.sub(r'(?<=[a-zëç])-\s*(?=[a-zëç])', '', text)
    return re.sub(r'\s+', '', t)


def diff_summary(a: str, b: str) -> str:
    import difflib
    wa, wb = a.split(), b.split()
    sm = difflib.SequenceMatcher(None, wa, wb, autojunk=False)
    ops = [f'“{" ".join(wa[i1:i2])}” → “{" ".join(wb[j1:j2])}”' for o, i1, i2, j1, j2 in sm.get_opcodes() if o != 'equal']
    return '; '.join(ops)[:400]


# ------------------------------------------------------------------ the build

def editions() -> dict:
    eds = {}
    for name in ARCHIVE:
        b = cached(wb_url(name))
        units, notes = qbzpdf.read_edition(b)
        eds[name] = {'units': clean(units, notes), 'notes': notes, 'url': wb_url(name), 'sha': sha(b)}
    meta, b = fetch.publication('kushtetuta', offline=True)
    units, notes = qbzpdf.read_edition(b)
    eds['q2026'] = {'units': clean(units, notes), 'notes': notes, 'url': fetch.SITE + meta['pdf']['url'], 'sha': sha(b),
                    'meta_url': f'{fetch.API}/publications?type=kushtetuta'}
    return eds


def clean(units: dict, notes: dict) -> dict:
    """Drop what an edition prints only as a placeholder: a repealed article or part ('(Shfuqizuar me ligjin ...)')."""
    out = {}
    for k, u in units.items():
        n = notes.get(k, '')
        body = u['text'].rstrip('\n').split('\n')[1:]
        if re.match(r'^\(\s*(Shfuqizuar|.*; shfuqizuar me)', n, re.I) and (not body or u['kind'] == 'part'):
            continue
        out[k] = u
    return out


def build():
    laws = load_laws()
    eds = editions()
    k1998_bytes = cached(wb_url('k1998'))
    base, base_notes = qbzpdf.read_edition(k1998_bytes)
    assert not base_notes, base_notes

    # 1. replay every law in turn on the 1998 text
    states = [('1998-11-28', BASE_LAW, base, set())]
    logs = []
    for key, _, _ in LAWS:
        after, touched, log = replay(key, laws[key], states[-1][2])
        states.append((laws[key]['_in_force'], key, after, touched))
        logs += log
    last_touch: dict[str, int] = {}
    for i, (_, _, _, touched) in enumerate(states):
        for k in touched:
            last_touch[k] = i

    # 2. the words of each state, by the rule in the module docstring
    final = eds['q2026']['units']
    ed_at = {i: EDITION_AFTER[s[1]] for i, s in enumerate(states) if EDITION_AFTER.get(s[1])}
    touches = {}
    for i, (_, _, replayed, touched) in enumerate(states):
        for k in (replayed if i == 0 else touched):
            touches.setdefault(k, []).append(i)
    report = []
    chosen_states = []
    for i, (day, key, replayed, touched) in enumerate(states):
        ed = EDITION_AFTER.get(key)
        words = {}
        for k, u in replayed.items():
            # the period of this provision's words: from the last state that touched it to the next one
            a = max(t for t in touches[k] if t <= i)
            later = [t for t in touches[k] if t > i]
            if not later:
                src = final[k]
            else:
                inside = [ed_at[t] for t in sorted(ed_at) if a <= t < later[0] and k in eds[ed_at[t]]['units']]
                src = eds[inside[-1]]['units'][k] if inside else states[a][2][k]
            words[k] = {'label': u['label'], 'kind': u['kind'], 'text': src['text']}
        chosen_states.append(words)
    # the last state must be today's edition, unit for unit
    assert chosen_states[-1].keys() == final.keys(), set(chosen_states[-1]) ^ set(final)
    for k in final:
        assert chosen_states[-1][k]['text'] == final[k]['text'], k

    # verification: each law replayed on the words of the state before it, for every provision it touches, against
    # the official words chosen for the state after it (an edition's, wherever one covers that period)
    for i in range(1, len(states)):
        key = states[i][1]
        rep, touched, _ = replay(key, laws[key], chosen_states[i - 1])
        assert touched == states[i][3], key
        for k in sorted(touched):
            a = rep.get(k, {}).get('text', '')
            b = chosen_states[i].get(k, {}).get('text', '')
            if flat(a) != flat(b):
                report.append(f'{key}: {k}: ' + (diff_summary(a, b) if a and b else ('repealed by the replay only' if not a else 'missing from the replay')))
    # editorial differences: the Assembly's 1998 copy against the QBZ words used for provisions in force unchanged
    editorial = []
    for k, u in states[0][2].items():
        if chosen_states[0][k]['text'] != u['text']:
            d = diff_summary(u['text'], chosen_states[0][k]['text']) if flat(u['text']) != flat(chosen_states[0][k]['text']) else 'line breaks and spacing only'
            editorial.append(f'{k}: {d}')

    # 3. credit check against the publisher's notes in today's edition
    notes = eds['q2026']['notes']
    credit_report = []
    num_of = {k: re.search(r'ligji-(\d+)-', k).group(1) for k, _, _ in LAWS}
    def note_for(k):
        # annex articles carry no note of their own: the annex heading's note covers them
        return notes.get(k) or (notes.get('aneks', '') if k.startswith('aneks-') else '') \
            or (final[k]['text'].split('\n')[0] if k.startswith('kalimtare-') else '')
    for i, (day, key, _, touched) in enumerate(states[1:], 1):
        for k in touched:
            if k in final and not re.search(rf'nr\.\s*{num_of[key]}\b', note_for(k)):
                credit_report.append(f'{k}: changed by {key} but the note reads {note_for(k)!r}')
    for k, n in notes.items():
        for key, num in num_of.items():
            if re.search(rf'nr\.\s*{num}\b', n) and k in final and not any(k in s[3] for s in states if s[1] == key):
                credit_report.append(f'{k}: the note names {key} ({n!r}) but the law\'s instructions do not touch it')
    return laws, eds, states, chosen_states, report, credit_report, logs, k1998_bytes, editorial


def main():
    laws, eds, states, words, report, credit_report, logs, k1998_bytes, editorial = build()
    versions = []
    prev = None
    for i, (day, key, _, touched) in enumerate(states):
        units = words[i]
        if i == 0:
            v = {'from': day, 'source_url': wb_url('k1998'), 'sha256': sha(k1998_bytes),
                 'units': units,
                 'note': ('The text as enacted, from the Assembly\'s own copy (Internet Archive, 25 May 2006); provisions '
                          'no later law changed read as in the official QBZ edition of today.')}
        else:
            changes = {k: units.get(k) for k in sorted(set(units) | set(prev)) if units.get(k) != prev.get(k)}
            unexplained = [k for k in changes if k not in touched]
            assert not unexplained, (key, unexplained)
            law = laws[key]
            ed = EDITION_AFTER[key]
            v = {'from': day, 'source_url': law['_docx_url'], 'sha256': law['_docx_sha'], 'changes': changes,
                 'credits': {k: [key] for k in sorted(changes)}}
            if ed:
                v['note'] = (f'Words as in the official QBZ edition {ed[1:]} '
                             f'({"today" if ed == "q2026" else "Internet Archive capture"}); '
                             f'the changes replayed from {law["label"]} match it.')
            else:
                v['note'] = f'No consolidated edition of this state survives: the changes are replayed from {law["label"]}.'
        versions.append(v)
        prev = units

    law_out = {BASE_LAW: {
        'label': 'Ligji nr. 8417', 'title': 'Kushtetuta e Republikës së Shqipërisë', 'kind': 'law',
        'enacted': '1998-10-21', 'published': None, 'url': None, 'temporary_until': None, 'restores': None,
        'note': None}}
    for key, _, _ in LAWS:
        law_out[key] = {k: v for k, v in laws[key].items() if not k.startswith('_')}

    decisions = [
        'The act archive of qbz.gov.al starts in 2000 and has no dated versions of the Constitution, so its history is rebuilt by replaying the seven amending laws on the 1998 text.',
        'The 1998 text is the Assembly\'s own copy ("Kushtetuta e RSH.pdf", made from Word on 8 January 2006, linked from parlament.al), read from an Internet Archive capture of 25 May 2006. It predates the first amendment (law 9675 of 13 January 2007), so it is the text as enacted. The Fletorja Zyrtare 1998 nr. 28 itself is not online.',
        'Each law\'s instructions are applied to the text before it by parse.py (whole articles replaced, added or repealed; paragraphs, letters and phrases replaced or deleted). No instruction was applied by hand.',
        'The words of each version come from the official QBZ consolidated edition of that state where one exists (2008, 2012, 2015, 2016 and today), and from the replay otherwise. A provision that no later law changes reads as in today\'s edition throughout, so editorial differences between copies (capitals, spacing, word-division hyphens) never show as changes.',
        'Every provision the replay touches is compared with the QBZ edition of its state; differences that remain after ignoring whitespace and word-division hyphens are listed below.',
        'In-force dates: art. 84(3) of the Constitution sets the default (a law takes effect no sooner than 15 days after publication in the Fletorja Zyrtare). Each amending law states its own: 9675/2007 and 137/2015 "hyn në fuqi menjëherë" (dated here to the day of publication), the other five "15 ditë pas botimit" (publication day + 15). Publication days are the Fletorja Zyrtare issue dates given by qbz.gov.al, each checked against the date printed on the first page of that issue\'s PDF.',
        'The Constitution itself took effect on promulgation by the President (art. 183), by decree nr. 2260 of 28 November 1998, after the referendum of 22 November 1998.',
        'Enactment dates are read from each law\'s own text ("Miratuar në datën ..." or its heading); the qbz.gov.al act record is a day early for 88/2012 and 16/2022.',
        'Repealed provisions are removed: QBZ prints them only as a heading and a note ("(Shfuqizuar me ligjin ...)"). Part Twelve (the Central Election Commission, arts. 153-154) was repealed whole by law 9904/2008.',
        'The publisher\'s amendment notes are kept out of the text and used only to check the credits.',
    ]
    decisions += [f'Replay vs edition: {r}' for r in report] or ['Replay vs edition: every provision matches.']
    decisions += [f'Credit check: {r}' for r in credit_report] or ['Credit check: every credited provision is named in QBZ\'s note for that law, and every note matches a credited change.']
    decisions += [f'Law text: {l}' for l in logs] + [f'Law text (76/2016): {l}' for l in sorted(QUOTE_LOG)]
    words_only = [e for e in editorial if 'spacing only' not in e]
    decisions.append(f'Editorial differences between the Assembly\'s 1998 copy and the QBZ words used for the same '
                     f'provisions while unamended: {len(words_only)} provisions differ in their words (listed here), '
                     f'{len(editorial) - len(words_only)} more only in spacing or line breaks: '
                     + ' | '.join(words_only))

    sources = [
        {'name': 'Qendra e Botimeve Zyrtare (qbz.gov.al): amending laws (.docx), act records and Fletorja Zyrtare issues', 'url': 'https://qbz.gov.al/api/v1',
         'retrieved': RETRIEVED, 'requests': None,
         'licence': 'Official texts of the Republic of Albania; legal acts and their official collections are not subject to copyright (ligji nr. 35/2016, neni 12, pika 1, shkronja “b”).',
         'notes': 'Open JSON API, no login; one .docx per act.'},
        {'name': 'Qendra e Botimeve Zyrtare: consolidated Constitution (today\'s edition, PDF)', 'url': eds['q2026']['url'],
         'retrieved': RETRIEVED, 'requests': None, 'licence': 'As above.', 'notes': 'Free download; text layer, no OCR.'},
        {'name': 'Internet Archive: QBZ consolidated editions 2008, 2012, 2015, 2016', 'url': 'https://web.archive.org/',
         'retrieved': RETRIEVED, 'requests': None, 'licence': 'Internet Archive terms of use; texts as above.',
         'notes': '; '.join(f'{n}: {ts} {u}' for n, (ts, u) in ARCHIVE.items() if n != 'k1998')},
        {'name': 'Internet Archive: Kuvendi i Shqipërisë, "Kushtetuta e RSH.pdf" (the 1998 text)', 'url': wb_url('k1998'),
         'retrieved': RETRIEVED, 'requests': None, 'licence': 'Internet Archive terms of use; official text of the Assembly.',
         'notes': f'Capture {ARCHIVE["k1998"][0]} of {ARCHIVE["k1998"][1]}.'},
    ]
    urls = [json.loads(l)['url'] for l in open(CACHE / 'requests.jsonl', encoding='utf-8') if l.strip()]
    qbz = [u for u in urls if u.startswith(fetch.SITE)]
    arc = [u for u in urls if u.startswith('https://web.archive.org/')]
    today = eds['q2026']['url']
    counts = [
        sum(1 for u in qbz if u != today and 'publications' not in u),
        sum(1 for u in qbz if u == today or 'publications' in u),
        sum(1 for u in arc if 'qbz.gov.al' in u),
        sum(1 for u in arc if 'parlament' in u),
    ]
    for s, n in zip(sources, counts):
        s['requests'] = n
    sources[2]['notes'] += '. Request counts include archive.org CDX searches made while looking for sources.'

    part = {
        'country': {
            'code': 'AL', 'name': 'Albania', 'slug': 'albania', 'lang': 'sq', 'tz': 'Europe/Tirane',
            'future_branch': 'e-ardhme',
            'publisher': {'name': 'Qendra e Botimeve Zyrtare', 'email': 'qbz@qbz.gov.al.invalid'},
            'default_in_force_rule': {
                'text': 'Kushtetuta, neni 84 pika 3: "Ligji hyn në fuqi me kalimin e jo më pak se 15 ditëve nga botimi i tij në Fletoren Zyrtare." A law\'s own clause sets its day; most say "15 ditë pas botimit".',
                'source': eds['q2026']['url']},
            'licence_note': 'Texts: Qendra e Botimeve Zyrtare (qbz.gov.al) and Kuvendi i Shqipërisë; official acts are not subject to copyright in Albania.',
        },
        'sources': sources,
        'laws': law_out,
        'acts': [{
            'slug': 'kushtetuta', 'short': 'Kushtetuta', 'title': 'Kushtetuta e Republikës së Shqipërisë',
            'url': eds['q2026']['url'], 'first_law': BASE_LAW, 'earlier_laws': [],
            'versions': versions,
        }],
        'applies': [],
        'decisions': decisions,
        'ai_use': ['Claude Code (claude-opus-5-5) wrote fetch.py, qbzpdf.py and parse.py and chose the sources. No model output is used as legal text: every word comes from the cached official files.'],
    }
    OUT.parent.mkdir(exist_ok=True)
    tmp = OUT.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(part, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    tmp.replace(OUT)
    print(f'{OUT.name}: {len(versions)} versions, {len(versions[-1 if False else 0]["units"])} units at the start')
    for v in versions:
        print(' ', v['from'], len(v.get('changes', v.get('units', {}))), v['source_url'][:80])
    print('replay vs edition differences:', len(report))
    for r in report:
        print('  ', r)
    print('credit check:', len(credit_report))
    for r in credit_report:
        print('  ', r)
    for l in logs:
        print('  ', l)


if __name__ == '__main__':
    main()
