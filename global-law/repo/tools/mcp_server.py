#!/usr/bin/env python3
"""An MCP server for the global law tree. Standard library only; run it from a clone with its submodules.

  git clone --recurse-submodules https://github.com/lexifina/global-law && cd global-law
  claude mcp add global-law -- python tools/mcp_server.py          (or any MCP client: stdio, newline-delimited JSON-RPC)

It gives an AI model the same answers as tools/law.py, with the record's limits stated on every answer: the law in
force on a date in any jurisdiction, who wrote each word, what changed between two dates, every law that changed a
provision, a search of all the law in force on a date, and the full record of any law's commit. It reads git and
changes nothing.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import traceback
from functools import lru_cache
from pathlib import Path

sys.dont_write_bytecode = True  # never leave cache files inside the tree (they block git checkout)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import law  # noqa: E402

ROOT = law.ROOT
PROTOCOL_VERSIONS = ('2025-06-18', '2025-03-26', '2024-11-05')
SERVER = {'name': 'global-law', 'title': 'Global law: every jurisdiction, one history', 'version': '1.0.0'}
NOT_LAW = re.compile(r'(^|/)(README|LICENSE|REPRODUCE|KORREKTUREN|CHANGELOG|RESEARCH)[^/]*$|(^|/)(tools|tests|data|build|\.github)/')


class UserError(Exception):
    """A mistake in the request: reported to the model as a tool error it can correct."""


# --- caching: every answer reads the same timeline and manifest; both change only when HEAD moves -----------------

def head() -> str:
    return law.git('rev-parse', 'HEAD').strip()


@lru_cache(maxsize=4)
def _timeline(_head: str):
    return _original_timeline()


@lru_cache(maxsize=4)
def _manifest(_head: str):
    return _original_manifest()


_original_timeline, _original_manifest = law.timeline, law.manifest
law.timeline = lambda: _timeline(head())  # law.py's own functions call these by name, so they share the cache
law.manifest = lambda: _manifest(head())


def run_law(fn, *args):
    """law.py stops with SystemExit on a bad date or path; here that is a correctable tool error."""
    try:
        return fn(*args)
    except SystemExit as e:
        raise UserError(str(e.code if e.code is not None else e)) from None


def date_arg(value) -> str:
    if isinstance(value, int) and len(str(value)) == 8:  # 20220101, as some models write dates
        value = f'{str(value)[:4]}-{str(value)[4:6]}-{str(value)[6:]}'
    return run_law(law.day, str(value or 'today').strip())


def num(args: dict, key: str, default: int, most: int) -> int:
    value = args.get(key)
    if value in (None, ''):
        return default
    try:
        return max(1, min(int(value), most))
    except (TypeError, ValueError):
        raise UserError(f'{key} must be a whole number, not {value!r}.') from None


def explain(date: str, path: str) -> str:
    """law.py's reason for missing text, with its command-line hint turned into the matching tool."""
    why = run_law(law.explain_missing, date, path)
    return re.sub(r'see `law\.py log [^`]*`', 'provision_history shows when and by which law', why)


def path_arg(value: str) -> str:
    if not value or not value.strip():
        raise UserError('A path is needed, for example us/federal/usc/title-11/1182.md. Use find_provision to look one up.')
    path = law.norm(value.strip())
    run_law(law.corpus_of, path)
    return path


# --- the index of provisions, for find_provision --------------------------------------------------------------------

@lru_cache(maxsize=16)
def names_of(corpus: str, sha: str) -> tuple[str, ...]:
    """Every law file in a corpus at one commit (names only: cheap even for a large corpus)."""
    out = law.git('ls-tree', '-r', '--name-only', sha, cwd=ROOT / corpus).splitlines()
    return tuple(n for n in out if n.endswith('.md') and not NOT_LAW.search(n))


@lru_cache(maxsize=64)
def provisions(corpus: str, sha: str, inner: str = '') -> list[tuple[str, str]]:
    """(path inside the corpus, first heading) for the law files under `inner` in a corpus at one commit. Headings
    are read only for the files asked about, so browsing one folder of a large corpus stays fast."""
    cwd = ROOT / corpus
    names = [n for n in names_of(corpus, sha) if not inner or n == inner or n.startswith(inner + '/')]
    headings: dict[str, str] = {}
    # Every file in one git process. Sizes are in bytes, so read bytes and decode each file on its own.
    batch = subprocess.run(['git', 'cat-file', '--batch'], cwd=cwd, input=''.join(f'{sha}:{n}\n' for n in names).encode('utf-8'),
                           capture_output=True).stdout
    pos = 0
    for name in names:
        line_end = batch.index(b'\n', pos)
        size = int(batch[pos:line_end].split()[2])
        body = batch[line_end + 1:line_end + 1 + size].decode('utf-8', 'replace')
        pos = line_end + 1 + size + 1
        heading = next((l.lstrip('#').strip() for l in body.splitlines() if l.startswith('#')), '')
        title = re.search(r'^(?:title|heading): (.+)$', body, re.M)
        headings[name] = heading if heading else (title.group(1) if title else '')
    return [(n, headings.get(n, '')) for n in names]


@lru_cache(maxsize=4)
def _aliases(_head: str) -> list[dict]:
    done = subprocess.run(['git', 'show', 'HEAD:aliases.json'], cwd=ROOT, capture_output=True, encoding='utf-8')
    text = done.stdout if done.returncode == 0 else ((ROOT / 'aliases.json').read_text(encoding='utf-8') if (ROOT / 'aliases.json').exists() else '')
    try:
        return json.loads(text).get('aliases', []) if text else []
    except json.JSONDecodeError:
        return []


def aliases() -> list[dict]:
    return _aliases(head())


def corpus_head(corpus: str) -> str:
    return law.pinned('HEAD', corpus) or ''


# --- tools ------------------------------------------------------------------------------------------------------------

def t_list_jurisdictions(args: dict) -> tuple[str, dict]:
    m = law.manifest()
    events = law.timeline()
    rows, data = [], []
    for c in m['corpora']:
        own = [e for e in events if e.corpus == c['path'] and e.kind != 'documentation']
        first, last = (own[0].in_force, own[-1].in_force) if own else (None, None)
        files = names_of(c['path'], corpus_head(c['path']))
        example = files[0] if files else ''
        info = {'path': c['path'], 'name': c['name'], 'language': c.get('language'), 'coverage': c.get('coverage'),
                'provision_files': len(files), 'record_starts': first, 'last_change_in_record': last,
                'record_to': c.get('record_to'), 'record_note': c.get('record_note'), 'changes': len(own),
                'example_path': f"{c['path']}/{example}"}
        data.append(info)
        rows.append(f"- {c['path']}: {c['name']} ({c.get('language')}; {len(files)} provision files; {len(own)} changes)."
                    f" Covers {c.get('coverage')}. Record from {first}; last change {last}"
                    + (f"; complete to {c['record_to']}. {c.get('record_note', '')}" if c.get('record_to') else '.')
                    + f" Example path: {info['example_path']}")
    tree = json.loads(law.git('show', 'HEAD:jurisdiction.json'))
    text = ('Paths are country (ISO 3166-1) / level / corpus / file. Dates are in-force dates (YYYY-MM-DD).\n'
            + '\n'.join(rows))
    return text, {'corpora': data, 'tree': tree, 'scheme': m.get('scheme'), 'date_rule': m.get('date_rule')}


