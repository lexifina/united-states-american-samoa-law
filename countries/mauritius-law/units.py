"""Splits a Revised Laws of Mauritius text into units (one file per section or schedule).

    units, notes = revised_units(pdf, start=r'^1\\. The State$', stop=r'^LAWS RELATED TO THE CONSTITUTION$')
"""
from __future__ import annotations

import re
from pathlib import Path

import revised as R

ORDINALS = ['FIRST', 'SECOND', 'THIRD', 'FOURTH', 'FIFTH', 'SIXTH', 'SEVENTH', 'EIGHTH', 'NINTH', 'TENTH',
            'ELEVENTH', 'TWELFTH']
SCHED = re.compile(r'^(?:(' + '|'.join(ORDINALS) + r') )?SCHEDULE(?: \((?:section|sections|s\.)[^)]*\))?$', re.I)


def revised_units(pdf: Path, start: str, stop: str | None, width: int = 3,
                  heading_rx: str = r'^(?:CHAPTER|PART|BOOK|TITLE|SUB-?PART|SECTION|§|PARAGRAPH)\b') -> tuple[dict, list]:
    lines = R.lines_of(pdf)
    paras = R.paragraphs(lines)
    dh = R.Dehyphen(paras)
    texts = [(dh.join(p['lines']), p) for p in paras]
    i0 = next(i for i, (t, p) in enumerate(texts) if p['bold'] and re.match(start, t))
    units: dict[str, dict] = {}
    notes: list[tuple[str, str]] = []
    cur = None
    sched_mode = False
    for t, p in texts[i0:]:
        if stop and re.match(stop, t):
            break
        if R.NOTE.match(t) or (t.startswith('[') and t.endswith(']')):
            notes.append((cur, t))
            continue
        if p['bold']:
            m = SCHED.match(t)
            if m and 'continued' not in t.lower():
                n = ORDINALS.index(m.group(1).upper()) + 1 if m.group(1) else 1
                cur = f'sch-{n:02d}'
                units[cur] = {'label': (m.group(1).title() + ' Schedule') if m.group(1) else 'Schedule',
                              'kind': 'schedule', 'lines': [f'# {t.title() if t.isupper() else t}']}
                sched_mode = True
                continue
            if re.search(r'SCHEDULE\s*—\s*continued', t, re.I):
                continue
            if not sched_mode:
                rng = R.SECTION_RANGE.match(t)
                if rng:
                    cur = None   # "14. – 36. --": repealed run, no text
                    continue
                m = R.SECTION.match(t)
                if m:
                    num, head = m.group(1), m.group(2).strip()
                    if head in ('—', '', '-'):
                        cur = None  # repealed section left as a number only
                        continue
                    cur = 's-' + R.key_num(num, width)
                    if cur in units:
                        cur = cur + '-dup'
                    units[cur] = {'label': f's. {num}', 'kind': 'section', 'lines': [f'# {num}. {head}']}
                    continue
                if re.match(heading_rx, t) or t.isupper():
                    continue  # Chapter, Part, Book headings: structure, not a provision
        if cur is None:
            continue
        units[cur]['lines'].append(t)
    out = {}
    for k, u in units.items():
        out[k] = {'label': u['label'], 'kind': u['kind'], 'text': '\n'.join(u['lines']) + '\n'}
    return out, notes
