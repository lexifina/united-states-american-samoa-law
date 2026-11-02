"""Canton of Zurich for git-for-law (gitlaw-scraper-dell, 2026-10-30): ZH-Lex (Zürcher Loseblattsammlung, LS) on
www.zh.ch, each Nachtrag's text as a text-layer PDF on www.notes.zh.ch. Private (world-law-ops), never published.

    python -X utf8 scripts/world-law/ch_zurich.py fetch [--laws N]   # one process; one request at a time per host
    python -X utf8 scripts/world-law/ch_zurich.py parse 2026-10-30
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html as htmlmod
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'switzerland-zurich-law'
CACHE = FOLDER / '.cache'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'
BASE = 'https://www.zh.ch'
LIST = BASE + '/de/politik-staat/gesetze-beschluesse/gesetzessammlung/_jcr_content/main/lawcollectionsearch_312548694.zhweb-zhlex-ls.zhweb-cache.json'
PAUSE = 1.0
_last: dict[str, float] = {}


def cpath(url: str, ext: str) -> Path:
    return CACHE / (hashlib.sha256(url.encode()).hexdigest() + ext)


def get(url: str, ext: str = '.html', offline: bool = False) -> bytes | None:
    p = cpath(url, ext)
    if p.exists():
        return p.read_bytes()
    if offline:
        return None
    CACHE.mkdir(parents=True, exist_ok=True)
    host = urllib.parse.urlsplit(url).netloc
    for attempt in range(4):
        w = _last.get(host, 0) + PAUSE - time.time()
        if w > 0:
            time.sleep(w)
        t0 = time.time()
        r = subprocess.run(['curl', '-s', '-L', '-m', '120', '--compressed', '-A', UA, '-w', '\n%{http_code}', url],
                           capture_output=True)
        _last[host] = time.time()
        body, _, code = r.stdout.rpartition(b'\n')
        code = code.decode().strip()
        with open(CACHE / 'requests.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps({'at': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'url': url,
                                'status': code, 'bytes': len(body), 'secs': round(_last[host] - t0, 2)}) + '\n')
        if code == '200':
            if b'Just a moment' in body[:3000] or b'challenge-platform' in body[:5000]:
                raise SystemExit(f'challenge at {url}: stop')
            tmp = p.with_suffix('.tmp')
            tmp.write_bytes(body)
            os.replace(tmp, p)
            return body
        if code == '404':
            return None
        if code == '204':  # no results
            p.write_bytes(b'')
            return b''
        if code in ('403', '429') or code.startswith('5'):
            if code == '403' and attempt >= 1:
                raise SystemExit(f'403 twice at {url}: stop')
            time.sleep(30 * (attempt + 1))
            continue
        time.sleep(5)
    raise SystemExit(f'{url} failed ({code})')


def acts_list() -> list[dict]:
    return json.loads(get(LIST, '.json'))['data']


def page_info(html: str) -> dict:
    """Facts from one act/Nachtrag page: the Nachtrag list, its PDF, its dates."""
    t = re.sub(r'(?s)<(script|style).*?</\1>', ' ', html)
    text = ' '.join(htmlmod.unescape(re.sub(r'<[^>]+>', ' ', t)).split())
    links = sorted(set(re.findall(r'href="(/de/politik-staat/gesetze-beschluesse/gesetzessammlung/zhlex-ls/erlass-[^"]+\.html)"', html)))
    pdf = re.findall(r'(https://www\.notes\.zh\.ch/appl/zhlex_r\.nsf/OpenAttachment\?Open&(?:amp;)?docid=[0-9A-F]+&(?:amp;)?file=[^"\']+\.pdf)', html)
    pdf = htmlmod.unescape(pdf[0]) if pdf else None
    if pdf:  # OpenAttachment answers with a script redirect to this WebView address
        m = re.search(r'docid=([0-9A-F]+)&file=(.+\.pdf)$', pdf)
        pdf = f'https://www.notes.zh.ch/appl/zhlex_r.nsf/WebView/{m.group(1)}/$File/{m.group(2)}'

    def field(name):
        m = re.search(re.escape(name) + r' (\S+)', text)
        return m.group(1) if m and m.group(1) != '-' else None
    hist = re.findall(r'(\d{3})\s*\((aktuell|in Kraft bis (\d\d\.\d\d\.\d{4})|in Kraft ab (\d\d\.\d\d\.\d{4}))\)', text)
    return {'links': links, 'pdf': pdf, 'title': field('Erlasstitel'), 'nr': field('Ordnungsnummer'),
            'erlassdatum': field('Erlassdatum'), 'inkraft': field('Inkraftsetzungsdatum'),
            'aufhebung': field('Aufhebungsdatum'), 'publikation': field('Publikationsdatum'),
            'hist': hist, 'text': text}


def fetch_act(link: str, offline=False) -> dict | None:
    b = get(BASE + link, offline=offline)
    if b is None:
        return None
    info = page_info(b.decode('utf-8', 'replace'))
    out = {'link': link, 'info': info, 'versions': {}}
    # every Nachtrag page of the current Erlass (same ordnr + same erlass dates prefix)
    stem = re.match(r'(.*-)\d{3}\.html$', link).group(1)
    for l in [link] + [x for x in info['links'] if x.startswith(stem) and x != link]:
        vb = get(BASE + l, offline=offline) if l != link else b
        if vb is None:
            continue
        vi = page_info(vb.decode('utf-8', 'replace'))
        pdfb = get(vi['pdf'], '.pdf', offline=offline) if vi['pdf'] else None
        if pdfb is not None and not pdfb.startswith(b'%PDF'):
            raise SystemExit(f'not a PDF: {vi["pdf"]}')
        out['versions'][l] = {'info': {k: v for k, v in vi.items() if k not in ('text', 'links')},
                              'pdf_ok': pdfb is not None}
    return out


# ---------------------------------------------------------------- corpus

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ch_zurich_pdf as P  # noqa: E402

MONTHS = {m: i + 1 for i, m in enumerate(['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August',
                                          'September', 'Oktober', 'November', 'Dezember'])}
DMY = re.compile(r'(\d{1,2})\.\s*(' + '|'.join(MONTHS) + r')\s+(\d{4})')


def iso(s: str | None) -> str | None:
    m = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', s or '')
    return f'{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}' if m else None


def gdate(s: str) -> str | None:
    m = DMY.search(s or '')
    return f'{m.group(3)}-{MONTHS[m.group(2)]:02d}-{int(m.group(1)):02d}' if m else None


def note_law(note: str) -> tuple[str, dict, str | None] | None:
    """An endnote naming an OS entry -> (law key, law, in-force day)."""
    m = re.search(r'\bOS\s+(\d+),\s*(\d+)', note)
    if not m:
        return None
    key = f'os-{m.group(1)}-{m.group(2)}'
    label = f'OS {m.group(1)}, {m.group(2)}'
    enacted = gdate(re.split(r'\(OS', note)[0])
    kind_m = re.search(r'(Änderung|Gesetz|Beschluss|Verordnung|Volksabstimmung)[^()]*?vom\s+\d{1,2}\.\s*\w+\s+\d{4}', note)
    title = f'{kind_m.group(0)} ({label})' if kind_m else label
    inf = re.search(r'In Kraft seit\s+(.+?\d{4})', note)
    return key, {'label': label, 'title': title, 'kind': 'law', 'enacted': enacted, 'published': None,
                 'url': None, 'temporary_until': None, 'restores': None, 'note': None}, gdate(inf.group(1)) if inf else None


def parse_act(link: str) -> tuple[dict, dict] | str | None:
    r = fetch_act(link, offline=True)
    if r is None:
        return None
    vers = []
    for l, v in r['versions'].items():
        info = v['info']
        if not v['pdf_ok'] or not info.get('pdf') or not iso(info.get('publikation')):
            continue
        mnr = re.search(r'-(\d+)\.html$', l)
        if not mnr:
            continue
        nr = int(mnr.group(1))
        vers.append({'from': iso(info['publikation']), 'nr': nr, 'link': l, 'pdf': info['pdf'], 'info': info})
    if not vers:
        return 'skip'
    vers.sort(key=lambda v: (v['from'], v['nr']))
    by_day = {}
    for v in vers:
        by_day[v['from']] = v  # the last Nachtrag of a day stands
    vers = sorted(by_day.values(), key=lambda v: v['from'])
    laws: dict[str, dict] = {}
    out_versions = []
    prev_units = prev_meta = prev_from = None
    cur_info = r['info']
    for v in vers:
        path = cpath(v['pdf'], '.pdf')
        units, meta = P.parse_pdf(path)
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        notes = {n: note_law(t) for n, t in meta['notes'].items()}
        for nl in notes.values():
            if nl:
                laws.setdefault(nl[0], nl[1])
        ver = {'from': v['from'], 'source_url': v['pdf'], 'sha256': sha, 'nachtrag': v['nr']}
        if prev_units is None:
            ver['units'] = units
            ver['credits'] = {}
        else:
            changed = sorted(k for k in set(prev_units) | set(units)
                             if prev_units.get(k, {}).get('text') != units.get(k, {}).get('text'))
            if not changed:
                continue
            ver['changes'] = {k: units.get(k) for k in changed}
            window = sorted({nl[0] for nl in notes.values() if nl and nl[2] and prev_from < nl[2] <= v['from']})
            credits = {}
            for k in changed:
                rs = meta['refs'].get(k, []) if k in units else prev_meta['refs'].get(k, [])
                nn = notes if k in units else {n: note_law(t) for n, t in prev_meta['notes'].items()}
                ls = sorted({nn[int(x)][0] for x in rs if int(x) in nn and nn[int(x)]
                             and nn[int(x)][2] and prev_from < nn[int(x)][2] <= v['from']})
                if not ls:
                    ls = window
                if ls:
                    credits[k] = ls
            ver['credits'] = credits
        out_versions.append(ver)
        prev_units, prev_meta, prev_from = units, meta, v['from']
    v0 = out_versions[0]
    first_meta_units, first_meta = P.parse_pdf(cpath(vers[0]['pdf'], '.pdf'))
    first_law, earlier = None, []
    orig = [note_law(first_meta['notes'][int(x)]) for x in first_meta['refs'].get('ingress', [])
            if int(x) in first_meta['notes'] and note_law(first_meta['notes'][int(x)])]
    inkraft = iso(cur_info.get('inkraft'))
    if orig and inkraft and v0['from'] == inkraft and vers[0]['nr'] == min(v['nr'] for v in vers):
        first_law = orig[0][0]
        laws.setdefault(orig[0][0], orig[0][1])
        laws[first_law]['enacted'] = iso(cur_info.get('erlassdatum')) or laws[first_law]['enacted']
    else:
        earlier = sorted({nl[0] for nl in (note_law(t) for t in first_meta['notes'].values())
                          if nl and nl[2] and nl[2] <= v0['from']})
        if orig:
            earlier = sorted(set(earlier) | {orig[0][0]})
            laws.setdefault(orig[0][0], orig[0][1])
    nr = cur_info.get('nr') or ''
    full_title = next((a['enactmentTitle'] for a in acts_list() + all_law_entries() if a['link'] == link), None)         or cur_info.get('title') or ''
    if first_law:
        laws[first_law]['title'] = P.clean(full_title)
    act = {'slug': ascii_slug(nr), 'short': f'LS {nr}', 'title': P.clean(full_title),
           'url': BASE + link, 'first_law': first_law, 'earlier_laws': earlier, 'systematic_number': nr,
           'versions': out_versions}
    used = set(earlier) | ({first_law} if first_law else set())
    for v in out_versions:
        for ls in v.get('credits', {}).values():
            used.update(ls)
    return act, {k: laws[k] for k in sorted(used)}


def ascii_slug(nr: str) -> str:
    return 'ls-' + P.ascii_key(nr)


def write_part(p: Path, part: dict):
    if p.with_suffix('.PUBLISH').exists():
        return  # a published part never changes
    tmp = p.with_suffix('.tmp')
    tmp.write_text(json.dumps(part, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    os.replace(tmp, p)


COUNTRY = {
    'code': 'CH-ZH', 'name': 'Zurich', 'slug': 'switzerland-zurich', 'lang': 'de', 'tz': 'Europe/Zurich',
    'future_branch': 'zukunft',
    'publisher': {'name': 'Kanton Zürich, Zürcher Gesetzessammlung (ZH-Lex)', 'email': 'zhlex@zh.ch.invalid'},
    'default_in_force_rule': {
        'text': ('Each version is dated by the day ZH-Lex gives for its Nachtrag (the day the amendment it '
                 'incorporates took effect); cantonal acts take effect on the day the act or the government sets.'),
        'source': 'https://www.zh.ch/de/politik-staat/gesetze-beschluesse/gesetzessammlung.html'},
    'licence_note': ('Text: Kanton Zürich, Zürcher Loseblattsammlung (LS), ZH-Lex. Laws are not protected by '
                     'copyright in Switzerland (Art. 5 para. 1 let. a URG).'),
}
SOURCE = {'name': 'Kanton Zürich: Zürcher Loseblattsammlung (LS), ZH-Lex',
          'url': 'https://www.zh.ch/de/politik-staat/gesetze-beschluesse/gesetzessammlung.html',
          'licence': 'Laws are not protected by copyright (Art. 5 para. 1 let. a URG, SR 231.1); the canton\'s '
                     'Nutzungshinweise exempt law texts from their copyright notice.',
          'notes': 'Every Nachtrag of each act that ZH-Lex links as a PDF, with its endnotes.'}
DECISIONS = [
    'Each version is the PDF of one Nachtrag in ZH-Lex, dated by the day ZH-Lex gives for that Nachtrag; when two '
    'Nachträge share a day only the later one is kept.',
    'Changes are credited to the amending act (its entry in the Official Compilation, OS) named in the endnote '
    'attached to the changed provision, when that endnote says it took effect after the previous version and on or '
    'before this one; otherwise to every OS entry whose endnote gives an in-force day in that window; otherwise the '
    'change is unexplained.',
    'Margin titles are the article titles; section headings are kept in gliederung.md, the title, date and preamble '
    'in ingress.md. Note references, running heads, page numbers and the endnotes are left out.',
    'The text is read from the PDFs\' text layer (no OCR).',
]
AI_USE = ['A model (Claude) wrote the fetch and parse code and chose which acts to include; it wrote no law text.']


def all_law_entries() -> list[dict]:
    """The ZH-Lex list caps a search at 150 results, so the laws are listed by title: 'Gesetz ...' and '<letter>*gesetz'."""
    seen = {}
    for q in ['gesetz'] + [f'{c}*gesetz' for c in 'abcdefghijklmnopqrstuvwxyzäöü']:
        page = 1
        while True:
            b = get(LIST + '?' + urllib.parse.urlencode({'enactmentTitle': q, 'page': page}), '.json')
            if not b:
                break
            d = json.loads(b)
            for x in d.get('data', []):
                seen.setdefault(x['link'], x)
            if page >= d.get('numberOfResultPages', 1):
                break
            page += 1
    def nat(s):
        return [int(t) if t.isdigit() else t for t in re.findall(r'\d+|\D+', s)]
    return sorted(seen.values(), key=lambda x: nat(x['referenceNumber']))


def law_links() -> list[str]:
    out = []
    for a in all_law_entries():
        if a.get('withdrawalDate'):
            continue
        t = a['enactmentTitle']
        if a['referenceNumber'] == '101' or not re.search(r'gesetz', t, re.I) or re.search(
                r'verordnung|reglement|beschluss|vereinbarung|konkordat|vertrag|weisung|richtlinie|tarif|statut|abkommen', t, re.I):
            continue
        out.append(a['link'])
    return out


def parse_all(docs_date: str, size: int = 50):
    out = FOLDER / 'corpus.d'
    out.mkdir(exist_ok=True)
    const = [a for a in acts_list() if a['referenceNumber'] == '101'][0]
    r = parse_act(const['link'])
    act, laws = r
    write_part(out / '10-verfassung.json', {'country': COUNTRY, 'sources': [SOURCE], 'laws': laws, 'acts': [act],
                                            'decisions': DECISIONS, 'ai_use': AI_USE})
    print('10-verfassung', len(act['versions']), 'versions')
    links = law_links()
    done = (CACHE / 'fetch-done.txt').exists()
    for pi in range(0, len(links), size):
        chunk = links[pi:pi + size]
        if len(chunk) < size and not done:
            break
        acts, laws = [], {}
        ok = True
        for l in chunk:
            r = parse_act(l)
            if r is None:
                ok = False
                break
            if r == 'skip':
                continue
            acts.append(r[0])
            for k, v in r[1].items():
                laws.setdefault(k, v)
        if not ok:
            break
        name = f'{20 + pi // size:02d}-gesetze-{pi // size + 1}'
        write_part(out / f'{name}.json', {'laws': dict(sorted(laws.items())), 'acts': acts})
        print(name, len(acts), 'acts', sum(len(a['versions']) for a in acts), 'versions')


def letters_check(part: str) -> list[str]:
    p = json.loads((FOLDER / 'corpus.d' / f'{part}.json').read_text(encoding='utf-8'))
    from collections import Counter
    probs = []
    for act in p['acts']:
        units = {}
        for v in act['versions']:
            if 'units' in v:
                units = dict(v['units'])
            else:
                for k, u in v['changes'].items():
                    if u is None:
                        units.pop(k, None)
                    else:
                        units[k] = u
            a = Counter(P.source_letters(cpath(v['source_url'], '.pdf')))
            b = Counter(P.letters(''.join(u['text'] for u in units.values())))
            if a != b:
                probs.append(f'{act["slug"]} {v["from"]}: source-only {dict((a - b).most_common(6))} '
                             f'corpus-only {dict((b - a).most_common(6))}')
    return probs


# ---------------------------------------------------------------- docs, scaffold, verification

DOCS = ROOT.parent.parent


def _long(d: str) -> str:
    x = dt.date.fromisoformat(d)
    return f'{x.day} {x.strftime("%B")} {x.year}'


def write_docs(extra=(), out: Path | None = None):
    parts = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((FOLDER / 'corpus.d').glob('*.json'))
             if p.with_suffix('.PUBLISH').exists() or p.stem in extra]
    rows, nacts, nvers = [], 0, 0
    nords = any('verordnungen' in p.stem for p in (FOLDER / 'corpus.d').glob('*.json')
                if p.with_suffix('.PUBLISH').exists() or p.stem in extra)
    for part in parts:
        for a in part['acts']:
            vs = a['versions']
            nacts += 1
            nvers += len(vs)
            span = _long(vs[0]['from']) if len(vs) == 1 else f'{_long(vs[0]["from"])} to {_long(vs[-1]["from"])}'
            hist = ('as enacted, then ' if a.get('first_law') else 'oldest version available, then ') if len(vs) > 1 \
                else ('as enacted' if a.get('first_law') else 'one version (the oldest available)')
            rows.append(f'| `{a["slug"]}/` | {a["title"]} (LS {a["systematic_number"]}) | {len(vs)} | '
                        f'{hist}{"each Nachtrag: " if len(vs) > 1 else ""}{span} |')
    pr = FOLDER / 'pruned.json'
    left_out = sorted({x for v in (json.loads(pr.read_text(encoding='utf-8')).values() if pr.exists() else []) for x in v})
    left_note = ('' if not left_out else ' Laws whose PDF layout the parser does not yet read letter for letter are left out '
                 'until it does: ' + ', '.join('LS ' + x[3:].replace('-', '.') for x in left_out) + '.')
    repo = out or (FOLDER / 'repo')
    repo.mkdir(parents=True, exist_ok=True)
    readme = f"""# Zurich: law history in git

