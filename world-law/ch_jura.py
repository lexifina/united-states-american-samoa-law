"""Jura for switzerland-jura-law, from the RSJU's own PDF of each act (current text only). Private: scripts/world-law.

    python -X utf8 scripts/world-law/ch_jura.py constitution <docs-date>
    python -X utf8 scripts/world-law/ch_jura.py list                       # act list from the RSJU's category pages
    python -X utf8 scripts/world-law/ch_jura.py build lois|ordonnances <docs-date>   # parts of 50 (cached fetch)
    python -X utf8 scripts/world-law/ch_jura.py publish <part> <docs-date>

The act list: the Sommaire page names every category of the systematic collection (List.aspx?idn=<n>); each leaf
category's page lists its acts (RSJU number, title, viewdocument id). Lois go to 20-lois-N, ordonnances to
40-ordonnances-N; acts whose own text check fails, or whose notes give no entry into force, are left out and listed
in left-out.json.
"""
from __future__ import annotations

import hashlib
import html as htmlmod
import json
import os
import re
import time
import sys
import warnings
from pathlib import Path

warnings.filterwarnings('ignore')
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ch_cantons as C  # noqa: E402
import ch_romandy as R  # noqa: E402

SLUG = 'jura'
BASE = 'https://rsju.jura.ch/fr/viewdocument.html'
clean = C.clean
letters = C.letters
MONTHS = 'janvier février mars avril mai juin juillet août septembre octobre novembre décembre'.split()


def _ref(s):  # endnote reference: 8 pt "5)" or "7)9)10)"
    return s['size'] < 8.6 and re.fullmatch(r'\s*(\d+\)\s*)+', s['text'])


def rows(raw: bytes):
    """Body rows [(page, y, [spans])] (no running head, page number, endnotes) and the endnote text."""
    import pymupdf
    doc = pymupdf.open(stream=raw, filetype='pdf')
    body, notes, in_notes = [], [], False
    for pn, pg in enumerate(doc):
        h = pg.rect.height
        lines = []
        for b in pg.get_text('dict')['blocks']:
            for l in b.get('lines', []):
                sp = [s for s in l['spans'] if s['text'].strip()]
                if sp:
                    lines.append([round(l['bbox'][1], 1), sp])
        lines.sort(key=lambda r: r[0])
        merged = []
        for y, sp in lines:
            if merged and abs(merged[-1][0] - y) < 2.5:
                merged[-1][1].extend(sp)
            else:
                merged.append([y, list(sp)])
        for y, sp in merged:
            sp.sort(key=lambda s: s['bbox'][0])
            if y < 80 or y > h - 75:
                continue
            main = [s for s in sp if not _ref(s) and s['size'] > 9.5]
            if not in_notes and main and all(abs(s['size'] - 10.0) < 0.3 for s in main):
                in_notes = True
            if in_notes:
                notes.append(''.join(s['text'] for s in sp))
                continue
            body.append((pn, y, sp))
    return body, ' '.join(notes)


def _text(sp, first_num=True):
    out, prev = [], None
    for i, s in enumerate(sp):
        if _ref(s):
            prev = s
            continue
        t = s['text']
        if s['size'] < 8.6 and re.fullmatch(r'\s*\d+\s*', t):
            t = t.strip() + ' '
        if prev is not None and s['bbox'][0] - prev['bbox'][2] > 1.5 and not t.startswith(' '):
            t = ' ' + t
        out.append(t)
        prev = s
    return clean(''.join(out))


