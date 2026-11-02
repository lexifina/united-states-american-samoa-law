"""Sicily (italy-sicily-law) for git-for-law, gitlaw-scraper-dell, 2026-10-30. Private (world-law-ops).

Source: Assemblea Regionale Siciliana (www.ars.sicilia.it), "Statuto della Regione e norme di attuazione": the
Statute of the Sicilian Region as the ARS publishes it (PDF of June 2019, a text layer, with the ARS's footnotes).
The ARS law database (dati.ars.sicilia.it) shows its documents under /icaro/, which its robots.txt disallows, so the
regional laws are not built. Current text only.

    python -X utf8 scripts/world-law/it_sicily.py parse <docs-date>
    python -X utf8 scripts/world-law/it_sicily.py publish <docs-date>
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import it_fetch  # noqa: E402
import it_regions as R  # noqa: E402

SLUG = 'sicily'
HOST = 'www.ars.sicilia.it'
PAGE = f'https://{HOST}/statuto-della-regione'
PDF = f'https://{HOST}/sites/default/files/downloads/2019-06/Statuto2019.pdf'

SRC = {
    'host': HOST,
    'publisher': 'Assemblea Regionale Siciliana',
    'short': 'the Assemblea Regionale Siciliana (ARS)',
    'url': PAGE,
    'licence': 'L. 633/1941 art. 5: official acts are not protected. The ARS site states no restriction on reusing '
               'the texts.',
    'licence_note': 'Fonte: Assemblea Regionale Siciliana, Statuto della Regione Siciliana, '
                    'https://www.ars.sicilia.it/statuto-della-regione',
    'source_notes': 'The Statute as the ARS publishes it (PDF of June 2019, text layer, with the ARS\'s footnotes). '
                    'Current text only.',
    'in_force_rule': 'Statuto della Regione Siciliana, art. 29: regional laws are published in the Gazzetta Ufficiale '
                     'della Regione; the general rule (preleggi art. 10) is entry into force on the fifteenth day after '
                     'publication unless the law says otherwise. (Not applied here: the text is the current one, '
                     'dated the retrieval day.)',
    'history': 'current-only',
    'scope_note': ('So far this repository holds only the Statute: the ARS\'s database of regional laws shows its texts '
                   'on paths its robots.txt asks crawlers to avoid, so the regional laws are not included.'),
    'source_md': ('The Statute of the Sicilian Region (Statuto speciale della Regione Siciliana: R.D.Lgs. 15 maggio 1946, '
                  'n. 455, converted into legge costituzionale 26 febbraio 1948, n. 2, and amended by the constitutional '
                  'laws of 1972, 1989, 2001 and 2013) as the Assemblea Regionale Siciliana publishes it on '
                  '<https://www.ars.sicilia.it/statuto-della-regione>: a PDF of June 2019 extracted from the ARS volume '
                  '"Regolamento interno dell\'Assemblea", read from its text layer, with the ARS\'s footnotes. The running '
                  'header and page numbers are left out; words the PDF hyphenates at a line end are joined.'),
    'files_md': ('`statuto/art-001.md` is Articolo 1 of the Statute; `intestazione.md` holds the title page and the list '
                 'of the acts that approved and amended it. The headings of titles and sections stay in the file of the '
                 'article they stand before, and the ARS\'s footnotes in the file of the page text they follow (a note '
                 'number printed after an article number, as in "Art. 33", is the note mark of Art. 3).'),
    'official_md': 'The binding text of the Statute is the one published in the Gazzetta Ufficiale; the ARS PDF is a '
                   'reading copy.',
    'terms_md': ('The ARS site sets no condition on reusing the texts it publishes; the Statute is an official act outside '
                 'copyright under art. 5 above. This repository is free and non-commercial and credits the source.'),
}


def lines_of_pdf(b: bytes) -> list[str]:
    import pymupdf
    d = pymupdf.open(stream=b, filetype='pdf')
    out = []
    for page in d:
        ls = [R.clean_line(x) for x in page.get_text().splitlines()]
        ls = [x for x in ls if x]
        if page.number >= 2:
            if ls and ls[0] == str(page.number + 1):
                ls = ls[1:]
            if ls and ls[0] == 'STATUTO DELLA REGIONE':
                ls = ls[1:]
        # the page's footnotes: from the line that starts with the next note number to the page's end
        for i, x in enumerate(ls):
            if page.number >= 1 and re.match(rf'^{FN[0]}\s+\S', x):
                body, foot = ls[:i], ls[i:]
                break
        else:
            body, foot = ls, []
        for x in foot:
            m = re.match(r'^(\d+)\s+\S', x)
            if m and int(m.group(1)) == FN[0]:
                FN[0] += 1
                NOTES.append([x])
            elif NOTES:
                NOTES[-1].append(x)
        out += body
    return dehyphen(out)


FN = [2]       # note 1 sits on the title page, inside the front matter
NOTES: list[str] = []


def dehyphen(lines: list[str]) -> list[str]:
    j = []
    for x in lines:
        if j and j[-1].endswith('-') and x[:1].islower():
            j[-1] = j[-1][:-1] + x
        else:
            j.append(x)
    return j


def paragraphs(lines: list[str]) -> list[str]:
    out = []
    for x in lines:
        prev = out[-1] if out else None
        new = (prev is None or re.match(r'^Art\.\s*\d+\s*$', x) or re.match(r'^\d+\.\s', x)
               or re.match(r'^(TITOLO|Sezione|Capo|CAPO|SEZIONE)\b', x) or re.match(r'^\d+\s+\S', x)
               or re.match(r'^Art\.\s*\d+\s*$', prev) or prev.endswith(('.', ':', ';', ')'))
               or re.match(r'^(TITOLO|Sezione|SEZIONE|CAPO)\b', prev) or prev.isupper())
        if new:
            out.append(x)
        else:
            out[-1] = prev + ' ' + x
    return out


def units_of(b: bytes) -> dict:
    paras = paragraphs(lines_of_pdf(b))
    units, cur_k, cur_lab, cur, expect = {}, 'intestazione', 'Intestazione', [], 1
    carry = []

    def put():
        if cur:
            units[cur_k] = {'label': cur_lab, 'kind': 'preamble' if cur_k == 'intestazione' else 'art',
                            'text': '\n'.join(cur) + '\n'}
    for p in paras:
        m = re.match(r'^Art\.\s*(\d+)\s*$', p)
        if m and cur_k != 'intestazione' or (m and cur_k == 'intestazione' and m.group(1).startswith('1')):
            digits = m.group(1)
            n = expect if digits.startswith(str(expect)) else int(digits)
            put()
            cur_k, cur_lab = f'art-{n:03d}', f'Articolo {n}'
            cur = carry + [p]
            carry = []
            expect = n + 1
            continue
        if re.match(r'^(TITOLO|Sezione|SEZIONE|CAPO)\b', p) or (carry and len(p) < 80 and not re.match(r'^\d', p)
                                                               and not p.endswith('.')):
            if cur_k != 'intestazione':
                carry.append(p)
                continue
        cur.append(p)
    cur += carry
    put()
    if NOTES:
        notes = []
        for n in NOTES:
            notes += paragraphs(dehyphen(n))
        units['note'] = {'label': 'Note (ARS)', 'kind': 'other', 'text': '\n'.join(notes) + '\n'}
    return units


def build(docs_date: str) -> dict:
    b = it_fetch.path_for(PDF).read_bytes()
    units = units_of(b)
    key = 'lcost-1948-002'
    laws = {key: {'label': 'Legge costituzionale 26 febbraio 1948, n. 2',
                  'title': 'Conversione in legge costituzionale dello Statuto della Regione siciliana, approvato col '
                           'decreto legislativo 15 maggio 1946, n. 455',
                  'kind': 'law', 'enacted': '1948-02-26', 'published': '1948-03-09', 'url': PAGE,
                  'temporary_until': None, 'restores': None, 'note': None}}
    act = {'slug': 'statuto', 'short': 'Statuto', 'title': 'Statuto speciale della Regione Siciliana', 'url': PAGE,
           'first_law': None, 'earlier_laws': [key],
           'versions': [{'from': docs_date, 'source_url': PDF, 'sha256': hashlib.sha256(b).hexdigest(), 'units': units,
                         'credits': {}, 'note': 'The ARS\'s text of June 2019, read on the retrieval day.'}]}
    return {'country': R.country_block(SLUG, SRC), 'laws': laws, 'acts': [act],
            'sources': [R.source_block(SRC, docs_date)],
            'decisions': ['Current-only: the Statute as the ARS publishes it (PDF of June 2019), one "oldest version '
                          'available" commit dated the retrieval day, naming legge costituzionale 1948, n. 2.',
                          'Paragraphs are rebuilt from the PDF\'s lines: the running header "STATUTO DELLA REGIONE" and '
                          'page numbers are left out, words hyphenated at a line end are joined; footnotes stay where '
                          'the PDF prints them. An article number with a note mark glued to it ("Art. 33") is read as '
                          'the next article in sequence (Art. 3).',
                          'Regional laws are not included: the ARS database shows them under /icaro/, which its '
                          'robots.txt disallows.'],
            'ai_use': ['A model (Claude) wrote the parse code; it wrote no law text. Every word comes from the ARS PDF.']}


def letters_check(slug: str, part_name: str) -> list[str]:
    from pypdf import PdfReader
    part = json.loads((R.folder(slug) / 'corpus.d' / f'{part_name}.json').read_text(encoding='utf-8'))
    probs = []
    for act in part['acts']:
        v = act['versions'][0]
        b = it_fetch.path_for(v['source_url']).read_bytes()
        if hashlib.sha256(b).hexdigest() != v['sha256']:
            probs.append('sha256 differs')
            continue
        txt = []
        for no, pg in enumerate(PdfReader(io.BytesIO(b)).pages, 1):
            ls = [x for x in (pg.extract_text() or '').split('\n') if x.strip()]
            if no >= 3:
                ls = [x for x in ls if x.strip() != str(no) and ' '.join(x.split()) not in
                      ('STATUTO DELLA REGIONE', f'{no} STATUTO DELLA REGIONE')]
            txt += ls
        src = R.letters(' '.join(txt))
        lm = R.letters(''.join(u['text'] for u in v['units'].values()))
        if Counter(src) != Counter(lm):
            ca, cb = Counter(src), Counter(lm)
            probs.append(f'{act["slug"]}: source-only {dict((ca - cb).most_common(6))} corpus-only '
                         f'{dict((cb - ca).most_common(6))}')
    return probs


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    R.below_normal()
    cmd, dd = sys.argv[1], sys.argv[2]
    if cmd == 'parse':
        R.write_part(SLUG, '10-statuto', build(dd))
        print(letters_check(SLUG, '10-statuto'))
    elif cmd == 'publish':
        print(R.publish(SLUG, SRC, '10-statuto', dd, letters_check)[:400])
