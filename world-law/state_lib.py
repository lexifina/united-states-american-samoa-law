"""Shared helper for the US-state first builds: polite cached fetching, text normalising, corpus assembly.

Each state folder keeps its own copy (the builder ships a folder's scripts in the repository's tools/ so the repo can
rebuild itself). No model output is ever treated as legal text.
"""
import hashlib
import json
import os
import re
import subprocess
import threading
import time

_lock = threading.Lock()
_last = [0.0]


class Fetcher:
    """curl, cached by the sha256 of the URL, one request log line per request, at most `rate` requests a second."""

    def __init__(self, folder, ua, delay=0.5):
        self.cache = os.path.join(folder, '.cache')
        os.makedirs(os.path.join(self.cache, 'raw'), exist_ok=True)
        self.ua = ua
        self.delay = delay
        self.log = os.path.join(self.cache, 'requests.jsonl')

    def path(self, url):
        return os.path.join(self.cache, 'raw', hashlib.sha256(url.encode()).hexdigest())

    def cached(self, url):
        p = self.path(url)
        return open(p, 'rb').read() if os.path.exists(p) else None

    def get(self, url, refresh=False, ok=()):
        """bytes, or None for a 404 (cached as a negative answer)."""
        p = self.path(url)
        if not refresh and os.path.exists(p):
            return open(p, 'rb').read()
        if not refresh and os.path.exists(p + '.404'):
            return None
        code = ''
        for i in range(5):
            with _lock:
                wait = self.delay - (time.time() - _last[0])
                if wait > 0:
                    time.sleep(wait)
                _last[0] = time.time()
            r = subprocess.run(['curl', '-sS', '-L', '--compressed', '-m', '120', '-A', self.ua, '-o', p + '.tmp',
                                '-w', '%{http_code}', url], capture_output=True)
            code = r.stdout.decode().strip()
            with _lock:
                with open(self.log, 'a', encoding='utf-8') as f:
                    f.write(json.dumps({'url': url, 'status': code, 'at': time.strftime('%Y-%m-%dT%H:%M:%S')}) + '\n')
            if code == '200' or code in ok:
                os.replace(p + '.tmp', p)
                return open(p, 'rb').read()
            if code in ('404', '410'):
                if os.path.exists(p + '.tmp'):
                    os.remove(p + '.tmp')
                open(p + '.404', 'w').close()
                return None
            time.sleep(4 * (i + 1))
        raise RuntimeError(f'{url}: {code} {r.stderr[:200]!r}')


def sha(b):
    return hashlib.sha256(b).hexdigest()


def norm(s):
    """Typesetting normalised once: NBSP to space, runs of spaces collapsed, curly quotes and dashes to one form."""
    s = re.sub('[ -   　]', ' ', s)
    s = s.replace(' ', ' ').replace('​', '').replace('﻿', '').replace('­', '')
    s = s.replace('‘', "'").replace('’', "'").replace('“', '"').replace('”', '"')
    s = s.replace('–', '-').replace('—', '-').replace('‒', '-').replace('‑', '-')
    return re.sub(r'\s+', ' ', s).strip()


def key(prefix, label, width=4):
    """sec-0601a from '601A': lowercase ASCII, every number zero-padded so keys sort naturally."""
    k = re.sub(r'[^a-z0-9]+', '-', label.lower()).strip('-')
    k = re.sub(r'\d+', lambda m: m.group(0).zfill(width), k)
    return f'{prefix}-{k}' if prefix else k


def text_of(lines):
    ls = [norm(l) for l in lines]
    ls = [l for l in ls if l]
    return '\n'.join(ls) + '\n' if ls else ''


class Act:
    def __init__(self, slug, short, title, url, from_date, source_url=None, sha256=None, note=None):
        self.slug, self.short, self.title, self.url = slug, short, title, url
        self.from_date, self.source_url, self.sha256, self.note = from_date, source_url or url, sha256, note
        self.units = {}

    def add(self, k, label, kind, text):
        if not text.strip():
            return
        base, n = k, 2
        while k in self.units:  # two sections that print the same number: keep both, in order
            k = f'{base}-dup{n}'
            n += 1
        self.units[k] = {'label': label, 'kind': kind, 'text': text}

    def as_dict(self):
        v = {'from': self.from_date, 'source_url': self.source_url, 'units': dict(sorted(self.units.items()))}
        if self.sha256:
            v['sha256'] = self.sha256
        if self.note:
            v['note'] = self.note
        return {'slug': self.slug, 'short': self.short, 'title': self.title, 'url': self.url, 'first_law': None,
                'earlier_laws': [], 'versions': [v]}


def write_corpus(folder, country, sources, acts, decisions, ai_use=('none',)):
    acts = [a for a in acts if a.units]
    c = {'country': country, 'sources': sources, 'laws': {}, 'acts': [a.as_dict() for a in acts], 'applies': [],
         'decisions': list(decisions), 'ai_use': list(ai_use)}
    out = os.path.join(folder, 'corpus.json')
    with open(out + '.tmp', 'w', encoding='utf-8', newline='\n') as f:
        json.dump(c, f, ensure_ascii=False, indent=1)
        f.write('\n')
    os.replace(out + '.tmp', out)
    n = sum(len(a.units) for a in acts)
    print(f'corpus.json: {len(acts)} acts, {n} units')
    return c


def write_docs(folder, spec):
    """repo/README.md, repo/LICENSE and repo/jurisdiction.json for a state first build. spec keys: name, state, code,
    domain, acts_table (list of (folder, title, versions, history)), source, dates, limits, license."""
    d = os.path.join(folder, 'repo')
    os.makedirs(d, exist_ok=True)
    s = spec
    rows = '\n'.join(f'| `{a[0]}` | {a[1]} | {a[2]} | {a[3]} |' for a in s['acts_table'])
    readme = f"""# {s['name']}: law history in git

The law of {s['state']} as a git history: one file per provision, with `git blame` and `git log` working line by line.
It follows the shared design of [lexifina/global-law](https://github.com/lexifina/global-law).

**What is in it now (a first build, not complete)**

| Folder | Act | Versions | History |
| --- | --- | ---: | --- |
{rows}

**Source.** {s['source']}

## Dates

{s['dates']}

## How it is checked

Every version is read back from git on the day it took effect and on the day before (`tools/check_repo.py`) and must match `corpus.json`; the results are in `REPRODUCE.md`.

## What "author" means

The author of a commit is the law that made the change, with an e-mail address that cannot exist (`<law key>@{s['domain']}.invalid`). In this first build no dated history is available, so every commit is credited to the publisher as "oldest version available". The committer is always Lexifina.

## Limits

{s['limits']}
"""
    open(os.path.join(d, 'README.md'), 'w', encoding='utf-8', newline='\n').write(readme)
    open(os.path.join(d, 'LICENSE'), 'w', encoding='utf-8', newline='\n').write(s['license'].rstrip() + """

Lexifina's own contributions (the arrangement of the history, the commit messages, the tables and the
tools) are dedicated to the public domain under CC0 1.0 Universal: https://creativecommons.org/publicdomain/zero/1.0/
""")
    open(os.path.join(d, 'jurisdiction.json'), 'w', encoding='utf-8', newline='\n').write(json.dumps({
        'path': s['code'].lower().replace('-', '/'), 'code': s['code'], 'name': s['name'], 'level': 'state',
        'repo': f"https://github.com/lexifina/united-states-{s['slug']}-law", 'build': 'built'}, indent=2) + '\n')
