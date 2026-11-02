"""Ticino for switzerland-ticino-law, from LexFind (www.lexfind.ch, run for the cantons by the Swiss State
Chancellors' Conference), which keeps every version of the canton's official PDF since 2006. The canton's own hosts
(m3.ti.ch, www3/www4.ti.ch) time out from this machine. Private: scripts/world-law.

    python -X utf8 scripts/world-law/ch_ticino.py act <lexfind tol id>         # print a parse summary
    python -X utf8 scripts/world-law/ch_ticino.py constitution <docs-date>
    python -X utf8 scripts/world-law/ch_ticino.py publish <part> <docs-date>
    python -X utf8 scripts/world-law/ch_ticino.py laws <docs-date> [max|0] [first part no]  # 0 = no cap
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import warnings
from pathlib import Path

warnings.filterwarnings('ignore')
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ch_cantons as C  # noqa: E402
import ch_romandy as R  # noqa: E402

SLUG = 'ticino'
LF = 'https://www.lexfind.ch'
clean = C.clean
letters = C.letters
_iso = C.iso


def _pages(raw: bytes):
    import pymupdf
    return pymupdf.open(stream=raw, filetype='pdf')


def _is_ref(s):  # footnote reference: small superscript digits
    return s['size'] < 7.5 and (s['flags'] & 1) and re.fullmatch(r'\s*\d+\s*', s['text'])


def body_lines(raw: bytes):
    """[(page, y, [spans])] of the body (no running head, page number or footnote zone), plus {n: footnote text}."""
    doc = _pages(raw)
    out, notes = [], {}
    for pn, pg in enumerate(doc):
        h = pg.rect.height
        rows = []
        for b in pg.get_text('dict')['blocks']:
            for l in b.get('lines', []):
                sp = [s for s in l['spans'] if s['text'].strip()]
                if sp:
                    rows.append((round(l['bbox'][1], 1), l['bbox'][0], sp))
        rows.sort(key=lambda r: (r[0], r[1]))
        # merge rows on one baseline (list letter + text, "Art. 1" + its first paragraph)
        merged = []
        for y, x, sp in rows:
            if merged and abs(merged[-1][0] - y) < 2.5:
                merged[-1][2].extend(sp)
            else:
                merged.append([y, x, list(sp)])
        for m in merged:
            m[2].sort(key=lambda s: s['bbox'][0])
        zone = False
        cur = None
        for y, x, sp in merged:
            if y < 50 or y > h - 45:
                continue  # running head (the RL number) and page number
            first = sp[0]
            if not zone and first['size'] < 7.5 and not (first['flags'] & 1) and re.fullmatch(r'\s*\d+\s*', first['text']) \
                    and len(sp) > 1:
                zone = True
            if zone:
                if first['size'] < 7.5 and re.fullmatch(r'\s*\d+\s*', first['text']):
                    cur = int(first['text'])
                    notes[cur] = clean(''.join(s['text'] for s in sp[1:]))
                elif cur is not None:
                    notes[cur] = clean(notes[cur] + ' ' + ''.join(s['text'] for s in sp))
                continue
            out.append((pn, y, sp))
    return out, notes


STRUCT = re.compile(r'^(TITOLO|CAPITOLO|SEZIONE|PARTE|LIBRO|Titolo|Capitolo|Sezione|Parte)\b')


def parse_ti_pdf(raw: bytes):
    lines, notes = body_lines(raw)
    units, order, outline, ingress = {}, [], [], []
    refs = {}  # unit -> [footnote numbers]
    cur = None
    pending_marg = None
    after_struct = False
    last_y = None
    para = None

    def target():
        return units[cur]['lines'] if cur else ingress

    def flush():
        nonlocal para
        if para is not None and clean(para):
            target().append(clean(para))
        para = None

    for pn, y, sp in lines:
        bold = [s for s in sp if 'Bold' in s['font']]
        txt_all = clean(''.join(s['text'] for s in sp if not _is_ref(s)))
        for s in sp:
            if _is_ref(s):
                refs.setdefault(cur or 'ingress', []).append(int(s['text']))
        if not txt_all:
            continue
        lead_bold = clean(''.join(s['text'] for s in sp[:len(bold)] if 'Bold' in s['font'])) if sp and 'Bold' in sp[0]['font'] else ''
        if lead_bold and re.match(r'^Art\.\s*\d', lead_bold):
            flush()
            m = re.match(r'^Art\.\s*(\d+[a-z]*(?:\s?(?:bis|ter|quater|quinquies|sexies))?)', lead_bold)
            num = m.group(1).replace(' ', '')
            key = R.art_key(num)
            b, i = key, 2
            while key in units:
                key = f'{b}-{i}'
                i += 1
            cur = key
            label = clean(lead_bold)
            units[key] = {'label': label, 'lines': ['# ' + clean(f'{label} {pending_marg or ""}')]}
            order.append(key)
            pending_marg = None
            after_struct = False
            rest = [s for s in sp if 'Bold' not in s['font']]
            if rest:
                para = _line_text(rest)
            last_y = y
            continue
        if not bold and STRUCT.match(txt_all) and len(txt_all) < 40:
            flush()
            outline.append('## ' + txt_all)
            after_struct = True
            last_y = y
            continue
        if bold and len(bold) == len(sp):
            flush()
            if after_struct and outline:
                outline[-1] = outline[-1] + ' ' + txt_all
                after_struct = False
            else:
                if pending_marg:
                    target().append(pending_marg)
                pending_marg = txt_all
            last_y = y
            continue
        # body text
        t = _line_text(sp)
        starts = (sp[0]['size'] < 9.5 and not (sp[0]['flags'] & 1) and re.fullmatch(r'\s*\d+\s*', sp[0]['text'])) \
            or re.match(r'^([a-z]|\d+)[).]\s', t) or re.match(r'^[-–•]\s', t) or (last_y is not None and y - last_y > 15) \
            or pn_changed(pn)
        if pending_marg:
            flush()
            target().append(pending_marg)
            pending_marg = None
        if para is None or starts:
            flush()
            para = t
        else:
            para = para + ' ' + t
        last_y = y
    flush()
    out = {}
    if ingress:
        ingress[0] = '# ' + ingress[0]
        out['ingress'] = {'label': 'Titolo e preambolo', 'kind': 'preamble', 'text': '\n'.join(ingress) + '\n'}
    for k in order:
        out[k] = {'label': units[k]['label'], 'kind': 'art', 'text': '\n'.join(units[k]['lines']) + '\n'}
    if outline:
        out['gliederung'] = {'label': 'Struttura', 'kind': 'heading', 'text': '\n'.join(outline) + '\n'}
    return out, notes, refs


_last_pn = [None]


def pn_changed(pn):
    return False


def layout_ok(raw: bytes) -> bool:
    """The Word/Aspose layout (8 pt paragraph numbers, 6.5 pt superscript footnote references) the parser reads;
    LexFind's older re-assembled PDFs set numbers differently and are not used."""
    from collections import Counter
    c = Counter()
    for pg in _pages(raw):
        for b in pg.get_text('dict')['blocks']:
            for l in b.get('lines', []):
                for s in l['spans']:
                    if s['text'].strip() and s['size'] < 9.5:
                        c[round(s['size'], 1)] += 1
    return c[8.0] > c[7.9]


