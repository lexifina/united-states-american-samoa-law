"""Add the UN Treaty Collection treaty-action act (slug un-treaties) to a country corpus.json. Usage: add_untc.py <country-folder> <UNTC state name>"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import p3_untc
d = Path(sys.argv[1]); state = sys.argv[2]
c = json.load(open(d / 'corpus.json', encoding='utf8'))
act, laws, src, n = p3_untc.treaties_act(state)
act['slug'] = 'un-treaties'
act['short'] = 'UN treaties'
act['title'] = f'Treaty actions of {state} on multilateral treaties deposited with the UN Secretary-General (UN Treaty Collection; no treaty text)'
c['acts'] = [a for a in c['acts'] if a['slug'] != 'un-treaties'] + [act]
c['laws'].update(laws)
if not any(s['name'].startswith('UN Treaty Collection') for s in c['sources']): c['sources'].append(src)
c['decisions'] = [x for x in c['decisions'] if not x.startswith('UN Treaty Collection')]
c['decisions'].append(f'UN Treaty Collection: {n} multilateral treaties deposited with the UN Secretary-General, with the state\'s signature, ratification, accession, succession, acceptance or approval dates. Facts only; one version per action date, with the first version credited to the action. Treaties outside the 78 status pages read are not listed.')
json.dump(c, open(d / 'corpus.json', 'w', encoding='utf8', newline='\n'), ensure_ascii=False, indent=1)
print(n, 'treaties,', len(act['versions']), 'versions')
