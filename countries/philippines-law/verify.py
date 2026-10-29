"""Cross-check corpus.json against the Lawphil Project's copies (a cross-check only; never a text source).

    python -X utf8 verify.py           fetch the Lawphil pages once (cached in .cache/) and compare word sequences

For each act it compares the corpus text (all units, in order, headings removed) with the Lawphil page's text as
sequences of lowercase words, and prints every differing stretch. Lawphil is the Arellano Law Foundation's
unofficial copy; a difference is a lead to read the official page again, not a correction.
"""
from __future__ import annotations

import difflib
import hashlib
import html
import json
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
LAWPHIL = {
    'constitution': ('https://lawphil.net/consti/cons1987.html', 'PREAMBLE', 'Ratified'),
    'data-privacy-act': ('https://lawphil.net/statutes/repacts/ra2012/ra_10173_2012.html', 'Short Title', 'Approved,'),
}


def get(url: str) -> bytes:
    p = CACHE / hashlib.sha256(url.encode()).hexdigest()
    if p.exists():
        return p.read_bytes()
    time.sleep(1)
    r = subprocess.run(['curl', '-sS', '-L', '--compressed', '-A', UA, '--max-time', '60', url], capture_output=True)
    p.write_bytes(r.stdout)
    with open(CACHE / 'requests.jsonl', 'a', encoding='utf-8') as f:
        f.write(json.dumps({'url': url, 'bytes': len(r.stdout), 'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                            'via': 'verify.py'}) + '\n')
    return r.stdout


def words(s: str) -> list[str]:
    s = s.replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"')
    # Item numbers ("(1)", "a.") are typeset differently on the two sites, so bare numbers and single letters drop out.
    return [w for w in re.findall(r"[a-z0-9]+(?:'[a-z]+)?", s.lower()) if not w.isdigit() and len(w) > 1]


def main() -> int:
    corpus = json.loads((HERE / 'corpus.json').read_text(encoding='utf-8'))
    bad = 0
    for act in corpus['acts']:
        if act['slug'] not in LAWPHIL:
            continue
        url, start, stop = LAWPHIL[act['slug']]
        raw = get(url)
        try:
            t = raw.decode('utf-8')
        except UnicodeDecodeError:
            t = raw.decode('windows-1252', 'replace')
        t = html.unescape(re.sub(r'<[^>]+>', ' ', re.sub(r'<(script|style)\b.*?</\1>', '', t, flags=re.S | re.I)))
        i = t.find(start)
        j = t.find(stop, i)
        ref = words(t[i:j])
        units = act['versions'][-1]['units']
        ours = words('\n'.join('\n'.join(l for l in u['text'].splitlines() if not l.startswith('# ')) for u in units.values()))
        sm = difflib.SequenceMatcher(a=ours, b=ref, autojunk=False)
        diffs = [op for op in sm.get_opcodes() if op[0] != 'equal']
        print(f'{act["slug"]}: {len(ours)} words here, {len(ref)} on Lawphil, ratio {sm.ratio():.4f}, {len(diffs)} differing stretches')
        for tag, a1, a2, b1, b2 in diffs:
            print(f'  {tag:7} ours[{a1}]: {" ".join(ours[max(0,a1-4):a2+4])!r}\n          lawphil: {" ".join(ref[max(0,b1-4):b2+4])!r}')
        bad += len(diffs)
    return 0 if bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
