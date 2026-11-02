"""gitlaw-scraper-dell (2026-10-30): the German-speaking Community of Belgium (lexifina/belgium-german-speaking-
community-law), current text from the Parliament's "Rechtsgrundlagen der Deutschsprachigen Gemeinschaft" (pdg.be,
9th ed., August 2026): Abschnitt II (Law of 31 December 1983 on institutional reforms for the DG) and Abschnitt III
(the DG's decrees exercising powers of the Walloon Region). Private: fetch code never goes into the repo.

    python -X utf8 be_dg.py parse <docs-date>
    python -X utf8 be_dg.py letters <part>
    python -X utf8 be_dg.py publish <part> <docs-date>
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
import warnings
from pathlib import Path

warnings.filterwarnings('ignore')
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DOCS = ROOT.parent.parent
sys.path.insert(0, str(HERE))
import be_fetch  # noqa: E402

SLUG = 'belgium-german-speaking-community'
FOLDER = ROOT / f'{SLUG}-law'
PAGE = 'https://pdg.be/desktopdefault.aspx/tabid-4037/'
PDFS = {
    'II': 'https://pdg.be/DownloadCount.aspx?raid=219863&docid=93582&rn=60743447-82e0-40b8-ba90-8f6e9c0c3f9f',
    'III': 'https://pdg.be/DownloadCount.aspx?raid=219864&docid=93583&rn=25be7380-89d4-4980-804e-e7992d108f71',
}
MONTHS = {m: i + 1 for i, m in enumerate(['januar', 'februar', 'märz', 'april', 'mai', 'juni', 'juli', 'august',
                                           'september', 'oktober', 'november', 'dezember'])}
TITLE = re.compile(r'^(\d{1,2})\.\s*([A-ZÄÖÜa-zäöü]+)\s+(\d{4})\s+(?:[–-]\s+)?(DEKRET|GESETZ|SONDERDEKRET)\b')
ART = re.compile(r'^\[?\s*(?:Artikel|Art\.)\s*\[?(\d+[a-z]*(?:\.\d+)?)\]?(?![\w.])')
HEAD = re.compile(r'^\[?\s*(TITEL|KAPITEL|ABSCHNITT|UNTERABSCHNITT)\b')
HEADLINE = re.compile(r'^\[?\s*(?:TITEL|KAPITEL|ABSCHNITT|UNTERABSCHNITT|Titel|Kapitel|Abschnitt|Unterabschnitt)\s+'
                      r'[IVXLC0-9]+(?:bis|ter|quater)?\s*[–-]\s')


def pdf_path(k: str) -> Path:
    return be_fetch.path_for(PDFS[k])


# ---------------------------------------------------------------- reader 1 (MuPDF): structure

def lines_of(pdf: Path):
    import fitz
    doc = fitz.open(str(pdf))
    for pno in range(doc.page_count):
        rows = {}
        for b in doc[pno].get_text('dict')['blocks']:
            for ln in b.get('lines', []):
                for s in ln['spans']:
                    if not 9.5 <= s['size'] <= 10.5:   # drops headers (9), footnotes (8/5), markers (6.5), covers
                        continue
                    y = round(s['origin'][1])
                    rows.setdefault(y, []).append((s['origin'][0], s['text'], bool(s['flags'] & 16)))
        for y in sorted(rows):
            spans = sorted(rows[y])
            text = ''.join(t for _, t, _ in spans)
            first_bold = next((bo for _, t, bo in spans if t.strip() and t.strip() != '['), False)
            bold_all = all(bo for _, t, bo in spans if t.strip() and t.strip() not in ('[', ']'))
            yield pno, text, first_bold, bold_all


def join(lines: list[str]) -> str:
    out = ''
    for ln in lines:
        ln = re.sub(r'\s+', ' ', ln.replace(' ', ' ')).strip()
        if not ln:
            continue
        if not out:
            out = ln
            continue
        m = re.search(r'([A-Za-zÄÖÜäöüß])-$', out)
        nxt = ln.split(' ')[0]
        if m and nxt and nxt[0].isalpha() and nxt not in ('und', 'oder', 'bzw.', 'sowie') and \
                (nxt[0].islower() == m.group(1).islower()):
            out = out[:-1] + ln
        else:
            out += ' ' + ln
    return out


def paragraphs(pdf: Path) -> list[dict]:
    paras, cur, cur_bold, cur_head = [], [], False, False

    def flush():
        nonlocal cur
        if cur:
            paras.append({'text': join(cur), 'bold': cur_bold, 'head': cur_head})
        cur = []
    for pno, text, first_bold, bold_all in lines_of(pdf):
        if not text.strip():
            flush()
            continue
        t = text.strip()
        starts_art = first_bold and ART.match(t)
        is_head = (t.upper() == t and any(c.isalpha() for c in t) and (bold_all or bool(HEAD.match(t))))             or bool(HEADLINE.match(t))
        if starts_art or (is_head and not (cur and cur_head)):
            flush()
        if not cur:
            cur_bold, cur_head = first_bold, is_head
        cur.append(text)
    flush()
    return paras


def de_date(s: str) -> str | None:
    m = re.match(r'(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})', s)
    if m:
        return f'{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}'
    m = re.match(r'(\d{1,2})\.\s*([A-Za-zäÄ]+)\.?\s*(\d{4})', s)
    if m and m.group(2).lower() in MONTHS:
        return f'{m.group(3)}-{MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}'
    return None


def acts_of(pdf: Path) -> list[dict]:
    raw = paragraphs(pdf)
    paras = []
    for p in raw:   # a title printed over several bold upper-case lines with blank lines between
        if paras and paras[-1].get('title_open') and p['bold'] and p['text'].upper() == p['text']:
            paras[-1]['text'] += ' ' + p['text']
            continue
        if 'INHALTSVERZEICHNIS' in p['text'] and not p['text'].startswith('INHALTSVERZEICHNIS'):
            a, b = p['text'].split('INHALTSVERZEICHNIS', 1)
            paras.append(dict(p, text=a.strip()))
            paras.append(dict(p, text='INHALTSVERZEICHNIS' + b, bold=False, head=False))
            continue
        q = dict(p)
        if p['bold'] and re.match(r'^\d{1,2}\.\s*[A-ZÄÖÜ]+\s+\d{4}$', p['text']):
            q['title_open'] = True
        elif paras and paras[-1].get('title_open'):
            paras[-1]['title_open'] = False
        paras.append(q)
    acts, act, mode = [], None, None
    for p in paras:
        t = p['text']
        if p['bold'] and TITLE.match(t) and t.upper() == t:
            act = {'title': t, 'hinweise': [], 'units': [], 'heads': []}
            acts.append(act)
            mode = 'pre'
            continue
        if act is None:
            continue
        if mode == 'pre':
            if t.startswith('ALLGEMEINE HINWEISE'):
                mode = 'hinweise'
            continue
        if mode in ('hinweise', 'toc'):
            if t.startswith('INHALTSVERZEICHNIS'):
                mode = 'toc'
                continue
            body_start = (p['bold'] and ART.match(t)) or (p['head'] and HEAD.match(t) and t.upper() == t)
            if not body_start:
                if mode == 'hinweise' and set(t) - set('_ '):
                    act['hinweise'].append(t)
                continue
            mode = 'body'
        if p['head'] and not (p['bold'] and ART.match(t)):
            act['heads'].append(t)
            continue
        m = ART.match(t) if p['bold'] else None
        if m:
            act['units'].append({'num': m.group(1).replace(' ', ''), 'lines': [t]})
        elif act['units']:
            act['units'][-1]['lines'].append(t)
        else:
            act.setdefault('ingress', []).append(t)
    return acts


def in_force(hinweise: list[str], docs_date: str) -> tuple[str, str | None]:
    """(latest in-force day <= docs_date named in the notes, original in-force day)"""
    txt = ' '.join(hinweise)
    days = []
    for m in re.finditer(r'(?:in Kraft(?: am)?|trat am|tritt am|Inkrafttreten am)\s*(\d{1,2}\.\s*(?:\d{1,2}\.|[A-Za-zä]+\.?)\s*\d{4})',
                         txt):
        d = de_date(m.group(1))
        if d:
            days.append(d)
    for m in re.finditer(r'vollständigen Erneuerung[^()]{0,80}\((\d{1,2}\.\s*[A-Za-zä]+\s*\d{4})\)', txt):
        d = de_date(m.group(1))
        if d:
            days.append(d)
    orig = None
    m = re.search(r'(?:trat|tritt) am\s*(\d{1,2}\.\s*(?:\d{1,2}\.|[A-Za-zä]+\.?)\s*\d{4})\s*in Kraft', txt)
    if m:
        orig = de_date(m.group(1))
    ok = [d for d in days if d <= docs_date]
    return max(ok), orig


def padnum(s: str) -> str:
    return re.sub(r'\d+', lambda m: m.group(0).zfill(3), s)


def unit_key(num: str) -> str:
    k = re.sub(r'(\d)([a-z])', r'\1-\2', num.lower())
    return 'art-' + padnum(re.sub(r'[^a-z0-9]+', '-', k).strip('-'))


def slug_of(title: str, seen: set) -> str:
    m = TITLE.match(title)
    d = de_date(f'{m.group(1)}. {m.group(2)} {m.group(3)}')
    base = f'{m.group(4).lower()}-{d}'
    s, n = base, 2
    words = {'ENERGIE': 'energie', 'RAUMORDNUNG': 'raumordnung', 'WOHNUNGSWESEN': 'wohnungswesen'}
    if True:
        for w, sl in words.items():
            if w in title:
                s = f'{base}-{sl}'
                break
    while s in seen:
        s, n = f'{base}-{n}', n + 1
    seen.add(s)
    return s


def nice_title(t: str) -> str:
    """The title as printed, in upper case; keep it (no recasing)."""
    return t


LAWS: dict = {}


def build_act(a: dict, k: str, docs_date: str, seen: set) -> dict:
    slug = slug_of(a['title'], seen)
    day, orig = in_force(a['hinweise'], docs_date)
    units = {}
    if a.get('ingress'):
        units['ingress'] = {'label': 'Eingang', 'kind': 'preamble', 'text': '\n'.join(a['ingress']) + '\n'}
    if a['heads']:
        units['gliederung'] = {'label': 'Gliederung', 'kind': 'headings',
                               'text': '\n'.join(f'# {h}' for h in a['heads']) + '\n'}
    for u in a['units']:
        key = unit_key(u['num'])
        while key in units:
            key += '-x'
        lab = f'Art. {u["num"]}'
        units[key] = {'label': lab, 'kind': 'art', 'text': f'# {lab}\n' + '\n'.join(u['lines']) + '\n'}
    sha = __import__('hashlib').sha256(pdf_path(k).read_bytes()).hexdigest()
    m = TITLE.match(a['title'])
    enacted = de_date(f'{m.group(1)}. {m.group(2)} {m.group(3)}')
    pm = re.search(r'Staatsblatt \(B\.S\.\) vom\s*(\d{1,2}\.\s*[A-Za-zä]+\.?\s*\d{4})', ' '.join(a['hinweise']))
    kind_de = {'DEKRET': 'Dekret', 'GESETZ': 'Gesetz', 'SONDERDEKRET': 'Sonderdekret'}[m.group(4)]
    y, mo, dd = enacted.split('-')
    mname = [n for n, i in MONTHS.items() if i == int(mo)][0].capitalize().replace('März', 'März')
    LAWS[slug] = {'label': f'{kind_de} vom {int(dd)}. {mname} {y}', 'title': a['title'], 'kind': 'law',
                  'enacted': enacted, 'published': de_date(pm.group(1)) if pm else None, 'url': PAGE,
                  'temporary_until': None, 'restores': None, 'note': None}
    return {'slug': slug, 'short': slug, 'title': a['title'], 'url': PAGE, 'first_law': None, 'earlier_laws': [slug],
            'versions': [{'from': day, 'source_url': PDFS[k], 'sha256': sha, 'units': units, 'credits': {},
                          'note': ('Allgemeine Hinweise (Parlament der Deutschsprachigen Gemeinschaft): '
                                   + ' '.join(a['hinweise']))}],
            '_orig': orig}


COUNTRY = {
    'code': 'BE-DG', 'name': 'German-speaking Community of Belgium', 'slug': SLUG, 'lang': 'de',
    'tz': 'Europe/Brussels', 'future_branch': 'zukunft',
    'publisher': {'name': 'Parlament der Deutschsprachigen Gemeinschaft (Rechtsgrundlagen der Deutschsprachigen '
                          'Gemeinschaft, 9. Auflage, August 2026)', 'email': 'rechtsgrundlagen@pdg.be.invalid'},
    'default_in_force_rule': {
        'text': ('Current text only: each act is dated by the latest in-force day its "Allgemeine Hinweise" name '
                 '(the original in-force day or that of the last amendment) on or before the retrieval day.'),
        'source': PAGE},
    'licence_note': ('Text: Parlament der Deutschsprachigen Gemeinschaft, Rechtsgrundlagen der Deutschsprachigen '
                     'Gemeinschaft (pdg.be). Official acts of the authorities are not protected by copyright in '
                     'Belgium (Code of Economic Law, Art. XI.172 §2).'),
}
DECISIONS = [
    'Current text only: the Parliament publishes one coordinated text per act (9th edition, August 2026). Each act '
    'has one version, the oldest version available, dated by the latest in-force day the act\'s "Allgemeine '
    'Hinweise" name on or before the retrieval day, and credited to the publisher.',
    'Text is read from the PDF by font size: body text (10 pt) only; running headers (9 pt), footnotes (8 pt) and '
    'footnote markers (superscript) are left out. The square brackets that mark amended or inserted wording, and '
    '[...] for repealed wording, are kept as printed. Words hyphenated at a line end are joined.',
    'The "Allgemeine Hinweise" (publication, in-force day and amendment list) are the publisher\'s notes, kept as the '
    'version note, not as law text. Headings (TITEL, KAPITEL, ABSCHNITT) are kept in gliederung.md.',
    'The Law of 31 December 1983 is a federal law; it is included as the Community\'s basic institutional statute, '
    'in the official German translation of its unofficial coordination, as the Parliament publishes it.',
]
AI_USE = ['A model (Claude) wrote the parse code and chose which texts to include; it wrote no law text. Every word '
          'of law comes from the Parliament\'s own collection.']


def write_part(p: Path, part: dict):
    if p.with_suffix('.PUBLISH').exists():
        return
    tmp = p.with_suffix('.tmp')
    tmp.write_text(json.dumps(part, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    os.replace(tmp, p)


def parse(docs_date: str):
    out = FOLDER / 'corpus.d'
    out.mkdir(parents=True, exist_ok=True)
    seen = set()
    src = {'name': 'Parlament der Deutschsprachigen Gemeinschaft: Rechtsgrundlagen der Deutschsprachigen '
                   'Gemeinschaft, 9. aktualisierte Auflage, August 2026', 'url': PAGE, 'retrieved': docs_date,
           'licence': 'Official acts are excluded from copyright (Code of Economic Law, Art. XI.172 §2); the PDFs '
                      'carry "Alle Rechte vorbehalten", which covers the edition, not the official texts.',
           'notes': 'Abschnitt II and III PDFs, current coordinated text with amendment notes.'}
    rep = {}
    for k, name in (('II', '10-grundlagengesetz'), ('III', '20-dekrete-regionale-befugnisse')):
        acts = [build_act(a, k, docs_date, seen) for a in acts_of(pdf_path(k))]
        for a in acts:
            a.pop('_orig')
        laws = {a['slug']: LAWS[a['slug']] for a in acts}
        part = {'laws': laws, 'acts': acts}
        if k == 'II':
            part = {'country': COUNTRY, 'sources': [src], 'laws': laws, 'acts': acts, 'decisions': DECISIONS,
                    'ai_use': AI_USE}
        write_part(out / f'{name}.json', part)
        rep[name] = [(a['slug'], a['versions'][0]['from'], len(a['versions'][0]['units'])) for a in acts]
    print(json.dumps(rep, ensure_ascii=False, indent=1))


# ---------------------------------------------------------------- reader 2 (pypdf): letters and digits

def letters(s: str) -> str:
    return ''.join(ch for ch in unicodedata.normalize('NFC', s) if ch.isalnum())


def pypdf_body(pdf: Path) -> list[str]:
    """Per page, the text runs whose effective font size is 9.5-10.5 pt and that sit below the running header,
    read with pypdf's own content-stream parser."""
    from pypdf import PdfReader
    r = PdfReader(str(pdf))
    pages = []
    for pg in r.pages:
        parts = []

        def vis(text, cm, tm, font, size):
            sc = (tm[0] ** 2 + tm[1] ** 2) ** 0.5 * (cm[0] ** 2 + cm[1] ** 2) ** 0.5
            eff = size * sc if sc else size
            if 9.5 <= eff <= 10.5 and text:
                parts.append(text)
        pg.extract_text(visitor_text=vis)
        pages.append(''.join(parts))
    return pages


