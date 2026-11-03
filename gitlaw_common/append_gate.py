"""Append-only publishing for autopush (Alan, 2026-11-02: published history only grows by fast-forward).

    GITLAW_VERIFIED_PARTS_ONLY=1 python -X utf8 append_gate.py <scripts/<slug>-law> --repo <publish clone> \
        --url https://github.com/lexifina/<slug>-law.git --docs-date D [--seed <build clone>] [--corrections]

The publish clone is kept apart from the build clone, which build.py empties on every build. Each run:
1. syncs the publish clone to the published repo: origin/main, and exactly the remote's tags (local tags left by an
   earlier unpushed run are pruned, local only); main is reset to origin/main. A sparse checkout writes no files:
   append.py needs a clean status, not a working tree. --seed copies objects from the build clone first, so a first
   sync downloads little.
2. runs append.append(): new acts and newer versions go on top, then a new docs commit. When nothing is new but the
   documentation differs from main's (a README fix, a new builder), it appends one documentation commit instead,
   since append.py writes none when there are no new commits.
3. checks main with check.py against the corpus up to --docs-date (later versions are not on main yet). Only a clean
   check may be pushed.
It prints one JSON object. `result` is one of:
- 'same': nothing to add;
- 'tags' (with --repair-tags): nothing to append, but published commits lack tags they should carry (repair_tags());
  they are created here and pushed as new tags. Any append also creates such missing tags (tags_repaired);
- 'appended' or 'docs': main moved, a fast-forward of `old`;
- 'refused': append.py refused (main differs from the corpus in versions it already holds: a correction or a
  back-fill, decided by hand);
- 'check failed' or 'error'.
With --corrections (off unless given), held text that differs from the corpus is not refused: append.py appends one
labelled correction commit per wrong act version, and the check is append.check_corrected(), which reads main
with its corrections applied and requires the tip to equal the corpus on --docs-date. A main that already holds
correction commits is always checked that way.
It never pushes. autopush.publish() audits and pushes.

With --incremental, step 3 checks only what was appended (check_appended()): every version of each act the new
commits touch, read back on its day and the day before; the trailers and dates of the new commits; and, for every act,
the text main ends with against the corpus's newest version (one `git ls-tree`). The whole-corpus check moves to a
nightly gate: --full-check syncs the publish clone and runs check_main() on the published head, changing nothing.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import append as AP  # noqa: E402
import check as K  # noqa: E402
import publish_marker  # noqa: E402
import published_parts  # noqa: E402

B = AP.B
NO_FILES = '/.gitlaw-append-no-files\n'


class Frozen(type(Path())):
    """The corpus folder as it was when freeze() ran: corpus.d/*.json lists only the parts that were verified then (had
    a valid .PUBLISH, under GITLAW_VERIFIED_PARTS_ONLY=1; else every part), a later .PUBLISH reads as absent, and
    corpus.json, those parts and their markers read back the bytes read then. build.load() reads through it, so append,
    docs and check in one gate run all see one corpus: a PUBLISH that lands mid-run goes out on the next run."""
    snap: dict[str, bytes] | None = None
    parts_dir = ''
    selected: set[str] | None = None

    def glob(self, pattern, *a, **k):
        if Frozen.snap is not None and str(self) == Frozen.parts_dir and pattern == '*.json':
            return iter(sorted(self / Path(p).name for p in Frozen.snap
                               if os.path.dirname(p) == Frozen.parts_dir and p.endswith('.json')
                               and (Frozen.selected is None or p in Frozen.selected)))
        return super().glob(pattern, *a, **k)

    def publication_parts(self):
        return sorted(Frozen(p) for p in (Frozen.snap or {})
                      if os.path.dirname(p) == Frozen.parts_dir and p.endswith('.json'))

    def exists(self, *a, **k):
        s = str(self)
        if Frozen.snap is not None and os.path.dirname(s) == Frozen.parts_dir and s.endswith('.PUBLISH'):
            return s in Frozen.snap and (Frozen.selected is None
                                         or str(self.with_suffix('.json')) in Frozen.selected)
        return super().exists(*a, **k)

    def read_bytes(self):
        if (Frozen.snap is not None and os.path.dirname(str(self)) == Frozen.parts_dir
                and self.suffix in ('.PUBLISH', '.json') and str(self) not in Frozen.snap):
            raise FileNotFoundError(str(self))
        b = Frozen.snap.get(str(self)) if Frozen.snap is not None else None
        return b if b is not None else super().read_bytes()


def freeze(folder: Path) -> Path:
    """Snapshot the corpus once (corpus.json and the parts load() would read now) and return the folder as a Frozen
    path; every B.load(folder) in this run then reads that snapshot."""
    folder = Path(folder).resolve()
    parts = folder / 'corpus.d'
    snap: dict[str, bytes] = {}
    if (folder / 'corpus.json').exists():
        snap[str(folder / 'corpus.json')] = (folder / 'corpus.json').read_bytes()
    if parts.is_dir():
        for p in sorted(parts.glob('*.json')):
            marker = p.with_suffix('.PUBLISH')
            try:
                snap[str(marker)] = marker.read_bytes()
            except FileNotFoundError:
                pass
            snap[str(p)] = p.read_bytes()
    Frozen.snap, Frozen.parts_dir, Frozen.selected = snap, str(parts), None
    selected = set()
    if os.environ.get('GITLAW_VERIFIED_PARTS_ONLY') == '1':
        for p in list((Frozen(folder) / 'corpus.d').glob('*.json')):
            state, detail = publish_marker.status(p)
            if state not in ('legacy', 'match'):
                if state == 'mismatch':
                    print(f'UNVERIFIED: {detail}', file=sys.stderr)
            else:
                selected.add(str(p))
        Frozen.selected = selected
    return Frozen(folder)


def g(repo: Path, *a: str, check: bool = True) -> str:
    r = subprocess.run(['git', *a], cwd=repo, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if check and r.returncode:
        raise RuntimeError(f'git {" ".join(a[:3])}: {r.stderr.strip()[:300]}')
    return r.stdout.strip()


def sync(repo: Path, url: str, seed: Path | None) -> str | None:
    """The publish clone at the published main and tags. Returns the published main, or None when there is none."""
    if not (repo / '.git').exists():
        repo.mkdir(parents=True, exist_ok=True)
        g(repo, 'init', '-q', '-b', 'main')
        g(repo, 'remote', 'add', 'origin', url)
    g(repo, 'config', 'core.autocrlf', 'false')
    g(repo, 'config', 'core.sparseCheckout', 'true')
    (repo / '.git' / 'info').mkdir(exist_ok=True)
    (repo / '.git' / 'info' / 'sparse-checkout').write_text(NO_FILES, encoding='utf-8', newline='\n')
    if g(repo, 'remote', 'get-url', 'origin', check=False) != url:
        g(repo, 'remote', 'set-url', 'origin', url)
    if seed and (seed / '.git').exists():
        g(repo, 'fetch', '-q', '--no-tags', str(seed), '+refs/remotes/origin/main:refs/remotes/seed/main', check=False)
    heads = g(repo, 'ls-remote', '--heads', 'origin', 'main')
    if not heads:
        return None
    # --prune with these refspecs touches only this clone's refs/remotes/origin/main and refs/tags/*.
    g(repo, 'fetch', '-q', '--prune', 'origin', '+refs/heads/main:refs/remotes/origin/main', '+refs/tags/*:refs/tags/*')
    g(repo, 'checkout', '-q', '-f', '-B', 'main', 'refs/remotes/origin/main')
    return g(repo, 'rev-parse', 'main')


def docs_only(folder: Path, repo: Path, docs_date: str) -> bool:
    """One documentation commit on main when the docs differ from main's and there is no new law commit."""
    required = published_parts.required(repo, folder)
    part_records = {}
    c, raw = B.load(folder, part_records=part_records, required_parts=required)
    c['_docs_date'] = docs_date
    c['_repo'] = str(repo)
    B.M.load(c, folder, repo)
    log = AP.published_log(repo)
    tags = {t: 0 for t in g(repo, 'tag', '--list').split()}
    docs = B.docs_files(c, folder, raw, log, tags, docs_date, part_records=part_records)
    docs['tools/append.py'] = (HERE / 'append.py').read_text(encoding='utf-8').replace('\r\n', '\n')
    have = {}
    for line in g(repo, 'ls-tree', '-r', 'main').splitlines():
        meta, _, path = line.partition('\t')
        have[path] = meta.split()[2]
    changed = {p: t for p, t in docs.items() if (p in have if t is None else have.get(p) != K.blob_oid(t))}
    if not changed:
        return False
    head = g(repo, 'rev-parse', 'main')
    head_ct, head_tz = g(repo, 'log', '-1', '--format=%ct %ci', 'main').split()[0::3]
    co = c['country']
    committer = ('Lexifina', f'{co["slug"]}-law@lexifina.com')
    w = AP.Appender(repo, head, int(head_ct), head_tz)
    ts, tz = B.Clock(co['tz']).stamp(docs_date).split()
    when = f'{max(min(int(ts), int(time.time())), int(head_ct))} {tz}'  # never in the future, never before the head
    w.commit(committer, when, committer,
             f'Documentation update: tables, tools and REPRODUCE.md\n\nNo new law commits on {head[:12]}; corpus sha256 '
             f'{B.hashlib.sha256(raw).hexdigest()}, data retrieved {docs_date}.\n\nKind: documentation\n', changed)
    w.finish()
    g(repo, '-c', 'checkout.workers=0', 'checkout', '-q', '-f', 'main')
    return True


def check_main(folder: Path, repo: Path, docs_date: str, corrections: bool = False,
               held: dict[str, str] | None = None) -> dict:
    """check.py on main against the corpus as of docs_date: versions in force later are appended on their day.
    corrections, or a main that already holds correction commits: append.check_corrected() instead, which applies
    them (append.Reader) and checks the tip too. With `held` ({act: newest In-force day main holds}, from
    append.published_state()), only what main already holds is checked: the corpus is normally ahead of a published
    head between appends, and acts or versions not appended yet are not missing from it."""
    c, _ = B.load(folder)
    if held is not None:
        c['acts'] = [{**a, 'versions': vs} for a in c['acts'] if a['slug'] in held
                     if (vs := [v for v in a['versions'] if v['from'] <= held[a['slug']]])]
    if corrections or AP.corrections_on(repo):
        return AP.check_corrected(repo, c, docs_date)
    c['acts'] = [{**a, 'versions': vs} for a in c['acts'] if (vs := [v for v in a['versions'] if v['from'] <= docs_date])]
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / 'corpus.json'
        p.write_text(json.dumps(c, ensure_ascii=False), encoding='utf-8', newline='\n')
        res = K.check(repo, p, checked_on=docs_date)
    return {k: v for k, v in res.items() if k != 'corpus_sha256'}


def _acts_of(path: str, want) -> list[str]:
    """The acts a path lies at or under (check.py's rule: a commit belongs to an act when it touches a path under it)."""
    parts = path.split('/')
    return [p for p in ('/'.join(parts[:i]) for i in range(1, len(parts) + 1)) if p in want]


def _rows(repo: Path, rev: str, acts: set[str]) -> dict[str, list[tuple[str, str]]]:
    """check.all_commits_by_act() for `acts` only: the walk is limited to their paths when the list fits on a command
    line (Windows caps it near 32k characters), else it walks every commit as check.py does. Same rows either way."""
    rows: dict[str, list[tuple[str, str]]] = {a: [] for a in acts}
    paths = sorted(acts)
    limit = ['--', *paths] if sum(len(p) + 1 for p in paths) < 8000 else []
    out = subprocess.run(['git', '-c', 'core.quotePath=false', 'log', '--no-merges', '--no-renames', '--name-only',
                          '--format=%x00%H%x09%(trailers:key=In-force,valueonly,separator=)', rev, *limit],
                         cwd=repo, capture_output=True, text=True, encoding='utf-8', check=True).stdout
    for rec in out.split('\x00')[1:]:
        head, _, names = rec.partition('\n')
        h, _, d = head.partition('\t')
        d = d.strip()
        if not d:
            continue
        for a in {a for name in names.splitlines() if name for a in _acts_of(name, rows)}:
            rows[a].append((h, d))
    return rows


def _versions_match(cat, trees: dict, slug: str, vs: list[dict], rows: list[tuple[str, str]],
                    details: list) -> tuple[int, int]:
    """check.check()'s per-act test, kept identical: every version on its day, and the version before it on the day
    before. Returns (versions, mismatches)."""
    import datetime as dt
    versions = mismatches = 0
    for i, v in enumerate(vs):
        versions += 1
        if i + 1 < len(vs) and vs[i + 1]['from'] == v['from']:
            continue
        before = next((w for w in reversed(vs[:i]) if w['from'] < v['from']), None)
        for day, want in ((v['from'], v), ((dt.date.fromisoformat(v['from']) - dt.timedelta(days=1)).isoformat(), before)):
            h = K.state_on(rows, day)
            if want is None:
                if h is not None:
                    mismatches += 1
                    details.append(f'{slug}: something is in force on {day}, before the first version')
                continue
            if h is None:
                mismatches += 1
                details.append(f'{slug}: nothing in force on {day}')
                continue
            files = K.tree_oids(cat, h, slug, trees)
            expect = {f'{slug}/{k}.md': K.blob_oid(u['text']) for k, u in want['units'].items()}
            for f in sorted(set(files) | set(expect)):
                if files.get(f) != expect.get(f):
                    mismatches += 1
                    if len(details) < 50:
                        details.append(f'{slug} on {day}: {f} differs from version {want["from"]}')
    return versions, mismatches


def check_appended(folder: Path, repo: Path, docs_date: str, old: str, new: str) -> dict:
    """check_main() for an append only: what old..new added, against the corpus as of docs_date.
    1. Touched acts (a law file, any .md but the act's README.md, changed in old..new): every version read back on its
       day and on the day before, as check.py does, through the whole history at `new`.
    2. Every act: the text main ends with (the tree of `new`) equals the corpus's newest version up to docs_date. Main
       holds no version in force after docs_date, so that is the text in force on docs_date: a version append.py left
       out, or a law file changed in an act it did not report, is caught without walking the history.
    3. The new commits only: trailers parse and law commits carry In-force (Lexifina's docs commits excepted), no
       merges, committer dates never go backwards (starting from `old`'s), none dated after now (the docs commit may be
       up to two days ahead, as in check.py), and no In-force day after docs_date (counted as future_dated).
    The caller has confirmed that `old` is an ancestor of `new`. Same keys as check.check(), plus touched_acts."""
    c, _ = B.load(folder)
    acts = {a['slug']: vs for a in c['acts'] if (vs := [v for v in a['versions'] if v['from'] <= docs_date])}
    rng = f'{old}..{new}'
    names = subprocess.run(['git', '-c', 'core.quotePath=false', 'log', '--no-merges', '--no-renames', '--name-only',
                            '--format=', rng], cwd=repo, capture_output=True, text=True, encoding='utf-8',
                           check=True).stdout
    touched = {a for n in names.splitlines() if n.endswith('.md')
               for a in _acts_of(n, acts) if n != f'{a}/README.md'}
    details: list[str] = []
    versions = mismatches = 0
    cat = K.Cat(repo)
    try:
        rows = _rows(repo, new, touched) if touched else {}
        trees: dict = {}
        for slug in sorted(touched):
            n, m = _versions_match(cat, trees, slug, acts[slug], rows[slug], details)
            versions += n
            mismatches += m
    finally:
        cat.close()
    have: dict[str, dict[str, str]] = {a: {} for a in acts}
    tree = subprocess.run(['git', '-c', 'core.quotePath=false', 'ls-tree', '-r', '--full-tree', new], cwd=repo,
                          capture_output=True, text=True, encoding='utf-8', check=True).stdout
    for line in tree.splitlines():
        meta, _, path = line.partition('\t')
        kind, oid = meta.split()[1:3]
        if kind != 'blob' or not path.endswith('.md'):
            continue
        for a in _acts_of(path, have):
            if path != f'{a}/README.md':
                have[a][path] = oid
    for slug, vs in acts.items():
        expect = {f'{slug}/{k}.md': K.blob_oid(u['text']) for k, u in vs[-1]['units'].items()}
        if have[slug] != expect:
            bad = sorted(f for f in set(have[slug]) | set(expect) if have[slug].get(f) != expect.get(f))
            mismatches += len(bad)
            if len(details) < 50:
                details.append(f'{slug}: main ends with {len(bad)} file(s) unlike version {vs[-1]["from"]}, e.g. {bad[:3]}')
    trailer_errors = missing_in_force = late = 0
    # Not g(): str.strip() counts \x1c-\x1f as whitespace and would eat an empty last field.
    out = subprocess.run(['git', 'log', '--no-merges', '--format=%H%x1f%an%x1f%(trailers:only,unfold,separator=%x1e)%x1d',
                          rng], cwd=repo, capture_output=True, text=True, encoding='utf-8', check=True).stdout
    for rec in out.split('\x1d'):
        rec = rec.strip('\n')
        if not rec:
            continue
        h, an, tr = (rec.split('\x1f') + ['', ''])[:3]
        if an == 'Lexifina':
            continue
        fields = [t.split(':', 1) for t in tr.split('\x1e') if t]
        if not fields:
            trailer_errors += 1
        elif 'In-force' not in [f[0] for f in fields]:
            missing_in_force += 1
        else:
            days = [f[1].strip() for f in fields if f[0] == 'In-force' and len(f) > 1]
            if any(d > docs_date for d in days):
                late += 1
                if len(details) < 50:
                    details.append(f'{h[:12]}: In-force {max(days)} is after the data date {docs_date}')
    merges = int(g(repo, 'rev-list', '--merges', '--count', rng) or 0)
    cts = [int(g(repo, 'log', '-1', '--format=%ct', old))] + \
        [int(x) for x in g(repo, 'log', '--first-parent', '--reverse', '--format=%ct', rng).split()]
    backwards = sum(1 for a, b in zip(cts, cts[1:]) if b < a)
    if backwards and len(details) < 50:
        details.append(f'{backwards} new commit(s) dated before the commit they follow')
    now = int(time.time())
    added = cts[1:]
    future_dated = sum(1 for x in added[:-1] if x > now) + (1 if added and added[-1] > now + 2 * 86400 else 0) + late
    tip = AP.H.check(repo, c, docs_date)
    return {**tip, 'mode': 'incremental', 'acts': len(acts), 'touched_acts': len(touched), 'versions': versions,
            'mismatches': mismatches, 'trailer_errors': trailer_errors, 'missing_in_force': missing_in_force,
            'merges': merges, 'backwards': backwards, 'future_dated': future_dated, 'details': details}


FAIL_KEYS = ('mismatches', 'trailer_errors', 'missing_in_force', 'merges', 'backwards', 'future_dated',
             'tip_mismatches', 'image_errors', 'tip_errors')  # tip_mismatches is from check_corrected()


def repair_tags(repo: Path) -> int:
    """Create, in the publish clone, the tags main's history should carry but the remote lacks (sync() leaves exactly
    the remote's tags here), so the push sends them as new tags: a main pushed earlier without its tags (a tag push
    that failed after main landed, or another tool's push) gets them on the next run. Names as append.py and build.py
    give them, from main's data/commits.csv: per row, <act>/<day> for each act it lists and law/<key> for a law or
    start row; rows are matched to main's law commits (first parent, Lexifina's docs commits skipped). Nothing is
    created when the count or any day disagrees with the commits' In-force trailers; an existing tag is never moved.
    Returns the number created."""
    try:
        log = AP.published_log(repo)
    except SystemExit:  # no data/commits.csv on main
        return 0
    rows = [e for e in log if e['branch'] == 'main']
    out = subprocess.run(['git', 'log', '--first-parent', '--reverse',
                          '--format=%H%x1f%an%x1f%(trailers:key=In-force,valueonly,separator=)%x1e', 'main'],
                         cwd=repo, capture_output=True, text=True, encoding='utf-8', check=True).stdout
    commits = [(h, d.strip()) for h, an, d in ((rec.strip('\n').split('\x1f') + ['', ''])[:3]
                                               for rec in out.split('\x1e') if rec.strip('\n')) if an != 'Lexifina']
    if len(rows) != len(commits) or any(e['day'] != d for e, (_, d) in zip(rows, commits)):
        return 0
    want: dict[str, str] = {}
    for e, (h, _) in zip(rows, commits):
        for a in e['acts']:
            want.setdefault(f'{a}/{e["day"]}', h)
        if e['law'] and e['kind'] in ('law', 'start'):
            want.setdefault(f'law/{e["law"]}', h)
    have = set(g(repo, 'tag', '--list').split())
    missing = {t: h for t, h in want.items() if t not in have}
    if missing:
        data = ''.join(f'create refs/tags/{t} {h}\n' for t, h in sorted(missing.items()))
        subprocess.run(['git', 'update-ref', '--stdin'], cwd=repo, input=data, text=True, encoding='utf-8', check=True)
    return len(missing)


def full_check(folder: Path, repo: Path, url: str, docs_date: str, seed: Path | None) -> dict:
    """The nightly gate: the publish clone synced to the published head, then check_main() over the whole corpus.
    Appends nothing and pushes nothing."""
    head = sync(repo, url, seed)
    if head is None:
        return {'result': 'error', 'reason': 'the remote has no main to check'}
    try:
        published_parts.required(repo, folder, head)
    except published_parts.PublishedPartError as exc:
        return {'head': head, 'result': 'error', 'reason': str(exc)}
    # Only what the published head already holds (published_state(), as append reads it; it refuses a held version
    # whose text differs from the corpus unless main carries correction commits, which check_corrected() then reads).
    try:
        held = AP.published_state(repo, B.load(folder)[0], verify=not AP.corrections_on(repo))
    except SystemExit as e:  # B.CorpusError: main differs from the corpus in versions it already holds
        return {'head': head, 'result': 'check failed', 'check': {}, 'details': [str(e)[:2000]]}
    chk = check_main(folder, repo, docs_date, held=held)
    out = {'head': head, 'check': {k: v for k, v in chk.items() if k != 'details'}}
    if any(chk.get(k) for k in FAIL_KEYS):
        return {**out, 'result': 'check failed', 'details': chk['details'][:10]}
    return {**out, 'result': 'checked'}


def run(folder: Path, repo: Path, url: str, docs_date: str, seed: Path | None, incremental: bool = False,
        corrections: bool = False, repair: bool = False) -> dict:
    old = sync(repo, url, seed)
    if old is None:
        return {'result': 'error', 'reason': 'the remote has no main to append to'}
    out = {'old': old}
    try:
        published_parts.required(repo, folder, old)
    except published_parts.PublishedPartError as exc:
        return {**out, 'result': 'error', 'reason': str(exc)}
    try:
        res = AP.append(folder, repo, docs_date, corrections=True) if corrections else AP.append(folder, repo, docs_date)
    except SystemExit as e:  # B.CorpusError
        msg = str(e)
        if msg.startswith('main does not match the corpus'):
            return {**out, 'result': 'refused', 'reason': msg[:3000]}
        return {**out, 'result': 'error', 'reason': msg[:1000]}
    out.update(commits=res['commits'], new_acts=res['new_acts'], extended_acts=res['extended_acts'],
               tags_added=res.get('tags_added', 0))
    if res.get('corrections'):
        out.update(corrections=res['corrections'], corrected=res.get('corrected', {}))
    if res['commits']:
        out['result'] = 'appended'
    elif docs_only(folder, repo, docs_date):
        out['result'] = 'docs'
    else:
        n = repair_tags(repo) if repair else 0
        return {**out, 'result': 'tags' if n else 'same', 'new': old, 'tags_repaired': n}
    out['tags_repaired'] = repair_tags(repo)
    new = g(repo, 'rev-parse', 'main')
    if subprocess.run(['git', 'merge-base', '--is-ancestor', old, new], cwd=repo).returncode:
        return {**out, 'result': 'error', 'reason': f'internal: {new[:12]} is not a fast-forward of {old[:12]}'}
    out['new'] = new
    # check_appended() reads without corrections applied: a main holding them gets check_main() (check_corrected()).
    fixed = corrections or bool(AP.corrections_on(repo))
    chk = (check_appended(folder, repo, docs_date, old, new) if incremental and not fixed
           else check_main(folder, repo, docs_date, fixed))
    out['check'] = {k: v for k, v in chk.items() if k != 'details'}
    if any(chk.get(k) for k in FAIL_KEYS):
        out.update(result='check failed', details=chk['details'][:10])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('folder')
    ap.add_argument('--repo', required=True, help='the publish clone (created if missing)')
    ap.add_argument('--url', required=True, help='the published repository')
    ap.add_argument('--docs-date', required=True)
    ap.add_argument('--seed', help='a local clone holding the published main, to copy objects from')
    ap.add_argument('--incremental', action='store_true', help='check only what was appended (check_appended())')
    ap.add_argument('--corrections', action='store_true',
                    help='append labelled correction commits where main differs from the corpus, instead of refusing')
    ap.add_argument('--repair-tags', action='store_true',
                    help="with nothing to append, still create published commits' missing tags (result 'tags')")
    ap.add_argument('--full-check', action='store_true',
                    help='append nothing: sync, then check the published head against the whole corpus (nightly)')
    ap.add_argument('--freeze-parts', action='store_true',
                    help='read the corpus (and which parts are verified) once, at the start: append and check see '
                         'the same parts even if a .PUBLISH lands during the run (freeze())')
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    try:
        seed = Path(a.seed).resolve() if a.seed else None
        folder = freeze(a.folder) if a.freeze_parts else Path(a.folder).resolve()
        if a.full_check:
            out = full_check(folder, Path(a.repo).resolve(), a.url, a.docs_date, seed)
        else:
            out = run(folder, Path(a.repo).resolve(), a.url, a.docs_date, seed, a.incremental,
                      a.corrections, a.repair_tags)
    except Exception as e:  # reported, never raised: the caller reads one JSON line
        out = {'result': 'error', 'reason': f'{type(e).__name__}: {str(e)[:800]}'}
    print(json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    main()