def _line_text(sp):
    parts = []
    prev = None
    for i, s in enumerate(sp):
        if _is_ref(s):
            continue
        t = s['text']
        if i == 0 and s['size'] < 9.5 and re.fullmatch(r'\s*\d+\s*', t):
            t = t.strip() + ' '  # paragraph number
        if prev is not None and s['bbox'][0] - prev['bbox'][2] > 1.5:
            t = ' ' + t  # a tab stop (list letter, dash) becomes a space
        parts.append(t)
        prev = s
    return clean(''.join(parts)).replace('’', "'").replace('‘', "'")


def pdf_source_letters(raw: bytes) -> str:
    """Letters and digits of every span outside the running head, page number and footnote zone, less the
    superscript footnote references: span by span, independent of how lines become units."""
    lines, _ = body_lines(raw)
    return letters(''.join(s['text'] for _, _, sp in lines for s in sp if not _is_ref(s)))


NOTE_INFORCE = re.compile(r'in vigore dal (\d{1,2})\.(\d{1,2})\.(\d{4})')
NOTE_BU = re.compile(r'BU\s*(\d{4})\s*,\s*(\d+)')


def note_laws(notes: dict) -> dict:
    """{footnote n: (law key, label, in force, decided)} for footnotes naming an in-force day and a BU entry."""
    out = {}
    for n, t in notes.items():
        m = NOTE_INFORCE.search(t)
        b = NOTE_BU.search(t)
        d = re.search(r'(?:del|dell’|dell\')\s*(\d{1,2})\.(\d{1,2})\.(\d{4})', t)
        dec = f'{d.group(3)}-{int(d.group(2)):02d}-{int(d.group(1)):02d}' if d else None
        if not b or not (m or dec):
            continue
        # no "in vigore dal": the day of the popular vote (or decision) stands in for the window match
        inf = f'{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}' if m else dec
        out[n] = (f'ti-bu-{b.group(1)}-{int(b.group(2))}', f'BU {b.group(1)}, {int(b.group(2))}', inf, dec, t)
    return out


