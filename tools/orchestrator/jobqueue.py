"""One shared, sharded job queue for the global-law corpora: replaces hand-written claim files (2026-11-03).

Every lexifina/*-law repo has one STATUS, and open repos have JOBS that workers lease for a set time.

Repo status
  open       work left
  complete   finished: the source's own listing matches what is published (95%+);
             'by-size' means it was seeded as complete from its size and still needs that check
  exhausted  every lawful text is published, so it stays small
  blocked    robots, terms, challenge, paywall, scans only or unreachable (reason recorded)
  held       waiting on Alan (HOLD-alan claim)
"Open repos" is the finish line: drive it to zero.

Jobs: (repo, platform, step[, shard]) with a priority. A worker leases the best queued job; an expired lease
returns to the queue by itself (every command reaps first).
  * Within a host: never parallel. A job with a host is not leased while another lease holds that host.
  * Within a repo: one appender. Only steps ending in '-shard' (parallel history builds by act range) may run beside
    another lease on the same repo; the step that pushes is always single.
  * Claims bridge: a lease writes scripts/world-law/claims/<slug>.txt ('queue-lease <owner> until <utc> job <id>'),
    so the existing autopush loops skip it; done, fail, release and expiry remove that file again. A repo whose claim
    file was written by anyone else is never leased.
Order (priority): national empty with a source 100 > national small 80 > subnational empty 60 > subnational small 40 >
unclear 20; shared-platform shards +5.

  python -X utf8 jobqueue.py seed                         # build/refresh from census + source check + claims (idempotent)
  python -X utf8 jobqueue.py lease --owner gpt-sol-3 [--platform sibom] [--tier national] [--step breadth] [--minutes 90]
  python -X utf8 jobqueue.py renew <id> --owner X [--minutes 90]
  python -X utf8 jobqueue.py done <id> --owner X [--status complete|exhausted|blocked] [--reason "..."]
  python -X utf8 jobqueue.py fail <id> --owner X --note "..."   # back to the queue; failed after 3 attempts
  python -X utf8 jobqueue.py release <id> --owner X
  python -X utf8 jobqueue.py add <slug> --step history-shard --shard "acts 0-999" [--host h] [--priority 70]
  python -X utf8 jobqueue.py mark <slug> --status blocked --reason "..."
  python -X utf8 jobqueue.py status | list [--state queued]
Windows Python only (the database is SQLite on NTFS); from WSL call python.exe with this path.
"""
import argparse
import datetime as dt
import json
import os
import re
import sqlite3
import sys
from pathlib import Path
from urllib.parse import urlparse

HOME = Path(__file__).resolve().parent
DB = HOME / 'queue' / 'jobs.sqlite'
SCRIPTS = Path(r'C:\Users\alany\Documents\lexifina\scripts')
CLAIMS = SCRIPTS / 'world-law' / 'claims'
SOURCES = SCRIPTS / 'world-law' / 'wave4-sources.json'
OVERRIDES = HOME / 'queue' / 'status-overrides.json'   # {slug: {"status": ..., "reason": ...}} kept by hand
CENSUS = HOME / 'census'
SMALL_KB, BIG_KB = 500, 5000
TERMINAL = ('complete', 'exhausted', 'blocked', 'held')
MAX_ATTEMPTS = 3

# shared engines: one proven runner covers a whole shard
PLATFORMS = [
    (r'^argentina-.*-city-law$', 'sibom'),
    (r'^brazil-.*-city-law$', 'sapl'),
    (r'^switzerland-.*-city-law$', 'lexwork'),
    (r'^indonesia-.+-law$', 'jdih'),
    (r'^bosnia-.+-law$', 'ba-gazette'),
    (r'^russia-.+-law$', 'pravo-catalogue'),
]


def now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def iso(t):
    return t.strftime('%Y-%m-%dT%H:%M:%SZ')


def connect():
    DB.parent.mkdir(exist_ok=True)
    c = sqlite3.connect(DB, timeout=30, isolation_level=None)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA journal_mode=WAL')
    c.executescript("""
    CREATE TABLE IF NOT EXISTS repos(slug TEXT PRIMARY KEY, tier TEXT, platform TEXT, status TEXT, reason TEXT,
        size_kb INTEGER, source_url TEXT, updated TEXT);
    CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY, slug TEXT, platform TEXT, step TEXT, shard TEXT DEFAULT '',
        host TEXT, priority INTEGER, state TEXT, owner TEXT, lease_until TEXT, attempts INTEGER DEFAULT 0, note TEXT,
        created TEXT, updated TEXT, done_at TEXT);
    CREATE UNIQUE INDEX IF NOT EXISTS jobs_key ON jobs(slug, step, shard) WHERE state IN ('queued','leased');
    CREATE TABLE IF NOT EXISTS events(at TEXT, job INTEGER, slug TEXT, owner TEXT, what TEXT, detail TEXT);
    """)
    return c


