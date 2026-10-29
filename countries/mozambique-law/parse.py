"""Builds scripts/mozambique-law/corpus.json and corpus.d/*.json from the cache only (no network).

    python -X utf8 scripts/mozambique-law/parse.py            # write the corpus
    python -X utf8 scripts/mozambique-law/parse.py --report   # also print how the 2004 and 2018 texts line up

Constituição da República de Moçambique (CRM), two versions, both born-digital PDFs with a text layer (no OCR):
- 2005-01-21: the 2004 text as approved on 16 Nov 2004, Assembleia da República PDF
  (parlamento.mz/wp-content/uploads/2022/06/Constituicao-da-Republica.pdf); in force 21 Jan 2005 (Conselho
  Constitucional, "Historial": "tendo entrado em vigor a 21 de Janeiro de 2005"; WIPO Lex 21389 agrees).
- 2018-06-12: the text as revised by Lei n.º 1/2018 (published and in force 12 Jun 2018, WIPO Lex 21389), from the
  Assembleia da República Secretariat's compilation "Legislação Básica" (2022), PDF pages 14-156.

The PDF text is split into paragraphs, then into the preamble and one unit per article (art-001 ...). Title,
chapter and section headings and the closing approval and signature formula are not units.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF: reads the PDF text layer only

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'

CRM_2004 = 'https://www.parlamento.mz/wp-content/uploads/2022/06/Constituicao-da-Republica.pdf'
LEG_BASICA = 'https://www.parlamento.mz/wp-content/uploads/2022/08/Legislacao_Basica.pdf'
CC_HISTORIAL = 'https://cconstitucional.org.mz/historial/'
WIPO_21389 = 'https://www.wipo.int/wipolex/en/legislation/details/21389'
CC_CRM_PAGE = 'https://cconstitucional.org.mz/constituicao-da-republica/'
LEI_26_2007_SCAN = 'https://cconstitucional.org.mz/wp-content/uploads/2023/12/Lei26-2007de16deNovembroalteraoartigo304daConstituicaodaRepublica.pdf'
CIP_2023 = 'https://www.cipmoz.org/wp-content/uploads/2023/08/Descentralizacao-entenda-como-a-Frelimo-forcou-a-revisao-da-Constituicao-.pdf'
FAOLEX_2018 = 'https://faolex.fao.org/docs/pdf/moz117331POR.pdf'


def cached(url: str) -> bytes:
    p = CACHE / hashlib.sha256(url.encode()).hexdigest()
    if not p.exists():
        raise SystemExit(f'not cached (run fetch.py --all): {url}')
    return p.read_bytes()


def sha(url: str) -> str:
    return hashlib.sha256(cached(url)).hexdigest()


def norm(s: str) -> str:
    """Publisher typesetting normalised once: spaces, quotes, dashes."""
    s = s.replace('\xa0', ' ').replace('­', '').replace('ﬁ', 'fi').replace('ﬂ', 'fl')
    s = re.sub('[‘’‚′´`]', "'", s)
    s = re.sub('[“”„″«»]', '"', s)
    s = re.sub('[‐‑−]', '-', s)  # hyphens
    s = re.sub('[‒–—―]', '–', s)  # dashes: one form, the en dash
    s = s.replace('…', '...')
    s = re.sub(r'\s+', ' ', s).strip()
    # The 2022 compilation sets compound hyphens with spaces ("Procurador - Geral", "decretos - lei"); the hyphen
    # (not the dash) between two word characters is closed up.
    s = re.sub(r'(?<=\w) ?- ?(?=\w)', '-', s)
    return s


def join(lines: list[str]) -> str:
    """One paragraph from its lines; a line ending in a hyphen ("bem-" / "estar") runs on without a space."""
    out = ''
    for l in lines:
        l = l.strip()
        out += l if out.endswith('-') else (' ' + l if out else l)
    return out


ENUM = re.compile(r'^(\d+\.\s|[a-z]\d*\)(\s|$)|Artigo\s+\d+\s*$|\()')
HEAD = re.compile(r'^(TÍTULO|CAPÍTULO|SECÇÃO|SUBSECÇÃO)\s+[IVXLC]+\b')
ART = re.compile(r'^Artigo\s+(\d+)\s*$')
ITEM = re.compile(r'^(\d+\.\s|[a-z]\d*\)(\s|$))')
BARE_ITEM = re.compile(r'^[a-z]\d*\)$')  # "f)" alone on a line, its words on the next


def lines_2004() -> list[list[str]]:
    """Paragraphs of the 2004 PDF: blank lines separate them; the page number heads each page from page 2."""
    doc = fitz.open(stream=cached(CRM_2004), filetype='pdf')
    paras: list[list[str]] = []
    cur: list[str] = []
    for i, page in enumerate(doc):
        ls = page.get_text().split('\n')
        while ls and not ls[0].strip():
            ls.pop(0)
        while ls and not ls[-1].strip():  # whether a paragraph ends at the page foot is decided on the next page
            ls.pop()
        if i and ls and ls[0].strip().isdigit():
            ls.pop(0)
            while ls and not ls[0].strip():
                ls.pop(0)
        first = True
        for raw in ls:
            t = raw.strip()
            if not t:
                if cur:
                    paras.append(cur)
                    cur = []
                first = False
                continue
            if first and cur:
                # a paragraph running on from the previous page continues only if that page's last line did not
                # end a sentence and this line does not start a new item
                prev = cur[-1]
                if prev.endswith(('.', ':', ';', ')')) or ENUM.match(t) or HEAD.match(t) or HEAD.match(cur[0]):
                    paras.append(cur)
                    cur = []
            elif cur and ITEM.match(t):
                # list items ("a) ...", "1. ...") follow each other without a blank line
                paras.append(cur)
                cur = []
            first = False
            cur.append(t)
    if cur:
        paras.append(cur)
    return paras


def lines_2018() -> list[list[str]]:
    """Paragraphs of the 2018 text in the AR compilation: no blank lines, so a line that wraps ends in a space;
    a line without one ends its paragraph. Page footers ("<n>" / "Constituição da República") are dropped."""
    doc = fitz.open(stream=cached(LEG_BASICA), filetype='pdf')
    raw: list[str] = []
    for i in range(13, 156):
        ls = [l for l in doc[i].get_text().split('\n') if l.strip()]
        # the running footer is a page number and "Constituição da República", in either order
        drop = set()
        for j, l in enumerate(ls):
            if l.strip() == 'Constituição da República':
                for n in (j - 1, j + 1):
                    if 0 <= n < len(ls) and ls[n].strip().isdigit():
                        drop |= {j, n}
        raw.extend(l for j, l in enumerate(ls) if j not in drop)
    paras: list[list[str]] = []
    cur: list[str] = []
    for j, l in enumerate(raw):
        t = l.strip()
        if cur and (ENUM.match(t) or HEAD.match(t) or ART.match(cur[-1].strip())):
            paras.append(cur)
            cur = []
        cur.append(t)
        if ART.match(t) or (not l.endswith(' ') and not t.endswith('-') and not BARE_ITEM.match(t)):
            paras.append(cur)
            cur = []
    if cur:
        paras.append(cur)
    return paras


def units(paras: list[list[str]], last_article: int) -> dict:
    """Preamble and articles. Headings are skipped up to the next article; the text ends at the approval formula."""
    out: dict[str, dict] = {}
    key = None
    body: list[str] = []
    skipping = False

    def close():
        if key:
            if 'text' in out[key]:
                raise SystemExit(f'{key} twice')
            out[key]['text'] = '\n'.join(body) + '\n'

    for p in paras:
        text = norm(join(p))
        if not text:
            continue
        if text in ('CONSTITUIÇÃO DA REPÚBLICA',) and key is None:
            continue
        if text == 'Preâmbulo' and key is None:
            key, body = 'preambulo', ['# Preâmbulo']
            out[key] = {'label': 'Preâmbulo', 'kind': 'preamble'}
            continue
        m = re.fullmatch(r'Artigo (\d+)(?: (\([^()]+\)))?', text)  # the 2004 PDF keeps the heading in the same block
        if m:
            close()
            n = int(m.group(1))
            key, body, skipping = f'art-{n:03d}', [f'# Artigo {n}' + (f' {m.group(2)}' if m.group(2) else '')], False
            out[key] = {'label': f'Art. {n}', 'kind': 'art'}
            continue
        if HEAD.match(text):
            close()
            key, skipping = None, True
            continue
        if text.startswith('Aprovada pela Assembleia da República'):
            if key != f'art-{last_article:03d}':
                raise SystemExit(f'approval formula after {key}')
            close()
            key = None
            break
        if skipping or key is None:
            continue
        if len(body) == 1 and key.startswith('art-') and text.startswith('(') and text.endswith(')'):
            body[0] += f' {text}'  # the article's heading, "(Soberania e legalidade)"
            continue
        body.append(text)
    else:
        raise SystemExit('approval formula not found')
    nums = sorted(int(k[4:]) for k in out if k.startswith('art-'))
    if nums != list(range(1, last_article + 1)):
        raise SystemExit(f'articles missing or extra: {sorted(set(range(1, last_article + 1)) - set(nums))}')
    return {k: out[k] for k in sorted(out, key=lambda k: (k != 'preambulo', k))}


def heading(u: dict) -> str:
    return u['text'].split('\n', 1)[0].split(' ', 3)[-1] if '(' in u['text'].split('\n', 1)[0] else ''


def report(v04: dict, v18: dict) -> None:
    """Line the two texts up by article heading: how many articles kept their words under a new number."""
    by_head = {}
    for k, u in v18.items():
        by_head.setdefault(heading(u), []).append(k)
    same = moved = changed = 0
    for k, u in v04.items():
        body = u['text'].split('\n', 1)[1] if '\n' in u['text'] else ''
        cands = by_head.get(heading(u), [])
        hit = [c for c in cands if v18[c]['text'].split('\n', 1)[1] == body]
        if k in v18 and v18[k]['text'] == u['text']:
            same += 1
        elif hit:
            moved += 1
        else:
            changed += 1
            print('changed or gone:', k, heading(u)[:60])
    print(f'2004 -> 2018: {same} unchanged in place, {moved} same words under a new number, {changed} other')


PUBLISHER = {'name': 'Assembleia da República de Moçambique', 'email': 'publicacoes@parlamento.invalid'}


def build() -> tuple[dict, dict, dict, dict]:
    v04 = units(lines_2004(), 306)
    v18 = units(lines_2018(), 313)
    credits = {k: ['lei-2018-1'] for k in sorted(set(v04) | set(v18))
               if v04.get(k, {}).get('text') != v18.get(k, {}).get('text')}
    country = {
        'code': 'MZ', 'name': 'Mozambique', 'slug': 'mozambique', 'lang': 'pt', 'tz': 'Africa/Maputo',
        'future_branch': 'futuro',
        'publisher': PUBLISHER,
        'default_in_force_rule': {
            'text': 'Lei n.º 6/2006 (Boletim da República): os actos normativos entram em vigor no prazo neles '
                    'fixado ou, na falta de fixação, 15 dias após a publicação. Each law here states its own '
                    'commencement, which is used as given.',
            'source': 'https://www.inm.gov.mz'},
        'licence_note': 'Texts published by the Assembleia da República (parlamento.mz). No licence is stated on the '
                        'site; official legislative texts. This repository is private.',
    }
    sources = [
        {'name': 'Assembleia da República: Constituição da República (2004, as approved)', 'url': CRM_2004,
         'retrieved': '2026-10-28', 'requests': 1, 'sha256': sha(CRM_2004),
         'licence': 'No licence stated (Assembleia da República)',
         'notes': 'Born-digital PDF (Word), 97 pages, 306 articles: the text approved on 16 November 2004.'},
        {'name': 'Assembleia da República, Secretariado-Geral: Legislação Básica (2022)', 'url': LEG_BASICA,
         'retrieved': '2026-10-28', 'requests': 1, 'sha256': sha(LEG_BASICA),
         'licence': 'No licence stated (Assembleia da República)',
         'notes': 'Born-digital compilation; PDF pages 14-156 hold the Constitution as revised by Lei n.º 1/2018 '
                  '(313 articles). It prints "Promulgado, a 16 de Novembro de 2014" (sic) under the 2004 approval '
                  'formula; the formula is not a unit here.'},
        {'name': 'Conselho Constitucional: Historial', 'url': CC_HISTORIAL, 'retrieved': '2026-10-28', 'requests': 1,
         'sha256': sha(CC_HISTORIAL), 'licence': 'No licence stated',
         'notes': '"Em 2004, uma nova Constituição da República é aprovada tendo entrado em vigor a 21 de Janeiro '
                  'de 2005". Its PDFs of the 1990, 2004 and 2018 texts and of Lei n.º 26/2007 are image scans '
                  '(not used: no OCR).'},
        {'name': 'WIPO Lex: Constitution of the Republic of Mozambique (details 21389)', 'url': WIPO_21389,
         'retrieved': '2026-10-28', 'requests': 1, 'sha256': sha(WIPO_21389), 'licence': 'WIPO Lex terms of use',
         'notes': 'Entry into force 21 January 2005; adopted 16 November 2004; Lei n.º 1/2018 "promulgated on June '
                  '11, 2018, and was published and entered into force on June 12, 2018".'},
    ]
    laws = {
        'crm-2004': {'label': 'Constituição da República (2004)', 'title': 'Constituição da República de Moçambique',
                     'kind': 'law', 'enacted': '2004-11-16', 'published': None, 'url': CRM_2004,
                     'temporary_until': None, 'restores': None, 'note': None},
        'lei-2018-1': {'label': 'Lei n.º 1/2018', 'title': 'Lei de Revisão Pontual da Constituição da República',
                       'kind': 'law', 'enacted': '2018-06-11', 'published': '2018-06-12', 'url': WIPO_21389,
                       'temporary_until': None, 'restores': None, 'note': None},
    }
    const = {
        'slug': 'constituicao', 'short': 'CRM', 'title': 'Constituição da República de Moçambique',
        'url': CC_CRM_PAGE, 'first_law': 'crm-2004', 'earlier_laws': [],
        'versions': [
            {'from': '2005-01-21', 'source_url': CRM_2004, 'sha256': sha(CRM_2004), 'units': v04, 'credits': {},
             'note': 'The text approved on 16 November 2004, in force from 21 January 2005 (art. 306: the day after '
                     'the 2004 general election results were validated and proclaimed).'},
            {'from': '2018-06-12', 'source_url': LEG_BASICA, 'sha256': sha(LEG_BASICA), 'units': v18,
             'credits': credits,
             'note': 'The text as revised by Lei n.º 1/2018 and republished with it (art. 304(2) of the revised '
                     'text), from the Assembleia da República compilation. The revision rewrites the provisions on '
                     'provincial, district and local government and renumbers most articles from art. 140 on (306 '
                     'articles become 313), so many files change only because a different article now has that '
                     'number.'},
        ],
    }
    decisions_common = [
        'Only born-digital PDFs with a text layer are read; scanned Boletim da República issues and scanned PDFs '
        'are left out and named (no OCR).',
        'Text normalisation: NBSP and runs of spaces collapsed, curly quotes to straight, en and em dashes to "-", '
        'page numbers and running footers dropped, lines joined into paragraphs (blank-line separated in the 2004 '
        'PDF; in the 2022 compilation a wrapped line ends in a space and a new item starts with its number or '
        'letter).',
        'Units: the preamble and one file per article (art-NNN), the article heading on the first line. Title, '
        'chapter and section headings and the closing approval and signature formula are not units.',
    ]
    decisions_const = [
        'CRM v1 from 2005-01-21 (Conselho Constitucional, Historial; WIPO Lex), the 2004 text from the Assembleia '
        'da República PDF, credited to the Constitution as approved on 2004-11-16.',
        'CRM v2 from 2018-06-12 (WIPO Lex: Lei n.º 1/2018 published and in force on 12 June 2018), the revised text '
        'from the Assembleia da República compilation "Legislação Básica" (2022). Lei n.º 1/2018 republished the '
        'whole text (its art. 304(2) of the new text), so every provision that differs is credited to it, '
        'including articles that differ only because the revision renumbered them.',
        'LEFT OUT, Lei n.º 26/2007 (16 Nov 2007, alters art. 304 of the 2004 text, "Assembleias provinciais"): '
        'the only copy found is an image scan (Conselho Constitucional), so its wording is unknown and no version '
        'shows it. From 2007 until 2018 art-304 therefore reads as in 2004. The 2018 revision has no counterpart '
        'of that article (art. 304 of the 2018 text is "Alterações constitucionais"), so the 2018 commit is right '
        'for the text it produces.',
        'LEFT OUT, the 2023 revision of art. 311(3) (approved by the Assembleia da República on 3 Aug 2023 and '
        'promulgated on 4 Aug 2023, per Centro de Integridade Pública): no law number, Boletim da República issue '
        'or text-layer copy was found. So the last version here is not today\'s text, and this act is not marked '
        'verified (no corpus.d/10-constituicao.PUBLISH).',
        'The official republication of 2018 (BR I Série n.º 115, 2.º suplemento, 12 Jun 2018) was found only as a '
        'scan with an automatic OCR layer (FAOLEX), so it is not used.',
    ]
    ai = ['Claude Code with Claude Opus 5.5 (claude-opus-5-5) wrote fetch.py and parse.py and chose the sources. '
          'No model wrote or altered legal text, and no model runs at build time.']
    corpus = {'country': country, 'sources': sources, 'laws': {}, 'acts': [], 'applies': [],
              'decisions': decisions_common, 'ai_use': ai}
    part = {'laws': laws, 'acts': [const], 'decisions': decisions_const}
    return corpus, part, v04, v18


def write(path: Path, data: dict) -> None:
    path.parent.mkdir(exist_ok=True)
    tmp = path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    tmp.replace(path)


def main(argv: list[str]) -> None:
    corpus, part, v04, v18 = build()
    write(HERE / 'corpus.json', corpus)
    write(HERE / 'corpus.d' / '10-constituicao.json', part)
    print(f'constituicao: {len(v04)} units (2004), {len(v18)} units (2018), '
          f'{len(part["acts"][0]["versions"][1]["credits"])} credited to Lei n.º 1/2018')
    if '--report' in argv:
        report(v04, v18)


if __name__ == '__main__':
    main(sys.argv[1:])
