"""Read only .cache/ and write corpus.json (gitlaw_common SCHEMA.md).

Phase 1 so far: the Basic Law, 2002 -> Amended Basic Law 2003 -> 2005 amendment (replayed).
Every text is Al-Muqtafi's copy of the gazette text (getleg.asp?id=N, windows-1256 HTML).
"""
import hashlib, html, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fetch  # noqa: E402  (cache paths only; parse never touches the network)

LEG = 'http://muqtafi.birzeit.edu/pg/getleg.asp?id=%d'


def raw(id_):
    p = fetch.path_for(LEG % id_)
    b = open(p, 'rb').read()
    return b, hashlib.sha256(b).hexdigest()


def norm(s):
    s = html.unescape(re.sub(r'<[^>]+>', '\n', s)).replace('\xa0', ' ').replace('ـ', '')
    lines = [re.sub(r'[ \t]+', ' ', l).strip() for l in s.split('\n')]
    return '\n'.join(l for l in lines if l) + '\n'


def parse_leg(id_):
    b, sha = raw(id_)
    t = b.decode('cp1256')
    body = t.split('</H1>', 1)[1]
    units = {}
    first = re.search(r'<center>\s*<br />\s*<br />\s*<H3>|<FONT COLOR="BLACK"></FONT>\s*<A NAME=', body)
    pre = norm(body[:first.start()]) if first else ''
    pre = pre.split('\n', 1)[1] if pre.startswith('</center>') else pre
    pre = re.sub(r'^(?:\s*\n)*', '', pre)
    if pre.strip():
        units['preamble'] = {'label': 'Preamble', 'kind': 'preamble', 'text': pre}
    ch = 0
    for m in re.finditer(r'<H3>(.*?)</H3>|<A NAME="A\d+_[^"]*" />\s*<center>\s*<FONT COLOR="BLACK">\s*مادة\s*\(([^)]*)\)\s*</FONT>\s*</center>\s*<div>(.*?)</div>|<p>(.*?)</p>', body, flags=re.S):
        if m.group(1) is not None:
            ch += 1
            units['chapter-%02d' % ch] = {'label': 'Chapter %d' % ch, 'kind': 'heading', 'text': norm(m.group(1))}
        elif m.group(2) is not None:
            n = m.group(2).strip()
            mm = re.match(r'(\d+)\s*(مكرر)?', n)
            key = 'art-%03d' % int(mm.group(1)) + ('-bis' if mm.group(2) else '')
            units[key] = {'label': 'Art. %s' % n, 'kind': 'art', 'text': '# مادة (%s)\n' % n + norm(m.group(3))}
        else:
            units['promulgation'] = {'label': 'Promulgation', 'kind': 'promulgation', 'text': norm(m.group(4))}
    return units, sha


def between(text, a, b):
    i = text.index(a) + len(a)
    j = text.index(b, i) if b else len(text)
    return text[i:j].strip('\n:').strip() + '\n'


def basic_law():
    v2002, s2002 = parse_leg(14094)
    v2003, s2003 = parse_leg(14138)
    # 2005 amendment: replay its Art. 1-2 onto the 2003 text.
    b, s2005 = raw(14860)
    am = norm(b.decode('cp1256'))
    new36 = between(am, 'المادة (36)', 'المادة (47) بند 3:')
    new47_3 = between(am, 'المادة (47) بند 3:', 'المادة (48)')
    new48 = between(am, 'المادة (48)', 'المادة (55)')
    new55 = between(am, 'المادة (55)', 'مادة (2)')
    new47b = between(am, 'المادة (47) مكرر:', 'مادة (3)')
    v2005 = json.loads(json.dumps(v2003))
    v2005['art-036']['text'] = '# مادة (36)\n' + new36
    lines = v2005['art-047']['text'].split('\n')
    idx = [i for i, l in enumerate(lines) if l.startswith('3-')]
    assert len(idx) == 1
    lines[idx[0]] = '3- ' + new47_3.strip()
    v2005['art-047']['text'] = '\n'.join(lines)
    v2005['art-048']['text'] = '# مادة (48)\n' + new48
    v2005['art-055']['text'] = '# مادة (55)\n' + new55
    v2005['art-047-bis'] = {'label': 'Art. 47 bis', 'kind': 'art', 'text': '# مادة (47) مكرر\n' + new47b}

    def changed(a, b):
        return sorted(k for k in set(a) | set(b) if a.get(k, {}).get('text') != b.get(k, {}).get('text'))

    c2003 = changed(v2002, v2003)
    c2005 = changed(v2003, v2005)
    assert c2005 == ['art-036', 'art-047', 'art-047-bis', 'art-048', 'art-055'], c2005
    return {
        'slug': 'basic-law',
        'short': 'BL',
        'title': 'القانون الأساسي المعدل لسنة 2003م وتعديلاته (Amended Basic Law)',
        'url': LEG % 14138,
        'first_law': 'basic-law-2002',
        'earlier_laws': [],
        'versions': [
            {'from': '2002-07-07', 'source_url': LEG % 14094, 'sha256': s2002, 'units': v2002, 'credits': {},
             'note': 'Basic Law of 2002 as published in Al-Waqa\'i\' special issue of 7 July 2002 (Art. 112: in force on publication).'},
            {'from': '2003-03-19', 'source_url': LEG % 14138, 'sha256': s2003,
             'changes': {k: v2003.get(k) for k in c2003},
             'credits': {k: ['basic-law-2003'] for k in c2003},
             'note': 'Amended Basic Law of 2003, republished whole in the special issue of 19 March 2003 (Art. 121: in force on publication). Articles were renumbered, so many files change.'},
            {'from': '2005-08-18', 'source_url': LEG % 14860, 'sha256': s2005,
             'changes': {k: v2005.get(k) for k in c2005},
             'credits': {k: ['basic-law-2005'] for k in c2005},
             'note': 'Basic Law of 2005 amending Arts. 36, 47(3), 48 and 55 and adding Art. 47 bis, replayed onto the 2003 text (its Art. 3: in force on publication, issue 57 of 18 August 2005).'},
        ],
    }


