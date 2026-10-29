"""Cabo Verde: read only .cache/ and write corpus.json (scripts/gitlaw_common/SCHEMA.md).

    python -X utf8 scripts/cabo-verde-law/parse.py            # writes corpus.json atomically
    python -X utf8 scripts/cabo-verde-law/parse.py --dump DIR # also writes each version's units as text, for checking

Text comes from the PDFs' own text layers: the two-column Boletim Oficial through PyMuPDF, read column by column
(pdf_text); the single-column Assembleia Nacional edition (cross-check only) through poppler's pdftotext. No OCR, no
network, no model. Everything that is decided by hand is in DECISIONS and printed in REPRODUCE.md by the builder.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
RETRIEVED = '2026-10-28'

TC = ('https://www.tribunalconstitucional.cv/wp-admin/admin-ajax.php?juwpfisadmin=false&action=wpfd&task=file.download'
      '&wpfd_category_id=199&wpfd_file_id={}')
TC_LIST = 'https://www.tribunalconstitucional.cv/index.php/leis-constitucionais/'
CNPD = 'https://www.cnpd.cv/wp-content/uploads/2025/03/'
CNPD_LIST = 'https://www.cnpd.cv/legislacao/'
URL = {
    'crcv-1999': TC.format(3370),        # Suplemento ao BO I Série nº 43, 23 Nov 1999: LC 1/V/99 + republication
    'rect-2000': TC.format(3367),        # BO I Série nº 3, 14 Feb 2000: rectification of LC 1/V/99
    'crcv-2010': TC.format(3369),        # BO I Série nº 17, 3 May 2010: LC 1/VII/2010 + republication
    'crcv-1992': TC.format(3368),        # scan, no text layer: not used
    'crcv-1995': TC.format(3371),        # scan, no text layer: not used
    'an-2010': CNPD + 'GDLeisRepublica.pdf',   # Assembleia Nacional, 4th edition 2010 (cross-check only)
    'pd-2013': CNPD + 'Lei-n-41_VIII_2013-regime-juridico-geral-de-proteccao-de-dados-pessoais-das-pessoas-singulares.pdf',
    'pd-2021': CNPD + 'Lei-121.IX_.2021-alteracao-Lei-41.VIII_.2013.pdf',
}

DECISIONS: list[str] = []
WARN: list[str] = []


def cache_path(url: str) -> Path:
    return CACHE / hashlib.sha256(url.encode()).hexdigest()


def sha(url: str) -> str:
    return hashlib.sha256(cache_path(url).read_bytes()).hexdigest()


def pdf_text(url: str, columns: bool = True) -> str:
    """The PDF's text layer, page by page ('\\f' between pages).

    columns=True (the Boletim Oficial, set in two columns): PyMuPDF text blocks in reading order, column by column.
    pdftotext's own reading order interleaves the columns on some pages of the 2010 republication (text of art. 78º
    landed in arts. 79º/80º). A block wider than 60% of the page is full-width (titles, the act's heading); full-width
    blocks cut the page into bands, and each band is read left column top to bottom, then right column.
    Inside a block, PyMuPDF lines on one baseline (it splits a justified line at wide word gaps) are first merged
    into one visual line. A visual line is then joined to the one before it when:
    - the one before is only an item label ("a)", "1."), set apart from its text by a hanging indent; or
    - both are capitals (a heading set over several lines), unless the one before is a bare "TÍTULO II" etc.; or
    - the one before runs to the block's right edge (a justified line that wrapped), the new line starts no further
      right than the one before (a paragraph's first line is indented), or, after an item's first line, no further
      right than a hanging indent; and the new line does not start an item, article or epígrafe after a line that
      ends a clause (".", ";", ":", ")"): "alíneas m) e" / "n) do número 1" is a wrapped cross-reference.
    At such a wrap after a hyphen: a repeated hyphen ("cabo-" / "-verdiano", the Portuguese rule for a compound broken
    at its hyphen) and a hyphen before a capital ("Vice-" / "Presidente") are one hyphenated word; before a small
    letter the line break is kept for clean_lines' hyphen rule. PyMuPDF breaks words at a ligature glyph
    ("quali\\ufb01 car", "con\\ufb01 -"), so the space after a ligature is removed.
    columns=False: poppler pdftotext's reading order (the single-column Assembleia Nacional edition)."""
    if not columns:
        out = subprocess.run(['pdftotext', '-enc', 'UTF-8', str(cache_path(url)), '-'], capture_output=True, check=True)
        return out.stdout.decode('utf-8')
    import fitz  # PyMuPDF  # noqa: PLC0415
    edge, indent, hanging = 8.0, 2.0, 40.0  # points
    label = re.compile(r'^\s*(\d+\s*\.|[a-z]\s*\))\s*$')
    starts = re.compile(r'^\s*(\d+\s*\.\s*\S|[a-z]\s*\)|Artigo\s+\d|\()')
    bare_head = re.compile(r'^\s*(PARTE|T[ÍI]TULO|CAP[ÍI]TULO|SEC[ÇC][ÃA]O|LIVRO)\s+[IVXLCl]+\s*$')

    def caps(s: str) -> bool:
        return bool(re.search(r'[A-ZÀ-Ú]', s)) and not re.search(r'[a-zà-ú]', s)

    def visual_lines(b: dict) -> list[dict]:
        rows: list[dict] = []
        for ln in b['lines']:
            t = ''.join(s['text'] for s in ln['spans'])
            if not t.strip():
                continue
            y = (ln['bbox'][1] + ln['bbox'][3]) / 2
            if rows and abs(rows[-1]['y'] - y) < 2.5 and ln['bbox'][0] >= rows[-1]['bbox'][2] - 1:
                r = rows[-1]
                r['text'] = r['text'].rstrip() + ' ' + t.lstrip()
                r['bbox'] = (r['bbox'][0], min(r['bbox'][1], ln['bbox'][1]), ln['bbox'][2], max(r['bbox'][3], ln['bbox'][3]))
            else:
                rows.append({'text': t, 'bbox': tuple(ln['bbox']), 'y': y})
        return rows

    def block_text(b: dict) -> str:
        x1 = b['bbox'][2]
        out: list[str] = []
        prev = None
        first = False  # is `prev` the first line of an item (label, then text)?
        for ln in visual_lines(b):
            t = re.sub(r'([ﬀ-ﬄ]) (?=[a-zà-ú-])', r'\1', ln['text'])
            reach = ln['bbox'][0] <= prev['bbox'][0] + (hanging if first else indent) if prev else False
            if prev is not None and label.match(out[-1]):
                out[-1] = out[-1].strip() + ' ' + t.lstrip()
                prev, first = ln, True
                continue
            if prev is not None and caps(out[-1]) and caps(t) and not bare_head.match(out[-1]):
                out[-1] = out[-1].rstrip() + ' ' + t.lstrip()
            elif (prev is not None and prev['bbox'][2] >= x1 - edge and reach
                    and (not starts.match(t) or not re.search(r'[.;:)]\s*$', out[-1]))):
                p, n = out[-1].rstrip(), t.lstrip()
                if p.endswith('-') and n.startswith('-'):
                    out[-1] = p + n[1:]
                elif p.endswith('-') and n[:1].isupper():
                    out[-1] = p + n
                elif p.endswith('-'):
                    out.append(t)
                else:
                    out[-1] = p + ' ' + n
                first = False
            else:
                out.append(t)
                first = bool(starts.match(t))
            prev = ln
        return '\n'.join(out)

    pages = []
    with fitz.open(cache_path(url)) as doc:
        for page in doc:
            w = page.rect.width
            blocks = [b for b in page.get_text('dict', sort=False)['blocks']
                      if b['type'] == 0 and any(s['text'].strip() for ln in b['lines'] for s in ln['spans'])]
            mid = w / 2
            wide = lambda b: (b['bbox'][2] - b['bbox'][0] > w * 0.6  # noqa: E731
                              or (b['bbox'][0] < mid - 10 and b['bbox'][2] > mid + 10))  # centred across the gutter
            full = sorted((b for b in blocks if wide(b)), key=lambda b: (b['bbox'][1], b['bbox'][0]))
            cols = [b for b in blocks if not wide(b)]
            cuts = [b['bbox'][1] for b in full] + [float('inf')]
            out: list = []
            for i, top in enumerate([float('-inf')] + [b['bbox'][1] for b in full]):
                if i:
                    out.append(full[i - 1])
                band = [b for b in cols if top <= (b['bbox'][1] + b['bbox'][3]) / 2 < cuts[i]]
                left = sorted((b for b in band if (b['bbox'][0] + b['bbox'][2]) / 2 < mid), key=lambda b: b['bbox'][1])
                right = sorted((b for b in band if (b['bbox'][0] + b['bbox'][2]) / 2 >= mid), key=lambda b: b['bbox'][1])
                # Before a full-width block, a left-column block lying wholly below the right column's last block
                # opens the single-column part above it (a heading), so it is read after the right column.
                after = []
                if right and cuts[i] != float('inf'):
                    floor = max(b['bbox'][3] for b in right)
                    while left and left[-1]['bbox'][1] > floor + 5:
                        after.insert(0, left.pop())
                out += left + right + after
            pages.append('\n'.join(block_text(b) for b in out))
    return '\f'.join(pages)


# ---------------------------------------------------------------- typesetting normalisation

LIGS = {'\ufb01': 'fi', '\ufb02': 'fl', '\ufb00': 'ff', '\ufb03': 'ffi', '\ufb04': 'ffl', '\u00a0': ' ', '\u2009': ' ',
        '\u202f': ' ', '\u00ad': '', '\u201c': '"', '\u201d': '"', '\u201e': '"', '\u2018': "'", '\u2019': "'",
        '\u2014': '–', '\u2013': '–', '\u2012': '–', '\u2026': '...', '\t': ' '}


def norm(line: str) -> str:
    line = unicodedata.normalize('NFC', ''.join(LIGS.get(c, c) for c in line))
    line = re.sub(r' {2,}', ' ', line).strip()
    line = re.sub(r'^(\d+)\s*\.\s*(?=\S)', r'\1. ', line)            # "1.Cabo" / "4 . No" -> "1. Cabo"
    line = re.sub(r'^([a-z])\s+\)', r'\1)', line)                     # "c ) Demissão" -> "c) Demissão"
    line = re.sub(r'\s+([;:,])', r'\1', line)                         # "criminal ;" -> "criminal;"
    line = re.sub(r'(\d)\s+º', r'\1º', line)                          # "110 º" -> "110º"
    line = re.sub(r' - ', ' – ', line)
    line = re.sub(r'\.{3,}', '...', line)
    line = re.sub(r'^\.(?=(PARTE|T[ÍI]TULO|CAP[ÍI]TULO|SEC[ÇC][ÃA]O)\b)', '', line)   # ".TÍTULO X"
    m = re.match(r'^(PARTE|T[ÍI]TULO|CAP[ÍI]TULO|SEC[ÇC][ÃA]O|Sec[çc][ãa]o|LIVRO)\s+([IVXLCl]+)$', line)
    if m:                                                              # "SECÇÃO Ill" -> "SECÇÃO III"
        line = f'{m.group(1)} {m.group(2).replace("l", "I")}'
    return line


PAGE_JUNK = [
    re.compile(r'^\d*\s*I\s*S[ÉE]RIE\s*[—–-].*(19|20)\d\d\s*\d*$', re.I),
    re.compile(r'^\d+$'),
    re.compile(r'^[—–-]{2,}(o§o[—–-]+)?$'),
    re.compile(r'^Constituição 2010\.indd'),
    re.compile(r'^\d\d-\d\d-\d{4} \d+:\d\d:\d\d$'),
    re.compile(r'^©\s*Todos os direitos reservados'),
    re.compile(r'^https?://kiosk\.incv\.cv'),
    re.compile(r'^\d \d{6} \d{6}$'),
]


def clean_lines(raw: str) -> list[str]:
    """Drop page furniture, normalise, and join paragraphs that a page or column break split."""
    lines = []
    for l in raw.replace('\f', '\n').split('\n'):
        l = norm(l)
        if not l or any(p.match(l) for p in PAGE_JUNK):
            continue
        lines.append(l)
    vocab = set(re.findall(r'\w+-\w+', ' '.join(lines)))
    out: list[str] = []
    for l in lines:
        if out and re.match(r'^[a-zà-ú]', l) and not re.match(r'^[a-z]\)', l) and not re.search(r'[.;:!?)]$', out[-1]):
            prev = out[-1]
            if prev.endswith('-'):
                w1 = re.search(r'(\w+)-$', prev).group(1) if re.search(r'(\w+)-$', prev) else ''
                w2 = re.match(r'\w+', l).group(0) if re.match(r'\w+', l) else ''
                out[-1] = prev + l if f'{w1}-{w2}' in vocab else prev[:-1] + l
            else:
                out[-1] = prev + ' ' + l
            continue
        out.append(l)
    return out


# ---------------------------------------------------------------- articles and headings

ART = re.compile(r'^Artigo\s+(\d+)\s*\.?\s*º\s*(?:-\s*([A-Z]))?\s*(\(.*\))?\s*$')
HEAD = re.compile(r'^(PARTE|T[ÍI]TULO|CAP[ÍI]TULO|SEC[ÇC][ÃA]O|Sec[çc][ãa]o|LIVRO)\s+[IVXLC]+\b.*$')


def art_key(n: str, letter: str | None) -> str:
    return f'art-{int(n):03d}' + (f'-{letter.lower()}' if letter else '')


def art_label(n: str, letter: str | None) -> str:
    return f'Artigo {int(n)}º' + (f'-{letter}' if letter else '')


def split_articles(lines: list[str], preamble_title: str | None = None) -> dict:
    """lines: the act's text from its first line to its last. Returns ordered units."""
    units: dict[str, dict] = {}
    heads: list[str] = []
    cur = None
    pre: list[str] = []
    i = 0
    in_head = False
    while i < len(lines):
        l = lines[i]
        m = ART.match(l)
        if m:
            key, label = art_key(m.group(1), m.group(2)), art_label(m.group(1), m.group(2))
            if key in units:
                WARN.append(f'duplicate {key}')
                key += '-bis'
            epi = m.group(3)
            if not epi and i + 1 < len(lines) and lines[i + 1].startswith('('):
                i += 1
                epi = lines[i]
                while not epi.endswith(')') and i + 1 < len(lines):
                    i += 1
                    epi += ' ' + lines[i]
            title = f'# {label}' + (f' {epi}' if epi else '')
            cur = units[key] = {'label': label, 'kind': 'art', 'lines': [title]}
            if heads and heads[-1].endswith('\u0000'):
                heads[-1] = heads[-1][:-1] + f' [{label}]'
            in_head = False
        elif HEAD.match(l):
            heads.append(l + '\u0000')
            in_head = True
            cur = None
        elif in_head:
            heads[-1] = heads[-1][:-1] + ' – ' + l + '\u0000'
        elif cur is None:
            pre.append(l)
        else:
            cur['lines'].append(l)
        i += 1
    out = {}
    if pre:
        out['preambulo'] = {'label': 'Preâmbulo', 'kind': 'preamble',
                            'text': (f'# {preamble_title}\n' if preamble_title else '') + '\n'.join(pre) + '\n'}
    if heads:
        out['estrutura'] = {'label': 'Estrutura (partes, títulos, capítulos, secções)', 'kind': 'heading',
                            'text': '\n'.join(h.rstrip('\u0000') for h in heads) + '\n'}
    for k, u in units.items():
        out[k] = {'label': u['label'], 'kind': u['kind'], 'text': '\n'.join(u['lines']) + '\n'}
    return out


def between(lines: list[str], start: str, end: str | None, after: str | None = None) -> list[str]:
    i0 = lines.index(after) + 1 if after else 0
    s = next(i for i in range(i0, len(lines)) if lines[i] == start)
    e = next((i for i in range(s + 1, len(lines)) if end and lines[i] == end), len(lines))
    return lines[s:e]


# ---------------------------------------------------------------- the Constitution

def constitution_text(src: str, after: str) -> dict:
    lines = clean_lines(pdf_text(URL[src]))
    i0 = next(i for i, l in enumerate(lines) if l.startswith(after))
    body = lines[i0 + 1:]
    s = next(i for i, l in enumerate(body) if l.upper() in ('PREÂMBULO', 'CONSTITUIÇÃO DA REPÚBLICA DE CABO VERDE'))
    if body[s].upper().startswith('CONSTITUI'):
        s += 1
    body = body[s + 1:]          # drop the "Preâmbulo" title line itself
    e = body.index('ANEXOS')
    main, annex = body[:e], body[e + 1:]
    sign = [l for l in main if l.startswith('O Presidente da Assembleia Nacional')]
    main = [l for l in main if not l.startswith('O Presidente da Assembleia Nacional')]
    units = split_articles(main, 'Preâmbulo')
    if sign:
        units['assinatura'] = {'label': 'Assinatura', 'kind': 'other', 'text': '\n'.join(sign) + '\n'}
    annex = [l for l in annex if not l.startswith('O Presidente da Assembleia Nacional')
             and not l.startswith('HINO NACIONAL')]
    units['anexo'] = {'label': 'Anexos (Hino Nacional)', 'kind': 'annex', 'text': '# Anexos\n' + '\n'.join(annex) + '\n'}
    return units


def rectify_2000(units: dict) -> tuple[dict, list[str]]:
    """Apply the three corrections to the Constitution in BO I Série nº 3, 14 Feb 2000 (Secretaria-Geral da
    Assembleia Nacional, 28 Jan 2000). Each 'Onde se lê' string must be found in the cached rectification and in the
    1999 text, or parse stops."""
    rect = '\n'.join(clean_lines(pdf_text(URL['rect-2000'])))
    fixes = [
        ('art-065', 'a) Na definição da política de instituições', 'b) Na definição da política de instituições'),
        # the rectification quotes the printed n. 2 inexactly ("alínea p) do número 3"; printed: "alínea p) do
        # número 1 e do número 3"): its "Deve ler-se" wording replaces the whole paragraph
        ('art-153', 'nos termos da alínea p) do número 1 e do número 3 do artigo 134º',
         'nos termos da alínea o) do número 3 do artigo 134º'),
        ('art-260', '180º números 2 e 4 e 182º', '180º número 1 e 182º'),
    ]
    out = dict(units)
    changed = []
    for key, old, new in fixes:
        assert new in rect, (key, 'correction not in the rectification text')
        t = out[key]['text']
        assert t.count(old) == 1, (key, old)
        out[key] = dict(out[key], text=t.replace(old, new))
        changed.append(key)
    return out, changed


def diff_keys(a: dict, b: dict) -> list[str]:
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


def constitution() -> tuple[dict, dict]:
    laws = {
        'lc-1-iv-92': {'label': 'Lei Constitucional nº 1/IV/92', 'title': 'Aprova a Constituição da República de Cabo Verde',
                       'kind': 'law', 'enacted': '1992-09-25', 'published': '1992-09-25', 'url': URL['crcv-1992']},
        'lc-1-iv-95': {'label': 'Lei Constitucional nº 1/IV/95', 'title': '1ª Revisão da Constituição de 1992',
                       'kind': 'law', 'enacted': '1995-11-13', 'published': '1995-11-13', 'url': URL['crcv-1995']},
        'lc-1-v-99': {'label': 'Lei Constitucional nº 1/V/99', 'title': 'Revê a Constituição da República de Cabo Verde',
                      'kind': 'law', 'enacted': '1999-11-10', 'published': '1999-11-23', 'url': URL['crcv-1999']},
        'rect-lc-1-v-99': {'label': 'Rectificação da Lei Constitucional nº 1/V/99',
                           'title': 'Rectificação da Lei Constitucional nº 1/V/99 (BO I Série nº 3, 14 de Fevereiro de 2000)',
                           'kind': 'law', 'enacted': '2000-01-28', 'published': '2000-02-14', 'url': URL['rect-2000'],
                           'note': 'A rectification by the Secretaria-Geral of the Assembleia Nacional of text published '
                                   'inexactly in the 1999 republication; it changes no law, only corrects the printed words.'},
        'lc-1-vii-2010': {'label': 'Lei Constitucional nº 1/VII/2010', 'title': 'Revê a Constituição da República de Cabo Verde',
                          'kind': 'law', 'enacted': '2010-04-07', 'published': '2010-05-03', 'url': URL['crcv-2010']},
    }
    for k in laws:
        laws[k].setdefault('temporary_until', None)
        laws[k].setdefault('restores', None)
        laws[k].setdefault('note', None)
    v1 = constitution_text('crcv-1999', 'O Presidente da Assembleia Nacional, António do Espírito Santo Fonseca..')
    v2, fixed = rectify_2000(v1)
    v3 = constitution_text('crcv-2010', 'O Presidente da Assembleia Nacional, Aristides Raimundo Lima')
    # the last of the three signature lines before the republication
    d3 = diff_keys(v2, v3)
    versions = [
        {'from': '1999-11-23', 'source_url': URL['crcv-1999'], 'sha256': sha(URL['crcv-1999']), 'units': v1,
         'credits': {},
         'note': 'The Constitution of 1992 as revised by Leis Constitucionais 1/IV/95 and 1/V/99, from the republication '
                 'in the Suplemento ao Boletim Oficial, I Série, nº 43, 23 Nov 1999. The 1992 and 1995 texts are scans '
                 'with no text layer, so this is the oldest version in the record.'},
        {'from': '2000-02-14', 'source_url': URL['rect-2000'], 'sha256': sha(URL['rect-2000']),
         'changes': {k: v2[k] for k in fixed}, 'credits': {k: ['rect-lc-1-v-99'] for k in fixed}},
        {'from': '2010-05-03', 'source_url': URL['crcv-2010'], 'sha256': sha(URL['crcv-2010']),
         'changes': {k: v3.get(k) for k in d3}, 'credits': {k: ['lc-1-vii-2010'] for k in d3},
         'note': 'Republication of the whole Constitution with Lei Constitucional 1/VII/2010, which renumbered the '
                 'articles (its art. 5).'},
    ]
    act = {'slug': 'constituicao', 'short': 'CRCV', 'title': 'Constituição da República de Cabo Verde',
           'url': TC_LIST, 'first_law': None, 'earlier_laws': ['lc-1-iv-92', 'lc-1-iv-95', 'lc-1-v-99'],
           'versions': versions}
    return laws, act, {'v1': v1, 'v2': v2, 'v3': v3}


# ---------------------------------------------------------------- main

def main(argv: list[str]) -> int:
    laws, act, dump = constitution()
    corpus = {
        'country': {
            'code': 'CV', 'name': 'Cabo Verde', 'slug': 'cabo-verde', 'lang': 'pt', 'tz': 'Atlantic/Cape_Verde',
            'future_branch': 'futuro',
            'publisher': {'name': 'Imprensa Nacional de Cabo Verde (Boletim Oficial)', 'email': 'boletim-oficial@incv.cv.invalid'},
            'default_in_force_rule': {
                'text': 'Each act in the record sets its own entry into force, which is used: LC 1/V/99 art. 185 '
                        '("entra imediatamente em vigor"), LC 1/VII/2010 art. 6 ("na data da sua publicação"), Leis '
                        '41/VIII/2013 and 121/IX/2021 ("trinta dias após a sua publicação").',
                'source': TC_LIST},
            'licence_note': 'Texts of the Boletim Oficial da República de Cabo Verde (Imprensa Nacional de Cabo Verde), '
                            'read from the copies published by the Tribunal Constitucional and the Comissão Nacional de '
                            'Protecção de Dados.',
        },
        'sources': [
            {'name': 'Tribunal Constitucional de Cabo Verde: Leis Constitucionais', 'url': TC_LIST, 'retrieved': RETRIEVED,
             'requests': 0, 'licence': 'Official texts of the Boletim Oficial; site "Todos os direitos Reservados".',
             'notes': 'Eleven PDFs of every constitutional law since 1975. The 1992 and 1995 files are image scans '
                      '(no text layer) and are not used; 1999, the 2000 rectification and 2010 have text layers.'},
        ],
        'laws': laws,
        'acts': [act],
        'applies': [],
        'decisions': DECISIONS,
        'ai_use': ['Claude Code with Claude Opus 5.5 (claude-opus-5-5) wrote fetch.py and parse.py and chose the '
                   'sources; no model wrote, read or corrected any legal text, and no model runs at build time.'],
    }
    log = [json.loads(l) for l in (CACHE / 'requests.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
    corpus['sources'][0]['requests'] = sum(1 for r in log if 'tribunalconstitucional.cv' in r.get('url', ''))
    DECISIONS.extend([
        'Text is read from each Boletim Oficial PDF\'s own text layer with PyMuPDF, column by column: blocks wider than '
        '60% of the page or centred across the gutter cut the page into bands, and each band is read left column, then '
        'right column (pdftotext\'s own order interleaved the columns on some 2010 pages, moving text of art. 78º into '
        'arts. 79º and 80º). Inside a block, lines are joined into paragraphs by their position (a justified line '
        'running to the right edge continues; an indented line starts a paragraph). Page headers, page numbers and '
        'print furniture are dropped, and paragraphs split by a page or column break are joined.',
        'Hyphens at a line break: a repeated hyphen ("cabo-" / "-verdiano", the Portuguese rule for a compound broken '
        'at its hyphen) and a hyphen before a capital ("Procurador-" / "Geral") are kept as one hyphenated word; before '
        'a small letter the hyphen is kept only where the hyphenated word occurs elsewhere in the same document.',
        'Typesetting is normalised once: ligatures, non-breaking spaces, curly quotes to straight, em/en dashes to "–", '
        '"1.Texto" to "1. Texto", "c )" to "c)", spaces before ; : , removed, "110 º" to "110º".',
        'One file per article (art-NNN, art-NNN-a for "Artigo Nº-A"); the article number and epígrafe are the first '
        'line. Part, title, chapter and section headings are listed in constituicao/estrutura.md with the first '
        'article under each.',
        'Constitution: the 1992 original (LC 1/IV/92) and the 1995 revision (LC 1/IV/95) are only image scans on the '
        'Tribunal Constitucional site, so with no OCR the record starts at the 1999 republication, credited to the '
        'publisher as the oldest version available.',
        'Constitution: LC 1/V/99 art. 185 puts it in force immediately; the in-force day used is the day of its '
        'publication, 23 Nov 1999 (Suplemento ao BO nº 43).',
        'Constitution: the rectification in BO I Série nº 3 of 14 Feb 2000 corrects three printing errors in the 1999 '
        'republication (arts. 65, 153 and 260). It is dated on its publication, 14 Feb 2000, although a rectification '
        'is read as the text from the original publication.',
        'Constitution: LC 1/VII/2010 art. 6 puts it in force on publication, 3 May 2010 (BO I Série nº 17). It '
        'renumbered the articles, so after 2010 an article file holds the article now bearing that number; git does '
        'not follow an article across the renumbering.',
    ])
    if WARN:
        DECISIONS.append('Parser warnings: ' + '; '.join(WARN))
    tmp = HERE / 'corpus.json.tmp'
    tmp.write_text(json.dumps(corpus, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    os.replace(tmp, HERE / 'corpus.json')
    if '--dump' in argv:
        d = Path(argv[argv.index('--dump') + 1])
        for name, units in dump.items():
            (d / name).mkdir(parents=True, exist_ok=True)
            for k, u in units.items():
                (d / name / f'{k}.md').write_text(u['text'], encoding='utf-8', newline='\n')
    for name, units in dump.items():
        print(name, len(units), 'units', sum(1 for k in units if k.startswith('art-')), 'articles')
    print('warnings:', WARN)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
