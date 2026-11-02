"""Private (never published): python br_city_years.py <folder>; prints the years whose every listed law PDF is in the cache (or answered 404)."""
import hashlib, json
from pathlib import Path
import sys
H = Path(sys.argv[1]).resolve()
idx = json.loads((H / '.cache' / 'index.json').read_text(encoding='utf-8'))
raw = H / '.cache' / 'www' / 'raw'
ys = {}
for e in idx.values():
    if e.get('date'):
        p = raw / hashlib.sha256(e['url'].encode()).hexdigest()
        ys.setdefault(e['date'][:4], []).append(p.exists() or Path(str(p) + '.404').exists() or Path(str(p) + '.500').exists())
print(' '.join(y for y in sorted(ys) if all(ys[y])))
