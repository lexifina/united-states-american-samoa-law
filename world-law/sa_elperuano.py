"""El Peruano search (busquedas.elperuano.pe) pages -> hits, for the Peruvian regional units (gitlaw-scraper-dell).
The page data is a React Router turbo-stream: a flat JSON array in which objects are {"_<key index>": <value index>}.
Private (world-law-ops only)."""
from __future__ import annotations

import json
import re

UNDEF = {-5: None, -7: None, -1: None}


def stream(s: str) -> list:
    out = []
    for m in re.finditer(r'streamController\.enqueue\((".*?")\);?</script>', s, re.S):
        chunk = json.loads(m.group(1))
        for line in chunk.splitlines():
            line = line.strip()
            if line.startswith('['):
                out.append(json.loads(line))
    return out


def decode(arr: list):
    memo = {}

    def val(i):
        if isinstance(i, int) and i < 0:
            return UNDEF.get(i)
        if i in memo:
            return memo[i]
        x = arr[i]
        if isinstance(x, dict):
            o = {}
            memo[i] = o
            for k, v in x.items():
                o[arr[int(k[1:])]] = val(v)
            return o
        if isinstance(x, list):
            o = []
            memo[i] = o
            o.extend(val(v) for v in x)
            return o
        return x
    return val(0)


def page(s: str) -> dict:
    chunks = stream(s)
    if not chunks:
        return {}
    root = decode(chunks[0])
    ld = root.get('loaderData') or {}
    return ld.get('routes/_index') or {}


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    d = page(open(sys.argv[1], encoding='utf-8').read())
    r = d.get('results') or {}
    print(json.dumps({k: v for k, v in r.items() if k != 'hits' and k != 'entities'}, ensure_ascii=False)[:500])
    for h in (r.get('hits') or [])[:int(sys.argv[2]) if len(sys.argv) > 2 else 5]:
        print(json.dumps(h, ensure_ascii=False)[:800])
