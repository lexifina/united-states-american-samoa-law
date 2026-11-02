"""What never leaves this machine for a shared repo (user's rule, 2026-10-29).

Speed-up methods go to the private lexifina/world-law-max-speed; operational notes (handoffs, issues, correspondence,
licence assessments, logs) go to the private lexifina/world-law-ops. The builder (tools/ in each country repo) skips
these files and scrubs this machine's home path from what it does publish. Before any push to a shared repo,
autopush runs audit_push() over exactly the objects being pushed, with the same names and markers as the final privacy
audit of every lexifina repo, so a push can never add a finding that audit would report.
"""
import re
import subprocess
from pathlib import Path

PRIVATE_NAME = re.compile(
    r'^(PROGRESS\.md|ISSUES\.md|PERMISSION[^/]*|NOTES\.md|[^/]*\.log|wayback[^/]*\.py|fetch[^/]*\.(py|sh)|crawl[^/]*\.py|'
    r'grab[^/]*\.py|probe[^/]*\.py|discover[^/]*\.py|ia\.py|cc_[^/]*\.py|download[^/]*\.py|harvest[^/]*\.py|'
    r'[^/]*push[^/]*\.sh|peachjam\.py|lii\.py|autopush\.py|watchdog\.sh|backup\.sh|BRIEF\.md|FANOUT\.md|WAVE\.md|'
    r'FORK\.md|ALT-SOURCES\.md|PEACHJAM\.md|register\.json|QUEUE[^/]*\.md|BENCHMARKS\.md|SCRAPING-LOG\.md)$')  # case-sensitive: a law's own notes.md is law content (2026-10-29 fix)
SPEED_MARK = re.compile(rb'host_get|cc_get|cc_captures|import wayback|wayback\.|ThreadPoolExecutor|requests a second|'
                        rb'Crawl-delay|adaptive rate|commoncrawl\.org|cluster\.idx|cloudflare|bot challenge|captcha|'
                        rb'firewall page', re.I)
# A script that is part of fetching: it imports a fetch module, calls into one, reads the fetch cache or opens URLs.
FETCH_USE = re.compile(rb'^[ \t]*(?:import|from)[ \t]+(?:fetch|wayback|lii|peachjam|download|crawl|harvest|grab)\w*\b|'
                       rb'\b(?:fetch|wayback|lii|peachjam)\w*\.\w+\(|\bload_cached\b|\burlopen\(|urllib\.request|'
                       rb'\brequests\.(?:get|post|Session)\b|\.cache/|requests\.jsonl', re.M)
HOME = re.compile(r'(?i)(?:[A-Z]:[\\/]+Users[\\/]+alany|/c/Users/alany|/home/alany)')
# The final privacy audit's content markers, checked in every text blob a push would add.
AUDIT_MARKS = {
    'speed tooling': re.compile(rb'host_get|cc_get\b|cc_captures|import wayback|wayback\.(get|captures|fetch)|'
                                rb'ThreadPoolExecutor|requests a second(?! (?:evaluation|opinion|hearing|review|examination))|adaptive rate', re.I),  # law text: "requests a second evaluation" (C.R.S. 16-8.5-103)
    'common crawl / archive tactics': re.compile(rb'data\.commoncrawl\.org|index\.commoncrawl\.org|cluster\.idx', re.I),
    'home path': re.compile(rb'(?i)(?:[A-Z]:(?:\\\\|\\|/)+Users(?:\\\\|\\|/)+alany|/c/Users/alany)'),
    'bot-challenge notes': re.compile(rb'(?i)cloudflare|bot challenge|captcha|firewall page'),
    # How the work is run (shared with gitlaw-scraper-dell's audit): session names, subagents, client identification.
    'agent workflow': re.compile(rb'\bgitlaw-[a-z]|\bsubagents?\b|\buser-agent\b|\bMozilla/\d', re.I),
    # How the sources were fetched: Lexifina's fetch scripts by name, their cache and request log, request counts.
    'scraping process': re.compile(rb'^[ \t]*(?:import|from)[ \t]+fetch\w*\b|\bfetch\w*\.(?:py|sh)\b|requests\.jsonl|'
                                   rb'cached by the sha256|fill the cache|\| Requests \||fetch scripts are kept', re.M),
}
AUDIT_TEXT = ('.py', '.sh', '.md', '.json', '.txt', '.csv', '.toml', '.yml', '.yaml')


def is_private(path: Path) -> bool:
    """True for a file that must stay private: a handoff, issue list, correspondence draft or log, a fetch helper by
    name, the playbook or the push tooling, or a script that uses the fast-fetch tooling or notes a site's defences."""
    if PRIVATE_NAME.match(path.name):
        return True
    if path.suffix in ('.py', '.sh', '.json'):
        try:
            data = path.read_bytes()
            # Any shipped script or config that the push audit would refuse stays private instead of blocking the push.
            return bool(SPEED_MARK.search(data) or FETCH_USE.search(data)
                        or any(rx.search(data) for rx in AUDIT_MARKS.values()))
        except OSError:
            return True
    return False


