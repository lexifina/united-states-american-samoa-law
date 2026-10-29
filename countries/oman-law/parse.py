"""Build corpus.json for Oman from the cache only (no network). Deterministic.

Texts: Qanoon.om transcriptions of the Official Gazette (each decree as issued, plus the consolidated "(معدل)" page whose
footnotes name the amending decree). Official check: the MJLA (Ministry of Justice and Legal Affairs) PDFs of the current
texts, compared article by article (see verify.py).
"""
import datetime, hashlib, json, os, re
import fetch, qpage

HERE = os.path.dirname(os.path.abspath(__file__))
RETRIEVED = '2026-10-29'
AR2EN = qpage.TO_EN
MONTHS = {'يناير': 1, 'فبراير': 2, 'مارس': 3, 'أبريل': 4, 'ابريل': 4, 'مايو': 5, 'يونيو': 6, 'يوليو': 7,
          'أغسطس': 8, 'اغسطس': 8, 'سبتمبر': 9, 'أكتوبر': 10, 'اكتوبر': 10, 'نوفمبر': 11, 'ديسمبر': 12}


def raw(p):
    return fetch.get(fetch.qurl(p), offline=True).decode('utf-8')


def sha(p):
    return hashlib.sha256(fetch.get(fetch.qurl(p), offline=True)).hexdigest()


def text(lines):
    return '\n'.join(lines) + '\n'


def ar_date(s):
    s = s.translate(AR2EN)
    m = re.search(r'(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{4})', s)
    if m:
        d, mo, y = map(int, m.groups())
        return '%04d-%02d-%02d' % (y, mo, d)
    m = re.search(r'(\d{1,2})\s+من\s+(\S+)\s+(?:سنة\s+)?(\d{4})', s)
    if m:
        return '%04d-%02d-%02d' % (int(m.group(3)), MONTHS[m.group(2)], int(m.group(1)))
    raise ValueError('no date in ' + s)


def decree_meta(p, key, label, title):
    """Issue date, gazette issue and date, and the in-force day from the decree's own commencement article."""
    pre, isdar, arts, notes, meta = qpage.parse(raw(p), '\0')
    sig = meta['sig']
    issued = ar_date(next(x for x in sig if x.startswith('الموافق')).split(':', 1)[1])
    j = next(i for i, x in enumerate(sig) if x.startswith('نشر'))
    pubm = ' '.join(sig[j:])
    gaz = re.search(r'رقم \(([٠-٩0-9]+)\)', pubm).group(1).translate(AR2EN)
    published = ar_date(pubm.split('الصادر في', 1)[1])
    rule = next(l for u in isdar for l in u['lines'] if 'يعمل به' in l)
    pd = datetime.date.fromisoformat(published)
    if 'من تاريخ صدوره' in rule:
        inforce = issued
    elif 'من اليوم التالي لتاريخ نشره' in rule:
        inforce = (pd + datetime.timedelta(days=1)).isoformat()
    elif 'بعد انقضاء سنة من تاريخ نشره' in rule:
        inforce = pd.replace(year=pd.year + 1).isoformat()
    else:
        raise ValueError('commencement not understood: ' + rule)
    h1 = re.search(r'<h1 class="entry-title">(.*?)</h1>', raw(p), re.S)
    title = qpage.clean_line(__import__('html').unescape(re.sub(r'<[^>]+>', '', h1.group(1))))   # the decree's own title
    law = {'label': label, 'title': title, 'kind': 'decree', 'enacted': issued, 'published': published,
           'url': fetch.qurl(p), 'temporary_until': None, 'restores': None, 'note': None}
    dec = '%s: issued %s, Official Gazette %s%s of %s; in force %s by its own article: "%s"' % (
        key, issued, 'supplement to issue ' if 'ملحق' in pubm else 'issue ', gaz, published, inforce, rule)
    return law, inforce, dec


def unit(label, kind, lines):
    return {'label': label, 'kind': kind, 'text': text(lines)}


