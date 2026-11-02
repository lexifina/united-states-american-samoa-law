"""Builds corpus.d/10-lei-organica.json for the Município de @CITY@ from the PDF of the Lei Orgânica the Câmara
Municipal's SAPL holds (a text layer of its own; no network).

    python -X utf8 parse.py --today YYYY-MM-DD

The PDF is read with PyMuPDF line by line. Lines repeated at the top or bottom of most pages (letterheads,
footers), lines that are only a page number and rule lines are left out. The text runs from the line CONFIG['start']
(its first match after CONFIG['after']) to the last line matching CONFIG['end']; the table of contents and anything
after the closing line (signatures, appendices) are left out. Lines are joined into paragraphs: a new paragraph at a
provision label, a heading line, or after a line ending in ".", ";" or ":". Notes in parentheses that the edition
adds after a provision (CONFIG['note']: "(Nova redação dada pela Emenda nº ...)", "(Acrescido pela ...)") are left
out of the text; a paragraph carrying a note that it was declared unconstitutional (CONFIG['void']) is left out whole.
"""
import argparse, re, sys
from pathlib import Path

import pymupdf

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from br_lib import units_of, write_part, sha, norm  # noqa: E402

CONFIG = @CONFIG@
BASE = 'https://' + CONFIG['host']
RAW = HERE / '.cache' / 'sapl' / 'raw'
STARTS = re.compile(r'^(?:Art\.|Art\s+\d|Artigo\s+\d|§|Par[áa]grafo|[IVXLC]+\s*[-–.)]|[a-z]\)|T[ÍI]TULO|CAP[ÍI]TULO|'
                    r'Se[c]?[çc][ãa]o|SE[C]?[ÇC][ÃA]O|Subse[c]?[çc][ãa]o|SUBSE[C]?[ÇC][ÃA]O|PRE[ÂA]MBULO|ATO\s+DAS)')
HEADING = re.compile(r'^(?:T[ÍI]TULO|CAP[ÍI]TULO|SE[C]?[ÇC][ÃA]O|Se[c]?[çc][ãa]o|Subse[c]?[çc][ãa]o|SUBSE[C]?[ÇC][ÃA]O)'
                     r'\s+(?:[IVXLC]+|[ÚU]NIC[OA])\b|^PRE[ÂA]MBULO$|^ATO\s+DAS\s+DISPOSI')
LABEL = re.compile(r'^(?:Art\.?\s*\d|Artigo\s+\d|§|Par[áa]grafo|[IVXLC]+\s*[-–.)]|[a-z]\))')
PAGENO = re.compile(r'^(?:P[áa]g(?:ina)?\.?\s*)?\d{1,3}(?:\s*(?:/|de)\s*\d{1,3})?$|^_{5,}$', re.I)
MONTHS = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro',
          'novembro', 'dezembro']

COUNTRY = {
    'code': CONFIG['code'], 'name': CONFIG['city'], 'slug': CONFIG['slug'], 'lang': 'pt', 'tz': CONFIG['tz'],
    'future_branch': 'futuro',
    'publisher': {'name': f"Câmara Municipal de {CONFIG['city']} (SAPL)", 'email': f"sapl@{CONFIG['email_domain']}.invalid"},
    'default_in_force_rule': {
        'text': CONFIG['rule'] + ' Municipal laws: Decreto-Lei 4.657/1942 (LINDB) art. 1 gives 45 days unless a law '
                'says otherwise; this record takes in only laws whose vigência clause says they take effect on their '
                'publication (or signature) and dates each by the publication date SAPL records for it (else by its '
                'date).',
        'source': f"{BASE}/norma/{CONFIG['norma']}"},
    'licence_note': f"Texts: Câmara Municipal de {CONFIG['city']}, SAPL (Sistema de Apoio ao Processo Legislativo), "
                    f"{CONFIG['host']}; SAPL: \"Conteúdo e dados sob licença Creative Commons 4.0 Atribuir Fonte - "
                    'Compartilhar Igual". Lei 9.610/1998 art. 8 IV: the texts of laws and other official acts are not '
                    'protected by copyright. Non-official text: only the official gazette is authoritative.',
}
AI = ["Claude Code (claude-opus-5-5) wrote Lexifina's code and chose the sources. No model output is used as legal "
      "text or dates: every word comes from the Câmara's SAPL."]