The law of the canton of Zurich (Kanton Zürich, Switzerland) as a git history: one file per article, one commit per amending act on the day it took effect, and the amending act as the commit's author. `git blame` names the act behind every paragraph; `git log` lists every change to an article; checking out a date gives the text in force that day.

It follows the shared design of [lexifina/global-law](https://github.com/lexifina/global-law), which places it at `ch-zh/`. The federal law is in [lexifina/switzerland-law](https://github.com/lexifina/switzerland-law).

The text is in German, the canton's official language, exactly as the canton publishes it.

## What this repository holds

{nacts} act{"s" if nacts != 1 else ""} with {nvers} versions so far: the cantonal constitution, then the cantonal laws (Gesetze) in force{(' and the ordinances (Verordnungen and Reglemente) in force' if nords else '')}, in the order of the Zürcher Loseblattsammlung (LS), added in parts. {('Decrees' if nords else 'Ordinances, decrees')}, intercantonal agreements and repealed acts are not included yet.{left_note}

| Folder | Act | Versions | History |
| --- | --- | ---: | --- |
{chr(10).join(rows)}

## Source

The Zürcher Loseblattsammlung (LS) in ZH-Lex, the canton's collection of its law in force, at <https://www.zh.ch/de/politik-staat/gesetze-beschluesse/gesetzessammlung.html>. For each act ZH-Lex lists every Nachtrag (each reissue of the act after an amendment) with its date and links the Nachtrag's text as a PDF. The endnotes of each PDF name, for every amended provision, the amending act, its entry in the Official Compilation (OS) and the day it took effect.

## Dates

- Each commit is dated at **noon, Europe/Zurich, on the day ZH-Lex gives for the Nachtrag**, which is the day the amendments it incorporates took effect. The decision date of each amending act is the `Enacted:` trailer.
- An act's first commit is the oldest Nachtrag of the act in force today. It is credited to the act as enacted when it is the act's first Nachtrag and dated the day the act took effect; otherwise it is the "oldest version available".
- `--before="YYYY-MM-DD"` alone uses your clock's time of day; use `T23:59:59Z` or `tools/on.py`.

## Files

`<act>/art-005.md` is Art. 5 (or § 5), `art-005a.md` Art. 5a; the first line holds the article's margin title. `ingress.md` holds the title, date and preamble; `gliederung.md` the section headings; `abschnitt-*.md` text printed under a heading with no article (such as transitional provisions of an amendment). One paragraph or list item per line. Note references, running heads, page numbers and the endnotes are left out.

## How it is checked

- Every version of every act is read back from git on the day it took effect and on the day before (`tools/check_repo.py`); both must match `corpus.json`.
- The letters and digits of every version equal those of the text layer of that Nachtrag's PDF (read span by span, less running heads, page numbers, note references and endnotes).
- Health checks: no merge commits, commit dates never go backwards, nothing dated in the future, and every commit's trailers parse.

## What "author" means

The author of a commit is the amending act, named by its entry in the Official Compilation (`OS <volume>, <page>`), with an e-mail address that cannot exist (`<act key>@zh.ch.invalid`). A change is credited to the act named in the endnote of the changed provision; where no endnote of that provision names an act taking effect in that window, every act whose endnote gives an in-force day in the window is named; where there is none, the change is unexplained and committed by the publisher. The committer is always Lexifina.

## Limits

This is not an official publication; the binding text is the one in the canton's official publications. The history starts with the oldest Nachtrag ZH-Lex links as a PDF for the act in force today, so older versions of an act (before a total revision, such as the constitution of 1869) are not included. Only the acts listed above are included.
"""
    lic = """The law texts in this repository are official texts of the canton of Zurich (Kanton Zürich), taken from the
Zürcher Loseblattsammlung (LS) in ZH-Lex (https://www.zh.ch/de/politik-staat/gesetze-beschluesse/gesetzessammlung.html).

Swiss law does not protect them by copyright. Federal Act on Copyright and Related Rights (URG, SR 231.1),
Art. 5 para. 1: "Keinen urheberrechtlichen Schutz geniessen: a. Gesetze, Verordnungen, völkerrechtliche Verträge
und andere amtliche Erlasse; [...]" (Not protected by copyright: a. acts, ordinances, international treaties and
other official enactments.)

The canton's own terms of use (https://www.zh.ch/de/nutzungshinweise.html) agree: the content of its websites is
protected "soweit sie nicht (wie Gesetzestexte und Gerichtsurteile) durch einschlägige Rechtsnormen ausdrücklich vom
Schutz ausgenommen werden" (unless, like law texts and court judgments, it is expressly excluded from protection by
the relevant legal provisions). This repository is not an official publication.