def t_find_provision(args: dict) -> tuple[str, dict]:
    query = (args.get('query') or '').strip()
    if not query:
        raise UserError('Give a query: a section or article number ("1182", "16a", "reg 13") or words from a heading.')
    scope = (args.get('jurisdiction') or '').strip().strip('/')
    limit = num(args, 'max_results', 15, 100)
    words = [w for w in re.split(r'[\s,§]+', query.lower()) if w]
    numbers = [w for w in words if re.fullmatch(r'\d+[a-z]?', w)]
    found = []
    q = query.lower()
    for entry in aliases():  # popular names ("Schuldenbremse"), which the text itself never uses
        names = [n.lower() for n in entry['names']]
        if len(q) < 3:
            continue
        if any(q == n or (q in n and len(q) >= 0.6 * len(n)) or (n in q and len(n) >= 0.6 * len(q)) for n in names):
            weight = 100  # the query is the popular name
        elif any(n in q for n in names):
            weight = 4  # the name is part of a longer query: rank beside heading matches, not above them
        else:
            continue
        for rank, p in enumerate(entry['paths']):
            if not scope or p.startswith(scope):
                found.append((weight - rank * (1 if weight == 100 else 0), p, f"{entry['names'][0]}: {entry.get('note', '')}"))
    for c in law.manifest()['corpora']:
        if scope and not c['path'].startswith(scope):
            continue
        for name, heading in provisions(c['path'], corpus_head(c['path'])):
            stem = re.sub(r'\.md$', '', name.rsplit('/', 1)[-1]).lower().lstrip('0').removeprefix('art-').lstrip('0')
            hay = f'{name} {heading}'.lower()
            score = 0
            for n in numbers:
                if stem == n or stem == n.lstrip('0'):
                    score += 10
                elif re.search(rf'(^|[^0-9a-z]){re.escape(n)}([^0-9a-z]|$)', hay):
                    score += 2
            score += sum(3 for w in words if w not in numbers and w in heading.lower())
            score += sum(1 for w in words if w not in numbers and w in name.lower())
            if score:
                found.append((score, f"{c['path']}/{name}", heading))
    if not found and words:
        # Headings are often only a number ("Artikel 16a"), so fall back to the words of the law in force today.
        root = law.root_on(date_arg('today'), law.timeline())
        for c in law.manifest()['corpora']:
            if scope and not c['path'].startswith(scope):
                continue
            sha = law.pinned(root, c['path'])
            if not sha:
                continue
            terms = [w for w in words if len(w) > 2]
            grep = ['git', 'grep', '-c', '-i', '-I', '-F', *[a for w in terms for a in ('-e', w)], sha, '--', '*.md']
            out = subprocess.run(grep, cwd=ROOT / c['path'], capture_output=True, encoding='utf-8', errors='replace').stdout
            heads = dict(provisions(c['path'], sha))
            for line in out.splitlines():
                name, _, count = line.removeprefix(f'{sha}:').rpartition(':')
                if name in heads and count.isdigit():
                    found.append((int(count), f"{c['path']}/{name}", heads[name] + '  (matched in the text)'))
    found.sort(key=lambda r: (-r[0], r[1]))
    seen: set[str] = set()
    found = [r for r in found if not (r[1] in seen or seen.add(r[1]))]
    hits = [{'path': p, 'heading': h, 'score': s} for s, p, h in found[:limit]]
    if not hits:
        return f'No provision matches {query!r}. Try list_jurisdictions for the layout, or search_law for words in the text.', {'results': []}
    return '\n'.join(f"{h['path']}  {h['heading']}" for h in hits), {'results': hits}


SOURCE_KEYS = ('Source', 'Affecting', 'In-Kraft-Quelle', 'Reader')


def commit_body(corpus: str, sha: str) -> str:
    return law.git('show', '-s', '--format=%B', sha, cwd=law.corpus_dir(corpus))


def sources_of(corpus: str, sha: str) -> list[str]:
    """The official links a change carries, for citing it."""
    out = []
    for line in commit_body(corpus, sha).splitlines():
        key, sep, value = line.partition(': ')
        if sep and key in SOURCE_KEYS and value.startswith('http') and value not in out:
            out.append(value.strip())
    return out


# --- applicability: which changes reach a case commenced on a date -------------------------------------------------
# A corpus may record, per change, the cases it applies to, one line per group of cases (groups are alternatives,
# conditions within a group all hold):  Applies: 11 U.S.C. §1182(1) | commenced-on-or-after 2020-03-27; pending-on 2022-06-21 | set-by …
# A change with no Applies line has no recorded scope: the general rule is that it applies from its in-force date.

def applies_groups(body: str) -> list[dict]:
    groups = []
    for line in body.splitlines():
        if not line.startswith('Applies: '):
            continue
        parts = [p.strip() for p in line[len('Applies: '):].split('|')]
        conds = []
        for c in (parts[1].split(';') if len(parts) > 1 else []):
            kind, _, when = c.strip().partition(' ')
            if kind:
                conds.append((kind, when.strip()))
        set_by = next((p.removeprefix('set-by').strip() for p in parts[2:] if p.startswith('set-by')), None)
        groups.append({'provision': parts[0], 'conditions': conds, 'set_by': set_by})
    return groups


def group_holds(conditions: list[tuple[str, str]], commenced: str) -> tuple[bool, list[str]]:
    """Whether a case commenced on `commenced` meets every condition, and the assumptions made to say so."""
    assumed = []
    for kind, when in conditions:
        if kind == 'any-commencement':
            continue
        if kind == 'commenced-on-or-after' and not commenced >= when:
            return False, []
        if kind == 'commenced-after' and not commenced > when:
            return False, []
        if kind == 'commenced-before' and not commenced < when:
            return False, []
        if kind == 'commenced-on-or-before' and not commenced <= when:
            return False, []
        if kind == 'pending-on':
            if commenced > when:
                return False, []
            assumed.append(f'the case was still pending on {when}')
        if kind not in ('commenced-on-or-after', 'commenced-after', 'commenced-before', 'commenced-on-or-before', 'pending-on'):
            assumed.append(f'a condition this tool cannot check holds: {kind} {when}'.strip())
    return True, assumed


def scope_in_words(body: str, section: str) -> list[str]:
    """Sentences like "Applies to any case commenced on or after March 27, 2020", from the part of a change's message
    about this provision. A message has one block per provision changed: a heading line, then indented lines."""
    blocks, current = [], []
    for line in body.splitlines():
        if line and not line[0].isspace():
            blocks.append(current)
            current = [line]
        else:
            current.append(line)
    blocks.append(current)
    mine = [b for b in blocks if b and re.search(rf'§\s*{re.escape(section)}\b', b[0])] or blocks
    out = []
    for b in mine:
        text = '\n'.join(b)
        for m in re.finditer(r'(?m)^[ \t]*(Applies to [^\n]*(?:\n[ \t]+(?![ \t]|https?:|Instruction:)[^\n]+)*)', text):
            sentence = re.sub(r'\s+', ' ', m.group(1)).strip()
            if sentence not in out:
                out.append(sentence)
    return out


MONTHS = {m: i for i, m in enumerate(('january', 'february', 'march', 'april', 'may', 'june', 'july', 'august',
                                      'september', 'october', 'november', 'december'), 1)}