def versions_of(tol_id):
    meta = json.loads(R.get(SLUG, f'{LF}/api/fe/it/texts-of-law/{tol_id}/with-version-groups'))
    fams = meta['families']
    fam = fams[0]  # the current family
    out = []
    for group in fam:
        # several entries share an in-force day ("formless" republications): the one found last stands
        g = sorted(group, key=lambda x: (_iso(x['version_found_at']) or '', x['id']))
        best = g[-1]
        frm = _iso(best['version_active_since'])
        url = next((u['url'] for u in best.get('dtah_urls', []) if u['language'] == 'it'), None)
        if frm and url:
            out.append((frm, best, LF + url))
    out.sort(key=lambda x: x[0])
    return meta, out


def ti_act(tol_id, docs_date):
    meta, vs = versions_of(tol_id)
    laws, versions = {}, []
    prev_units, prev_from = None, None
    title = None
    raws = [(frm, best, url, R.get(SLUG, url)) for frm, best, url in vs]
    ok = [layout_ok(r[3]) for r in raws]
    start = max([i + 1 for i, o in enumerate(ok) if not o] or [0])
    for frm, best, url, raw in raws[start:]:
        units, notes, refs = parse_ti_pdf(raw)
        if not units:
            continue
        title = title or clean(best['title'])
        nl = note_laws(notes)
        for n, (k, label, inf, dec, t) in nl.items():
            laws.setdefault(k, {'label': label, 'title': clean(t)[:300], 'kind': 'law', 'enacted': dec,
                                'published': None, 'url': None, 'temporary_until': None, 'restores': None,
                                'note': None})
        ver = {'from': frm, 'source_url': url, 'sha256': hashlib.sha256(raw).hexdigest()}
        if prev_units is None:
            ver['units'], ver['credits'] = units, {}
        else:
            changed = sorted(k for k in set(prev_units) | set(units)
                             if prev_units.get(k, {}).get('text') != units.get(k, {}).get('text'))
            if not changed:
                continue
            ver['changes'] = {k: units.get(k) for k in changed}
            window = {n: v for n, v in nl.items() if prev_from < v[2] <= frm}
            day = sorted({v[0] for v in window.values()})
            cr = {}
            for k in changed:
                ls = sorted({window[n][0] for n in refs.get(k, []) if n in window}) or (day if len(day) == 1 else [])
                if ls:
                    cr[k] = ls
            ver['credits'] = cr
        versions.append(ver)
        prev_units, prev_from = units, frm
    sn = meta['systematic_number']
    used = set()
    for v in versions:
        for ls in v.get('credits', {}).values():
            used.update(ls)
    okey = f'ti-{C.ascii_key(sn)}-oldest'
    act = {'slug': C.ascii_key(sn), 'short': f'RL {sn}', 'title': title or sn,
           'url': f'{LF}/fe/it/tol/{tol_id}/it', 'first_law': None, 'earlier_laws': [],
           'systematic_number': sn, 'versions': versions}
    return act, {k: laws[k] for k in sorted(used)}