def parse(raw: bytes):
    body, notes = rows(raw)
    units, order, outline, ingress = {}, [], [], []
    cur, marg, para, last_y, last_pn, marg_y = None, [], None, None, None, None

    def tgt():
        return units[cur]['lines'] if cur else ingress

    def flush():
        nonlocal para
        if para and clean(para):
            tgt().append(clean(para))
        para = None

    for pn, y, sp in body:
        margin = [s for s in sp if abs(s['size'] - 9.0) < 0.3]
        rest = [s for s in sp if s not in margin]
        if margin:
            mt = clean(''.join(s['text'] for s in margin))
            u = units.get(cur) if cur else None
            if u is not None and u.get('marg_y') is not None and 0 < y - u['marg_y'] < 14 and not marg:
                u['lines'][0] += ' ' + mt  # the margin title runs on to a second line
                u['marg_y'] = y
            else:
                marg.append(mt)
                marg_y = y
        if not rest:
            continue
        bold = 'Bold' in rest[0]['font']
        lead = clean(''.join(s['text'] for s in rest if 'Bold' in s['font'])) if bold else ''
        m = re.match(r'^(Article premier|Art\.\s*\d+[a-z]*(?:\s?(?:bis|ter|quater))?)', lead)
        if m:
            flush()
            num = '1' if m.group(1) == 'Article premier' else re.sub(r'^Art\.\s*', '', m.group(1)).replace(' ', '')
            key = R.art_key(num)
            b, i = key, 2
            while key in units:
                key = f'{b}-{i}'
                i += 1
            cur = key
            label = m.group(1)
            title = clean(' '.join(marg))
            marg = []
            rem = clean(lead[m.end():])  # the rest of a bold lead such as "Art. 5 à 8" (a range of articles)
            units[key] = {'label': label, 'lines': ['# ' + clean(f'{label} {rem} {title}' if rem else f'{label} {title}')],
                          'marg_y': marg_y if title else None}
            order.append(key)
            after = [s for s in rest if 'Bold' not in s['font']]
            para = _text(after) if after else None
            last_y, last_pn = y, pn
            continue
        if bold and all('Bold' in s['font'] for s in rest if not _ref(s)):
            flush()
            t = _text(rest)
            if cur is None and rest[0]['size'] > 13:
                ingress.append('# ' + t if not ingress else t)
            else:
                outline.append('## ' + t)
            last_y, last_pn = y, pn
            continue
        if marg and cur is not None:
            # a margin title with no article on its row: it heads the paragraphs that follow
            flush()
            tgt().append(clean(' '.join(marg)))
            marg = []
        t = _text(rest)
        new = (rest[0]['size'] < 8.6 and re.fullmatch(r'\s*\d+\s*', rest[0]['text'])) or \
            re.match(r'^([a-z]|\d+)[).]\s', t) or re.match(r'^[-–•]\s', t) or \
            (last_y is not None and pn == last_pn and y - last_y > 20)
        if para is None or new:
            flush()
            para = t
        else:
            para += ' ' + t
        last_y, last_pn = y, pn
    flush()
    if marg:
        tgt().append(clean(' '.join(marg)))
    out = {}
    if ingress:
        out['ingress'] = {'label': 'Titre et préambule', 'kind': 'preamble', 'text': '\n'.join(ingress) + '\n'}
    for k in order:
        out[k] = {'label': units[k]['label'], 'kind': 'art', 'text': '\n'.join(units[k]['lines']) + '\n'}
    if outline:
        out['gliederung'] = {'label': 'Structure', 'kind': 'heading', 'text': '\n'.join(outline) + '\n'}
    return out, notes


def source_letters(raw: bytes) -> str:
    """Every body span (running head, page numbers, endnotes and endnote references left out), span by span."""
    body, _ = rows(raw)
    spans = [s for _, _, sp in body for s in sp if not _ref(s)]
    side = [s for s in spans if abs(s['size'] - 9.0) < 0.3]  # margin titles: their own column, read after the text
    return letters(''.join(s['text'] for s in spans if s not in side) + ''.join(s['text'] for s in side))


def last_in_force(notes: str, docs_date: str):
    days = []
    for m in re.finditer(r'Entrée en vigueur le (\d{1,2})(?:er)?\s+(' + '|'.join(MONTHS) + r')\s+(\d{4})', notes):
        d = f'{m.group(3)}-{MONTHS.index(m.group(2)) + 1:02d}-{int(m.group(1)):02d}'
        if d <= docs_date:
            days.append(d)
    return max(days) if days else None


