"""Credits proposed by a model (CORPUS-STANDARD.md §5b): check them, then turn the checked ones into correction parts.

    python -X utf8 credits.py check <country folder> [--tsv FILE] [--write]
    python -X utf8 credits.py emit  <country folder> [--tsv FILE] [--prefix 95] [--date YYYY-MM-DD]

A model may propose the law that made a change where the source names none (the publisher is credited today). Its
proposal is never law text and is never published as a credit by itself. The proposals live in a TSV in the country
folder (default `credits-proposed.tsv`), one row per changed provision in one version:

    path            the provision file, <act slug>/<unit key>.md, as published
    version_from    the version's `from` day (the commit the change is in)
    proposed_law    a key of the corpus's `laws`
    evidence        one line quoted from the source that names the law and the provision
    evidence_url    where that line is, on an official host the corpus already uses
    model           the model that proposed it
    confidence      0 to 1, as the model gave it
    checked         written by `check --write`: `yes`, or `no: <reason>`

`check` accepts a row only when every rule holds:
- the act, the version and the provision exist, and the provision's text changed in that version (or the version is
  the act's first, credited to nobody);
- the corpus credits no law for it yet;
- the law exists; it was published or enacted on or before the version's day;
- the version's day is the law's commencement as the corpus's own data gives it (the law's `in_force` or
  `commenced` day); the evidence never establishes one, and fails the row if it states another commencement day;
- the evidence is one line that names the provision (a provision word and its number, no other number or suffix:
  "s. 1" is not "s. 10" or "s. 1A") and the law by its whole label ("Act 7 of 2015", not "Act 17 of 2015"), and its
  URL is on the host of the act, of the law, or of one of the corpus's sources.

`emit` re-checks, then plans the parts of one emission, named <prefix>-credits-<day>-<nn>-*.json (nn counts the day's
emissions), and writes nothing unless every one is new and sorts after every part already in corpus.d, so it loads
after the parts it corrects:
- <...>-ai-use.json, always: `ai_use` gives what the model proposed, by model, and how many were checked and rejected;
- <...>-<part>.json, one per part holding a credited act (SCHEMA.md, correction parts): it corrects the latest part
  that holds those acts, replacing them whole, with the checked credits set in the versions' own `credits` and a
  version-level `correction` (`metadata_only`, and a Reason naming the law and the evidence URL), so
  `append.py --corrections` appends labelled correction commits and never rewrites.
Each part gets <part>.PUBLISH.pending, a review request; it reaches main only once a reviewer signs it off
(<part>.PUBLISH, publish_marker.write). Rejected rows are never published, as credits or otherwise.
"""
from __future__ import annotations

import argparse
import copy
import csv
import datetime as dt
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build as B  # noqa: E402

COLUMNS = ['path', 'version_from', 'proposed_law', 'evidence', 'evidence_url', 'model', 'confidence', 'checked']


def read_tsv(path: Path) -> list[dict]:
    with open(path, encoding='utf-8', newline='') as f:
        return [{k: (v or '').strip() for k, v in r.items()} for r in csv.DictReader(f, delimiter='\t')]


def write_tsv(path: Path, rows: list[dict]) -> None:
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, delimiter='\t', lineterminator='\n', extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


def host(url: str) -> str:
    h = (urlparse(url).hostname or '').lower()
    return h[4:] if h.startswith('www.') else h


MONTHS = {m: i for i, ms in enumerate([
    ('january', 'janvier', 'enero', 'januar', 'gennaio', 'janeiro'), ('february', 'février', 'fevrier', 'febrero', 'februar', 'febbraio', 'fevereiro'),
    ('march', 'mars', 'marzo', 'märz', 'marz', 'março', 'marco'), ('april', 'avril', 'abril', 'aprile'),
    ('may', 'mai', 'mayo', 'maggio', 'maio'), ('june', 'juin', 'junio', 'juni', 'giugno', 'junho'),
    ('july', 'juillet', 'julio', 'juli', 'luglio', 'julho'), ('august', 'août', 'aout', 'agosto'),
    ('september', 'septembre', 'septiembre', 'setiembre', 'settembre', 'setembro'), ('october', 'octobre', 'octubre', 'oktober', 'ottobre', 'outubro'),
    ('november', 'novembre', 'noviembre', 'novembro'), ('december', 'décembre', 'decembre', 'diciembre', 'dezember', 'dicembre', 'dezembro')], 1)
    for m in ms}
