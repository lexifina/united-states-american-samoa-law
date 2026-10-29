"""Build corpus.json for Qatar from the Al Meezan API cache only (no network). Deterministic."""
import calendar, datetime, hashlib, html, json, os, re
import fetch

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = 'https://almeezan.qa'
RETRIEVED = '2026-10-28'

AR_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')


def clean(desc):
    """Al Meezan HTML -> one paragraph per line. Typesetting only; words untouched."""
    s = desc or ''
    s = re.sub(r'(?i)<br\s*/?>|</div>|</p>|</li>|<div[^>]*>|<p[^>]*>', '\n', s)
    s = re.sub(r'<[^>]+>', '', s)
    s = html.unescape(s)
    s = s.replace(' ', ' ').replace('‏', '').replace('‎', '').replace('ـ', '')  # NBSP, RLM/LRM, tatweel
    s = s.replace('\r', '\n').replace('\t', ' ')
    s = s.replace('“', '"').replace('”', '"').replace('–', '-').replace('—', '-')
    lines = []
    for ln in s.split('\n'):
        ln = re.sub(r' {2,}', ' ', ln).strip()
        ln = re.sub(r' +([،؛:.)\]])', r'\1', ln)      # no space before Arabic comma, semicolon, colon, full stop, closer
        ln = re.sub(r'([(\[]) +', r'\1', ln)
        if ln:
            lines.append(ln)
    # an amending law's quotation marks around the new wording are not part of the article
    if lines and lines[0].startswith('"') and lines[0].count('"') % 2 == 1:
        lines[0] = lines[0][1:].lstrip()
    if lines and lines[-1].endswith('"') and lines[-1].count('"') % 2 == 1:
        lines[-1] = lines[-1][:-1].rstrip()
    return '\n'.join(lines) + '\n' if lines else ''


def unit_key(title, issuance=False):
    t = title.translate(AR_DIGITS)
    m = re.match(r'\s*مادة\s+(\d+)\s*(?:\((مكرر[اًً]*)(?:\s*/?\s*(\d+))?\))?', t)
    if not m:
        raise ValueError('unparsed article title: ' + title)
    n, bis, k = m.groups()
    key = ('isdar-%02d' if issuance else 'art-%03d') % int(n)
    label = ('مادة %s (إصدار)' if issuance else 'مادة %s') % n
    if bis:
        key += '-bis' + ('-%s' % k if k else '')
        label += ' (%s%s)' % (bis, (' ' + k) if k else '')
    return key, label


def day(s):
    return s[:10] if s else None


def add_month(d, months=1):
    y, m, dd = map(int, d.split('-'))
    m += months
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    dd = min(dd, calendar.monthrange(y, m)[1])
    return '%04d-%02d-%02d' % (y, m, dd)


def sha_of(url):
    return hashlib.sha256(open(fetch.path_for(url), 'rb').read()).hexdigest()


# In-force day: Constitution art. 142 (one month after gazette publication) unless the law fixes its own day.
OWN_RULE = {
    'd22cbd77-f94c-4894-b113-d96a51766d10': ('next-day', 'مادة 4: "ويُعمل به من اليوم التالي لتاريخ نشره في الجريدة الرسمية"'),
    'd8a3673d-24aa-4a2b-8d5e-3e844a3b51c3': ('2024-11-06', 'مادة 2: "يُعمل بالتعديلات الدستورية لسنة 2024 ... اعتباراً من تاريخ إعلان نتيجة الاستفتاء في 1446/05/04 هجرية، الموافق 2024/11/06 ميلادية"'),
    '415d8273-12e0-4e2c-aa02-5c0bf0a5c53c': ('+15', 'مادة 3 (إصدار): "ويعمل به بعد خمسة عشر يوماً من تاريخ نشره في الجريدة الرسمية"'),
    '8e6147cb-a8a8-4378-b59f-6f85d59b83f3': ('almeezan', 'the effective date Al Meezan records (the day after its publication in the Official Gazette); the Constitution was issued on 8 June 2004 and, by its promulgation, published a year later'),
}


# Al Meezan's record of the draft constitutional amendments (issued 2024-10-29, gazette issue 16 of 2024) is the same
# amendment text later approved by referendum; chains that name it are credited to the issued amendments (d8a3673d).
SAME_LAW = {'69c36fc9-930a-42bf-9086-c6b161cef4c3': 'd8a3673d-24aa-4a2b-8d5e-3e844a3b51c3'}


