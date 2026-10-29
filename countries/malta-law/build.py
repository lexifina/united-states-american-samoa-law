"""Build the Malta law repository from the legislation.mt cache.

    python scripts/malta-law/build.py ~/Documents/malta-law --today YYYY-MM-DD [--workers 8] [--limit N]

Steps:
1. Parse every cached English version PDF into units (parse_pdf.py), cached as .cache/parsed/<snapshot>.json.
2. For each law (Chapter or subsidiary legislation), take its versions in date order. The first is the consolidated
   text as published then: a baseline commit by the Legislation Unit, labelled `Kind: consolidated`. Each later
   version is compared with the one before, unit by unit (article, regulation, schedule, title page).
3. A changed unit is credited to the law that the consolidation itself names for it: a citation that is new in that
   unit's margin history ("Amended by: XXV.2026.3", "Substituted by: L.N. 218 of 2026"). Failing that, a citation new
   anywhere in that law's version (`Evidence: law`); failing that, the one related Act or Legal Notice published
   between the two versions (`Evidence: date`); otherwise the change is the Legislation Unit's, `Kind: unexplained`.
4. Commits: one per amending law per in-force date, across every law it touched, dated noon Malta time on the date of
   the consolidated version (legislation.mt's point in time). Dates before 1970 are clamped to 1970-01-01, one second
   apart in order; the real date is in the `In-force:` trailer. Written with git fast-import, so the same cache always
   gives the same hashes.
"""
import argparse
import csv
import hashlib
import io
import json
import re
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent
CACHE = HERE / '.cache'
LAWS = CACHE / 'laws'
PDF = CACHE / 'pdf'
PARSED = CACHE / 'parsed'
PARSER_VERSION = '3'

COMMITTER = 'Lexifina <malta@lexifina.com>'
UNIT_AUTHOR = ('Legislation Unit (legislation.mt)', 'legislation-unit@legislation-mt.invalid')
ROMAN = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
MALTA_SUMMER = None  # Malta follows CET/CEST; computed in malta_offset()


# ---------------------------------------------------------------------------------------------------- parsing

def parse_one(snap: str) -> str:
    out = PARSED / f'{snap}.json'
    if out.exists():
        try:
            if json.loads(out.read_text('utf-8')).get('parser') == PARSER_VERSION:
                return snap
        except json.JSONDecodeError:
            pass
    import warnings
    warnings.filterwarnings('ignore')
    import parse_pdf
    try:
        d = parse_pdf.parse(str(PDF / f'{snap}.pdf'))
        d['parser'] = PARSER_VERSION
    except Exception as e:  # noqa: BLE001 - recorded, the version is skipped
        d = {'parser': PARSER_VERSION, 'error': f'{type(e).__name__}: {e}', 'preamble': [], 'units': []}
    out.write_text(json.dumps(d, ensure_ascii=False), 'utf-8')
    return snap


# ---------------------------------------------------------------------------------------------------- citations

def roman(s: str) -> int | None:
    s = s.upper()
    if not s or any(c not in ROMAN for c in s):
        return None
    total = 0
    for i, c in enumerate(s):
        v = ROMAN[c]
        total += -v if i + 1 < len(s) and ROMAN[s[i + 1]] > v else v
    return total


def cite_key(c: str) -> tuple | None:
    """'XXIII.1971.6' -> ('act', 1971, 23); 'L.N. 46 of 1965' -> ('ln', 1965, 46). Section numbers are dropped:
    the author of a commit is the whole law."""
    c = c.strip()
    m = re.match(r'^L\.\s*N\.?\s*(\d+)\s*(?:of|/)\s*(\d{4})', c, re.I)
    if m:
        return ('ln', int(m.group(2)), int(m.group(1)))
    m = re.match(r'^([IVXLCDM]+)\s*\.\s*(\d{4})\b', c)
    if m and roman(m.group(1)):
        return ('act', int(m.group(2)), roman(m.group(1)))
    m = re.match(r'^(?:Act|Att)\s+([IVXLCDM]+)\s+(?:of|tal-)\s*(\d{4})', c, re.I)
    if m and roman(m.group(1)):
        return ('act', int(m.group(2)), roman(m.group(1)))
    m = re.match(r'^G\.\s*N\.?\s*(\d+)\s*(?:of|/)\s*(\d{4})', c, re.I)
    if m:
        return ('gn', int(m.group(2)), int(m.group(1)))
    return None


