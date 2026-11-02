"""Parse and letters-check every catalogued Act of the given counties. Private."""
import sys, json
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE))
import pkmy_fetch as f, parse as P, check_letters as C
for c in sys.argv[1:]:
    for it in json.load(open(HERE.parent / '.lk-ke-ph' / 'ke' / f'{c}.catalogue.json', encoding='utf-8')):
        p = f.path_for(it['url']); name = (it['url'].split('/')[-1] or it['url'].split('/')[-3])[:50]
        try:
            u, m = P.parse(p)
        except Exception as e:
            print(f'{c:12} {name:50} PARSE {e}'); continue
        ok, msg = C.check_act(u, C.source(p, m['start_page'], m['end_page']), m['aside'], m['headings'])
        print(f"{c:12} {name:50} secs={m['sections']:3} sch={sum(1 for k in u if k.startswith('sch'))} A={m['assent']} C={m['commencement']} G={m['gazette_date']} {'OK' if ok else 'BAD ' + msg[:120]}")