def law_key(d):
    if d['typeCode'] == 'constitution':
        return 'dustur-2004'
    if 'التعديلات الدستورية' in d['title']:
        return 'tadilat-dusturiya-2024'
    return 'law-%s-%s' % (d['year'], d['number'])


def law_entry(d, decisions):
    g = d.get('officialGazette') or {}
    pub = day(g.get('publishDate'))
    rule = OWN_RULE.get(d['id'])
    if rule is None:
        inforce = add_month(pub)
        how = 'Constitution art. 142 (one month after publication in the Official Gazette)'
    elif rule[0] == 'next-day':
        inforce = (datetime.date.fromisoformat(pub) + datetime.timedelta(days=1)).isoformat()
        how = "the law's own rule, " + rule[1]
    elif rule[0] == '+15':
        inforce = (datetime.date.fromisoformat(pub) + datetime.timedelta(days=15)).isoformat()
        how = "the law's own rule, " + rule[1]
    elif rule[0] == 'almeezan':
        inforce = day(d['effectiveDate'])
        how = rule[1]
    else:
        inforce = rule[0]
        how = "the law's own rule, " + rule[1]
    key = law_key(d)
    label = {'dustur-2004': 'الدستور الدائم لدولة قطر (2004)',
             'tadilat-dusturiya-2024': 'التعديلات الدستورية لسنة 2024'}.get(key, 'القانون رقم (%s) لسنة %s' % (d['number'], d['year']))
    decisions.append('%s: in force %s by %s; Al Meezan records issue %s, gazette %s (%s), effective %s.' % (
        key, inforce, how, day(d['publishDate']), pub, g.get('title'), day(d['effectiveDate'])))
    entry = {'label': label, 'title': d['title'],
             'kind': 'referendum' if key == 'tadilat-dusturiya-2024' else 'law',
             'enacted': day(d['publishDate']), 'published': pub,
             'url': SITE + d['legislationURL'], 'temporary_until': None, 'restores': None, 'note': None}
    if key == 'tadilat-dusturiya-2024':
        entry['note'] = ('Constitutional amendments approved in the referendum of 5 November 2024 and issued by the Amir; '
                         'in force from the announcement of the result on 6 November 2024 (art. 2).')
    return key, entry, inforce


def api_url(d):
    if d['typeCode'] == 'constitution':
        return fetch.API + '/Legislation/' + d['id']
    return fetch.API + '/Legislation/details-by-key?number=%s&year=%s&typeCode=%s&sourceCode=general' % (d['number'], d['year'], d['typeCode'])


def kind_of(key):
    return 'preamble' if key == 'preamble' else ('issuance' if key.startswith('isdar') else 'art')


def is_issuance(path):
    return bool(path and path[0].startswith('مواد الإصدار'))


