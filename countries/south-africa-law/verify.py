"""Checks today's text in corpus.json against the latest official consolidation, word by word.

    python -X utf8 scripts/south-africa-law/verify.py [corpus.json]

POPIA: every section of the last version against the Department of Justice consolidation (2013-004.pdf).
Constitution: every section and schedule of the last version against the Department of Justice consolidation
(SAConstitution-web-eng.pdf, up to the 17th Amendment) with the 18th Amendment applied (constitution.py).
Writes verification.json beside this file.
"""
from __future__ import annotations

import difflib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import fetch  # noqa: E402


def words(s: str) -> list[str]:
    s = s.replace('­', '').replace('ﬁ', 'fi').replace('ﬂ', 'fl')
    s = re.sub(r'[‘’“”"\'`]', '', s)
    s = re.sub(r'[—–-]', ' ', s)
    s = re.sub(r'[^\w\s()\[\].,;:]', ' ', s)
    s = re.sub(r'([(),;:\[\]])', r' \1 ', s)
    s = re.sub(r'\.(?=\s|$)', ' . ', s)
    ws = [w.lower() for w in s.split()]
    # "Act No. 2 of 2000" (gazette) and "Act 2 of 2000" (Juta/DoJ house style) are the same citation
    return [w for i, w in enumerate(ws) if not (w == 'no' and i + 2 < len(ws) and ws[i + 1] == '.' and ws[i + 2][:1].isdigit())
            and not (w == '.' and i and ws[i - 1] == 'no' and i + 1 < len(ws) and ws[i + 1][:1].isdigit())]


def pdf_text(url: str) -> str:
    import fitz
    doc = fitz.open(stream=fetch.fetch(url, offline=True), filetype='pdf')
    return '\n'.join(p.get_text() for p in doc)


def popia_reference() -> dict[str, list[str]]:
    t = pdf_text('https://www.justice.gov.za/legislation/acts/2013-004.pdf')
    t = re.sub(r'© \d{4} Juta and Company \(Pty\) Ltd\.\nDownloaded:[^\n]*\n', '\n', t)
    t = re.sub(r'\n\d+\n(?=©|\n)', '\n', t)
    t = re.sub(r'\[Date of commencement[^\]]*\]', '', t)
    t = re.sub(r'\n +\d+ +[^\n]*\n(?:[^\n]*\(Proc[^\n]*\)\n)?', '\n', t)       # Juta footnotes
    body = t[t.index('CHAPTER 1\nDEFINITIONS AND PURPOSE (ss'):]
    body = body[:body.index('\n115  ') + 2000]
    body = re.split(r'\nSchedule\n', body)[0]
    out: dict[str, list[str]] = {}
    cur = None
    skip_next = False
    for line in body.split('\n'):
        m = re.match(r'^(\d+)  (\S.*)$', line)
        if m and (cur is None or int(m.group(1)) == int(cur) + 1):
            cur = m.group(1)
            out[cur] = words(m.group(2))
            continue
        if skip_next:
            skip_next = False
            continue
        if re.match(r'^(CHAPTER \d+|Part [A-Z]|Condition \d+)\s*$', line):
            skip_next = True      # the title line under a Chapter, Part or Condition number
            continue
        if re.match(r'^[A-Z][A-Z ,]+(\(ss? [\d-]+\))?$', line) or re.search(r'\(ss? \d+-\d+\)\s*$', line):
            continue
        if cur is not None:
            out[cur] += words(line)
    return out


def compare(name: str, ours: list[str], ref: list[str]) -> dict:
    sm = difflib.SequenceMatcher(a=ours, b=ref, autojunk=False)
    diffs = [(op, ' '.join(ours[i1:i2]), ' '.join(ref[j1:j2])) for op, i1, i2, j1, j2 in sm.get_opcodes() if op != 'equal']
    return {'unit': name, 'ratio': round(sm.ratio(), 4), 'diffs': diffs}


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / 'corpus.json'
    c = json.loads(path.read_text(encoding='utf-8'))
    report = {}
    for act in c['acts']:
        units: dict = {}
        for v in act['versions']:
            if 'units' in v:
                units = v['units']
            elif 'changes' in v:
                units = {**units, **{k: u for k, u in v['changes'].items() if u}}
                for k, u in v['changes'].items():
                    if u is None:
                        units.pop(k, None)
        if act['slug'] == 'popia':
            ref = popia_reference()
            res = []
            for k, u in sorted(units.items()):
                m = re.match(r'section-(\d+)$', k)
                if not m:
                    continue
                n = str(int(m.group(1)))
                text = re.sub(r'^# \d+\. ', '', u['text'])
                ours = words(text)
                res.append(compare(k, ours, ref.get(n, [])))
        elif act['slug'] == 'constitution':
            import constitution_corpus as constitution
            res = constitution.verify(units, words, compare)
        elif act['slug'] == 'companies-act':
            import companies_corpus
            res = companies_corpus.verify(units, words, compare)
        else:
            continue
        bad = [r for r in res if r['diffs']]
        report[act['slug']] = {'units': len(res), 'identical': len(res) - len(bad), 'differ': bad}
        print(f'{act["slug"]}: {len(res)} units, {len(res) - len(bad)} identical word for word, {len(bad)} differ')
        for r in bad[:40]:
            print(f'  {r["unit"]} {r["ratio"]}: ' + ' | '.join(f'{op}: [{a}] -> [{b}]' for op, a, b in r['diffs'][:4])[:600])
    (HERE / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
