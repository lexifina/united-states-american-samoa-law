"""Independent letters-and-digits check of a county Act's units against its PDF, read by a second engine
(pdftotext -raw). Private (gitlaw-scraper-dell, 2026-10-31).

    python -X utf8 check_letters.py <scripts/kenya-<county>-law/corpus.d/part.json> [...]

Each unit's lines (build labels "# ..." and the section headings parse.py set aside left out), word by word and reduced
to letters and digits, must be found in order in the PDF's text from the Act's title on. Between two words the source
may hold only page furniture: page numbers, the running heads and the section headings and margin notes. Anything else
is a mismatch, also any body text after the last word.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))


def ld(s: str) -> str:
    return ''.join(ch for ch in s if ch.isalnum())


def source(pdf: Path, first_page: int, end_page: int) -> str:
    out = subprocess.run(['pdftotext', '-raw', '-enc', 'UTF-8', '-f', str(first_page + 1), '-l', str(end_page), str(pdf), '-'],
                         capture_output=True).stdout
    return ld(out.decode('utf-8', 'replace'))


def furniture_only(gap: str, aside: list[str]) -> bool:
    for a in aside:
        if a:
            gap = gap.replace(a, '')
    return re.fullmatch(r'(\d{1,4})*', gap) is not None and len(gap) <= 8


def check_act(units: dict, S: str, aside_texts: list[str], headings: list[str]) -> tuple[bool, str]:
    aside = sorted({ld(a) for a in list(aside_texts) + list(headings) if ld(a)}, key=len, reverse=True)
    skip = set(headings)
    words = [w for u in units.values() for line in u['text'].split('\n')
             if line and not line.startswith('# ') and line not in skip for w in line.split() if ld(w)]
    if not words:
        return False, 'no words'
    # anchored on the first eight words, not a stray match; when the title row is split around the running head in
    # the source, anchor on the long title and look for each word of the title rows before it
    pos = -1
    for j in range(0, min(25, len(words))):
        pos = S.find(''.join(ld(w) for w in words[j:j + 8]))
        if pos >= 0:
            head = S[max(0, pos - 400):pos]
            if any(ld(w) not in head for w in words[:j]):
                return False, f'title words {words[:j]} not before the anchor'
            words = words[j:]
            break
    if pos < 0:
        return False, 'first words not in source'
    for w in words:
        t = ld(w)
        if S.startswith(t, pos):
            pos += len(t)
            continue
        skipped = True
        while skipped and not S.startswith(t, pos):
            skipped = False
            for a in aside:
                if S.startswith(a, pos):
                    pos += len(a)
                    skipped = True
                    break
            if not skipped:
                m = re.match(r'\d{1,4}', S[pos:])
                if m and S.startswith(t, pos + m.end()):
                    pos += m.end()
        if S.startswith(t, pos):
            pos += len(t)
            continue
        i = S.find(t, pos)
        if i < 0:
            return False, f'"{w}" not found after source position {pos}'
        if not furniture_only(S[pos:i], aside):
            return False, f'before "{w}" the source has "{S[pos:i][:80]}" that is not in the record'
        pos = i + len(t)
    if not furniture_only(S[pos:], aside):
        return False, f'source text after the last unit is not in the record: "{S[pos:pos + 80]}"'
    return True, 'ok'


def main(paths: list[str]) -> int:
    import pkmy_fetch as F
    import parse as P
    bad = n = 0
    for p in paths:
        part = json.loads(Path(p).read_text(encoding='utf-8'))
        for act in part['acts']:
            for v in act['versions']:
                pdf = F.path_for(v['source_url'])
                _, meta = P.parse(pdf)
                ok, msg = check_act(v['units'], source(pdf, meta['start_page'], meta['end_page']), meta['aside'], meta['headings'])
                n += 1
                if not ok:
                    bad += 1
                    print('MISMATCH', act['slug'], msg)
    print(f'{n} versions checked, {bad} mismatches')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main(sys.argv[1:]))
