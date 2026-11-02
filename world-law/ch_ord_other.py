"""Ordinances for the Swiss cantons without LexWork (gitlaw-scraper-dell fork, ordinances wave 2026-10-30): Vaud
(BLV règlements, dated history), Geneva (SILGENEVE règlements, current text), Neuchatel (RSN règlements, current
text), Ticino (LexFind regolamenti, dated history) and Zurich (ZH-Lex Verordnungen/Reglemente, dated history).
Same sources, fetch helpers, parsers and rules as each canton's law tooling. Private: scripts/world-law only.

    python -X utf8 scripts/world-law/ch_ord_other.py build <slug> <docs-date>     # fetch (cached) + write parts
    python -X utf8 scripts/world-law/ch_ord_other.py verify <slug> <docs-date> [part ...]   # batch: PUBLISH files

Parts are named 40-<word>-N (after the law parts); acts whose own text check fails are left out and listed in
<folder>/ord-left-out.json.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ch_cantons as C  # noqa: E402  (read-only use)
import ch_romandy as R  # noqa: E402

SIZE = 50
WORD = {'vaud': 'reglements', 'geneva': 'reglements', 'neuchatel': 'reglements', 'ticino': 'regolamenti',
        'zurich': 'verordnungen'}


def folder(slug):
    return C.ROOT / f'switzerland-{slug}-law'


def load_ok():
    p = Path(os.environ.get('LOCALAPPDATA', '')) / 'gitlaw-cpu.log'
    while True:
        try:
            last = p.read_text(encoding='utf-8').strip().splitlines()[-1]
            c, r = int(last.split('cpu5=')[1].split()[0]), int(last.split('ram=')[1].split()[0])
        except Exception:
            return
        if c <= 92 and r <= 85:
            return
        time.sleep(60)


def left_out(slug, name, items):
    p = folder(slug) / 'ord-left-out.json'
    cur = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
    cur[name] = items
    p.write_text(json.dumps(cur, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')


def published_sns(slug):
    out = set()
    for p in (folder(slug) / 'corpus.d').glob('*.json'):
        if WORD[slug] not in p.stem:
            out.update(a['systematic_number'] for a in json.loads(p.read_text(encoding='utf-8'))['acts'])
    return out


def write(slug, i, acts, laws):
    name = f'{40 + i:02d}-{WORD[slug]}-{i + 1}'
    p = folder(slug) / 'corpus.d' / f'{name}.json'
    if slug == 'zurich':
        import ch_zurich as Z
        Z.write_part(p, {'laws': dict(sorted(laws.items())), 'acts': acts})
    else:
        R.write_part(p, {'laws': dict(sorted(laws.items())), 'acts': acts})
    print(name, len(acts), 'acts', sum(len(a['versions']) for a in acts), 'versions', flush=True)


RESUME_KEY = {'zurich': lambda it: it[1]['referenceNumber']}


def chunked(slug, items, make):
    """items: [(id, ...)] in collection order; make(item) -> (act, laws) | None. Parts of SIZE kept acts."""
    have = published_sns(slug)
    acts, laws, bad, i = [], {}, [], 0
    # resume: continue after the last act of the last ordinance part already written (those parts never change)
    done_parts = sorted((folder(slug) / 'corpus.d').glob(f'*-{WORD[slug]}-*.json'),
                        key=lambda p: int(p.stem.split('-')[-1]))
    if done_parts and RESUME_KEY.get(slug):
        last = json.loads(done_parts[-1].read_text(encoding='utf-8'))['acts'][-1]['systematic_number']
        keys = [RESUME_KEY[slug](it) for it in items]
        if last not in keys:
            raise SystemExit(f'resume: {last} not in the list')
        items = items[keys.index(last) + 1:]
        i = len(done_parts)
        print(f'resume after {last}: {len(items)} items left, next part {40 + i}', flush=True)
    for it in items:
        load_ok()
        p = folder(slug) / 'corpus.d' / f'{40 + i:02d}-{WORD[slug]}-{i + 1}.json'
        if p.with_suffix('.PUBLISH').exists():
            raise SystemExit(f'{p.name} already published: rebuild would change it')
        try:
            r = make(it)
        except SystemExit:
            raise
        except Exception as e:
            if re.search(r'HTTP (403|429|5\d\d)|stopping|challenge', str(e)):
                raise SystemExit(f'{slug}: {e}')   # the host refused: stop, never skip past it
            print('skip', it[0], str(e)[:120], flush=True)
            bad.append(f'{it[0]}: {str(e)[:80]}')
            continue
        if not r:
            continue
        a, l = r
        if a['systematic_number'] in have or not a['versions']:
            continue
        probs = (__import__('ch_zurich').letters_check_acts([a]) if slug == 'zurich' else R.acts_problems(slug, [a]))
        if probs:
            print('left out (text check)', it[0], probs[0][:120], flush=True)
            bad.append(f'{a["systematic_number"]}: text check')
            continue
        while a['slug'] in {x['slug'] for x in acts}:
            a['slug'] += '-2'
        acts.append(a)
        for k, v in l.items():
            laws.setdefault(k, v)
        if len(acts) == SIZE:
            write(slug, i, acts, laws)
            left_out(slug, f'{40 + i:02d}-{WORD[slug]}-{i + 1}', bad)
            acts, laws, bad, i = [], {}, [], i + 1
    if acts:
        write(slug, i, acts, laws)
        left_out(slug, f'{40 + i:02d}-{WORD[slug]}-{i + 1}', bad)
    (folder(slug) / '.cache' / 'ord-build-done.txt').write_text('done\n', encoding='utf-8')


# ---------------------------------------------------------------- Vaud

def vaud_list():
    import ch_vaud as V
    top = json.loads(R.get('vaud', f'{V.VD_API}recueil-systematique'))
    out = []

    def walk(n):
        for x in n:
            if x.get('typeElement') == 'ACTE' and re.match(r'^RÈGLEMENT\b', x.get('libelle', '')) and x.get('atelierId'):
                out.append((x['code'], x['atelierId']))
            walk(x.get('children') or [])
    for vol in top:
        walk(json.loads(R.get('vaud', f'{V.VD_API}recueil-systematique?code={vol["code"]}')))
    seen, res = set(), []
    for c, a in out:
        if a not in seen:
            seen.add(a)
            res.append((c, a))
    return res


def vaud_build(docs_date):
    import ch_vaud as V
    # first the LOIs the earlier run never reached (151-204), same process, same host pace
    r = subprocess.run([sys.executable, '-X', 'utf8', str(Path(V.__file__)), 'laws', docs_date])
    if r.returncode:
        raise SystemExit('vaud laws run failed')
    chunked('vaud', vaud_list(), lambda it: V.vd_act(it[0], it[1]))


# ---------------------------------------------------------------- Geneva

def geneva_list():
    b = R.get('geneva', 'https://silgeneve.ch/sitemap.xml')
    urls = [u.decode() for u in re.findall(rb'<loc>([^<]+)</loc>', b)]
    return [(u,) for u in urls if re.search(r'/rsg_[a-z]\d+_\d+p\d+\.htm$', u)]


def geneva_act(url, docs_date):
    """ch_geneva_laws.ge_act for a règlement (same parse, dating and credit; the title must be a Règlement)."""
    raw = R.get('geneva', url)
    t = raw.decode('cp1252', 'replace')
    m = re.search(r'<title>rsGE ([^:]+):\s*(.*?)</title>', t, re.S)
    if not m:
        return None
    code, title = C.clean(m.group(1)), C.clean(m.group(2))
    if not re.match(r'^R[èe]glement\b', title):
        return None
    units, rows, _ = R.parse_geneva_doc(raw)
    days = [r['inforce'] for r in rows if r['inforce'] and r['inforce'] <= docs_date]
    if not days or len(units) < 2:
        return None
    frm = max(days)
    short = None
    ab = re.search(r'\(([A-Z][A-Za-z0-9-]{1,15})\)\s*$', title)
    if ab:
        short = ab.group(1)
    act = R.current_only_act('geneva', units, url, hashlib.sha256(raw).hexdigest(), frm, title, short, code,
                             f'Text in force since {frm} (the latest entry into force in its history table), as '
                             'published on SILGENEVE; no earlier wording is held.')
    first = next((r for r in rows if r['adopted'] and r['inforce']), None)
    laws = {}
    if first:
        k = C.ascii_key(f'ge-{code}-{first["adopted"]}')
        laws[k] = {'label': f'{short or code} du {C._dmy(first["adopted"])}',
                   'title': f'{title}, du {C._dmy(first["adopted"])}', 'kind': 'law', 'enacted': first['adopted'],
                   'published': None, 'url': url, 'temporary_until': None, 'restores': None, 'note': None}
        act['earlier_laws'] = [k]
    return act, laws


def geneva_build(docs_date):
    chunked('geneva', geneva_list(), lambda it: geneva_act(it[0], docs_date))


# ---------------------------------------------------------------- Neuchatel

def neuchatel_list():
    lst = json.loads((folder('neuchatel') / '.cache' / 'lexfind-act-list.json').read_text(encoding='utf-8'))
    return [(sn,) for sn in sorted({sn for sn, title, cat in lst if cat in (5, 7) and title.startswith('Règlement')},
                                   key=C.natkey)]


def neuchatel_build(docs_date):
    import ch_neuchatel_laws as N

    def make(it):
        R.get('neuchatel', R.NE_BASE + it[0] + '.htm')   # a refusal propagates here (ne_act swallows errors)
        return N.ne_act(it[0], docs_date)
    chunked('neuchatel', neuchatel_list(), make)


# ---------------------------------------------------------------- Ticino

def ticino_list():
    import ch_ticino as T
    d = json.loads(R.get('ticino', f'{T.LF}/api/fe/it/entities/21/systematics'))
    ids = [k for k, v in d.items() if k and not v.get('children')]
    tols = []
    for i in range(0, len(ids), 80):
        q = '&'.join('tols_for_systematics%5B%5D=' + x for x in ids[i:i + 80])
        d2 = json.loads(R.get('ticino', f'{T.LF}/api/fe/it/entities/21/systematics?active_only=true&' + q))
        tols += [(t['systematic_number'], t['id']) for v in d2.values() for t in v.get('tols', [])
                 if t.get('is_active') and re.match(r'^Regolamento\b', t['title'])]
    seen, out = set(), []
    for sn, tid in sorted(tols, key=lambda x: C.natkey(x[0])):
        if tid not in seen:
            seen.add(tid)
            out.append((sn, tid))
    return out


def ticino_make(it, docs_date):
    import ch_ticino as T
    a, l = T.ti_act(it[1], docs_date)
    if not a['versions'] or len(a['versions'][0]['units']) < 2:
        return None
    return a, l


def ticino_build(docs_date):
    chunked('ticino', ticino_list(), lambda it: ticino_make(it, docs_date))


# ---------------------------------------------------------------- Zurich

ZW = 'abcdefghijklmnopqrstuvwxyzäöü'


def zurich_list():
    """ZH-Lex caps a search at 150 results and ANDs its terms, so each search is split by a further '<letter>*'
    term until it fits."""
    import ch_zurich as Z
    seen = {}

    capped = []

    def pages(q):
        page = 1
        while True:
            b = Z.get(Z.LIST + '?' + urllib.parse.urlencode({'enactmentTitle': q, 'page': page}), '.json')
            if not b:
                return {}
            d = json.loads(b)
            for x in d.get('data', []):
                seen.setdefault(x['link'], x)
            if page == 1:
                first = d
            if page >= d.get('numberOfResultPages', 1):
                return first
            page += 1

    def search(head, pre, tail):
        """head + ' ' + pre* (pre='' for no second term) or pre*tail; a capped search is split by lengthening pre."""
        q = f'{pre}*{tail}' if tail else (f'{head} {pre}*' if pre else head)
        d = pages(q)
        if d.get('moreSearchResultsThanAllowed'):
            if len(pre) >= 4:
                capped.append(q)
                return
            for c in ZW:
                search(head, pre + c, tail)
    for w in ('verordnung', 'reglement'):
        d = pages(w)
        if d.get('moreSearchResultsThanAllowed'):
            for c in ZW:
                search(w, c, None)     # 'verordnung <c>*'
        for c in ZW:
            search(w, c, w)            # compounds: '<c>*verordnung'
    if capped:
        print('still capped (results taken as far as served):', capped, flush=True)
    out = []
    for a in seen.values():
        t = a['enactmentTitle']
        if a.get('withdrawalDate') or a['referenceNumber'] == '101':
            continue
        if not any(re.match(r'^(\w*(verordnung|reglement)(e|en)?)$', w, re.I) for w in re.findall(r'\w+', t)[:2]):
            continue
        out.append(a)

    def nat(s):
        return [int(x) if x.isdigit() else x for x in re.findall(r'\d+|\D+', s)]
    out.sort(key=lambda x: nat(x['referenceNumber']))
    return [(a['link'], a) for a in out]


def zurich_build(docs_date):
    import ch_zurich as Z
    lst = zurich_list()
    print(len(lst), 'ordinances listed', flush=True)
    titles = {l: a['enactmentTitle'] for l, a in lst}
    orig_all = Z.all_law_entries
    Z.all_law_entries = lambda: orig_all() + [a for _, a in lst]   # full title lookup inside parse_act

    def make(it):
        if Z.fetch_act(it[0]) is None:
            return None
        r = Z.parse_act(it[0])
        if r is None or r == 'skip':
            return None
        return r
    chunked('zurich', lst, make)


def _z_letters_check_acts(acts):
    import ch_zurich as Z
    from collections import Counter
    probs = []
    for act in acts:
        units = {}
        for v in act['versions']:
            if 'units' in v:
                units = dict(v['units'])
            else:
                for k, u in v['changes'].items():
                    if u is None:
                        units.pop(k, None)
                    else:
                        units[k] = u
            a = Counter(Z.P.source_letters(Z.cpath(v['source_url'], '.pdf')))
            b = Counter(Z.P.letters(''.join(u['text'] for u in units.values())))
            if a != b:
                probs.append(f'{act["slug"]} {v["from"]}: source-only {dict((a - b).most_common(6))} '
                             f'corpus-only {dict((b - a).most_common(6))}')
    return probs


# ---------------------------------------------------------------- batch verification

def verify(slug, docs_date, names):
    """Letters check of each part (the canton's own reader of the source), then ONE scratch build of every published
    part plus the batch, and check.py on it. PUBLISH for every part of the batch when all is clean."""
    src = folder(slug)
    if slug == 'zurich':
        import ch_zurich as Z
        lc, wd = Z.letters_check, (lambda extra, out: Z.write_docs(extra=extra, out=out))
        host = 'ZH-Lex Nachtrag PDFs (www.zh.ch, www.notes.zh.ch)'
    else:
        lc, wd = (lambda n: R.letters_check(slug, n)), (lambda extra, out: R.write_docs(slug, docs_date, extra=extra, out=out))
        host = R.ROMANDY[slug][3]
    out, good = {}, []
    for n in names:
        load_ok()
        probs = lc(n)
        if probs:
            out[n] = (False, f'letters: {len(probs)}: {probs[0]}')
        else:
            good.append(n)
    if not good:
        return out
    tmp, build = C.DOCS / f'switzerland-{slug}-law-verify', C.DOCS / f'switzerland-{slug}-law-verifybuild'
    for d in (tmp, build):
        C._rm(d)
    (tmp / 'corpus.d').mkdir(parents=True)
    keep = sorted({p.stem for p in (src / 'corpus.d').glob('*.json') if p.with_suffix('.PUBLISH').exists()} | set(good))
    for n in keep:
        shutil.copy2(src / 'corpus.d' / f'{n}.json', tmp / 'corpus.d' / f'{n}.json')
    wd(good, tmp / 'repo')
    build.mkdir()
    subprocess.run(['git', 'init', '-q'], cwd=build, check=True)
    load_ok()
    env = dict(os.environ, GITLAW_NO_CHECKOUT='1')
    b = C._low([sys.executable, '-X', 'utf8', str(C.ROOT / 'gitlaw_common' / 'build.py'), str(tmp), '--repo',
                str(build), '--docs-date', docs_date], env=env)
    res = None
    if not b.returncode:
        c = C._low([sys.executable, '-X', 'utf8', str(C.ROOT / 'gitlaw_common' / 'check.py'), str(build), '--corpus',
                    str(tmp / 'corpus.json')])
        try:
            res = json.loads(c.stdout[c.stdout.index('{'):])
        except Exception:
            res = None
    clean = res is not None and not any(res.get(k) for k in ('mismatches', 'trailer_errors', 'merges', 'backwards',
                                                              'future_dated', 'missing_in_force'))
    for n in good:
        if not clean:
            out[n] = (False, ('build failed: ' + (b.stderr or b.stdout)[-400:]) if b.returncode else
                      'check.py: ' + json.dumps({k: v for k, v in (res or {}).items() if k != 'details'})[:300]
                      + json.dumps((res or {}).get('details', [])[:3], ensure_ascii=False)[:300])
            continue
        p = json.loads((src / 'corpus.d' / f'{n}.json').read_text(encoding='utf-8'))
        nv = sum(len(a['versions']) for a in p['acts'])
        days = sorted(v['from'] for a in p['acts'] for v in a['versions'])
        out[n] = (True, f'{len(p["acts"])} act(s), {nv} versions {days[0]}..{days[-1]} ({host}): letters-and-digits '
                        f'of every version equal the source document; scratch build of all published parts + this '
                        f'batch ({", ".join(good)}): check.py {res["versions"]} versions, 0 mismatches, 0 trailer '
                        f'errors, 0 merges ({docs_date}).')
    if clean:
        C._rm(tmp)
        C._rm(build)
        wd(good, None)
        for n in good:
            pub = src / 'corpus.d' / f'{n}.PUBLISH'
            pub.with_suffix('.ptmp').write_text(out[n][1] + '\n', encoding='utf-8', newline='\n')
        for n in good:
            pub = src / 'corpus.d' / f'{n}.PUBLISH'
            os.replace(pub.with_suffix('.ptmp'), pub)
    return out


if __name__ == '__main__':
    import ch_zurich as _Z
    _Z.letters_check_acts = _z_letters_check_acts
    cmd, slug, day = sys.argv[1], sys.argv[2], sys.argv[3]
    if cmd == 'build':
        {'vaud': vaud_build, 'geneva': geneva_build, 'neuchatel': neuchatel_build, 'ticino': ticino_build,
         'zurich': zurich_build}[slug](day)
    elif cmd == 'list':
        lst = {'vaud': vaud_list, 'geneva': geneva_list, 'neuchatel': neuchatel_list, 'ticino': ticino_list,
               'zurich': zurich_list}[slug]()
        print(len(lst), lst[:3])
    elif cmd == 'verify':
        names = sys.argv[4:] or [p.stem for p in sorted((folder(slug) / 'corpus.d').glob('*.json'))
                                 if not p.with_suffix('.PUBLISH').exists()]
        for n, (ok, line) in sorted(verify(slug, day, names).items()):
            print(n, 'PUBLISH' if ok else 'NOT VERIFIED', line[:400], flush=True)
