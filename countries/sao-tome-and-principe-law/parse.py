"""São Tomé and Príncipe: build corpus.json from the cached official copies (no network).

Reads only .cache/dl/ (written by fetch.py from pinned archive.org id_ captures) and writes corpus.json
atomically. Text comes from each PDF's own text layer (xpdf pdftotext -layout -enc UTF-8); nothing is OCR'd.
"""
import hashlib, io, json, os, re, subprocess, sys, tempfile, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DL = HERE / '.cache' / 'dl'
SRC = json.load(open(HERE / 'sources.json', encoding='utf-8'))
PINS = {p['name']: p for p in SRC['captures']}


def wb_url(name):
    p = PINS[name]
    return f"https://web.archive.org/web/{p['ts']}id_/{p['url']}"


def sha(name):
    return hashlib.sha256((DL / name).read_bytes()).hexdigest()


def pdf_text(data: bytes) -> str:
    with tempfile.TemporaryDirectory() as td:
        pdf = Path(td) / 'in.pdf'
        pdf.write_bytes(data)
        out = Path(td) / 'out.txt'
        subprocess.run(['pdftotext', '-layout', '-enc', 'UTF-8', str(pdf), str(out)], check=True)
        return out.read_text(encoding='utf-8')


def zip_pdf_text(name: str) -> str:
    z = zipfile.ZipFile(DL / name)
    pdfs = sorted(n for n in z.namelist() if n.lower().endswith('.pdf'))
    assert len(pdfs) == 1, (name, pdfs)
    return pdf_text(z.read(pdfs[0]))


def norm(s: str) -> str:
    s = s.replace(' ', ' ').replace('\f', '')
    s = s.replace('“', '"').replace('”', '"').replace('„', '"').replace('‘', "'").replace('’', "'")
    s = s.replace('—', '–')
    s = re.sub(r'[ \t]+', ' ', s)
    return s.strip()


HEAD_RE = re.compile(r'^\s*Artigo\s*(\d+)\s*\.?\s*º?\s*\.?\s*$')
INLINE_HEAD_RE = re.compile(r'^\s*Art\.\s*(\d+)\s*\.?\s*º\s*[-–]\s*(.*)$')
STRUCT_RE = re.compile(r'^\s*(PARTE|T[ÍI]TULO|CAP[ÍI]TULO|SEC[ÇC][ÃA]O|Sec[çc][ãa]o|Cap[íi]tulo|T[íi]tulo)\b')
ITEM_RE = re.compile(r'^(\d+\s*\)\s*\S|\d+\s*\.(?!\s*º)\s*\S|\d+\s*[-–]\s|[a-z]\s?\)\s?\S|[a-z]\s?\)$)')
PAGE_RE = re.compile(r'^\s*\d+\s*$')


def paragraphs(lines):
    """Join wrapped lines into paragraphs: a paragraph ends at . ; : ! ? » or " and items start new ones."""
    paras = []
    for raw in lines:
        t = norm(raw)
        if not t:
            continue
        if paras and not ITEM_RE.match(t) and not re.search(r'[.;:!?»"]$', paras[-1]):
            paras[-1] = paras[-1] + ' ' + t
        else:
            paras.append(t)
    return [re.sub(r' +', ' ', p) for p in paras]


def indent(line):
    return len(line) - len(line.lstrip(' '))