DECISIONS = [
    'Every version is the canton\'s official PDF as LexFind keeps it, dated by the day LexFind gives it as in force '
    '(version_active_since); where LexFind holds several copies for one day (formal republications), the copy it '
    'found last is used, and a version whose text is unchanged is skipped.',
    'Changes are credited to the amending acts that the version\'s own footnotes name with an entry into force after '
    'the previous version and on or before this one ("in vigore dal ... - BU yyyy, p"), matched to the article that '
    'cites the footnote (a footnote that gives no entry into force is matched by the day of the popular vote or '
    'decision it names); a change in an article that cites none of them is credited to that act only when the '
    'window holds a single amending act, and is otherwise recorded as unexplained, from the publisher.',
    'Each act\'s first version is the oldest LexFind holds in the canton\'s current PDF layout (older copies LexFind '
    're-assembled set paragraph numbers and footnote references differently and are not used); it is credited to '
    'the publisher as the oldest version available. Typographic apostrophes are written as \'.',
    'Section headings are kept together in gliederung.md; the title, date and preamble in ingress.md. Running heads, '
    'page numbers, footnotes and footnote references are left out.',
]

R.SOURCE_DOCS[SLUG] = {
    'holds': 'Each act has every version LexFind keeps of the canton\'s official text in its current PDF layout (for the constitution, from 2013) to today. It holds the constitution, laws (leggi) and the regolamenti in force, in the order of the systematic collection, added in parts; decrees, agreements and repealed acts are not included yet.',
    'source': 'The Raccolta delle leggi del Cantone Ticino, as the canton publishes it in PDF, in the copies kept by [LexFind](https://www.lexfind.ch/), the portal of Swiss federal and cantonal legislation run on behalf of the Swiss State Chancellors\' Conference, which holds every version of each act published since May 2006.',
    'dates': 'Each version is dated by the day LexFind gives it as in force, taken from the act\'s text. Each act\'s first commit is the oldest version LexFind holds, credited to the publisher.',
    'author': 'The author of each later commit is the amending act named in the version\'s footnotes by its entry in the Bollettino ufficiale delle leggi (BU yyyy, page), with an e-mail address that cannot exist. Where several take effect in one version and the footnotes do not tie a change to one of them, the commit names them all.',
    'limits': 'The binding text is the one published in the Bollettino ufficiale delle leggi. The text is read from PDF; footnotes are not included. Only the acts listed above are included.',
    'licence_src': 'Taken from the canton\'s official PDF editions as kept by LexFind (https://www.lexfind.ch/), the portal run for the Swiss State Chancellors\' Conference.',
}


