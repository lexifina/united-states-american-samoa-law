"""Reads only .cache/ and writes corpus.json for Suriname (gitlaw-SR). See scripts/gitlaw_common/SCHEMA.md.

    python -X utf8 scripts/suriname-law/parse.py

PDF text is read with PyMuPDF from the official PDFs' own text layer (no OCR, no model). Body text is told apart from
footnote references, footnotes and page furniture by font size, as laid out by the publisher. Deterministic: the same
cache gives the same bytes.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
RETRIEVED = '2026-10-28'

DNA_GW_1992 = 'https://www.dna.sr/media/vyjchhar/grondwet-suriname.pdf'
GOV_GW_1992 = 'https://gov.sr/wp-content/uploads/2023/09/grondwet_suriname.pdf'
SB_2025_15 = ('https://sris.sr/wp-content/uploads/2025/04/RESOLUTIE-van-6-februari-2025-no.14.22724-houdende-plaatsing-'
              'staatsblad-republiek-suriname-thans-geldende-tekst-grondwet-rep-sur-S.B.-2025-no.-15.pdf')
SB_2023_157 = 'https://www.dna.sr/media/o4jhmh2z/sb_2023___157.pdf'


def cached(url: str) -> Path:
    p = CACHE / hashlib.sha256(url.encode('utf-8')).hexdigest()
    if not p.exists():
        raise SystemExit(f'not in cache (run fetch.py): {url}')
    return p


def sha(url: str) -> str:
    return hashlib.sha256(cached(url).read_bytes()).hexdigest()


# ---------------------------------------------------------------- text normalisation

TRANS = str.maketrans({' ': ' ', '‘': "'", '’': "'", '‚': "'", '“': '"', '”': '"',
                       '„': '"', '–': '-', '—': '-', '‑': '-', '­': '', '\t': ' ',
                       '': '-', '•': '-'})


def norm(s: str) -> str:
    s = s.translate(TRANS)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()


# ---------------------------------------------------------------- PDF rows

def pdf_rows(path: Path, body_min: float = 11.0) -> tuple[list[dict], dict[str, str]]:
    """Rows of body text, each {page, y, x, text, refs}, plus the footnotes {number: text} (numbers are per document
    and may repeat across pages, so keys are '<page>:<n>')."""
    doc = fitz.open(path)
    rows, notes = [], {}
    for pno, page in enumerate(doc):
        lines = []
        for b in page.get_text('dict')['blocks']:
            for l in b.get('lines', []):
                spans = [s for s in l['spans'] if s['text']]
                if spans:
                    lines.append((round(l['bbox'][1], 1), round(l['bbox'][0], 1), spans))
        # merge lines that sit on the same baseline (the "1." marker and its text are separate lines)
        lines.sort(key=lambda t: (t[0], t[1]))
        merged: list[list] = []
        for y, x, spans in lines:
            if merged and abs(merged[-1][0] - y) < 3.5:
                merged[-1][2].extend(spans)
                merged[-1][1] = min(merged[-1][1], x)
            else:
                merged.append([y, x, list(spans)])
        for y, x, spans in merged:
            spans.sort(key=lambda s: s['bbox'][0])
            body = [s for s in spans if s['size'] >= body_min and not s['font'].startswith('Courier')]
            small = [s for s in spans if s['size'] < body_min and not s['font'].startswith('Courier')]
            if small and not body:
                # a footnote line: S.B. 2025 no. 15 sets some footnote numbers in Courier (note 60, art. 163)
                small = [s for s in spans if s['size'] < body_min]
            text = ''.join(s['text'] for s in body)
            if norm(text):
                refs = [norm(s['text']) for s in small if norm(s['text']).isdigit()]
                rows.append({'page': pno, 'y': y, 'x': x, 'text': text, 'refs': refs,
                             'bold': all(s['flags'] & 16 for s in body if s['text'].strip())})
            elif small:
                t = norm(''.join(s['text'] for s in small))
                m = re.match(r'^(\d+)\s*(.*)$', t)
                if m and m.group(2):
                    notes[f'{pno}:{m.group(1)}'] = m.group(2)
                elif m:
                    notes[f'{pno}:{m.group(1)}'] = ''
                elif t and notes:
                    last = list(notes)[-1]
                    notes[last] = (notes[last] + ' ' + t).strip()
    # a footnote whose number and text fell on separate rows: "4" then "Gew. bij ..."
    return rows, notes


# ---------------------------------------------------------------- the Grondwet

ART = re.compile(r'^Artikel\s+(\d+)\s*([a-z])?\s*$')
HEADING = re.compile(r'^[A-Z0-9ËÉÈÏÖÜ .,\'"/()&-]+$')
MARKER = re.compile(r'^(\d+[a-z]?\.|[a-z]\.|[a-z]\)|\d+[a-z]?\)|-)(\s|$)')


def joinlines(parts: list[str]) -> str:
    out = ''
    for p in parts:
        p = norm(p)
        if not p:
            continue
        if not out:
            out = p
        elif re.search(r'[a-zà-ÿ]-$', out) and re.match(r'^(en|of)\b', p):
            out += ' ' + p              # "uit- en inwendige", "hoofd- of werkelijk": a real hyphen before "en"/"of"
        elif re.search(r'[a-zà-ÿ]-$', out) and re.match(r'^[a-zà-ÿ]', p):
            out = out[:-1] + p          # a word the typesetter broke at the line end
        elif re.search(r'[a-zà-ÿ]-$', out) and re.match(r'^[A-Z]', p):
            out += p                    # "Vice-" / "President": a compound with a capital keeps its hyphen
        elif re.search(r'[A-Z]{2}-$', out) and re.match(r'^[A-Z]{2}', p):
            out = out[:-1] + p          # "VOLKSRAAD-" / "PLEGING": a capitalised word broken at the line end
        else:
            out += ' ' + p
    return out


def grondwet(url: str, first_page: int, footnote_law: dict) -> tuple[dict, dict, list[str]]:
    """Units of one consolidated Grondwet text, and for each unit the laws its footnotes name."""
    rows, notes = pdf_rows(cached(url))
    units: dict[str, dict] = {}
    credits: dict[str, set] = {}
    headings: list[str] = []
    cur = None            # current unit key
    paras: list[list[str]] = []
    last = None           # last row
    started = False

    def flush():
        if cur and paras:
            lines = [joinlines(p) for p in paras]
            lines = [l for l in lines if l]
            # "1." on its own line before its text: glue a bare marker to the next line
            fixed = []
            for l in lines:
                if fixed and re.fullmatch(r'(\d+[a-z]?\.|[a-z]\.)', fixed[-1]):
                    fixed[-1] = fixed[-1] + ' ' + l
                else:
                    fixed.append(l)
            units[cur]['body'] = fixed

    for r in rows:
        if r['page'] < first_page:
            continue
        t = norm(r['text'])
        if re.match(r'^\d{4} -\s*\d+\s*- No\. \d+$', t) or re.fullmatch(r'-?\s*\d+\s*-?', t):
            continue                                    # page header / page number
        if not started:
            if t.startswith('Preambule'):
                started = True
                cur = 'preambule'
                units[cur] = {'label': 'Preambule', 'head': '# Preambule'}
                paras = []
                credits[cur] = set(r['refs'])
                last = r
            continue
        if t.startswith('Gegeven te Paramaribo') or t.startswith('MEMORIE VAN TOELICHTING'):
            break
        m = ART.match(t)
        if m:
            flush()
            n, suf = int(m.group(1)), m.group(2) or ''
            cur = f'art-{n:03d}{suf}'
            units[cur] = {'label': f'Artikel {n}{suf}', 'head': f'# Artikel {n}{suf}'}
            credits[cur] = set(r['refs'])
            paras = []
            last = r
            continue
        if HEADING.match(t) and re.search(r'[A-Z]{4}', t) and cur != 'preambule' or \
                (cur == 'preambule' and re.match(r'^HOOFDSTUK\b', t)):
            flush()
            if cur == 'preambule':
                cur = None
            headings.append(t)
            for ref in r['refs']:
                credits.setdefault('indeling', set()).add(ref)
            cur_heading = True
            last = r
            # text after a heading belongs to no article until the next "Artikel"
            if cur and cur.startswith('art-'):
                units[cur]['heading_after'] = True
            cur = None if cur != 'preambule' else cur
            paras = []
            continue
        if cur is None:
            last = r
            continue
        credits[cur].update(r['refs'])
        newpara = (not paras or last is None or MARKER.match(t) is not None
                   or r['page'] == last['page'] and r['y'] - last['y'] > 22)
        if newpara:
            paras.append([r['text']])
        else:
            paras[-1].append(r['text'])
        last = r
    flush()
    # footnote numbers -> laws. Footnote keys are '<page>:<n>'; a reference on page p names a note on p or p+1.
    note_by_n: dict[str, list[str]] = {}
    for k, v in notes.items():
        note_by_n.setdefault(k.split(':')[1], []).append(v)
    out_units, out_notes = {}, {}
    for k, u in units.items():
        body = u.get('body', [])
        out_units[k] = {'label': u['label'], 'kind': 'preamble' if k == 'preambule' else 'art',
                        'text': '\n'.join([u['head']] + body) + '\n'}
        laws = set()
        for ref in credits.get(k, ()):
            for v in note_by_n.get(ref, []):
                for pat, law in footnote_law.items():
                    if re.search(pat, v):
                        laws.add(law)
        out_notes[k] = sorted(laws)
    out_units['indeling'] = {'label': 'Indeling (hoofdstukken en afdelingen)', 'kind': 'structure',
                             'text': '# Indeling\n' + '\n'.join(headings) + '\n'}
    return out_units, out_notes, headings


FOOTNOTE_LAW = {r'1992\s*no\.?\s*38': 'sb-1992-38', r'2023\s*no\.?\s*157': 'sb-2023-157'}


def relayout(old: str, new: str) -> str | None:
    """The words of `old` broken into lines where `new` breaks them. The two publishers set paragraph breaks
    differently (the 1992 consolidation runs oath sentences and the preamble's clauses together); this keeps such
    layout differences out of the history. Returns None when a break of `new` falls inside changed words."""
    oh, *ob = old.rstrip('\n').split('\n')
    nh, *nb = new.rstrip('\n').split('\n')
    if oh != nh:
        return None
    ow = ' '.join(ob).split(' ')
    nw, breaks = [], []
    for line in nb:
        if nw:
            breaks.append(len(nw))
        nw.extend(line.split(' '))
    sm = difflib.SequenceMatcher(None, ow, nw, autojunk=False)
    nmap = {}
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            for d in range(i2 - i1):
                nmap[j1 + d] = i1 + d
    cuts = []
    for b in breaks:
        # a break maps when the word before it (or, failing that, the word after it) is unchanged
        if b - 1 in nmap:
            cuts.append(nmap[b - 1] + 1)
        elif b in nmap:
            cuts.append(nmap[b])
        else:
            return None
    if cuts != sorted(set(cuts)) or (cuts and (cuts[0] <= 0 or cuts[-1] >= len(ow))):
        return None
    lines, prev = [], 0
    for c in cuts + [len(ow)]:
        lines.append(' '.join(ow[prev:c]))
        prev = c
    return '\n'.join([oh] + lines) + '\n'


def word_changes(old: str, new: str) -> list[str]:
    """Plain list of the word-level differences between two texts of one unit, for the decisions."""
    ow, nw = old.split(), new.split()
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ow, nw, autojunk=False).get_opcodes():
        if tag == 'equal':
            continue
        a, b = ' '.join(ow[i1:i2]), ' '.join(nw[j1:j2])
        out.append(f'"{a}" -> "{b}"' if a and b else (f'adds "{b}"' if b else f'drops "{a}"'))
    return out


LAW_2023 = 'sb-2023-157'
SB_2025_ISSUED = '2025-02-07'     # "Uitgegeven te Paramaribo, de 7e februari 2025" (S.B. 2025 no. 15, page 1)


def build_grondwet() -> tuple[dict, list[str]]:
    u92, n92, _ = grondwet(DNA_GW_1992, 0, FOOTNOTE_LAW)
    u25, n25, _ = grondwet(SB_2025_15, 2, FOOTNOTE_LAW)
    report: list[str] = []
    # cross-check: the gov.sr copy of the 1992 consolidation
    ug, _, _ = grondwet(GOV_GW_1992, 0, FOOTNOTE_LAW)
    for k in sorted(set(u92) | set(ug)):
        a, b = u92.get(k, {}).get('text', ''), ug.get(k, {}).get('text', '')
        if a != b:
            ch = word_changes(a, b)
            report.append(f'Grondwet {k}: the gov.sr copy of the 1992 consolidation differs from the dna.sr copy '
                          f'used here' + (f' ({"; ".join(ch)})' if ch else ' (paragraph layout only)') + '.')
    if set(u92) != set(u25):
        raise SystemExit(f'unit sets differ: {sorted(set(u92) ^ set(u25))}')
    by_2023 = sorted(k for k in u25 if LAW_2023 in n25.get(k, []))
    if by_2023 != ['art-060', 'art-061', 'art-161', 'art-163']:
        raise SystemExit(f'unexpected S.B. 2023 no. 157 footnotes: {by_2023}')
    # 1992: the dna.sr consolidation, with the 2025 paragraph breaks where the words allow
    v1u = {}
    for k, u in u92.items():
        t = u['text']
        if k not in by_2023 and t != u25[k]['text']:
            r = relayout(t, u25[k]['text'])
            if r is not None:
                t = r
            else:
                report.append(f'Grondwet {k}: 1992 paragraph breaks kept (a 2025 break falls inside changed words).')
        v1u[k] = dict(u, text=t)
    # 2023-10-27: the 1992 text with the four articles S.B. 2023 no. 157 rewrote, in their S.B. 2025 no. 15 wording
    v2u = dict(v1u)
    for k in by_2023:
        v2u[k] = u25[k]
    # 2025-02-07: S.B. 2025 no. 15 in full; whatever else differs has no amending law and stays uncredited
    v3u = u25
    editorial = []
    for k in sorted(v3u):
        if v2u[k]['text'] != v3u[k]['text']:
            ch = word_changes(v2u[k]['text'], v3u[k]['text'])
            editorial.append(k)
            report.append(f'Grondwet {k}: S.B. 2025 no. 15 differs from the 1992 consolidation with no amending law: '
                          + ('; '.join(ch) if ch else 'paragraph layout only') + '. Left uncredited (publisher).')
    marked92 = ', '.join(k for k in sorted(n92) if 'sb-1992-38' in n92[k])
    v1 = {'from': '1992-04-08', 'source_url': DNA_GW_1992, 'sha256': sha(DNA_GW_1992), 'units': v1u, 'credits': {},
          'note': ('Oldest text available online: the Grondwet of 1987 (S.B. 1987 no. 116) as amended by the Wet van '
                   '8 april 1992 (S.B. 1992 no. 38), in the consolidation published by De Nationale Assemblee. '
                   'Its footnotes mark these units as changed, inserted or repealed by S.B. 1992 no. 38: '
                   + marked92 + '.')}
    v2 = {'from': '2023-10-27', 'source_url': SB_2025_15, 'sha256': sha(SB_2025_15), 'units': v2u,
          'credits': {k: [LAW_2023] for k in by_2023},
          'note': ('Arts. 60, 61, 161 and 163 as rewritten by S.B. 2023 no. 157 (in force the day after its '
                   'afkondiging on 26 October 2023), in the wording of the official consolidation S.B. 2025 no. 15, '
                   'which footnotes exactly these four articles "Gew. bij S.B. 2023 no. 157". The amending act '
                   'itself is a scanned PDF with no text layer. All other units are unchanged from 1992.')}
    v3 = {'from': SB_2025_ISSUED, 'source_url': SB_2025_15, 'sha256': sha(SB_2025_15), 'units': v3u, 'credits': {},
          'note': ('The official consolidation placed in the Staatsblad by Resolutie of 6 February 2025 no. 14.227/24 '
                   '(S.B. 2025 no. 15, uitgegeven 7 February 2025). It states the Grondwet as amended by S.B. 1992 '
                   'no. 38 and S.B. 2023 no. 157 only, yet differs from the 1992 consolidation in '
                   + str(len(editorial)) + ' further units (spelling, punctuation, numbering, one omitted word). '
                   'No amending law explains these, so they are committed by the publisher, unexplained.')}
    act = {'slug': 'grondwet', 'short': 'Grondwet',
           'title': 'Grondwet van de Republiek Suriname',
           'url': 'https://www.dna.sr/wetgeving/surinaamse-wetten/geldende-teksten-t-m-2005/grondwet-van-de-republiek-suriname/',
           'first_law': None, 'earlier_laws': ['sb-1987-116', 'sb-1992-38'], 'versions': [v1, v2, v3]}
    return act, report


LAWS = {
    'sb-1987-116': {'label': 'S.B. 1987 no. 116', 'title': 'Grondwet van de Republiek Suriname', 'kind': 'referendum',
                    'enacted': '1987-09-30', 'published': None,
                    'url': 'https://www.dna.sr/wetgeving/surinaamse-wetten/geldende-teksten-t-m-2005/grondwet-van-de-republiek-suriname/',
                    'temporary_until': None, 'restores': None},
    'sb-1992-38': {'label': 'S.B. 1992 no. 38', 'title': 'Wet van 8 april 1992, houdende wijziging van de Grondwet van de Republiek Suriname',
                   'kind': 'law', 'enacted': '1992-04-08', 'published': None,
                   'url': 'https://www.sris.sr/wp-content/uploads/2020/06/Grondwet-met-Mvt.pdf',
                   'temporary_until': None, 'restores': None},
    'sb-2023-157': {'label': 'S.B. 2023 no. 157',
                    'title': 'Wet van 25 oktober 2023, houdende nadere wijziging van de Grondwet van de Republiek Suriname',
                    'kind': 'law', 'enacted': '2023-10-25', 'published': '2023-10-26', 'url': SB_2023_157,
                    'temporary_until': None, 'restores': None},
}


def requests_count() -> dict[str, int]:
    out: dict[str, int] = {}
    p = CACHE / 'requests.jsonl'
    if p.exists():
        for line in p.read_text(encoding='utf-8').splitlines():
            host = re.sub(r'^https?://(www\.)?', '', json.loads(line)['url']).split('/')[0]
            out[host] = out.get(host, 0) + 1
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    gw, report = build_grondwet()
    rq = requests_count()
    corpus = {
        'country': {
            'code': 'SR', 'name': 'Suriname', 'slug': 'suriname', 'lang': 'nl', 'tz': 'America/Paramaribo',
            'future_branch': 'toekomst',
            'publisher': {'name': 'Staatsblad van de Republiek Suriname (dna.sr, sris.sr)', 'email': 'staatsblad@dna.invalid'},
            'default_in_force_rule': {
                'text': ('Grondwet art. 80 lid 1: laws "verkrijgen kracht van wet na afkondiging"; art. 118 leaves the '
                         'manner and moment to the law; Wet Algemene Bepalingen (G.B. 1868 no. 14) art. 1: no '
                         'regulation binds before its afkondiging. So a law binds from its afkondiging in the '
                         'Staatsblad, unless its own slotbepaling sets another day (most say "de dag volgende op die '
                         'van haar afkondiging").'),
                'source': 'https://sris.sr/wp-content/uploads/2025/04/ (S.B. 2025 no. 15, arts. 80 and 118); '
                          'https://www.dna.sr/media/frtc5hy3/wet_algemene_bepalingen.pdf'},
            'licence_note': ('Official texts of the Republic of Suriname: Staatsblad van de Republiek Suriname, as '
                             'published by De Nationale Assemblee (dna.sr) and the Surinaams Rechtsinformatiesysteem '
                             '(sris.sr).'),
        },
        'sources': [
            {'name': 'De Nationale Assemblee, Surinaamse wetten', 'url': 'https://www.dna.sr/wetgeving/surinaamse-wetten/',
             'retrieved': RETRIEVED, 'requests': rq.get('dna.sr', 0),
             'licence': 'Official legislative text; no licence stated; robots.txt absent (404)',
             'notes': 'Consolidations to 2005 with per-article footnotes; later Staatsblad issues as scanned PDFs.'},
            {'name': 'Surinaams Rechtsinformatiesysteem (sris.sr)', 'url': 'https://sris.sr/',
             'retrieved': RETRIEVED, 'requests': rq.get('sris.sr', 0),
             'licence': 'Official Staatsblad text; no licence stated', 'notes': 'S.B. 2025 no. 15 (current Grondwet).'},
            {'name': 'Government of Suriname (gov.sr)', 'url': 'https://gov.sr/', 'retrieved': RETRIEVED,
             'requests': rq.get('gov.sr', 0), 'licence': 'Official text; no licence stated',
             'notes': 'Second copy of the 1992 Grondwet consolidation, used only to cross-check the dna.sr copy.'},
        ],
        'laws': LAWS,
        'acts': [gw],
        'applies': [],
        'decisions': [
            'Grondwet: the original 1987 text (S.B. 1987 no. 116) and the 1992 amending act (S.B. 1992 no. 38) are not '
            'online in any official copy we found (dna.sr, its Wayback history, sris.sr, gov.sr, WIPO Lex), so the '
            'history starts with the 1992 consolidation, committed by the publisher as the oldest version available.',
            'Grondwet: the first version is dated 1992-04-08, the date of the Wet van 8 april 1992; its Staatsblad issue '
            'date and commencement clause could not be read online, so the real in-force day may be a few days later.',
            'Grondwet: S.B. 2023 no. 157 took effect the day after its afkondiging (art. II lid 2); it was uitgegeven on '
            '26 October 2023, so the in-force day is 2023-10-27.',
            'Grondwet: three versions. 1992-04-08 is the dna.sr 1992 consolidation. 2023-10-27 is that text with arts. '
            '60, 61, 161 and 163, the articles S.B. 2025 no. 15 footnotes "Gew. bij S.B. 2023 no. 157", replaced by '
            'their S.B. 2025 no. 15 wording and credited to S.B. 2023 no. 157 (whose own PDF is a scan with no text '
            'layer). 2025-02-07, the day S.B. 2025 no. 15 was uitgegeven, is S.B. 2025 no. 15 in full; every other '
            'difference from 1992 has no amending law and is committed uncredited by the publisher.',
            'Grondwet: the wording S.B. 2025 no. 15 gives arts. 60, 61, 161 and 163 was compared by eye with the page '
            'images of S.B. 2023 no. 157. It agrees, except that the act reads "per ressort, en de methode" in art. 161 '
            'lid 4 where S.B. 2025 no. 15 has no comma. The 2023-10-27 version uses the S.B. 2025 no. 15 wording, so '
            'that comma is not in this history; adding it would mean transcribing a scan.',
            'Grondwet: S.B. 2025 no. 15 is a republication by Resolutie (no. 14.227/24), not an amending law, so its '
            'changes against the 1992 consolidation are not credited to any law; each is listed below.',
            'Grondwet: art. 56 lid 2 "in geval van oorlog of andere buitengewone omstandigheden" is read as in the '
            'dna.sr 1992 consolidation; the sris.sr 1992 edition with memorie van toelichting agrees, while the gov.sr '
            'copy and S.B. 2025 no. 15 omit "oorlog". The omission appears in the 2025-02-07 commit, uncredited.',
            'Grondwet: the two publishers break some paragraphs differently (the preamble clauses, the oaths in arts. '
            '93 and 114, art. 66, the list in art. 142 lid 1). Where the words agree, the 1992 version takes the line '
            'breaks of S.B. 2025 no. 15, so layout does not show up as change.',
            'Grondwet: parse completeness was checked word by word against each PDF text layer: every body word of '
            'S.B. 2025 no. 15 is in the units in order, apart from headings (kept in grondwet/indeling.md) and words '
            'joined across a line-end hyphen.',
            'Wetboek van Strafrecht and the old Burgerlijk Wetboek (G.B. 1860 no. 4) not included: no official '
            'consolidation after 2005, and later amending acts (WvSr: S.B. 2023 no. 133 and S.B. 2023 no. 135 scans '
            'with OCR layers, S.B. 2020 no. 42 uncorrected OCR layer, S.B. 2014 no. 118 scan, S.B. 2017 no. 85 not '
            'listed; old BW: 2016 and S.B. 2022 no. 34 scans) cannot be applied from official text, so no text in '
            'force today could be built and checked. The new Burgerlijk Wetboek of 2024 is built (corpus.d part '
            '20-burgerlijk-wetboek). No data protection law is in force: sris.sr holds only a bill, the Ontwerpwet '
            'Bescherming Privacy en Persoonsgegevens (2020).',
            'Chapter and section headings are kept in one unit, grondwet/indeling.md, so article files hold only '
            'article text.',
            'Quotes and dashes are normalised to straight quotes and "-"; words the typesetter broke at a line end are '
            'joined.',
        ] + report,
        'ai_use': [
            'Claude Opus 5.5 (claude-opus-5-5, Claude Code) researched the sources and wrote fetch.py and parse.py. '
            'It viewed the 6 page images of S.B. 2023 no. 157 to identify the amending act and its commencement '
            'clause and to compare its wording of arts. 60, 61, 161 and 163 with S.B. 2025 no. 15 (one difference '
            'found and recorded in decisions, not applied); no legal text in this corpus was written, transcribed or OCRed by a model: all text comes from PDF text '
            'layers via PyMuPDF.',
        ],
    }
    out = json.dumps(corpus, ensure_ascii=False, indent=1, sort_keys=False) + '\n'
    tmp = HERE / 'corpus.json.tmp'
    tmp.write_text(out, encoding='utf-8', newline='\n')
    tmp.replace(HERE / 'corpus.json')          # atomic: autopush builds every change
    for a in corpus['acts']:
        print(a['slug'], [(v['from'], len(v['units']), len(v['credits'])) for v in a['versions']])
    for r in report:
        print('REPORT', r)


if __name__ == '__main__':
    main()
