"""Lithuania: build corpus.json from the cache only (no network). Deterministic: the same cache gives the same bytes.

The Constitution (1992):
  * version 1 is the Register of Legal Acts' (e-TAR) text of the Constitution as adopted (rs/legalact);
  * 1996-2006: e-TAR's consolidated editions for these years are not in any archive, so each amending law's own text
    (e-TAR rs/legalact) is replayed on the version before it. The replay is checked against the Seimas's consolidated
    page (lrs.lt) as archived in January 2006 (in force 2004-08-14 to 2006-05-25) and against e-TAR's 2014 edition;
  * 2014-, 2019-, 2022- editions are e-TAR's own consolidated texts (rs/actualedition), each checked against the
    lrs.lt page of the same period, and the 2022 edition against lrs.lt as served on the retrieval day.
In-force days are e-TAR's own edition dates ("Suvestinė redakcija nuo …"), from its edition list.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from lt_common import cached, paragraphs, sha, wb_url, CACHE  # noqa: E402
import konstitucija as K  # noqa: E402

SRC = json.loads((HERE / 'sources.json').read_text(encoding='utf-8'))
RETRIEVED = '2026-10-29'
TAR_ACT = 'https://www.e-tar.lt/portal/lt/legalAct/'
CHECKS: list[str] = []
PROBLEMS: list[str] = []


def cap(act, role):
    c = next(c for c in SRC['acts'][act]['captures'] if c['role'] == role)
    return c


def load(act, role):
    c = cap(act, role)
    b = cached(c['ts'], c['url'])
    return b, wb_url(c['ts'], c['url'])


def lawkey(no: str) -> str:
    return no.lower().replace('/', '-')


# ------------------------------------------------------------------ the Constitution

def edition_list(b: bytes) -> list[dict]:
    """e-TAR's list of consolidated editions: [{'from','to','laws':[(date, kind, no)],'id'}], oldest first."""
    s = b.decode('utf-8')
    out = []
    for row in re.findall(r'<tr[^>]*>(.*?)</tr>', s, flags=re.S):
        m = re.search(r'Suvestinė nuo (\d{4}-\d{2}-\d{2})', row)
        if not m:
            continue
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, flags=re.S)
        txt = [re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', c)).strip() for c in cells]
        to = next((re.search(r'\d{4}-\d{2}-\d{2}', t).group(0) for t in txt[1:2] if re.search(r'\d{4}-\d{2}-\d{2}', t)), None)
        laws = re.findall(r'(\d{4}-\d{2}-\d{2}) (įstatymas|nutarimas|pranešimas)(?: Nr\. ([\w/-]+))?', re.sub(r'<[^>]+>', ' ', row))
        ed = re.search(r'TAR\.47BB952431DA/([A-Za-z]{10})', row)
        out.append({'from': m.group(1), 'to': to, 'laws': laws, 'id': ed.group(1) if ed else None})
    return sorted(out, key=lambda e: e['from'])


def change_list(paras: list[str]) -> list[dict]:
    """The 'Pakeitimai:' list at the end of an e-TAR consolidated text: every amending act with its number, adoption
    date, publication and title."""
    i = len(paras) - 1 - paras[::-1].index('Pakeitimai:')
    out = []
    j = i + 1
    while j < len(paras):
        if re.fullmatch(r'\d+\.', paras[j]):
            who, ref, title = paras[j + 1], paras[j + 2], paras[j + 3]
            out.append({'who': who, 'ref': ref, 'title': title})
            j += 4
        else:
            j += 1
    return out


def set_para(lines, idx, new):
    lines = list(lines)
    lines[idx] = new
    return lines


def replay(prev: dict, law: str, paras: list[str]) -> tuple[dict, list[str]]:
    """Apply one amending law (its e-TAR text) to the units before it. Each law's operative wording is matched, so a
    law that does not say what this expects stops the build."""
    q = K.quoted(paras)
    body = ' '.join(paras)
    u = dict(prev)
    if law == 'I-1390':  # "Papildyti ... 47 straipsnį šia antrąja dalimi" + renumber parts 2-4 to 3-5
        assert 'Papildyti Lietuvos Respublikos Konstitucijos 47 straipsnį šia antrąja dalimi:' in body
        lines = K.body(u['art-047'])
        assert len(q) == 1 and len(q[0]) == 1 and len(lines) == 4
        u['art-047'] = K.make('art-047', '47 straipsnis', 'art', '# 47 straipsnis', [lines[0], q[0][0]] + lines[1:])
        return u, ['art-047']
    if law in ('VIII-32', 'IX-959'):  # 119(2) restated
        assert re.search(r'119 straipsnio 2 dal\w+ .*išdėstyti taip:', body)
        lines = K.body(u['art-119'])
        assert len(q) == 1 and len(q[0]) == 1 and len(lines) == 4
        u['art-119'] = K.make('art-119', '119 straipsnis', 'art', '# 119 straipsnis', set_para(lines, 1, q[0][0]))
        return u, ['art-119']
    if law in ('IX-1305', 'IX-1379', 'IX-2344'):  # whole article restated
        assert len(q) == 1, law
        m = K.ART.match(q[0][0])
        assert m, law
        key = f'art-{int(m.group(1)):03d}'
        assert f'Pakeisti {"Konstitucijos " if law == "IX-2344" else ""}{int(m.group(1))} straipsnį ir jį išdėstyti taip:' in body, law
        u[key] = K.make(key, q[0][0], 'art', f'# {q[0][0]}', q[0][1:])
        return u, [key]
    if law == 'IX-1378':  # 84 point 11 restated
        assert 'Papildyti 84 straipsnio 11 punktą ir jį išdėstyti taip:' in body
        lines = K.body(u['art-084'])
        idx = next(i for i, l in enumerate(lines) if l.startswith('11) '))
        assert len(q) == 1 and len(q[0]) == 1 and q[0][0].startswith('11) ')
        item = q[0][0]
        # the law ends the restated point with a full stop; every consolidated text keeps the list's semicolon
        if item.endswith('.') and lines[idx].endswith(';'):
            item = item[:-1] + ';'
        u['art-084'] = K.make('art-084', '84 straipsnis', 'art', '# 84 straipsnis', set_para(lines, idx, item))
        return u, ['art-084']
    if law == 'IX-2343':  # art 150 restated + the Constitutional Act on EU membership added as a component part
        assert len(q) == 2
        act, a150 = q
        assert a150[0] == '150 straipsnis' and 'Papildyti Lietuvos Respublikos Konstitucijos 150 straipsnį ir jį išdėstyti taip:' in body
        u['art-150'] = K.make('art-150', '150 straipsnis', 'art', '# 150 straipsnis', a150[1:])
        assert act[:3] == ['LIETUVOS RESPUBLIKOS', 'KONSTITUCINIS AKTAS', 'DĖL LIETUVOS RESPUBLIKOS NARYSTĖS EUROPOS SĄJUNGOJE']
        u['sudedamoji-4-es'] = K.make('sudedamoji-4-es', 'Konstitucinis aktas „Dėl Lietuvos Respublikos narystės Europos Sąjungoje“',
                                      'component', '# KONSTITUCINIS AKTAS „DĖL LIETUVOS RESPUBLIKOS NARYSTĖS EUROPOS SĄJUNGOJE“',
                                      act[3:] + ['2004 m. liepos 13 d.'])
        return u, ['art-150', 'sudedamoji-4-es']
    if law == 'X-572':  # 125(2) repealed; 125(3) becomes (2), words inserted, restated
        assert 'Konstitucijos 125 straipsnio 2 dalį pripažinti netekusia galios.' in body
        lines = K.body(u['art-125'])
        assert len(lines) == 3 and len(q) == 1 and len(q[0]) == 1
        ins = 'ir Lietuvos banko valdybos pirmininko teisinį statusą bei jo atleidimo pagrindus'
        assert lines[2].replace('įgaliojimus ', f'įgaliojimus {ins} ') == q[0][0]
        u['art-125'] = K.make('art-125', '125 straipsnis', 'art', '# 125 straipsnis', [lines[0], q[0][0]])
        return u, ['art-125']
    raise SystemExit(f'no replay rule for {law}')


def same(a: dict, b: dict, what: str, skip=()) -> None:
    keys = (set(a) | set(b)) - set(skip)
    bad = sorted(k for k in keys if a.get(k, {}).get('text') != b.get(k, {}).get('text'))
    if bad:
        PROBLEMS.append(f'{what}: differs in {", ".join(bad)}')
    else:
        CHECKS.append(f'{what}: identical in all {len(keys)} units')


def lrs(act, role):
    b, url = load(act, role)
    return K.split(paragraphs(b, True), 'lrs')[0]


def eu_act_in_lrs(paras: list[str], unit: dict) -> bool:
    """The EU membership Constitutional Act as lrs.lt prints it among the Constitution's component parts."""
    want = K.body(unit)[:-1]
    i = next(i for i, p in enumerate(paras) if p == 'DĖL LIETUVOS RESPUBLIKOS NARYSTĖS EUROPOS SĄJUNGOJE')
    got = paras[i + 1:i + 1 + len(want)]
    return got == want


def konstitucija():
    act = 'konstitucija'
    eb, eurl = load(act, 'editions')
    editions = edition_list(eb)
    ob, ourl = load(act, 'original')
    units, _ = K.split(paragraphs(ob), 'tar')
    # the two earlier captures of the same original differ only in the transcription slips the Register corrected
    for role in ('original:2015', 'original:2017'):
        b, _ = load(act, role)
        u2, _ = K.split(paragraphs(b), 'tar')
        d = sorted(k for k in units if units[k]['text'] != u2.get(k, {}).get('text'))
        CHECKS.append(f'e-TAR original text, capture {cap(act, role)["ts"]} against {cap(act, "original")["ts"]}: differs only in {", ".join(d) or "nothing"}')
    # notes and the change list from the newest edition
    nb, nurl = load(act, 'edition:2022-05-22')
    npar = paragraphs(nb)
    newest, notes = K.split(npar, 'tar')
    changes = change_list(npar)

    laws = {
        'referendumas-1992': {
            'label': 'Referendumas 1992-10-25', 'kind': 'referendum',
            'title': 'Lietuvos Respublikos Konstitucija, priimta 1992 m. spalio 25 d. referendume (Lietuvos aidas, 1992-11-10, Nr. 220; Valstybės žinios, 1992-11-30, Nr. 33-1014)',
            'enacted': '1992-10-25', 'published': '1992-11-10', 'url': TAR_ACT + 'TAR.47BB952431DA',
            'temporary_until': None, 'restores': None, 'note': None},
    }
    urls = {'I-1390': 'TAR.651FF3A29BC8', 'VIII-32': 'TAR.A5C16B3B5A0F', 'IX-959': 'TAR.FE97B1581593',
            'IX-1305': 'TAR.20536641E86D', 'IX-1378': 'TAR.314594719DFB', 'IX-1379': 'TAR.BA8A36926F52',
            'IX-2343': 'TAR.7BBBC89D161E', 'IX-2344': 'TAR.52AEB2C9C6DF', 'X-572': 'TAR.25EC748CCEA6',
            'PRANESIMAS-2013': 'TAR.C827F9A316A3', 'KT2-N1/2014': 'e404190084f311e3aba3d2563f167b94',
            'XIII-2004': '4a18f140553f11e9975f9c35aedfe438', 'XIV-1028': '075a92f0c17a11ec8d9390588bf2de65',
            'XIV-1029': '3ce1bac0c17a11ec8d9390588bf2de65', 'XIV-1030': '90188660c17a11ec8d9390588bf2de65'}
    for c in changes:
        m = re.match(r'(?:Nr\. ([\w/-]+), )?(\d{4}-\d{2}-\d{2}), (?:Žin\., \d{4}, Nr\. [\d-]+ \((\d{4}-\d{2}-\d{2})\)|paskelbta TAR (\d{4}-\d{2}-\d{2}))', c['ref'])
        assert m, c['ref']
        no = m.group(1) or 'PRANESIMAS-2013'
        pub = m.group(3) or m.group(4)
        if no == 'PRANESIMAS-2013':
            pub = re.search(r'\((\d{4}-\d{2}-\d{2})\)', c['ref']).group(1)
        kind = 'court' if 'Konstitucinis Teismas' in c['who'] or 'Konstitucinio Teismo' in c['who'] else 'law'
        label = {'PRANESIMAS-2013': 'KT pirmininko pranešimas 2013-11-13', 'KT2-N1/2014': 'KT nutarimas KT2-N1/2014'}.get(no, f'Įstatymas Nr. {no}')
        note = None
        if no == 'PRANESIMAS-2013':
            note = ('Notice by the President of the Constitutional Court, published 16 November 2013: the operation of the '
                    '2006 law amending Article 125 (No. X-572) is suspended while the Court examines it. The words of the '
                    'Constitution did not change.')
        if no == 'KT2-N1/2014':
            note = ('Constitutional Court ruling KT2-N1/2014: the 2006 law amending Article 125 (No. X-572) was adopted '
                    'contrary to Article 147(1). From the ruling\'s publication that law, including Article 125(2), may not '
                    'be applied, and the earlier wording does not return (part VII, points 2-3). The Register keeps '
                    'printing the 2006 wording with a note, and so does this record.')
        laws[lawkey(no)] = {'label': label, 'kind': kind, 'title': c['title'], 'enacted': m.group(2), 'published': pub,
                            'url': TAR_ACT + urls[no], 'temporary_until': None, 'restores': None, 'note': note}

    # law number -> the e-TAR text used for the replay
    texts = {}
    for c in SRC['acts'][act]['captures']:
        if c['role'].startswith('law:'):
            texts[c['role'][4:]] = c
    versions = [{'from': '1992-11-02', 'source_url': ourl, 'sha256': sha(ob), 'units': units}]
    state = units
    ed_sources = {'2014-01-24': 'edition:2014-01-24', '2019-09-01': 'edition:2019-09-01', '2022-05-22': 'edition:2022-05-22'}
    for ed in editions:
        nos = [no or ('PRANESIMAS-2013' if kind == 'pranešimas' else None) for _, kind, no in ed['laws']]
        if ed['from'] in ed_sources:
            b, url = load(act, ed_sources[ed['from']])
            par = paragraphs(b)
            assert par[0].startswith(f'Suvestinė redakcija nuo {ed["from"]}'), par[0]
            new, _ = K.split(par, 'tar')
            changed = sorted(k for k in set(new) | set(state) if new.get(k, {}).get('text') != state.get(k, {}).get('text'))
            # the component act added in 2004 is printed by lrs.lt, not by e-TAR's consolidated text: carry it
            if 'sudedamoji-4-es' in state:
                new['sudedamoji-4-es'] = state['sudedamoji-4-es']
                changed = [k for k in changed if k != 'sudedamoji-4-es']
            src_url, digest = url, sha(b)
        else:
            new, changed = dict(state), []
            for no in nos:
                if no in ('PRANESIMAS-2013',):
                    continue
                c = texts[no]
                b = cached(c['ts'], c['url'])
                new, ch = replay(new, no, paragraphs(b))
                changed += ch
            if len(nos) == 1:
                c = texts.get(nos[0])
            src_url = wb_url(texts[nos[0]]['ts'], texts[nos[0]]['url']) if nos[0] in texts else eurl
            digest = sha(cached(texts[nos[0]]['ts'], texts[nos[0]]['url'])) if nos[0] in texts else sha(eb)
        credits = {}
        for k in changed:
            if len(nos) == 1:
                credits[k] = [lawkey(nos[0])]
            else:
                named = [n for n in nos if n in notes.get(k, [])]
                if k == 'sudedamoji-4-es':
                    named = ['IX-2343']
                if len(named) != 1:
                    PROBLEMS.append(f'{ed["from"]}: cannot tell which of {nos} changed {k} (notes: {notes.get(k)})')
                    continue
                credits[k] = [lawkey(named[0])]
        v = {'from': ed['from'], 'source_url': src_url, 'sha256': digest}
        if changed:
            v['units'] = new
        else:  # a notice or ruling that changed no words
            assert nos and all(n in ('PRANESIMAS-2013', 'KT2-N1/2014') for n in nos), (ed, nos)
            credits = {'art-125': [lawkey(nos[0])]}
            if nos[0] == 'KT2-N1/2014':
                kb = cached(texts['KT2-N1/2014']['ts'], texts['KT2-N1/2014']['url'])
                v['source_url'], v['sha256'] = wb_url(texts['KT2-N1/2014']['ts'], texts['KT2-N1/2014']['url']), sha(kb)
        v['credits'] = credits
        versions.append(v)
        CHECKS.append(f'{ed["from"]}: {", ".join(nos)} -> {", ".join(sorted(credits)) or "-"}'
                      f'{" (wording unchanged)" if not changed else ""}')
        state = new

    def at(day):
        u = None
        for v in versions:
            if v['from'] <= day and 'units' in v:
                u = v['units']
        return u

    # independent checks of the replay and of each edition against the Seimas's own page
    same(at('2006-05-25'), lrs(act, 'lrs:2006-01'), 'replayed text in force 2004-08-14..2006-05-25 vs lrs.lt (Jan 2006)', skip=['sudedamoji-4-es'])
    for role, day in (('lrs:2007-11', '2007-11-15'), ('lrs:2008-10', '2008-10-31'), ('lrs:2014-02', '2014-02-08'),
                      ('lrs:2016-06', '2016-06-10'), ('lrs:2020-11', '2020-11-13'), ('lrs:2026-10', '2026-10-20')):
        same(at(day), lrs(act, role), f'text in force {day} vs lrs.lt capture {cap(act, role)["ts"]}', skip=['sudedamoji-4-es'])
    # lrs.lt updated its page for the 2022 amendments after 27 June 2022: that capture still shows the 2019 text
    same(at('2022-05-21'), lrs(act, 'lrs:2022-06'), f'text in force 2019-09-01..2022-05-21 vs lrs.lt capture {cap(act, "lrs:2022-06")["ts"]} (the page lagged the 2022-05-22 edition)', skip=['sudedamoji-4-es'])
    replayed_2006 = at('2013-11-15')
    b14, _ = load(act, 'edition:2014-01-24')
    same(replayed_2006, K.split(paragraphs(b14), 'tar')[0], 'replayed text in force 2006-05-26 vs e-TAR 2014-01-24 edition', skip=['sudedamoji-4-es'])
    for role in ('edition:2014-01-24:a', 'edition:2014-01-24:b', 'edition:2019-09-01:a'):
        b, _ = load(act, role)
        par = paragraphs(b)
        u2 = K.split(par, 'tar')[0]
        day = par[0].split()[3]
        d = sorted(k for k in u2 if u2[k]['text'] != at(day).get(k, {}).get('text'))
        CHECKS.append(f'e-TAR edition from {day}, capture {cap(act, role)["ts"]}: differs only in {", ".join(d) or "nothing"}')
    # today's text: lrs.lt as served on the retrieval day, and the EU act among its component parts
    live = CACHE / 'direct' / 'lrs-live.html'
    if live.exists():
        lb = live.read_bytes()
        same(versions[-1]['units'], K.split(paragraphs(lb, True), 'lrs')[0], f'text in force today vs lrs.lt as served {RETRIEVED}', skip=['sudedamoji-4-es'])
        ok = eu_act_in_lrs(paragraphs(lb, True), versions[-1]['units']['sudedamoji-4-es'])
        (CHECKS if ok else PROBLEMS).append(f'EU membership Constitutional Act (from Law IX-2343) vs lrs.lt {RETRIEVED}: {"identical" if ok else "DIFFERS"}')
    pb, _ = load(act, 'portal-latest')
    cur = re.search(r'Galiojanti suvestinė redakcija:.*?(\d{4}-\d{2}-\d{2}) -', pb.decode('utf-8'), flags=re.S).group(1)
    (CHECKS if cur == versions[-1]['from'] else PROBLEMS).append(
        f'e-TAR act page captured {cap(act, "portal-latest")["ts"]} names the edition in force from {cur}; the newest version here is from {versions[-1]["from"]}')

    return {
        'slug': 'konstitucija', 'short': 'Konstitucija',
        'title': 'Lietuvos Respublikos Konstitucija',
        'url': TAR_ACT + 'TAR.47BB952431DA',
        'first_law': 'referendumas-1992', 'earlier_laws': [],
        'versions': versions,
    }, laws


def main():
    acts, laws = [], {}
    a, l = konstitucija()
    acts.append(a)
    laws.update(l)
    reqs = sum(1 for _ in open(CACHE / 'requests.jsonl', encoding='utf-8'))
    corpus = {
        'country': {
            'code': 'LT', 'name': 'Lithuania', 'slug': 'lithuania', 'lang': 'lt', 'tz': 'Europe/Vilnius',
            'future_branch': 'ateitis',
            'publisher': {'name': 'Teisės aktų registras (e-TAR)', 'email': 'tar@e-tar.invalid'},
            'default_in_force_rule': {
                'text': 'Konstitucija art. 149(3): a law amending the Constitution takes effect no earlier than one month after its adoption; '
                        'art. 70(2): other laws take effect after signature and official publication, unless they set a later day. '
                        'The in-force day of each version here is the one the Register of Legal Acts gives its consolidated edition.',
                'source': TAR_ACT + 'TAR.47BB952431DA'},
            'licence_note': ('Legal acts and their official translations are not objects of copyright (Lietuvos Respublikos autorių teisių ir '
                             'gretutinių teisių įstatymas, art. 5). Texts from the Register of Legal Acts (www.e-tar.lt) and the Seimas '
                             '(www.lrs.lt), read through Internet Archive captures and, for lrs.lt, directly.'),
        },
        'sources': [
            {'name': 'Teisės aktų registras (Register of Legal Acts, www.e-tar.lt), via the Internet Archive', 'url': 'https://www.e-tar.lt',
             'retrieved': RETRIEVED, 'requests': reqs,
             'licence': 'Legal acts are not objects of copyright (Law on Copyright and Related Rights, art. 5); Internet Archive Wayback Machine captures (id_ raw form), pinned by timestamp in sources.json',
             'notes': 'www.e-tar.lt and e-seimas.lrs.lt answer this machine with a Cloudflare challenge and were not fetched; data.gov.lt (dataset 2613, the Register\'s open data) answers with a firewall block page. Every e-TAR text was read from a pinned Wayback capture: ' +
                      '; '.join(f'{c["role"]} {c["url"]} at {c["ts"]}' for c in SRC['acts']['konstitucija']['captures'] if 'e-tar' in c['url'])},
            {'name': 'Lietuvos Respublikos Seimas: Lietuvos Respublikos Konstitucija (www.lrs.lt)', 'url': 'https://www.lrs.lt/home/Konstitucija/Konstitucija.htm',
             'retrieved': RETRIEVED, 'requests': 1,
             'licence': 'Legal acts are not objects of copyright (Law on Copyright and Related Rights, art. 5)',
             'notes': 'Used to check every version, not as text: the page as served on the retrieval day, and Wayback captures ' +
                      ', '.join(c['ts'] for c in SRC['acts']['konstitucija']['captures'] if 'lrs.lt' in c['url']) + '. robots.txt allows it (Crawl-delay 20).'},
        ],
        'laws': dict(sorted(laws.items())),
        'acts': acts,
        'applies': [],
        'decisions': DECISIONS + [f'Check: {c}' for c in CHECKS] + [f'Open: {p}' for p in PROBLEMS],
        'ai_use': ['Claude Code (Claude Opus 5.5, claude-opus-5-5) wrote fetch.py, parse.py, konstitucija.py and lt_common.py and chose the sources. '
                   'No model wrote or altered legal text: every unit is the publisher\'s text or the amending law\'s own words, applied by code, '
                   'and the commit notes for the 2013 notice and the 2014 ruling paraphrase those documents in English (2 notes).'],
    }
    tmp = HERE / 'corpus.json.tmp'
    tmp.write_text(json.dumps(corpus, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    tmp.replace(HERE / 'corpus.json')
    for c in CHECKS:
        print('ok  ', c)
    for p in PROBLEMS:
        print('FAIL', p)
    print(sum(len(a['versions']) for a in acts), 'versions,', len(laws), 'laws')


DECISIONS = [
    'Lithuanian, the official language, as the Register of Legal Acts (e-TAR) prints it. The README is in English first.',
    'e-TAR, e-seimas.lrs.lt and the Constitutional Court site answer with a Cloudflare challenge, and data.gov.lt with a firewall block page; none was worked around. e-TAR texts come from pinned Internet Archive captures.',
    'In-force days are the start dates e-TAR gives its consolidated editions ("Suvestinė redakcija nuo"). No constitutional amendment sets its own day; Art. 149(3) only says not earlier than one month after adoption.',
    'Version 1 is e-TAR\'s text of the Constitution as adopted (rs/legalact), capture of 2018-06-26. The 2015 capture of the same page reads "KONSTITUCIJA" for "KONSTITUCIJĄ" in the preamble and the 2017 capture adds a comma in Art. 7; both are transcription slips the Register later corrected, and every consolidated text agrees with the 2018 capture.',
    'e-TAR\'s consolidated editions from 1996-07-21 to 2013-11-16 are in no archive, so those versions replay each amending law\'s own words (e-TAR rs/legalact) on the version before: I-1390 (Art. 47 part 2 inserted), VIII-32 and IX-959 (Art. 119(2) restated), IX-1305 (Art. 47), IX-1378 (Art. 84 point 11), IX-1379 (Art. 118), IX-2343 (Art. 150 and the EU membership Constitutional Act), IX-2344 (Art. 57), X-572 (Art. 125). Each rule asserts the law\'s operative words, and the result is checked against lrs.lt (2006) and e-TAR\'s 2014 edition (see the checks).',
    'Law IX-1378 restates Art. 84 point 11 ending with a full stop; e-TAR and lrs.lt print it with the semicolon that ends every point of the list, and so does this record.',
    'Where two or more laws took effect on one day (2003-04-21, 2004-08-14, 2022-05-22), each article is credited to the law that e-TAR\'s note under it names ("Straipsnio pakeitimas: Nr. …").',
    'The 2013 notice of the President of the Constitutional Court (suspension of Law X-572) and ruling KT2-N1/2014 changed no words; they are versions without units, credited to Art. 125. Their kinds are court.',
    'Units: the preamble (with the referendum line), the 15 chapter headings (I-XIV skirsnis and Baigiamieji nuostatai), the 154 articles, and from 2004 the Constitutional Act "Dėl Lietuvos Respublikos narystės Europos Sąjungoje", added to the Constitution by Law IX-2343 art. 1 and printed among its component parts by lrs.lt (e-TAR\'s consolidated text lists it in Art. 150 but does not print it). The three component parts of 1991-1992 (Art. 150) are separate acts and not included.',
    'Left out of the units: the title lines (in the act title), the 1992 signature block, e-TAR\'s notes under articles ("Straipsnio pakeitimas", "TAR pastaba") and its change list.',
    'Typesetting normalised once (lt_common.norm): spaces, straight and curly double quotes to „…“, a spaced hyphen to an en dash, soft hyphens dropped. On lrs.lt a <br> ends a paragraph.',
]

if __name__ == '__main__':
    main()
