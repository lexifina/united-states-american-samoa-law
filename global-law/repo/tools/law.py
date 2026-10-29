#!/usr/bin/env python3
"""Read the global law tree on any date. Standard library only.

Every root commit is one law taking effect somewhere, in the order the changes took force, and pins every corpus at
that moment. So one root commit is the state of all the law in the tree, and the tools below never check anything
out: they read the pinned corpus commits straight from the submodules.

  python tools/law.py world 2022-05-01                     what every corpus looked like that day
  python tools/law.py show 2022-05-01 us/federal/usc/title-11/1182.md
  python tools/law.py blame 2022-07-01 us/federal/usc/title-11/1182.md
  python tools/law.py words 2022-07-01 us/federal/usc/title-11/1182.md   which law wrote each word
  python tools/law.py diff 2022-05-01 2022-07-01 us/federal/usc/title-11/1182.md
  python tools/law.py log us/federal/usc/title-11/1182.md   every law that changed a file, with its dates
  python tools/law.py laws 1990-01-01 1990-12-31 [de]       laws that took force in a window, by jurisdiction

Run `git submodule update --init` once first. Dates are in-force dates read from each commit's In-force trailer,
so dates before 1970 work even though git cannot store them as commit dates.
"""
from __future__ import annotations

import difflib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def git(*args: str, cwd: Path = ROOT, check: bool = True) -> str:
    done = subprocess.run(['git', *args], cwd=cwd, capture_output=True, encoding='utf-8')
    if check and done.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {done.stderr.strip()}")
    return done.stdout


def manifest() -> dict:
    return json.loads(git('show', 'HEAD:manifest.json'))


@dataclass
class Event:
    commit: str
    corpus: str
    corpus_commit: str
    law: str
    in_force: str
    kind: str
    subject: str


