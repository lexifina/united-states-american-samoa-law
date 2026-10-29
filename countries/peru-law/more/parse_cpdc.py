"""Build corpus.d/70-consumidor.json: the Código de Protección y Defensa del Consumidor (Ley 29571) with its history.

Reads only the cache (../.cache). Deterministic. Writes atomically.

    python -X utf8 more/parse_cpdc.py            write ../corpus.d/70-consumidor.json
    python -X utf8 more/parse_cpdc.py --report   print problems, the law table and the checkpoints
    python -X utf8 more/parse_cpdc.py --out P    write elsewhere (testing)

Backwards from the Ministry of Justice's third official edition (current to 27 Nov 2020): its footnotes quote the
wording before each amendment. Forwards from that edition: the amending laws' own texts (more/cpdc_forward.py).
Checkpoints: the second official edition (31 May 2018), Editora Peru's NLA (Aug 2024) and the SPIJ text Indecopi
publishes on gob.pe (April 2025).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import fetch  # noqa: E402
import edition  # noqa: E402
import history  # noqa: E402
import cpdc_forward as forward  # noqa: E402
from history import Problem, calls_in, classify, strip_calls, vigencia  # noqa: E402

ED3 = 'https://cdn.www.gob.pe/uploads/document/file/1837776/C%C3%B3digo%20Protecci%C3%B3n%20Consumidor%202020.pdf?v=1619483959'
ED3_PAGE = ('https://www.gob.pe/institucion/minjus/informes-publicaciones/1877837-codigo-de-proteccion-y-defensa-del-'
            'consumidor-y-normas-complementarias-tercera-edicion-oficial-actualizada-al-27-de-noviembre-de-2020')
ED3_PAGES = (58, 159)
ED3_DATE = '2020-11-27'     # "La presente edición se encuentra actualizada hasta el 27 de noviembre de 2020" (p. 12)
ED2 = ('https://web.archive.org/web/20191101065438id_/http://spij.minjus.gob.pe:80/content/publicaciones_oficiales/'
       'img/CODIGO-CONSUMIDOR.pdf')
ED2_PAGES = (28, 131)
ED2_DATE = '2018-05-31'     # "La presente edición se encuentra actualizada hasta el 31 de mayo de 2018"
NLA = 'https://web.archive.org/web/20240819051628id_/https://diariooficial.elperuano.pe/Normas/obtenerDocumento?idNorma=17'
SPIJ = 'https://cdn.www.gob.pe/uploads/document/file/1351847/1244218-ley-29571_spij.pdf?v=1745616997'
PUBLISHED = '2010-09-02'
D0 = '2010-10-02'   # Cuarta Disposición Complementaria Final: in force 30 calendar days counted from the day after publication

OUT = HERE.parent / 'corpus.d' / '70-consumidor.json'

# Typesetting faults of the third edition, mended from the second official edition (no law touched these
# provisions between the two): unit key -> paragraph index.
#   art-121: the third edition drops the end of the first paragraph ("...a partir del día en que la" + nothing)
#   art-042: the third edition breaks "anotaciones" as "anotacion es" across a line
EDITION_FIXES = {'art-121': 1, 'art-042': 1}

# Notes whose quote gives only the changed part without a "(...)" marker: treated as partial quotes.
PARTIAL = {'20', '27', '42'}


def wb_path(url: str) -> Path | None:
    """A Wayback/archive capture cached by gitlaw_common/wayback.py (sha256 of the URL, no .json metadata)."""
    p = fetch.CACHE / hashlib.sha256(url.encode('utf-8')).hexdigest()
    return p if p.exists() else None


def text_of(paras: list[str]) -> str:
    return ''.join(strip_calls(p).rstrip() + '\n' for p in paras)


def unquote(paras: list[str]) -> list[str]:
    """The editions print quoted earlier wording between “ and ”; drop those marks (a paragraph with an odd number of
    quote marks opens or closes the quotation). A full stop printed after the closing quote ends the provision."""
    out = []
    for p in paras:
        core = strip_calls(p).strip()
        if core.count('"') % 2 == 0 and core.startswith('"') and re.search(r'"\s*\.?$', core) and len(core) > 2:
            # one quoted paragraph: “…”. -> …
            p = re.sub(r'^(\s*(?:\x01[^\x01]*\x01)*)\s*"\s*', r'\1', p, count=1)
            p = re.sub(r'"\s*(\.?)\s*((?:\x01[^\x01]*\x01)*)\s*$', lambda m: (m.group(1) or '') + m.group(2), p)
            p = re.sub(r'\.\.((?:\x01[^\x01]*\x01)*)$', r'.\1', p)
            out.append(p)
            continue
        if core.count('"') % 2 == 1:
            if core.lstrip().startswith('"'):
                p = re.sub(r'^(\s*(?:\x01[^\x01]*\x01)*)\s*"\s*', r'\1', p, count=1)
            elif re.search(r'"\s*\.?\s*(?:\x01[^\x01]*\x01)*\s*$', p):
                p = re.sub(r'"\s*(\.?)\s*((?:\x01[^\x01]*\x01)*)\s*$', lambda m: (m.group(1) or '') + m.group(2), p)
                p = re.sub(r'\.\.((?:\x01[^\x01]*\x01)*)$', r'.\1', p)
        core = strip_calls(p)
        if core.count('"') % 2 == 1 and re.search(r'"\s*\.?\s*(?:\x01[^\x01]*\x01)*\s*$', p):
            p = re.sub(r'"\s*(\.?)\s*((?:\x01[^\x01]*\x01)*)\s*$', lambda m: (m.group(1) or '') + m.group(2), p)
        out.append(p)
    return out


def fix_note(n: edition.Note):
    if n.quote:
        n.quote = unquote(n.quote)
        whole = re.match(r'\s*Art[íi]culo\s+(?:\d+(?:-[A-Z])?\s+)?(?:modificad|sustituid)', n.header, re.I)
        if (n.id in PARTIAL or not whole) and not any(edition.ELLIPSIS.match(strip_calls(p)) for p in n.quote):
            # mark the quote as partial: the changed part follows the heading (or stands alone)
            q = n.quote
            if q and (edition.HEAD.match(strip_calls(q[0])) or edition.DISP.match(strip_calls(q[0]))):
                n.quote = [q[0], '(...)'] + q[1:]
            else:
                n.quote = ['(...)'] + q
    for s in n.subs.values():
        fix_note(s)


def load(path: Path, pages, profile):
    body, notes = edition.read(str(path), *pages, profile)
    units, struct = edition.units(body)
    trees = {str(n): edition.note_tree(ls, str(n)) for n, ls in notes.items()}
    for t in trees.values():
        fix_note(t)
    return units, struct, trees


def _undo_77(paras: list[str], note: edition.Note) -> list[str]:
    """Note 9 (Ley 30534): the law's own text (ADLP 30534-TXM) adds literals c) to f) to numeral 77.1 and replaces
    its closing paragraph; the note quotes only the old closing paragraph."""
    i = next(i for i, p in enumerate(paras) if edition.label_of(p) == ('lit', 'b'))
    j = next(j for j in range(i + 1, len(paras)) if edition.label_of(paras[j]) is None)
    old = [p for p in note.quote if not edition.ELLIPSIS.match(p) and edition.label_of(p) is None
           and not edition.HEAD.match(p)]
    assert len(old) == 1 and strip_calls(paras[j]).startswith('Los proveedores deben adoptar medidas'), (old, paras[j])
    return paras[:i + 1] + old + paras[j + 1:]


ED2_TEXT: dict[str, list[str]] = {}     # filled by build(): the second edition's provisions, notes and calls removed


def ed2_paras(paras: list[str]) -> list[str]:
    """A second-edition provision without its CONCORDANCIAS box (edition furniture) and footnote calls."""
    out = []
    for p in paras:
        if strip_calls(p).startswith('CONCORDANCIAS'):
            break
        out.append(edition.clean_par(strip_calls(p)))
    return out


def _undo_106(paras: list[str], note: edition.Note) -> list[str]:
    """Notes 20-23 (Decreto Legislativo 1390) restructure art. 106 into 106.1 and 106.2 and quote only fragments;
    the wording before is the second official edition's (current to 31 May 2018; nothing changed art. 106 between
    then and Decreto Legislativo 1390)."""
    return list(ED2_TEXT['art-106'])


def _same(paras: list[str], note: edition.Note) -> list[str]:
    """Covered by note 23's undo (the whole article from the second edition)."""
    return paras


