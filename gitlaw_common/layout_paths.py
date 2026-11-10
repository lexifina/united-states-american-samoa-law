"""Kind/year/number act folders (data/paths.json) for the shared publishers, without touching the builder.

A repository whose layout commit (layout-fix tools/land_layout.py) renamed every act folder from its id
(lr-2006-004/) to <kind>/<year>/<number>/ (lr/2006/004/) holds data/paths.json: {"paths": {act id: folder}, "since":
day, ...}. build.py, append.py and check.py keep working in the flat layout (one folder per act id); the publishers
translate at the boundary, and only for a published branch whose tip holds data/paths.json:

    lay = Layout.at(repo, tip)                       # None without data/paths.json: nothing here runs
    flat, real2flat = flatten(repo, tip, lay)       # the branch as the flat builder reads it (see flatten())
    ... the unchanged flat publisher runs on `flat` (append_onto, append.append, check.py) and makes new_flat ...
    real, flat2real, lay2 = lift(repo, tip, flat, new_flat, lay)   # its new commits written onto the real tip

flatten() rewrites only the commits from the one that brought data/paths.json (the layout commit, or on a future
branch the merge of it) to the tip: same author, committer and message bytes, the tree with every act folder back at
its id and data/paths.json left out (a correction's Act-path/Files trailers translated likewise). The commits before
it are the published ones, unchanged. Same input, same SHAs: nothing is stored.

lift() replays each new flat commit onto the real tip: the tree with every act folder moved to its folder (new acts
get one by the slug rules below, never one another act holds or sits inside), the author, committer and message bytes
kept (correction trailers translated). Law and correction commits carry the published data/paths.json; a
documentation commit (Lexifina's, not a correction) gets data/paths.json with the new acts added, and the files named
in paths.json "carry" (if any) from the published tip. A documentation commit that changes nothing is dropped.
Standard library only.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import threading
import zlib
from pathlib import Path

PATHS_FILE = 'data/paths.json'
RESERVED = {'data', 'tools', 'README.md'}


class LayoutError(RuntimeError):
    pass


def _git(repo: Path, *args: str, data: bytes | None = None, check: bool = True) -> bytes:
    p = subprocess.run(['git', '-c', 'core.quotePath=false', *args], cwd=repo, input=data, capture_output=True)
    if check and p.returncode:
        raise LayoutError(f'git {" ".join(args[:3])}: {p.stderr.decode("utf-8", "replace").strip()[:300]}')
    return p.stdout


def has_layout(repo: Path, ref: str) -> bool:
    """True when `ref` holds data/paths.json (one `git cat-file -e`)."""
    return subprocess.run(['git', 'cat-file', '-e', f'{ref}:{PATHS_FILE}'], cwd=repo,
                          capture_output=True).returncode == 0


# ---------------------------------------------------------------- folder rules for new acts
# The slug rules of layout-fix tools/slug_paths.py place() (first match wins; the slug stays the act id).
_Y = r'(1[6-9]\d\d|20[0-2]\d)'
RULES = [
    ('kind-date-num', re.compile(rf'^([a-z][a-z-]*?)-{_Y}-(\d\d)-(\d\d)-([0-9a-z-]+)$'),
     lambda m: f'{m[1]}/{m[2]}/{m[3]}-{m[4]}-{m[5]}'),
    ('kind-year-num', re.compile(rf'^([a-z][a-z-]*?)-{_Y}-([0-9][0-9a-z-]*)$'), lambda m: f'{m[1]}/{m[2]}/{m[3]}'),
    ('kind-num-year', re.compile(rf'^([a-z][a-z-]*?)-(\d[0-9a-z]*)-{_Y}$'), lambda m: f'{m[1]}/{m[3]}/{m[2]}'),
    ('name-act-year', re.compile(rf'^([a-z0-9-]+)-(act|law|code|ordinance|regulations?|rules|statute|decree|order)-{_Y}$'),
     lambda m: f'{"regulation" if m[2].startswith("regulation") else m[2]}/{m[3]}/{m[1]}'),
    ('name-year', re.compile(rf'^([a-z][a-z0-9-]+)-{_Y}$'), lambda m: f'act/{m[2]}/{m[1]}'),
    ('constitution', re.compile(r'^(constitu\w*|konstitu\w*|verfassung|grundgesetz|lei-organica|ustava|ustav)(-.*)?$'),
     lambda m: f'constitution/{m[0]}'),
    ('code', re.compile(r'^(cod|kodeks|kodeksi|kodik|kod|codice|code|kodex)[a-z]*-.+$'), lambda m: f'code/{m[0]}'),
]


def place(slug: str) -> str:
    """The folder the slug rules give an act id (the id itself when no rule matches)."""
    leaf = slug.rsplit('/', 1)[-1]
    for _, rx, f in RULES:
        m = rx.match(leaf)
        if m:
            return f(m)
    return slug


class Layout:
    """data/paths.json of one published tip: {act id: folder}, both ways, and the path translations."""

    def __init__(self, doc: dict, blob: str | None = None):
        self.doc = doc
        self.blob = blob  # the published data/paths.json blob, reused while no act is added
        self.paths: dict[str, str] = dict(doc.get('paths') or {})
        self.back: dict[str, str] = {}
        for k, v in self.paths.items():
            if v in self.back:
                raise LayoutError(f'data/paths.json gives {self.back[v]} and {k} one folder {v}')
            self.back[v] = k
        self.added: list[str] = []

    @classmethod
    def at(cls, repo: Path, ref: str) -> 'Layout | None':
        p = subprocess.run(['git', 'rev-parse', '-q', '--verify', f'{ref}:{PATHS_FILE}'], cwd=repo,
                           capture_output=True, text=True)
        if p.returncode:
            return None
        blob = p.stdout.strip()
        try:
            doc = json.loads(_git(repo, 'cat-file', 'blob', blob).decode('utf-8'))
        except ValueError as e:
            raise LayoutError(f'{ref}:{PATHS_FILE} is not JSON ({e})')
        if not isinstance(doc.get('paths'), dict):
            raise LayoutError(f'{ref}:{PATHS_FILE} has no "paths" map')
        return cls(doc, blob)

    @staticmethod
    def _sub(path: str, table: dict[str, str]) -> str:
        """`path` with its longest act-folder prefix found in `table` replaced (unchanged when none is)."""
        parts = path.split('/')
        for i in range(len(parts), 0, -1):
            hit = table.get('/'.join(parts[:i]))
            if hit is not None:
                return '/'.join([hit] + parts[i:])
        return path

    def to_new(self, path: str) -> str:
        return self._sub(path, self.paths)

    def to_old(self, path: str) -> str:
        return self._sub(path, self.back)

    def covers(self, path: str) -> bool:
        parts = path.split('/')
        return any('/'.join(parts[:i]) in self.paths for i in range(1, len(parts) + 1))

    def moves(self) -> list[tuple[str, str]]:
        """(act id, folder) for every act whose folder differs from its id."""
        return [(k, v) for k, v in self.paths.items() if k != v]

    def _free(self, cand: str, taken: set[str], above: set[str]) -> bool:
        if cand in above or cand.split('/', 1)[0] in RESERVED:
            return False
        parts = cand.split('/')
        return not any('/'.join(parts[:i]) in taken for i in range(1, len(parts) + 1))

    def extended(self, acts: list[str]) -> 'Layout':
        """A copy with a folder for each act id in `acts` that has none: the slug rule's folder, else
        <folder>-<id>, else the id; never one that another act holds, sits inside or holds inside it."""
        new = [a for a in sorted(set(acts)) if a not in self.paths]
        if not new:
            return self
        doc = json.loads(json.dumps(self.doc))
        paths = doc['paths']
        taken = set(paths.values())
        above = {'/'.join(v.split('/')[:i]) for v in taken for i in range(1, v.count('/') + 1)}
        for a in new:
            base = place(a)
            for cand in (base, f'{base}-{a.rsplit("/", 1)[-1]}', a):
                if self._free(cand, taken, above):
                    break
            else:
                raise LayoutError(f'no free folder for the new act {a} (tried {base})')
            paths[a] = cand
            taken.add(cand)
            above |= {'/'.join(cand.split('/')[:i]) for i in range(1, cand.count('/') + 1)}
        out = Layout(doc)
        out.added = new
        return out

    def json_bytes(self) -> bytes:
        """data/paths.json as land_layout.py writes it (indent 0, UTF-8, newline at the end)."""
        return (json.dumps(self.doc, ensure_ascii=False, indent=0) + '\n').encode('utf-8')


# ---------------------------------------------------------------- objects and trees
class Objects:
    """One `git cat-file --batch` for reads; loose objects written as git writes them."""

    def __init__(self, repo: Path):
        self.repo = repo
        self.p = subprocess.Popen(['git', 'cat-file', '--batch'], cwd=repo, stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE)
        d = _git(repo, 'rev-parse', '--git-path', 'objects').decode().strip()
        self.objdir = Path(d) if Path(d).is_absolute() else repo / d
        self.trees: dict[str, dict] = {}

    def read(self, oid: str) -> tuple[bytes, bytes]:
        self.p.stdin.write(oid.encode() + b'\n')
        self.p.stdin.flush()
        head = self.p.stdout.readline()
        if head.endswith(b'missing\n'):
            raise LayoutError(f'missing object {oid}')
        _, kind, size = head.split()
        data = self.p.stdout.read(int(size))
        self.p.stdout.read(1)
        return kind, data

    def tree(self, oid: str) -> dict[bytes, tuple[bytes, str]]:
        if oid not in self.trees:
            kind, data = self.read(oid)
            if kind != b'tree':
                raise LayoutError(f'{oid} is a {kind.decode()}, not a tree')
            out, i = {}, 0
            while i < len(data):
                sp = data.index(b' ', i)
                nul = data.index(b'\0', sp)
                out[data[sp + 1:nul]] = (data[i:sp], data[nul + 1:nul + 21].hex())
                i = nul + 21
            self.trees[oid] = out
        return self.trees[oid]

    def write(self, kind: str, body: bytes) -> str:
        data = f'{kind} {len(body)}\0'.encode() + body
        sha = hashlib.sha1(data).hexdigest()
        path = self.objdir / sha[:2] / sha[2:]
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(f'.tmp-{sha[2:]}-{os.getpid()}-{threading.get_ident()}')
            tmp.write_bytes(zlib.compress(data, 1))
            try:
                os.replace(tmp, path)
            except OSError:
                if not path.exists():
                    raise
                tmp.unlink(missing_ok=True)
        return sha

    def write_tree(self, entries: dict[bytes, tuple[bytes, str]]) -> str:
        body = b''.join(m + b' ' + n + b'\0' + bytes.fromhex(o) for n, (m, o) in
                        sorted(entries.items(), key=lambda e: e[0] + (b'/' if e[1][0] == b'40000' else b'')))
        return self.write('tree', body)

    def close(self):
        try:
            self.p.stdin.close()
            self.p.wait()
            self.p.stdout.close()
        except OSError:
            pass


class _Edit:
    """A tree being edited: unchanged subtrees stay (mode, oid); a changed directory becomes a dict."""

    def __init__(self, objs: Objects, root: str):
        self.o = objs
        self.root = dict(objs.tree(root))

    def _parent(self, parts: list[bytes], create: bool) -> dict | None:
        node = self.root
        for name in parts:
            e = node.get(name)
            if isinstance(e, dict):
                node = e
            elif e is not None and e[0] == b'40000':
                node[name] = d = dict(self.o.tree(e[1]))
                node = d
            elif e is None and create:
                node[name] = d = {}
                node = d
            else:
                return None
        return node

    def pop(self, path: bytes):
        *dirs, leaf = path.split(b'/')
        node = self._parent(dirs, False)
        return None if node is None else node.pop(leaf, None)

    def get(self, path: bytes):
        *dirs, leaf = path.split(b'/')
        node = self._parent(dirs, False)
        return None if node is None else node.get(leaf)

    def put(self, path: bytes, entry, replace: bool = False):
        *dirs, leaf = path.split(b'/')
        node = self._parent(dirs, True)
        if node is None:
            raise LayoutError(f'{path.decode("utf-8", "replace")}: a file is in the way')
        if leaf in node and not replace:
            raise LayoutError(f'{path.decode("utf-8", "replace")} is already in the tree')
        node[leaf] = entry

    def write(self) -> str:
        def w(node: dict) -> str | None:
            out = {}
            for name, e in node.items():
                if isinstance(e, dict):
                    oid = w(e)
                    if oid is not None:
                        out[name] = (b'40000', oid)
                else:
                    out[name] = e
            return self.o.write_tree(out) if out else None
        return w(self.root) or self.o.write_tree({})


def translate_tree(objs: Objects, tree: str, moves: list[tuple[str, str]], set_files: dict[str, tuple | None]) -> str:
    """`tree` with each (src, dst) folder moved (a src the tree lacks is skipped; a dst already there is an error),
    then each set_files path set to (mode, oid) or removed (None)."""
    e = _Edit(objs, tree)
    found = []
    for src, dst in moves:
        x = e.pop(src.encode('utf-8'))
        if x is not None:
            found.append((dst.encode('utf-8'), x))
    for dst, x in found:
        e.put(dst, x)
    for p, v in set_files.items():
        if v is None:
            e.pop(p.encode('utf-8'))
        else:
            e.put(p.encode('utf-8'), v, replace=True)
    return e.write()


# ---------------------------------------------------------------- commits
def _split(raw: bytes) -> tuple[list[bytes], bytes]:
    head, _, msg = raw.partition(b'\n\n')
    return head.split(b'\n'), msg


def _field(lines: list[bytes], name: bytes) -> bytes:
    return next((l[len(name) + 1:] for l in lines if l.startswith(name + b' ')), b'')


def is_correction(msg: bytes) -> bool:
    return re.search(rb'(?m)^Kind: *correction\s*$', msg) is not None


def is_docs(raw: bytes) -> bool:
    """Lexifina's own commit that is not a correction (documentation, layout)."""
    lines, msg = _split(raw)
    author = _field(lines, b'author')
    return author[:author.rfind(b'<')].strip() == b'Lexifina' and not is_correction(msg)