def _iso(text: str) -> str | None:
    m = re.search(r'([A-Z][a-z]+)\.? (\d{1,2}), (\d{4})', text)
    if m and m.group(1).lower() in MONTHS:
        return f'{m.group(3)}-{MONTHS[m.group(1).lower()]:02d}-{int(m.group(2)):02d}'
    m = re.search(r'(\d{4}-\d{2}-\d{2})', text)
    return m.group(1) if m else None


def conditions_from_words(sentence: str) -> list[tuple[str, str]] | None:
    """The common US forms of a scope sentence as conditions, or None when the sentence is not one of them. Only exact,
    well-known phrasings are read; anything else stays words for the reader to check."""
    s = sentence.lower()
    if 'before, on, or after' in s or 'before, on or after' in s:
        return [('any-commencement', '')]
    conds = []
    for phrase, kind in (('commenced on or after', 'commenced-on-or-after'), ('commenced before', 'commenced-before'),
                         ('commenced after', 'commenced-after'), ('commenced on or before', 'commenced-on-or-before'),
                         ('pending on', 'pending-on')):
        for m in re.finditer(re.escape(phrase) + r'([^;.]*?)(?=(?:,| and| or|;|\.|$))', sentence, re.I):
            # "commenced under title 11 on or after March 27, 2020": the date may follow a few words later
            tail = sentence[m.start():m.start() + 120]
            when = _iso(tail)
            if when:
                conds.append((kind, when))
    if not conds:
        m = re.search(r'commenced under [^,;.]*? (on or after|before|after|on or before) ([A-Z][a-z]+\.? \d{1,2}, \d{4})', sentence)
        if m:
            kind = {'on or after': 'commenced-on-or-after', 'before': 'commenced-before', 'after': 'commenced-after',
                    'on or before': 'commenced-on-or-before'}[m.group(1)]
            conds.append((kind, _iso(m.group(2))))
    return conds or None


def t_applies_to_case(args: dict) -> tuple[str, dict]:
    path, commenced, date = path_arg(args.get('path', '')), date_arg(args.get('commenced')), date_arg(args.get('date'))
    if commenced > date:
        raise UserError(f'The case is commenced on {commenced}, after the date asked about ({date}).')
    corpus, _ = law.corpus_of(path)
    hist = [h for h in run_law(law.history, path) if h['in_force'] <= date]
    if not hist and not run_law(law.history, path):
        raise UserError(explain(date, path))  # not in the record at any date
    # A provision not yet in force on the date can still be looked ahead from (the case may be pending when it comes in).
    rows, any_scope = [], False
    for h in hist:
        body = commit_body(corpus, h['commit'])
        groups = applies_groups(body)
        any_scope = any_scope or bool(groups)
        if not groups:
            # No structured scope; the record may still say in words which cases a change reaches.
            said = scope_in_words(body, Path(path).stem.lstrip('0'))
            verdict, why, assumed = ('in force' if h['in_force'] <= commenced else 'no recorded scope'), said[:5], []
            read = [c for c in (conditions_from_words(w) for w in said) if c]
            if read and h['in_force'] > commenced:
                results = [group_holds(c, commenced) for c in read]
                ok = [a for holds, a in results if holds]
                verdict = 'applies (scope read from the record\'s words)' if ok else 'does not apply (scope read from the record\'s words)'
                assumed = ok[0] if ok else []
        else:
            results = [(g, *group_holds(g['conditions'], commenced)) for g in groups]
            ok = [(g, a) for g, holds, a in results if holds]
            verdict = 'applies' if ok else 'does not apply'
            why = ['; '.join(f'{k} {w}'.strip() for k, w in g['conditions']) + (f" (set by {g['set_by']})" if g['set_by'] else '') for g in groups]
            assumed = ok[0][1] if ok else []
        rows.append({**h, 'verdict': verdict, 'scope': why, 'assumptions': assumed})
    later = [r for r in rows if r['in_force'] > commenced]
    excluded = [r for r in later if r['verdict'].startswith('does not apply')]
    text_date = date if not excluded else max([commenced] + [r['in_force'] for r in later if r['in_force'] < excluded[0]['in_force']])
    lines = [f'{path} for a case commenced on {commenced}, read on {date}.']
    for r in later:
        lines.append(f"- {r['in_force']} {r['law']}: {r['verdict']}" + (f" (scope: {' OR '.join(r['scope'])})" if r['scope'] else '')
                     + (f" — assuming {', '.join(r['assumptions'])}" if r['assumptions'] else ''))
    if not later:
        lines.append('No change took effect after the case was commenced; the text in force on the commencement date applies.')
    if not any_scope:
        read = [r for r in later if 'read from the record' in r['verdict']]
        if read:
            lines.append('Scope here is read from the words of the record (the change notes), not from structured data, '
                         'for the changes marked above; other changes follow the general rule that a change applies from its in-force date. '
                         'Check the amending laws for anything the words do not cover.')
        else:
            lines.append('No scope is recorded for these changes, so this reading follows the general rule: each change applies from its in-force date.'
                         + (' The record mentions a scope in words (shown above); check it against the case.' if any(r['scope'] for r in later)
                            else ' Check the amending laws for transition rules.'))
    if excluded:
        lines.append(f'At least one later change does not reach this case, so the text below is the text in force on {text_date}, before it; '
                     'later changes that do reach the case are listed above and may need to be read in.')
    # Look ahead: a law in force after the date asked about may still reach back to this case (Pub. L. 117-151 and
    # the 2022 gap). Say so, with the date to read its text on.
    ahead = []
    section = Path(path).stem.lstrip('0')
    for h in run_law(law.history, path):
        if h['in_force'] <= date:
            continue
        body = commit_body(corpus, h['commit'])
        groups = [g['conditions'] for g in applies_groups(body)] or [c for c in (conditions_from_words(w) for w in scope_in_words(body, section)) if c]
        reaching = [g for g in groups if any(k in ('commenced-on-or-after', 'commenced-after', 'any-commencement') for k, _ in g)]
        reach = [group_holds(g, commenced) for g in reaching]
        if any(ok for ok, _ in reach):
            assumed = next(a for ok, a in reach if ok)
            diff = run_law(law.diff_between, text_date, h['in_force'], path)
            changed = '\n'.join(l for l in diff.splitlines() if ('{+' in l or '[-' in l))
            ahead.append({'in_force': h['in_force'], 'law': h['law'], 'commit': h['commit'], 'assumptions': assumed,
                          'changes_to_the_text': changed})
    for a in ahead:
        lines.append(f"Later, after the date asked about: {a['law']} (in force {a['in_force']}) reaches back to this case"
                     + (f", assuming {', '.join(a['assumptions'])}" if a['assumptions'] else '')
                     + f". Compared with the text below, the text it puts in force reads ([-removed-] {{+added+}}):\n"
                     + (a['changes_to_the_text'][:3000] or '  (no difference in the words)'))
    # The case's own timeline: which text governed it in each period, so a reading "as of today" cannot hide a
    # period in between (the 2022-2024 window for §1182(1)).
    periods, start = [], commenced
    steps = [r for r in later if not r['verdict'].startswith('does not apply')]
    for r in steps:
        if r['in_force'] > start:
            periods.append({'from': start, 'until': r['in_force'], 'text_as_of': start, 'by': None})
        start = r['in_force']
        periods[-1:] and None
        periods.append({'from': start, 'until': None, 'text_as_of': start, 'by': r['law'],
                        'certain': r['verdict'].startswith('applies'), 'verdict': r['verdict']})
    if not steps:
        periods.append({'from': commenced, 'until': None, 'text_as_of': commenced, 'by': None})
    for i in range(len(periods) - 1):
        periods[i]['until'] = periods[i + 1]['from']
    periods = [p for p in periods if p['until'] is None or p['until'] > p['from']]
    if len(periods) > 1:
        lines.insert(1, 'For this case, period by period:')
        prev = None
        for i, p in enumerate(periods, 2):
            text_now = run_law(law.text_on, p['text_as_of'], path) or ''
            span = f"{p['from']} to {p['until']} (exclusive)" if p['until'] else f"from {p['from']}"
            how = (f" by {p['by']}" + ('' if p.get('certain') else ' — no recorded scope: check whether it reaches cases already pending')) if p['by'] else ''
            delta = ''
            if prev is not None:
                d = run_law(law.diff_between, prev, p['text_as_of'], path)
                delta = ' Changes: ' + ' / '.join(l.strip() for l in d.splitlines() if '{+' in l or '[-' in l)[:600] if d else ' No change in the words.'
            lines.insert(i, f"  - {span}: the text in force on {p['text_as_of']}{how}.{delta}")
            prev = p['text_as_of']
            del text_now
    text = run_law(law.text_on, text_date, path) or ''
    return '\n'.join(lines) + '\n\n' + text, {'path': path, 'commenced': commenced, 'date': date, 'changes': rows, 'periods': periods,
                                              'text_date': text_date, 'text': text, 'scope_recorded': any_scope,
                                              'later_changes_reaching_back': ahead}


