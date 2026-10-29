"""Turns the cache of scripts/uruguay-law/fetch.py into scripts/uruguay-law/corpus.json (gitlaw_common/SCHEMA.md).

    python -X utf8 scripts/uruguay-law/parse.py

Reads only .cache/ (no network). Deterministic: the same cache gives the same bytes.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fetch  # noqa: E402
import impo_history  # noqa: E402

RETRIEVED = '2026-10-28'
IMPO = fetch.IMPO

from parse_text import (MARK, WRAP, _debug_word_diff, cell_paragraphs, impo_paragraphs, key_of,  # noqa: E402,F401
                        norm, strip_tags, wrap_width)


# ---------------------------------------------------------------- the Constitution

def letter_key(letter: str) -> str:
    base = letter[0].lower()
    primes = letter.count("'")
    return f'disp-trans-{base}' + ('', '-prima', '-segunda')[primes]


def letter_label(letter: str) -> str:
    return f'Disposición transitoria y especial {letter})'


def parlamento_constitution(raw: bytes) -> dict[str, list[str]]:
    """Units (key -> paragraphs) of a Parlamento HTML text of the Constitution."""
    try:
        h = raw.decode('utf-8')
    except UnicodeDecodeError:
        h = raw.decode('latin-1')
    i = h.find('<!--ARTICULADO')
    h = h[i:] if i >= 0 else h[h.index('name="art1"') - 200:]
    end = h.find('U-Include="pieley')
    h = h[:end] if end > 0 else h
    units: dict[str, list[str]] = {}
    cur: list[str] | None = None
    in_trans = False
    for m in re.finditer(r'<table\b.*?</table>|<h4\b[^>]*>.*?</h4>|<p\b[^>]*>.*?</p>', h, re.S | re.I):
        block = m.group(0)
        if block[:3].lower() == '<h4':
            if 'DISPOSICIONES TRANSITORIAS' in strip_tags(block).upper():
                in_trans = True
            continue
        if block[:6].lower() == '<table':
            for row in re.findall(r'<tr\b[^>]*>(.*?)</tr>', block, re.S | re.I):
                cells = re.findall(r'<td\b[^>]*>(.*?)</td>', row, re.S | re.I)
                if not cells:
                    continue
                lead = norm(strip_tags(cells[0]))
                if in_trans and lead and not lead.strip('*'):
                    return units          # the footnote table that closes the old site's pages
                lead = lead.replace('*', '').strip()
                body: list[str] = []
                pending = ''
                for c in cells[1:]:
                    if not norm(strip_tags(c)).strip('*'):
                        continue
                    ps = cell_paragraphs(c)
                    if len(ps) == 1 and re.fullmatch(r"(\d+º?|[A-Za-z]'{0,2})\)", ps[0]):
                        pending = f'{pending} {ps[0]}'.strip()   # a cell holding only an item's letter
                        continue
                    if pending and ps:
                        ps[0] = f'{pending} {ps[0]}'
                        pending = ''
                    body += ps
                if pending:
                    body.append(pending)
                if in_trans and re.fullmatch(r"[A-Z]('{0,2}|\")\)", lead):
                    letter = lead[0] + ("''" if '"' in lead else "'" * (len(lead) - 2))
                    k = letter_key(letter)
                    while k in units:          # the Parlamento repeats a letter where IMPO writes V'), Z")
                        letter += "'"
                        k = letter_key(letter)
                    cur = units.setdefault(k, [])
                    lead_txt = f'{letter})'
                    if body:
                        body[0] = f'{lead_txt} {body[0]}'
                    else:
                        body = [lead_txt]
                    cur += body
                    continue
                if cur is None:
                    continue
                if lead and body:
                    body[0] = f'{lead} {body[0]}'
                elif lead:
                    body = [lead]
                cur += body
            continue
        art = re.search(r'<a name="art(\d+)">', block)
        if art:
            in_trans = False
            cur = units.setdefault(f'art-{int(art.group(1)):03d}', [])
            text = re.sub(r'^.*?</u>\s*\.?-?\s*', '', block, count=1, flags=re.S)
            cur += cell_paragraphs(text)
            continue
        if cur is not None:
            cur += cell_paragraphs(block)
    # The transitional heading row "W)" etc. may carry an anchor; letters were read from the first cell.
    return units


def impo_constitution(main: dict, trans: dict) -> dict[str, list[str]]:
    width = wrap_width([a['textoArticulo'] for a in main['articulos']])
    units: dict[str, list[str]] = {}
    for a in main['articulos']:
        n = int(a['nroArticulo'])
        key = f'art-{n:03d}' + (f'-{a["secArticulo"].strip().lower()}' if a['secArticulo'].strip() else '')
        units[key] = impo_paragraphs(a['textoArticulo'], width)
    tx = trans['articulos'][0]['textoArticulo']
    paras = impo_paragraphs(tx, width)
    cur = None
    for p in paras:
        m = re.match(r"([A-Z])('{0,2}|\"|´{1,2})\)\s", p)
        if m:
            letter = m.group(1) + ("''" if m.group(2) in ('"', "''") else m.group(2).replace('´', "'"))
            cur = units.setdefault(letter_key(letter), [])
            p = f'{letter}) ' + p[m.end():]
        if cur is not None:
            cur.append(p)
    return units


def render(key: str, paras: list[str]) -> str:
    return f'# {label_of(key)}\n' + ''.join(p + '\n' for p in paras)


def label_of(key: str) -> str:
    if key.startswith('art-'):
        rest = key[4:]
        n, _, sec = rest.partition('-')
        return f'Artículo {int(n)}' + (f' {sec.upper()}' if sec else '')
    if key.startswith('disp-trans-'):
        rest = key[len('disp-trans-'):]
        letter = rest[0].upper() + {'': '', '-prima': "'", '-segunda': "''"}[rest[1:]]
        return letter_label(letter)
    return key


def unit_kind(key: str) -> str:
    return 'transitional' if key.startswith('disp-trans-') else 'art'


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------- reforms of the Constitution

# (law key, plebiscite day, version "from" day, Parlamento text of the Constitution as amended by it)
REFORMS = [
    ('plebiscito-1966-11-27', '1966-11-27', '1967-02-15', fetch.CONST_PARLAMENTO['1967']),
    ('plebiscito-1989-11-26', '1989-11-26', '1990-05-01', fetch.CONST_PARLAMENTO_OLD['1989']),
    ('plebiscito-1994-11-27', '1994-11-27', '1994-11-27', fetch.CONST_PARLAMENTO_OLD['1994']),
    ('plebiscito-1996-12-08', '1996-12-08', '1996-12-08', fetch.CONST_PARLAMENTO['1997']),
    ('plebiscito-2004-10-31', '2004-10-31', '2004-10-31', fetch.CONST_PARLAMENTO_OLD['2004']),
]
SPANISH_DAY = {'1966-11-27': '27 de noviembre de 1966', '1989-11-26': '26 de noviembre de 1989',
               '1994-11-27': '27 de noviembre de 1994', '1996-12-08': '8 de diciembre de 1996',
               '2004-10-31': '31 de octubre de 2004'}
LAW_NOTES = {
    'plebiscito-1966-11-27': ('Its transitional provision A) put it in force on 15 February 1967 (Secciones VIII '
                              'to XI and XVI on 1 March 1967); this version is dated 15 February 1967.'),
    'plebiscito-1989-11-26': ('Its transitional provision V) puts the reform of article 67 in force on 1 May 1990; '
                              'this version is dated on that day.'),
    'plebiscito-1994-11-27': ('It took effect when the Corte Electoral proclaimed the result. No source we read '
                              'dates that proclamation, so this version is dated on the plebiscite day; the '
                              'Parlamento files the text as "vigencia 1995".'),
    'plebiscito-1996-12-08': ('It took effect when the Corte Electoral proclaimed the result (its transitional '
                              'provision A). No official source we read dates that proclamation, so this version is '
                              'dated on the plebiscite day; the Parlamento files the text as "vigencia 1997".'),
    'plebiscito-2004-10-31': ('It took effect when the Corte Electoral proclaimed the result. No source we read '
                              'dates that proclamation, so this version is dated on the plebiscite day; Decreto '
                              '435/004 of 13 December 2004 states that the reform was then in force.'),
}
SPANISH_MONTH = {'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
                 'setiembre': 9, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12}


def spanish_date(s: str) -> str:
    d, m, y = re.match(r'(\d+) de (\w+) de (\d{4})', s).groups()
    return f'{y}-{SPANISH_MONTH[m.lower()]:02d}-{int(d):02d}'


def impo_reform_notes(main: dict, trans: dict) -> dict[str, set[str]]:
    """IMPO's own notes: plebiscite day -> the units it says that reform wrote or added."""
    out: dict[str, set[str]] = {}
    for a in main['articulos']:
        n = re.sub(r'\s+', ' ', strip_tags(a.get('notasArticulo') or ''))
        key = f'art-{int(a["nroArticulo"]):03d}'
        for m in re.finditer(r'plebiscito de fecha (\d+ de \w+ de \d{4})', n):
            out.setdefault(spanish_date(m.group(1)), set()).add(key)
    n = re.sub(r'\s+', ' ', strip_tags(trans['articulos'][0].get('notasArticulo') or '').replace('´', "'"))
    for sent in re.split(r'(?<=\d{4})\.', n):
        m = re.search(r'plebiscito de fecha (\d+ de \w+ de \d{4})', sent)
        lets = re.search(r'letras? (.*?) fue', sent)
        if not m or not lets:
            continue
        for letter, primes in re.findall(r"([A-Z])('{0,2}|\")\)", lets.group(1)):
            primes = "''" if primes == '"' else primes
            out.setdefault(spanish_date(m.group(1)), set()).add(letter_key(letter + primes))
    return out