def _personal_emails() -> set[str]:
    """This machine's global git email is personal (never published); read it rather than writing it down here."""
    out = subprocess.run(['git', 'config', '--global', 'user.email'], capture_output=True, text=True).stdout.strip()
    return {out.lower()} if out and not out.lower().endswith('lexifina.com') else set()


# In a law file the bare word "CAPTCHA" is law (accessibility rules quoting WCAG: BremBITV Anlage 1 "alternative
# CAPTCHAs", "Audio-CAPTCHA"; 2026-11-01): there the bot-challenge marker counts only its other words.
LAW_BOT_MARK = re.compile(rb'(?i)cloudflare|bot challenge|firewall page')


def audit_push(repo: Path, new: str, old: str | None = None) -> list[str]:
    """Findings in what pushing `new` over `old` would add to a shared repo: private file names, the audit's content
    markers or the personal email in any added text blob, and any author or committer outside lexifina.com and the
    .invalid placeholders. Empty when the push is clean."""
    def git(*a: str, data: bytes | None = None) -> bytes:
        return subprocess.run(['git', *a], cwd=repo, capture_output=True, input=data).stdout
    span = [new] + ([f'^{old}'] if old else [])
    found: list[str] = []
    blobs: dict[str, str] = {}
    for line in git('rev-list', '--objects', *span).decode('utf-8', 'replace').splitlines():
        sha, _, path = line.partition(' ')
        if path:
            if PRIVATE_NAME.match(path.rsplit('/', 1)[-1]):
                found.append(f'private file name: {path}')
            if path.endswith(AUDIT_TEXT):
                blobs.setdefault(sha, path)
    if blobs:
        q = git('cat-file', '--batch', data=''.join(f'{s}\n' for s in blobs).encode())
        mails = [re.compile(re.escape(m).encode(), re.I) for m in _personal_emails()]
        i = 0
        for sha, path in blobs.items():
            end = q.index(b'\n', i)
            head = q[i:end].split()
            if len(head) < 3:  # not a blob (a tree named like a file)
                i = end + 1
                continue
            size = int(head[2])
            body = q[end + 1:end + 1 + size]
            i = end + 1 + size + 1
            # Law files (<act>/<unit>.md) can use these words as law ("subagents" in money-transfer regulations): the
            # workflow marker only applies to repository docs, data and tools.
            docs = '/' not in path or path.startswith(('tools/', 'data/'))
            # Shipped tools (the builder included) must not carry the fast-fetch markers either.
            if path.startswith('tools/') and SPEED_MARK.search(body):
                found.append(f'speed marker in shipped tool: {path}')
            found += [f'{k}: {path}' for k, rx in AUDIT_MARKS.items()
                      if (docs or k != 'agent workflow') and rx.search(body)
                      and (docs or k != 'bot-challenge notes' or LAW_BOT_MARK.search(body))]
            found += [f'personal email: {path}' for rx in mails if rx.search(body)]
    people = set(git('log', '--format=%ae%n%ce', *span).decode('utf-8', 'replace').split())
    found += [f'commit identity outside lexifina.com: {e}' for e in sorted(people)
              if not (e.endswith('lexifina.com') or e.endswith('.invalid'))]
    return found


# How a source was fetched, in a README (composer's rule, 2026-11-02): a README may say what the source is and credit
# it, but not the tools, rates, machine, robots/crawl-delay or reachability notes. Warn-only until every owner's README
# sweep is done; then these join AUDIT_MARKS. "wayback" is left out on purpose (often a legitimate credit).
FETCH_WARN = re.compile(rb'\bcurl\b|robots\.txt|crawl-delay|requests? (?:a|per) second|build machine|not reachable|'
                        rb'did not answer|challenge page', re.I)


def fetch_warnings(repo: Path, new: str, old: str | None = None) -> list[str]:
    """Repository docs, data and tools files that pushing `new` over `old` would add and that describe how a source was
    fetched. Reported, not blocking."""
    span = [new] + ([f'^{old}'] if old else [])
    out = subprocess.run(['git', 'rev-list', '--objects', *span], cwd=repo, capture_output=True).stdout
    found = []
    for line in out.decode('utf-8', 'replace').splitlines():
        sha, _, path = line.partition(' ')
        # Repository docs, data and tools only, never act folders (law text and their generated READMEs can use these
        # words in other senses), as for the 'agent workflow' marker.
        docs = '/' not in path or path.startswith(('tools/', 'data/'))
        # Code is skipped: the shared builder's own scrubbing patterns name these words in order to remove them.
        if docs and path.endswith(AUDIT_TEXT) and not path.endswith(('.py', '.sh')):
            body = subprocess.run(['git', 'cat-file', 'blob', sha], cwd=repo, capture_output=True).stdout
            hits = sorted({m.group(0).decode('utf-8', 'replace').lower() for m in FETCH_WARN.finditer(body)})
            if hits:
                found.append(f'{path}: {", ".join(hits)}')
    return found


def scrub(text: str) -> str:
    """This machine's home path replaced by ~, so published files name no user or machine."""
    return HOME.sub('~', text)