@lru_cache(maxsize=16)
def modifies_in(corpus: str, sha: str) -> list[dict]:
    """Every `Modifies:` effect in a corpus's history: a change to how a provision applies that leaves its words alone
    (proposed shape: Modifies: <provision> | <kind> | <from>..<until> | <effect> | set-by <source>)."""
    out = law.git('log', sha, '--format=%x1e%an%x1f%B', '--grep=^Modifies: ', cwd=law.corpus_dir(corpus))
    effects = []
    for record in out.split('\x1e'):
        author, _, body = record.partition('\x1f')
        curated = bool(re.search(r'(?m)^Curated: yes\b', body))
        for line in body.splitlines():
            if not line.startswith('Modifies: '):
                continue
            parts = [p.strip() for p in line[len('Modifies: '):].split('|')]
            span = parts[2] if len(parts) > 2 else ''
            start, _, end = span.partition('..')
            effects.append({'provision': parts[0], 'kind': parts[1] if len(parts) > 1 else '', 'from': start.strip() or None,
                            'until': end.strip() or None, 'effect': parts[3] if len(parts) > 3 else '',
                            'set_by': (parts[4].removeprefix('set-by').strip() if len(parts) > 4 else author.strip()),
                            'curated': curated})
    return effects


def beyond_the_words(date: str, path: str) -> list[str]:
    """Where the words in force on a date are not the whole answer: a later law that reaches back over the date, or
    an effect that changes how the provision applies without changing its words."""
    corpus, rel = law.corpus_of(path)
    notes = []
    section = Path(path).stem.lstrip('0')
    for h in run_law(law.history, path):
        if h['in_force'] <= date:
            continue
        body = commit_body(corpus, h['commit'])
        groups = [g['conditions'] for g in applies_groups(body)] or [c for c in (conditions_from_words(w) for w in scope_in_words(body, section)) if c]
        for conds in groups:
            starts = [w for k, w in conds if k in ('commenced-on-or-after', 'commenced-after') and w <= date]
            if starts or any(k == 'any-commencement' for k, _ in conds):
                notes.append(f"{h['law']}, in force {h['in_force']}, reaches back: it applies to cases commenced "
                             + (f'on or after {starts[0]}' if starts else 'before, on or after its date')
                             + f', so for some cases pending on {date} a later text may govern (see applies_to_case).')
                break
    effects = [e for e in modifies_in(corpus, law.pinned('HEAD', corpus) or 'HEAD')
               if rel.removesuffix('.md') in e['provision'] or e['provision'].endswith(f'/{section}') or f'§{section}' in e['provision']]
    ended = sorted(e['from'] for e in effects if e['kind'] == 'ended' and e['from'])
    current: dict[tuple[str, str], dict] = {}
    for e in sorted(effects, key=lambda e: e['from'] or ''):
        if e['kind'] == 'ended' or not ((e['from'] or '') <= date):
            continue
        until = e['until'] or next((d for d in ended if d > (e['from'] or '')), None)  # an open effect ends at the next "ended"
        if until and date >= until:
            continue
        current[(e['provision'], e['kind'])] = e  # a later effect of the same kind supersedes an open earlier one
    for e in current.values():
        notes.append(f"On {date} this provision was {e['kind'] or 'modified'} without a change to its words: {e['effect']} "
                     f"(set by {e['set_by']}" + ('; entered by hand from the cited source' if e.get('curated') else '') + ').')
    return notes


def status_of(date: str, path: str) -> dict:
    corpus, _ = law.corpus_of(path)
    events = law.timeline()
    root = law.root_on(date, events)
    hist = run_law(law.history, path)
    last = [h for h in hist if h['in_force'] <= date]
    upcoming = [h for h in hist if h['in_force'] > date]
    return {'date': date, 'path': path, 'corpus': corpus, 'world_commit': root,
            'corpus_commit': law.pinned(root, corpus), 'caveats': law.caveats(date, corpus, events),
            'last_change': last[-1] if last else None, 'next_change': upcoming[0] if upcoming else None}


def t_read_law(args: dict) -> tuple[str, dict]:
    date, path = date_arg(args.get('date')), path_arg(args.get('path', ''))
    text = run_law(law.text_on, date, path)
    st = status_of(date, path)
    if text is None:
        why = explain(date, path)
        info = law.corpus_info(st['corpus'])
        if 'any date' in why and info.get('record_to') and date > info['record_to']:
            why += f" The record ends on {info['record_to']}, so it may exist in the law after that date."
        return why + ''.join(f'\nNote: {c}' for c in st['caveats']), {**st, 'in_force': False, 'text': None, 'why': why}
    head_lines = [f'{path} as in force on {date}.']
    if st['last_change']:
        lc = st['last_change']
        st['sources'] = sources_of(st['corpus'], lc['commit'])
        head_lines.append(f"Last changed by {lc['law']}, in force {lc['in_force']}."
                          + (f" Sources: {' '.join(st['sources'])}" if st['sources'] else ''))
    if st['next_change']:
        nc = st['next_change']
        head_lines.append(f"Next change in the record: {nc['law']}, in force {nc['in_force']}.")
    head_lines += [f'Note: {c}' for c in st['caveats']]
    beyond = beyond_the_words(date, path)
    head_lines += [f'Not the whole answer: {b}' for b in beyond]
    return '\n'.join(head_lines) + '\n\n' + text, {**st, 'in_force': True, 'text': text, 'beyond_the_words': beyond}