def event(c, job, slug, owner, what, detail=''):
    c.execute('INSERT INTO events VALUES (?,?,?,?,?,?)', (iso(now()), job, slug, owner, what, detail))


# ---------- claims bridge ----------

def claim_line(slug):
    f = CLAIMS / f'{slug}.txt'
    try:
        return f.read_text(encoding='utf-8', errors='replace').splitlines()[0].strip() if f.exists() else ''
    except (OSError, IndexError):
        return ''


def write_claim(slug, owner, until, job):
    (CLAIMS / f'{slug}.txt').write_text(f'queue-lease {owner} until {iso(until)} job {job}\n', encoding='utf-8')


def drop_claim(slug, job):
    f = CLAIMS / f'{slug}.txt'
    line = claim_line(slug)
    if line.startswith('queue-lease ') and line.endswith(f' job {job}'):
        f.unlink(missing_ok=True)


def reap(c):
    t = iso(now())
    for j in c.execute("SELECT * FROM jobs WHERE state='leased' AND lease_until < ?", (t,)).fetchall():
        c.execute("UPDATE jobs SET state='queued', owner=NULL, lease_until=NULL, updated=? WHERE id=?", (t, j['id']))
        drop_claim(j['slug'], j['id'])
        event(c, j['id'], j['slug'], j['owner'], 'expired')


# ---------- seeding ----------

def latest_census():
    f = max(CENSUS.glob('census-*.tsv'), key=lambda p: p.name)
    rows = {}
    for line in f.read_text(encoding='utf-8').splitlines():
        p = line.split('\t')
        if len(p) >= 4 and p[0].isdigit():
            rows[p[3]] = int(p[0])
    return rows


def tiers(slugs):
    """'national' unless another repo's stem is a dash-prefix of this one (brazil-parana-law under brazil-law)."""
    stems = {s.removesuffix('-law') for s in slugs}
    out = {}
    for s in slugs:
        st = s.removesuffix('-law')
        out[s] = 'sub' if any(t != st and st.startswith(t + '-') for t in stems) else 'national'
    return out


def platform_of(slug):
    return next((p for rx, p in PLATFORMS if re.match(rx, slug)), 'own')


def seed(c):
    sizes = latest_census()
    tier = tiers(sizes)
    src = {}
    if SOURCES.exists():
        src = {x['slug']: x for x in json.loads(SOURCES.read_text(encoding='utf-8'))}
    over = json.loads(OVERRIDES.read_text(encoding='utf-8')) if OVERRIDES.exists() else {}
    t = iso(now())
    added = 0
    for slug, kb in sizes.items():
        s = src.get(slug, {})
        plat = platform_of(slug)
        cur = c.execute('SELECT status, reason FROM repos WHERE slug=?', (slug,)).fetchone()
        line = claim_line(slug)
        # status: an override or a worker's final status wins; then holds; then the source check; then size
        if slug in over:
            status, reason = over[slug]['status'], over[slug].get('reason', '')
        elif cur and cur['status'] in ('complete', 'exhausted', 'blocked') and cur['reason'] != 'by-size':
            status, reason = cur['status'], cur['reason']
        elif line.startswith('HOLD-alan'):
            status, reason = 'held', line
        elif plat == 'pravo-catalogue':
            status, reason = 'blocked', 'publication.pravo.gov.ru robots.txt disallows /File (texts); catalogue only'
        elif s.get('verdict') in ('blocked', 'scans-only', 'unreachable'):
            status, reason = 'blocked', f"{s['verdict']}: {(s.get('notes') or '')[:200]}"
        elif kb >= BIG_KB:
            status, reason = 'complete', 'by-size'
        else:
            status, reason = 'open', s.get('verdict') or ''
        c.execute('INSERT INTO repos VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(slug) DO UPDATE SET tier=excluded.tier, '
                  'platform=excluded.platform, status=excluded.status, reason=excluded.reason, size_kb=excluded.size_kb, '
                  'source_url=excluded.source_url, updated=excluded.updated',
                  (slug, tier[slug], plat, status, reason, kb, s.get('source_url') or '', t))
        if status != 'open':
            for j in c.execute("SELECT id FROM jobs WHERE slug=? AND state='queued'", (slug,)).fetchall():
                c.execute("UPDATE jobs SET state='cancelled', updated=? WHERE id=?", (t, j['id']))
            continue
        empty = kb < SMALL_KB
        step = 'breadth' if empty else 'depth'
        if tier[slug] == 'national':
            pri = 100 if empty and s.get('verdict') in (None, 'go', 'go-small') else 80
        else:
            pri = 60 if empty else 40
        if s.get('verdict') == 'unclear':
            pri = 20
        if plat != 'own':
            pri += 5
        host = urlparse(s['source_url']).netloc.lower() if s.get('source_url') else None
        try:
            c.execute("INSERT INTO jobs(slug, platform, step, shard, host, priority, state, created, updated) "
                      "VALUES (?,?,?,?,?,?, 'queued', ?, ?)", (slug, plat, step, '', host, pri, t, t))
            added += 1
        except sqlite3.IntegrityError:
            c.execute("UPDATE jobs SET priority=?, host=COALESCE(host, ?) WHERE slug=? AND step=? AND shard='' AND "
                      "state='queued'", (pri, host, slug, step))
    return added