R.SOURCE_DOCS[SLUG] = {
    'holds': 'The RSJU publishes only the current text of each act, so each act has one version: the text in force today, dated by the latest entry into force its own notes give. It holds the constitution, the laws (lois) and the ordinances (ordonnances) in force, in the order of the systematic collection, added in parts; decrees, agreements, other acts and repealed acts are not included yet.',
    'source': 'The Recueil systématique de la législation jurassienne (RSJU), published by the Chancellerie d\'Etat at <https://rsju.jura.ch/>, as the PDF of each act; its notes list every amendment with its popular vote, federal guarantee and entry into force.',
    'dates': 'Each act\'s single version is dated by the latest entry into force named in its notes (for laws and ordinances, also in its own entry-into-force article) on or before the retrieval day; it is the "oldest version available" and is credited to the publisher. Earlier wording is not held.',
    'author': 'The author of each act\'s first commit is the publisher (RSJU), because the text is the current consolidation rather than the act as adopted, with an e-mail address that cannot exist.',
    'limits': 'The printed edition is binding (art. 5a of the loi sur les publications officielles, RSJU 170.51). The text is read from PDF; the notes are not included. Only the current wording is held. Only the acts listed above are included.',
    'licence_src': 'Taken from the Recueil systématique de la législation jurassienne (https://rsju.jura.ch/), Chancellerie d\'Etat. The site\'s terms (https://rsju.jura.ch/fr/Conditions-d-utilisation.html) reserve reproduction of the site\'s content; laws are not protected by copyright (Art. 5 URG).',
}


def constitution(docs_date):
    url = f'{BASE}?idn=20002&id=36641&download=1'
    raw = R.get(SLUG, url)
    units, notes = parse(raw)
    frm = last_in_force(notes, docs_date)
    title = 'Constitution de la République et Canton du Jura'
    act = R.current_only_act(SLUG, units, url, hashlib.sha256(raw).hexdigest(), frm, title, 'Cst. JU', '101',
                             f'Text as the RSJU publishes it today, in force since {frm} (the latest entry into force in '
                             'its notes); no earlier wording is held.')
    act['earlier_laws'] = ['ju-101-1977-03-20']
    pub = 'Chancellerie d\'Etat du Jura, Recueil systématique de la législation jurassienne (RSJU)'
    part = {'country': R.country_block(SLUG, pub, 'https://rsju.jura.ch/'),
            'sources': [{'name': 'Recueil systématique de la législation jurassienne (RSJU)', 'url': 'https://rsju.jura.ch/',
                         'retrieved': docs_date, 'licence': 'Art. 5 para. 1 let. a URG (SR 231.1): no copyright in acts.',
                         'notes': 'Current consolidated text of each act (PDF), with its amendment notes.'}],
            'laws': {'ju-101-1977-03-20': {'label': 'Cst. JU du 20 mars 1977', 'title': title + ' du 20 mars 1977',
                                           'kind': 'referendum', 'enacted': '1977-03-20', 'published': None, 'url': url,
                                           'temporary_until': None, 'restores': None, 'note': None}},
            'acts': [act], 'decisions': [
                'The RSJU publishes only the current text, so each act has one version, the oldest version available, '
                'dated by the latest entry into force in the act\'s notes on or before the retrieval day and credited '
                'to the publisher.',
                'The text is read from the PDF: each article\'s margin title follows its number on the first line; '
                'section headings are kept together in gliederung.md; the title, date and preamble in ingress.md. '
                'Running heads, page numbers, the notes and their references are left out.'],
            'ai_use': R.AI_USE}
    R.write_part(R.folder(SLUG) / 'corpus.d' / '10-constitution.json', part)
    return act


# ---------------------------------------------------------------- laws and ordinances

SITE = 'https://rsju.jura.ch'