def main():
    corpus = {
        'country': {
            'code': 'PS', 'name': 'Palestine', 'slug': 'palestine', 'lang': 'ar', 'tz': 'Asia/Hebron',
            'future_branch': 'future',
            'publisher': {'name': "Al-Muqtafi (Institute of Law, Birzeit University)", 'email': 'muqtafi@birzeit.invalid'},
            'default_in_force_rule': {
                'text': 'Amended Basic Law 2003, Art. 116: laws are published in the Official Gazette and take effect 30 days after publication unless the law provides otherwise',
                'source': LEG % 14138},
            'licence_note': "عن منظومة القضاء والتشريع في فلسطين - المقتفي -، اعداد معهد الحقوق في جامعة بيرزيت. (Al-Muqtafi, Institute of Law, Birzeit University; its pages state the material is copyrighted and may not be copied without permission. The law texts are the official gazette texts of Al-Waqa'i' al-Filastiniyya.)",
        },
        'sources': [
            {'name': "Al-Muqtafi gazette mirror (Al-Waqa'i' al-Filastiniyya)", 'url': 'http://muqtafi.birzeit.edu/pg/',
             'retrieved': '2026-10-29', 'requests': sum(1 for _ in open(os.path.join(fetch.CACHE, 'requests.jsonl'), encoding='utf-8')),
             'licence': 'Copyright Institute of Law, Birzeit University (stated on its pages); the underlying law texts are official gazette texts',
             'notes': 'HTTPS times out from the build machine; plain HTTP answers. Ministry of Justice and Diwan al-Fatwa wa al-Tashri sites did not answer.'},
        ],
        'laws': {
            'basic-law-2002': {'label': 'Basic Law 2002', 'title': 'القانون الأساسي لسنة 2002', 'kind': 'law',
                               'enacted': '2002-05-29', 'published': '2002-07-07', 'url': LEG % 14094,
                               'temporary_until': None, 'restores': None, 'note': None},
            'basic-law-2003': {'label': 'Amended Basic Law 2003', 'title': 'القانون الأساسي المعدل لسنة 2003', 'kind': 'law',
                               'enacted': '2003-03-18', 'published': '2003-03-19', 'url': LEG % 14138,
                               'temporary_until': None, 'restores': None, 'note': None},
            'basic-law-2005': {'label': 'Basic Law 2005', 'title': 'القانون الأساسي لسنة 2005م بتعديل بعض أحكام القانون الأساسي المعدل لسنة 2003م', 'kind': 'law',
                               'enacted': '2005-08-13', 'published': '2005-08-18', 'url': LEG % 14860,
                               'temporary_until': None, 'restores': None, 'note': None},
        },
        'acts': [basic_law()],
        'applies': [],
        'decisions': [
            'Al-Muqtafi serves each gazette text as published, not consolidated; the 2005 amendment is replayed onto the 2003 text by parse.py (Arts. 36, 47 item 3, 48, 55 replaced; 47 bis added).',
            'In-force dates come from each law\'s own clause (in force on publication): 2002-07-07, 2003-03-19, 2005-08-18, the gazette issue dates Al-Muqtafi lists.',
            'Chapter headings are kept as chapter-NN units, the promulgation formula as a promulgation unit; tatweel and NBSP are removed and spaces collapsed.',
            'Not yet verified against an official consolidated text (Al-Muqtafi\'s consolidated view needs a login), so no PUBLISH.',
        ],
        'ai_use': ['Claude Code (claude-opus-5-5) wrote fetch.py, index.py and parse.py; no model wrote or altered legal text.'],
    }
    out = os.path.join(HERE, 'corpus.json')
    tmp = out + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(corpus, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, out)
    a = corpus['acts'][0]
    print('versions', len(a['versions']), 'units v1', len(a['versions'][0]['units']),
          'changes', [len(v.get('changes', {})) for v in a['versions'][1:]])


if __name__ == '__main__':
    main()