def split_constitution(text: str, start_re: str, end_re: str, sig_re: str, epigraphs: bool):
    """Split one constitution text into preamble, articles and a heading outline."""
    lines = text.replace('\r', '').split('\n')
    i0 = next(i for i, l in enumerate(lines) if re.search(start_re, l))
    i1 = next((i for i in range(i0, len(lines)) if re.search(end_re, lines[i])), len(lines)) if end_re else len(lines)
    lines = [l for l in lines[i0:i1] if not PAGE_RE.match(l)]
    pre, arts, outline = [], [], []
    cur = None          # current article: dict(num, epi, lines)
    heading = []        # structural heading lines collected before the next article
    in_head = False
    for l in lines:
        m = HEAD_RE.match(l)
        mi = INLINE_HEAD_RE.match(l) if not m else None
        if m or mi:
            num = int((m or mi).group(1))
            # centred unnumbered subheadings ("GOVERNO", "Assembleia Popular") just before an article header
            if cur is not None:
                sub = []
                while cur['lines'] and (not cur['lines'][-1].strip() or (
                        indent(cur['lines'][-1]) >= 15 and not ITEM_RE.match(norm(cur['lines'][-1]))
                        and not re.search(r'[.;:,!?»"]$', norm(cur['lines'][-1])))):
                    t = norm(cur['lines'].pop())
                    if t:
                        sub.insert(0, t)
                if sub:
                    heading.append(' '.join(sub))
            if heading:
                outline.append((' – '.join(heading), num))
                heading = []
            in_head = False
            cur = {'num': num, 'epi': None, 'lines': [], 'fresh': True}
            arts.append(cur)
            if mi:
                cur['lines'].append(mi.group(2))
                cur['fresh'] = False
            continue
        if STRUCT_RE.match(l) or (cur is None and re.match(r'^\s*CONSTITUI[ÇC][ÃA]O POL[ÍI]TICA\s*$', l)):
            if not re.match(r'^\s*CONSTITUI', l):
                in_head = True
                heading.append(norm(l))
            continue
        if in_head:
            t = norm(l)
            if t and heading:
                titled = ' – ' in heading[-1] or not re.match(r'^\S+\s+[IVXLC\dº.]+$', heading[-1])
                heading[-1] = heading[-1] + (' ' if titled else ' – ') + t
            continue
        if cur is None:
            pre.append(l)
            continue
        t = norm(l)
        if cur['fresh'] and t:
            cur['fresh'] = False
            if epigraphs and indent(l) >= 15 and not ITEM_RE.match(t) and not re.search(r'[.;:,]$', t):
                cur['epi'] = t
                continue
        cur['lines'].append(l)
    # cut the signatures / promulgation off the last article
    last = arts[-1]['lines']
    k = next((i for i, l in enumerate(last) if re.search(sig_re, l)), None)
    if k is not None:
        arts[-1]['lines'] = last[:k]
    return paragraphs(pre), arts, outline


def art_units(pre, arts, outline, preamble_drop=0):
    units = {}
    if pre:
        units['preambulo'] = {'label': 'Preâmbulo', 'kind': 'preamble', 'text': '# Preâmbulo\n' + '\n'.join(pre[preamble_drop:]) + '\n'}
    seen = set()
    for a in arts:
        n = a['num']
        key = f'art-{n:03d}'
        assert key not in seen, key
        seen.add(key)
        head = f"# Artigo {n}.º" + (f" ({a['epi']})" if a['epi'] else '')
        body = paragraphs(a['lines'])
        units[key] = {'label': f'Artigo {n}.º', 'kind': 'art', 'text': head + '\n' + '\n'.join(body) + '\n'}
    if outline:
        units['estrutura'] = {'label': 'Estrutura (partes, títulos, capítulos, secções)', 'kind': 'heading',
                              'text': ''.join(f'{h} [Artigo {n}.º]\n' for h, n in outline)}
    return units


def check_seq(units, name):
    nums = sorted(int(k[4:]) for k in units if k.startswith('art-'))
    missing = sorted(set(range(1, nums[-1] + 1)) - set(nums))
    return nums[-1], missing


# --------------------------------------------------------------------------- the five texts

SIG = r'^\s*(Assembleia Popular Nacional|Assembleia Nacional|Aprovada por)'
T75 = zip_pdf_text('Lei_17_07_1975.zip')
T80 = zip_pdf_text('L1_80.zip')
T82 = zip_pdf_text('L2_82.zip')
T87 = zip_pdf_text('L1_87.zip')
T90 = zip_pdf_text('L7_90Const.zip')
T03 = zip_pdf_text('L1_03.zip')

V75 = art_units(*split_constitution(T75, r'Durante cinco séculos o Povo do Arquipélago', r'^\s*Anexo\s*$', SIG, False))
V80 = art_units(*split_constitution(T80, r'^\s*1\. Durante cinco séculos', None, SIG, False))
V82 = art_units(*split_constitution(T82, r'^\s*1\. Durante cinco séculos', None, SIG, False))
V90 = art_units(*split_constitution(T90, r'Durante cinco séculos', None, SIG, True))
V03 = art_units(*split_constitution(T03, r'Durante cinco séculos', None, SIG, True))


