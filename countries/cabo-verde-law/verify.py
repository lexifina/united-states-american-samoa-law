"""Checks on the parsed corpus that need no network: unit text sanity, and the 2010 republication against the
Assembleia Nacional's own 4th edition of the Constitution (2010), which says it includes the rectification in
BO I Série nº 28, 26 Jul 2010.

    python -X utf8 scripts/cabo-verde-law/verify.py
"""
import difflib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import parse  # noqa: E402


def state(act, upto=None):
    units = {}
    for v in act['versions']:
        if upto and v['from'] > upto:
            break
        if 'units' in v:
            units = dict(v['units'])
        for k, u in (v.get('changes') or {}).items():
            if u is None:
                units.pop(k, None)
            else:
                units[k] = u
    return units


LETTERS = 'abcdefghijklmnopqrstuvwxyz'


def sequence_breaks(text: str) -> list[str]:
    """Inside one article, the numbers ("1.", "2.") and the alíneas ("a)", "b)") that open its lines must run in
    order, alíneas restarting under each number. A break is how a reading-order fault shows up (an alínea of one
    article landing in another). Letters follow the Portuguese alphabet with k, w, y (a, b, ..., j, k, l)."""
    out = []
    num, let = 0, -1
    for l in text.splitlines()[1:]:
        m = re.match(r'^(\d+)\. ', l)
        if m:
            n = int(m.group(1))
            if n != num + 1:
                out.append(f'number {n} after {num or "none"}')
            num, let = n, -1
            continue
        m = re.match(r'^([a-z])\) ', l)
        if m:
            i = LETTERS.index(m.group(1))
            if i != let + 1:
                out.append(f'alínea {m.group(1)}) after {LETTERS[let] + ")" if let >= 0 else "none"} (under {num or "-"})')
            let = i
    return out


def main():
    corpus = json.loads((HERE / 'corpus.json').read_text(encoding='utf-8'))
    report = {}
    for act in corpus['acts']:
        for v in act['versions']:
            st = state(act, v['from'])
            odd = []
            seq = {}
            for k, u in st.items():
                for i, l in enumerate(u['text'].splitlines()[1:], 2):
                    if u['kind'] == 'art' and not re.search(r'[.;:!?)"…]$', l):
                        odd.append(f'{k}:{i}: {l[-60:]}')
                if u['kind'] == 'art' and sequence_breaks(u['text']):
                    seq[k] = sequence_breaks(u['text'])
            report[f"{act['slug']}@{v['from']}"] = {'no_final_punctuation': odd, 'sequence_breaks': seq}
            print(act['slug'], v['from'], len(st), 'units;', len(odd), 'lines without final punctuation;',
                  len(seq), 'articles whose numbers/alíneas break sequence')
            for o in odd[:12]:
                print('   ', o)
            for k, s in seq.items():
                print('    seq', k, s)
    json.dump(report, open(HERE / '.tmp' / 'verify-lines.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()


def an_edition_articles():
    """Articles of the Assembleia Nacional's 4th edition (2010) as word lists."""
    lines = parse.clean_lines(parse.pdf_text(parse.URL['an-2010'], columns=False))
    lines = [l for l in lines if not re.match(r'^(2010 )?CONSTITUIÇÃO DA REPÚBLICA DE CABO VERDE( 2010)?$', l)]
    s = next(i for i, l in enumerate(lines) if l.startswith('A proclamação da Independência'))
    e = max(i for i, l in enumerate(lines) if l.startswith('ANEXOS'))
    arts, cur = {}, None
    for l in lines[s:e]:
        m = re.match(r'^Artigo\s+(\d+)\s*º\s*(?:-\s*([A-Z]))?\s*(\(.*)?$', l)
        if m:
            cur = parse.art_key(m.group(1), m.group(2))
            arts[cur] = [m.group(3) or '']
        elif cur and not parse.HEAD.match(l):
            arts[cur].append(l)
    out = {}
    for k, v in arts.items():
        t = ' '.join(v)
        t = re.sub(r'(2010 )?CONSTITUIÇÃO DA REPÚBLICA DE CABO VERDE( 2010)?', ' ', t)
        t = re.sub(r'(\w)- (\w)', r'', t)
        out[k] = fold(t)
    return out


def fold(t):
    t = t.lower().replace('-', '')
    return re.sub(r'[^\w\s]', ' ', t).split()


def words(text):
    return fold(' '.join(text.splitlines()[0].split(' ', 3)[3:] + text.splitlines()[1:]))


def compare_an(corpus):
    act = next(a for a in corpus['acts'] if a['slug'] == 'constituicao')
    st = state(act)
    an = an_edition_articles()
    keys = sorted(k for k in st if k.startswith('art-'))
    print('2010 BO articles', len(keys), '; AN edition articles', len(an))
    diffs = {}
    for k in keys:
        a, b = words(st[k]['text']), an.get(k, [])
        if a != b:
            sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
            ops = [(t, ' '.join(a[i1:i2]), ' '.join(b[j1:j2])) for t, i1, i2, j1, j2 in sm.get_opcodes() if t != 'equal']
            diffs[k] = ops
    print('articles differing word-for-word:', len(diffs))
    for k, ops in diffs.items():
        print(' ', k, ops[:4])
    return diffs


if __name__ == '__main__' and '--an' in sys.argv:
    compare_an(json.loads((HERE / 'corpus.json').read_text(encoding='utf-8')))