def build_act(act, laws, law_inforce, decisions, problems):
    d = fetch.act_detail(act, offline=True)
    url = api_url(d)
    first_key, first_entry, first_day = law_entry(d, decisions)
    laws[first_key] = first_entry
    law_inforce[d['id']] = (first_key, first_day)

    def amender(r, field):
        lid = r.get(field + 'LegislationId')
        if not lid:
            return None
        lid = SAME_LAW.get(lid, lid)
        if lid not in law_inforce:
            k, e, f = law_entry(fetch.detail(lid, offline=True), decisions)
            laws[k] = e
            law_inforce[lid] = (k, f)
        return law_inforce[lid]

    units0, order, events = {}, [], []     # events: (day, key, (label, text) or None, law key)
    if d.get('description'):
        order.append('preamble')
        units0['preamble'] = ('الديباجة', clean(d['description']))
    tree = fetch.articles(d)
    have = {a['id'] for _, a in tree}
    for x in fetch.lookup(d['id'], offline=True):
        if x['id'] not in have:
            m = fetch.mada(d['id'], x['id'], offline=True)
            if not m.get('cancelationDate'):
                # an article Al Meezan's tree omits (Law 13/2016 arts 1-2, 23-32): a current article outside any chapter
                tree.append((None, m))
    tree.sort(key=lambda pa: (not is_issuance(pa[0]), unit_key(pa[1]['title'], is_issuance(pa[0]))[0]))
    current = {}
    for path, a in tree:
        key, label = unit_key(a['title'], is_issuance(path))
        if key in order:
            if path is None:
                continue
            problems.append('%s: duplicate unit %s' % (act['slug'], key))
            continue
        order.append(key)
        top = clean(a['description'])
        if 'ملغاة' not in a['title']:
            current[key] = top
        if not (a.get('hasHistory') or a.get('hasPreviousVersion')):
            units0[key] = (label, top)
            continue
        chain = sorted(fetch.mada(d['id'], a['id'], offline=True)['relatedAlmawad'], key=lambda r: r['chainPosition'] or 0)
        codes = [r['relationCode'] for r in chain]
        if codes == ['Addition']:
            k, f = amender(chain[0], 'parent')
            events.append((f, key, (label, top), k))
            continue
        if codes == ['Cancel']:
            units0[key] = (label, top)           # Al Meezan keeps the repealed wording as the article's text
            k, f = amender(chain[0], 'to')
            events.append((f, key, None, k))
            continue
        seen, kept = set(), []
        for r in chain:
            if r['relationCode'] == 'Amendment' or r.get('isLatest') or r is chain[-1]:
                if r['id'] not in seen:
                    seen.add(r['id'])
                    kept.append(r)
        dropped = [r for r in chain if r['id'] not in seen]
        if dropped:
            decisions.append('%s %s: dropped %d Al Meezan history entr%s with no relation, dated %s but carrying the current wording.' % (
                act['slug'], label, len(dropped), 'y' if len(dropped) == 1 else 'ies', day(dropped[0]['effectiveDate'])))
        if len(kept) < 2 or any(r['relationCode'] != 'Amendment' for r in kept[:-1]):
            problems.append('%s %s: unexpected history chain %s' % (act['slug'], key, codes))
        units0[key] = (label, clean(kept[0]['description']))
        for prev, r in zip(kept, kept[1:]):
            k, f = amender(prev, 'to') or amender(r, 'parent')
            events.append((f, key, (label, clean(r['description'])), k))
        if clean(kept[-1]['description']) != top:
            problems.append('%s %s: latest history entry differs from the current text' % (act['slug'], key))
    if d.get('description'):
        current['preamble'] = clean(d['description'])

    v0 = {k: {'label': units0[k][0], 'kind': kind_of(k), 'text': units0[k][1]} for k in order if k in units0}
    versions = [{'from': first_day, 'source_url': url, 'sha256': sha_of(url), 'units': v0, 'credits': {}}]
    state = dict(v0)
    for f in sorted({e[0] for e in events}):
        changes, credits = {}, {}
        for ef, key, val, lk in events:
            if ef != f:
                continue
            if val is None:
                changes[key] = None
                state.pop(key, None)
            else:
                u = {'label': val[0], 'kind': kind_of(key), 'text': val[1]}
                changes[key] = u
                state[key] = u
            credits.setdefault(key, [])
            if lk not in credits[key]:
                credits[key].append(lk)
        versions.append({'from': f, 'source_url': url, 'sha256': sha_of(url), 'changes': changes, 'credits': credits})
    mism = sorted(k for k in set(current) | set(state) if current.get(k) != (state.get(k) or {}).get('text'))
    if mism:
        problems.append('%s: final version differs from Al Meezan current text at %s' % (act['slug'], mism))
    return {'slug': act['slug'], 'short': act['short'], 'title': act.get('title') or d['title'],
            'url': SITE + d['legislationURL'], 'first_law': first_key, 'earlier_laws': [], 'versions': versions}