# Lei 1/87: replaces Articles 47 to 51 of the 1982 text (each named in the law). Its first block amends
# alíneas b), i), r), t), u) of an article whose number the official copy omits ("Art.º - b)"), so it is not applied.
def lei_1_87(base):
    lines = T87.replace('\r', '').split('\n')
    i0 = next(i for i, l in enumerate(lines) if re.match(r'^\s*Art\.\s*47\.º', l))
    i1 = next(i for i, l in enumerate(lines) if re.match(r'^\s*Art,\s*2\.º', l))
    block = lines[i0:i1]
    arts, cur = [], None
    for l in block:
        m = re.match(r'^\s*Art\.\s*(\d+)\.º\s*-\s*(.*)$', l)
        if m:
            cur = {'num': int(m.group(1)), 'lines': [m.group(2)]}
            arts.append(cur)
        elif cur and not PAGE_RE.match(l):
            cur['lines'].append(l)
    out = dict(base)
    changed = []
    for a in arts:
        key = f"art-{a['num']:03d}"
        body = paragraphs(a['lines'])
        # the closing guillemet of the quoted amendment text ends Art. 51.º
        out[key] = {'label': f"Artigo {a['num']}.º", 'kind': 'art', 'text': f"# Artigo {a['num']}.º\n" + '\n'.join(body) + '\n'}
        changed.append(key)
    return out, changed, [a['num'] for a in arts]


V87, CH87, N87 = lei_1_87(V82)
assert N87 == [47, 48, 49, 50, 51], N87


def credits_all(prev, cur, law):
    keys = set(prev) | set(cur)
    return {k: [law] for k in sorted(keys) if prev.get(k, {}).get('text') != cur.get(k, {}).get('text')}


def delta(prev, cur):
    ch = {}
    for k in sorted(set(prev) | set(cur)):
        if k not in cur:
            ch[k] = None
        elif prev.get(k) != cur[k]:
            ch[k] = cur[k]
    return ch


PARL = 'http://www.parlamento.st/Legisl/leg%20Constit/leg_const.htm'
laws = {
    'constituicao-1975': {'label': 'Constituição Política de 1975', 'title': 'Constituição Política da República Democrática de São Tomé e Príncipe (aprovada em 5 de Novembro de 1975; Diário da República n.º 39, de 15 de Dezembro de 1975)',
                          'kind': 'law', 'enacted': '1975-11-05', 'published': '1975-12-15', 'url': wb_url('Lei_17_07_1975.zip'),
                          'temporary_until': None, 'restores': None, 'note': None},
    'lei-1-80': {'label': 'Lei n.º 1/80', 'title': 'Lei de revisão à Constituição de 1975 (Diário da República n.º 7, de 7 de Fevereiro de 1980)',
                 'kind': 'law', 'enacted': '1980-01-30', 'published': '1980-02-07', 'url': wb_url('L1_80.zip'),
                 'temporary_until': None, 'restores': None, 'note': None},
    'lei-2-82': {'label': 'Lei n.º 2/82', 'title': 'Aprova a Constituição Política do País (Diário da República n.º 35, de 31 de Dezembro de 1982)',
                 'kind': 'law', 'enacted': '1982-12-31', 'published': '1982-12-31', 'url': wb_url('L2_82.zip'),
                 'temporary_until': None, 'restores': None, 'note': None},
    'lei-1-87': {'label': 'Lei n.º 1/87', 'title': 'Emenda ao Capítulo III da Constituição Política (4.º Suplemento ao Diário da República n.º 13, de 31 de Dezembro de 1987)',
                 'kind': 'law', 'enacted': '1987-12-31', 'published': '1987-12-31', 'url': wb_url('L1_87.zip'),
                 'temporary_until': None, 'restores': None, 'note': None},
    'lei-7-90': {'label': 'Lei n.º 7/90', 'title': 'Constituição da República Democrática de São Tomé e Príncipe (Diário da República n.º 13, de 20 de Setembro de 1990)',
                 'kind': 'law', 'enacted': '1990-09-10', 'published': '1990-09-20', 'url': wb_url('L7_90Const.zip'),
                 'temporary_until': None, 'restores': None, 'note': None},
    'lei-1-2003': {'label': 'Lei n.º 1/2003', 'title': 'Lei de Revisão Constitucional: Constituição da República Democrática de São Tomé e Príncipe (Diário da República n.º 2, de 29 de Janeiro de 2003)',
                   'kind': 'law', 'enacted': '2003-01-25', 'published': '2003-01-29', 'url': wb_url('L1_03.zip'),
                   'temporary_until': None, 'restores': None, 'note': None},
}