def _message(msg: bytes, fn) -> bytes:
    """A correction's Act-path and Files trailer values through fn (other messages unchanged)."""
    if not is_correction(msg):
        return msg

    def sub(m):
        return m.group(1) + fn(m.group(2).decode('utf-8')).encode('utf-8')
    return re.sub(rb'(?m)^((?:Act-path|Files): *)(\S.*?)$', sub, msg)


def _commit(objs: Objects, raw: bytes, tree: str, parent: str, fn) -> str:
    """`raw` with a new tree and one parent; author, committer, encoding and message kept (correction trailers
    through fn); any signature or merge header dropped."""
    lines, msg = _split(raw)
    body = [b'tree ' + tree.encode(), b'parent ' + parent.encode()]
    body += [l for l in lines if l.startswith((b'author ', b'committer ', b'encoding '))]
    return objs.write('commit', b'\n'.join(body) + b'\n\n' + _message(msg, fn))


def _first_parents(repo: Path, rng: str) -> list[str]:
    return _git(repo, 'rev-list', '--first-parent', '--reverse', rng).decode().split()


def transition(repo: Path, tip: str) -> str:
    """The first first-parent commit of `tip` that holds data/paths.json (the layout commit, or the merge of it)."""
    shas = _git(repo, 'log', '--first-parent', '--format=%H', tip, '--', PATHS_FILE).decode().split()
    if not shas:
        raise LayoutError(f'{tip[:12]} has no commit that brings {PATHS_FILE}')
    t = shas[-1]
    parents = _git(repo, 'rev-list', '--parents', '-n', '1', t).decode().split()[1:]
    if not parents or has_layout(repo, parents[0]):
        raise LayoutError(f'{t[:12]}: no parent without {PATHS_FILE} (a root commit, or it was removed and re-added)')
    return t