MANUAL_UNDO = {('art-077', '9'): _undo_77, ('art-106', '23'): _undo_106, ('art-106', '22'): _same,
               ('art-106', '21'): _same, ('art-106', '20'): _same}

_orig_undo = history.undo


def _undo(ev, paras, log, unit):
    f = MANUAL_UNDO.get((unit, ev.note.id))
    if f:
        log.append(f'{unit} note {ev.note.id}: undone by hand ({f.__doc__.split(";")[0].strip()})')
        return f(paras, ev.note)
    return _orig_undo(ev, paras, log, unit)


history.undo = _undo

# Start days the notes do not give by themselves, with where they come from.
OVERRIDE: dict[str, tuple[str, str]] = {}


def law_table(trees: dict, log: list[str]):
    laws: dict[str, dict] = {}
    for t in trees.values():
        for ev in history.all_events(t):
            if not ev.law or ev.kind != 'words':
                continue
            key, label = ev.law
            L = laws.setdefault(key, {'label': label, 'published': set(), 'stated': {}})
            if ev.published:
                L['published'].add(ev.published)
            d, how = vigencia(ev.note.header, ev.published)
            if how:
                L['stated'].setdefault(d, how)
    out = {}
    for key, L in laws.items():
        pubs = sorted(L['published'])
        if len(pubs) > 1:
            log.append(f'law {key}: notes give several publication days {pubs}; using the earliest')
        pub = pubs[0] if pubs else None
        stated = {d: h for d, h in L['stated'].items() if d}
        if key in OVERRIDE:
            d, how = OVERRIDE[key]
        elif len(stated) == 1:
            d, how = next(iter(stated.items()))
        elif pub:
            d, how = history.plus(pub, days=1), 'default: the day after publication (Constitución art. 109)'
        else:
            d, how = None, None
        out[key] = {'label': L['label'], 'published': pub, 'in_force': d, 'how': how}
    return out