V = [
    ('1975-11-05', 'Lei_17_07_1975.zip', V75, 'constituicao-1975',
     'The Constitution as approved on 5 Nov 1975 (in force on approval, art. 49), from the Assembleia Nacional\'s copy "Lei de 15 de Dezembro de 1975, D.R. nº 39".'),
    ('1980-02-07', 'L1_80.zip', V80, 'lei-1-80',
     'Full text as revised by Lei n.º 1/80, in force on publication (art. 70) in Diário da República n.º 7 of 7 Feb 1980.'),
    ('1982-12-31', 'L2_82.zip', V82, 'lei-2-82',
     'Full text approved by Lei n.º 2/82, in force on publication (art. 72) in Diário da República n.º 35 of 31 Dec 1982.'),
    ('1987-12-31', 'L1_87.zip', V87, 'lei-1-87',
     'Lei n.º 1/87 (in force on publication, art. 3.º, 4.º Suplemento ao DR n.º 13 of 31 Dec 1987) replaces Articles 47 to 51. Its amendment of alíneas b), i), r), t), u) of an article whose number the official copy omits is not applied.'),
    ('1990-09-20', 'L7_90Const.zip', V90, 'lei-7-90',
     'Full text of the 1990 Constitution (Lei n.º 7/90), in force on publication (art. 128) in Diário da República n.º 13 of 20 Sep 1990.'),
    ('2003-02-28', 'L1_03.zip', V03, 'lei-1-2003',
     'Full text revised by Lei n.º 1/2003, published in Diário da República n.º 2 of 29 Jan 2003 and in force on the thirtieth day after publication (art. 160.1). Under art. 160.2-3, Articles 80 to 82 applied only from the start of the next presidential term; until then a single Article 80 (quoted in art. 160.3) applied.'),
]

versions = []
prev = {}
for frm, src, units, law, note in V:
    cr = credits_all(prev, units, law)
    ver = {'from': frm, 'source_url': wb_url(src), 'sha256': sha(src)}
    if not prev:
        ver['units'] = units
    else:
        ver['changes'] = delta(prev, units)
    ver['credits'] = cr
    ver['note'] = note
    versions.append(ver)
    prev = units

decisions = [
    'No official legislation portal of São Tomé and Príncipe is online today (dre.gov.st, the electronic Diário da República, no longer resolves). Every text is read from the Assembleia Nacional\'s own former site, parlamento.st, through pinned Internet Archive id_ captures of February 2007.',
    'The Assembleia Nacional\'s page "Legislação Constitucional" (parlamento.st/Legisl/leg Constit/leg_const.htm, captured 2007-02-03) lists every constitutional law with its Diário da República issue and links one zipped PDF per law; those PDFs have a text layer and are the only texts used.',
    'Text is read with xpdf pdftotext 4.00 -layout -enc UTF-8. Page numbers and the title block are dropped; wrapped lines are joined into one paragraph per line, a paragraph ending at . ; : ! ? » or a quote, and numbered items and alíneas starting new lines.',
    'Typesetting is normalised once: non-breaking spaces, curly quotes to straight, em dash to en dash, runs of spaces collapsed. Spelling and typing slips in the official copies (for example "Princípios de lgualdade") are kept as published.',
    'One file per article (art-NNN). The article number and, from 1990 on, its epígrafe form the first line. Part, title, chapter and section headings are listed in constituicao/estrutura.md with the first article under each.',
    'Every revision from 1980 to 2003 republished the whole Constitution, so each version is the full official text of that law and every changed article is credited to it. Article numbers were reused with different content across revisions; the history shows such an article as changed, not moved.',
    '1975: the Assembleia Nacional\'s file holds the Lei Fundamental of 12 Jul 1975, the Constituição Política and, after it, an annex "Lei da Nacionalidade". Only the Constituição Política is used; the Lei Fundamental (a separate provisional act, superseded by the Constitution) and the nationality law are left out.',
    '1975: in force on its approval on 5 Nov 1975 under its own art. 49 ("entra imediatamente em vigor após a sua aprovação"), although the Diário da República issue (n.º 39) is dated 15 Dec 1975. In the official copy Article 4 is set inline as "Art.4º - 1. ..." and is read as Article 4.',
    'Lei n.º 1/80, 2/82, 1/87 and 7/90 each say they enter into force on publication; the in-force day used is the Diário da República date that the Assembleia Nacional\'s index and the 2003 text (art. 159) give for each.',
    'Lei n.º 1/87 replaces Articles 47 to 51 of the 1982 text in full, and those are applied. Its first block ("Art.º - b) ... u)") amends alíneas of an article whose number the official copy omits; that change is not applied rather than guessed, so the 1987 version shows that article in its 1982 wording. The 1990 revision replaced the whole text.',
    'Lei n.º 1/2003: the Assembleia Nacional\'s index and the 2003 text\'s own art. 159 give Diário da República n.º 2 of 29 Jan 2003. The government\'s copy (gov.st/data/filestorage/docs/constistp.pdf, captured 2007-08-13) says "n.º 1, de 26 de Janeiro de 2003" in the same place. The parliament\'s date is used; with art. 160.1 (in force on the thirtieth day after publication) the in-force day is 28 Feb 2003.',
    'Lei n.º 1/2003, art. 160.2-3: Articles 80 to 82 applied only from the start of the next presidential term, with a single transitional Article 80 meanwhile. The source gives no date for that term, so the record shows the full 2003 text from 28 Feb 2003 and says so in the version note; no typed applicability is set.',
    'The 2003 text was compared with the government\'s own copy (gov.st constistp.pdf, the same file the Assembleia Nacional published as parlamento.st/Lei/constistp.zip); see verify.py.',
    'No later amendment of the 2003 Constitution was found in any official source that could be read (parliament, government, ministry and DGRN sites and their archives). The record ends at the 2003 text and does not claim it is current today.',
]