def constitution(docs_date):
    act, laws = ti_act(20038, docs_date)
    pub = 'Repubblica e Cantone Ticino, Raccolta delle leggi (copy kept by LexFind)'
    if not laws:
        laws = {}
    okey = 'ti-cost-1997-12-14'
    laws[okey] = {'label': 'Costituzione del 14 dicembre 1997', 'title': act['title'], 'kind': 'referendum',
                  'enacted': '1997-12-14', 'published': None, 'url': None, 'temporary_until': None,
                  'restores': None, 'note': None}
    act['earlier_laws'] = [okey]
    part = {'country': R.country_block(SLUG, pub, LF + '/fe/it/'),
            'sources': [{'name': 'LexFind: Raccolta delle leggi del Cantone Ticino', 'url': LF + '/fe/it/',
                         'retrieved': docs_date,
                         'licence': 'Art. 5 para. 1 let. a URG (SR 231.1): no copyright in acts.',
                         'notes': 'Every version of the official PDF that LexFind keeps (since 2006).'}],
            'laws': dict(sorted(laws.items())), 'acts': [act], 'decisions': DECISIONS, 'ai_use': R.AI_USE}
    R.write_part(R.folder(SLUG) / 'corpus.d' / '10-costituzione.json', part)
    return act


def law_list():
    """Every active "Legge ..." of Ticino in LexFind's systematic order (metadata only)."""
    d = json.loads(R.get(SLUG, f'{LF}/api/fe/it/entities/21/systematics'))
    ids = [k for k, v in d.items() if k and not v.get('children')]
    tols = []
    for i in range(0, len(ids), 80):
        q = '&'.join('tols_for_systematics%5B%5D=' + x for x in ids[i:i + 80])
        d2 = json.loads(R.get(SLUG, f'{LF}/api/fe/it/entities/21/systematics?active_only=true&' + q))
        tols += [(t['systematic_number'], t['id'], t['title']) for v in d2.values() for t in v.get('tols', [])
                 if t.get('is_active') and re.match(r'^Legge\b', t['title'])]
    seen, out = set(), []
    for sn, tid, title in sorted(tols, key=lambda x: C.natkey(x[0])):
        if tid not in seen and sn != '101.000':
            seen.add(tid)
            out.append((sn, tid))
    return out


def laws(docs_date, mx=None, part_no=1):
    """part_no > 1 continues after the parts already written: acts already in a leggi part are skipped."""
    lst = law_list()
    if mx:
        lst = lst[:mx]
    done = set()
    for q in sorted((R.folder(SLUG) / 'corpus.d').glob('*-leggi-*.json')):
        if int(q.stem.rsplit('-', 1)[1]) < part_no:
            done |= {a['url'].split('/')[-2] for a in json.loads(q.read_text(encoding='utf-8'))['acts']}
    lst = [(sn, tid) for sn, tid in lst if str(tid) not in done]
    print(len(lst), 'laws', flush=True)
    acts, lw = [], {}
    for sn, tid in lst:
        try:
            a, l = ti_act(tid, docs_date)
        except Exception as e:  # an act whose PDFs the parser cannot read is left out
            print('skip', sn, str(e)[:100], flush=True)
            continue
        if not a['versions'] or len(a['versions'][0]['units']) < 2:
            continue
        if not R.act_ok(SLUG, a):
            print('left out (text check)', sn, flush=True)
            continue
        if a['slug'] in {x['slug'] for x in acts}:
            a['slug'] += '-2'
        acts.append(a)
        lw.update(l)
        if len(acts) == 50:
            R.write_part(R.folder(SLUG) / 'corpus.d' / f'{19 + part_no:02d}-leggi-{part_no}.json',
                         {'laws': dict(sorted(lw.items())), 'acts': acts})
            print('part', part_no, flush=True)
            acts, lw, part_no = [], {}, part_no + 1
    if acts:
        R.write_part(R.folder(SLUG) / 'corpus.d' / f'{19 + part_no:02d}-leggi-{part_no}.json',
                     {'laws': dict(sorted(lw.items())), 'acts': acts})
        print('part', part_no, 'last', len(acts), flush=True)


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'laws':
        laws(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] != '0' else None,
             int(sys.argv[4]) if len(sys.argv) > 4 else 1)
    elif cmd == 'constitution':
        a = constitution(sys.argv[2])
        print([v['from'] for v in a['versions']], len(a['versions'][0]['units']))
    elif cmd == 'publish':
        print(R.publish(SLUG, sys.argv[2], sys.argv[3]))