def replay(current: list[str], target_key: str) -> list[str] | None:
    """IMPO's paragraphs with one block of paragraphs (incisos a later reform added) removed, when that has exactly
    the words of the earlier Parlamento text."""
    n = len(current)
    for i in range(n):
        for j in range(i + 1, n + 1):
            cand = current[:i] + current[j:]
            if cand and key_of('\n'.join(cand)) == target_key:
                return cand
    return None


def constitution(verification: dict) -> tuple[dict, dict]:
    c_url, t_url = fetch.ACTS['constitucion'][:2]
    raw_main, raw_trans = fetch.fetch(c_url, True), fetch.fetch(t_url, True)
    jm, jt = json.loads(raw_main.decode('latin-1')), json.loads(raw_trans.decode('latin-1'))
    current = impo_constitution(jm, jt)
    parl = [parlamento_constitution(fetch.fetch(u, True)) for *_, u in REFORMS]
    notes = impo_reform_notes(jm, jt)
    keys = sorted(set(current).union(*parl))
    n = len(REFORMS)

    def k(i: int, u: str) -> str | None:
        return key_of('\n'.join(parl[i][u])) if u in parl[i] else None

    touched: dict[int, set[str]] = {i: set() for i in range(1, n)}
    parl_only: list[dict] = []
    for u in keys:
        for i in range(1, n):
            if k(i, u) != k(i - 1, u):
                if u in notes.get(REFORMS[i][1], set()):
                    touched[i].add(u)
                else:
                    parl_only.append({'unit': u, 'between': [REFORMS[i - 1][1], REFORMS[i][1]],
                                      'diff': _debug_word_diff(' '.join(parl[i - 1].get(u, [])),
                                                               ' '.join(parl[i].get(u, [])))})
    for i in range(1, n):
        day = REFORMS[i][1]
        if touched[i] != notes.get(day, set()):
            raise SystemExit(f'reform {day}: Parlamento changes {sorted(touched[i])} '
                             f'!= IMPO notes {sorted(notes.get(day, set()))}')
    # A unit's text from its last reform on is IMPO's; before that it is the Parlamento's (or IMPO's minus the
    # incisos added later, when that has exactly the Parlamento's words).
    texts: list[dict[str, list[str]]] = [dict() for _ in range(n)]
    sources: dict[str, list[str]] = {}
    for u in keys:
        last = max([i for i in range(1, n) if u in touched[i]], default=0)
        for i in range(n):
            if i >= last:
                if u not in current:
                    raise SystemExit(f'{u} is in the Parlamento text but not in IMPO')
                texts[i][u] = current[u]
                sources.setdefault(u, []).append('impo')
            elif u in parl[i]:
                seg = max([j for j in range(1, i + 1) if u in touched[j]], default=0)
                r = replay(current[u], key_of('\n'.join(parl[seg][u])))
                texts[i][u] = r if r is not None else parl[seg][u]
                sources.setdefault(u, []).append('impo-minus-later-incisos' if r is not None else 'parlamento')
            else:
                sources.setdefault(u, []).append('-')
    differ = []
    for u in keys:
        if u in parl[-1] and u in current and k(n - 1, u) != key_of('\n'.join(current[u])):
            differ.append({'unit': u, 'diff': _debug_word_diff(' '.join(parl[-1][u]), ' '.join(current[u]))})
    verification['constitucion'] = {
        'reforms_match_impo_notes': {REFORMS[i][1]: sorted(touched[i]) for i in range(1, n)},
        'parlamento_changes_no_reform_explains': parl_only,
        'impo_vs_parlamento_2004_word_differences': differ,
        'unit_sources_per_version': {u: s for u, s in sources.items() if set(s) != {'impo'}},
    }
    laws, versions = {}, []
    for i, (law, day, frm, url) in enumerate(REFORMS):
        laws[law] = {'label': f'Plebiscito de {SPANISH_DAY[day]}',
                     'title': (f'Reforma constitucional aprobada por plebiscito de {SPANISH_DAY[day]}' if i else
                               'Constitución de la República, plebiscitada el 27 de noviembre de 1966'),
                     'kind': 'referendum', 'enacted': day,
                     'published': '1967-02-02' if i == 0 else None,
                     'url': url if i else c_url.replace('?json=true', ''),
                     'temporary_until': None, 'restores': None, 'note': LAW_NOTES[law]}
        units = {u: {'label': label_of(u), 'kind': unit_kind(u), 'text': render(u, ps)}
                 for u, ps in sorted(texts[i].items())}
        credits = {}
        if i:
            prev = versions[-1]['units']
            for u in sorted(set(units) | set(prev)):
                if units.get(u, {}).get('text') != prev.get(u, {}).get('text'):
                    credits[u] = [law]
        last = i == n - 1
        raw = raw_main if last else fetch.fetch(url, True)
        vnote = ('Today\'s text: IMPO\'s consolidated Constitución and Disposiciones Transitorias y Especiales.'
                 if last else
                 'Units a later reform changed are the Parlamento\'s text of this edition; every other unit is '
                 'IMPO\'s text, the same words in IMPO\'s transcription.')
        versions.append({'from': frm, 'source_url': c_url.replace('?json=true', '') if last else url,
                         'sha256': sha(raw), 'units': units, 'credits': credits, 'note': vnote})
    # Each version against its own Parlamento edition: every unit has the edition's words, except units where the
    # two publishers' transcriptions differ (listed above), and the units of today's text are IMPO's.
    vs = {}
    for i, v in enumerate(versions):
        other = [u for u in sorted(set(v['units']) | set(parl[i]))
                 if key_of(v['units'].get(u, {}).get('text', '')) != key_of('\n'.join(parl[i].get(u, [])))]
        vs[v['from']] = {'units': len(v['units']), 'parlamento_units': len(parl[i]),
                         'differ_from_parlamento_edition': other}
    verification['constitucion']['versions_vs_parlamento_edition'] = vs
    verification['constitucion']['last_version_equals_impo'] = all(
        versions[-1]['units'][u]['text'] == render(u, current[u]) for u in current) and len(current) == len(
        versions[-1]['units'])
    act = {'slug': 'constitucion', 'short': 'Constitución',
           'title': 'Constitución de la República Oriental del Uruguay',
           'url': c_url.replace('?json=true', ''), 'first_law': REFORMS[0][0], 'earlier_laws': [],
           'versions': versions}
    return laws, act