# ---------- leasing ----------

def lease(c, owner, minutes=90, platform=None, tier=None, step=None):
    c.execute('BEGIN IMMEDIATE')
    try:
        reap(c)
        q = ("SELECT j.* FROM jobs j JOIN repos r ON r.slug=j.slug WHERE j.state='queued' AND r.status='open'"
             + (' AND j.platform=?' if platform else '') + (' AND r.tier=?' if tier else '')
             + (' AND j.step=?' if step else '') + ' ORDER BY j.priority DESC, j.attempts, j.id')
        args = [a for a in (platform, tier, step) if a]
        busy_hosts = {r[0] for r in c.execute("SELECT host FROM jobs WHERE state='leased' AND host IS NOT NULL")}
        busy_single = {r[0] for r in c.execute("SELECT slug FROM jobs WHERE state='leased' AND step NOT LIKE '%-shard'")}
        busy_any = {r[0] for r in c.execute("SELECT slug FROM jobs WHERE state='leased'")}
        for j in c.execute(q, args).fetchall():
            if j['host'] and j['host'] in busy_hosts:
                continue
            if j['slug'] in busy_single or (not j['step'].endswith('-shard') and j['slug'] in busy_any):
                continue
            line = claim_line(j['slug'])
            if line and not line.startswith('queue-lease '):
                continue  # claimed by hand by someone else: never take it
            until = now() + dt.timedelta(minutes=minutes)
            c.execute("UPDATE jobs SET state='leased', owner=?, lease_until=?, updated=? WHERE id=?",
                      (owner, iso(until), iso(now()), j['id']))
            if not j['step'].endswith('-shard') or not line:
                write_claim(j['slug'], owner, until, j['id'])
            event(c, j['id'], j['slug'], owner, 'leased', iso(until))
            c.execute('COMMIT')
            r = c.execute('SELECT * FROM repos WHERE slug=?', (j['slug'],)).fetchone()
            return {**dict(j), 'state': 'leased', 'owner': owner, 'lease_until': iso(until),
                    'tier': r['tier'], 'source_url': r['source_url'], 'repo_reason': r['reason']}
        c.execute('COMMIT')
        return None
    except Exception:
        c.execute('ROLLBACK')
        raise


def mine(c, job, owner):
    j = c.execute('SELECT * FROM jobs WHERE id=?', (job,)).fetchone()
    if not j or j['state'] != 'leased' or j['owner'] != owner:
        sys.exit(f'job {job} is not leased by {owner}')
    return j


def finish(c, job, owner, how, status=None, reason='', note='', minutes=90):
    c.execute('BEGIN IMMEDIATE')
    reap(c)
    j = mine(c, job, owner)
    t = iso(now())
    if how == 'renew':
        until = now() + dt.timedelta(minutes=minutes)
        c.execute('UPDATE jobs SET lease_until=?, updated=? WHERE id=?', (iso(until), t, job))
        if claim_line(j['slug']).endswith(f' job {job}'):
            write_claim(j['slug'], owner, until, job)
    elif how == 'done':
        c.execute("UPDATE jobs SET state='done', note=?, updated=?, done_at=? WHERE id=?", (reason or note, t, t, job))
        if status:
            c.execute('UPDATE repos SET status=?, reason=?, updated=? WHERE slug=?', (status, reason, t, j['slug']))
        drop_claim(j['slug'], job)
    elif how == 'fail':
        n = j['attempts'] + 1
        c.execute("UPDATE jobs SET state=?, owner=NULL, lease_until=NULL, attempts=?, note=?, updated=? WHERE id=?",
                  ('failed' if n >= MAX_ATTEMPTS else 'queued', n, note, t, job))
        drop_claim(j['slug'], job)
    elif how == 'release':
        c.execute("UPDATE jobs SET state='queued', owner=NULL, lease_until=NULL, updated=? WHERE id=?", (t, job))
        drop_claim(j['slug'], job)
    event(c, job, j['slug'], owner, how, status or note or reason)
    c.execute('COMMIT')


