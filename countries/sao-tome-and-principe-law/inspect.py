"""Diagnostics: list units whose last line lacks closing punctuation (a sign of leaked headings)."""
import json, re, sys
c = json.load(open('corpus.json', encoding='utf8'))
st = {}
for v in c['acts'][0]['versions']:
    if 'units' in v: st = dict(v['units'])
    else:
        for k, u in v['changes'].items():
            if u is None: st.pop(k, None)
            else: st[k] = u
    for k, u in sorted(st.items()):
        if k == 'estrutura': continue
        lines = u['text'].rstrip('\n').split('\n')
        last = lines[-1]
        if not re.search(r'[.;:!?»")]$', last) or len(lines) < 2:
            print(v['from'], k, '|', last[-90:])