def words(paras) -> str:
    t = ' '.join(strip_calls(p) for p in paras)
    t = re.sub(r'(Art[íi]culo\s+[IVXL\d]+)\s*[°º˚]', r'\1', t)
    t = re.sub(r'\(\s*sic\s*\)', ' ', t)
    t = t.replace('núm.', 'Nº').replace('N°', 'Nº')
    return ' '.join(re.findall(r'\w+', t.lower()))


def word_diff(a: str, b: str, n: int = 6) -> str:
    import difflib
    a, b = a.split(), b.split()
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag != 'equal':
            out.append(f'[{" ".join(a[i1:i2])[:150]} => {" ".join(b[j1:j2])[:150]}]')
    return f'{len(out)} edits: ' + ' '.join(out[:n])


def state_on(versions, day):
    st = {}
    for v in versions:
        if v['from'] > day:
            break
        for k, u in (v.get('units') or v.get('changes') or {}).items():
            if u is None:
                st.pop(k, None)
            else:
                st[k] = u
    return st


def compare(st: dict, theirs: dict[str, str]):
    res = {'same': [], 'diff': [], 'missing_here': [], 'missing_there': []}
    for key in sorted(set(st) | set(theirs)):
        if key == 'promulgacion':
            continue
        if key not in st:
            res['missing_here'].append(key)
            continue
        if key not in theirs:
            res['missing_there'].append(key)
            continue
        a = words([st[key]['text']])
        b = theirs[key]
        (res['same'] if a == b else res['diff']).append(key if a == b else (key, a, b))
    return res


