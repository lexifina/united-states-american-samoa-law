"""Emilia-Romagna (italy-emilia-romagna-law), gitlaw-scraper-dell 2026-10-30. Private; never published.

Source: Demetra, the Assemblea legislativa's open data ("Scarica i dati", CC BY 4.0): one zip per legislature of the
regional laws in XML Norme in Rete, each the text in force (NIR tipo="vigente", with its vigenza start) or, for laws
never amended, the original text. 12 requests in all (cached in scripts/world-law/.it-cache).

    python -X utf8 scripts/world-law/it_emilia_romagna.py parse        # write corpus.d parts
    python -X utf8 scripts/world-law/it_emilia_romagna.py publish <part>
    python -X utf8 scripts/world-law/it_emilia_romagna.py letters <part>
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html
import io
import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import it_fetch  # noqa: E402
import it_regions as R  # noqa: E402

SLUG = 'emilia-romagna'
HOST = 'demetra.regione.emilia-romagna.it'
ZIP = ('https://demetra.regione.emilia-romagna.it/al/public/resources/themes/simple/class/download_archive.php'
       '?type=zip&formato=xml&tipo=LR&metaleg={leg}')
DOCS_DATE = '2026-10-30'
PART_SIZE = 50
MONTHS = ['gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio', 'agosto', 'settembre', 'ottobre',
          'novembre', 'dicembre']

SRC = {
    'host': HOST,
    'publisher': "Assemblea legislativa della Regione Emilia-Romagna, Demetra",
    'short': 'Demetra (Assemblea legislativa della Regione Emilia-Romagna)',
    'url': 'https://demetra.regione.emilia-romagna.it/al/',
    'licence': 'CC BY 4.0 (open data, "Scarica i dati"); L. 633/1941 art. 5: official acts are not protected.',
    'licence_note': ('Source: Assemblea legislativa della Regione Emilia-Romagna, Demetra, '
                     'https://demetra.regione.emilia-romagna.it/al/ (open data, CC BY 4.0)'),
    'source_notes': ('The open-data zips of the regional laws (Leggi regionali, XML Norme in Rete), legislatures I-XII, '
                     'for the current texts; for earlier versions of amended laws, the original text and the '
                     'consolidated texts ("Testo Coordinato") on each law\'s "storia" tab.'),
    'in_force_rule': ('Statuto della Regione Emilia-Romagna, art. 55, comma 1: laws enter into force on the fifteenth '
                      'day after publication in the Bollettino Ufficiale, unless they set another term. A current text '
                      'is dated by the start of validity Demetra records for it; an earlier version by the in-force '
                      'day of the law that made it (its own entry-into-force clause, else the start of validity '
                      'Demetra records for a law never amended, else this rule).'),
    'in_force_source': 'https://demetra.regione.emilia-romagna.it/al/articolo?urn=er:assemblealegislativa:legge:2005;13',
    'history': 'dated',
    'source_md': ('Demetra, the database of the Assemblea legislativa della Regione Emilia-Romagna, '
                  '<https://demetra.regione.emilia-romagna.it/al/>, through its open data ("Scarica i dati"): one zip '
                  'per legislature with every regional law in XML Norme in Rete. For a law that has been amended the '
                  'file holds the consolidated text in force (Demetra\'s "testo vigente") with the day that text '
                  'started to apply; for a law never amended, the text as published. Laws Demetra marks as wholly '
                  'repealed are left out. Demetra\'s editor\'s notes are not copied; their markers are dropped.\n\n'
                  'The **earlier versions** of an amended law come from its "storia" tab on Demetra (for the Statute, '
                  '<https://demetra.regione.emilia-romagna.it/al/articolo?urn=er:assemblealegislativa:legge:2005;13>, '
                  'tab "Storia"): the original text ("Testo originale") and each consolidated text ("Testo '
                  'Coordinato") Demetra keeps, each labelled with the publication day of the law that made it, read '
                  'from Demetra\'s pages. Those pages print the enacting formula and the articles but not the closing '
                  'formula and signature, so an earlier version\'s heading, closing formula and annex titles are the '
                  'current text\'s (they are the law\'s own heading and promulgation record; the heading and annex '
                  'titles on each version page are checked to be the same). Where the current text has no enacting '
                  'formula, its earlier versions leave it out too. A law is kept with its current text only '
                  'when its pages cannot be read into the same provisions as its open-data file or fail the checks. '
                  'Demetra typed some old texts again when it consolidated them, so a commit for an amendment can '
                  'also carry corrections of spelling, capitals, accents or headings that Demetra made in that '
                  'consolidated text; lines that differ only in spaces and punctuation are not shown as changed.'),
    'dates_md': ('- Each commit is dated at **noon, Europe/Rome**.\n'
                 '- A law never amended is recorded **as first published**, on the day Demetra gives as the start of '
                 'its validity (by Statuto art. 55 the fifteenth day after publication, unless the law sets another '
                 'term), and credited to the law itself.\n'
                 '- An amended law with its history starts with its **original text**, dated the day it entered into '
                 'force and credited to itself, then has one commit for each consolidated text Demetra keeps, dated '
                 'the day the law that made it entered into force and credited to that law. The publication days are '
                 'the ones Demetra\'s storia tab gives. The in-force day is the one the law\'s own entry-into-force '
                 'clause gives (for example "il giorno successivo alla sua pubblicazione"); for a law without one, '
                 'the start of validity Demetra records when the law was never amended, otherwise the fifteenth day '
                 'after publication (Statuto art. 55, comma 1; for laws before the 2005 Statute the same default term '
                 'of art. 10 of the disposizioni preliminari al codice civile). Each commit\'s message says which. '
                 'The current text keeps the day Demetra gives as the start of its validity.\n'
                 '- Demetra does not keep a text after every amendment: where one consolidated text carries the '
                 'changes of several laws, they are one commit, credited to the latest and naming the others, on that '
                 'law\'s day. Single provisions that a law brings into force on another day are not dated separately.\n'
                 '- Demetra\'s pages and its open-data files space words around references differently (for example '
                 '"dell\'articolo" and "dell\' articolo"), and old texts were re-typed ("Emilia - Romagna", "LR"): a '
                 'provision or line whose letters and digits are those of the next version\'s takes the next '
                 'version\'s form, so no commit records a change of spaces or punctuation only.\n'
                 '- An amended law whose earlier versions could not be read is recorded by its **current consolidated '
                 'text only**, as its **oldest version available**, dated the day Demetra gives as the start of '
                 'validity of that text and credited to Demetra as publisher, naming the law and the amending laws '
                 'before it.'),
    'files_md': ('`<act>/art-005.md` is Art. 5, `art-005-bis.md` Art. 5 bis; `intestazione.md` holds the heading and '
                 'title, `preambolo.md` the enacting formula and preamble, `formula-finale.md` the closing formula '
                 'and signature, `allegati.md` any annex printed in the text. Headings of titles, chapters and '
                 'sections stay in the file of the article they stand before. Acts are named `lr-<year>-<number>`; '
                 'the Statute is `statuto/`.'),
    'official_md': 'The binding text is the one published in the Bollettino Ufficiale della Regione Emilia-Romagna.',
    'terms_md': ('Demetra releases these datasets under the Creative Commons Attribution 4.0 licence ("I dati ... sono '
                 'rilasciati in licenza Creative Commons (CC BY 4.0) per il libero riuso"), '
                 'https://creativecommons.org/licenses/by/4.0/. The site\'s general copyright note reserves its '
                 'trade marks, logos and distinctive signs; none is used here.'),
    'scope_note': 'Regulations, internal rules and wholly repealed laws are not included.',
}


def zips() -> dict[int, zipfile.ZipFile]:
    return {leg: zipfile.ZipFile(io.BytesIO(it_fetch.get(ZIP.format(leg=leg), timeout=900))) for leg in range(1, 13)}


# ---------------------------------------------------------------- parse

H = '{http://www.w3.org/HTML/1998/html4}'
BLOCK = {'comma', 'el', 'en', 'ep', 'alinea', 'coda', 'rubrica', 'p', 'tr', 'li', 'div', 'br', 'h1', 'h2', 'h3', 'h4',
         'table', 'tbody', 'tipoDoc', 'titoloDoc', 'emanante', 'dataeluogo', 'sottoscrizioni',
         'sottoscrizione', 'visto', 'preambolo', 'titolopreambolo', 'premessapreambolo', 'decorazione'}
CONTAINERS = {'libro', 'parte', 'titolo', 'capo', 'sezione', 'paragrafo'}


def local(tag) -> str:
    return tag.rsplit('}', 1)[-1] if isinstance(tag, str) else ''


def flat(el, out: list[str], top=True):
    """Text of `el` with a break (NUL) around block elements; the file's own layout whitespace is a space; footnote
    markers (ndr) dropped, their tail kept."""
    name = local(el.tag)
    if name == 'ndr':
        return
    block = name in BLOCK and not top
    if block:
        out.append(BRK)
    if el.text:
        out.append(WS.sub(' ', el.text))
    for ch in el:
        flat(ch, out, top=False)
        if ch.tail:
            out.append(WS.sub(' ', ch.tail))
    if block:
        out.append(BRK)


WS = re.compile(r'\s+')
BRK = '\x01'
NL = chr(10)


def lines_of(el) -> list[str]:
    buf: list[str] = []
    flat(el, buf)
    return [x for x in (R.clean_line(s) for s in ''.join(buf).split(BRK)) if x]


def num_lines_inline(el) -> list[str]:
    """An article: its num and rubrica on their own lines, then each comma (num + corpo on one line)."""
    buf: list[str] = []
    for ch in el:
        n = local(ch.tag)
        if n in ('num', 'rubrica'):
            buf.append(BRK)
            flat(ch, buf)
            buf.append(BRK)
        else:
            flat(ch, buf, top=False)
        if ch.tail:
            buf.append(WS.sub(' ', ch.tail))
    if el.text:
        buf.insert(0, WS.sub(' ', el.text))
    return [x for x in (R.clean_line(s) for s in ''.join(buf).split(BRK)) if x]


ROMAN = ['bis', 'ter', 'quater', 'quinquies', 'sexies', 'septies', 'octies', 'novies', 'nonies', 'decies',
         'undecies', 'duodecies', 'terdecies', 'quaterdecies', 'quinquiesdecies', 'sexiesdecies']


def art_key(num_text: str, idx: int) -> str:
    t = R.ascii_slug(num_text)
    m = re.match(r'^(?:art|articolo)?-?(\d+)(?:-?([a-z]+))?(?:-(.*))?$', t)
    if m:
        k = f'art-{int(m.group(1)):03d}'
        if m.group(2):
            k += '-' + m.group(2)
        if m.group(3):
            k += '-' + m.group(3)
        return k
    if t in ('articolo-unico', 'art-unico', 'unico'):
        return 'art-001'
    return f'art-x{idx:03d}'


def units_of(root) -> dict:
    legge = next(iter(root))  # <Legge> (or another act element)
    units: dict[str, dict] = {}

    def put(key, label, kind, lines):
        if not lines:
            return
        k, n = key, 2
        while k in units:
            k, n = f'{key}-dup{n}', n + 1
        units[k] = {'label': label, 'kind': kind, 'text': '\n'.join(lines) + '\n'}
        return k

    rest_end: list[str] = []
    for ch in legge:
        n = local(ch.tag)
        if n == 'meta':
            continue
        if n == 'intestazione':
            put('intestazione', 'Intestazione', 'preamble', lines_of(ch))
        elif n == 'formulainiziale':
            put('preambolo', 'Preambolo', 'preamble', lines_of(ch))
        elif n == 'articolato':
            pending: list[str] = []
            last = [None]
            idx = [0]

            def walk(el):
                for c in el:
                    cn = local(c.tag)
                    if cn == 'articolo':
                        idx[0] += 1
                        num = c.find('num')
                        numt = ''.join(num.itertext()) if num is not None else ''
                        key = art_key(numt, idx[0])
                        ls = pending + num_lines_inline(c)
                        pending.clear()
                        last[0] = put(key, R.clean_line(numt) or f'Articolo {idx[0]}', 'art', ls)
                    elif cn in CONTAINERS:
                        if c.text and c.text.strip():
                            pending.append(R.clean_line(WS.sub(' ', c.text)))
                        for cc in c:
                            if local(cc.tag) in ('num', 'rubrica'):
                                pending.extend(lines_of_wrapped(cc))
                            else:
                                walk([cc])
                            if cc.tail and cc.tail.strip():
                                pending.append(R.clean_line(WS.sub(' ', cc.tail)))
                    else:
                        pending.extend(lines_of_wrapped(c))
                    if isinstance(el, list):
                        continue
                    if c.tail and c.tail.strip():
                        pending.append(R.clean_line(WS.sub(' ', c.tail)))
            if ch.text and ch.text.strip():
                pending.append(R.clean_line(WS.sub(' ', ch.text)))
            walk(ch)
            if pending:
                if last[0]:
                    u = units[last[0]]
                    u['text'] += '\n'.join(pending) + '\n'
                else:
                    put('articolato', 'Articolato', 'art', pending)
        elif n in ('formulafinale', 'conclusione'):
            rest_end.extend(lines_of_wrapped(ch))
        elif n == 'annessi':
            if rest_end:
                put('formula-finale', 'Formula finale', 'final', rest_end)
                rest_end = []
            put('allegati', 'Allegati', 'annex', lines_of_wrapped(ch))
        else:
            ls = lines_of_wrapped(ch)
            if ls and not any(u['kind'] == 'art' for u in units.values()) and not rest_end:
                if 'preambolo' in units:
                    units['preambolo']['text'] += NL.join(ls) + NL
                else:
                    put('preambolo', 'Preambolo', 'preamble', ls)
            else:
                rest_end.extend(ls)
        if ch.tail and ch.tail.strip():
            t = [R.clean_line(WS.sub(' ', ch.tail))]
            if not any(u['kind'] == 'art' for u in units.values()) and not rest_end:
                if 'preambolo' in units:
                    units['preambolo']['text'] += t[0] + NL
                else:
                    put('preambolo', 'Preambolo', 'preamble', t)
            else:
                rest_end.extend(t)
    put('formula-finale', 'Formula finale', 'final', rest_end)
    return units


def lines_of_wrapped(el) -> list[str]:
    buf: list[str] = []
    flat(el, buf, top=False)
    return [x for x in (R.clean_line(s) for s in ''.join(buf).split(BRK)) if x]


def nir_date(s: str) -> str | None:
    m = re.match(r'^(\d{4})(\d{2})(\d{2})$', s or '')
    if not m:
        return None
    try:
        return dt.date(int(m[1]), int(m[2]), int(m[3])).isoformat()
    except ValueError:
        return None


URN = re.compile(r'urn:nir:regione\.emilia\.romagna:(legge|regolamento|legge\.statutaria):(\d{4})-(\d{2})-(\d{2});(\d+)')


def law_of(m) -> tuple[str, dict]:
    kind, y, mo, d, n = m.groups()
    key = f'lr-{y}-{int(n)}' if kind == 'legge' else f'{R.ascii_slug(kind)}-{y}-{int(n)}'
    lab = 'L.R.' if kind == 'legge' else kind.capitalize()
    label = f'{lab} {int(d)} {MONTHS[int(mo) - 1]} {y}, n. {int(n)}'
    return key, {'label': label, 'title': label, 'kind': 'law', 'enacted': f'{y}-{mo}-{d}', 'published': None,
                 'url': f'https://demetra.regione.emilia-romagna.it/al/articolo?urn=er:assemblealegislativa:legge:'
                        f'{y};{int(n)}', 'temporary_until': None, 'restores': None, 'note': None}


def candidates(zs) -> list[dict]:
    out = []
    for leg, z in zs.items():
        for name in z.namelist():
            if not name.endswith('.xml'):
                continue
            raw = z.read(name)
            try:
                x = raw.decode('utf-8')
            except UnicodeDecodeError:
                x = raw.decode('latin-1')
            tipo = (re.search(r'<NIR[^>]*tipo="(\w+)"', x) or [None, '?'])[1]
            if re.search(r'<articolato[^>]*status="(abrogato|omissis)"', x):
                continue
            red = re.search(r'(?is)<redazionale>(.*)</redazionale>', x)
            if red and re.search(r'(?i)\blegge\s+abrogat', html.unescape(re.sub(r'<[^>]+>', '', red.group(1)))):
                continue
            passive = '<passiva' in x
            if tipo == 'originale' and (passive or (red and re.search(r'(?i)abrogat', red.group(1)))):
                continue  # an original text that is no longer the text in force
            if tipo not in ('vigente', 'originale'):
                continue
            mu = URN.search(re.search(r'<urn>(.*?)</urn>', x).group(1)) if re.search(r'<urn>(.*?)</urn>', x) else None
            if not mu:
                continue
            out.append({'leg': leg, 'name': name, 'tipo': tipo, 'urn': mu, 'x': x, 'raw': raw})
    # one file per law: a zip may list a member twice, and a file's URN may name another law (7_LR_2003_18.xml
    # carries the URN of L.R. 19/2003): prefer the file whose own name matches its URN, then the later legislature
    best: dict[tuple, dict] = {}
    for c in out:
        y, n = c['urn'].group(2), int(c['urn'].group(5))
        own = c['name'].endswith(f'_LR_{y}_{n}.xml')
        rank = (own, c['leg'])
        k = (c['urn'].group(1), y, n)
        if k not in best or rank > best[k][0]:
            best[k] = (rank, c)
    keep = {id(c) for _, c in best.values()}
    # the parts keep the membership they were first cut with (the whole list, duplicates included); a duplicate is
    # then dropped inside its part, so no published part changes
    out.sort(key=lambda c: (c['urn'].group(2), c['urn'].group(3), c['urn'].group(4), int(c['urn'].group(5))))
    for c in out:
        c['keep'] = id(c) in keep
    return out


def act_of(c) -> tuple[dict, dict] | None:
    raw, x = c['raw'], c['x']
    root = ET.fromstring(raw)
    units = units_of(root)
    if not any(u['kind'] == 'art' for u in units.values()):
        return None
    key, law = law_of(c['urn'])
    vig = nir_date((re.search(r'<vigenza[^>]*inizio="(\d*)"', x) or [None, ''])[1])
    pub = nir_date((re.search(r'<pubblicazione[^>]*norm="(\d*)"', x) or [None, ''])[1])
    title = R.clean_line(' '.join(''.join(t.itertext()) for t in root.iter('titoloDoc'))) or law['label']
    laws = {key: dict(law, title=title[:300])}
    y, n = c['urn'].group(2), int(c['urn'].group(5))
    if c['tipo'] == 'originale':
        law_pub = pub
        laws[key]['published'] = law_pub
        frm = vig or (dt.date.fromisoformat(law_pub) + dt.timedelta(days=15)).isoformat() if (vig or law_pub) else None
        first_law, earlier = key, []
    else:
        frm = vig
        first_law = None
        earlier = [key]
        for m in URN.finditer(' '.join(re.findall(r'<passiva[^>]*>', x))):
            k2, l2 = law_of(m)
            if frm and l2['enacted'] <= frm and k2 not in earlier:
                earlier.append(k2)
                laws[k2] = l2
    if not frm:
        frm = DOCS_DATE
        note = 'Demetra gives no start of validity for this text: dated the retrieval day.'
    else:
        note = None
    v = {'from': frm, 'source_url': ZIP.format(leg=c['leg']) + '#' + c['name'],
         'sha256': hashlib.sha256(raw).hexdigest(), 'units': units,
         'credits': {k: [first_law] for k in units} if first_law else {}}
    if note:
        v['note'] = note
    slug = 'statuto' if (y, n) == ('2005', 13) else f'lr-{y}-{n}'
    act = {'slug': slug, 'short': f'L.R. {n}/{y}' if slug != 'statuto' else 'Statuto',
           'title': (f'Statuto della Regione Emilia-Romagna (L.R. 31 marzo 2005, n. 13)' if slug == 'statuto'
                     else f'{law["label"]}: {title}')[:400],
           'url': law['url'], 'first_law': first_law, 'earlier_laws': earlier, 'versions': [v]}
    return act, laws


def decisions() -> list[str]:
    return [
        'Every regional law in Demetra\'s open-data zips (XML Norme in Rete, legislatures I-XII) is included unless '
        'Demetra marks it as wholly repealed (articolato status "abrogato" or "omissis", or an editor\'s note '
        '"Legge abrogata"), or its file holds only the original text of a law that has since been amended.',
        'A law never amended is recorded as first published, dated by its own start of validity, credited to itself. '
        'An amended law has its earlier versions from Demetra\'s storia tab (the original text and each "Testo '
        'Coordinato"), each dated by the in-force day of the law that made it (its own entry-into-force clause; '
        'else the start of validity Demetra records for a law never amended; else the fifteenth day after the '
        'publication day the storia tab gives) and credited to it, then its consolidated text in force, dated the '
        'start of validity Demetra gives for it (vigenza inizio).',
        'An earlier version is used only when Demetra\'s page for the current text reads into the same provisions as '
        'the open-data file, every provision whose wording changed reads line for line the same on that page as in '
        'the file (up to spaces), and the letters and digits of the version equal its page\'s. Otherwise the law '
        'keeps its current text only, as the oldest version available, credited to Demetra.',
        'An earlier version\'s heading, closing formula and signature, and annex titles are the current text\'s: '
        'Demetra\'s version pages do not print the closing formula, and they print the heading and annex titles the '
        'same as the current page (checked).',
        'Units: the heading (intestazione), the enacting formula and preamble, one file per article (headings of '
        'titles, chapters and sections in the file of the next article), the closing formula and signature, and '
        'annexes printed in the text. Demetra\'s editor\'s notes are not copied and their markers are dropped.',
        'Attachments shipped as separate files (spreadsheets, Word or PDF annexes) are not included.',
    ]


AI_USE = ['A model (Claude) wrote the parse code and chose which laws to include; it wrote no law text. Every word of '
          'law comes from Demetra\'s open-data XML files and, for earlier versions, from Demetra\'s version pages.']


def parse():
    zs = zips()
    cands = candidates(zs)
    acts, laws_all = [], {}
    for c in cands:
        r = act_of(c)
        if r is None:
            continue
        a, l = r
        acts.append((a, l, c['keep']))
    stat = [x for x in acts if x[0]['slug'] == 'statuto']
    rest = [x for x in acts if x[0]['slug'] != 'statuto']
    plan = [('10-statuto', stat)] + [(f'30-leggi-{i // PART_SIZE + 1:02d}', rest[i:i + PART_SIZE])
                                     for i in range(0, len(rest), PART_SIZE)]
    labels: dict[str, str] = {}
    for name, members in plan:
        part = {'country': R.country_block(SLUG, SRC), 'laws': {}, 'acts': []}
        for a, l, keep in members:
            if not keep:
                continue
            part['acts'].append(a)
            for k, v in l.items():
                labels.setdefault(k, v['label'])
                v['label'] = labels[k]
                if k in part['laws'] and part['laws'][k].get('published') and not v.get('published'):
                    continue
                part['laws'][k] = v
        part['laws'] = dict(sorted(part['laws'].items()))
        if name == '10-statuto':
            part.update(sources=[R.source_block(SRC, DOCS_DATE)], decisions=decisions(), ai_use=AI_USE)
        R.write_part(SLUG, name, part)
    print(f'{len(cands)} candidates, {len(acts)} acts, {len(plan)} parts')
    return plan


# ---------------------------------------------------------------- independent letters check

def letters_check(slug: str, part_name: str, path=None) -> list[str]:
    """Reads each source file again by regex (not ElementTree): everything after </meta>, ndr markers and comments
    removed, entities decoded; its letters and digits must equal the act's units', and each unit is found in order.
    `path`: a staged part to read instead of corpus.d/<part>.json (it_er_history.py checks earlier versions itself
    and passes only the current ones here)."""
    p = path or (R.folder(slug) / 'corpus.d' / f'{part_name}.json')
    part = json.loads(p.read_text(encoding='utf-8'))
    zs: dict[str, zipfile.ZipFile] = {}
    probs = []
    for act in part['acts']:
        for v in act['versions']:
            url, member = v['source_url'].split('#', 1)
            if url not in zs:
                zs[url] = zipfile.ZipFile(io.BytesIO(it_fetch.get(url)))
            raw = zs[url].read(member)
            if hashlib.sha256(raw).hexdigest() != v['sha256']:
                probs.append(f'{act["slug"]}: sha256 differs')
                continue
            try:
                x = raw.decode('utf-8')
            except UnicodeDecodeError:
                x = raw.decode('latin-1')
            body = x[x.find('</meta>') + 7:]
            body = re.sub(r'(?s)<!--.*?-->', '', body)
            body = re.sub(r'(?s)<ndr\b[^>]*/>|<ndr\b[^>]*>.*?</ndr>', '', body)
            body = html.unescape(re.sub(r'<[^>]+>', ' ', body))
            src = R.letters(body)
            mine = ''.join(u['text'] for u in v['units'].values())
            if Counter(src) != Counter(R.letters(mine)) or len(src) != len(R.letters(mine)):
                ca, cb = Counter(src), Counter(R.letters(mine))
                probs.append(f'{act["slug"]}: source-only {dict((ca - cb).most_common(6))} '
                             f'corpus-only {dict((cb - ca).most_common(6))}')
                continue
            pos = 0
            for k, u in v['units'].items():
                lu = R.letters(u['text'])
                i = src.find(lu, pos)
                if i < 0:
                    probs.append(f'{act["slug"]} {k}: not found in order')
                    break
                pos = i + len(lu)
    return probs


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    R.below_normal()
    cmd = sys.argv[1]
    if cmd == 'parse':
        parse()
    elif cmd == 'letters':
        pr = letters_check(SLUG, sys.argv[2])
        print('\n'.join(pr[:30]) or 'clean', len(pr))
    elif cmd == 'publish':
        for name in sys.argv[2:]:
            print(name, R.publish(SLUG, SRC, name, DOCS_DATE, letters_check)[:600], flush=True)