def units_of(p, act_title, law_only=False):
    pre, isdar, arts, notes, meta = qpage.parse(raw(p), act_title, law_only=law_only)
    u = {}
    if pre:
        u['preamble'] = unit('ديباجة مرسوم الإصدار', 'preamble', pre)
    for x in isdar:
        u[x['key']] = unit(x['label'], 'issuance', x['lines'])
    for a in arts:
        if a['key'] in u:
            raise ValueError('%s: duplicate %s' % (p, a['key']))
        u[a['key']] = unit(a['label'], 'art', a['lines'])
    return u, arts, notes, meta


def skeleton(s):
    """Letters and digits only, Arabic digits, alef/yeh/teh-marbuta forms folded: for containment checks."""
    s = s.translate(qpage.TO_AR)
    s = re.sub('[أإآٱ]', 'ا', s).replace('ى', 'ي').replace('ة', 'ه')
    return re.sub(r'[^ء-ي٠-٩]', '', s)


def changes_between(a, b):
    """{key: unit or None} turning state a into state b."""
    out = {}
    for k in sorted(set(a) | set(b)):
        if a.get(k) != b.get(k):
            out[k] = b.get(k)
    return out


def law_key_of_note(note):
    m = re.search(r'رقم ([٠-٩]+) / ([٠-٩]+)', note)
    n, y = (int(x.translate(AR2EN)) for x in m.groups())
    return 'rd-%d-%d' % (y, n)


# ---------------------------------------------------------------- the Basic Statute
def replay_2011(v1, problems):
    """Apply Royal Decree 99/2011 to the 1996 Basic Statute. The decree's five items are applied as written."""
    bl, _ = qpage.blocks(raw('2011/rd2011099'))
    i = next(j for j, b in enumerate(bl) if b[1][0] == 'تعديلات بعض أحكام النظام الأساسي للدولة')
    items, cur = {}, None
    for kind, lines, fns in bl[i + 1:]:
        m = re.match(r'^(أولا|ثانيا|ثالثا|رابعا|خامسا|سادسا):\s*(.*)$', lines[0])
        if m:
            cur = m.group(1)
            items[cur] = []
            lines = ([m.group(2)] if m.group(2) else []) + lines[1:]
            if not lines:
                continue
        items[cur].append((kind, lines))
    if sorted(items) != sorted(['أولا', 'ثانيا', 'ثالثا', 'رابعا', 'خامسا']):
        problems.append('RD 99/2011: unexpected items %s' % sorted(items))
    v = dict(v1)

    def replaced_article(item, key, label):
        body = items[item]
        assert body[0][1][0].startswith('يستبدل بنص المادة'), body[0]
        assert qpage.ART.match(body[1][1][0].translate(AR2EN)), body[1]
        return unit(label, 'art', [l for _, ls in body[2:] for l in ls])

    v['art-006'] = replaced_article('أولا', 'art-006', v1['art-006']['label'])
    # ثانيا: a new paragraph in art. 42, sixth among its paragraphs
    body = items['ثانيا']
    assert body[0][1][0].startswith('تضاف فقرة جديدة إلى نص المادة (٤٢)') and 'سادسا' in body[0][1][0], body[0]
    assert body[1][1] == ['"الفقرة السادسة"'], body[1]
    new = [l for _, ls in body[2:] for l in ls]
    lines = v1['art-042']['text'].rstrip('\n').split('\n')
    lines = lines[:6] + new + lines[6:]          # line 0 is the article's opening sentence; items are lines 1..
    v['art-042'] = unit(v1['art-042']['label'], 'art', lines)
    # ثالثا: the fourth paragraph of art. 44 replaced
    body = items['ثالثا']
    assert body[0][1][0].startswith('يستبدل بالفقرة الرابعة من المادة (٤٤)'), body[0]
    new = [l for _, ls in body[1:] for l in ls]
    lines = v1['art-044']['text'].rstrip('\n').split('\n')
    if not lines[4].startswith('- مناقشة خطط التنمية'):
        problems.append('RD 99/2011 item 3: the fourth paragraph of art. 44 is not the development-plans paragraph')
    lines = lines[:4] + new + lines[5:]
    v['art-044'] = unit(v1['art-044']['label'], 'art', lines)
    v['art-056'] = replaced_article('رابعا', 'art-056', v1['art-056']['label'])
    # خامسا: Part V (art. 58) replaced by a new Part V, arts 58 and 58 bis to 58 bis (44)
    body = items['خامسا']
    assert body[0][1][0].startswith('يستبدل بالباب الخامس'), body[0]
    cur = None
    added = {}
    for kind, lines in body[1:]:
        m = qpage.ART.match(lines[0].translate(AR2EN)) if kind == 'h' else None
        if m:
            n, b1, k1, b2, k2, rest = m.groups()
            key, label = qpage.art_key(n, b1 or b2, k1 or k2)
            cur = key
            added[key] = (label, lines[1:])
            continue
        if kind == 'h':
            continue                                   # the part's heading
        added[cur][1].extend(lines)
    del v['art-058']
    for k, (label, lines) in added.items():
        v[k] = unit(label, 'art', lines)
    return v