def letters_check(part_name: str) -> list[str]:
    part = json.loads((FOLDER / 'corpus.d' / f'{part_name}.json').read_text(encoding='utf-8'))
    k = 'II' if part_name.startswith('10') else 'III'
    pages = pypdf_body(pdf_path(k))
    # the reader-2 text from the first act title on, without the Inhaltsverzeichnis pages
    start = next(i for i, t in enumerate(pages)
                 if re.search(r'\d{1,2}\.\s*[A-ZÄÖÜ]+\s+\d{4}\s*(?:[–-]\s*)?(?:DEKRET|GESETZ)', t))
    body, skip = [], False
    for t in pages[start:]:
        if 'INHALTSVERZEICHNIS' in t:
            skip = True
        if skip and re.search(r'TITEL I\b', t):
            skip = False
        if not skip:
            body.append(t)
    src = letters(''.join(body))
    mine, ordered, heads = '', [], []
    for a in part['acts']:
        v = a['versions'][0]
        note = v['note'].split(': ', 1)[1]
        ordered += [letters(a['title']), letters(note)]
        mine += letters(a['title']) + letters('ALLGEMEINE HINWEISE') + letters(note)
        for key, u in v['units'].items():
            lines = u['text'].splitlines()
            body_lines = lines[1:] if key.startswith('art-') else lines
            if key == 'gliederung':
                heads += [letters(x) for x in lines]
            else:
                ordered.append(letters(''.join(body_lines)))
            mine += letters(''.join(body_lines))
    probs = []
    if sorted(src) != sorted(mine):
        from collections import Counter
        ca, cb = Counter(src), Counter(mine)
        probs.append(f'{part_name}: letters differ (source {len(src)}, corpus {len(mine)}): '
                     f'source-only {dict((ca - cb).most_common(8))} corpus-only {dict((cb - ca).most_common(8))}')
    for x in heads:
        if x and x not in src:
            probs.append(f'{part_name}: heading not found in the source: {x[:80]}')
    # titles, notes and articles appear in the source as contiguous runs, in corpus order
    pos = 0
    for x in ordered:
        if not x:
            continue
        i = src.find(x, pos)
        if i < 0:
            # a table: the two readers take its cells in a different order (rows / columns). Accept when the run
            # starts at the next place in the source and the same-length window holds the same letters.
            j = src.find(x[:40], pos)
            if j >= 0 and sorted(src[j:j + len(x)]) == sorted(x):
                pos = j + len(x)
                continue
            probs.append(f'{part_name}: not found in order in the source after {pos}: {x[:80]}')
            break
        pos = i + len(x)
    return probs