def lines_of(path):
    d = pymupdf.open(str(path))
    pages = [[l for l in (norm(x) for x in pg.get_text().split('\n')) if l] for pg in d]
    seen = {}
    for ls in pages:
        for l in set(ls[:6] + ls[-4:]):
            k = re.sub(r'\d', '#', l)
            seen[k] = seen.get(k, 0) + 1
    rep = {k for k, n in seen.items() if n >= max(3, len(pages) // 2)}  # on most pages: letterhead, footer
    return [l for ls in pages for l in ls if re.sub(r'\d', '#', l) not in rep and not PAGENO.match(l)]


def paragraphs(lines):
    paras = []
    for l in lines:
        head = bool(HEADING.match(l))
        prev = paras[-1] if paras else None
        if prev is not None and re.fullmatch(r'Art\.?', prev[1]):
            prev[1] += ' ' + l
            continue
        if prev is None or STARTS.match(l) or head or re.search(r'[.;:]["”]?$', prev[1]):
            paras.append([head, l])
        elif prev[1].endswith('-') and not prev[1].endswith(' -'):
            prev[1] += l
        else:
            prev[1] += ' ' + l
    out = []
    note = re.compile(CONFIG['note'], re.I) if CONFIG.get('note') else None
    void = re.compile(CONFIG['void'], re.I) if CONFIG.get('void') else None
    dropped = 0
    for h, t in paras:
        if void and void.search(t):
            dropped += 1
            continue
        if note:
            t = note.sub(' ', t)
        t = norm(t)
        if t and re.search(r'\w', t):
            out.append(('h2' if h else 'p', t))
    return out, dropped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--today', required=True)
    a = ap.parse_args()
    path = RAW / sha(CONFIG['url'].encode())
    b = path.read_bytes()
    lines = lines_of(path)
    after = next(i for i, l in enumerate(lines) if re.search(CONFIG['after'], l))
    start = next(i for i, l in enumerate(lines) if i >= after and re.search(CONFIG['start'], l))
    end = max(i for i, l in enumerate(lines) if i > start and re.search(CONFIG['end'], l))
    paras, dropped = paragraphs(lines[start:end + 1])
    units = units_of(paras, title_label='Preâmbulo', adt=True)
    key = CONFIG['law_key']
    page = f"{BASE}/norma/{CONFIG['norma']}"
    laws = {key: {'label': CONFIG['label'], 'title': CONFIG['title'], 'kind': 'law', 'enacted': CONFIG['enacted'],
                  'published': CONFIG.get('published'), 'url': page, 'temporary_until': None, 'restores': None,
                  'note': None}}
    v = {'from': CONFIG['from'], 'source_url': CONFIG['url'], 'sha256': sha(b), 'units': units, 'note': CONFIG['vnote']}
    act = {'slug': 'lei-organica', 'short': f"LOM-{CONFIG['city'].replace(' ', '-')}",
           'title': f"Lei Orgânica do Município de {CONFIG['city']}", 'url': page,
           'first_law': key if CONFIG['mode'] == 'enacted' else None,
           'earlier_laws': [] if CONFIG['mode'] == 'enacted' else [key], 'versions': [v]}
    c = {'country': COUNTRY,
         'sources': [{'name': f"Câmara Municipal de {CONFIG['city']}, SAPL: {CONFIG['source_name']}", 'url': page,
                      'retrieved': a.today, 'licence': COUNTRY['licence_note'], 'notes': '1 act.'}],
         'laws': laws, 'acts': [act], 'applies': [], 'decisions': CONFIG['decisions'], 'ai_use': AI}
    print(write_part(HERE / 'corpus.d', '10-lei-organica', c), len(units), 'units', dropped, 'paragraphs left out')


if __name__ == '__main__':
    main()