def trailers(body: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in body.splitlines():
        key, sep, value = line.partition(': ')
        if sep and key and ' ' not in key and key[0].isupper():
            out.setdefault(key, value.strip())
    return out


def timeline() -> list[Event]:
    """Root commits that move a corpus, oldest first (first parent only)."""
    raw = git('log', '--first-parent', '--reverse', '--format=%H%x1f%s%x1f%B%x1e')
    events = []
    for record in raw.split('\x1e'):
        if not record.strip():
            continue
        commit, subject, body = record.strip('\n').split('\x1f', 2)
        t = trailers(body)
        if 'Corpus' in t:
            events.append(Event(commit, t['Corpus'], t['Corpus-commit'], t.get('Law', ''), t['In-force'], t.get('Kind', 'law'), subject))
    return events


def root_on(date: str, events: list[Event] | None = None) -> str | None:
    """The last root commit whose change was in force on `date`. The timeline is in in-force order, so this is a
    prefix: the first event after the date ends it."""
    found = None
    for event in events if events is not None else timeline():
        if event.in_force > date:
            break
        found = event.commit
    return found


def corpus_of(path: str) -> tuple[str, str]:
    for corpus in sorted(manifest()['corpora'], key=lambda c: -len(c['path'])):
        prefix = corpus['path'] + '/'
        if path.startswith(prefix):
            return corpus['path'], path[len(prefix):]
    raise SystemExit(f'{path} is not inside a corpus; see manifest.json')


def pinned(root_commit: str | None, corpus: str) -> str | None:
    if root_commit is None:
        return None
    line = git('ls-tree', root_commit, '--', corpus).split()
    return line[2] if len(line) >= 3 and line[1] == 'commit' else None


def corpus_dir(corpus: str) -> Path:
    path = ROOT / corpus
    if not (path / '.git').exists():
        raise SystemExit(f'{corpus} is not checked out; run: git submodule update --init')
    return path


def text_on(date: str, path: str) -> str | None:
    corpus, rel = corpus_of(path)
    sha = pinned(root_on(date), corpus)
    if sha is None:
        return None
    done = subprocess.run(['git', 'show', f'{sha}:{rel}'], cwd=corpus_dir(corpus), capture_output=True, encoding='utf-8')
    return done.stdout if done.returncode == 0 else None


def blame_on(date: str, path: str) -> list[tuple[str, str]]:
    """(law, line) for every line of the file as it stood on `date`."""
    corpus, rel = corpus_of(path)
    sha = pinned(root_on(date), corpus)
    if sha is None:
        return []
    out, law = [], ''
    for line in git('blame', '--line-porcelain', sha, '--', rel, cwd=corpus_dir(corpus)).splitlines():
        if line.startswith('author '):
            law = line[7:]
        elif line.startswith('\t'):
            out.append((law, line[1:]))
    return out


def _credit_words(old: list[str], old_authors: list[str], new: list[str], law: str) -> list[str]:
    ops = difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes()
    credited: list[str] = []
    for i, (op, a0, a1, b0, b1) in enumerate(ops):
        # A few common words ("means a") left between two rewritten stretches were rewritten too.
        island = (op == 'equal' and 0 < i < len(ops) - 1 and ops[i - 1][0] != 'equal' and ops[i + 1][0] != 'equal'
                  and sum(not t.isspace() for t in new[b0:b1]) < 3)
        credited += [law] * (b1 - b0) if op != 'equal' or island else old_authors[a0:a1]
    return credited


def words_on(date: str, path: str) -> list[tuple[str, str]]:
    """(law, run of text) for the file as it stood on `date`, credited word by word. git blame credits whole lines;
    here each version of the file is compared with the one before, word by word, and words that survive keep the law
    that first wrote them. Text moved within the file usually keeps its author; text that is rewritten in place is
    credited to the law that rewrote it. Unchanged lines are matched first, so only changed stretches are compared
    word by word, which keeps long sections fast."""
    corpus, rel = corpus_of(path)
    sha = pinned(root_on(date), corpus)
    if sha is None:
        return []
    cwd = corpus_dir(corpus)
    lines: list[str] = []
    authors: list[list[str]] = []  # per line, one law per token
    for record in git('log', '--reverse', '--format=%H%x1f%an', sha, '--', rel, cwd=cwd).splitlines():
        commit, law = record.split('\x1f', 1)
        shown = subprocess.run(['git', 'show', f'{commit}:{rel}'], cwd=cwd, capture_output=True, encoding='utf-8')
        new_lines = shown.stdout.splitlines(keepends=True) if shown.returncode == 0 else []
        new_authors: list[list[str]] = []
        for op, a0, a1, b0, b1 in difflib.SequenceMatcher(None, lines, new_lines, autojunk=False).get_opcodes():
            if op == 'equal':
                new_authors += authors[a0:a1]
                continue
            old_block = [re.findall(r'\s+|\S+', line) for line in lines[a0:a1]]
            block = [re.findall(r'\s+|\S+', line) for line in new_lines[b0:b1]]
            old_tokens = [t for line in old_block for t in line]
            if len(old_tokens) * sum(map(len, block)) <= 400_000:
                old_credit = [a for line_authors in authors[a0:a1] for a in line_authors]
                credit = _credit_words(old_tokens, old_credit, [t for line in block for t in line], law)
                for line in block:
                    new_authors.append(credit[:len(line)])
                    credit = credit[len(line):]
            else:
                # A large rewrite: pair each new line with the most similar old line and compare only those two,
                # which keeps a whole-section rewrite (17 U.S.C. §115 in 2018) to seconds rather than minutes.
                for line in block:
                    best, score = None, 0.0
                    for j, old in enumerate(old_block):
                        s = difflib.SequenceMatcher(None, old, line, autojunk=False).quick_ratio()
                        if s > score:
                            best, score = j, s
                    if best is not None and score >= 0.6:
                        new_authors.append(_credit_words(old_block[best], authors[a0 + best], line, law))
                    else:
                        new_authors.append([law] * len(line))
        lines, authors = new_lines, new_authors
    tokens = [t for line in lines for t in re.findall(r'\s+|\S+', line)]
    flat = [a for line_authors in authors for a in line_authors]
    runs: list[tuple[str, str]] = []
    for law, token in zip(flat, tokens):
        if token.isspace() and runs:
            law = runs[-1][0]  # spaces never start a new run
        if runs and runs[-1][0] == law:
            runs[-1] = (law, runs[-1][1] + token)
        else:
            runs.append((law, token))
    return runs


EMPTY_TREE = '4b825dc642cb6eb9a060e54bf8d69288fbee4904'  # git's empty tree: "nothing yet", before a record starts


def diff_between(date_a: str, date_b: str, path: str) -> str:
    corpus, rel = corpus_of(path)
    events = timeline()
    a, b = pinned(root_on(date_a, events), corpus), pinned(root_on(date_b, events), corpus)
    if a == b:
        return ''
    return git('diff', '--word-diff=plain', a or EMPTY_TREE, b or EMPTY_TREE, '--', rel, cwd=corpus_dir(corpus))


def corpus_info(corpus: str) -> dict:
    return next(c for c in manifest()['corpora'] if c['path'] == corpus)


def caveats(date: str, corpus: str, events: list[Event] | None = None) -> list[str]:
    """What a reader must know about a date in one corpus: before its record starts, or after it ends."""
    own = [e for e in (events if events is not None else timeline()) if e.corpus == corpus and e.kind != 'documentation']
    info = corpus_info(corpus)
    out = []
    if own and date < own[0].in_force:
        out.append(f"{corpus}: the record starts on {own[0].in_force} ({own[0].law}); nothing earlier is in it.")
    if info.get('record_to') and date > info['record_to']:
        out.append(f"{corpus}: the record runs to {info['record_to']}. {info.get('record_note', '')}".rstrip())
    return out


def explain_missing(date: str, path: str) -> str:
    """Why there is no text: a mistyped path, before the record, not yet in force, or repealed."""
    corpus, rel = corpus_of(path)
    cwd = corpus_dir(corpus)
    if not git('log', '-1', '--format=%H', 'HEAD', '--', rel, cwd=cwd).strip():
        names = git('ls-tree', '-r', '--name-only', 'HEAD', cwd=cwd).split()
        close = difflib.get_close_matches(rel, names, n=3, cutoff=0.6)
        hint = f" Did you mean {', '.join(f'{corpus}/{c}' for c in close)}?" if close else ''
        return f'{path} is not in this record at any date.{hint}'
    h = history(path)
    if not h:
        return f'{path} has no dated change in the record.'
    if date < h[0]['in_force']:
        return f"{path} was not yet in force on {date}. It first appears on {h[0]['in_force']} ({h[0]['law']})."
    gone = [x for x in h if x['in_force'] <= date][-1]
    back = next((x for x in h if x['in_force'] > date), None)
    again = f" It is in force again from {back['in_force']} ({back['law']})." if back else ''
    return f"{path} was not in force on {date}: it was removed on {gone['in_force']} ({gone['law']}).{again}"


USAGE = {'world': 1, 'show': 2, 'blame': 2, 'words': 2, 'diff': 3, 'log': 1, 'laws': 2}


def day(value: str) -> str:
    """An ISO date, checked. "today" is allowed; times are dropped."""
    import datetime as dt
    if value == 'today':
        return dt.date.today().isoformat()
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}(T.*)?', value):
        try:
            return dt.date.fromisoformat(value[:10]).isoformat()
        except ValueError:
            pass
    raise SystemExit(f'Not a date: {value!r}. Use YYYY-MM-DD, for example 2022-05-01.')