# ---------------------------------------------------------------- docs, verify, publish

def _verified(extra=()):
    return [json.loads(p.read_text(encoding='utf-8')) for p in sorted((FOLDER / 'corpus.d').glob('*.json'))
            if p.with_suffix('.PUBLISH').exists() or p.stem in extra]


def _long(d: str) -> str:
    x = dt.date.fromisoformat(d)
    return f'{x.day} {x.strftime("%B")} {x.year}'


def write_docs(docs_date: str, extra=(), out: Path | None = None):
    rows, nacts = [], 0
    for part in _verified(extra):
        for a in part['acts']:
            nacts += 1
            v = a['versions'][0]
            rows.append(f'| `{a["slug"]}/` | {a["title"][:150]} | {len(v["units"])} | current text, dated '
                        f'{_long(v["from"])} |')
    repo = out or (FOLDER / 'repo')
    repo.mkdir(parents=True, exist_ok=True)
    readme = f"""# German-speaking Community of Belgium: law in git

The law of the German-speaking Community of Belgium (Deutschsprachige Gemeinschaft, Ostbelgien) in git: one file per article, in the form the Community's Parliament publishes it. `git blame` and `tools/on.py` work as in the other repositories of the shared design.

It follows the shared design of [lexifina/global-law](https://github.com/lexifina/global-law), which places it at `be-dg/`. The federal law is in [lexifina/belgium-law](https://github.com/lexifina/belgium-law).

The text is in German, the official language of the Community.

## What this repository holds

**Current text only, no history yet.** {nacts} acts, one version each: the Community's basic institutional statute (the Law of 31 December 1983 on institutional reforms for the German-speaking Community, in the official German translation of its coordination) and the decrees by which the Community exercises powers of the Walloon Region. The Community's other decrees are not included yet.

| Folder | Act | Files | History |
| --- | --- | ---: | --- |
{chr(10).join(rows)}

## Source

"Rechtsgrundlagen der Deutschsprachigen Gemeinschaft", 9th updated edition (August 2026), edited by the legal service of the Parliament of the German-speaking Community and published at <{PAGE}>: Abschnitt II (the Law of 31 December 1983) and Abschnitt III (decrees exercising regional powers). Each text opens with "Allgemeine Hinweise": its publication in the Belgisches Staatsblatt, the day it took effect and its amendments.

## Dates

- Each act has one commit, the "oldest version available", dated at **noon, Europe/Brussels**, on the latest in-force day its "Allgemeine Hinweise" name on or before the retrieval day (the act's own in-force day, or the day its last amendment took effect). It is credited to the publisher.
- The amendment notes are kept in the commit message, not in the law files.

## Files

`<act>/art-005.md` is Art. 5, `art-005-001.md` Art. 5.1, `art-054-bis.md` Art. 54bis; `gliederung.md` holds the headings (TITEL, KAPITEL, ABSCHNITT). The first line is the article number; then one paragraph per line. Square brackets mark wording that an amendment inserted or replaced, and `[...]` wording it repealed, as in the printed coordination; the footnote numbers that name each amendment are left out.

## How it is checked

- Every act is read back from git on the day of its version and the day before (`tools/check_repo.py`); both must match `corpus.json`.
- The letters and digits of the whole repository text (titles, notes, headings and articles, in order) equal those of the body text of the PDF, read a second time with a separate PDF parser.

## Limits

This is not an official publication. The binding text is the one published in the Belgisches Staatsblatt / Moniteur belge. There is no earlier version: the history of these acts before the current text is not recorded here.
"""
    lic = """The law texts in this repository are official texts, taken from "Rechtsgrundlagen der Deutschsprachigen
Gemeinschaft" (9th edition, August 2026), published by the Parliament of the German-speaking Community of
Belgium (https://pdg.be/).

Belgian law does not protect them by copyright. Code of Economic Law, Art. XI.172 §2: "Les actes officiels de
l'autorité ne donnent pas lieu au droit d'auteur." / "Officiële akten van de overheid geven geen aanleiding tot
auteursrecht." (Official acts of the authorities do not give rise to copyright.) The edition carries the notice
"© Parlament der Deutschsprachigen Gemeinschaft. Alle Rechte vorbehalten."; that notice covers the edition's own
material (its layout, introductions and tables of contents), which this repository does not reproduce, apart from
the "Allgemeine Hinweise" quoted as notes on each version.

Source: Parlament der Deutschsprachigen Gemeinschaft. This repository is not an official publication.

Lexifina's own contributions (the arrangement, the commit messages, the tables and the tools) are dedicated to the
public domain under CC0 1.0 Universal: https://creativecommons.org/publicdomain/zero/1.0/
"""
    juris = {'path': 'be-dg', 'code': 'BE-DG', 'name': 'German-speaking Community of Belgium', 'level': 'community',
             'parent': 'be', 'repo': f'https://github.com/lexifina/{SLUG}-law',
             'build': f'built: current text of {nacts} basic acts from the Parliament\'s Rechtsgrundlagen',
             'language': 'de', 'sources': 1}
    (repo / 'README.md').write_text(readme, encoding='utf-8', newline='\n')
    (repo / 'LICENSE').write_text(lic, encoding='utf-8', newline='\n')
    (repo / 'jurisdiction.json').write_text(json.dumps(juris, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
                                            newline='\n')


def _low(cmd, env=None):
    return subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', env=env,
                          creationflags=0x4000 if os.name == 'nt' else 0)


