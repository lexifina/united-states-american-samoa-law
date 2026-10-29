"""Equatorial Guinea git-for-law: read the cached Boletín Oficial del Estado PDF of the Ley Fundamental (Ley 1/2012)
from its text layer and write corpus.json in the gitlaw_common SCHEMA.md format. No network; the same cache gives the
same bytes.

    python -X utf8 scripts/equatorial-guinea-law/parse.py

The BOE file is an FPDF document (Arial 11 pt, one column, left margin 85 pt, right margin 513 pt) with an
electronic-signature line (Helvetica 10 pt, "Documento firmado electrónicamente con código de verificación …") on every
page; that line is dropped. Paragraphs are rebuilt from the layout: a sentence end followed by a blank line or by a
line short of the right margin ends a paragraph, and a line without a sentence end runs on (also across a page
break). Numbered paragraphs ("2.-") and list items ("a)") start new lines. Bold, centred lines are headings.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from pathlib import Path

import fitz  # PyMuPDF

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
RETRIEVED = '2026-10-29'
LF_URL = 'https://boe.gob.gq/sites/default/files/2026-10/LEY%20FUNDAMENTAL_0.pdf'
LF_ALT = 'https://boe.gob.gq/files/LEY%20FUNDAMENTAL.pdf'       # the search result's link; byte-identical file
REFORM_2025 = 'https://boe.gob.gq/files/MODIFICACI%C3%93N%20DE%20LA%20LEY%20FUNDAMENTAL.pdf'
BOE = 'https://boe.gob.gq'


def cached(url: str) -> Path:
    return CACHE / hashlib.sha256(url.encode('utf-8')).hexdigest()


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def norm(s: str) -> str:
    s = unicodedata.normalize('NFC', s)
    for a, b in ((' ', ' '), (' ', ' '), (' ', ' '), ('\t', ' '), ('’', "'"), ('‘', "'"),
                 ('“', '«'), ('”', '»'), ('—', '–'), ('‑', '-')):
        s = s.replace(a, b)
    s = re.sub(r' {2,}', ' ', s)
    return s.strip()


# ------------------------------------------------------------------ PDF -> visual lines

RIGHT = 513.0


def visual_lines(pdf: Path) -> list[dict]:
    out = []
    for pno, page in enumerate(fitz.open(pdf)):
        rows: list[dict] = []
        for b in page.get_text('dict')['blocks']:
            for ln in b.get('lines', []):
                for s in ln['spans']:
                    if s['text'].startswith('Documento firmado electr'):
                        continue                                 # the e-signature line on every page
                    x0, y0, x1, y1 = s['bbox']
                    yc = (y0 + y1) / 2
                    row = next((r for r in rows if abs(r['yc'] - yc) < 3), None)
                    if row is None:
                        row = {'yc': yc, 'spans': []}
                        rows.append(row)
                    row['spans'].append((x0, x1, s['text'], bool(s['flags'] & 16), s['size']))
        rows.sort(key=lambda r: r['yc'])
        for r in rows:
            sp = sorted(r['spans'])
            ink = [s for s in sp if s[2].strip()]
            if not ink:
                out.append({'page': pno, 'blank': True})
                continue
            out.append({'page': pno, 'blank': False, 'text': norm(''.join(s[2] for s in sp)), 'x0': ink[0][0],
                        'x1': ink[-1][1], 'y': r['yc'], 'bold': all(s[3] for s in ink),
                        'size': max(s[4] for s in ink)})
    return out


ART_RX = re.compile(r'^Artículo\s+(\d+)\s*\.?-\s*(.*)$')
START_RX = re.compile(r'^(Artículo\s+\d+\s*\.?-|\d+\s*\.-|[a-zñ]\)\s|(Primera|Segunda|Tercera|Cuarta)\.\s)')
TERMINAL = ('.', ';', ':', '!', '?', '»')


def join(a: str, b: str) -> str:
    if re.search(r'\w-$', a) and b[:1].isalpha():
        return a + b          # a compound split at its hyphen ("Vice-" / "Presidente"); the hyphen is kept
    return a + ' ' + b


def paragraphs(lines: list[dict]) -> list[dict]:
    paras: list[dict] = []
    prev = None
    blank = False
    for ln in lines:
        if ln['blank']:
            blank = True
            continue
        t = ln['text']
        head = ln['bold'] and ln['x0'] > 150 and not START_RX.match(t)
        if head:
            starter = bool(re.match(r'^(TÍTULO|CAPÍTULO|DISPOSICI|P R E|I N T R)', t))
            if (paras and paras[-1]['kind'] == 'head' and not starter and prev is not None
                    and ln['page'] == prev['page'] and ln['y'] - prev['y'] < 15):
                paras[-1]['text'] += ' ' + t                    # a heading set over several lines
            else:
                paras.append({'kind': 'head', 'text': t})
        else:
            new = True
            # a centred line (the closing "POR UNA GUINEA MEJOR" and signature) stands on its own
            if prev is not None and paras and paras[-1]['kind'] == 'text' and not START_RX.match(t) and \
                    ln['x0'] < 150 and prev['x0'] < 150:
                ends = paras[-1]['text'].endswith(TERMINAL)
                short = prev['x1'] < RIGHT - 18
                new = ends and (blank or short)
            if new:
                paras.append({'kind': 'text', 'text': t})
            else:
                paras[-1]['text'] = join(paras[-1]['text'], t)
        prev = ln
        blank = False
    for p in paras:
        p['text'] = norm(p['text'])
    return paras


# ------------------------------------------------------------------ paragraphs -> units

DISP = {'DISPOSICIONES TRANSITORIAS:': 'transitoria', 'DISPOSICIÓN DEROGATORIA:': 'derogatoria',
        'DISPOSICIÓN FINAL:': 'final'}
ORD = {'Primera': 1, 'Segunda': 2, 'Tercera': 3, 'Cuarta': 4}


def ley_fundamental() -> tuple[dict, list[str]]:
    paras = paragraphs(visual_lines(cached(LF_URL)))
    units: dict[str, dict] = {}
    structure: list[str] = []
    pending: list[str] = []
    problems: list[str] = []
    cur = None
    mode = None
    for p in paras:
        t = p['text']
        if p['kind'] == 'head':
            flat = t.replace(' ', '')
            if flat == 'INTRODUCCIÓN':
                cur, mode = 'introduccion', 'body'
                units[cur] = {'label': 'Introducción (fórmula de promulgación)', 'kind': 'enacting',
                              'lines': ['# Introducción']}
            elif flat == 'PREÁMBULO':
                cur, mode = 'preambulo', 'body'
                units[cur] = {'label': 'Preámbulo', 'kind': 'preamble', 'lines': ['# Preámbulo']}
            elif t in DISP:
                mode = DISP[t]
                if mode != 'transitoria':
                    cur = f'disposicion-{mode}'
                    label = {'derogatoria': 'Disposición derogatoria', 'final': 'Disposición final'}[mode]
                    units[cur] = {'label': label, 'kind': 'final' if mode == 'final' else 'repeal',
                                  'lines': [f'# {label}']}
            elif cur in (None, 'introduccion') or t.startswith('LEY FUNDAMENTA'):
                continue                       # title page, and the title repeated before the preamble
            else:
                pending.append(t)
            continue
        if cur is None:
            continue                           # title page text before the introduction
        m = ART_RX.match(t)
        if m and mode in ('body', None) or (m and cur.startswith('art-')):
            key = f'art-{int(m.group(1)):03d}'
            label = f'Artículo {int(m.group(1))}'
            if key in units:
                problems.append(f'duplicate {key}')
            if pending:
                structure.append(' | '.join(pending) + f' | {label}')
                pending = []
            units[key] = {'label': label, 'kind': 'art', 'lines': [f'# {label}']}
            if m.group(2).strip():
                units[key]['lines'].append(m.group(2).strip())
            cur = key
            continue
        if pending:
            problems.append(f'text after a heading with no article: {t[:60]}')
        if mode == 'transitoria':
            mo = re.match(r'^(Primera|Segunda|Tercera|Cuarta)\.\s*(.*)$', t)
            if mo:
                n = ORD[mo.group(1)]
                cur = f'disposicion-transitoria-{n}'
                units[cur] = {'label': f'Disposición transitoria {mo.group(1).lower()}', 'kind': 'transitional',
                              'lines': [f'# Disposición transitoria {mo.group(1).lower()}', mo.group(2)]}
                continue
        if mode == 'final' and t.startswith('Por todo cuanto antecede'):
            cur, mode = 'formula-final', 'formula'
            units[cur] = {'label': 'Fórmula de promulgación', 'kind': 'final',
                          'lines': ['# Fórmula de promulgación']}
        units[cur]['lines'].append(t)
    out = {k: {'label': v['label'], 'kind': v['kind'], 'text': '\n'.join(v['lines']) + '\n'} for k, v in units.items()}
    out['estructura'] = {'label': 'Estructura (títulos y capítulos)', 'kind': 'structure',
                         'text': '# Estructura\n' + '\n'.join(structure) + '\n'}
    return out, problems


# ------------------------------------------------------------------ corpus

COUNTRY = {
    'code': 'GQ', 'name': 'Equatorial Guinea', 'slug': 'equatorial-guinea', 'lang': 'es', 'tz': 'Africa/Malabo',
    'future_branch': 'futuro',
    'publisher': {'name': 'Boletín Oficial del Estado de Guinea Ecuatorial', 'email': 'boe@boe-gob-gq.invalid'},
    'default_in_force_rule': {
        'text': 'Not applied as a general rule. Ley 1/2012, Disposición final: "La presente Ley Fundamental entrará '
                'en vigor a partir de su promulgación por el Presidente de la República, después de haber sido '
                'aprobada en Referéndum y su publicación en el Boletín Oficial del Estado"; it was promulgated in '
                'Bata on 16 February 2012, the date under which the BOE lists it. Its BOE publication date is not '
                'given by the source.',
        'source': LF_URL},
    'licence_note': 'Text: Ley Núm. 1/2012, de fecha 16 de febrero, sobre la Constitución de la República de Guinea '
                    'Ecuatorial (Ley Fundamental), as published by the Boletín Oficial del Estado de Guinea '
                    'Ecuatorial (Presidencia del Gobierno), https://boe.gob.gq. Official text of the Republic of '
                    'Equatorial Guinea.',
}


def main() -> None:
    pdf = cached(LF_URL)
    if sha(pdf) != sha(cached(LF_ALT)):
        raise SystemExit('the two BOE links to the Ley Fundamental no longer serve the same file')
    units, problems = ley_fundamental()
    if problems:
        raise SystemExit('parse problems:\n' + '\n'.join(problems))
    reqs = sum(1 for line in (CACHE / 'requests.jsonl').read_text(encoding='utf-8').splitlines()
               if '"url": "https://boe.gob.gq' in line)
    laws = {
        'ley-1-2012': {'label': 'Ley 1/2012', 'kind': 'law',
                       'title': 'Ley Núm. 1/2012, de fecha 16 de febrero, sobre la Constitución de la República de '
                                'Guinea Ecuatorial (Ley Fundamental), aprobada en Referéndum Popular el 13 de '
                                'noviembre de 2011',
                       'enacted': '2012-02-16', 'published': None, 'url': LF_URL, 'temporary_until': None,
                       'restores': None, 'note': None},
    }
    corpus = {
        'country': COUNTRY,
        'sources': [{
            'name': 'Boletín Oficial del Estado de Guinea Ecuatorial (boe.gob.gq)',
            'url': BOE, 'retrieved': RETRIEVED, 'requests': reqs,
            'licence': 'Official text. The BOE states no licence.',
            'notes': 'Ley Fundamental: "LEY FUNDAMENTAL_0.pdf" (linked from the BOE home page, uploaded October 2026; '
                     'byte-identical to the file at /files/LEY FUNDAMENTAL.pdf that the BOE search lists), 22 '
                     'pages, made with FPDF 1.82 on 2020-11-27, read from its text layer. The BOE search '
                     '(POST /resultados, then GET /masresultados) lists two Ley Fundamental documents: Ley 1/2012 '
                     'and Ley 1/2025 (a scan).'}],
        'laws': laws,
        'acts': [{
            'slug': 'ley-fundamental',
            'short': 'Ley Fundamental',
            'title': 'Ley Fundamental de Guinea Ecuatorial',
            'url': LF_URL,
            'first_law': 'ley-1-2012',
            'earlier_laws': [],
            'versions': [{
                'from': '2012-02-16',
                'source_url': LF_URL,
                'sha256': sha(pdf),
                'units': dict(sorted(units.items())),
                'credits': {},
                'note': 'Ley Núm. 1/2012 as promulgated in Bata on 16 February 2012, after the referendum of 13 '
                        'November 2011. The reform of arts. 56.1, 80 and 84.1 and 2 by Ley 1/2025, de 16 de julio, '
                        'is not applied: the BOE publishes it only as a scan (see the README).',
            }],
        }],
        'applies': [],
        'decisions': [
            'One act, one version: the Ley Fundamental as promulgated by Ley 1/2012 (16 February 2012), credited to '
            'Ley 1/2012 as enacted. It replaced the Ley Fundamental of 1991 (reformed in 1995), whose texts were not '
            'found online with a text layer (BOE search, Internet Archive CDX of boe.gob.gq); the Common Crawl index '
            'did not answer from this machine. So the history before 2012 is missing.',
            'The version is dated 2012-02-16, the promulgation date (Disposición final: in force on promulgation and '
            'BOE publication). The BOE lists the law under that date and gives no separate publication date.',
            'Not today\'s text: Ley 1/2025, de 16 de julio, reforms arts. 56.1, 80 and 84.1 and 2. The BOE publishes '
            'it only as images (FPDF wrapper, no text layer), and scans are not transcribed (no OCR), so the reform '
            'is not applied and its in-force date is not known. The build stays on preview.',
            'The e-signature line printed on every page ("Documento firmado electrónicamente con código de '
            'verificación …"), the title page and the repeated title before the preamble are left out. The '
            'introduction (the promulgation formula before the text) and the closing promulgation formula are kept '
            'as their own units.',
            'Paragraphs are rebuilt from the layout: a sentence end followed by a blank line or a short line ends a '
            'paragraph; a line without a sentence end runs on, also across a page break; numbered paragraphs '
            '("2.-"), list items ("a)") and articles start new lines.',
            'Unit layout: one file per article (art-NNN), the preamble, the introduction, each transitional '
            'provision, the repealing and final provisions, the closing formula, and one structure file '
            '(estructura) naming the article each heading precedes.',
            'Typesetting is normalised once: NBSP to space, curly apostrophes to straight ones, curly double quotes '
            'to « », runs of spaces collapsed. Spelling is kept as printed (for example "DELAS FUERZAS ARMADAS").',
        ],
        'ai_use': ['Claude Code (Claude Opus 5.5, claude-opus-5-5) wrote fetch.py and parse.py, chose the sources '
                   'and wrote the decisions. No model wrote, summarised or transformed legal text: parse.py is '
                   'deterministic code over the cached PDF.'],
    }
    tmp = HERE / 'corpus.json.tmp'
    tmp.write_text(json.dumps(corpus, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    os.replace(tmp, HERE / 'corpus.json')
    print('ley fundamental units:', len(units))


if __name__ == '__main__':
    main()