def load_ok():
    p = Path(os.environ.get('LOCALAPPDATA', '')) / 'gitlaw-cpu.log'
    while True:
        try:
            last = p.read_text(encoding='utf-8').strip().splitlines()[-1]
            c, r = int(last.split('cpu5=')[1].split()[0]), int(last.split('ram=')[1].split()[0])
        except Exception:
            return
        if c <= 92 and r <= 85:
            return
        time.sleep(60)


def categories():
    """{idn: number} of every category named on the Sommaire page (a parent's page may list acts of its own)."""
    t = R.get(SLUG, SITE + '/fr/Sommaire/Sommaire.html').decode('utf-8', 'replace')
    cats = {}
    for m in re.finditer(r'List\.aspx\?idn=(\d+)&(?:amp;)?name=SubCategories"[^>]*>([^<]*)', t):
        lab = htmlmod.unescape(m.group(2)).strip()
        num = re.match(r'^(\d+)\.', lab)
        if num:
            cats.setdefault(m.group(1), num.group(1))
    return cats


def act_list():
    out, seen = [], set()
    for idn, num in sorted(categories().items(), key=lambda x: C.natkey(x[1])):
        load_ok()
        t = R.get(SLUG, f'{SITE}/Scripts/Modules/CustomView/List.aspx?idn={idn}&name=SubCategories').decode('utf-8')
        for m in re.finditer(r'<a href="/fr/viewdocument\.html\?idn=(\d+)&(?:amp;)?id=(\d+)"><strong>([^<]*)</strong>'
                             r'<span>([^<]*)</span>', t):
            if m.group(1) != idn or m.group(2) in seen:
                continue
            seen.add(m.group(2))
            out.append((clean(htmlmod.unescape(m.group(3))), idn, m.group(2), clean(htmlmod.unescape(m.group(4)))))
    out.sort(key=lambda x: C.natkey(x[0]))
    (R.folder(SLUG) / '.cache' / 'act-list.json').write_text(json.dumps(out, ensure_ascii=False, indent=0) + '\n',
                                                            encoding='utf-8')
    return out


def act_in_force(notes: str, docs_date: str, body: str = ''):
    """The latest entry into force the notes of a law or ordinance give on or before docs_date: "Entrée en vigueur
    le ...", "en vigueur depuis/dès le ..." (amendments), or a note that is only a date (the act's own entry into
    force, cited from its last article), or the act's own article ("La présente loi entre en vigueur le ...").
    The constitution keeps last_in_force (its published date)."""
    mo = '|'.join(MONTHS)
    pats = [r'Entrée en vigueur le (\d{1,2})(?:er)?\s+(' + mo + r')\s+(\d{4})',
            r'en\s+vigueur\s+(?:depuis|dès)\s+le\s+(\d{1,2})(?:er)?\s+(' + mo + r')\s+(\d{4})',
            r'(?:^|\s)\d+\)\s*(\d{1,2})(?:er)?\s+(' + mo + r')\s+(\d{4})(?=[\s,.;]|$)']
    days = []
    for p in pats:
        for m in re.finditer(p, notes):
            d = f'{m.group(3)}-{MONTHS.index(m.group(2)) + 1:02d}-{int(m.group(1)):02d}'
            if d <= docs_date:
                days.append(d)
    # the act's own article: "La présente ordonnance entre en vigueur le ..."
    for m in re.finditer(r'présente?\s+\w+\s+entre\s+en\s+vigueur\s+le\s+(\d{1,2})(?:er)?\s+(' + mo + r')\s+(\d{4})',
                         body or ''):
            d = f'{m.group(3)}-{MONTHS.index(m.group(2)) + 1:02d}-{int(m.group(1)):02d}'
            if d <= docs_date:
                days.append(d)
    return max(days) if days else None


def adopted_day(units):
    t = units.get('ingress', {}).get('text', '')
    m = re.search(r'\bdu (\d{1,2})(?:er)?\s+(' + '|'.join(MONTHS) + r')\s+(\d{4})', t)
    return f'{m.group(3)}-{MONTHS.index(m.group(2)) + 1:02d}-{int(m.group(1)):02d}' if m else None