PROVISION_WORDS = (r'(?:s|ss|sec|secs|section|sections|art|arts|article|articles|artículo|articulo|artigo|artikel|'
                   r'§|§§|reg|regs|regulation|para|paras|paragraph|rule|cl|clause|item|schedule|sch)')


def norm(s: str) -> str:
    """Casefolded, punctuation as spaces, the words for "number" dropped: 'Act No. 7 of 2015' -> 'act 7 of 2015'."""
    s = re.sub(r'[^\w§]+', ' ', s.casefold())
    return ' '.join(t for t in s.split() if t not in ('no', 'nº', 'n', 'n°', 'nr', 'num', 'number', 'núm', 'numero', 'número'))


def dated(s: str) -> list[tuple[str, int]]:
    """(day, offset) for every calendar day a line states: 2017-04-01, 1/4/2017, 1.4.2017, 1 April 2017, April 1, 2017
    (day first for numeric forms, as legislation outside the US writes them)."""
    out = []
    for m in re.finditer(r'\b(\d{4})-(\d{2})-(\d{2})\b', s):
        out.append((f'{m[1]}-{m[2]}-{m[3]}', m.start()))
    for m in re.finditer(r'\b(\d{1,2})[./](\d{1,2})[./](\d{4})\b', s):
        out.append((f'{m[3]}-{int(m[2]):02d}-{int(m[1]):02d}', m.start()))
    words = s.lower()  # lower() keeps offsets for these scripts
    for m in re.finditer(r'\b(\d{1,2})(?:er|st|nd|rd|th|º|°)?\s+(?:de\s+)?([a-zéûçä]+)\s+(?:de\s+)?(\d{4})\b', words):
        if m[2] in MONTHS:
            out.append((f'{m[3]}-{MONTHS[m[2]]:02d}-{int(m[1]):02d}', m.start()))
    for m in re.finditer(r'\b([a-zéûçä]+)\s+(\d{1,2}),?\s+(\d{4})\b', words):
        if m[1] in MONTHS:
            out.append((f'{m[3]}-{MONTHS[m[1]]:02d}-{int(m[2]):02d}', m.start()))
    return sorted(out, key=lambda t: t[1])


def dates_in(s: str) -> set[str]:
    return {d for d, _ in dated(s)}


# Words that make the day after them a commencement day, and words that make it some other day (review of 918f755:
# a publication or retrieval day in the same quote passed as the commencement).
COMMENCES = re.compile(r'in force|into force|entry into|with effect|effect from|takes effect|took effect|effective|'
                       r'commenc|operative|\bfrom\b|en vigueur|à compter|a compter|à partir|a partir|en vigor|vigencia|'
                       r'desde|em vigor|vigência|vigencia|in kraft|mit wirkung|\bab\b|vigore|decorrenza|účinn|obowiązuje|wchodzi')
OTHER_DAY = re.compile(r'publish|publication|gazett|retriev|access|download|promulgat|sign|assent|enact|made\b|dated|'
                       r'passed|approv|publié|publicad|publicaç|verkünd|ausgefertigt|pubblicat|vyhlás|ogłosz|amended on')


def commencement_days(ev: str) -> set[str]:
    """The days the evidence states as commencement: a day whose own clause (the text before it, back to the previous
    day, ';', ',', '(' or ')') holds a commencement word and no word for another kind of day."""
    out, prev = set(), 0
    for day, at in dated(ev):
        clause = ev[prev:at]
        cut = max(clause.rfind(c) for c in ';,()')
        clause = clause[cut + 1:].lower() if cut >= 0 else clause.lower()
        if COMMENCES.search(clause) and not OTHER_DAY.search(clause):
            out.add(day)
        prev = at + 1
    return out


