"""Fetch the pinned archive.org id_ captures this corpus is built from (resumable, cached, shared rate)."""
import sys, json
sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common')
import wayback
CACHE = r'C:/Users/alany/Documents/lexifina/scripts/sao-tome-and-principe-law/.cache'
PINS = json.load(open(r'C:/Users/alany/Documents/lexifina/scripts/sao-tome-and-principe-law/sources.json', encoding='utf-8'))['captures']
for p in PINS:
    b = wayback.get(p['url'], ts=p['ts'], cache=CACHE)
    print(p['name'], len(b) if b else None, flush=True)
    if b:
        open(CACHE + '/dl/' + p['name'], 'wb').write(b)