def t_world_on_date(args: dict) -> tuple[str, dict]:
    date = date_arg(args.get('date'))
    events = law.timeline()
    root = law.root_on(date, events)
    rows, data = [], []
    for c in law.manifest()['corpora']:
        last = [e for e in events if e.corpus == c['path'] and e.in_force <= date and e.kind != 'documentation']
        nxt = next((e for e in events if e.corpus == c['path'] and e.in_force > date and e.kind != 'documentation'), None)
        notes = law.caveats(date, c['path'], events)
        data.append({'corpus': c['path'], 'name': c['name'], 'last_change': last[-1].law if last else None,
                     'last_change_in_force': last[-1].in_force if last else None,
                     'next_change': nxt.law if nxt else None, 'next_change_in_force': nxt.in_force if nxt else None,
                     'corpus_commit': law.pinned(root, c['path']), 'caveats': notes})
        rows.append(f"- {c['path']}: " + (f'{last[-1].law}, in force {last[-1].in_force}' if last else 'not yet in the record')
                    + (f'; next: {nxt.law} on {nxt.in_force}' if nxt else '') + ''.join(f' [{n}]' for n in notes))
    return f'World commit on {date}: {root or "(before every record)"}\n' + '\n'.join(rows), {'date': date, 'world_commit': root, 'corpora': data}


def t_who_wrote(args: dict) -> tuple[str, dict]:
    date, path = date_arg(args.get('date')), path_arg(args.get('path', ''))
    by = (args.get('granularity') or 'word').lower()
    if run_law(law.text_on, date, path) is None:
        raise UserError(explain(date, path))
    if by == 'line':
        lines = run_law(law.blame_on, date, path)
        laws = sorted({a for a, _ in lines})
        return '\n'.join(f'{a} | {l}' for a, l in lines), {'date': date, 'path': path, 'lines': [{'law': a, 'text': l} for a, l in lines], 'laws': laws}
    runs = run_law(law.words_on, date, path)
    keys: dict[str, int] = {}
    for author, _ in runs:
        keys.setdefault(author, len(keys) + 1)
    shares: dict[str, int] = {}
    for author, text in runs:
        shares[author] = shares.get(author, 0) + len(text.split())
    legend = '\n'.join(f'[{n}] {a} ({shares[a]} words)' for a, n in keys.items())
    marked = ''.join(f'[{keys[a]}]{t}' for a, t in runs)
    return (f'{path} on {date}, each run of words marked with the law that wrote it:\n\n{marked}\n\n{legend}',
            {'date': date, 'path': path, 'runs': [{'law': a, 'text': t} for a, t in runs],
             'laws': [{'law': a, 'words': shares[a]} for a in keys]})


def t_compare_dates(args: dict) -> tuple[str, dict]:
    a, b, path = date_arg(args.get('date_a')), date_arg(args.get('date_b')), path_arg(args.get('path', ''))
    if a > b:
        a, b = b, a
    diff = run_law(law.diff_between, a, b, path)
    between = [h for h in run_law(law.history, path) if a < h['in_force'] <= b]
    corpus, _ = law.corpus_of(path)
    notes = law.caveats(a, corpus) + law.caveats(b, corpus)
    body = '\n'.join(l for l in diff.splitlines() if not l.startswith(('diff --git', 'index ', '--- ', '+++ ')))
    head_text = (f'{path}: {len(between)} change(s) took effect after {a} and on or before {b}'
                 + (': ' + '; '.join(f"{h['law']} ({h['in_force']})" for h in between) if between else '') + '.')
    legend = 'In the text, [-...-] was removed and {+...+} was added.'
    text = '\n'.join([head_text] + [f'Note: {n}' for n in notes] + ([legend, '', body] if body else ['No difference in the text.']))
    return text, {'path': path, 'date_a': a, 'date_b': b, 'changes': between, 'word_diff': body, 'caveats': notes}


def t_provision_history(args: dict) -> tuple[str, dict]:
    path = path_arg(args.get('path', ''))
    hist = run_law(law.history, path)
    if not hist:
        raise UserError(explain('9999-12-31', path))
    corpus, _ = law.corpus_of(path)
    for h in hist:
        h['sources'] = sources_of(corpus, h['commit'])
    lines = [f"{h['in_force']}  {h['law']}" + ''.join(f"  {k} {h[k]}" for k in ('enacted', 'published') if h[k])
             + f"  (commit {h['commit'][:10]})" + (f"  {h['sources'][0]}" if h['sources'] else '') for h in hist]
    return f'{path}: {len(hist)} change(s), oldest first. Dates: in force, then enacted or made, then published.\n' + '\n'.join(lines), {'path': path, 'changes': hist}


def t_laws_between(args: dict) -> tuple[str, dict]:
    a, b = date_arg(args.get('start')), date_arg(args.get('end'))
    if a > b:
        a, b = b, a
    scope = (args.get('jurisdiction') or '').strip().strip('/')
    rows = [e for e in law.timeline() if a <= e.in_force <= b and e.kind != 'documentation' and e.corpus.startswith(scope)]
    data = [{'in_force': e.in_force, 'corpus': e.corpus, 'law': e.law, 'summary': re.sub(r'^[^:]+:\s*', '', e.subject),
             'provisions_changed': changed_count(e.corpus, e.corpus_commit),
             'world_commit': e.commit, 'corpus_commit': e.corpus_commit} for e in rows]
    if not data:
        return f'No change took effect between {a} and {b}' + (f' in {scope}' if scope else '') + '.', {'changes': []}
    per_law: dict[str, int] = {}
    for d in data:
        per_law[d['law']] = per_law.get(d['law'], 0) + d['provisions_changed']
    top = sorted(per_law.items(), key=lambda kv: -kv[1])[:5]
    return ('\n'.join(f"{d['in_force']}  {d['corpus']}  {d['law']} ({d['provisions_changed']} provisions): {d['summary']}" for d in data)
            + '\nMost provisions changed: ' + '; '.join(f'{k} ({v})' for k, v in top)), {'changes': data, 'provisions_per_law': per_law}


@lru_cache(maxsize=4096)
def changed_count(corpus: str, sha: str) -> int:
    names = law.git('show', '--name-only', '--format=', sha, cwd=law.corpus_dir(corpus)).split('\n')
    return sum(1 for n in names if n.strip().endswith('.md') and not NOT_LAW.search(n.strip()))


VARIANTS = {'-': '(-|‐|‑|‒|–|—)', '–': '(-|‐|‑|‒|–|—)', '—': '(-|‐|‑|‒|–|—)', '"': '("|“|”|„)', '“': '("|“|”|„)',
            '”': '("|“|”|„)', "'": "('|‘|’)", '’': "('|‘|’)", '‘': "('|‘|’)", ' ': '[[:space:]]+'}


def loose_pattern(text: str) -> str:
    """A plain-text query as an extended regex in which dashes, quotes and spacing match their typographic forms."""
    return ''.join(VARIANTS.get(ch, re.sub(r'([.^$*+?()\[\]{}|\\])', r'\\\1', ch)) for ch in text)


