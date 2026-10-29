"""Check corpus.json against the official MJLA PDFs. Cache only; writes verification.json.

The MJLA PDFs' text layer keeps every Arabic letter but not their order inside ligatures (لم comes out as مل,
لأ as األأ), adds stray marks (6س, 8ص, |ص, {ش, z) and reverses some digit runs. So the check is on letters, not
words: for each article, the multiset of its letters (alef forms and digits left out, ى/ي folded) must equal that of
some contiguous run of letters in the PDF. A changed, added or dropped letter anywhere in the article fails it.
Usage: python -X utf8 verify.py
"""
import json, os, random, re
import numpy as np
import fitz
import fetch

HERE = os.path.dirname(os.path.abspath(__file__))
PDF = {
    'nizam-asasi': 'https://www.mjla.gov.om/images/laws/file/Book871678.pdf',
    'qanun-al-jaza': 'https://www.mjla.gov.om/images/laws/file/Book285100.pdf',
    'himayat-al-bayanat': 'https://www.mjla.gov.om/images/laws/file/Book591474.pdf',
}
LETTERS = 'بتثجحخدذرزسشصضطظعغفقكلمنهوي' + 'ةءؤئ'
rng = random.Random(20261029)
WEIGHT = {c: rng.getrandbits(62) for c in LETTERS}


def letters(s):
    s = s.replace('ى', 'ي').replace('ﻻ', 'ل')
    return [c for c in s if c in WEIGHT]


def pdf_stream(url):
    d = fitz.open(fetch.path_for(url))
    return letters('\n'.join(p.get_text() for p in d))


def found(stream_prefix, unit_letters):
    n = len(unit_letters)
    if n == 0 or n >= len(stream_prefix):
        return False
    target = np.uint64(sum(WEIGHT[c] for c in unit_letters) % (1 << 64))
    win = stream_prefix[n:] - stream_prefix[:-n]
    return bool(np.any(win == target))


def states(act):
    st, out = {}, []
    for v in act['versions']:
        if 'units' in v:
            st = dict(v['units'])
        for k, u in (v.get('changes') or {}).items():
            if u is None:
                st.pop(k, None)
            else:
                st[k] = u
        out.append((v['from'], dict(st)))
    return out


def main():
    corpus = json.load(open(os.path.join(HERE, 'corpus.json'), encoding='utf-8'))
    report = {'method': __doc__.split('Usage')[0].strip(), 'acts': {}}
    lines = []
    for act in corpus['acts']:
        url = PDF[act['slug']]
        s = pdf_stream(url)
        w = np.array([0] + [WEIGHT[c] for c in s], dtype=np.uint64)
        pre = np.cumsum(w, dtype=np.uint64)
        per = []
        for day, st in states(act):
            arts = {k: u for k, u in st.items() if k.startswith('art-')}
            ok = sorted(k for k, u in arts.items() if found(pre, letters(u['text'])))
            per.append({'version': day, 'articles': len(arts), 'match': len(ok),
                        'unmatched': sorted(set(arts) - set(ok))})
        best = max(per, key=lambda r: (r['match'] / max(r['articles'], 1), r['version']))
        report['acts'][act['slug']] = {'pdf': url, 'sha256': __import__('hashlib').sha256(fetch.get(url, offline=True)).hexdigest(),
                                       'pdf_letters': len(s), 'per_version': per, 'pdf_is': best['version']}
        lines.append('%s: MJLA PDF matches the version of %s (%d of %d articles letter for letter; unmatched %s)' % (
            act['slug'], best['version'], best['match'], best['articles'], ', '.join(best['unmatched']) or 'none'))
    report['summary'] = ' '.join(lines)
    with open(os.path.join(HERE, 'verification.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print('\n'.join(lines))
    for a, r in report['acts'].items():
        for p in r['per_version']:
            print('  ', a, p['version'], p['match'], '/', p['articles'], p['unmatched'][:12])


if __name__ == '__main__':
    main()