def names_provision(ev: str, unit: dict, key: str) -> bool:
    """The evidence names this provision: a provision word followed by its number (and any suffix such as bis)."""
    label = norm(unit.get('label', '') or '')
    m = re.search(r'(\d+)\s*([a-z]*)\s*$', label) or re.search(r'(\d+)(?:-([a-z]+))?$', key)
    if not m:
        return False
    num, suffix = m.group(1).lstrip('0') or '0', (m.group(2) or '')
    pat = rf'\b{PROVISION_WORDS}\s+0*{num}' + (rf'\s*{suffix}\b' if suffix else r'(?!\w)(?!\s*(?:bis|ter|quater)\b)')
    return re.search(pat, norm(ev)) is not None


def names_law(ev: str, law: dict) -> bool:
    """The evidence names this law: its whole label, compared word for word after norm()."""
    label = norm(law.get('label', ''))
    return bool(label) and re.search(rf'(?<!\w){re.escape(label)}(?!\w)', norm(ev)) is not None


def find_act(acts: dict, path: str) -> tuple[dict | None, str]:
    if not path.endswith('.md'):
        return None, ''
    for slug in sorted(acts, key=len, reverse=True):
        if path.startswith(slug + '/'):
            return acts[slug], path[len(slug) + 1:-3]
    return None, ''


