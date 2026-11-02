"""Phase 3 corpora for laos, cambodia, british-virgin-islands: UN Treaty Collection actions, Wikidata facts,
and the Cambodian Constitution (English, Senate edition, read from an Internet Archive capture).
Usage: phase3_build.py <cache dir holding untc/*.html, wikidata.json, kh/c2021.pdf>
Writes scripts/<slug>-law/corpus.json."""
import sys, re, json, html, hashlib
from pathlib import Path

CACHE = Path(sys.argv[1])
ROOT = Path(__file__).resolve().parents[1]
RET = '2026-10-30'
MON = {m: i for i, m in enumerate('Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split(), 1)}
NAMES = {"Cambodia": "cambodia", "Lao People's Democratic Republic": "laos"}
KIND = {'a': 'Accession', 'd': 'Succession', 'A': 'Acceptance', 'AA': 'Approval', 'c': 'Formal confirmation', '': 'Ratification'}
SKIP = {'VI-18', 'XXI-6-a', 'XI-A-1', 'VII-1'}


def iso(s):
    m = re.match(r'(\d+) (\w{3}) (\d{4})', s)
    return f'{int(m[3]):04d}-{MON[m[2]]:02d}-{int(m[1]):02d}'


def txt(s):
    s = re.sub(r'<sup>.*?</sup>', '', s, flags=re.S | re.I)
    s = re.sub(r'<[^>]+>', ' ', s)
    return re.sub(r'\s+', ' ', html.unescape(s).replace('\xa0', ' ')).strip()


def untc():
    out = {'laos': {}, 'cambodia': {}}
    for f in sorted((CACHE / 'untc').glob('*.html')):
        mid = f.stem
        if mid in SKIP or f.stat().st_size < 20000:
            continue
        raw = f.read_bytes()
        h = raw.decode('utf8', 'ignore')
        j = h.find('tcTreaty"')
        cell = h[j:h.find('</td>', j)]
        cell = re.sub(r'<br\s*/?>|</div>|</p>', '\n', cell.split('>', 1)[1])
        lines = [txt(x) for x in cell.split('\n')]
        lines = [x for x in lines if x]
        if re.match(r'^\d+\.?\s*[a-z]?\.?$', lines[0]):
            lines = lines[1:]
        title = re.sub(r'^\d+\.\s*([a-z]\s+)?', '', lines[0])
        adopted = lines[1] if len(lines) > 1 and re.search(r'\d{4}', lines[1]) and len(lines[1]) < 80 else None
        k = h.find('td_Ptitle')
        hdr = [x for x in (txt(x) for x in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', h[k:k + 3000], re.S)) if x][:3]
        has_sig = len(hdr) > 1 and hdr[1].startswith('Signature')
        for r in re.findall(r'<tr class="trB[^>]*>(.*?)</tr>', h, re.S):
            cs = re.findall(r'<td[^>]*>(.*?)</td>', r, re.S)
            if not cs or len(cs) > 5:
                continue
            n = re.sub(r'\s+\d+(\s*,\s*\d+)*$', '', txt(cs[0]))
            if n not in NAMES:
                continue
            cells = [txt(c) for c in cs[1:]]
            sig, act = (cells[0], cells[-1]) if has_sig else (None, cells[0])
            ev = []
            if sig and re.match(r'\d+ \w{3} \d{4}', sig):
                ev.append(('Signature', iso(sig)))
            if act:
                m = re.match(r'(\d+ \w{3} \d{4})\s*(AA|A|a|c|d)?', act)
                if m:
                    ev.append((KIND[m[2] or ''], iso(m[1])))
            if ev:
                out[NAMES[n]][mid] = dict(title=title, adopted=adopted, events=ev, sha=hashlib.sha256(raw).hexdigest(),
                                          url='https://treaties.un.org/Pages/ViewDetails.aspx?src=TREATY&mtdsg_no=' + mid.split('-')[0] + '-' + mid.split('-')[1] + '&clang=_en')
    return out


def treaties_act(items, label):
    ev = {}
    for mid, t in items.items():
        for kind, d in t['events']:
            ev.setdefault(d, []).append((mid, kind, t))
    laws, versions, state = {}, [], {}
    for d in sorted(ev):
        key = f'untc-{d}'
        laws[key] = dict(label=f'UN Treaty Collection: actions of {d}',
                         title=f'Treaty actions by {label} recorded in the United Nations Treaty Collection on {d}',
                         kind='treaty', enacted=d, published=None, url='https://treaties.un.org/',
                         temporary_until=None, restores=None, note=None)
        ch, cr = {}, {}
        for mid, kind, t in ev[d]:
            ukey = 'treaty-' + re.sub(r'[^a-z0-9]+', '-', mid.lower()).strip('-')
            st = state.setdefault(ukey, [])
            st.append((kind, d))
            lines = [f"# {t['title']}"]
            if t['adopted']:
                lines.append(f"Adopted: {t['adopted']}")
            lines.append('Depositary: Secretary-General of the United Nations')
            lines += [f'{kk}: {dd}' for kk, dd in st]
            lines.append(f"Source: {t['url']}")
            ch[ukey] = dict(label=t['title'][:80], kind='treaty', text='\n'.join(lines) + '\n')
            cr[ukey] = [key]
        v = {'from': d, 'source_url': 'https://treaties.un.org/Pages/ViewDetails.aspx',
             'sha256': hashlib.sha256(''.join(sorted(t['sha'] for _, _, t in ev[d])).encode()).hexdigest()}
        if not versions:
            v['units'] = ch
        else:
            v['changes'] = ch
        v['credits'] = cr
        versions.append(v)
    return laws, dict(slug='treaties', short='UNTC', title=f'Treaty actions of {label} (UN Treaty Collection): signature, ratification, accession',
                      url='https://treaties.un.org/Pages/ParticipationStatus.aspx', first_law=None, earlier_laws=[], versions=versions)


def legal_system(w):
    L = [f"# {w['name']}"]
    for k in ('official_name', 'capital', 'language', 'government', 'legislature', 'inception'):
        if w.get(k):
            L.append(f"{k.replace('_', ' ').capitalize()} (Wikidata): {w[k]}")
    L.append(f"Wikidata item: https://www.wikidata.org/wiki/{w['qid']}")
    units = {'state': dict(label='State', kind='fact', text='\n'.join(L) + '\n')}
    if w.get('courts'):
        C = ['# Courts recorded in Wikidata'] + [n + (f' (inception {d})' if d else '') + f': https://www.wikidata.org/wiki/{q}' for n, d, q in w['courts']]
        units['courts'] = dict(label='Courts', kind='fact', text='\n'.join(C) + '\n')
    if w.get('texts'):
        T = ['# Legal texts recorded in Wikidata'] + [f'{n}: https://www.wikidata.org/wiki/{q}' for n, q in w['texts']]
        units['legal-texts'] = dict(label='Legal texts', kind='fact', text='\n'.join(T) + '\n')
    v = {'from': w['modified'], 'source_url': f"https://www.wikidata.org/wiki/Special:EntityData/{w['qid']}.json", 'sha256': w['sha'], 'units': units,
         'note': 'Oldest version available: the Wikidata item as last modified on ' + w['modified'] + ' (retrieved ' + RET + '). It states facts about the legal system; it is not law text.'}
    return dict(slug='legal-system', short='Wikidata', title=f"Legal system of {w['name']}: open facts from Wikidata",
                url=f"https://www.wikidata.org/wiki/{w['qid']}", first_law=None, earlier_laws=[], versions=[v])


def constitution():
    import pymupdf
    raw = (CACHE / 'kh' / 'c2021.pdf').read_bytes()
    t = ''.join(p.get_text() for p in pymupdf.open(stream=raw, filetype='pdf')).split('\n')
    i = [n for n, l in enumerate(t) if l.strip() == 'PREAMBLE'][0]
    L = [re.sub(r'^New (Article \d)', lambda m: m.group(1), l.strip()) for l in t[i:]]
    add = [n for n, l in enumerate(L) if l.startswith('Additional Provisions to the Constitution')][0]

    def blocks(lines):
        paras, cur, prev = [], '', ''
        for l in lines:
            if not l or set(l) == {'*'}:
                if cur:
                    paras.append(cur)
                cur, prev = '', ''
                continue
            header = re.match(r'^(Article \d+.{0,70}|CHAPTER [IVXL]+|PREAMBLE|WE, THE PEOPLE OF CAMBODIA,|WITH THIS RESOLUTE WILL,)$', cur) if cur else None
            if cur and not header and not re.search(r'[.;:?!"”)]$', prev) and not (re.match(r'^Article \d', l) and (re.search(r'[.;:?!"”)]$', prev) or prev.isupper()) or not prev) and not re.match(r'^(CHAPTER [IVXL]+$|-|WITH |We |[A-Z]\.\s|[a-z]\)|\d+[.)]\s)', l):
                cur += ('' if cur.endswith('-') else ' ') + l
            else:
                if cur:
                    paras.append(cur)
                cur = l
            prev = l
        if cur:
            paras.append(cur)
        return paras

    res, cur, pending = {}, None, None
    for pre, paras in (('art-', blocks(L[:add])), ('add-art-', blocks(L[add + 1:]))):
        for p in paras:
            if p == 'PREAMBLE':
                cur = ['preamble', 'Preamble', 'preamble', ['# Preamble']]
                res['preamble'] = cur
                continue
            if pre == 'art-' and re.match(r'^CHAPTER [IVXL]+$', p):
                n = sum(1 for k in res if k.startswith('chapter-')) + 1
                cur = [f'chapter-{n:02d}', p.title().replace('Chapter', 'Chapter'), 'heading', [f'# {p}']]
                res[cur[0]] = cur
                pending = cur
                continue
            m = re.match(r'^Article (\d+)\b\s*[-:.]?\s*(.*)$', p)
            if m and len(p) < 110 and re.search(r'(:|New|\))\s*$|^Article \d+\.?\s*$', p):
                n = int(m[1])
                extra = re.sub(r'^[-:\s]+', '', m[2]).rstrip(': ')
                head = '# ' + ('Additional provision, ' if pre == 'add-art-' else '') + f'Art. {n}' + (f' ({extra})' if extra else '')
                cur = [f'{pre}{n:03d}', ('Additional provision, ' if pre == 'add-art-' else '') + f'Art. {n}', 'art', [head]]
                res[cur[0]] = cur
                pending = None
                continue
            if cur is None:
                continue
            if pending is not None and cur is pending and len(cur[3]) == 1:
                cur[3].append('# ' + p)
                continue
            cur[3].append(p)
    units = {k: dict(label=v[1], kind=v[2], text='\n'.join(v[3]) + '\n') for k, v in res.items()}
    return units, raw


def main():
    wd = json.load(open(CACHE / 'wikidata.json', encoding='utf8'))
    U = untc()
    specs = {'laos': ('LA', 'Laos', 'lo', 'Asia/Vientiane'), 'cambodia': ('KH', 'Cambodia', 'km', 'Asia/Phnom_Penh'),
             'british-virgin-islands': ('VG', 'British Virgin Islands', 'en', 'America/Tortola')}
    for slug, (code, name, lang, tz) in specs.items():
        laws, acts, sources, decisions = {}, [], [], []
        if U.get(slug):
            l, a = treaties_act(U[slug], name)
            laws.update(l)
            acts.append(a)
            sources.append(dict(name='United Nations Treaty Collection (multilateral treaties deposited with the Secretary-General)', url='https://treaties.un.org/', retrieved=RET,
                                licence='Facts only (treaty names, kinds of action, dates); no descriptive text copied. robots.txt Crawl-delay of 2 seconds obeyed.',
                                notes=f'Status-of-treaty pages for {len(U[slug])} treaties, each read once.'))
            decisions += ['Treaty actions are dated by the action date shown in the UN Treaty Collection; each date is one version credited to a law key untc-<date>.',
                          'Signature, ratification, accession (a), succession (d), acceptance (A), approval (AA) and formal confirmation (c) are copied as the Treaty Collection records them, under the participant name it uses.']
        w = wd[slug]
        acts.append(legal_system(w))
        sources.append(dict(name='Wikidata', url='https://www.wikidata.org/', retrieved=RET, licence='CC0 1.0', notes='Entity ' + w['qid'] + ', a courts query and the legal texts it links.'))
        decisions.append('The legal-system act is a single snapshot of Wikidata facts dated by the item own last-modified day, as the oldest version available.')
        if slug == 'cambodia':
            units, raw = constitution()
            cu = 'https://www.mfaic.gov.kh/files/uploads/2Z87AYOO63VI/Constitution%20of%20the%20Kingdom%20of%20Cambodia.pdf'
            acts.insert(0, dict(slug='constitution', short='Const.', title='Constitution of the Kingdom of Cambodia (as amended to February 2008), English translation', url=cu,
                                first_law=None, earlier_laws=[],
                                versions=[{'from': '2008-02-19', 'source_url': 'https://web.archive.org/web/20211102150800id_/' + cu, 'sha256': hashlib.sha256(raw).hexdigest(), 'units': units,
                                           'note': "Oldest version available. The Senate's foreword (March 2008) says the last amendment was promulgated in February 2008; 19 February 2008 is the date in the publisher's file name for this edition. English translation, not authoritative; the Khmer text alone is authentic."}]))
            sources.append(dict(name='Senate Secretariat General compilation, hosted by the Ministry of Foreign Affairs (mfaic.gov.kh)', url=cu, retrieved=RET,
                                licence='Not protected by copyright: Law on Copyright and Related Rights (2003), Article 10(a) and (d) exclude the Constitution and translations of it.',
                                notes='Bytes read from the Internet Archive capture of 2021-11-02; the host itself answers this machine with a WAF page, which was not touched. Text layer, no OCR.'))
            decisions += ["Constitution: the English text of the Senate Secretariat General compilation, as archived on 2021-11-02, is one oldest-version-available snapshot dated 2008-02-19; the source gives no per-article amendment history.",
                          "Paragraphs: the PDF's hard line wraps were joined into one paragraph per line (a line of 90 or more characters continues on the next line); hyphenated line ends were joined without a space.",
                          'The Khmer original is authentic and is not in this repository; the English text is the Senate\'s own non-official translation.']
        country = dict(code=code, name=name, slug=slug, lang=lang, tz=tz, future_branch='future',
                       publisher=dict(name='United Nations Treaty Collection and Wikidata' + ('; Senate of Cambodia (Constitution)' if slug == 'cambodia' else ''), email=f'{slug}@lexifina-first-build.invalid'),
                       default_in_force_rule=dict(text='No single commencement rule is applied: each version is dated by the event date its source records (treaty action date, last-modified day of a Wikidata item, or the compilation date of the Senate edition).', source='https://treaties.un.org/'),
                       licence_note='UN Treaty Collection facts; Wikidata (CC0)' + ('; Cambodian Constitution (not protected: Law on Copyright 2003, Art. 10)' if slug == 'cambodia' else ''))
        corpus = dict(country=country, sources=sources, laws=laws, acts=acts, applies=[], decisions=decisions, ai_use=['none'])
        p = ROOT / f'{slug}-law' / 'corpus.json'
        p.write_text(json.dumps(corpus, ensure_ascii=False, indent=1) + '\n', encoding='utf8', newline='\n')
        print(slug, {a['slug']: len(a['versions']) for a in acts}, len(laws))


main()