def to_roman(n: int) -> str:
    out = ''
    for v, s in ((1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'), (100, 'C'), (90, 'XC'), (50, 'L'), (40, 'XL'),
                 (10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I')):
        while n >= v:
            out += s
            n -= v
    return out


def law_name(key: tuple) -> tuple[str, str]:
    kind, year, num = key
    if kind == 'act':
        word = 'Ordinance' if year < 1921 else 'Act'
        return f'{word} {to_roman(num)} of {year}', f'act-{year}-{num}@legislation-mt.invalid'
    if kind == 'ln':
        return f'L.N. {num} of {year}', f'ln-{year}-{num}@legislation-mt.invalid'
    return f'G.N. {num} of {year}', f'gn-{year}-{num}@legislation-mt.invalid'


def related_key(r: dict) -> tuple | None:
    m = re.match(r'eli/(act|ln)/(\d{4})/(\d+)', r.get('uri') or '')
    if m:
        return (m.group(1), int(m.group(2)), int(m.group(3)))
    return cite_key(r.get('name') or '')


# ---------------------------------------------------------------------------------------------------- files

def law_dir(law: dict) -> str:
    return f"{law['kind']}/{law['id']}"


def unit_path(law: dict, uid: str) -> str:
    safe = re.sub(r'[^0-9A-Za-z.~-]', '-', uid)
    return f'{law_dir(law)}/{safe}.md'


def norm(s: str) -> str:
    s = s.replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"')
    s = s.replace('–', '-').replace('—', '-').replace('­', '')
    return re.sub(r'\s+', ' ', s).strip()


def is_maltese(parsed: dict) -> bool:
    sample = ' '.join(parsed['preamble'][:8] + [l for u in parsed['units'][:15] for l in u['lines'][:3]])[:6000]
    return sum(sample.count(c) for c in 'ħġżċĦĠŻĊ') >= 8


def squash(s: str) -> str:
    return re.sub(r'\s+', '', s)


def clean_title(t: str | None) -> str:
    t = re.sub(r'<[^>]+>', ' ', t or '')
    t = re.split(r'\s+(?:Repealed|Revoked)\s+by\b', t)[0]
    return re.sub(r'\s+', ' ', t).strip()


def unit_text(u: dict) -> str:
    lines = []
    head = [h for h in u['heading'] if h]
    title = head[-1] if head and u['kind'] == 'article' else ''
    for h in (head[:-1] if title else head):
        lines.append(f'## {norm(h)}')
    lines.append(f"# {u['id']}. {norm(title)}".rstrip() if u['kind'] == 'article' else f"# {norm(u['id'])}")
    lines.extend(norm(l) for l in u['lines'] if norm(l))
    for n in u['notes']:
        if n['by']:
            lines.append(f"- {n['kind']} by: {'; '.join(norm(b) for b in n['by'])}.")
    for r in u['refs']:
        lines.append(f'- See {norm(r)}.')
    return '\n'.join(lines) + '\n'


def version_files(law: dict, parsed: dict) -> dict[str, tuple[str, set]]:
    """path -> (text, citation keys in that unit's history)."""
    files: dict[str, tuple[str, set]] = {}
    if parsed.get('preamble'):
        pre = '\n'.join(norm(l) for l in parsed['preamble'] if norm(l)) + '\n'
        keys = {k for k in (cite_key(c) for c in re.findall(r'(?:Act|Acts|Legal Notices?|L\.N\.)[^;.]*', pre)) if k}
        files[f'{law_dir(law)}/title.md'] = (pre, keys)
    for u in parsed['units']:
        keys = {k for n in u['notes'] for k in (cite_key(b) for b in n['by']) if k}
        files[unit_path(law, u['id'])] = (unit_text(u), keys)
    return files


# ---------------------------------------------------------------------------------------------------- dates

def malta_offset(d: datetime) -> int:
    """Malta: CET (+1), summer time (+2) from the last Sunday of March to the last Sunday of October (EU rule;
    applied to every year, which only matters for the hour shown)."""
    def last_sunday(month: int) -> datetime:
        x = datetime(d.year, month, 31 if month in (3, 10) else 30)
        return x - timedelta(days=(x.weekday() + 1) % 7)
    return 2 if last_sunday(3) <= d.replace(tzinfo=None) < last_sunday(10) else 1


def git_date(day: str, seq: int) -> tuple[str, str]:
    """(git date string, real date). Noon Malta time; before 1970, 1970-01-01 plus seq seconds."""
    d = datetime.strptime(day, '%Y-%m-%d').replace(hour=12)
    off = malta_offset(d)
    ts = int((d - timedelta(hours=off)).replace(tzinfo=timezone.utc).timestamp()) if d.year >= 1970 else seq
    return f'{ts} +0{off}00', day


# ---------------------------------------------------------------------------------------------------- history

def load_laws(limit: int | None) -> list[dict]:
    laws = []
    for f in sorted(LAWS.glob('*.json')):
        d = json.loads(f.read_text('utf-8'))
        raw = d.get('title') or ''
        d['title'] = clean_title(raw)
        m = re.search(r'(?:Repealed|Revoked)\s+by\s+([^<]+)', re.sub(r'<[^>]+>', ' ', raw))
        d['repealed_by'] = re.sub(r'\s+', ' ', m.group(1)).strip().rstrip('.') if m else ''
        d['eng'] = sorted([v for v in d['versions'] if v.get('snapshot') and (v.get('uri') or '').endswith('/eng')
                           and (PDF / f"{v['snapshot']}.pdf").exists()], key=lambda v: (v['date'], v['uri']))
        if d['eng']:
            laws.append(d)
    laws.sort(key=lambda d: (d['kind'], [int(x) if x.isdigit() else x for x in re.split(r'(\d+)', d['id'])]))
    return laws[:limit] if limit else laws


def label(law: dict) -> str:
    return f"Cap. {law['id']}" if law['kind'] == 'cap' else f"S.L. {law['id']}"


def plan(laws: list[dict]) -> tuple[list[dict], list[dict]]:
    """Every change as an event: {date, author key or None, law, path -> text|None, evidence}."""
    events: list[dict] = []
    issues: list[dict] = []
    for law in laws:
        prev_files: dict[str, tuple[str, set]] | None = None
        prev_v = None
        # Keep one English version per date: some English addresses serve the Maltese PDF, and some dates have
        # the same text uploaded more than once.
        chosen: dict[str, tuple[dict, dict]] = {}
        for v in law['eng']:
            parsed = json.loads((PARSED / f"{v['snapshot']}.json").read_text('utf-8'))
            if parsed.get('error') or not (parsed['units'] or parsed['preamble']):
                issues.append({'law': label(law), 'version': v['uri'], 'snapshot': v['snapshot'],
                               'issue': parsed.get('error') or 'no text'})
                continue
            if is_maltese(parsed):
                issues.append({'law': label(law), 'version': v['uri'], 'snapshot': v['snapshot'],
                               'issue': 'Maltese text at the English address'})
                continue
            chosen[v['date']] = (v, parsed)
        for _, (v, parsed) in sorted(chosen.items()):
            files = version_files(law, parsed)
            if prev_files is not None:
                # Typesetting alone (spacing, line breaks) is not a change: keep the earlier text.
                for p in files:
                    if p in prev_files and squash(files[p][0]) == squash(prev_files[p][0]):
                        files[p] = prev_files[p]
            if prev_files is None:
                events.append({'date': v['date'], 'author': None, 'kind': 'consolidated', 'law': law, 'version': v,
                               'changes': {p: t for p, (t, _) in files.items()}, 'evidence': {}})
            else:
                changed = {p for p in files if p not in prev_files or files[p][0] != prev_files[p][0]}
                removed = {p for p in prev_files if p not in files}
                if not changed and not removed:
                    prev_files, prev_v = files, v
                    continue
                law_new = set().union(*(files[p][1] for p in files)) - set().union(*(prev_files[p][1] for p in prev_files)) if prev_files else set()
                window = [r for r in law['related'] if r.get('published') and prev_v['date'] < r['published'] <= v['date']]
                window_keys = sorted({k for k in (related_key(r) for r in window) if k})
                buckets: dict[tuple | None, dict] = {}
                for p in sorted(changed | removed):
                    new = (files[p][1] if p in files else set()) - (prev_files[p][1] if p in prev_files else set())
                    if new:
                        who, ev = max(new), 'margin note'
                    elif len(law_new) == 1:
                        who, ev = next(iter(law_new)), 'law'
                    elif len(window_keys) == 1:
                        who, ev = window_keys[0], 'date'
                    else:
                        who, ev = None, 'none'
                    b = buckets.setdefault(who, {'changes': {}, 'evidence': {}, 'also': set()})
                    b['changes'][p] = files[p][0] if p in files else None
                    b['evidence'][p] = ev
                    b['also'] |= new - {who}
                for who, b in buckets.items():
                    events.append({'date': v['date'], 'author': who, 'kind': 'amendment' if who else 'unexplained',
                                   'law': law, 'version': v, 'prev': prev_v, 'changes': b['changes'],
                                   'evidence': b['evidence'], 'also': sorted(b['also'])})
            prev_files, prev_v = files, v
    return events, issues


def group(events: list[dict], related: dict) -> list[dict]:
    """One commit per (date, amending law) across every law it touched; baselines and unexplained changes are one
    commit per law per date."""
    commits: dict[tuple, dict] = {}
    for e in events:
        if e['kind'] == 'amendment':
            k = (e['date'], 1, e['author'], '')
        else:
            k = (e['date'], 0 if e['kind'] == 'consolidated' else 2, None, label(e['law']))
        c = commits.setdefault(k, {'date': e['date'], 'kind': e['kind'], 'author': e['author'], 'parts': []})
        c['parts'].append(e)
    def sort_key(k):
        date, order, author, lab = k
        return (date, order, author or ('', 0, 0), lab)
    return [commits[k] for k in sorted(commits, key=sort_key)]


def message(c: dict, related: dict) -> tuple[str, str, str]:
    laws = sorted({label(p['law']) for p in c['parts']})
    n = sum(len(p['changes']) for p in c['parts'])
    if c['kind'] == 'consolidated':
        p = c['parts'][0]
        name, email = UNIT_AUTHOR
        subject = f"{laws[0]}: {p['law']['title'] or ''} as consolidated on {c['date']}".strip()
        body = [f"The text of {laws[0]} as legislation.mt published it for {c['date']}, the earliest version it has.",
                'Who wrote each line before this date is not shown here; each article lists its history in its own',
                'margin notes, copied into the file.']
        trailers = [f'Kind: consolidated', f"Consolidated: {c['date']}", f"Law: {laws[0]}", f"Version: {p['version']['uri']}"]
    elif c['kind'] == 'unexplained':
        p = c['parts'][0]
        name, email = UNIT_AUTHOR
        subject = f"{laws[0]}: changes no law is credited with ({c['date']})"
        body = [f"legislation.mt's version of {laws[0]} for {c['date']} differs from the one for {p['prev']['date']} in",
                f"{n} unit(s), but neither the margin notes nor the related laws name one law for them."]
        trailers = ['Kind: unexplained', f"In-force: {c['date']}", f"Law: {laws[0]}", f"Version: {p['version']['uri']}"]
    else:
        name, email = law_name(c['author'])
        rel = related.get(c['author'], {})
        subject = f"{name}: {', '.join(laws[:6])}{' and others' if len(laws) > 6 else ''}"
        body = [f"Changes by {name} to {len(laws)} law(s), {n} unit(s), in force {c['date']}."]
        trailers = ['Kind: amendment', f"In-force: {c['date']}"]
        if rel.get('published'):
            trailers.append(f"Published: {rel['published']}")
        if rel.get('uri'):
            trailers.append(f"Source: https://legislation.mt/{rel['uri']}")
        evid = sorted({ev for p in c['parts'] for ev in p['evidence'].values()})
        trailers.append(f"Evidence: {', '.join(evid)}")
        also = sorted({law_name(a)[0] for p in c['parts'] for a in p.get('also', [])})
        for a in also:
            trailers.append(f'Also-cited: {a}')
        for lab in laws:
            trailers.append(f'Affecting: {lab}')
    return f'{name} <{email}>', subject, '\n'.join([subject, '', *body, '', *trailers]) + '\n'


# ---------------------------------------------------------------------------------------------------- write

def fast_import(repo: Path, commits: list[dict], related: dict, docs: dict[str, bytes], today: str) -> None:
    buf = io.BytesIO()
    w = buf.write
    seq = 0
    mark = 0
    for c in commits:
        seq += 1
        author, subject, msg = message(c, related)
        when, _ = git_date(c['date'], seq)
        mark += 1
        w(b'commit refs/heads/main\n')
        w(f'mark :{mark}\n'.encode())
        w(f'author {author} {when}\n'.encode())
        w(f'committer {COMMITTER} {when}\n'.encode())
        m = msg.encode('utf-8')
        w(f'data {len(m)}\n'.encode() + m + b'\n')
        for p in c['parts']:
            for path, text in sorted(p['changes'].items()):
                if text is None:
                    w(f'D {path}\n'.encode())
                else:
                    t = text.encode('utf-8')
                    w(f'M 100644 inline {path}\ndata {len(t)}\n'.encode() + t + b'\n')
        w(b'\n')
    # The documentation commit, dated by --today.
    when, _ = git_date(today, seq + 1)
    msg = f'Documentation: README, REPRODUCE, tools and laws.csv\n\nBuilt from the legislation.mt cache on {today}.\n'.encode()
    w(b'commit refs/heads/main\n')
    w(f'author {COMMITTER} {when}\ncommitter {COMMITTER} {when}\n'.encode())
    w(f'data {len(msg)}\n'.encode() + msg + b'\n')
    for path, data in sorted(docs.items()):
        w(f'M 100644 inline {path}\ndata {len(data)}\n'.encode() + data + b'\n')
    w(b'\n')
    r = subprocess.run(['git', '-C', str(repo), 'fast-import', '--quiet', '--force'], input=buf.getvalue(),
                       capture_output=True)
    if r.returncode:
        sys.exit(r.stderr.decode('utf-8', 'replace')[-3000:])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('repo', type=Path)
    ap.add_argument('--today', required=True)
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--limit', type=int)
    ap.add_argument('--parse-only', action='store_true')
    args = ap.parse_args()
    PARSED.mkdir(parents=True, exist_ok=True)

    laws = load_laws(args.limit)
    snaps = sorted({v['snapshot'] for law in laws for v in law['eng']})
    print(f'{len(laws)} laws, {len(snaps)} versions; parsing', flush=True)
    with ProcessPoolExecutor(args.workers) as pool:
        for i, _ in enumerate(pool.map(parse_one, snaps, chunksize=4), 1):
            if i % 500 == 0:
                print(f'  parsed {i}/{len(snaps)}', flush=True)
    if args.parse_only:
        return

    related: dict[tuple, dict] = {}
    for law in laws:
        for r in law['related']:
            k = related_key(r)
            if k and k not in related:
                related[k] = r
    events, issues = plan(laws)
    commits = group(events, related)
    print(f'{len(commits)} commits from {len(events)} events; {len(issues)} versions unreadable', flush=True)

    import docs as docmod
    docs = docmod.render(laws, commits, issues, related, args.today)

    repo = args.repo
    repo.mkdir(parents=True, exist_ok=True)
    remote = None
    if (repo / '.git').exists():
        r = subprocess.run(['git', '-C', str(repo), 'remote', 'get-url', 'origin'], capture_output=True, text=True)
        remote = r.stdout.strip() or None
        import shutil, os, stat
        def onerr(func, path, _):
            os.chmod(path, stat.S_IWRITE)
            func(path)
        shutil.rmtree(repo / '.git', onerror=onerr)
        for child in repo.iterdir():
            if child.name != '.git':
                shutil.rmtree(child, onerror=onerr) if child.is_dir() else child.unlink()
    subprocess.run(['git', 'init', '-q', '-b', 'main', str(repo)], check=True)
    subprocess.run(['git', '-C', str(repo), 'config', 'core.autocrlf', 'false'], check=True)
    if remote:
        subprocess.run(['git', '-C', str(repo), 'remote', 'add', 'origin', remote], check=True)
    fast_import(repo, commits, related, docs, args.today)
    subprocess.run(['git', '-C', str(repo), 'checkout', '-q', '-f', 'main'], check=True)
    head = subprocess.run(['git', '-C', str(repo), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    count = subprocess.run(['git', '-C', str(repo), 'rev-list', '--count', 'HEAD'], capture_output=True, text=True).stdout.strip()
    print(f'built {repo}: {count} commits, head {head}', flush=True)


if __name__ == '__main__':
    main()
