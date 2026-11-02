"""Batch publishing wrapper around ar_provinces.py (gitlaw-scraper-dell, Argentine provinces deepening, 2026-10-30).

The engine writes <part>.PUBLISH as soon as each part verifies. The deepening pass publishes in batches instead (the
autopush then rebuilds once per batch): this wrapper runs the engine's own drive(), but each part is only verified
(letters check + scratch build + check.py, the engine's verify_part) when it is written; every BATCH verified parts (and
at the end) the pending ones are published in order through the engine's publish(), which verifies each again with
the parts published before it. The engine file is unchanged.

    python -X utf8 scripts/world-law/ar_batch.py run <slug> --laws=N [--batch=5]
    python -X utf8 scripts/world-law/ar_batch.py verify <slug> <part> <docs-date>     (used by run)
    python -X utf8 scripts/world-law/ar_batch.py flush <slug> <docs-date>             (publish pending verified parts)

Private: lives in scripts/world-law (world-law-ops), never in a public repo.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ar_provinces as E  # noqa: E402

BATCH = 5

# Daily cap (coordinator rule, 2026-11-01): on a host without a stated Crawl-delay, about 5,000 requests per UTC day.
# Counted from the shared request log (so restarts and other runs on the same host count too); when a host reaches
# the cap, the next request to it waits until 00:00 UTC.
DAILY_CAP = 5000
_day_counts: dict[tuple[str, str], int] = {}


def _count_today(host: str, day: str) -> int:
    if (host, day) not in _day_counts:
        n = 0
        try:
            with open(HERE / 'logs' / 'ar-provinces-requests.jsonl', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('{"at": "' + day) and f'//{host}/' in line:
                        n += 1
        except FileNotFoundError:
            pass
        _day_counts[(host, day)] = n
    return _day_counts[(host, day)]


_orig_net_get = E.Net.get


def _capped_get(self, url: str):
    host = url.split('/')[2]
    import datetime as _d
    import time as _t
    while True:
        now = _d.datetime.now(_d.timezone.utc)
        day = now.strftime('%Y-%m-%d')
        if _count_today(host, day) < DAILY_CAP:
            break
        nxt = (now + _d.timedelta(days=1)).replace(hour=0, minute=0, second=5, microsecond=0)
        E.say(f'{host}: {DAILY_CAP} requests today (UTC); paused until {nxt:%Y-%m-%d %H:%M} UTC')
        _t.sleep(max(60, (nxt - now).total_seconds()))
    r = _orig_net_get(self, url)
    _day_counts[(host, day)] = _count_today(host, day) + 1
    return r


E.Net.get = _capped_get


def _sha(slug: str, name: str) -> str:
    import hashlib
    return hashlib.sha256((E.folder(slug) / 'corpus.d' / f'{name}.json').read_bytes()).hexdigest()


def pending(slug: str) -> list[str]:
    d = E.folder(slug) / 'corpus.d'
    return [p.stem.removesuffix('.VERIFIED') for p in sorted(d.glob('*.VERIFIED'))
            if not (d / (p.stem.removesuffix('.VERIFIED') + '.PUBLISH')).exists()]


def replan(slug: str):
    """A plan that extends a province without touching its published parts: published parts keep their names (and are
    skipped by drive()); laws already in a published part are dropped from the list (matched by record URL), and the
    rest, in catalogue order, are cut into new parts of about 50 numbered after the last published part. Parts already
    written but not yet published are recomputed the same way (the catalogue is read from the cache)."""
    orig = E.plan

    def plan(cat: dict) -> list[tuple[str, list[dict]]]:
        d = E.folder(slug) / 'corpus.d'
        pub = sorted(p.stem for p in d.glob('*.PUBLISH'))
        if not pub:
            return orig(cat)
        urls = set()
        for name in pub:
            for a in json.loads((d / f'{name}.json').read_text(encoding='utf-8'))['acts']:
                urls.add(a['url'])
                for v in a['versions']:
                    urls.add(v['source_url'])
        out = [(n, m) for n, m in orig({k: v for k, v in cat.items() if k != 'ley'}) if n not in pub]
        law_parts = [n for n in pub if '-leyes-' in n and len(n.split('-leyes-')[1]) == 2]
        last = max((int(n.split('-leyes-')[1]) for n in law_parts), default=0)

        def done(item):
            pg = item.get('page') or ''
            return any(u == pg or u.endswith(pg) for u in urls) if pg else False
        rest, seen = [], set()
        for it in cat.get('ley', []):   # a paged source can list one law twice (ties in its sort): keep it once
            if not done(it) and it.get('page') not in seen:
                seen.add(it.get('page'))
                rest.append(it)
        skip_f = E.folder(slug) / 'skip-pages.txt'   # records with a known source defect (e.g. a year-0026 date)
        skip = set(skip_f.read_text(encoding='utf-8').split()) if skip_f.exists() else set()
        rest = [it for it in rest if it.get('page') not in skip]
        prefix = os.environ.get('AR_PART_PREFIX')
        if prefix:
            # continuation scheme past part 99: '<prefix>-leyes-001', three digits, sorting after every old part
            ext = [n for n in pub if n.startswith(prefix + '-leyes-')]
            k0 = max((int(n.split('-leyes-')[1]) for n in ext), default=0)
            for i in range(0, len(rest), E.PART_SIZE):
                out.append((f'{prefix}-leyes-{k0 + i // E.PART_SIZE + 1:03d}', rest[i:i + E.PART_SIZE]))
            E.say(f'{slug}: replan: {len(cat.get("ley", [])) - len(rest)} laws already published or skipped, '
                  f'{len(rest)} to go, parts {prefix}-leyes-{k0 + 1:03d}..')
            return out
        for i in range(0, len(rest), E.PART_SIZE):
            k = last + i // E.PART_SIZE
            if 30 + k > 99:
                break
            out.append((f'{30 + k}-leyes-{k + 1:02d}', rest[i:i + E.PART_SIZE]))
        E.say(f'{slug}: replan: {len(cat.get("ley", [])) - len(rest)} laws already published, {len(rest)} to go, '
              f'parts from {30 + last}')
        return out
    E.plan = plan


def flush(slug: str, docs_date: str) -> list[str]:
    out = []
    for name in sorted(pending(slug)):
        # each pending part was verified when written (letters check + scratch build of the published parts + it +
        # check.py); the autopush checks the whole build again (check.py) before main moves. Publish as the engine's
        # publish() does after its verify step.
        d = E.folder(slug) / 'corpus.d'
        vl = (d / f'{name}.VERIFIED').read_text(encoding='utf-8').strip().splitlines()
        line = vl[0]
        if len(vl) < 2 or vl[1] != 'sha256 ' + _sha(slug, name):
            r = 'NOT VERIFIED part changed since verification (or no checksum): verify again'
        elif E.letters_check(slug, name):
            r = 'NOT VERIFIED letters check changed since verification'
        else:
            tmp = d / f'{name}.ptmp'
            tmp.write_text(line + '\n', encoding='utf-8', newline='\n')
            E.write_docs(slug, docs_date, extra=[name])
            os.replace(tmp, d / f'{name}.PUBLISH')
            top = E.folder(slug) / 'PUBLISH'
            if not top.exists():
                top.write_text('corpus.d parts are published one by one, each once its own <part>.PUBLISH is '
                               'written.\n', encoding='utf-8', newline='\n')
            r = 'PUBLISH ' + line
        E.say(f'{slug} {name}: {r[:300]}')
        E.progress(slug, f'{name}: {r[:600]}')
        out.append(r)
        if r.startswith('PUBLISH'):
            (E.folder(slug) / 'corpus.d' / f'{name}.VERIFIED').unlink(missing_ok=True)
        else:
            break
    return out


BA_CAPPED_YEARS = [2006, 2001, 1992, 1975, 1974, 1965, 1964, 1961, 1960, 1959, 1942, 1889]


def ba_pass2():
    """Buenos Aires second pass (coordinator, 2026-10-31): normas.gba.gob.ar serves at most 20 result pages (200 laws)
    per search, and 12 years reach that cap newest-first. This pass reads the same years oldest-first
    (by_publication_date_asc, up to 20 pages each); replan() drops every law already published."""
    base = E.GBA

    class GBA2(base):
        def catalogue(self, n_laws: int) -> dict:
            out = base.catalogue(self, 0)
            laws, seen = [], set()
            for year in BA_CAPPED_YEARS:
                for pg in range(1, 21):
                    s = self.page(f'/resultados?page={pg}&q%5Bsort%5D=by_publication_date_asc'
                                  f'&q%5Bterms%5D%5Braw_type%5D=Law&q%5Bterms%5D%5Byear%5D={year}')
                    new = [f for f in re.findall(r'href="(/ar-b/ley/[^"]+)"', s) if f not in seen]
                    if not new:
                        break
                    for f in new:
                        seen.add(f)
                        laws.append({'page': f, 'title': ''})
            out['ley'] = laws
            return out
    E.ADAPTERS['buenos-aires'] = GBA2


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    if os.environ.get('AR_BA_PASS2') == '1':
        ba_pass2()
    try:
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception:
        pass
    cmd = sys.argv[1]
    if cmd == 'verify':
        slug, name, dd = sys.argv[2:5]
        ok, line = E.verify_part(slug, name, dd)
        bad = [f"{a['slug']} {v['from']}" for a in json.loads((E.folder(slug) / 'corpus.d' / f'{name}.json')
                                                               .read_text(encoding='utf-8'))['acts']
               for v in a['versions'] if v['from'] < '1810-05-25']
        if ok and bad:   # a source typo (e.g. publication "0026-12-11"): before any Argentine law
            ok, line = False, f'date before 1810 (source typo?): {bad[:3]}'
        if ok:
            (E.folder(slug) / 'corpus.d' / f'{name}.VERIFIED').write_text(
                line + '\nsha256 ' + _sha(slug, name) + '\n', encoding='utf-8', newline='\n')
            print('VERIFIED (publish pending) ' + line)
        else:
            print('NOT VERIFIED ' + line)
        return
    if cmd == 'flush':
        flush(sys.argv[2], sys.argv[3])
        return
    assert cmd == 'run'
    args = sys.argv[2:]
    nl, batch = 200, BATCH
    for a in list(args):
        if a.startswith('--laws='):
            nl = int(a.split('=')[1]); args.remove(a)
        elif a.startswith('--batch='):
            batch = int(a.split('=')[1]); args.remove(a)
        elif a == '--replan':
            args.remove(a)
    dd = dt.date.today().isoformat()
    orig_low = E._low

    def low(c, env=None):
        if len(c) >= 7 and c[4] == 'publish':
            slug, name = c[5], c[6]
            vf = E.folder(slug) / 'corpus.d' / f'{name}.VERIFIED'
            if vf.exists() and vf.read_text(encoding='utf-8').strip().splitlines()[1:2] == ['sha256 ' + _sha(slug, name)]:
                import subprocess
                return subprocess.CompletedProcess(c, 0, 'VERIFIED earlier (publish pending)' + chr(10), '')
            r = orig_low([c[0], '-X', 'utf8', str(Path(__file__)), 'verify', slug, name, c[7]], env=env)
            if len(pending(slug)) >= batch:
                flush(slug, c[7])
            return r
        return orig_low(c, env=env)
    E._low = low
    for s_ in args:
        if '--replan' in sys.argv:
            replan(s_)
        try:
            E.drive(s_, dd, nl, None)
        except E.Stop as e:
            E.say(f'{s_}: STOPPED {e}')
            E.progress(s_, f'STOPPED: {e}')
        flush(s_, dd)


if __name__ == '__main__':
    main()