# slug, short, title, whether the norm's own law enacted the text (False: a re-edition, so the first commit is the
# oldest version available)
IMPO_TITLES = [
    ('ley-18331', 'Ley 18.331', 'Ley Nº 18.331 de Protección de Datos Personales', True),
    ('codigo-civil', 'Código Civil', 'Código Civil (texto aprobado por la Ley Nº 16.603)', False),
    ('codigo-penal', 'Código Penal', 'Código Penal (Ley Nº 9.155)', True),
]
# Norms whose own in-force day IMPO gives through another law: slug -> (IMPO path of that article, rule)
BASE_IN_FORCE = {
    'codigo-penal': ('leyes/9414-1934/2', '1934-08-01'),
}


COUNTRY = {
    'code': 'UY', 'name': 'Uruguay', 'slug': 'uruguay', 'lang': 'es', 'tz': 'America/Montevideo',
    'future_branch': 'futuro',
    'publisher': {'name': 'IMPO (Dirección Nacional de Impresiones y Publicaciones Oficiales)',
                  'email': 'impo@impo.invalid'},
    'default_in_force_rule': {
        'text': ('Código Civil art. 1: laws are binding by their promulgation by the Poder Ejecutivo, and the '
                 'promulgation is deemed known ten days after it is verified in the capital. A law\'s own '
                 'vigencia clause overrides this. A constitutional reform approved by plebiscite takes effect when '
                 'the Corte Electoral proclaims the result (Constitución, Disposición transitoria A).'),
        'source': f'{IMPO}/codigo-civil/16603-1994/1'},
    'licence_note': ('Texts from IMPO, Base de datos de normativa (www.impo.com.uy/bases), and the Parlamento del '
                     'Uruguay (parlamento.gub.uy, read through Wayback Machine captures).'),
}


