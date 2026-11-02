"""Phase 2 helper: refresh the 'What is in it now' table in scripts/<slug>-law/repo/README.md and the 'build' line of
repo/jurisdiction.json from corpus.json. Usage: phase2_docs.py <slug> "<history text for the table>" [intro sentence]"""
import json, re, sys
from pathlib import Path
slug, hist = sys.argv[1], sys.argv[2]
intro = sys.argv[3] if len(sys.argv) > 3 else None
root = Path(__file__).resolve().parent.parent / (slug + '-law')
corpus = json.loads((root / 'corpus.json').read_text(encoding='utf-8'))
rd = root / 'repo' / 'README.md'
t = rd.read_text(encoding='utf-8')
rows = ['| Folder | Act | Versions | History |', '| --- | --- | ---: | --- |']
for a in corpus['acts']:
    h = hist if a['slug'] != corpus['acts'][0]['slug'] else None
    old = re.search(r'\| `%s/` \|[^\n]*' % re.escape(a['slug']), t)
    if old:
        rows.append(old.group(0))
    else:
        rows.append('| `%s/` | %s | %d | %s |' % (a['slug'], a['title'], len(a['versions']), hist))
tbl = '\n'.join(rows)
t = re.sub(r'\| Folder \| Act \|[^\n]*\n\| --- [^\n]*\n(?:\|[^\n]*\n?)+', tbl + '\n', t, count=1)
if intro:
    t = re.sub(r'This is a first build:[^\n]*', intro, t, count=1)
rd.write_text(t, encoding='utf-8', newline='\n')
jd = root / 'repo' / 'jurisdiction.json'
j = json.loads(jd.read_text(encoding='utf-8'))
j['build'] = 'built: ' + '; '.join('%s (%d version%s)' % (a['title'], len(a['versions']), '' if len(a['versions']) == 1 else 's') for a in corpus['acts'])
j['sources'] = len(corpus['sources'])
jd.write_text(json.dumps(j, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
