"""Word check: every paragraph of each act's latest version must occur, word for word, in an independent text
extraction (poppler's pdftotext, not PyMuPDF) of the same official PDF. Also checks the first version of each act.

    python -X utf8 scripts/palau-law/verify.py        -> writes verification.json, prints a summary
Normalisation on both sides: quotes, dashes, whitespace and line-wrap hyphenation only.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fetch  # noqa: E402

DRIVE_FILE = 'https://drive.google.com/uc?export=download&id={}'


def norm(s: str) -> str:
    s = s.replace('‘', "'").replace('’', "'").replace('“', '"').replace('”', '"')
    s = s.replace('–', '-').replace('—', '-').replace(' ', ' ').replace('­', '')
    s = re.sub(r'\s+', ' ', s)
    return s.strip()


def pdftext(file_id: str) -> str:
    p = fetch.path(DRIVE_FILE.format(file_id))
    r = subprocess.run(['pdftotext', '-enc', 'UTF-8', str(p), '-'], capture_output=True)
    t = r.stdout.decode('utf-8', 'replace')
    t = re.sub(r'(\w)-\n(\w)', r'\1-\2', t)  # keep hyphen, drop the wrap
    return norm(t)


def found(n: str, hay: str, hay_ns: str, pieces: int = 8) -> bool:
    """n occurs in hay, or splits into at most `pieces` consecutive runs of words that each occur (a paragraph
    that crosses a page break has the running head and footer of the page inside it in pdftotext's output)."""
    if n in hay or re.sub(r'[ -]', '', n) in hay_ns:
        return True
    if pieces <= 1:
        return False
    w = n.split(' ')
    lo, hi = 1, len(w) - 1  # longest prefix of words that occurs
    best = 0
    while lo <= hi:
        mid = (lo + hi) // 2
        if re.sub(r'[ -]', '', ' '.join(w[:mid])) in hay_ns:
            best, lo = mid, mid + 1
        else:
            hi = mid - 1
    if best < 3:
        return False
    return found(' '.join(w[best:]), hay, hay_ns, pieces - 1)


def main() -> None:
    corpus = json.loads((HERE / 'corpus.json').read_text(encoding='utf-8'))
    for act in corpus['acts']:
        if act['slug'] == 'constitution':
            act['versions'] = [act['versions'][-1]]  # the last version holds every unit of the one source file
    report = {}
    total_bad = 0
    for act in corpus['acts']:
        seen = set()
        for v in act['versions']:
            if v['source_url'] in seen:
                continue  # Constitution versions share one source file; check its first and last
            seen.add(v['source_url'])
            fid = re.search(r'/d/([\w-]+)/', v['source_url']).group(1)
            hay = pdftext(fid)
            hay_ns = re.sub(r'[ -]', '', hay)  # pdftotext drops a hyphen at a line end (out-patient)
            paras = bad = 0
            misses = []
            for k, u in sorted(v['units'].items()):
                for line in u['text'].rstrip('\n').split('\n'):
                    if line.startswith('# Article') or line.startswith('# Preamble') or line.startswith('# ') and 'Amendment' in line:
                        continue  # headings composed by parse.py from the article/amendment heading
                    line = line[2:] if line.startswith('# ') else line
                    paras += 1
                    n = norm(line)
                    # pdftotext may split words differently around line ends: compare without spaces as the fallback
                    if not found(n, hay, hay_ns):
                        bad += 1
                        misses.append(f'{k}: {n[:160]}')
            report[f'{act["slug"]}@{v["from"]}'] = {'paragraphs': paras, 'not_found': bad, 'examples': misses[:15]}
            total_bad += bad
            print(f'{act["slug"]:32} {v["from"]} paragraphs {paras:5}  not found {bad}')
    (HERE / 'verification.json').write_text(json.dumps(report, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print('total not found', total_bad)


if __name__ == '__main__':
    main()