def t_search_law(args: dict) -> tuple[str, dict]:
    query = args.get('query') or ''
    if not query.strip():
        raise UserError('Give words or a phrase to search for.')
    date = date_arg(args.get('date'))
    scope = (args.get('jurisdiction') or '').strip().strip('/')
    limit = num(args, 'max_results', 30, 200)
    root = law.root_on(date, law.timeline())
    if root is None:
        return f'Nothing is in the record on {date}.', {'results': []}
    # Official texts use typographic dashes and quotes ("COVID–19", “debtor”); plain searches match either form.
    pattern = query if args.get('regex') else loose_pattern(query)
    flags = ['-E']
    if not args.get('case_sensitive'):
        flags.append('-i')
    done = subprocess.run(['git', 'grep', '--recurse-submodules', '-n', '-I', *flags, '-e', pattern, root], cwd=ROOT,
                          capture_output=True, encoding='utf-8', errors='replace')
    if done.returncode not in (0, 1):
        raise UserError(f'Search failed: {done.stderr.strip()[:300]}')
    results, files = [], set()
    for line in done.stdout.splitlines():
        _, _, rest = line.partition(':')  # drop the commit
        path, _, rest = rest.partition(':')
        number, _, text = rest.partition(':')
        if NOT_LAW.search(path) or (scope and not path.startswith(scope)) or not path.endswith('.md'):
            continue
        if path.count('/') < 3:  # files at the top of a corpus or of the tree are documentation
            continue
        files.add(path)
        if len(results) < limit:
            results.append({'path': path, 'line': int(number) if number.isdigit() else None, 'text': text.strip()[:400]})
    notes = sorted({n for r in results for n in law.caveats(date, law.corpus_of(r['path'])[0])})
    summary = (f'{len(files)} provision(s) in force on {date} contain {query!r}' + (f' in {scope}' if scope else '')
               + (f'; showing {len(results)} line(s).' if results else '.'))
    lines = [summary] + [f'Note: {n}' for n in notes] + [f"{r['path']}:{r['line']}: {r['text']}" for r in results]
    named = [e for e in aliases() if any(query.lower() == n.lower() for n in e['names'])]
    for e in named:  # a popular name: the law never uses it, but we know where it lives
        lines.append(f"'{query}' is a popular name, not words of the law: it refers to {', '.join(e['paths'])}. {e.get('note', '')}")
    related = []
    if not results and not args.get('regex'):
        # The words may name a reform rather than appear in its text ("Schuldenbremse"); try the change notes.
        _, found = t_search_changes({'query': query, 'jurisdiction': scope, 'end': date, 'max_results': 10})
        related = found['changes']
        if related:
            lines.append(f'The text does not contain it, but {len(related)} change note(s) do; the provisions those changes touched may be what you want '
                         '(law_details lists them):')
            lines += [f"  {c['in_force']}  {c['corpus']}  {c['law']}: {c['line']}" for c in related]
        else:
            lines.append('Nor does any change note. Words that name a reform (a popular name) may not appear in the law; '
                         'try words the text itself would use, or find_provision.')
    return '\n'.join(lines), {'date': date, 'world_commit': root, 'provisions': sorted(files), 'results': results,
                              'caveats': notes, 'related_changes': related,
                              'popular_name_for': [p for e in named for p in e['paths']]}


def t_list_provisions(args: dict) -> tuple[str, dict]:
    """Browse a corpus: the provision files under a folder, with headings, as in force on a date."""
    prefix = law.norm((args.get('path') or '').strip())
    if not prefix:
        raise UserError('Give a corpus or a folder in one, for example us/federal/usc/title-11 or de/bund/grundgesetz.')
    corpus = next((c['path'] for c in law.manifest()['corpora'] if prefix == c['path'] or prefix.startswith(c['path'] + '/')), None)
    if corpus is None:
        raise UserError(f'{prefix} is not a corpus or inside one; see list_jurisdictions.')
    date = date_arg(args.get('date'))
    sha = law.pinned(law.root_on(date, law.timeline()), corpus)
    if sha is None:
        return f'{corpus} has nothing in force on {date}.', {'provisions': []}
    inner = prefix[len(corpus):].strip('/')
    limit = num(args, 'max_results', 200, 2000)
    items = provisions(corpus, sha, inner)
    folders = sorted({p[len(inner):].strip('/').split('/')[0] for p, _ in items if '/' in p[len(inner):].strip('/')})
    shown = items[:limit]
    text = (f'{len(items)} provision file(s) under {prefix} in force on {date}'
            + (f'; folders: {", ".join(folders[:40])}' if folders and len(items) > limit else '') + '.\n'
            + '\n'.join(f'{corpus}/{p}  {h}' for p, h in shown) + ('\n...' if len(items) > limit else ''))
    return text, {'date': date, 'corpus': corpus, 'count': len(items), 'folders': folders,
                  'provisions': [{'path': f'{corpus}/{p}', 'heading': h} for p, h in shown]}


def t_search_changes(args: dict) -> tuple[str, dict]:
    """Search what each change says about itself: commit messages, which name the law, its dates and its effect."""
    query = (args.get('query') or '').strip()
    if not query:
        raise UserError('Give words to look for in the record of changes, for example "temporary", "COVID" or "Bundesrat".')
    scope = (args.get('jurisdiction') or '').strip().strip('/')
    start, end = date_arg(args.get('start') or '0001-01-01'), date_arg(args.get('end') or '9999-12-31')
    limit = num(args, 'max_results', 30, 200)
    by_commit = {(e.corpus, e.corpus_commit): e for e in law.timeline()}
    found = []
    for c in law.manifest()['corpora']:
        if scope and not c['path'].startswith(scope):
            continue
        cwd = law.corpus_dir(c['path'])
        for sha in law.git('log', '--format=%H', '-i', '--fixed-strings', f'--grep={query}', cwd=cwd).split():
            e = by_commit.get((c['path'], sha))
            if e is None or e.kind == 'documentation' or not (start <= e.in_force <= end):
                continue
            body = law.git('show', '-s', '--format=%B', sha, cwd=cwd)
            hit = next((l.strip() for l in body.splitlines() if query.lower() in l.lower()), '')
            found.append({'in_force': e.in_force, 'corpus': c['path'], 'law': e.law, 'commit': sha, 'line': hit[:300]})
    found.sort(key=lambda f: f['in_force'])
    if not found:
        return f'No change in the record mentions {query!r}.', {'changes': []}
    return (f'{len(found)} change(s) mention {query!r}:\n'
            + '\n'.join(f"{f['in_force']}  {f['corpus']}  {f['law']}: {f['line']}" for f in found[:limit])), {'changes': found[:limit]}


def t_phrase_history(args: dict) -> tuple[str, dict]:
    """When words came into the law and when they left it, at any date: every change whose added or removed text
    contains them (git's pickaxe search, -G)."""
    query = (args.get('query') or '').strip()
    if not query:
        raise UserError('Give words to trace, for example "COVID-19" or "7,500,000".')
    scope = (args.get('jurisdiction') or '').strip().strip('/')
    limit = num(args, 'max_results', 40, 300)
    pattern = query if args.get('regex') else loose_pattern(query)
    by_commit = {(e.corpus, e.corpus_commit): e for e in law.timeline()}
    found = []
    for c in law.manifest()['corpora']:
        if scope and not c['path'].startswith(scope):
            continue
        cwd = law.corpus_dir(c['path'])
        out = law.git('log', '--format=@%H', '--name-only', '-i', '--extended-regexp', f'-G{pattern}', '--', '*.md', cwd=cwd)
        sha = None
        for line in out.splitlines():
            if line.startswith('@'):
                sha = line[1:]
                continue
            name = line.strip()
            e = by_commit.get((c['path'], sha))
            if not name or e is None or e.kind == 'documentation' or NOT_LAW.search(name):
                continue
            diff = law.git('show', '--format=', '-U0', '--no-color', sha, '--', name, cwd=cwd)
            rx = re.compile(pattern, re.I)
            added = sum(1 for l in diff.splitlines() if l.startswith('+') and not l.startswith('+++') and rx.search(l))
            removed = sum(1 for l in diff.splitlines() if l.startswith('-') and not l.startswith('---') and rx.search(l))
            if added == removed:
                continue  # the words are on a line that changed for another reason
            found.append({'in_force': e.in_force, 'corpus': c['path'], 'law': e.law, 'path': f"{c['path']}/{name}",
                          'effect': 'added' if added > removed else 'removed', 'lines_added': added, 'lines_removed': removed})
    found.sort(key=lambda f: (f['in_force'], f['path']))
    if not found:
        return f'No change in the record added or removed text containing {query!r}.', {'changes': []}
    return (f'{len(found)} change(s) added or removed text containing {query!r}, oldest first:\n'
            + '\n'.join(f"{f['in_force']}  {f['effect']:<7}  {f['path']}  by {f['law']}" for f in found[:limit])), {'changes': found[:limit]}


