"""Deepening the 19 spain-<unit>-law repos (gitlaw-scraper-dell, 2026-10-30): the Autonómico norms the BOE consolidates
and marks as repealed as a whole (estatus_derogacion S), with their whole consolidated history and a last commit that
removes the text on the day the repeal took effect, credited to the repealing norm. New corpus.d parts
6N-derogadas-NN of about 50; published parts are never re-parsed. Shares es_ccaa.py's one fetcher (one request at a
time, 2-3 s apart, stops on any challenge/429/second 403/repeated 5xx).

    python -X utf8 scripts/world-law/es_ccaa_derog.py survey               # counts per unit, from the cached list
    python -X utf8 scripts/world-law/es_ccaa_derog.py fetch [unit ...]     # the one fetch process
    python -X utf8 scripts/world-law/es_ccaa_derog.py parse <unit> <docs-date>
    python -X utf8 scripts/world-law/es_ccaa_derog.py verify <unit> <docs-date>   # letters + scratch build + old trees
    python -X utf8 scripts/world-law/es_ccaa_derog.py publish <unit> <docs-date>  # writes the batch's PUBLISH files

Private: lives in scripts/world-law (world-law-ops), never in a public repo.
"""
from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import es_ccaa as e  # noqa: E402

BASE = 60
MONTHS = {'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
          'septiembre': 9, 'setiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12}
# A whole-norm repeal: the "SE DEROGA" reference names no article, chapter or part of the norm.
PARTIAL = re.compile(r'(?i)\b(art[íi]culos?|arts?\.|apartados?|disposici[óo]n|disposiciones|cap[íi]tulos?|t[íi]tulos?|'
                     r'secci[óo]n|anexos?|p[áa]rrafos?|letras?|par[áa]grafos?|lo indicado|parcialmente|en la forma|'
                     r'determinados|preceptos?|inciso|n[úu]meros?|reglas?|epígrafes?|cuadro|tarifas?|la transitoria|'
                     r'la adicional|la final|las adicionales|las transitorias|el (?:pre[áa]mbulo|cap|t[íi]t))')
EFECTOS = re.compile(r'(?i)con efectos? (?:de(?:sde)?|a partir del?)\s+(?:el\s+)?(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+'
                     r'(\d{4})')


def catalogue(u: str) -> list[dict]:
    deps = set(e.UNITS[u][3])
    skip = e.robots_ids()
    out = [d for d in e.listing().values() if d['ambito']['codigo'] == '2' and d['departamento']['codigo'] in deps
           and d.get('vigencia_agotada') == 'S' and d['identificador'] not in skip]
    return sorted(out, key=lambda d: (d.get('fecha_disposicion') or '', d.get('fecha_publicacion') or '',
                                      d['identificador']))


def plan(u: str, ids: list[str] | None = None) -> list[tuple[str, list[str]]]:
    ids = ids if ids is not None else [d['identificador'] for d in catalogue(u)]
    return [(f'{BASE + i // e.PART_SIZE}-derogadas-{i // e.PART_SIZE + 1:02d}', ids[i:i + e.PART_SIZE])
            for i in range(0, len(ids), e.PART_SIZE)]


EXCEPT = re.compile(r'(?i)\b(salvo|excepto|con (la )?excepci[óo]n|a excepci[óo]n|excepci[óo]n hecha)\b')


def tail(i: str) -> str:
    """Year and number of a BOE-style id (BOE-A-2014-90371, BOCL-h-2014-90371 -> 2014-90371)."""
    m = re.search(r'(\d{4}-\d+)$', i or '')
    return m.group(1) if m else (i or '')


def repeal_info(root: ET.Element) -> dict:
    """{'ok': True, 'date', 'by', 'note', 'how'} or {'ok': False, 'why'}.

    The BOE records a whole-norm repeal three ways, all required to agree: metadata estatus_derogacion S with
    fecha_derogacion (the day the repeal took effect); a version of the nota_inicial block dated that day ("Norma
    derogada, con efectos ...") whose id_norma is the repealing norm; and a "SE DEROGA" reference to that norm."""
    meta = root.find('data/metadatos')
    if (meta.findtext('estatus_derogacion') or '').strip() != 'S':
        why = 'annulled' if (meta.findtext('estatus_anulacion') or '').strip() == 'S' else 'exhausted, not repealed'
        return {'ok': False, 'why': why}
    fd = (meta.findtext('fecha_derogacion') or '').strip()
    d = e.iso(fd)
    if not d:
        return {'ok': False, 'why': f'repealed, no fecha_derogacion ({fd!r})'}
    notes = [(v.get('id_norma') or '').strip() for b in root.iter('bloque') if b.get('tipo') == 'nota_inicial'
             for v in b.findall('version') if v.get('fecha_vigencia') == fd]
    notes = [n for n in notes if n]
    refs = {(p.findtext('id_norma') or '').strip() for p in root.iter('posterior')
            if p.find('relacion') is not None and p.find('relacion').get('codigo') == '210'}
    if len(set(notes)) != 1:
        return {'ok': False, 'why': f'repealed, but {len(set(notes))} repeal notes on {d}'}
    by = notes[0]
    if by not in refs:
        # the note may give a regional bulletin's norm a BOE-A form of its id (BOE-A-2014-90371 for BOCL-h-2014-90371):
        # take the one SE DEROGA reference with the same year and number
        same = [r for r in refs if tail(r) == tail(by)]
        if len(same) != 1:
            return {'ok': False, 'why': f'repeal note names {by}, no SE DEROGA reference to it'}
        by = same[0]
    # nothing but the note may change on or after the repeal day
    late = {b.get('tipo') for b in root.iter('bloque') for v in b.findall('version')
            if e.iso(v.get('fecha_vigencia')) and v.get('fecha_vigencia') >= fd}
    if late - {'nota_inicial'}:
        return {'ok': False, 'why': f'text versions on or after the repeal day {d}'}
    note = next(e.clean(''.join(v.itertext())) for b in root.iter('bloque') if b.get('tipo') == 'nota_inicial'
                for v in b.findall('version') if v.get('fecha_vigencia') == fd)
    # "Norma derogada, salvo la disposición adicional 1, ...": part stays in force, so the norm is not repealed as a
    # whole. Look only at the stretch of the note that gives the repeal day (earlier partial repeals may be named too).
    x = dt.date.fromisoformat(d)
    longday = f'{x.day} de {[k for k, v in MONTHS.items() if v == x.month and k != "setiembre"][0]} de {x.year}'
    segs = [g for g in re.split(r'Ref\. ', note) if longday in g] or [note]
    if any(EXCEPT.search(g) for g in segs):
        return {'ok': False, 'why': f'partial repeal: the repeal note keeps part in force ({note[:120]})'}
    return {'ok': True, 'date': d, 'by': by, 'note': note, 'how': 'fecha_derogacion + repeal note',
            'atitles': e.analisis_titles(root)}


def published_state(u: str) -> tuple[set, dict]:
    used, laws_seen = set(), {}
    for p in sorted((e.folder(u) / 'corpus.d').glob('*.json')):
        if '-derogadas-' in p.stem and not p.with_suffix('.PUBLISH').exists():
            continue
        pj = json.loads(p.read_text(encoding='utf-8'))
        for a in pj.get('acts', []):
            used.add(a['slug'])
        for k, law in pj.get('laws', {}).items():
            laws_seen.setdefault(k, law)
    return used, laws_seen


DECISION = ('Repealed norms: the unit\'s Autonómico norms the BOE consolidates and marks as repealed as a whole '
            '(estatus_derogacion S) are included with their whole consolidated history. Their last commit removes '
            'every file on the day the repeal took effect (the BOE\'s fecha_derogacion), credited to the repealing '
            'norm the BOE names on its repeal note ("Norma derogada, con efectos ...") and in its "SE DEROGA" '
            'reference; the note itself is that commit\'s reason, not a version. Norms whose force ran out without a '
            'repeal (vigencia agotada), annulled norms, and repealed norms whose BOE record is not consistent (no '
            'repeal day, no single repeal note, or text versions on or after the repeal day) are left out.')


def parse(u: str, docs_date: str) -> dict:
    used, laws_seen = published_state(u)
    rep = {'added': [], 'left_out': {}}
    keep = []
    for d in catalogue(u):
        i = d['identificador']
        raw = e.fetch_norm(i, fetch=False)
        if not raw:
            rep['left_out'][i] = 'not fetched' if not e.norm_path(i).exists() else 'no XML (empty answer)'
            continue
        info = repeal_info(ET.fromstring(raw))
        if not info['ok']:
            rep['left_out'][i] = info['why']
            continue
        keep.append((i, info))
    infos = dict(keep)
    out_parts = {}
    for name, ids in plan(u, [i for i, _ in keep]):
        p = e.folder(u) / 'corpus.d' / f'{name}.json'
        if p.with_suffix('.PUBLISH').exists():
            continue
        acts, laws = [], {}
        for i in ids:
            info = infos[i]
            before = set(used)
            r = e.parse_norm(i, used, laws_seen)
            if r is None:
                rep['left_out'][i] = 'no dated text'
                continue
            act, l, rp = r
            vs = [v for v in act['versions'] if v['from'] < info['date']]
            if not vs:
                rep['left_out'][i] = 'no version before the repeal day'
                used.clear()
                used.update(before)
                continue
            act['versions'] = vs
            units = {}
            for v in vs:
                if 'units' in v:
                    units = dict(v['units'])
                else:
                    for kk, x in v['changes'].items():
                        if x is None:
                            units.pop(kk, None)
                        else:
                            units[kk] = x
            # laws credited only on dropped versions are not needed; keep those still credited
            need = {act.get('first_law')} | set(act.get('earlier_laws', [])) | \
                {x for v in vs for ls in v.get('credits', {}).values() for x in ls}
            l = {k: v for k, v in l.items() if k in need}
            rk = info['by'].lower()
            l[rk] = laws_seen.get(rk) or e.law_entry(info['by'], None, info['atitles'])
            act['versions'].append({'from': info['date'], 'source_url': e.norm_url(i),
                                    'sha256': vs[0]['sha256'],
                                    'changes': {kk: None for kk in units}, 'credits': {kk: [rk] for kk in units}})
            act['repealed'] = {'on': info['date'], 'by': rk, 'boe_note': info['note']}
            acts.append(act)
            for kk, v in l.items():
                laws.setdefault(kk, v)
                laws_seen.setdefault(kk, v)
            rep['added'].append({'id': i, 'slug': act['slug'], 'rango': d_rango(i), 'repealed': info['date'],
                                 'by': info['by'], 'versions': len(act['versions'])})
        if not acts:
            continue
        part = {'country': e.country_block(u), 'laws': dict(sorted(laws.items())), 'acts': acts}
        if name.endswith('-01'):
            part['decisions'] = [DECISION]
        e.write_part(p, part)
        out_parts[name] = len(acts)
    rep['parts'] = out_parts
    (e.folder(u) / '.tmp').mkdir(exist_ok=True)
    (e.folder(u) / '.tmp' / 'parse-derogadas.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1),
                                                               encoding='utf-8')
    return rep


def d_rango(i: str) -> str:
    return ((e.listing().get(i) or {}).get('rango') or {}).get('texto', '?')


# ---------------------------------------------------------------- checks

def source_repeal(raw: bytes) -> dict:
    """Independent of repeal_info (lxml, its own walk): the metadata flag and day, the ids on the nota_inicial versions
    of that day, the SE DEROGA reference ids, and the block types with a version on or after that day."""
    from lxml import etree
    root = etree.fromstring(raw)
    fd = (root.findtext('.//metadatos/fecha_derogacion') or '').strip()
    out = {'flag': (root.findtext('.//metadatos/estatus_derogacion') or '').strip(),
           'day': f'{fd[:4]}-{fd[4:6]}-{fd[6:8]}' if len(fd) == 8 else '', 'notes': set(), 'refs': set(),
           'late': set()}
    for b in root.iter('bloque'):
        for v in b.findall('version'):
            f = v.get('fecha_vigencia') or ''
            if f == fd and b.get('tipo') == 'nota_inicial':
                out['notes'].add((v.get('id_norma') or '').strip().lower())
            if re.fullmatch(r'\d{8}', f) and not f.startswith('9999') and f >= fd:
                out['late'].add(b.get('tipo'))
    for p in root.iter('posterior'):
        r = p.find('relacion')
        if r is not None and r.get('codigo') == '210':
            out['refs'].add((p.findtext('id_norma') or '').strip().lower())
    return out


def letters_check(u: str, part_name: str) -> list[str]:
    """es_ccaa's letters check for every version before the repeal; the repeal version must remove every file on the
    XML's fecha_derogacion, after every earlier version, credited (every file) to the norm named on that day's repeal
    note and in a SE DEROGA reference, with nothing but the note changing in the XML on or after that day."""
    p = e.folder(u) / 'corpus.d' / f'{part_name}.json'
    part = json.loads(p.read_text(encoding='utf-8'))
    probs = []
    for act in part['acts']:
        raw = gzip.decompress(e.norm_path(act['boe_id']).read_bytes())
        if hashlib.sha256(raw).hexdigest() != act['versions'][0]['sha256']:
            probs.append(f'{act["slug"]}: sha256 differs from the cached source')
            continue
        states = e.source_states(raw)
        units = {}
        vs = act['versions']
        for n, v in enumerate(vs):
            if 'units' in v:
                units = dict(v['units'])
            else:
                for k, x in v['changes'].items():
                    if x is None:
                        units.pop(k, None)
                    else:
                        units[k] = x
            if n == len(vs) - 1:
                s = source_repeal(raw)
                by = act['repealed']['by']
                if units:
                    probs.append(f'{act["slug"]} {v["from"]}: repeal version leaves {len(units)} files')
                if s['flag'] != 'S' or s['day'] != v['from'] or act['repealed']['on'] != v['from']:
                    probs.append(f'{act["slug"]}: repeal day {v["from"]} vs XML {s["flag"]} {s["day"]}')
                if {tail(x) for x in s['notes']} != {tail(by)} or by not in s['refs']:
                    probs.append(f'{act["slug"]}: repealer {by} vs XML note {s["notes"]} refs {sorted(s["refs"])[:4]}')
                if s['late'] - {'nota_inicial'}:
                    probs.append(f'{act["slug"]}: XML has text versions on or after the repeal day')
                if n == 0 or vs[n - 1]['from'] >= v['from']:
                    probs.append(f'{act["slug"]}: repeal version not after the last text version')
                if set(v['credits']) != set(v['changes']) or any(c != [by] for c in v['credits'].values()):
                    probs.append(f'{act["slug"]}: repeal credits incomplete')
                continue
            src = states.get(v['from'])
            if src is None:
                probs.append(f'{act["slug"]} {v["from"]}: no such day in the source')
                continue
            mine = e.letters(''.join(x['text'] for x in units.values()))
            if sorted(src) != sorted(mine):
                probs.append(f'{act["slug"]} {v["from"]}: letters differ')
                continue
            for k, x in units.items():
                if e.letters(x['text']) not in src:
                    probs.append(f'{act["slug"]} {v["from"]} {k}: text not found in order in the source')
                    break
    return probs


def git(repo: Path, *a: str) -> str:
    return subprocess.run(['git', *a], cwd=repo, capture_output=True, text=True, encoding='utf-8').stdout


def act_tree(repo: Path, ref: str, slug: str) -> dict[str, str]:
    out = {}
    for line in git(repo, 'ls-tree', '-r', ref, '--', f'{slug}/').splitlines():
        meta, path = line.split('\t', 1)
        if not path.endswith('/README.md'):
            out[path] = meta.split()[2]
    return out


def verify(u: str, docs_date: str) -> tuple[bool, list[str]]:
    """Every unpublished derogadas part: letters check; then ONE scratch build of the published parts plus all of them
    (check.py clean); then every previously published act's final tree on main and futuro equals the live repo's."""
    src = e.folder(u)
    new = [p.stem for p in sorted((src / 'corpus.d').glob('*-derogadas-*.json')) if not p.with_suffix('.PUBLISH').exists()]
    if not new:
        return False, ['no unpublished derogadas part']
    lines = []
    for n in new:
        pr = letters_check(u, n)
        if pr:
            return False, [f'{n}: letters check {len(pr)} problems: {pr[:3]}']
    tmp = e.DOCS / f'{e.repo_name(u)}-verify'
    build = e.DOCS / f'{e.repo_name(u)}-verifybuild'
    for d in (tmp, build):
        e._rm(d)
    (tmp / 'corpus.d').mkdir(parents=True)
    names = [p.stem for p in sorted((src / 'corpus.d').glob('*.json')) if p.with_suffix('.PUBLISH').exists()] + new
    for n in names:
        shutil.copy2(src / 'corpus.d' / f'{n}.json', tmp / 'corpus.d' / f'{n}.json')
    patch_estatuto_decision(tmp)
    e.write_docs(u, docs_date, extra=new, out=tmp / 'repo')
    build.mkdir()
    subprocess.run(['git', 'init', '-q'], cwd=build, check=True)
    env = dict(os.environ, GITLAW_NO_CHECKOUT='1')
    b = e._low([sys.executable, '-X', 'utf8', str(e.ROOT / 'gitlaw_common' / 'build.py'), str(tmp), '--repo',
                str(build), '--docs-date', docs_date], env=env)
    if b.returncode:
        return False, ['build failed: ' + (b.stderr or b.stdout)[-600:]]
    c = e._low([sys.executable, '-X', 'utf8', str(e.ROOT / 'gitlaw_common' / 'check.py'), str(build), '--corpus',
                str(tmp / 'corpus.json')])
    try:
        res = json.loads(c.stdout[c.stdout.index('{'):])
    except Exception:
        return False, ['check.py output unreadable: ' + (c.stderr or c.stdout)[-400:]]
    if res.get('mismatches') or res.get('trailer_errors') or res.get('merges') or res.get('backwards') \
            or res.get('future_dated') or res.get('missing_in_force'):
        return False, ['check.py: ' + json.dumps({k: v for k, v in res.items() if k != 'details'})[:300]
                       + json.dumps(res.get('details', [])[:3], ensure_ascii=False)[:400]]
    # previously published acts: final trees unchanged against the live repo (origin/main and origin/futuro)
    # a private bare mirror of the live repo (never the autopush's clone, which it rebuilds while we read)
    clone = e.HERE / '.cache' / 'es-derogcheck' / f'{e.repo_name(u)}.git'
    if not clone.exists():
        clone.mkdir(parents=True)
        git(clone, 'init', '-q', '--bare')
    remote = f'https://github.com/lexifina/{e.repo_name(u)}.git'
    live = {l.split('	')[1]: l.split('	')[0] for l in git(clone, 'ls-remote', remote).splitlines() if '	' in l}
    if 'refs/heads/main' not in live:
        return False, ['ls-remote: no main on the live repo']
    def fetched() -> bool:
        return all(git(clone, 'rev-parse', '-q', '--verify', f'refs/derogcheck/{r}').strip() == live[f'refs/heads/{r}']
                   for r in ('main', 'futuro') if f'refs/heads/{r}' in live)
    for attempt in range(4):  # the autopush works in the same clone; a ref lock can make one fetch fail
        if fetched():
            break
        git(clone, 'fetch', '-q', remote, *[f'+{r}:refs/derogcheck/{r.split("/")[-1]}' for r in
                                            ('refs/heads/main', 'refs/heads/futuro') if r in live])
        time.sleep(10 * attempt)
    if not fetched():
        return False, ['could not fetch the live main/futuro']
    old_slugs = []
    for p in sorted((src / 'corpus.d').glob('*.json')):
        if p.with_suffix('.PUBLISH').exists():
            old_slugs += [a['slug'] for a in json.loads(p.read_text(encoding='utf-8'))['acts']]
    has_fut_live = 'refs/heads/futuro' in live
    has_fut_new = bool(git(build, 'rev-parse', '-q', '--verify', 'refs/heads/futuro').strip())
    diffs = []
    for live_ref, new_ref, on in (('refs/derogcheck/main', 'main', True), ('refs/derogcheck/futuro', 'futuro', has_fut_live)):
        if not on:
            continue
        nref = new_ref if (new_ref == 'main' or has_fut_new) else 'main'
        for s in old_slugs:
            if act_tree(clone, live_ref, s) != act_tree(build, nref, s):
                diffs.append(f'{live_ref} {s}')
    if diffs:
        return False, [f'final trees of {len(diffs)} published acts differ: {diffs[:5]}']
    for n in new:
        pj = json.loads((src / 'corpus.d' / f'{n}.json').read_text(encoding='utf-8'))
        acts = pj['acts']
        nv = sum(len(a['versions']) for a in acts)
        days = sorted(v['from'] for a in acts for v in a['versions'])
        lines.append(
            f'{len(acts)} repealed norm(s), {nv} versions {days[0]}..{days[-1]} from BOE legislación consolidada, each '
            f'ending in a commit that removes the text on the repeal day, credited to the repealing norm: letters and '
            f'digits of every earlier version equal the BOE XML state of that day (independent lxml reader), every unit '
            f'found in it, and each repeal confirmed by the XML (estatus_derogacion S, SE DEROGA reference); scratch '
            f'build of verified parts + this batch: check.py {res["versions"]} versions, 0 mismatches, 0 trailer '
            f'errors, 0 merges; the final trees of all {len(old_slugs)} previously published norms on main'
            f'{" and futuro" if has_fut_live else ""} equal the live repo\'s ({docs_date}).')
    e._rm(tmp)
    e._rm(build)
    return True, list(zip(new, lines))


OLD_DECISION_TAIL = ' Repealed norms are left out.'


def patch_estatuto_decision(base: Path) -> bytes | None:
    """The published 10-estatuto part's decision said repealed norms are left out; drop that one sentence (decisions
    only: its acts are compared before and after). Returns the old bytes, or None if there was nothing to change."""
    p = base / 'corpus.d' / '10-estatuto.json'
    old = p.read_bytes()
    pj = json.loads(old.decode('utf-8'))
    ds = pj.get('decisions', [])
    if not any(OLD_DECISION_TAIL in d for d in ds):
        return None
    acts_before = json.dumps(pj['acts'], sort_keys=True)
    pj['decisions'] = [d.replace(OLD_DECISION_TAIL, '') for d in ds]
    assert json.dumps(pj['acts'], sort_keys=True) == acts_before
    tmp = p.with_suffix('.dtmp')
    tmp.write_text(json.dumps(pj, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    os.replace(tmp, p)
    return old


def publish(u: str, docs_date: str) -> str:
    ok, res = verify(u, docs_date)
    if not ok:
        return 'NOT VERIFIED ' + res[0]
    patch_estatuto_decision(e.folder(u))
    e.write_docs(u, docs_date, extra=[n for n, _ in res])
    for n, line in res:
        pub = e.folder(u) / 'corpus.d' / f'{n}.PUBLISH'
        tmp = pub.with_suffix('.ptmp')
        tmp.write_text(line + '\n', encoding='utf-8', newline='\n')
        os.replace(tmp, pub)
    return 'PUBLISH ' + '; '.join(f'{n}: {line[:60]}' for n, line in res)


# ---------------------------------------------------------------- fetch

def fetch(units: list[str]):
    e.norm_list(fetch=False)
    n0 = 0
    try:
        for u in units:
            ids = [d['identificador'] for d in catalogue(u)]
            for i in ids:
                if e.norm_path(i).exists():
                    continue
                while not e.cpu_ok():
                    time.sleep(60)
                e.fetch_norm(i)
                n0 += 1
            e.say(f'{u}: {len(ids)} repealed/exhausted norms fetched ({e.net().count if e.NET else 0} requests)')
    except e.Stop as x:
        e.say(f'STOPPED: {x}')
        sys.exit(2)
    e.say(f'fetch done: {n0} new norms')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    cmd = sys.argv[1]
    if cmd == 'survey':
        for u in e.UNITS:
            c = catalogue(u)
            print(u, len(c), dict(Counter(d['rango']['texto'] for d in c)))
    elif cmd == 'fetch':
        fetch(sys.argv[2:] or list(e.UNITS))
    elif cmd == 'parse':
        r = parse(sys.argv[2], sys.argv[3])
        e.progress(sys.argv[2], f'derogadas parse: {len(r["added"])} repealed norms in {r["parts"]}; left out '
                                f'{len(r["left_out"])}: ' + json.dumps(dict(Counter(v.split(":")[0].split(" (")[0]
                                                                         for v in r["left_out"].values())),
                                                                 ensure_ascii=False))
        print(json.dumps({'parts': r['parts'], 'added': len(r['added']),
                          'left_out': dict(Counter(v.split(' (')[0].split(':')[0] for v in r['left_out'].values()))},
                         ensure_ascii=False))
    elif cmd == 'letters':
        pr = letters_check(sys.argv[2], sys.argv[3])
        print('\n'.join(pr[:40]) or 'letters check: clean')
    elif cmd == 'verify':
        ok, res = verify(sys.argv[2], sys.argv[3])
        print('OK' if ok else 'NOT VERIFIED', res)
    elif cmd == 'publish':
        out = publish(sys.argv[2], sys.argv[3])
        e.progress(sys.argv[2], f'derogadas: {out[:700]}')
        print(out)