def basic_statute(laws, decisions, problems):
    T = 'النظام الأساسي للدولة'
    acts = []
    l96, f96, d = decree_meta('1996/rd1996101', 'rd-1996-101', 'المرسوم السلطاني رقم ١٠١ / ٩٦', 'مرسوم سلطاني رقم ١٠١ / ٩٦ بإصدار النظام الأساسي للدولة')
    laws['rd-1996-101'] = l96; decisions.append(d)
    l11, f11, d = decree_meta('2011/rd2011099', 'rd-2011-99', 'المرسوم السلطاني رقم ٩٩ / ٢٠١١', 'مرسوم سلطاني رقم ٩٩ / ٢٠١١ بتعديل بعض أحكام النظام الأساسي للدولة')
    laws['rd-2011-99'] = l11; decisions.append(d)
    l21, f21, d = decree_meta('2021/rd2021006', 'rd-2021-6', 'المرسوم السلطاني رقم ٦ / ٢٠٢١', 'مرسوم سلطاني رقم ٦ / ٢٠٢١ بإصدار النظام الأساسي للدولة')
    laws['rd-2021-6'] = l21; decisions.append(d)
    l26, f26, d = decree_meta('2026/rd2026079', 'rd-2026-79', 'المرسوم السلطاني رقم ٧٩ / ٢٠٢٦', 'مرسوم سلطاني رقم ٧٩ / ٢٠٢٦ بتعديل النظام الأساسي للدولة')
    laws['rd-2026-79'] = l26; decisions.append(d)

    v1, _, _, _ = units_of('1996/rd1996101', T)
    v2 = replay_2011(v1, problems)
    v3, _, _, _ = units_of('2021/rd2021006', T)
    v4, arts4, notes4, _ = units_of('2021/l2021006', T)
    # RD 79/2026 art. 1: "الادعاء العام" becomes "النيابة العامة" wherever it occurs; check that is the whole difference
    expect = {k: dict(u, text=u['text'].replace('الادعاء العام', 'النيابة العامة')) for k, u in v3.items()}
    diff = changes_between(expect, v4)
    for k in sorted(diff):
        if 'الادعاء العام' in v3[k]['text'] and 'النيابة العامة' in v4[k]['text']:
            decisions.append('Basic Statute %s: the consolidated text also makes the words that agree with "النيابة العامة" feminine (e.g. "يتولى" becomes "تتولى"), beyond the literal substitution of RD 79/2026 art. 1; the consolidated wording is used, credited to RD 79/2026.' % k)
        else:
            problems.append('basic statute: consolidated text differs from RD 6/2021 + RD 79/2026 at %s' % k)
    fn_units = sorted(a['key'] for a in arts4 if a['fns'])
    vs = [{'from': f96, 'source_url': fetch.qurl('1996/rd1996101'), 'sha256': sha('1996/rd1996101'), 'units': v1, 'credits': {}}]
    c = changes_between(v1, v2)
    vs.append({'from': f11, 'source_url': fetch.qurl('2011/rd2011099'), 'sha256': sha('2011/rd2011099'), 'changes': c,
               'credits': {k: ['rd-2011-99'] for k in c},
               'note': 'Rebuilt by applying the five items of Royal Decree 99/2011 to the 1996 text; no consolidated text of the amended 1996 statute is published.'})
    c = changes_between(v2, v3)
    vs.append({'from': f21, 'source_url': fetch.qurl('2021/rd2021006'), 'sha256': sha('2021/rd2021006'), 'changes': c,
               'credits': {k: ['rd-2021-6'] for k in c},
               'note': 'Royal Decree 6/2021 issued a new Basic Statute and repealed Royal Decrees 101/96 and 99/2011 (its art. 2).'})
    c = changes_between(v3, v4)
    vs.append({'from': f26, 'source_url': fetch.qurl('2021/l2021006'), 'sha256': sha('2021/l2021006'), 'changes': c,
               'credits': {k: ['rd-2026-79'] for k in c}})
    decisions.append('Basic Statute: RD 79/2026 changes %d units (%s); Qanoon.om footnotes the change only at %s, and art. 1 of the decree applies it "wherever it occurs", so every unit where the words occur is credited.' % (
        len(c), ', '.join(sorted(c)), ', '.join(fn_units)))
    return {'slug': 'nizam-asasi', 'short': 'النظام الأساسي', 'title': T, 'url': fetch.qurl('2021/l2021006'),
            'first_law': 'rd-1996-101', 'earlier_laws': [], 'versions': vs}