def build(report: bool = False):
    log: list[str] = []
    path = fetch.cached(ED3)
    if path is None:
        raise SystemExit(f'not in the cache: {ED3}')
    units, struct, trees = load(path, ED3_PAGES, 'cpdc')
    ed2_units, _, _ = load(wb_path(ED2), ED2_PAGES, 'cpdc2')
    ed2 = {u['key']: u['paras'] for u in ed2_units}
    ED2_TEXT.clear()
    ED2_TEXT.update({k: ed2_paras(v) for k, v in ed2.items()})
    for u in units:
        if u['key'] in EDITION_FIXES:
            i = EDITION_FIXES[u['key']]
            old, new = u['paras'][i], ed2[u['key']][i]
            assert not calls_in(old) and not calls_in(new), (old, new)
            log.append(f'{u["key"]}: third-edition paragraph {i} "{old}" replaced by the second edition\'s "{new}"')
            u['paras'][i] = new
    owner: dict[str, str] = {}
    for u in units:
        for p in u['paras']:
            for c in calls_in(p):
                owner[c] = u['key']
    for s, i in struct:
        for c in calls_in(s):
            owner[c] = 'estructura'
    for n in trees:
        if n not in owner:
            log.append(f'note {n} has no call in the body')
    laws = law_table(trees, log)

    def indate(ev):
        return laws[ev.law[0]]['in_force'] if ev.law else None

    problems = []
    timelines = {}
    for u in units:
        mine = {n: trees[n] for n in sorted(trees, key=int) if owner.get(n) == u['key']}
        try:
            orig, states, others = history.rewind(u['paras'], mine, indate, log, u['key'])
        except Problem as e:
            problems.append(str(e))
            continue
        timelines[u['key']] = (orig, states)
        for ev in others:
            if ev.kind not in ('info', 'erratum', 'commence'):
                log.append(f'{u["key"]}: note {ev.note.id} not used: {ev.note.header[:120]}')
    corpus = assemble(path, units, laws, timelines, log) if not problems else None
    checks = {}
    if corpus:
        versions = corpus['acts'][0]['versions']
        for name, (url, pages, prof, date) in CHECKPOINTS.items():
            p = wb_path(url) or fetch.cached(url)
            if p is None:
                continue
            us, _, _ = load(p, pages, prof)
            checks[name] = compare(state_on(versions, date), {u['key']: words(ed2_paras(u['paras'])) for u in us})
        for name, (date, parse) in forward.CHECKS.items():
            theirs = parse()
            if theirs:
                checks[name] = compare(state_on(versions, date), theirs)
        corpus['decisions'] += checkpoint_decisions(checks)
    if report:
        for name, res in checks.items():
            print(f'CHECKPOINT {name}: {len(res["same"])} same, {len(res["diff"])} differ, '
                  f'missing here {res["missing_here"]}, missing there {res["missing_there"]}')
            for k, a, b in res['diff']:
                print(f'   {k}: {word_diff(a, b)}')
        print('LAWS')
        for k, v in sorted(laws.items()):
            print('  ', k, v)
        print('PROBLEMS', len(problems))
        for p in problems:
            print('  ', p)
        print('LOG', len(log))
        for l in log:
            print('  ', l)
    return {'problems': problems, 'corpus': corpus, 'checks': checks, 'log': log}


CHECKPOINTS = {
    # name: (url, pages, layout profile, "actualizada hasta")
    'ed2-2018': (ED2, ED2_PAGES, 'cpdc2', ED2_DATE),
}


def unit_obj(label, kind, paras):
    return {'label': label, 'kind': kind, 'text': text_of(paras)}