def t_law_details(args: dict) -> tuple[str, dict]:
    """The full record of one law's change: its commit message with every trailer, and the provisions it changed."""
    corpus = (args.get('corpus') or '').strip().strip('/')
    law_name = (args.get('law') or '').strip()
    commit = (args.get('commit') or '').strip()
    corpora = [c['path'] for c in law.manifest()['corpora'] if not corpus or c['path'].startswith(corpus)]
    if not corpora:
        raise UserError(f'No corpus {corpus!r}; see list_jurisdictions.')
    if not law_name and not commit:
        raise UserError('Give a law (for example "Pub. L. 117-151", "36. Änderung", "S.I. 2020/471") or a commit.')
    found = []
    for c in corpora:
        cwd = law.corpus_dir(c)
        if commit:
            ok = subprocess.run(['git', 'cat-file', '-e', f'{commit}^{{commit}}'], cwd=cwd, capture_output=True).returncode == 0
            shas = [law.git('rev-parse', commit, cwd=cwd).strip()] if ok else []
        else:
            shas = law.git('log', '--format=%H', f'--author={law_name}', '--fixed-strings', '-i', cwd=cwd).split()
        for sha in shas[:10]:
            msg = law.git('show', '-s', '--format=%an%x1f%B', sha, cwd=cwd)
            author, _, body = msg.partition('\x1f')
            changed = law.git('show', '--name-status', '--format=', sha, cwd=cwd).split('\n')
            files = [f"{c}/{l.split(chr(9))[-1]}" for l in changed if l.strip() and not NOT_LAW.search(l.split('\t')[-1])]
            found.append({'corpus': c, 'commit': sha, 'law': author, 'message': body.strip(), 'trailers': law.trailers(body), 'provisions': files})
    if not found:
        raise UserError(f'No change in the record by {law_name or commit!r}. Use laws_between to list laws by date.')
    cap = max(500, num(args, 'max_message_chars', 3000, 50000))
    text = '\n\n'.join(f"=== {f['law']} ({f['corpus']}, commit {f['commit'][:10]}, {len(f['provisions'])} provisions)\n"
                       + (f['message'][:cap] + (f'\n[... {len(f["message"]) - cap} more characters; raise max_message_chars]' if len(f['message']) > cap else ''))
                       + '\n\nProvisions changed: ' + (', '.join(f['provisions']) or 'none (documentation only)') for f in found)
    return text, {'changes': found}


def t_changes_between(args: dict) -> tuple[str, dict]:
    """Every provision whose text differs between two dates, in every corpus, with the laws in between."""
    a, b = date_arg(args.get('date_a')), date_arg(args.get('date_b'))
    if a > b:
        a, b = b, a
    scope = (args.get('jurisdiction') or '').strip().strip('/')
    events = law.timeline()
    ra, rb = law.root_on(a, events), law.root_on(b, events)
    out, rows = [], []
    for c in law.manifest()['corpora']:
        if scope and not c['path'].startswith(scope):
            continue
        pa, pb = law.pinned(ra, c['path']), law.pinned(rb, c['path'])
        if pa == pb:
            continue
        names = law.git('diff', '--name-status', pa or law.EMPTY_TREE, pb, cwd=law.corpus_dir(c['path'])).splitlines()
        changed = [(l.split('\t')[0], l.split('\t')[-1]) for l in names if l.strip() and not NOT_LAW.search(l.split('\t')[-1])]
        laws = [e.law for e in events if e.corpus == c['path'] and a < e.in_force <= b and e.kind != 'documentation']
        kinds = {'A': 'added', 'M': 'changed', 'D': 'removed'}
        rows.append({'corpus': c['path'], 'laws': laws, 'provisions': [{'path': f"{c['path']}/{p}", 'change': kinds.get(s[0], s)} for s, p in changed]})
        out.append(f"{c['path']}: {len(changed)} provision(s), by {len(laws)} change(s)"
                   + (f" ({'; '.join(laws[:8])}{'; ...' if len(laws) > 8 else ''})" if laws else '') + '\n'
                   + '\n'.join(f"  {kinds.get(s[0], s)}: {c['path']}/{p}" for s, p in changed[:60])
                   + ('\n  ...' if len(changed) > 60 else ''))
    if not rows:
        return f'Nothing changed between {a} and {b}' + (f' in {scope}' if scope else '') + '.', {'corpora': []}
    return f'Changes after {a}, up to and including {b}:\n' + '\n'.join(out), {'date_a': a, 'date_b': b, 'corpora': rows}


DATE = {'type': 'string', 'description': 'An in-force date, YYYY-MM-DD, or "today". Defaults to today.'}
PATH = {'type': 'string', 'description': 'A provision file, for example us/federal/usc/title-11/1182.md, de/bund/grundgesetz/artikel/016a.md or gb/uk/send/uksi/2014/1530/regulation/13.md. Use find_provision to look one up.'}
SCOPE = {'type': 'string', 'description': 'Optional jurisdiction prefix, for example "de", "us/federal" or "gb/uk/send".'}
RO = {'readOnlyHint': True, 'idempotentHint': True, 'openWorldHint': False}