def main():
    acts_cfg = json.load(open(os.path.join(HERE, 'acts.json'), encoding='utf-8'))
    laws, law_inforce, decisions, problems = {}, {}, [], []
    acts = [build_act(a, laws, law_inforce, decisions, problems) for a in acts_cfg]
    nreq = sum(1 for _ in open(os.path.join(fetch.CACHE, 'requests.jsonl'), encoding='utf-8'))
    corpus = {
        'country': {
            'code': 'QA', 'name': 'Qatar', 'slug': 'qatar', 'lang': 'ar', 'tz': 'Asia/Qatar', 'future_branch': 'future',
            'publisher': {'name': 'Al Meezan (Ministry of Justice, State of Qatar)', 'email': 'almeezan@almeezan.invalid'},
            'default_in_force_rule': {
                'text': 'Constitution art. 142: "تنشر القوانين بعد المصادقة عليها وإصدارها في الجريدة الرسمية، وذلك خلال أسبوعين من تاريخ صدورها. ويعمل بها بعد شهر من تاريخ نشرها، ما لم ينص على تاريخ آخر في القانون ذاته." (Laws take effect one month after publication in the Official Gazette unless the law itself fixes another date.)',
                'source': 'https://almeezan.qa/legislations/constitution/2004/0/general'},
            'licence_note': 'Source: Al Meezan, Qatar Legal Portal, Ministry of Justice, State of Qatar (https://almeezan.qa).',
        },
        'sources': [{
            'name': 'Al Meezan, Qatar Legal Portal (Ministry of Justice)', 'url': 'https://almeezan.qa',
            'retrieved': RETRIEVED, 'requests': nreq,
            'licence': 'Official texts published by the Ministry of Justice of Qatar, credited to Al Meezan. The portal states no licence; see the README on copyright in official texts.',
            'notes': 'Public JSON API behind almeezan.qa (https://api.moj.gov.qa/api/v1, Accept-Language: ar): /Legislation/details-by-key (act with article tree), '
                     '/Legislation/{id}/almawad-lookup (all article ids), /Legislation/{id}/mada/{articleId} (each article\'s dated history chain, '
                     'naming the amending law and article), /Legislation/{id} (amending laws, with Official Gazette issue and date).'}],
        'laws': dict(sorted(laws.items())),
        'acts': acts,
        'applies': [],
        'decisions': [
            "Texts are Al Meezan's Arabic texts, which are authoritative; Al Meezan's English translations were not used.",
            "Versions are rebuilt from Al Meezan's per-article history chains (relatedAlmawad): the original wording, each replaced wording, and the amending law and article named for it. Unamended articles carry their current wording from the start.",
            "Every change is credited to the amending law Al Meezan names on the article's history entry (toLegislation / parentLegislation); nothing is credited by guess.",
            "In-force days come from the Official Gazette date Al Meezan records for each law, by Constitution art. 142 (one month after publication, the same day of the next month) unless the law fixes its own date. Al Meezan's per-article dates are the laws' issue dates and were not used.",
            "Repealed articles: Al Meezan keeps the repealed wording as the article's text and the repealing provision in its history; the article is removed on the repealing law's in-force day.",
            "Added articles (مكرر) take the wording Al Meezan shows for the article, from the adding law's in-force day.",
            "Text normalisation: HTML line breaks become lines; NBSP, RLM/LRM and tatweel removed; no space before Arabic punctuation; curly quotes and dashes unified; an amending law's quotation marks around a new wording dropped. Words and diacritics are untouched.",
            "Issuance articles (مواد الإصدار) of the Penal Code are units isdar-NN; each act's promulgation preamble is the unit 'preamble'.",
            "The constitutional amendments of 2024 are kind 'referendum': approved by referendum on 5 November 2024, in force on the announcement of the result, 6 November 2024 (their art. 2), and published in the Official Gazette on 31 December 2024.",
            "Al Meezan's history chains for constitution arts 1, 7, 13, 75 bis, 77-79, 82, 83, 125 and 150 name its record of the draft constitutional amendments of 2024 (69c36fc9, issued 2024-10-29, gazette 16 of 2024); they are credited to the issued amendments approved by referendum (d8a3673d) and dated 2024-11-06. To verify against both gazette texts.",
        ] + decisions + ['Open problem: ' + p for p in problems],
        'ai_use': ['None at data-build time: fetch.py and parse.py are deterministic code written with Claude Code (claude-opus-5-5); no model reads, writes, translates or summarises legal text.'],
    }
    tmp = os.path.join(HERE, 'corpus.json.tmp')
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(corpus, f, ensure_ascii=False, indent=1)
        f.write('\n')
    os.replace(tmp, os.path.join(HERE, 'corpus.json'))
    for a in acts:
        print(a['slug'], len(a['versions']), 'versions', [v['from'] for v in a['versions']], len(a['versions'][0]['units']), 'units')
    for p in problems:
        print('PROBLEM', p)


if __name__ == '__main__':
    main()