country = {
    'code': 'ST', 'name': 'São Tomé and Príncipe', 'slug': 'sao-tome-and-principe', 'lang': 'pt',
    'tz': 'Africa/Sao_Tome', 'future_branch': 'futuro',
    'publisher': {'name': 'Assembleia Nacional de São Tomé e Príncipe', 'email': 'assembleia@parlamento.st.invalid'},
    'default_in_force_rule': {
        'text': 'Each constitutional text sets its own entry into force, which is used: 1975 art. 49 (on approval), Lei 1/80 art. 70, Lei 2/82 art. 72, Lei 1/87 art. 3.º and Lei 7/90 art. 128 (on publication), Lei 1/2003 art. 160.1 (thirtieth day after publication).',
        'source': 'http://www.parlamento.st/Legisl/leg%20Constit/leg_const.htm'},
    'licence_note': 'Official texts of the Diário da República de São Tomé e Príncipe, read from the copies published by the Assembleia Nacional (parlamento.st), as preserved by the Internet Archive.',
}

sources = [
    {'name': 'Assembleia Nacional de São Tomé e Príncipe: Legislação Constitucional (parlamento.st)',
     'url': PARL, 'retrieved': '2026-10-28', 'requests': 7,
     'licence': 'Official legislative texts of the Assembleia Nacional; the site states no licence.',
     'notes': 'Six zipped PDFs, one per constitutional law (1975, 1980, 1982, 1987, 1990, 2003), all with a text layer. Read through Internet Archive id_ captures pinned in sources.json (Feb 2007).'},
    {'name': 'Governo de São Tomé e Príncipe: constistp.pdf (gov.st)', 'url': 'http://www.gov.st/data/filestorage/docs/constistp.pdf',
     'retrieved': '2026-10-28', 'requests': 1, 'licence': 'Official text; the site states no licence.',
     'notes': 'The government\'s copy of the 2003 Constitution, captured 2007-08-13; used only to verify the 2003 text.'},
    {'name': 'Internet Archive Wayback Machine', 'url': 'https://web.archive.org/', 'retrieved': '2026-10-28', 'requests': 14,
     'licence': 'Internet Archive terms of use; the archived texts keep their publishers\' status.',
     'notes': 'CDX listings of parlamento.st, gov.st, dre.gov.st, stj.st and tc.st, and the id_ captures pinned in sources.json.'},
]

corpus = {
    'country': country, 'sources': sources, 'laws': laws,
    'acts': [{
        'slug': 'constituicao', 'short': 'CRDSTP',
        'title': 'Constituição da República Democrática de São Tomé e Príncipe',
        'url': PARL, 'first_law': 'constituicao-1975', 'earlier_laws': [],
        'versions': versions,
    }],
    'applies': [],
    'decisions': decisions,
    'ai_use': ['Claude Code with Claude Opus 5.5 (claude-opus-5-5) found the sources and wrote fetch.py and parse.py; no model wrote, read or corrected any legal text, and no model runs at build time.'],
}

if __name__ == '__main__':
    for nm, u in [('1975', V75), ('1980', V80), ('1982', V82), ('1987', V87), ('1990', V90), ('2003', V03)]:
        print(nm, len(u), 'units; last art and gaps:', check_seq(u, nm))
    tmp = HERE / 'corpus.json.tmp'
    tmp.write_text(json.dumps(corpus, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    os.replace(tmp, HERE / 'corpus.json')
    print('wrote corpus.json')