TOOLS = [
    ('list_jurisdictions', 'List every jurisdiction and body of law in the tree, with how far each record reaches and an example path. Start here.',
     {}, [], t_list_jurisdictions),
    ('find_provision', 'Find the file path of a provision by its number ("1182", "Art. 16a", "reg 13") or words from its heading ("debtor", "Asylrecht").',
     {'query': {'type': 'string', 'description': 'A section, article or regulation number, or heading words.'}, 'jurisdiction': SCOPE,
      'max_results': {'type': 'integer', 'description': 'At most this many (default 15).'}}, ['query'], t_find_provision),
    ('read_law', 'The text of a provision as it was in force on a date, with the law that last changed it, the next change, and any limit of the record that applies.',
     {'path': PATH, 'date': DATE}, ['path'], t_read_law),
    ('world_on_date', 'What every jurisdiction in the tree looked like on one date: the last change in force in each, and the next.',
     {'date': DATE}, [], t_world_on_date),
    ('who_wrote', 'Which law wrote each word (or each line) of a provision as it stood on a date, with a count of words per law.',
     {'path': PATH, 'date': DATE, 'granularity': {'type': 'string', 'enum': ['word', 'line'], 'description': 'word (default) or line.'}}, ['path'], t_who_wrote),
    ('compare_dates', 'How a provision changed between two dates: a word-level diff and the laws that took effect in between.',
     {'path': PATH, 'date_a': DATE, 'date_b': DATE}, ['path', 'date_a', 'date_b'], t_compare_dates),
    ('provision_history', 'Every law that changed a provision, oldest first, with its in-force, enacted or made, and published dates.',
     {'path': PATH}, ['path'], t_provision_history),
    ('laws_between', 'Every law that took effect between two dates, across all jurisdictions or one, in the order they took effect.',
     {'start': DATE, 'end': DATE, 'jurisdiction': SCOPE}, ['start', 'end'], t_laws_between),
    ('search_law', 'Search the text of all the law in force on a date, across every jurisdiction or one. Plain text by default.',
     {'query': {'type': 'string', 'description': 'Words or a phrase; a regular expression if regex is true.'}, 'date': DATE, 'jurisdiction': SCOPE,
      'regex': {'type': 'boolean'}, 'case_sensitive': {'type': 'boolean'}, 'max_results': {'type': 'integer', 'description': 'Lines to return (default 30).'}},
     ['query'], t_search_law),
    ('changes_between', 'Every provision whose text differs between two dates, in every jurisdiction or one, with the laws that changed them.',
     {'date_a': DATE, 'date_b': DATE, 'jurisdiction': SCOPE}, ['date_a', 'date_b'], t_changes_between),
    ('list_provisions', 'Browse a corpus: the provision files under a corpus or folder (for example us/federal/usc/title-11), with headings, as in force on a date.',
     {'path': {'type': 'string', 'description': 'A corpus or a folder inside one.'}, 'date': DATE,
      'max_results': {'type': 'integer', 'description': 'At most this many (default 200).'}}, ['path'], t_list_provisions),
    ('search_changes', 'Search the record of changes (each commit message: the law, its dates, what it did) rather than the text of the law. For example "temporary", "COVID", "Bundesrat".',
     {'query': {'type': 'string'}, 'jurisdiction': SCOPE, 'start': DATE, 'end': DATE,
      'max_results': {'type': 'integer', 'description': 'At most this many (default 30).'}}, ['query'], t_search_changes),
    ('phrase_history', 'When words came into the law and when they left it, at any date and in every jurisdiction: each change whose added or removed text contains them. Use it for things no longer in force (for example "COVID" in the Grundgesetz).',
     {'query': {'type': 'string'}, 'jurisdiction': SCOPE, 'regex': {'type': 'boolean'},
      'max_results': {'type': 'integer', 'description': 'At most this many (default 40).'}}, ['query'], t_phrase_history),
    ('applies_to_case','For a case commenced on one date, which later changes to a provision reach it (from any scope the record holds, such as "cases commenced on or after"), and the text that applies to it.',
     {'path': PATH, 'commenced': {'type': 'string', 'description': 'The day the case (or matter) was commenced, YYYY-MM-DD.'}, 'date': DATE},
     ['path', 'commenced'], t_applies_to_case),
    ('law_details', 'The full record of a law\'s change: its commit message with every trailer (enacted, in force, published, sources, scope) and the provisions it changed.',
     {'law': {'type': 'string', 'description': 'The law as it appears as author, for example "Pub. L. 117-151", "36. Änderung", "S.I. 2020/471".'},
      'commit': {'type': 'string', 'description': 'Or a corpus commit hash, for example from provision_history.'}, 'corpus': SCOPE,
      'max_message_chars': {'type': 'integer', 'description': 'Cut each commit message at this many characters (default 3000).'}}, [], t_law_details),
]
HANDLERS = {name: fn for name, _, _, _, fn in TOOLS}

INSTRUCTIONS = (
    'Global law: the law of several jurisdictions as one git history, each change dated by the day it took effect and '
    'credited to the law that made it. Start with list_jurisdictions, then find_provision for a path, then read_law. '
    'Coverage is partial: each corpus holds only the law its description names (for example some US Code titles, or '
    'selected UK provisions), over a stated period, so "nothing found" means nothing in the record, not nothing in the '
    'law. Every answer states the limits of its record (where a record starts or ends); pass them on to the user. '
    'Dates are the dates each record gives a change: the day it took effect, or for a first version the day it was '
    'enacted or made. The text is copied from official publishers; for anything that matters, read the original.'
)


def tool_list() -> list[dict]:
    return [{'name': n, 'title': n.replace('_', ' ').capitalize(), 'description': d,
             'inputSchema': {'type': 'object', 'properties': p, 'required': r, 'additionalProperties': False},
             'annotations': RO} for n, d, p, r, _ in TOOLS]


def resources() -> list[dict]:
    return [{'uri': f'global-law://{name}', 'name': name, 'mimeType': mime, 'description': desc}
            for name, mime, desc in (('README.md', 'text/markdown', 'How the tree is arranged and read'),
                                     ('REPRODUCE.md', 'text/markdown', 'How it was built and how to rebuild it'),
                                     ('CHANGELOG.md', 'text/markdown', 'What has changed and what is open'),
                                     ('manifest.json', 'application/json', 'Every corpus and its coverage'))]


def handle(msg: dict) -> dict | None:
    method, mid, params = msg.get('method'), msg.get('id'), msg.get('params') or {}
    if mid is None:  # a notification: nothing to answer
        return None
    try:
        if method == 'initialize':
            asked = params.get('protocolVersion')
            result = {'protocolVersion': asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
                      'capabilities': {'tools': {'listChanged': False}, 'resources': {}},
                      'serverInfo': SERVER, 'instructions': INSTRUCTIONS}
        elif method == 'ping':
            result = {}
        elif method == 'tools/list':
            result = {'tools': tool_list()}
        elif method == 'resources/list':
            result = {'resources': resources()}
        elif method == 'resources/read':
            uri = params.get('uri', '')
            name = uri.removeprefix('global-law://')
            match = next((r for r in resources() if r['uri'] == uri), None)
            if not match:
                return error(mid, -32602, f'Unknown resource {uri}')
            result = {'contents': [{'uri': uri, 'mimeType': match['mimeType'], 'text': law.git('show', f'HEAD:{name}')}]}
        elif method == 'prompts/list':
            result = {'prompts': []}
        elif method == 'tools/call':
            name, args = params.get('name'), params.get('arguments') or {}
            if name not in HANDLERS:
                return error(mid, -32602, f'Unknown tool {name}')
            try:
                text, data = HANDLERS[name](args)
                result = {'content': [{'type': 'text', 'text': text}], 'structuredContent': data, 'isError': False}
            except UserError as e:
                result = {'content': [{'type': 'text', 'text': str(e)}], 'isError': True}
        else:
            return error(mid, -32601, f'Method not found: {method}')
        return {'jsonrpc': '2.0', 'id': mid, 'result': result}
    except Exception as e:  # never let one request take the server down
        traceback.print_exc(file=sys.stderr)
        return {'jsonrpc': '2.0', 'id': mid, 'result': {'content': [{'type': 'text', 'text': f'Internal error: {e}'}], 'isError': True}} \
            if method == 'tools/call' else error(mid, -32603, f'Internal error: {e}')


def error(mid, code: int, message: str) -> dict:
    return {'jsonrpc': '2.0', 'id': mid, 'error': {'code': code, 'message': message}}


def main() -> None:
    sys.stdin.reconfigure(encoding='utf-8')
    out = sys.stdout.buffer
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            reply = error(None, -32700, 'Parse error')
        else:
            batch = msg if isinstance(msg, list) else [msg]
            replies = [r for r in (handle(m) for m in batch if isinstance(m, dict)) if r is not None]
            reply = (replies if isinstance(msg, list) else (replies[0] if replies else None))
        if reply is not None:
            out.write((json.dumps(reply, ensure_ascii=False) + '\n').encode('utf-8'))
            out.flush()


if __name__ == '__main__':
    main()