# ---------------------------------------------------------------- acts with a consolidated page and footnoted amendments
def footnoted_act(slug, short, T, orig, cons, first, amenders, laws, decisions, problems, cons_law_only=False):
    lf, ff, d = decree_meta(orig, first[0], first[1], first[2])
    laws[first[0]] = lf; decisions.append(d)
    inforce = {}
    pages = {}
    for p, key, label, title in amenders:
        l, f, d = decree_meta(p, key, label, title)
        laws[key] = l; inforce[key] = f; pages[key] = p; decisions.append(d)
    v0, arts0, _, _ = units_of(orig, T)
    vf, artsf, notes, meta = units_of(cons, T, law_only=cons_law_only)
    if cons_law_only:                     # the consolidated page gives the law only; the decree's own units are as issued
        for k, u in v0.items():
            if not k.startswith('art-'):
                vf[k] = u
    credit = {}
    for a in artsf:
        fns = a['fns'] or ([] if a['key'] in v0 else a['sfns'])
        credit[a['key']] = sorted({law_key_of_note(notes[n]) for n in fns})
    for lines, fns in meta.get('dropped_heads', []):
        for n in fns:
            decisions.append('%s: Qanoon.om footnote "%s" is on the heading "%s"; headings are not units, so it has no commit of its own.' % (
                slug, notes[n], ' / '.join(lines)))
    events, tdiff = {}, []
    for k in sorted(set(v0) | set(vf)):
        if v0.get(k) == vf.get(k):
            if credit.get(k) and k in v0:
                problems.append('%s %s: footnoted (%s) but unchanged from the text as issued' % (slug, k, credit[k]))
            continue
        laws_k = credit.get(k) or []
        if not laws_k and k in v0 and k in vf:
            tdiff.append(k)
            vf[k] = v0[k]
            continue
        if len(laws_k) != 1:
            problems.append('%s %s: changed, credited to %s; not built' % (slug, k, laws_k or 'nothing'))
            continue
        lk = laws_k[0]
        # check: every line that is new in the consolidated text appears in the amending decree as published
        old = set((v0.get(k) or {'text': ''})['text'].split('\n'))
        dec = skeleton(' '.join(l for _, ls, _ in qpage.blocks(raw(pages[lk]))[0] for l in ls))
        for line in vf[k]['text'].split('\n') if vf.get(k) else []:
            if line and line not in old and skeleton(line) not in dec:
                problems.append('%s %s: new line not found in %s: %s' % (slug, k, lk, line[:80]))
        events.setdefault(inforce[lk], {})[k] = (lk, vf.get(k))
    if tdiff:
        decisions.append('%s: %s differ between the text as issued and the consolidated page with no footnote naming an amendment (transcription differences: a dropped letter or a line break); the text as issued is kept.' % (slug, ', '.join(tdiff)))
    vs = [{'from': ff, 'source_url': fetch.qurl(orig), 'sha256': sha(orig), 'units': v0, 'credits': {}}]
    for day in sorted(events):
        ch = {k: u for k, (lk, u) in sorted(events[day].items())}
        cr = {k: [lk] for k, (lk, u) in sorted(events[day].items())}
        lk0 = sorted({lk for lk, _ in events[day].values()})
        vs.append({'from': day, 'source_url': fetch.qurl(pages[lk0[0]]), 'sha256': sha(pages[lk0[0]]), 'changes': ch, 'credits': cr})
    # replay check: the last version equals the consolidated text
    state = dict(v0)
    for v in vs[1:]:
        for k, u in v['changes'].items():
            if u is None:
                state.pop(k, None)
            else:
                state[k] = u
    mism = sorted(changes_between(state, vf))
    if mism:
        problems.append('%s: replay differs from the consolidated text at %s' % (slug, mism))
    return {'slug': slug, 'short': short, 'title': T, 'url': fetch.qurl(cons), 'first_law': first[0], 'earlier_laws': [], 'versions': vs}


