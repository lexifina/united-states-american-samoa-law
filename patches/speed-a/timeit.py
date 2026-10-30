"""Wall-clock one command: python timeit.py <label> -- <cmd...>; appends a JSON line to times.jsonl."""
import json
import subprocess
import sys
import time

label = sys.argv[1]
cmd = sys.argv[sys.argv.index('--') + 1:]
t = time.perf_counter()
p = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
dt = time.perf_counter() - t
rec = {'label': label, 'seconds': round(dt, 2), 'rc': p.returncode, 'tail': (p.stdout or p.stderr)[-400:]}
with open('times.jsonl', 'a', encoding='utf-8') as f:
    f.write(json.dumps(rec) + '\n')
print(json.dumps(rec))