def assemble(path, units, laws, timelines, log):
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    by_key = {u['key']: u for u in units}
    used_laws = {'ley-29571'}
    events: dict[str, dict] = {}

    def ev(day):
        return events.setdefault(day, {'changes': {}, 'credits': {}, 'notes': []})

    first_units = {}
    for key in [u['key'] for u in units]:
        if key not in timelines:
            continue
        orig, states = timelines[key]
        u = by_key[key]
        if orig is not None:
            first_units[key] = unit_obj(u['label'], u['kind'], orig)
        last = {}
        for day, law, paras, e in states:
            if day is None:
                raise SystemExit(f'{key}: a change with no in-force day ({e})')
            last[day] = paras
            ev(day)['credits'].setdefault(key, [])
            if law and law not in ev(day)['credits'][key]:
                ev(day)['credits'][key].append(law)
                used_laws.add(law)
        for day, paras in last.items():
            ev(day)['changes'][key] = unit_obj(u['label'], u['kind'], paras) if paras is not None else None

    days = sorted(events)
    if any(d <= D0 for d in days):
        raise SystemExit(f'an event before the first version: {[d for d in days if d <= D0]}')
    versions = [{'from': D0, 'source_url': ED3, 'sha256': sha, 'units': dict(sorted(first_units.items())),
                 'credits': {}, 'note': FIRST_NOTE}]
    for d in days:
        e = events[d]
        v = {'from': d, 'source_url': ED3, 'sha256': sha, 'changes': dict(sorted(e['changes'].items())),
             'credits': {k: sorted(ls) for k, ls in sorted(e['credits'].items()) if ls}}
        versions.append(v)

    # The third-edition point: the replayed state must equal the edition's own text.
    state = state_on(versions, '9999-12-31')
    ed3 = {u['key']: text_of(u['paras']) for u in units}
    bad = sorted(k for k in set(ed3) | set(state) if ed3.get(k) != (state.get(k) or {}).get('text'))
    if bad:
        raise SystemExit(f'the state after the last third-edition version differs from the edition: {bad[:20]}')
    log.append(f'third-edition point: {len(ed3)} provisions equal the edition\'s text exactly')

    # After the edition: the laws' own texts
    extra_laws = {}
    applied = forward.apply(state, log)      # in publication order; versions go in in-force order
    for a in applied:
        for b in applied:
            if applied.index(a) < applied.index(b) and a['in_force'] > b['in_force'] and set(a['changes']) & set(b['changes']):
                raise SystemExit(f'{a["key"]} and {b["key"]} change the same provision out of order')
    if applied and applied[0]['in_force'] <= versions[-1]['from']:
        raise SystemExit('a forward law takes effect before the last edition-based version')
    for law in sorted(applied, key=lambda x: x['in_force']):
        key, day = law['key'], law['in_force']
        if versions[-1]['from'] == day:
            prev = versions[-1]
            prev['changes'].update(law['changes'])
            for k in law['changes']:
                prev['credits'][k] = sorted(set(prev['credits'].get(k, [])) | {key})
            prev['note'] = (prev.get('note', '') + ' ' + law['vnote']).strip()
        else:
            versions.append({'from': day, 'source_url': law['url'], 'sha256': law['sha256'],
                             'changes': dict(sorted(law['changes'].items())),
                             'credits': {k: [key] for k in sorted(law['changes'])}, 'note': law['vnote']})
        extra_laws[key] = law['law']
        used_laws.add(key)

    law_objs = {}
    for key in sorted(used_laws):
        if key in extra_laws:
            law_objs[key] = extra_laws[key]
        elif key in EXTRA_LAWS:
            law_objs[key] = EXTRA_LAWS[key]
        else:
            L = laws[key]
            law_objs[key] = {'label': L['label'], 'title': None, 'kind': 'law' if key.startswith('ley-') else 'decree',
                             'enacted': None, 'published': L['published'], 'url': LAW_URLS.get(key),
                             'temporary_until': None, 'restores': None, 'note': None}
    act = {'slug': 'codigo-consumidor', 'short': 'CPDC',
           'title': 'Código de Protección y Defensa del Consumidor (Ley 29571)',
           'url': ED3_PAGE, 'first_law': 'ley-29571', 'earlier_laws': [], 'versions': versions}
    return {'laws': law_objs, 'acts': [act], 'sources': SOURCES + forward.sources(),
            'decisions': decisions(laws) + forward.DECISIONS,
            'ai_use': ['none: no model wrote or chose any legal text; parsing is rule-based (more/edition.py, '
                       'more/history.py, more/cpdc_forward.py).']}


FIRST_NOTE = ('Ley 29571 as published in El Peruano on 2 September 2010, rebuilt from the "Texto anterior" footnotes of '
              'the Ministry of Justice\'s third official edition (current to 27 November 2020). The Code took effect 30 '
              'calendar days after the day following publication (Cuarta Disposición Complementaria Final); arts. 36 '
              'and 37 and the summary procedure (Título V, Capítulo III, Subcapítulo III) started later, 180 and 60 '
              'days after that.')

