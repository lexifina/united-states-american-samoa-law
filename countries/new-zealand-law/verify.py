"""Checks corpus.json against the official text, per act, and writes verification.json.

1. The newest archived `latest` page of the act (the current official consolidation when it was captured) must state
   the same "as at" date as the act's last version, and no archived page may state a later date.
2. The act replayed version by version from corpus.json must equal that newest page, unit by unit, exactly (after
   the same typesetting normalisation parse.py applies).
3. Every version must come from a cached source whose sha256 matches.

    python -X utf8 verify.py [corpus.json]
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import parse

HERE = Path(__file__).resolve().parent


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / 'corpus.json'
    corpus = json.loads(path.read_text(encoding='utf-8'))
    caps = json.loads((HERE / 'captures.json').read_text(encoding='utf-8'))
    out = {}
    for a in corpus['acts']:
        state = {}
        for v in a['versions']:
            raw = parse.cache_path(v['source_url']).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == v['sha256'], v['source_url']
            if 'units' in v:
                state = dict(v['units'])
            for k, u in (v.get('changes') or {}).items():
                if u is None:
                    state.pop(k, None)
                else:
                    state[k] = u
        last = a['versions'][-1]['from']
        rows = [c for c in caps[a['slug']] if c.get('as_at')]
        newest = max((c for c in rows if c['kind'].endswith('latest')), key=lambda c: c['timestamp'])
        latest_date = max(c['as_at'] for c in rows)
        page = parse.parse_page(parse.cache_path(
            f'https://web.archive.org/web/{newest["timestamp"]}id_/{newest["url"]}').read_bytes())['units']
        diff = sorted(k for k in set(page) | set(state)
                      if (page.get(k) or {}).get('text') != (state.get(k) or {}).get('text'))
        ok = newest['as_at'] == last == latest_date and not diff
        out[a['slug']] = {'last_version': last, 'newest_capture': newest['timestamp'], 'newest_url': newest['url'],
                          'newest_states': newest['as_at'], 'units': len(state), 'unit_mismatches': diff, 'ok': ok}
        print(a['slug'], 'OK' if ok else 'FAIL', out[a['slug']])
    (path.parent / 'verification.json').write_text(json.dumps(out, indent=1) + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