Lexifina's own contributions (the arrangement of the history, the commit messages, the tables and the tools) are
dedicated to the public domain under CC0 1.0 Universal: https://creativecommons.org/publicdomain/zero/1.0/
"""
    juris = {'path': 'ch-zh', 'code': 'CH-ZH', 'name': 'Zurich', 'level': 'canton', 'parent': 'ch',
             'repo': 'https://github.com/lexifina/switzerland-zurich-law',
             'build': f'built: constitution and cantonal laws ({nacts} acts, {nvers} versions) from ZH-Lex (LS)',
             'language': 'de', 'sources': 1}
    (repo / 'README.md').write_text(readme, encoding='utf-8', newline='\n')
    (repo / 'LICENSE').write_text(lic, encoding='utf-8', newline='\n')
    (repo / 'jurisdiction.json').write_text(json.dumps(juris, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
                                            newline='\n')


def _low(cmd, env=None):
    return subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', env=env,
                          creationflags=0x4000 if os.name == 'nt' else 0)


def publish(part: str, docs_date: str) -> str:
    import shutil
    probs = letters_check(part)
    if probs:
        return f'NOT VERIFIED letters: {len(probs)}: {probs[0]}'
    tmp, build = DOCS / 'switzerland-zurich-law-verify', DOCS / 'switzerland-zurich-law-verifybuild'
    def _rm(d):
        def onexc(fn, path, exc):
            os.chmod(path, 0o666)
            fn(path)
        if d.exists():
            shutil.rmtree(d, onexc=onexc)
    for d in (tmp, build):
        _rm(d)
    (tmp / 'corpus.d').mkdir(parents=True)
    names = [p.stem for p in sorted((FOLDER / 'corpus.d').glob('*.json')) if p.with_suffix('.PUBLISH').exists()]
    for n in names + [part]:
        shutil.copy2(FOLDER / 'corpus.d' / f'{n}.json', tmp / 'corpus.d' / f'{n}.json')
    write_docs(extra=[part], out=tmp / 'repo')
    build.mkdir()
    subprocess.run(['git', 'init', '-q'], cwd=build, check=True)
    env = dict(os.environ, GITLAW_NO_CHECKOUT='1')
    b = _low([sys.executable, '-X', 'utf8', str(ROOT / 'gitlaw_common' / 'build.py'), str(tmp), '--repo', str(build),
              '--docs-date', docs_date], env=env)
    if b.returncode:
        return 'NOT VERIFIED build: ' + (b.stderr or b.stdout)[-800:]
    c = _low([sys.executable, '-X', 'utf8', str(ROOT / 'gitlaw_common' / 'check.py'), str(build), '--corpus',
              str(tmp / 'corpus.json')])
    res = json.loads(c.stdout[c.stdout.index('{'):])
    bad = {k: res.get(k) for k in ('mismatches', 'trailer_errors', 'merges', 'backwards', 'future_dated',
                                   'missing_in_force') if res.get(k)}
    if bad:
        return f'NOT VERIFIED check.py {bad} {json.dumps(res.get("details", [])[:3], ensure_ascii=False)[:500]}'
    p = json.loads((FOLDER / 'corpus.d' / f'{part}.json').read_text(encoding='utf-8'))
    days = sorted(v['from'] for a in p['acts'] for v in a['versions'])
    line = (f'{len(p["acts"])} act(s), {sum(len(a["versions"]) for a in p["acts"])} versions {days[0]}..{days[-1]} '
            f'from ZH-Lex Nachtrag PDFs: letters-and-digits of every version equal the PDF text layer; scratch build of '
            f'verified parts + this part: check.py {res["versions"]} versions, 0 mismatches, 0 trailer errors, '
            f'0 merges ({docs_date}).')
    _rm(tmp)
    _rm(build)
    write_docs(extra=[part])
    pub = FOLDER / 'corpus.d' / f'{part}.PUBLISH'
    pub.with_suffix('.ptmp').write_text(line + '\n', encoding='utf-8', newline='\n')
    os.replace(pub.with_suffix('.ptmp'), pub)
    top = FOLDER / 'PUBLISH'
    if not top.exists():
        top.write_text('corpus.d parts are published one by one, each once its own <part>.PUBLISH is written.\n',
                       encoding='utf-8', newline='\n')
    return 'PUBLISH ' + line


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'fetch':
        acts = acts_list()
        const = [a for a in acts if a['referenceNumber'] == '101'][0]
        fetch_act(const['link'])
        print('constitution fetched', flush=True)
        nmax = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[2] == '--laws' else 10**9
        n = 0
        links = law_links()
        print(len(links), 'laws listed', flush=True)
        for l in links:
            fetch_act(l)
            n += 1
            print(f'law {n}: {l[-50:]}', flush=True)
            if n >= nmax:
                break
        (CACHE / 'fetch-done.txt').write_text(f'{n} laws\n', encoding='utf-8')
    elif cmd == 'parse':
        parse_all(sys.argv[2])
    elif cmd == 'letters':
        probs = letters_check(sys.argv[2])
        print('\n'.join(probs[:30]) or 'letters check: clean')
        print(len(probs), 'problems')
    elif cmd == 'prune':
        # drop acts whose letters check fails, so the part holds only verified acts; list them in pruned.json
        part = sys.argv[2]
        pp = FOLDER / 'corpus.d' / f'{part}.json'
        bad = sorted({x.split(' ')[0] for x in letters_check(part)})
        d = json.loads(pp.read_text(encoding='utf-8'))
        d['acts'] = [a for a in d['acts'] if a['slug'] not in bad]
        used = set()
        for a in d['acts']:
            used |= set(a.get('earlier_laws', [])) | ({a['first_law']} if a.get('first_law') else set())
            for v in a['versions']:
                for ls in v.get('credits', {}).values():
                    used |= set(ls)
        d['laws'] = {k: v for k, v in d['laws'].items() if k in used}
        write_part(pp, d)
        rec = FOLDER / 'pruned.json'
        cur = json.loads(rec.read_text(encoding='utf-8')) if rec.exists() else {}
        cur[part] = bad
        rec.write_text(json.dumps(cur, indent=1) + '\n', encoding='utf-8', newline='\n')
        print('pruned', bad, len(d['acts']), 'acts left')
    elif cmd == 'publish':
        print(publish(sys.argv[2], sys.argv[3]))