def requests_count(prefix: str) -> int:
    log = fetch.CACHE / 'requests.jsonl'
    if not log.exists():
        return 0
    urls = {json.loads(l)['url'] for l in log.read_text(encoding='utf-8').splitlines() if l.strip()}
    return sum(1 for u in urls if prefix in u)


DECISIONS = [
    'Constitution: the dated texts are the Parlamento\'s editions of 1967, 1989, 1994, 1997 and 2004; today\'s '
    'text is IMPO\'s consolidated text. The units each reform changed come from comparing consecutive Parlamento '
    'editions word by word, and parse.py stops unless they equal the units IMPO\'s own notes ("redacción dada '
    'por", "agregado por") assign to that plebiscite.',
    'Constitution: the Parlamento and IMPO transcriptions differ in a few words in about 40 units (listed in '
    'verification.json). These are not changes in the law, so a unit uses IMPO\'s text from its last reform on '
    '(throughout, if no reform touched it), and the Parlamento\'s text only before that.',
    'Constitution: where a reform added incisos to an article (arts. 47, 67, 188), the earlier text is IMPO\'s '
    'text minus those incisos whenever that has exactly the Parlamento\'s earlier words.',
    'Constitution: the Parlamento\'s 2004 edition changes words in a few articles that no reform and no IMPO note '
    'explains (verification.json, parlamento_changes_no_reform_explains); they are not committed as changes.',
    'Constitution: the 1994, 1996 and 2004 reforms took effect when the Corte Electoral proclaimed the result. No '
    'source we read dates those proclamations, so their versions are dated on the plebiscite day, and each law\'s '
    'note says so.',
    'Constitution: the 1989 reform is dated 1 May 1990, the day its transitional provision V) puts it in force.',
    'Constitution: the Parlamento letters the 1994 and 2004 transitional provisions as a second V) and a further '
    'Z); IMPO letters them V\') and Z"). IMPO\'s lettering is used (disp-trans-v-prima, disp-trans-z-segunda).',
    'Laws (impo_history.py): IMPO gives only today\'s text, with notes naming the amending law and article for '
    'each change, and a link to the article as originally published. The first version of an amended article is '
    'that original text; today\'s text follows the last amending law. A text in between is used only when a '
    'source gives it: the wording the earlier amending law quotes (IMPO\'s original of that law), today\'s text '
    'without an item IMPO says a later law added, or the earlier text with an item replaced by the wording the '
    'amending law quotes for it. Otherwise the change is shown on the next known day, credited to every law in '
    'between, and verification.json lists it as unresolved.',
    'Laws: an amending law takes effect on the day its own vigencia article gives ("regirá a partir del …", read '
    'from IMPO\'s text of the article its notes point to, or for Ley 18.719 its art. 3, read by hand), else ten '
    'days after its publication in the Diario Oficial (Código Civil art. 1).',
    'Laws: amending laws that took effect before the norm\'s own first day are already in its text and are not '
    'credited.',
    'Código Civil: the oldest version is the text approved by Ley Nº 16.603 (promulgated 19 October 1994, published '
    '21 November 1994, in force 1 December 1994 by Código Civil art. 1), the re-edition IMPO consolidates. The code of '
    '1868 and its amendments before 1994 are not in IMPO\'s data, so the first commit is "oldest version available".',
    'Código Civil arts. 2393 to 2405: IMPO still prints them, with a note that Ley Nº 19.920 art. 62 repealed the '
    'Ley Nº 10.084 that added them; they are removed on Ley 19.920\'s day.',
    'Vigencia articles read by hand (fetch.IMPO_ACTS) where IMPO\'s notes do not point to one: Ley 18.719 art. 3, '
    'Ley 17.703 art. 46, Ley 18.387 art. 255, Ley 19.075 art. 29, Ley 19.920 art. 63, Ley 19.670 art. 2, '
    'Ley 15.903 art. 2, Ley 17.897 art. 23 (in force on promulgation).',
    'Código Penal: in force 1 August 1934 by Ley Nº 9.414 art. 2, which IMPO\'s note on the code cites. IMPO\'s text '
    'is the update of the Versión Oficial of 26 October 1967 (Decreto 698/967), and IMPO records no amendment before '
    'Ley 13.737 (1969); changes made between 1934 and 1969, if any, are not shown and would appear inside the next '
    'recorded change of that article. A sample of 11 unamended articles has exactly the words of IMPO\'s 1933 '
    'original text.',
    'Código Penal: Ley 19.138 takes effect ten days after its regulation by the Poder Ejecutivo, which we did not '
    'date; its one change (art. 350 BIS literal C) is dated by the default rule.',
    'Unit text: IMPO\'s hard-wrapped lines are joined into paragraphs (one paragraph or lettered item per line); '
    'ordinal marks, quotes and IMPO\'s "(*)" amended markers are normalised once in parse.py.',
]


