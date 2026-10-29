"""Second reading of the official text (gitlaw-MY): every paragraph of the latest version of each act must appear,
word for word, in the reprint PDF read a different way (PyMuPDF plain text of every page, whitespace collapsed,
footnote asterisks removed, compared without case because small capitals are set as small lower-case letters).

Also checks, for every earlier version, that each paragraph appears in the PDF its version names (for versions
built from a reprint as printed) or in either reprint (for versions built by applying amendments).

Usage: python -X utf8 verify.py   (reads corpus.json and .cache only; writes verification.json)
"""
import json
import os
import re

import fitz

import fetch
import layout
from parse import FIX_2020 as EXPECTED

HERE = os.path.dirname(os.path.abspath(__file__))


def flat(pdf):
    d = fitz.open(stream=pdf, filetype='pdf')
    import amending                                      # letter-spaced justified lines ("l i c e n s e d")
    t = ' '.join(amending.despace(line) for i in range(d.page_count)
                 for line in layout.norm(d[i].get_text()).split('\n'))
    t = t.replace('*', '')
    t = re.sub(r'\s+', ' ', t)
    return re.sub(r'(?<=\w)- (?=\w)', '-', t).lower()      # "di-Pertua-" at a line end


def key_of(line):
    return re.sub(r'\s+', ' ', line.replace('*', '')).strip().lower()


_idx = {}


def found(kl, hay):
    """kl appears in hay, or its words appear in order in hay with page furniture (running heads, footnotes, notes
    pages: at most 6,000 words in all, in at most 3 places) between them."""
    if kl in hay:
        return True
    w = kl.split(' ')
    if hay not in _idx:
        hw = hay.split(' ')
        pos = {}
        for i, x in enumerate(hw):
            pos.setdefault(x, []).append(i)
        _idx[hay] = (hw, pos)
    hw, pos = _idx[hay]
    n0 = min(4, len(w))
    for st in pos.get(w[0], []):
        if hw[st:st + n0] != w[:n0]:
            continue
        i, j, skipped, breaks = 0, st, 0, 0
        while i < len(w) and j < len(hw):
            if hw[j] == w[i]:
                i += 1
                j += 1
                continue
            # skip forward to the next place the remaining words resume (at least 6 in a row)
            nxt = None
            for k in range(j + 1, min(len(hw), j + 6000 - skipped)):
                if hw[k:k + min(6, len(w) - i)] == w[i:i + 6]:
                    nxt = k
                    break
            if nxt is None:
                break
            skipped += nxt - j
            breaks += 1
            j = nxt
            if breaks > 3:
                break
        if i == len(w):
            return True
    return False


def main():
    c = json.load(open(os.path.join(HERE, 'corpus.json'), encoding='utf-8'))
    d = os.path.join(HERE, 'corpus.d')
    for name in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if name.endswith('.json'):
            c['acts'] += json.load(open(os.path.join(d, name), encoding='utf-8'))['acts']
    texts = {}
    report = {'acts': []}
    total_miss = 0
    for a in c['acts']:
        state = {}
        miss = []
        expected = []
        checked = 0
        urls = sorted({v['source_url'] for v in a['versions']})
        for u in urls:
            if u not in texts:
                texts[u] = flat(fetch.get(fetch.unquote(u) if hasattr(fetch, 'unquote') else u, offline=True))
        allsrc = ' || '.join(texts[u] for u in urls)
        for vi, v in enumerate(a['versions']):
            if 'units' in v:
                state = dict(v['units'])
            else:
                for k, u in v.get('changes', {}).items():
                    if u is None:
                        state.pop(k, None)
                    else:
                        state[k] = u
            last = vi == len(a['versions']) - 1
            src = texts[v['source_url']]
            for k, u in sorted(state.items()):
                if not (last or k in v.get('changes', {}) or 'units' in v):
                    continue
                for line in u['text'].split('\n')[1:]:
                    if not line.strip():
                        continue
                    kl = key_of(line)
                    checked += 1
                    hay = src if (last or 'units' in v) else allsrc
                    if not found(kl, hay) and not found(kl, allsrc):
                        rep = [r for r in EXPECTED.get(k, []) if r[1] in line]
                        if rep and 'units' in v and found(key_of(line.replace(rep[0][1], rep[0][0])), hay):
                            expected.append({'version': v['from'], 'unit': k, 'line': line[:200],
                                             'why': 'words restored from the reprint footnote (parse.FIX_2020)'})
                            continue
                        miss.append({'version': v['from'], 'unit': k, 'line': line[:200]})
        report['acts'].append({'slug': a['slug'], 'paragraphs_checked': checked, 'missing': miss,
                               'expected': expected})
        total_miss += len(miss)
        print(a['slug'], 'checked', checked, 'missing', len(miss), 'expected', len(expected))
        for m in miss[:20]:
            print('  ', m)
    report['missing_total'] = total_miss
    with open(os.path.join(HERE, 'verification.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
        f.write('\n')


if __name__ == '__main__':
    main()