def norm(path: str) -> str:
    return path.replace('\\', '/').removeprefix('./').strip('/')


ENACTED = ('Enacted', 'Made', 'Beschlossen')
PUBLISHED = ('Printed-in', 'Verkuendet', 'Verkündet')  # Germany's key is ASCII since its 2026-10-28 rebuild


def history(path: str) -> list[dict]:
    """Every law that changed a file, oldest first, with its dates: the reader's "follow" list."""
    corpus, rel = corpus_of(path)
    trailer = next(c['in_force_trailer'] for c in manifest()['corpora'] if c['path'] == corpus)
    raw = git('log', '--reverse', '--format=%H%x1f%an%x1f%B%x1e', '--', rel, cwd=corpus_dir(corpus))
    out = []
    for record in raw.split('\x1e'):
        if not record.strip():
            continue
        sha, author, body = record.strip('\n').split('\x1f', 2)
        t = trailers(body)
        if trailer not in t:
            continue  # documentation and the starting edition carry no in-force date
        out.append({'commit': sha, 'law': author, 'in_force': t[trailer],
                    'enacted': next((t[k] for k in ENACTED if k in t), None),
                    'published': next((t[k] for k in PUBLISHED if k in t), None)})
    return out


def main(argv: list[str]) -> None:
    if not argv:
        raise SystemExit(__doc__)
    sys.stdout.reconfigure(encoding='utf-8')  # law names and texts are not ASCII; Windows consoles default to cp1252
    sys.stderr.reconfigure(encoding='utf-8')
    command, args = argv[0], argv[1:]
    if command not in USAGE or len(args) < USAGE[command]:
        raise SystemExit(__doc__)
    # Dates are checked and paths accept ./ and Windows backslashes; caveats go to stderr so the text stays clean.
    if command in ('world', 'show', 'blame', 'words', 'laws'):
        args[0] = day(args[0])
    if command in ('diff', 'laws'):
        args[1] = day(args[1])
    if command in ('show', 'blame', 'words'):
        args[1] = norm(args[1])
    if command == 'diff':
        args[0], args[2] = day(args[0]), norm(args[2])
    if command == 'log':
        args[0] = norm(args[0])
    note = lambda lines: [print(f'Note: {line}', file=sys.stderr) for line in lines]  # noqa: E731
    if command == 'world':
        events = timeline()
        commit = root_on(args[0], events)
        print(f'Root commit on {args[0]}: {commit or "(nothing in force yet)"}')
        for corpus in manifest()['corpora']:
            last = [e for e in events if e.corpus == corpus['path'] and e.in_force <= args[0] and e.kind != 'documentation']
            state = f'{last[-1].law}, in force {last[-1].in_force}' if last else 'not yet in the record'
            print(f"  {corpus['path']:<24} {state}")
        note(c for corpus in manifest()['corpora'] for c in caveats(args[0], corpus['path'], events) if 'runs to' in c)
    elif command in ('show', 'blame', 'words'):
        corpus, _ = corpus_of(args[1])
        note(caveats(args[0], corpus))
        if text_on(args[0], args[1]) is None:
            raise SystemExit(explain_missing(args[0], args[1]))
        if command == 'show':
            print(text_on(args[0], args[1]), end='')
        elif command == 'blame':
            for law, line in blame_on(args[0], args[1]):
                print(f'{law[:60]:<60} | {line}')
        else:
            runs = words_on(args[0], args[1])
            keys: dict[str, int] = {}
            for law, _ in runs:
                keys.setdefault(law, len(keys) + 1)
            print(''.join(f'[{keys[law]}]{text}' for law, text in runs))
            print()
            for law, n in keys.items():
                print(f'[{n}] {law}')
    elif command == 'diff':
        corpus, _ = corpus_of(args[2])
        note(caveats(args[0], corpus) + caveats(args[1], corpus))
        print(diff_between(args[0], args[1], args[2]) or 'No change between those dates.')
    elif command == 'log':
        if not history(args[0]):
            raise SystemExit(explain_missing('9999-12-31', args[0]))
        for h in history(args[0]):
            dates = '; '.join(f'{k} {h[k]}' for k in ('enacted', 'published') if h[k])
            print(f"in force {h['in_force']}  {h['law']}" + (f'  ({dates})' if dates else ''))
    elif command == 'laws':
        if args[0] > args[1]:
            args[0], args[1] = args[1], args[0]
        prefix = args[2] if len(args) > 2 else ''
        for e in timeline():
            if args[0] <= e.in_force <= args[1] and e.corpus.startswith(prefix) and e.kind != 'documentation':
                print(f'{e.in_force}  {e.corpus:<24} {e.law}')
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
