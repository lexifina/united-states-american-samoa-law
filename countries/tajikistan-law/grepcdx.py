import json, sys, hashlib, re
from pathlib import Path
C = Path(__file__).parent / '.cache'
for line in open(C/'requests.jsonl', encoding='utf-8'):
    d = json.loads(line)
    if 'cdx/search' not in d['url'] or d['status'] != 200 or sys.argv[1] not in d['url']: continue
    h = hashlib.sha256(d['url'].encode()).hexdigest()
    fs = [p for p in C.iterdir() if p.name.startswith(h)]
    if not fs: continue
    rows = json.loads(fs[0].read_bytes())[1:]
    pat = re.compile(sys.argv[2], re.I)
    for r in rows:
        if pat.search(r[1]) or (len(sys.argv) > 3 and r[2] in sys.argv[3].split(',')): print(*r)