LAW_URLS = {
    'dleg-1308': 'https://cdn.www.gob.pe/uploads/document/file/1536616/DL%201308.pdf.pdf?v=1610113212',
    'dleg-1390': 'https://www.leyes.congreso.gob.pe/Documentos/2016_2021/Boletin_de_Normas_Legales/NL20180905.pdf',
    'ley-29888': 'https://www.leyes.congreso.gob.pe/Documentos/Leyes/29888.pdf',
    'ley-30046': 'https://www.leyes.congreso.gob.pe/Documentos/Leyes/30046.pdf',
    'ley-30534': 'https://www.leyes.congreso.gob.pe/Documentos/2016_2021/ADLP/Texto_Consolidado/30534-TXM.pdf',
    'ley-30908': 'https://www.leyes.congreso.gob.pe/Documentos/2016_2021/ADLP/Texto_Consolidado/30908-TXM.pdf',
    'ley-31040': 'https://www.leyes.congreso.gob.pe/Documentos/2016_2021/Boletin_de_Normas_Legales/NL20200829.pdf',
}

EXTRA_LAWS = {
    'ley-29571': {'label': 'Ley 29571', 'title': 'Código de Protección y Defensa del Consumidor', 'kind': 'law',
                  'enacted': '2010-09-01', 'published': '2010-09-02',
                  'url': 'https://www.gob.pe/institucion/indecopi/normas-legales/1244218-29571',
                  'temporary_until': None, 'restores': None, 'note': None},
}

SOURCES = [
    {'name': 'Ministerio de Justicia y Derechos Humanos: Código de Protección y Defensa del Consumidor y Normas '
             'Complementarias, Tercera Edición Oficial (diciembre 2020, actualizada al 27 de noviembre de 2020)',
     'url': ED3, 'retrieved': '2026-10-29', 'requests': 1,
     'licence': 'Official text (Peruvian legal norms are not subject to copyright, D.Leg. 822 art. 9)',
     'notes': 'PDF with a text layer, 312 pages (the Code on pp. 59-160). Footnotes quote the wording before each '
              'amendment ("Texto anterior a la modificación"). Body DINPro 9.5 pt, footnotes ClarendonBT 7 pt.'},
    {'name': 'MINJUS: Código de Protección y Defensa del Consumidor, Segunda Edición Oficial (junio 2018, actualizada '
             'al 31 de mayo de 2018), as served by SPIJ; Internet Archive capture 2019-11-01 06:54:38 UTC',
     'url': ED2, 'retrieved': '2026-10-29', 'requests': 1, 'licence': 'as above; archive.org capture',
     'notes': 'checkpoint only'},
    {'name': 'Decreto Legislativo 1308 (El Peruano, 30 December 2016), PCM copy on gob.pe',
     'url': LAW_URLS['dleg-1308'], 'retrieved': '2026-10-29', 'requests': 1, 'licence': 'as above',
     'notes': 'text layer; read for its vigencia (none of its own: the day after publication)'},
    {'name': 'El Peruano, Normas Legales, 5 September 2018 (Decreto Legislativo 1390), Congreso copy',
     'url': LAW_URLS['dleg-1390'], 'retrieved': '2026-10-29', 'requests': 1, 'licence': 'as above',
     'notes': 'text layer; read for its vigencia (none of its own: the day after publication)'},
    {'name': 'Congreso ADLP: Leyes 30534 and 30908 (texto publicado en El Peruano)',
     'url': LAW_URLS['ley-30534'], 'retrieved': '2026-10-29', 'requests': 2, 'licence': 'as above',
     'notes': 'text layer; Ley 30534 gives the change to art. 77 the edition\'s note leaves out; both read for vigencia '
              '(none of their own); Ley 30908 at ' + LAW_URLS['ley-30908']},
    {'name': 'El Peruano, Normas Legales, 29 August 2020 (Ley 31040), Congreso copy',
     'url': LAW_URLS['ley-31040'], 'retrieved': '2026-10-29', 'requests': 1, 'licence': 'as above',
     'notes': 'text layer; read for its vigencia (none of its own)'},
]