def _rm(d: Path):
    import stat

    def onerr(func, path, exc):
        os.chmod(path, stat.S_IWRITE)
        func(path)
    if d.exists():
        shutil.rmtree(d, onexc=onerr)


def verify_part(part: str, docs_date: str):
    probs = letters_check(part)
    if probs:
        return False, 'letters check: ' + probs[0]
    tmp, build = DOCS / f'{SLUG}-law-verify', DOCS / f'{SLUG}-law-verifybuild'
    for d in (tmp, build):
        _rm(d)
    (tmp / 'corpus.d').mkdir(parents=True)
    names = [p.stem for p in sorted((FOLDER / 'corpus.d').glob('*.json')) if p.with_suffix('.PUBLISH').exists()]
    for n in names + [part]:
        shutil.copy2(FOLDER / 'corpus.d' / f'{n}.json', tmp / 'corpus.d' / f'{n}.json')
    write_docs(docs_date, extra=[part], out=tmp / 'repo')
    build.mkdir()
    subprocess.run(['git', 'init', '-q'], cwd=build, check=True)
    env = dict(os.environ, GITLAW_NO_CHECKOUT='1')
    b = _low([sys.executable, '-X', 'utf8', str(ROOT / 'gitlaw_common' / 'build.py'), str(tmp), '--repo', str(build),
              '--docs-date', docs_date], env=env)
    if b.returncode:
        return False, 'build failed: ' + (b.stderr or b.stdout)[-800:]
    c = _low([sys.executable, '-X', 'utf8', str(ROOT / 'gitlaw_common' / 'check.py'), str(build), '--corpus',
              str(tmp / 'corpus.json')])
    try:
        res = json.loads(c.stdout[c.stdout.index('{'):])
    except Exception:
        return False, 'check.py output unreadable: ' + (c.stderr or c.stdout)[-600:]
    if any(res.get(k) for k in ('mismatches', 'trailer_errors', 'merges', 'backwards', 'future_dated',
                                'missing_in_force')):
        return False, 'check.py: ' + json.dumps({k: v for k, v in res.items() if k != 'details'})[:300]
    p = json.loads((FOLDER / 'corpus.d' / f'{part}.json').read_text(encoding='utf-8'))
    line = (f'{len(p["acts"])} act(s), current text (one version each) from the Parliament\'s Rechtsgrundlagen PDF: '
            f'letters-and-digits of the whole part equal the PDF body text read with pypdf (separate from the MuPDF '
            f'parse); scratch build: check.py {res.get("versions")} versions, 0 mismatches, 0 trailer errors, '
            f'0 merges ({docs_date}).')
    _rm(tmp)
    _rm(build)
    return True, line


def publish(part: str, docs_date: str) -> str:
    ok, line = verify_part(part, docs_date)
    if not ok:
        return 'NOT VERIFIED ' + line
    pub = FOLDER / 'corpus.d' / f'{part}.PUBLISH'
    tmp = pub.with_suffix('.ptmp')
    tmp.write_text(line + '\n', encoding='utf-8', newline='\n')
    write_docs(docs_date, extra=[part])
    os.replace(tmp, pub)
    top = FOLDER / 'PUBLISH'
    if not top.exists():
        top.write_text('corpus.d parts are published one by one, each once its own <part>.PUBLISH is written.\n',
                       encoding='utf-8', newline='\n')
    return 'PUBLISH ' + line


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'parse':
        parse(sys.argv[2])
    elif cmd == 'letters':
        pr = letters_check(sys.argv[2])
        print('\n'.join(pr) or 'letters check: clean')
    elif cmd == 'publish':
        print(publish(sys.argv[2], sys.argv[3]))