def ju_act(sn, idn, did, title, docs_date):
    url = f'{BASE}?idn={idn}&id={did}&download=1'
    raw = R.get(SLUG, url)
    units, notes = parse(raw)
    frm = act_in_force(notes, docs_date, ''.join(u['text'] for u in units.values()))
    if not frm:
        raise ValueError('no entry into force in the notes')
    if not any(k.startswith('art-') for k in units):
        raise ValueError('no articles read')
    act = R.current_only_act(SLUG, units, url, hashlib.sha256(raw).hexdigest(), frm, title, None, sn,
                             f'Text as the RSJU publishes it today, in force since {frm} (the latest entry into force '
                             'its notes or its own text give); no earlier wording is held.')
    act['short'] = f'RSJU {sn}'
    laws = {}
    ad = adopted_day(units)
    if ad and ad <= frm:
        k = C.ascii_key(f'ju-{sn}-{ad}')
        laws[k] = {'label': f'RSJU {sn} du {C._dmy(ad)}', 'title': f'{title} du {C._dmy(ad)}', 'kind': 'law',
                   'enacted': ad, 'published': None, 'url': url, 'temporary_until': None, 'restores': None,
                   'note': None}
        act['earlier_laws'] = [k]
    return act, laws


WORDS = {'lois': (20, r'^Loi\b'), 'ordonnances': (40, r'^Ordonnance\b')}


def left_out(name, items):
    p = R.folder(SLUG) / 'left-out.json'
    cur = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
    cur[name] = items
    p.write_text(json.dumps(cur, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')


def build(word, docs_date, size=50):
    base, pat = WORDS[word]
    p = R.folder(SLUG) / '.cache' / 'act-list.json'
    lst = json.loads(p.read_text(encoding='utf-8')) if p.exists() else act_list()
    items = [x for x in lst if re.match(pat, x[3]) and x[0] != '101']
    print(len(items), word, flush=True)
    acts, laws, bad, i = [], {}, [], 0

    def write():
        name = f'{base + i:02d}-{word}-{i + 1}'
        q = R.folder(SLUG) / 'corpus.d' / f'{name}.json'
        if q.with_suffix('.PUBLISH').exists():
            raise SystemExit(f'{name} already published: rebuild would change it')
        R.write_part(q, {'laws': dict(sorted(laws.items())), 'acts': acts})
        left_out(name, bad)
        print(name, len(acts), 'acts', flush=True)

    for sn, idn, did, title in items:
        load_ok()
        try:
            a, l = ju_act(sn, idn, did, title, docs_date)
        except RuntimeError as e:
            raise SystemExit(f'jura: {e}')   # the host refused: stop, never skip past it
        except Exception as e:
            print('skip', sn, str(e)[:120], flush=True)
            bad.append(f'{sn}: {str(e)[:80]}')
            continue
        probs = R.acts_problems(SLUG, [a])
        if probs:
            print('left out (text check)', sn, probs[0][:160], flush=True)
            bad.append(f'{sn}: text check')
            continue
        while a['slug'] in {x['slug'] for x in acts}:
            a['slug'] += '-2'
        acts.append(a)
        for k, v in l.items():
            laws.setdefault(k, v)
        if len(acts) == size:
            write()
            acts, laws, bad, i = [], {}, [], i + 1
    if acts:
        write()


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'constitution':
        a = constitution(sys.argv[2])
        print(a['versions'][0]['from'], len(a['versions'][0]['units']))
    elif cmd == 'list':
        lst = act_list()
        print(len(lst), sum(1 for x in lst if re.match(r'^Loi\b', x[3])), 'lois',
              sum(1 for x in lst if re.match(r'^Ordonnance\b', x[3])), 'ordonnances')
    elif cmd == 'build':
        build(sys.argv[2], sys.argv[3])
    elif cmd == 'publish':
        print(R.publish(SLUG, sys.argv[2], sys.argv[3]))
