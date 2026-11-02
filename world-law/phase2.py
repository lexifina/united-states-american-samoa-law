"""Phase 2 helper: add one act to an existing country corpus.json, leaving every other act untouched."""
import json, hashlib
from pathlib import Path

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def add_act(country_dir, act, source, decisions, ai_use=None):
    p = Path(country_dir) / 'corpus.json'
    c = json.loads(p.read_text(encoding='utf-8'))
    before = json.dumps(c['acts'], ensure_ascii=False)
    c['acts'] = [a for a in c['acts'] if a['slug'] != act['slug']] + [act]
    assert json.dumps(c['acts'][:-1], ensure_ascii=False) == before or any(a['slug'] == act['slug'] for a in json.loads(before))
    c['sources'] = [s for s in c['sources'] if s['url'] != source['url']] + [source]
    for d in decisions:
        if d not in c['decisions']:
            c['decisions'].append(d)
    if ai_use:
        for d in ai_use:
            if d not in c['ai_use']:
                c['ai_use'].append(d)
    p.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
    return c