def decisions(laws):
    out = [
        'Código de Protección y Defensa del Consumidor part (more/parse_cpdc.py, corpus.d/70-consumidor.json) is built '
        'from the Ministry of Justice\'s third official edition (text layer, no OCR). Its footnotes quote the wording '
        'before each amendment; more/history.py (a copy of proc/history.py) replays them backwards, newest first.',
        'The first version is the Code as published on 2 September 2010, in force on 2 October 2010 (Cuarta '
        'Disposición Complementaria Final: 30 calendar days counted from the day after publication), credited to '
        'Ley 29571. The later start of arts. 36-37 (180 days) and of the summary procedure (60 days) is noted in the '
        'first version, not committed separately.',
        'In-force days: the day after publication (Constitución art. 109) unless the law sets its own start. Decreto '
        'Legislativo 1308 (30 December 2016) and 1390 (5 September 2018) and Leyes 30534, 30908 and 31040 set none '
        '(read in their texts). The Congreso copies of Leyes 29888 and 30046 are image scans (no OCR), so their '
        'texts were not read; the default rule is applied to them.',
        'Art. 77 (Ley 30534): the edition\'s note quotes only the old closing paragraph of numeral 77.1; the law\'s '
        'own text shows it also added literals c) to f), so the earlier wording has literals a) and b) and the quoted '
        'closing paragraph.',
        'Art. 106 (Decreto Legislativo 1390): the edition\'s four notes quote fragments of a restructured article; the '
        'wording before is taken from the second official edition (current to 31 May 2018; no change to art. 106 '
        'between then and 6 September 2018).',
        'Two typesetting faults of the third edition are mended from the second edition: art. 121 loses the end of its '
        'first paragraph ("... desde que cesó, si fuera una infracción continuada."), and art. 42.1 prints '
        '"anotacion es" for "anotaciones".',
        'Quotation marks around quoted earlier wording are the editions\' typesetting and are dropped; a full stop '
        'printed after the closing quote ends the provision.',
        'Footnotes 20, 27 and 42 quote only the changed lead-in, literal or numeral without the edition\'s usual '
        '"(...)" marker; they are read as partial quotes (the rest of the article unchanged).',
        'Footnotes that only interpret, report concordances or report a related rule ("De conformidad con...", '
        '"Confrontar con...") are not commits; the edition\'s text is used as printed.',
        'Structure headings (títulos, capítulos, subcapítulos) are not tracked: the footnotes do not give their history.',
    ]
    for k, v in sorted(laws.items()):
        out.append(f'{v["label"]}: published {v["published"]}, in force {v["in_force"]} ({v["how"]}).')
    return out


def checkpoint_decisions(checks):
    out = []
    for name, res in checks.items():
        out.append(f'Checkpoint {name}: of the provisions in both, {len(res["same"])} match the rebuilt text at that '
                   f'date word for word (case, punctuation and "Nº/núm." ignored) and {len(res["diff"])} differ'
                   + (': ' + '; '.join(f'{k} ({word_diff(a, b, 2)})' for k, a, b in res['diff'])[:3000]
                      if res['diff'] else '.')
                   + (f' Only in the rebuilt text: {", ".join(res["missing_there"])}.' if res['missing_there'] else '')
                   + (f' Only in the checkpoint: {", ".join(res["missing_here"])}.' if res['missing_here'] else ''))
    return out


def write(corpus, out: Path):
    data = json.dumps(corpus, ensure_ascii=False, indent=1, sort_keys=False) + '\n'
    tmp = out.with_suffix('.json.tmp')
    tmp.write_text(data, encoding='utf-8', newline='\n')
    os.replace(tmp, out)
    return len(data)


if __name__ == '__main__':
    report = '--report' in sys.argv
    r = build(report=report)
    out = Path(sys.argv[sys.argv.index('--out') + 1]) if '--out' in sys.argv else OUT
    if r['problems']:
        print('not written: problems remain', file=sys.stderr)
        sys.exit(1)
    if '--dry' in sys.argv:
        sys.exit(0)
    n = write(r['corpus'], out)
    vs = r['corpus']['acts'][0]['versions']
    print(f'wrote {out} ({n} bytes): {len(vs)} versions, {len(r["corpus"]["laws"])} laws')