def flatten(repo: Path, tip: str, lay: Layout, objs: Objects | None = None) -> tuple[str, dict[str, str]]:
    """The branch at `tip` as the flat builder would have published it (see the module doc). Returns the flat tip and
    {real commit: flat commit} for the rewritten ones (earlier commits are their own)."""
    own = objs is None
    objs = objs or Objects(repo)
    try:
        t = transition(repo, tip)
        prev = _git(repo, 'rev-parse', f'{t}^1').decode().strip()
        back = [(v, k) for k, v in lay.moves()]
        seen_maps: set[str] = set()
        out: dict[str, str] = {}
        for c in _first_parents(repo, f'{t}^1..{tip}'):
            kind, raw = objs.read(c)
            tree = _field(_split(raw)[0], b'tree').decode()
            pj = objs.tree(tree).get(b'data')
            pj = objs.tree(pj[1]).get(b'paths.json') if pj and pj[0] == b'40000' else None
            if pj is None:
                raise LayoutError(f'{c[:12]} (after the layout commit) has no {PATHS_FILE}')
            if pj[1] not in seen_maps and pj[1] != lay.blob:
                older = json.loads(objs.read(pj[1])[1].decode('utf-8')).get('paths') or {}
                bad = [k for k, v in older.items() if lay.paths.get(k) != v]
                if bad:
                    raise LayoutError(f'{c[:12]}: data/paths.json gave {bad[0]} another folder than the tip does')
                seen_maps.add(pj[1])
            flat_tree = translate_tree(objs, tree, back, {PATHS_FILE: None})
            prev = out[c] = _commit(objs, raw, flat_tree, prev, lay.to_old)
        return prev, out
    finally:
        if own:
            objs.close()