def main():
    laws, decisions, problems = {}, [], []
    acts = [basic_statute(laws, decisions, problems)]
    acts.append(footnoted_act(
        'qanun-al-jaza', 'قانون الجزاء', 'قانون الجزاء', '2018/rd2018007', '2018/l2018007',
        ('rd-2018-7', 'المرسوم السلطاني رقم ٧ / ٢٠١٨', 'مرسوم سلطاني رقم ٧ / ٢٠١٨ بإصدار قانون الجزاء'),
        [('2022/rd2022068', 'rd-2022-68', 'المرسوم السلطاني رقم ٦٨ / ٢٠٢٢', 'مرسوم سلطاني رقم ٦٨ / ٢٠٢٢ بتعديل بعض أحكام قانون الجزاء'),
         ('2025/rd2025011', 'rd-2025-11', 'المرسوم السلطاني رقم ١١ / ٢٠٢٥', 'مرسوم سلطاني رقم ١١ / ٢٠٢٥ بتعديل بعض أحكام قانون الجزاء'),
         ('2026/rd2026066', 'rd-2026-66', 'المرسوم السلطاني رقم ٦٦ / ٢٠٢٦', 'مرسوم سلطاني رقم ٦٦ / ٢٠٢٦ بتعديل بعض أحكام قانون الجزاء')],
        laws, decisions, problems, cons_law_only=True))
    acts.append(footnoted_act(
        'himayat-al-bayanat', 'قانون حماية البيانات الشخصية', 'قانون حماية البيانات الشخصية', '2022/rd2022006', '2022/l2022006',
        ('rd-2022-6', 'المرسوم السلطاني رقم ٦ / ٢٠٢٢', 'مرسوم سلطاني رقم ٦ / ٢٠٢٢ بإصدار قانون حماية البيانات الشخصية'),
        [('2026/rd2026068', 'rd-2026-68', 'المرسوم السلطاني رقم ٦٨ / ٢٠٢٦', 'مرسوم سلطاني رقم ٦٨ / ٢٠٢٦ بتعديل بعض أحكام قانون حماية البيانات الشخصية')],
        laws, decisions, problems))
    nreq = sum(1 for _ in open(os.path.join(fetch.CACHE, 'requests.jsonl'), encoding='utf-8'))
    ver = {}
    vp = os.path.join(HERE, 'verification.json')
    if os.path.exists(vp):
        ver = json.load(open(vp, encoding='utf-8'))
    corpus = {
        'country': {
            'code': 'OM', 'name': 'Oman', 'slug': 'oman', 'lang': 'ar', 'tz': 'Asia/Muscat', 'future_branch': 'future',
            'publisher': {'name': 'Qanoon.om (transcription of the Official Gazette of Oman)', 'email': 'qanoon@qanoon.invalid'},
            'default_in_force_rule': {
                'text': 'Basic Statute of the State (RD 6/2021) art. 91: "تنشر القوانين في الجريدة الرسمية خلال أسبوعين من تاريخ إصدارها، ويعمل بها من تاريخ نشرها، ما لم ينص فيها على تاريخ آخر." (Laws take effect from publication in the Official Gazette unless they fix another date.) Every decree built here fixes its own date.',
                'source': fetch.qurl('2021/l2021006')},
            'licence_note': 'Texts: Qanoon.om (https://qanoon.om), transcribing the Official Gazette of the Sultanate of Oman; checked against the Ministry of Justice and Legal Affairs (https://mjla.gov.om), whose content is licensed under the Government Open Licence - Sultanate of Oman.',
        },
        'sources': [
            {'name': 'Qanoon.om', 'url': 'https://qanoon.om', 'retrieved': RETRIEVED, 'requests': nreq,
             'licence': 'Qanoon.om states that the texts of law are public property in Oman under the Copyright and Related Rights Law and may be used, copied, published and translated freely; it says it is not an official source and refers users to the Official Gazette.',
             'notes': 'Each royal decree as issued (https://qanoon.om/p/<year>/rd<year><number>/) and a consolidated page per law (/p/<year>/l<year><number>/) whose footnotes name the amending decree for each article.'},
            {'name': 'Ministry of Justice and Legal Affairs (MJLA), laws section', 'url': 'https://mjla.gov.om/laws/1', 'retrieved': RETRIEVED, 'requests': 0,
             'licence': 'Government Open Licence - Sultanate of Oman (stated in the site footer).',
             'notes': 'Official PDFs of the current texts; their text layer uses broken glyph mapping, so they are used only for the letter check in verify.py, never as text. Result: ' + (ver.get('summary') or 'not run') + ' PDF sha256: ' + '; '.join('%s %s' % (k, v['sha256']) for k, v in sorted((ver.get('acts') or {}).items()))},
        ],
        'laws': dict(sorted(laws.items())),
        'acts': acts,
        'applies': [],
        'decisions': [
            'Texts are the Arabic texts; Qanoon.om\'s and decree.om\'s English translations were not used.',
            'Qanoon.om is not an official source (its own words). Its text is used because the official MJLA PDFs have no usable text layer (Arabic glyphs mapped out of order), and OCR is not used. Every current article was checked against the MJLA PDF letter by letter (letter counts per article; see verify.py and verification.json).',
            'Versions are rebuilt from each decree as issued: the original text, then each amending decree\'s new wording, credited to the decree that Qanoon.om\'s footnote names. The last version is checked to equal Qanoon.om\'s consolidated text exactly, and every new line is checked to appear in the amending decree.',
            'In-force days are those the decrees fix themselves (date of issue, the day after publication, or one year after publication); publication dates are those Qanoon.om records for the Official Gazette issue.',
            'Units: the decree\'s preamble (preamble), the promulgating decree\'s articles (isdar-NN), and the law\'s articles (art-NNN, art-NNN-bis, art-NNN-bis-NN). Book, part and chapter headings are not units.',
            'Text normalisation: HTML line breaks become lines; NBSP, RLM/LRM, ZWNJ and tatweel removed; Western digits written as Arabic-Indic digits; curly quotes and dashes unified; no space before Arabic punctuation. Words are untouched.',
            'The Basic Statute of 1996 and that of 2021 are one act (one folder): RD 6/2021 issued a new statute and repealed RD 101/96 and RD 99/2011, so articles of the 1996 text that the 2021 text lacks are removed on 2021-01-11.',
        ] + decisions + ['Open problem: ' + p for p in problems],
        'ai_use': ['None at data-build time: fetch.py, qpage.py, parse.py and verify.py are deterministic code written with Claude Code (claude-opus-5-5); no model reads, writes, translates or summarises legal text.'],
    }
    tmp = os.path.join(HERE, 'corpus.json.tmp')
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(corpus, f, ensure_ascii=False, indent=1)
        f.write('\n')
    os.replace(tmp, os.path.join(HERE, 'corpus.json'))
    for a in acts:
        print(a['slug'], len(a['versions']), 'versions', [(v['from'], len(v.get('units') or v.get('changes'))) for v in a['versions']])
    for p in problems:
        print('PROBLEM', p)


if __name__ == '__main__':
    main()