def as_changes(act: dict) -> None:
    """After the first version, write each version as `changes` against the one before (SCHEMA.md, Large acts)."""
    prev = act['versions'][0]['units']
    for v in act['versions'][1:]:
        units = v.pop('units')
        v['changes'] = {k: units.get(k) for k in sorted(set(units) | set(prev)) if units.get(k) != prev.get(k)}
        prev = units
    for v in act['versions']:     # keep the key order of SCHEMA.md
        for k in ('credits', 'note'):
            v[k] = v.pop(k)


def main() -> None:
    if '--diff' in sys.argv:
        return
    verification: dict = {}
    laws, act = constitution(verification)
    acts = [act]
    for slug, short, title, enacted in IMPO_TITLES:
        path, base, vig = fetch.IMPO_ACTS[slug]
        bif = None
        if slug in BASE_IN_FORCE:
            vpath, day = BASE_IN_FORCE[slug]
            text = ' '.join(impo_history.load(vpath)['textoArticulo'].split())
            assert '1° de Agosto' in text, text      # Ley 9.414 art. 2: "El 1° de Agosto del corriente año ..."
            bif = (day, f'{vpath}: "{text}"')
        l2, a2 = impo_history.build_act(slug=slug, short=short, title=title, path=path, base=base,
                                        vigencia_arts=vig, verification=verification, base_is_enactment=enacted,
                                        base_in_force=bif)
        laws.update(l2)
        acts.append(a2)
    corpus = {
        'country': COUNTRY,
        'sources': [
            {'name': 'IMPO, Base de datos de normativa', 'url': 'https://www.impo.com.uy/bases',
             'retrieved': RETRIEVED, 'requests': requests_count('impo.com.uy'), 'licence': COUNTRY['licence_note'],
             'notes': 'JSON (?json=true) of the consolidated text in force, with IMPO\'s notes per article. '
                      'robots.txt Crawl-Delay: 10 is kept.'},
            {'name': 'Parlamento del Uruguay, dated texts of the Constitución, via the Wayback Machine',
             'url': 'https://parlamento.gub.uy/documentosyleyes/constitucion', 'retrieved': RETRIEVED,
             'requests': requests_count('web.archive.org'), 'licence': COUNTRY['licence_note'],
             'notes': 'parlamento.gub.uy answers 403 to this machine; capture timestamps are pinned in fetch.py.'},
        ],
        'laws': dict(sorted(laws.items())),
        'acts': acts,
        'applies': [],
        'decisions': DECISIONS,
        'ai_use': ['A model (Claude) wrote fetch.py and parse.py and chose the sources. It wrote no legal text: '
                   'every unit is parsed from IMPO or Parlamento bytes in the cache.'],
    }
    for a in corpus['acts']:
        as_changes(a)
    tmp = HERE / 'corpus.json.tmp'
    tmp.write_text(json.dumps(corpus, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    tmp.replace(HERE / 'corpus.json')
    (HERE / 'repo' / 'data').mkdir(parents=True, exist_ok=True)
    (HERE / 'repo' / 'data' / 'verification.json').write_text(json.dumps(verification, ensure_ascii=False, indent=1) + '\n',
                                            encoding='utf-8', newline='\n')
    for a in corpus['acts']:
        print(a['slug'], len(a['versions']), 'versions,',
              sum(len(v['credits']) for v in a['versions']), 'credited unit changes')




if __name__ == '__main__':
    main()