def _law_paths(repo: Path, a: str, b: str) -> set[str]:
    """Provision files (.md under an act folder, not README.md, not data/ or tools/) that differ between a and b."""
    out = _git(repo, 'diff', '-z', '--no-renames', '--name-only', a, b).decode('utf-8')
    paths = set()
    for t in out.split('\0'):
        top, _, rest = t.partition('/')
        if rest and t.endswith('.md') and not t.endswith('/README.md') and top not in ('data', 'tools'):
            paths.add(t)
    return paths


def lift(repo: Path, real_base: str, flat_base: str, flat_tip: str, lay: Layout,
         objs: Objects | None = None) -> tuple[str, dict[str, str], Layout]:
    """The flat commits flat_base..flat_tip (first parent; flat_base an ancestor) replayed onto real_base (see the
    module doc). Returns (real tip, {flat commit: real commit}, the layout with any new acts)."""
    if subprocess.run(['git', 'merge-base', '--is-ancestor', flat_base, flat_tip], cwd=repo).returncode:
        raise LayoutError(f'{flat_tip[:12]} does not descend from {flat_base[:12]}')
    own = objs is None
    objs = objs or Objects(repo)
    try:
        commits = _first_parents(repo, f'{flat_base}..{flat_tip}')
        if not commits:
            return real_base, {flat_base: real_base}, lay
        # New acts: an act id a new provision file lies under that has no folder yet and is not published at its id.
        new = set()
        for p in _law_paths(repo, flat_base, flat_tip):
            if not lay.covers(p):
                act = p.split('/', 1)[0]
                if _git(repo, 'ls-tree', real_base, '--', act).strip() == b'':
                    new.add(act)
        lay2 = lay.extended(sorted(new))
        if lay2 is lay:
            blob = lay.blob or _git(repo, 'rev-parse', f'{real_base}:{PATHS_FILE}').decode().strip()
        else:
            blob = objs.write('blob', lay2.json_bytes())
        carry = [p for p in (lay2.doc.get('carry') or []) if isinstance(p, str)]
        moves = lay2.moves()
        real_tree = lambda c: _field(_split(objs.read(c)[1])[0], b'tree').decode()  # noqa: E731
        base_edit = _Edit(objs, real_tree(real_base))
        carried = {p: base_edit.get(p.encode('utf-8')) for p in carry}
        out = {flat_base: real_base}
        prev = real_base
        for c in commits:
            _, raw = objs.read(c)
            tree = _field(_split(raw)[0], b'tree').decode()
            parent_pj = _Edit(objs, real_tree(prev)).get(PATHS_FILE.encode())
            if is_docs(raw):
                sets = {PATHS_FILE: (b'100644', blob), **{p: v for p, v in carried.items()}}
            else:
                sets = {PATHS_FILE: parent_pj}
            new_tree = translate_tree(objs, tree, moves, sets)
            if is_docs(raw) and new_tree == real_tree(prev):
                out[c] = prev  # a documentation commit with nothing new to say
                continue
            prev = out[c] = _commit(objs, raw, new_tree, prev, lay2.to_new)
        return prev, out, lay2
    finally:
        if own:
            objs.close()


def law_files(repo: Path, commit: str) -> dict[str, str]:
    out = _git(repo, 'ls-tree', '-r', '-z', commit).decode('utf-8')
    files = {}
    for rec in out.split('\0'):
        if rec:
            meta, _, path = rec.partition('\t')
            top, _, rest = path.partition('/')
            if rest and path.endswith('.md') and not path.endswith('/README.md') and top not in ('data', 'tools'):
                files[path] = meta.split()[2]
    return files


def verify(repo: Path, real: str, flat: str, lay: Layout) -> list[str]:
    """Problems ([] when none): the real tip's provision files must be the flat tip's, each at its folder."""
    want = {lay.to_new(p): o for p, o in law_files(repo, flat).items()}
    have = law_files(repo, real)
    bad = sorted(p for p in set(want) | set(have) if want.get(p) != have.get(p))
    return [f'{len(bad)} provision files differ from the flat build at their folders, e.g. {bad[:3]}'] if bad else []