# ---------- reporting ----------

def summary(c=None):
    """Finish-line figures for the goal page."""
    c = c or connect()
    reap(c)
    st = {r[0]: r[1] for r in c.execute('SELECT status, COUNT(*) FROM repos GROUP BY status')}
    nat = {r[0]: r[1] for r in c.execute("SELECT status, COUNT(*) FROM repos WHERE tier='national' GROUP BY status")}
    jobs = {r[0]: r[1] for r in c.execute('SELECT state, COUNT(*) FROM jobs GROUP BY state')}
    since = iso(now() - dt.timedelta(hours=6))
    done6 = c.execute("SELECT COUNT(*) FROM jobs WHERE state='done' AND done_at > ?", (since,)).fetchone()[0]
    left = jobs.get('queued', 0) + jobs.get('leased', 0)
    by_size = c.execute("SELECT COUNT(*) FROM repos WHERE status='complete' AND reason='by-size'").fetchone()[0]
    return {'repos': sum(st.values()), 'status': st, 'open': st.get('open', 0),
            'national_total': sum(nat.values()), 'national_finished': sum(nat.get(s, 0) for s in TERMINAL if s != 'held'),
            'national_open': nat.get('open', 0), 'complete_by_size': by_size, 'jobs': jobs,
            'jobs_done_6h': done6, 'eta_hours': round(left / (done6 / 6), 1) if done6 else None,
            'leases': [dict(r) for r in c.execute("SELECT id, slug, step, shard, owner, lease_until FROM jobs "
                                                   "WHERE state='leased' ORDER BY lease_until")]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['seed', 'lease', 'renew', 'done', 'fail', 'release', 'add', 'mark', 'status', 'list'])
    ap.add_argument('arg', nargs='?')
    ap.add_argument('--owner')
    ap.add_argument('--minutes', type=int, default=90)
    ap.add_argument('--platform')
    ap.add_argument('--tier', choices=['national', 'sub'])
    ap.add_argument('--step')
    ap.add_argument('--shard', default='')
    ap.add_argument('--host')
    ap.add_argument('--priority', type=int, default=70)
    ap.add_argument('--status', choices=['open', 'complete', 'exhausted', 'blocked', 'held'])
    ap.add_argument('--reason', default='')
    ap.add_argument('--note', default='')
    ap.add_argument('--state')
    a = ap.parse_args()
    c = connect()
    if a.cmd == 'seed':
        n = seed(c)
        print(json.dumps({'new_jobs': n, **{k: v for k, v in summary(c).items() if k != 'leases'}}))
    elif a.cmd == 'lease':
        if not a.owner:
            sys.exit('--owner is required')
        print(json.dumps(lease(c, a.owner, a.minutes, a.platform, a.tier, a.step)))
    elif a.cmd in ('renew', 'done', 'fail', 'release'):
        if not (a.owner and a.arg):
            sys.exit('job id and --owner are required')
        finish(c, int(a.arg), a.owner, a.cmd, a.status, a.reason, a.note, a.minutes)
        print('ok')
    elif a.cmd == 'add':
        t = iso(now())
        r = c.execute('SELECT platform FROM repos WHERE slug=?', (a.arg,)).fetchone()
        c.execute("INSERT INTO jobs(slug, platform, step, shard, host, priority, state, created, updated) "
                  "VALUES (?,?,?,?,?,?, 'queued', ?, ?)",
                  (a.arg, r['platform'] if r else platform_of(a.arg), a.step or 'breadth', a.shard, a.host, a.priority, t, t))
        print('ok')
    elif a.cmd == 'mark':
        over = json.loads(OVERRIDES.read_text(encoding='utf-8')) if OVERRIDES.exists() else {}
        over[a.arg] = {'status': a.status, 'reason': a.reason, 'at': iso(now())}
        OVERRIDES.write_text(json.dumps(over, indent=1, ensure_ascii=False), encoding='utf-8')
        seed(c)
        print('ok')
    elif a.cmd == 'status':
        print(json.dumps(summary(c), indent=1))
    elif a.cmd == 'list':
        q = 'SELECT id, slug, platform, step, shard, host, priority, state, owner, attempts FROM jobs'
        rows = c.execute(q + (' WHERE state=?' if a.state else '') + ' ORDER BY priority DESC, id', ([a.state] if a.state else [])).fetchall()
        for r in rows:
            print('\t'.join('' if v is None else str(v) for v in tuple(r)))


if __name__ == '__main__':
    main()