def is_day(s) -> bool:
    """A canonical calendar day, YYYY-MM-DD, that exists (re-review 4 of 7d8ac2a: 2017-02-29, 2017-13-01 and
    2017-04-01T00:00:00Z passed as equal strings)."""
    if not isinstance(s, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', s):
        return False
    try:
        return dt.date.fromisoformat(s).isoformat() == s
    except ValueError:
        return False


class DuplicateKey(ValueError):
    pass


def _pairs(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise DuplicateKey(k)
        d[k] = v
    return d


def duplicate_keys(folder: Path) -> list[str]:
    """The corpus files that give some key twice, at any depth (re-review 6 of b579062: a parser keeps one of the two,
    so whatever the other said is lost before any check can see it). Any such file makes the whole corpus ambiguous."""
    out = []
    d = folder / 'corpus.d'
    for f in [folder / 'corpus.json'] + (sorted(d.glob('*.json')) if d.exists() else []):
        if f.exists():
            try:
                json.loads(f.read_text(encoding='utf-8'), object_pairs_hook=_pairs)
            except DuplicateKey as e:
                out.append(f'{f.name} ({e.args[0]!r})')
    return out


def law_days(folder: Path) -> dict[str, list]:
    """Every definition of each law across corpus.json and every part, as written (build.load keeps one of them).
    Call only on a corpus with no duplicate keys."""
    out: dict[str, list] = {}
    d = folder / 'corpus.d'
    for f in [folder / 'corpus.json'] + (sorted(d.glob('*.json')) if d.exists() else []):
        if not f.exists():
            continue
        data = json.loads(f.read_text(encoding='utf-8'))
        laws = data.get('laws') if isinstance(data, dict) else None
        if isinstance(laws, dict):
            for k, law in laws.items():
                out.setdefault(k, []).append(law)
    return out


def commencement_of(defs: list[dict]) -> tuple[str | None, str]:
    """The law's one commencement day from the corpus data, or (None, why) when it gives none or is ambiguous: a key
    given twice, a value that is not a calendar day, or different days (in_force against commenced, or one part
    against another). Fails closed (re-review 4 of 7d8ac2a: ambiguous values were resolved silently)."""
    days = set()
    for law in defs:
        if not isinstance(law, dict):
            return None, 'a definition of the law is not an object'
        for field in ('in_force', 'commenced'):
            if field not in law:
                continue
            if not is_day(law[field]):  # present means a calendar day: null and "" are refused too (re-review 5)
                return None, f'the law\'s {field} {law[field]!r} is not a calendar day'
            days.add(law[field])
    if len(days) > 1:
        return None, f'the corpus gives the law different commencement days ({", ".join(sorted(days))})'
    return (days.pop() if days else None), ''


def check_row(c: dict, acts: dict, hosts_ok: set[str], r: dict, defs: dict | None = None) -> str:
    """'' when the row passes, else the first rule it fails."""
    if not is_day(r.get('version_from')):
        return f"version_from {r.get('version_from')!r} is not a calendar day"
    act, key = find_act(acts, r.get('path', ''))
    if act is None:
        return 'no act holds this path'
    vs = act['versions']
    idx = [i for i, v in enumerate(vs) if v.get('from') == r.get('version_from')]
    if not idx:
        return f"act {act['slug']} has no version from {r.get('version_from')!r}"
    i = idx[-1]  # the last version of its day is the one in force at the end of it
    v = vs[i]
    if key not in v.get('units', {}):
        return f'the provision {key} is not in that version'
    prev = vs[i - 1]['units'].get(key, {}).get('text') if i > 0 else None
    if i > 0 and prev == v['units'][key].get('text'):
        return 'the provision did not change in that version'
    if i == 0 and act.get('first_law'):
        return 'the first version is already credited to first_law'
    have = v.get('credits', {}).get(key)
    if have:
        return f'already credited to {", ".join(have)}'
    law = c.get('laws', {}).get(r.get('proposed_law', ''))
    if not law:
        return f"unknown law {r.get('proposed_law')!r}"
    day = r['version_from']
    for field in ('published', 'enacted'):
        for d_ in (defs or {}).get(r['proposed_law']) or [law]:
            if field in d_ and not is_day(d_[field]):
                return f"the law's {field} {d_[field]!r} is not a calendar day"
    made = law.get('published') or law.get('enacted')
    if not made or not is_day(made) or made > day:
        return f'the law is dated {made or "nowhere"}, not on or before {day}'
    ev = r.get('evidence', '')
    if not ev or '\n' in ev or len(ev) > 600:
        return 'evidence must be one line of at most 600 characters'
    # The commencement must come from the corpus's own data for the law (its in_force or commenced day, as the
    # builder read it from the official source), never from the quoted evidence: three reviews found phrasings
    # (other languages, a negation, a word after the day, a day in a neighbouring clause) that a text filter takes
    # for a commencement. The evidence can only disqualify a row, by stating another commencement day.
    stated, why = commencement_of((defs or {}).get(r['proposed_law']) or [law])
    if why:
        return f'no commencement day: {why}'
    if not stated:
        return (f'no commencement day: the corpus gives this law no in_force or commenced day (the evidence alone '
                f'cannot establish {day})')
    if stated != day:
        return f'the law is in force from {stated}, not {day}'
    said = commencement_days(ev)
    if said - {day}:
        return f'the evidence gives commencement {", ".join(sorted(said - {day}))}, not {day}'
    if not names_provision(ev, v['units'][key], key):
        return f'the evidence does not name the provision ({v["units"][key].get("label") or key})'
    if not names_law(ev, law):
        return f'the evidence does not name the law ({law.get("label")})'
    url = r.get('evidence_url', '')
    if not url.startswith(('https://', 'http://')) or host(url) not in hosts_ok:
        return 'the evidence URL is not on a host the corpus uses'
    if not r.get('model'):
        return 'no model named'
    try:
        conf = float(r.get('confidence') or 'nan')
    except ValueError:
        conf = float('nan')
    if not 0 <= conf <= 1:
        return 'confidence must be between 0 and 1'
    return ''


def corpus_hosts(c: dict) -> set[str]:
    hs = {host(s.get('url', '')) for s in c.get('sources', [])}
    hs |= {host(a.get('url', '')) for a in c.get('acts', [])}
    hs |= {host(law.get('url', '')) for law in c.get('laws', {}).values()}
    return {h for h in hs if h}


def check(folder: Path, tsv: Path, write: bool = False) -> tuple[list[dict], dict]:
    c, _ = B.load(folder)
    acts = {a['slug']: a for a in c.get('acts', [])}
    hosts_ok = corpus_hosts(c)
    rows = read_tsv(tsv)
    dups = duplicate_keys(folder)
    defs = {} if dups else law_days(folder)
    seen = set()
    for r in rows:
        why = (f'the corpus gives a key twice in {", ".join(dups)}; no row is checked until that is fixed' if dups
               else check_row(c, acts, hosts_ok, r, defs))
        k = (r.get('path'), r.get('version_from'))
        if not why and k in seen:
            why = 'a second proposal for the same provision and version'
        seen.add(k)
        r['checked'] = 'yes' if not why else f'no: {why}'
    counts = {'proposed': len(rows), 'checked': sum(r['checked'] == 'yes' for r in rows)}
    counts['rejected'] = counts['proposed'] - counts['checked']
    if write:
        write_tsv(tsv, rows)
    return rows, counts


def run_name(folder: Path, prefix: str, day: str) -> str:
    """This emission's name stem, <prefix>-credits-<day>-<nn>: nn counts the emissions of the day. Parts load in
    file-name order, so a later emission sorts after every part it corrects. An earlier emission is never replaced: a
    later one corrects the latest part that holds each act, so earlier credits carry forward."""
    pat = re.compile(rf'{re.escape(prefix)}-credits-{re.escape(day)}-(\d{{2}})-')
    used = [int(m.group(1)) for f in (folder / 'corpus.d').glob(f'{prefix}-credits-{day}-*')
            if (m := pat.match(f.name))]
    n = max(used, default=0) + 1
    if n > 99:
        raise B.CorpusError(f'more than 99 credit emissions on {day}')
    return f'{prefix}-credits-{day}-{n:02d}'


def write_part(path: Path, body: dict) -> Path:
    path.parent.mkdir(exist_ok=True)
    if path.exists():
        raise B.CorpusError(f'{path.name} exists; an emission never replaces a part')
    data = (json.dumps(body, ensure_ascii=False, indent=1) + '\n').encode('utf-8')
    tmp = path.with_suffix('.json.tmp')
    with open(tmp, 'xb') as f:  # 'x': never write over a part, even one created since new_part looked
        f.write(data)
    tmp.rename(path)
    # A review request, not a sign-off: only a separate reviewer writes <part>.PUBLISH (publish_marker.write).
    path.with_suffix('.PUBLISH.pending').write_text(
        f'sha256:{hashlib.sha256(data).hexdigest()}\nrequested-by: credits.py emit\n', encoding='utf-8', newline='\n')
    return path


def emit(folder: Path, tsv: Path, prefix: str = '95', date: str | None = None) -> list[Path]:
    """Correction parts for the checked rows, plus one disclosure part for every emission that read proposals (even
    when none passed), so ai_use always records what a model proposed and what was rejected."""
    rows, counts = check(folder, tsv)
    good = [r for r in rows if r['checked'] == 'yes']
    day = dt.date.today().isoformat() if date is None else date  # only an absent --date means today
    if not is_day(day):
        raise B.CorpusError(f'--date {day!r} is not a calendar day')
    if not rows:
        return []
    by_model: dict[str, list[int]] = {}
    for r in rows:
        m = r.get('model') or '(no model named)'
        by_model.setdefault(m, [0, 0])[0 if r['checked'] == 'yes' else 1] += 1
    disclosure = (f"credits.py {day}: a model proposed {counts['proposed']} credits for changes the source names no "
                  f"law for ({'; '.join(f'{m}: {a} checked, {b} rejected' for m, (a, b) in sorted(by_model.items()))}). "
                  f"{counts['checked']} passed the rule check and are named in correction commits; the law text is "
                  f"unchanged. {counts['rejected']} were rejected and are not published as credits.")
    run = run_name(folder, prefix, day)
    d = folder / 'corpus.d'
    plan = [(d / f'{run}-ai-use.json', {'acts': [], 'ai_use': [disclosure]})]
    if good:
        plan += correction_plan(folder, good, run)
    # The whole emission is checked before any file is written (review of 918f755: a refused name left a partial run).
    # build.load reads parts in sorted path order and a correction must come after the part it names, so every part
    # written here must sort after every part already there: a source part named 99-* or zz-*, or a --date earlier
    # than an earlier emission's, needs a later --prefix.
    existing = sorted(p for p in d.glob('*.json')) if d.exists() else []
    names = [p for p, _ in plan]
    # Names compared as a file system may: after NFC normalisation and case folding (re-review 4 of 7d8ac2a: an
    # NFC/NFD pair was written as two files). A collision with another new part or an existing one is refused.
    fold = lambda p: unicodedata.normalize('NFC', p.name).casefold()  # noqa: E731
    if len({fold(p) for p in names}) != len(names):
        raise B.CorpusError('two parts of one emission would share a file name (after Unicode normalisation and case)')
    have = {fold(p): p.name for p in existing}
    for p in names:
        if fold(p) in have:
            raise B.CorpusError(f'{p.name} would collide with the existing part {have[fold(p)]}')
    for p in names:
        if p.exists() or p.with_suffix('.json.tmp').exists():
            raise B.CorpusError(f'{p.name} exists; an emission never replaces a part')
    if existing and min(names) <= existing[-1]:
        raise B.CorpusError(f'{min(names).name} would load before {existing[-1].name}, which it must follow; '
                            f'use a --prefix that sorts after it (or a --date no earlier than the last emission)')
    return [write_part(p, body) for p, body in plan]


def correction_plan(folder: Path, good: list[dict], run: str) -> list[tuple[Path, dict]]:
    """(path, body) of each correction part: one per part that currently holds a credited act, named
    <run>-<that part's own stem>, made unique when two owners share a stem (an original part and an earlier
    emission's correction of it, review of 918f755)."""
    records: dict = {}
    c, _ = B.load(folder, part_records=records)
    acts = {a['slug']: a for a in c['acts']}
    owner = {}  # act slug -> the latest loaded part holding it (a correction part, if one already replaced it)
    for name, rec in records.items():
        for slug in rec['acts']:
            owner[slug] = name
    by_part: dict[str, dict[str, dict]] = {}
    for r in good:
        act, key = find_act(acts, r['path'])
        part = owner.get(act['slug'])
        if not part:
            raise B.CorpusError(f"{act['slug']} is in corpus.json, not a part; a correction part needs a part to name")
        new = by_part.setdefault(part, {}).setdefault(act['slug'], copy.deepcopy(act))
        v = [x for x in new['versions'] if x.get('from') == r['version_from']][-1]
        v.setdefault('credits', {})[key] = [r['proposed_law']]
        label = c['laws'][r['proposed_law']]['label']
        corr = v.setdefault('correction', {})
        corr.setdefault('metadata_only', True)
        found = corr.setdefault('_found', [])
        found.append(f'{label} ({r["evidence_url"]})')
    out, taken = [], set()
    for part, acts_new in sorted(by_part.items()):
        for act in acts_new.values():
            for v in act['versions']:
                corr = v.get('correction')
                if corr and '_found' in corr:
                    found = sorted(set(corr.pop('_found')))
                    corr['reason'] = 'credit found by a checked model proposal: ' + '; '.join(found)
        stem = re.sub(r'^.*?-credits-\d{4}-\d{2}-\d{2}-\d{2}-', '', Path(part).stem)  # 95-credits-<day>-01-20-fees -> 20-fees
        name, n = f'{run}-{stem}', 1
        while name in taken:
            n += 1
            name = f'{run}-{stem}-{n}'
        taken.add(name)
        out.append((folder / 'corpus.d' / f'{name}.json', {'corrects': part, 'acts': list(acts_new.values())}))
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('command', choices=('check', 'emit'))
    ap.add_argument('folder', type=Path)
    ap.add_argument('--tsv', type=Path)
    ap.add_argument('--write', action='store_true', help='check: write the checked column back')
    ap.add_argument('--prefix', default='95', help='emit: the file-name prefix that orders the parts (after the rest)')
    ap.add_argument('--date', help='emit: the day written in ai_use (default today)')
    a = ap.parse_args(argv)
    tsv = a.tsv or a.folder / 'credits-proposed.tsv'
    if a.command == 'check':
        rows, counts = check(a.folder, tsv, a.write)
        print(f"{counts['proposed']} proposed, {counts['checked']} checked, {counts['rejected']} rejected")
        reasons: dict[str, int] = {}
        for r in rows:
            if r['checked'] != 'yes':
                reasons[r['checked']] = reasons.get(r['checked'], 0) + 1
        for why, n in sorted(reasons.items(), key=lambda x: -x[1])[:15]:
            print(f'  {n:>6}  {why}')
        return 0
    for p in emit(a.folder, tsv, a.prefix, a.date):
        print('wrote', p)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
