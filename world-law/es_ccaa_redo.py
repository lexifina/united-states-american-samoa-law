"""Re-parse an already published corpus.d part of a spain-<unit>-law after a parser fix, verify it in a scratch copy of
the unit folder, and only then replace the part in place (its PUBLISH stays, so main never loses the part).

    python -X utf8 scripts/world-law/es_ccaa_redo.py <unit> <part> <docs-date>
"""
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import es_ccaa as e  # noqa: E402

u, name, day = sys.argv[1:4]
real = e.folder(u)
scratch = e.DOCS / f'{e.repo_name(u)}-redo'
e._rm(scratch)
(scratch / 'corpus.d').mkdir(parents=True)
for p in (real / 'corpus.d').iterdir():
    if p.stem != name or p.suffix not in ('.json', '.PUBLISH'):
        if p.suffix in ('.json', '.PUBLISH'):
            shutil.copy2(p, scratch / 'corpus.d' / p.name)
orig = e.folder
e.folder = lambda unit: scratch if unit == u else orig(unit)
rep = e.parse_part(u, name, dict(e.plan(u))[name], day)
ok, line = e.verify_part(u, name, day)
e.folder = orig
if not ok:
    print('NOT VERIFIED', line)
    sys.exit(1)
new = scratch / 'corpus.d' / f'{name}.json'
tmp = real / 'corpus.d' / f'{name}.json.redo'
shutil.copy2(new, tmp)
(real / 'corpus.d' / f'{name}.PUBLISH').write_text(line + '\n', encoding='utf-8', newline='\n')
os.replace(tmp, real / 'corpus.d' / f'{name}.json')
e.write_docs(u, day)
e._rm(scratch)
print('REDONE', line)
