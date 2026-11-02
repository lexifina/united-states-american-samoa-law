"""Swiss cantons without LexWork (gitlaw-scraper-dell fork, 2026-10-30): Geneva (SILGENEVE), Neuchatel (RSN),
Ticino (LexFind copies), Jura, Vaud. Same corpus.d layout as ch_cantons.py. Private: scripts/world-law only.

    python -X utf8 scripts/world-law/ch_romandy.py get <slug> <url>      # one cached request
    python -X utf8 scripts/world-law/ch_romandy.py parse <slug> <docs-date>
    python -X utf8 scripts/world-law/ch_romandy.py publish <slug> <part> <docs-date>
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html as htmlmod
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ch_cantons as C  # noqa: E402  (read-only use)

ROOT = C.ROOT
UA = C.UA
# slug: code, English, official name, host, language, pause (s)
ROMANDY = {
    'geneva': ('GE', 'Geneva', 'République et canton de Genève', 'silgeneve.ch', 'fr', 5.0),
    'neuchatel': ('NE', 'Neuchâtel', 'République et Canton de Neuchâtel', 'rsn.ne.ch', 'fr', 1.0),
    'ticino': ('TI', 'Ticino', 'Repubblica e Cantone Ticino', 'www.lexfind.ch', 'it', 1.0),
    'jura': ('JU', 'Jura', 'République et Canton du Jura', 'rsju.jura.ch', 'fr', 1.0),
    'vaud': ('VD', 'Vaud', 'Canton de Vaud', 'prestations.vd.ch', 'fr', 1.0),
}
for _s, _v in ROMANDY.items():
    C.OTHER[_s] = _v[:5] + (None,)


def folder(slug):
    return ROOT / f'switzerland-{slug}-law'


def cpath(slug, url):
    return folder(slug) / '.cache' / hashlib.sha256(url.encode()).hexdigest()


_last = {}


def get(slug, url) -> bytes:
    p = cpath(slug, url)
    if p.exists():
        return p.read_bytes()
    p.parent.mkdir(parents=True, exist_ok=True)
    gi = folder(slug) / '.gitignore'
    if not gi.exists():
        gi.write_text('.cache/\n', encoding='utf-8', newline='\n')
    pause = ROMANDY[slug][5]
    host = url.split('/')[2]
    w = _last.get(host, 0) + pause - time.time()
    if w > 0:
        time.sleep(w)
    for attempt in range(3):
        r = subprocess.run(['curl', '-sL', '-m', '120', '--compressed', '-A', UA, '-w', '\n%{http_code}', url],
                           capture_output=True)
        _last[host] = time.time()
        body, _, code = r.stdout.rpartition(b'\n')
        code = code.decode().strip()
        with open(p.parent / 'requests.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps({'at': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'url': url,
                                'status': code, 'bytes': len(body)}) + '\n')
        if code == '200':
            p.write_bytes(body)
            return body
        if code in ('403', '429') or code.startswith('5'):
            raise RuntimeError(f'{url}: HTTP {code}, stopping')
        time.sleep(5)
    raise RuntimeError(f'{url}: failed {code}')


clean = C.clean
letters = C.letters


def art_key(num: str) -> str:
    return C.unit_key_for_article(num)


ART = re.compile(r'^(Art\.|Article|Articolo|Art)\s*(premier|primo|\d+[a-zA-Z]*(?:\s?(?:bis|ter|quater|quinquies|sexies|septies|octies|novies|decies)\b)?)\s*(.*)$', re.S)


def _iso(d):
    return C.iso(d)


# ---------------------------------------------------------------- Geneva (Word-filtered HTML, current text)

def _sup_fix(el):
    """Footnote markers '(26)' out; paragraph-number superscripts become 'N '."""
    for s in list(el.iter('sup')):
        t = s.text_content().strip()
        if re.fullmatch(r'\(\d+\)|\[\d+\]|\d+\)', t) or s.find('.//a') is not None and re.fullmatch(r'\[?\d+\]?', t):
            s.drop_tree()
        else:
            tail = s.tail or ''
            s.drop_tree()  # keeps tail; re-insert text as plain
            # lxml drop_tree keeps the tail but drops text: put it back via a marker
            prev = None
    return el


def word_ps(raw: bytes, enc: str):
    from lxml import html
    t = raw.decode(enc)
    # superscripts: footnote refs out, the rest as text followed by a space
    t = re.sub(r'(?is)<sup>(?:\s|<[^>]+>)*(\(\d+\)|\[\d+\])(?:\s|<[^>]+>)*</sup>', '', t)
    t = re.sub(r'(?is)<a\s[^>]*href="#_(?:ftn|edn)\d+"[^>]*>.*?</a>', '', t)
    t = re.sub(r'(?is)<sup>(.*?)</sup>', lambda m: m.group(1) + ' ', t)
    r = html.fromstring(t)
    ws = r.find_class('WordSection1')
    return t, (ws[0] if ws else r.find('body'))


def parse_geneva_doc(raw: bytes):
    t, ws = word_ps(raw, 'cp1252')
    units, order, outline, ingress = {}, [], [], []
    cur = None
    hist = None
    kids = list(ws)
    for i, el in enumerate(kids):
        cls = el.get('class') or ''
        txt = clean(el.text_content())
        if el.tag == 'table' and ('RSG' in txt[:20] and 'Intitul' in txt[:40]):
            hist = el
            break
        if el.tag == 'table':
            if cur is None and not units:
                for p in el.iter('p'):
                    if clean(p.text_content()):
                        ingress.append(('# ' if p.get('class') == 'TitreLoi' else '') + clean(p.text_content()))
                continue
            for tr in el.iter('tr'):
                cells = [clean(td.text_content()) for td in tr.findall('td') if clean(td.text_content())]
                if cells:
                    (units[cur]['lines'] if cur else ingress).append(' | '.join(cells))
            continue
        if not txt:
            continue  # empty spacer paragraphs (retour1/retour2); a filled one is text
        if i < 5 and (txt.startswith('Source SILGENEVE') or txt.startswith('Dernières modifications')
                      or txt == 'Texte en vigueur'):
            continue
        if cls == 'article':
            m = ART.match(txt)
            if m:
                num = m.group(2)
                label = f'Art. {num}'
                key = art_key(num)
                b, n = key, 2
                while key in units:
                    key = f'{b}-{n}'
                    n += 1
                cur = key
                units[key] = {'label': label, 'lines': ['# ' + txt]}
                order.append(key)
                continue
            if cur is None:  # Préambule
                ingress.append('## ' + txt)
                continue
        if cls in ('titre', 'chapitre', 'section', 'soustitre', 'sous-section') or re.match(r'(sous)?(titre|chapitre|section)', cls):
            lvl = {'titre': 2, 'chapitre': 3, 'section': 4}.get(cls, 5)
            outline.append('#' * lvl + ' ' + txt)
            continue
        (units[cur]['lines'] if cur else ingress).append(txt)
    rows = []
    if hist is not None:
        for tr in hist.iter('tr'):
            tds = [clean(td.text_content()) for td in tr.findall('td')]
            if len(tds) >= 3:
                rows.append({'what': tds[0], 'adopted': _iso(tds[1]), 'inforce': _iso(tds[2])})
    out = {}
    if ingress:
        out['ingress'] = {'label': 'Titre et préambule', 'kind': 'preamble', 'text': '\n'.join(ingress) + '\n'}
    for k in order:
        out[k] = {'label': units[k]['label'], 'kind': 'art', 'text': '\n'.join(units[k]['lines']) + '\n'}
    if outline:
        out['gliederung'] = {'label': 'Structure', 'kind': 'heading', 'text': '\n'.join(outline) + '\n'}
    return out, rows, t


def geneva_source_letters(t: str) -> str:
    """Independent of the parser: regex over the raw page, from the title table to the history table."""
    body = t.split('class=WordSection1', 1)[1]
    i = body.find('class=Tteteintit')
    if i > 0:
        body = body[:body.rfind('<table', 0, i)]
    body = re.sub(r'(?is)<sup>(?:\s|<[^>]+>)*\(\d+\)(?:\s|<[^>]+>)*</sup>', ' ', body)  # footnote markers
    body = re.sub(r'(?is)Source(?:\s|<[^>]+>|&nbsp;)*SILGENEVE(?:\s|<[^>]+>|&nbsp;)*PUBLIC', ' ', body, count=1)
    W = r'(?:\s|&nbsp;|<[^>]+>)+'
    body = re.sub(r'(?is)Derni(?:è|&egrave;)res' + W + 'modifications' + W + r'au.*?</p>', ' </p>', body, count=1)
    body = re.sub(r'(?is)>(?:\s|&nbsp;)*Texte' + W + 'en' + W + r'vigueur(?:\s|&nbsp;)*<', '><', body, count=1)
    return letters(htmlmod.unescape(re.sub(r'<[^>]+>', ' ', body)))


# ---------------------------------------------------------------- shared part writing

def country_block(slug, publisher_name, rule_src):
    code, en, native, host, lang, _ = ROMANDY[slug]
    return {
        'code': f'CH-{code}', 'name': en, 'slug': f'switzerland-{slug}', 'lang': lang, 'tz': 'Europe/Zurich',
        'future_branch': C.FUTURE[lang],
        'publisher': {'name': publisher_name, 'email': f'legislation@{host}.invalid'},
        'default_in_force_rule': {
            'text': 'Each version is dated by the in-force day the official collection gives for it.',
            'source': rule_src},
        'licence_note': f'Text: {publisher_name}. Laws and decrees are not protected by copyright in Switzerland '
                        '(Art. 5 para. 1 let. a URG).',
    }


def current_only_act(slug, units, url, sha, frm, title, short, sn, note):
    return {'slug': C.ascii_key(f'{sn}-{short}') if short else C.ascii_key(sn), 'short': short or sn,
            'title': title, 'url': url, 'first_law': None, 'earlier_laws': [], 'systematic_number': sn,
            'versions': [{'from': frm, 'source_url': url, 'sha256': sha, 'units': units, 'credits': {},
                          'note': note}]}


AI_USE = C.AI_USE


def write_part(p, part):
    p.parent.mkdir(parents=True, exist_ok=True)
    C.write_part(p, part)


# ---------------------------------------------------------------- Geneva constitution

GE_BASE = 'https://silgeneve.ch/legis/data/'


def ge_constitution(docs_date):
    slug = 'geneva'
    url = GE_BASE + 'rsg_a2_00.htm'
    raw = get(slug, url)
    units, rows, t = parse_geneva_doc(raw)
    days = [r['inforce'] for r in rows if r['inforce'] and r['inforce'] <= docs_date]
    frm = max(days)
    title = 'Constitution de la République et canton de Genève'
    act = current_only_act(slug, units, url, hashlib.sha256(raw).hexdigest(), frm, title, 'Cst-GE', 'A 2 00',
                           f'Text in force since {frm} (the latest entry into force in the history table that '
                           'SILGENEVE prints under the act), as published on SILGENEVE; no earlier wording is held.')
    pub = 'Chancellerie d\'Etat de Genève, Service de la législation (SILGENEVE)'
    part = {'country': country_block(slug, pub, url),
            'sources': [{'name': 'SILGENEVE, recueil systématique genevois (rsGE)', 'url': 'https://silgeneve.ch/legis/',
                         'retrieved': docs_date, 'licence': 'Art. 5 para. 1 let. a URG (SR 231.1): no copyright in acts.',
                         'notes': 'Current consolidated text of each act (HTML), with its history table.'}],
            'laws': {'ge-a-2-00-2012-10-14': {
                'label': 'Cst-GE du 14 octobre 2012', 'title': title + ' du 14 octobre 2012 (adoptée en votation populaire)',
                'kind': 'referendum', 'enacted': '2012-10-14', 'published': None, 'url': url,
                'temporary_until': None, 'restores': None, 'note': None}},
            'acts': [act], 'decisions': DECISIONS_CURRENT, 'ai_use': AI_USE}
    act['earlier_laws'] = ['ge-a-2-00-2012-10-14']
    write_part(folder(slug) / 'corpus.d' / '10-constitution.json', part)
    return act


DECISIONS_CURRENT = [
    'The collection publishes only the current consolidated text, so each act has one version, the oldest version '
    'available, dated by the latest entry into force the act\'s own history table gives on or before the retrieval '
    'day; it is credited to the publisher.',
    'Section headings are kept together in one file per act (gliederung.md); the title, date and preamble in '
    'ingress.md. Footnote markers are left out.',
]


# ---------------------------------------------------------------- checks, docs, publish

def source_letters(slug, act, v):
    raw = cpath(slug, v['source_url']).read_bytes()
    if slug == 'geneva':
        return geneva_source_letters(raw.decode('cp1252'))
    if slug == 'neuchatel':
        return ne_source_letters(raw.decode('cp1252'), act.get('systematic_number', '101'))
    if slug == 'jura':
        import ch_jura
        return ch_jura.source_letters(raw)
    if slug == 'vaud':
        return _vaud_letters(raw)
    if slug in ('ticino',):
        import ch_ticino
        return ch_ticino.pdf_source_letters(raw)
    raise ValueError(slug)


def letters_check(slug, part):
    p = json.loads((folder(slug) / 'corpus.d' / f'{part}.json').read_text(encoding='utf-8'))
    return acts_problems(slug, p['acts'])


def act_ok(slug, act) -> bool:
    """A part builder keeps an act only when its own text check is clean (the rest are left out and listed)."""
    return not acts_problems(slug, [act])


def acts_problems(slug, acts):
    probs = []
    for act in acts:
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
            src = source_letters(slug, act, v)
            mine = letters(''.join(u['text'] for u in units.values()))
            if Counter(src) != Counter(mine):
                ca, cb = Counter(src), Counter(mine)
                probs.append(f'{act["slug"]} {v["from"]}: source-only {dict((ca - cb).most_common(8))} '
                             f'corpus-only {dict((cb - ca).most_common(8))}')
            for k, u in units.items():
                if k == 'gliederung':
                    continue  # headings sit apart from the text they head; their letters are in the counts
                lines = u['text'].splitlines()
                # line by line (margin titles precede the number); an article's heading line is covered by the counts
                chunks = [l.lstrip('# ') for l in (lines[1:] if k.startswith('art-') else lines)]
                bad = [c for c in chunks if letters(c) and letters(c) not in src]
                if bad:
                    probs.append(f'{act["slug"]} {v["from"]} {k}: not in order in source: {bad[0][:80]}')
                    break
    return probs


def write_docs(slug, docs_date, extra=(), out=None, source_line='', history_line=''):
    code, en, native, host, lang, _ = ROMANDY[slug]
    parts = []
    for p in sorted((folder(slug) / 'corpus.d').glob('*.json')):
        if p.with_suffix('.PUBLISH').exists() or p.stem in extra:
            parts.append(json.loads(p.read_text(encoding='utf-8')))
    rows, na, nv = [], 0, 0
    for part in parts:
        for a in part['acts']:
            vs = a['versions']
            na += 1
            nv += len(vs)
            span = C._long(vs[0]['from']) if len(vs) == 1 else f'{C._long(vs[0]["from"])} to {C._long(vs[-1]["from"])}'
            hist = 'current text only, in force since ' if len(vs) == 1 else 'each consolidated version: '
            rows.append(f'| `{a["slug"]}/` | {a["title"]} ({a["systematic_number"]}) | {len(vs)} | {hist}{span} |')
    meta = SOURCE_DOCS[slug]
    repo = out or folder(slug) / 'repo'
    repo.mkdir(parents=True, exist_ok=True)
    readme = f"""# {en}: law history in git

The law of the canton of {en} ({native}, Switzerland) as a git history: one file per article, one commit per change on the day it took effect. `git blame` and `git log` work line by line; checking out a date gives the text in force that day.

It follows the shared design of [lexifina/global-law](https://github.com/lexifina/global-law), which places it at `ch-{code.lower()}/`. The federal law is in [lexifina/switzerland-law](https://github.com/lexifina/switzerland-law).

The text is in {C.LANGNAME[lang]}, the canton's official language, exactly as published.

## What this repository holds

{na} act{"s" if na != 1 else ""} with {nv} version{"s" if nv != 1 else ""} so far, starting with the cantonal constitution. {meta['holds']}

| Folder | Act | Versions | History |
| --- | --- | ---: | --- |
{chr(10).join(rows)}

## Source

{meta['source']}

## Dates

- Each commit is dated at **noon, Europe/Zurich, on the day the version took effect**.
- {meta['dates']}
- `--before="YYYY-MM-DD"` alone uses your clock's time of day; use `T23:59:59Z` or `tools/on.py`.

## Files

`<act>/art-005.md` is Art. 5, `art-005a.md` Art. 5a; `ingress.md` holds the title, date and preamble; `gliederung.md` the headings of titles, chapters and sections. One paragraph or list item per line. Footnote markers are left out.

## How it is checked

- Every version of every act is read back from git on the day it took effect and on the day before (`tools/check_repo.py`); both must match `corpus.json`.
- The letters and digits of every version equal those of the source document, and every article's text appears in it in order.
- Health checks: no merge commits, commit dates never go backwards, nothing dated in the future, and every commit's trailers parse.

## What "author" means

{meta['author']} The committer is always Lexifina.

## Limits

This is not an official publication. {meta['limits']}
"""
    lic = f"""The law texts in this repository are official texts of the canton of {en} ({native}).
{meta['licence_src']}

Swiss law does not protect them by copyright. Federal Act on Copyright and Related Rights (URG, SR 231.1),
Art. 5 para. 1: "Keinen urheberrechtlichen Schutz geniessen: a. Gesetze, Verordnungen, völkerrechtliche Verträge
und andere amtliche Erlasse; [...]" (French text: "Ne sont pas protégés par le droit d'auteur: a. les lois,
ordonnances, accords internationaux et autres actes officiels; [...]")

This repository is not an official publication; the binding text is the one the canton publishes as binding.

Lexifina's own contributions (the arrangement of the history, the commit messages, the tables and the tools) are
dedicated to the public domain under CC0 1.0 Universal: https://creativecommons.org/publicdomain/zero/1.0/
"""
    juris = {'path': f'ch-{code.lower()}', 'code': f'CH-{code}', 'name': en, 'level': 'canton', 'parent': 'ch',
             'repo': f'https://github.com/lexifina/switzerland-{slug}-law',
             'build': f'built: {na} acts, {nv} versions', 'language': lang, 'sources': 1}
    (repo / 'README.md').write_text(readme, encoding='utf-8', newline='\n')
    (repo / 'LICENSE').write_text(lic, encoding='utf-8', newline='\n')
    (repo / 'jurisdiction.json').write_text(json.dumps(juris, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
                                            newline='\n')


SOURCE_DOCS = {
    'geneva': {
        'holds': 'SILGENEVE publishes only the current text of each act, so each act has one version: the text in force today, dated by the latest entry into force in the act\'s own history table. It holds the constitution, the laws (lois) and the règlements in force, in the order of the systematic collection, added in parts; agreements and repealed acts are not included yet.',
        'source': 'SILGENEVE, the systematic collection of Geneva law (recueil systématique genevois, rsGE), published by the Chancellerie d\'Etat, Service de la législation, at <https://silgeneve.ch/legis/>. Each act\'s page holds its consolidated text and a history table (adoption date and entry into force of every amendment).',
        'dates': 'Each act\'s single version is dated by the latest entry into force in its history table on or before the retrieval day; it is the "oldest version available" and is credited to the publisher. Earlier wording is not held.',
        'author': 'The author of each act\'s first commit is the publisher (SILGENEVE), because the text is the current consolidation rather than the act as adopted, with an e-mail address that cannot exist.',
        'limits': 'The binding text is the one published in the Feuille d\'avis officielle and the Recueil officiel. Only the current wording is held: the history of each act is not reconstructed yet. Only the acts listed above are included.',
        'licence_src': 'Taken from SILGENEVE (https://silgeneve.ch/legis/), Chancellerie d\'Etat, Service de la législation.',
    },
}


def verify_part(slug, part, docs_date):
    probs = letters_check(slug, part)
    if probs:
        return False, f'letters: {len(probs)}: {probs[0]}'
    src = folder(slug)
    tmp = C.DOCS / f'switzerland-{slug}-law-verify'
    build = C.DOCS / f'switzerland-{slug}-law-verifybuild'
    for d in (tmp, build):
        if d.exists():
            C._rm(d)
    (tmp / 'corpus.d').mkdir(parents=True)
    names = [p.stem for p in sorted((src / 'corpus.d').glob('*.json')) if p.with_suffix('.PUBLISH').exists()] + [part]
    for n in names:
        shutil.copy2(src / 'corpus.d' / f'{n}.json', tmp / 'corpus.d' / f'{n}.json')
    write_docs(slug, docs_date, extra=[part], out=tmp / 'repo')
    build.mkdir()
    subprocess.run(['git', 'init', '-q'], cwd=build, check=True)
    env = dict(os.environ, GITLAW_NO_CHECKOUT='1')
    b = C._low([sys.executable, '-X', 'utf8', str(ROOT / 'gitlaw_common' / 'build.py'), str(tmp), '--repo', str(build),
                '--docs-date', docs_date], env=env)
    if b.returncode:
        return False, 'build failed: ' + (b.stderr or b.stdout)[-600:]
    c = C._low([sys.executable, '-X', 'utf8', str(ROOT / 'gitlaw_common' / 'check.py'), str(build), '--corpus',
                str(tmp / 'corpus.json')])
    res = json.loads(c.stdout[c.stdout.index('{'):])
    if any(res.get(k) for k in ('mismatches', 'trailer_errors', 'merges', 'backwards', 'future_dated', 'missing_in_force')):
        return False, 'check.py: ' + json.dumps({k: v for k, v in res.items() if k != 'details'})[:300]
    p = json.loads((src / 'corpus.d' / f'{part}.json').read_text(encoding='utf-8'))
    nv = sum(len(a['versions']) for a in p['acts'])
    days = sorted(v['from'] for a in p['acts'] for v in a['versions'])
    line = (f'{len(p["acts"])} act(s), {nv} versions {days[0]}..{days[-1]} ({ROMANDY[slug][3]}): letters-and-digits of '
            f'every version equal the source document and every article is found in order; scratch build of verified '
            f'parts + this part: check.py {res["versions"]} versions, 0 mismatches, 0 trailer errors, 0 merges ({docs_date}).')
    C._rm(tmp)
    C._rm(build)
    return True, line


def publish(slug, part, docs_date):
    ok, line = verify_part(slug, part, docs_date)
    if not ok:
        return 'NOT VERIFIED ' + line
    pub = folder(slug) / 'corpus.d' / f'{part}.PUBLISH'
    tmp = pub.with_suffix('.ptmp')
    tmp.write_text(line + '\n', encoding='utf-8', newline='\n')
    write_docs(slug, docs_date, extra=[part])
    os.replace(tmp, pub)
    top = folder(slug) / 'PUBLISH'
    if not top.exists():
        top.write_text('corpus.d parts are published one by one, each once its own <part>.PUBLISH is written.\n',
                       encoding='utf-8', newline='\n')
    return 'PUBLISH ' + line


# ---------------------------------------------------------------- Neuchatel (Word-filtered HTML, current text)

NE_ART = re.compile(r'^(Article premier|Art\.\s*\d+[a-zA-Z]*(?:\s?(?:bis|ter|quater|quinquies|sexies|septies|octies|novies|decies)\b)?)\s*(.*)$', re.S)


def _ne_cut(t: str) -> str:
    body = t.split('class=WordSection1', 1)[1]
    m = re.search(r'TABLE(?:\s|&nbsp;)+DES(?:\s|&nbsp;)+MATI(?:E|È|&Egrave;)RES', body)
    i = m.start() if m else -1
    if i > 0:
        body = body[:body.rfind('<p', 0, i)]
    return body


def parse_ne_doc(raw: bytes, sn: str = '101'):
    from lxml import html
    t = raw.decode('cp1252')
    body = _ne_cut(t)
    body = re.sub(r'(?is)<a\s[^>]*href="#_(?:ftn|edn)\d+"[^>]*>.*?</a>', '', body)
    body = re.sub(r'(?is)<sup>(.*?)</sup>', lambda m: m.group(1) + ' ', body)
    r = html.fromstring('<div>' + body + '</div>')
    ps = [p for p in r.iter('p')]
    units, order, outline, ingress = {}, [], [], []
    cur, marg, edition = None, None, None
    date_parts = []
    for p in ps:
        cls = p.get('class') or ''
        txt = clean(p.text_content())
        if not txt:
            continue  # empty spacer lines (xLigneBlanche); a filled one is text
        if cls == 'xEdition':
            edition = txt
            continue
        if cls == 'xDateAdoption':
            date_parts.append(txt)
            continue
        if cls == 'xNom':
            if date_parts:
                ingress.append(' '.join(date_parts))
                date_parts = []
            ingress.insert(0, '# ' + txt)
            continue
        if cls == 'MsoNormal' and cur is None and txt == sn:
            continue
        if cls in ('xTitre', 'xChapitre', 'xNomChapitre', 'xSection'):
            lvl = {'xTitre': 2, 'xChapitre': 3, 'xNomChapitre': 3, 'xSection': 4}[cls]
            outline.append('#' * lvl + ' ' + txt)
            continue
        if cls == 'xMarginale':
            if marg:
                (units[cur]['lines'] if cur else ingress).append(marg)
            marg = txt
            continue
        m = NE_ART.match(txt)
        if m and (cls == 'xNormal' or 'LVMPART' in html.tostring(p, encoding='unicode')[:400]):
            num = '1' if m.group(1) == 'Article premier' else re.sub(r'^Art\.\s*', '', m.group(1)).replace(' ', '')
            label = m.group(1).strip()
            key = art_key(num)
            b, n = key, 2
            while key in units:
                key = f'{b}-{n}'
                n += 1
            cur = key
            head = '# ' + clean(f'{label} {marg or ""}')
            units[key] = {'label': label, 'lines': [head] + ([m.group(2)] if m.group(2) else [])}
            order.append(key)
            marg = None
            continue
        if marg:
            (units[cur]['lines'] if cur else ingress).append(marg)
            marg = None
        (units[cur]['lines'] if cur else ingress).append(txt)
    if marg:
        (units[cur]['lines'] if cur else ingress).append(marg)
    out = {}
    if ingress:
        out['ingress'] = {'label': 'Titre et préambule', 'kind': 'preamble', 'text': '\n'.join(ingress) + '\n'}
    for k in order:
        out[k] = {'label': units[k]['label'], 'kind': 'art', 'text': '\n'.join(units[k]['lines']) + '\n'}
    if outline:
        out['gliederung'] = {'label': 'Structure', 'kind': 'heading', 'text': '\n'.join(outline) + '\n'}
    return out, edition


def ne_source_letters(t, sn='101'):
    body = _ne_cut(t)
    body = re.sub(r'(?is)<a\s[^>]*href="#_(?:ftn|edn)\d+"[^>]*>.*?</a>', ' ', body)
    body = re.sub(r'(?is)<p class=xEdition>.*?</p>', ' ', body)
    body = re.sub(r'(?is)^.*?<span[^>]*>\s*' + re.escape(sn) + r'\s*</span>', ' ', body, count=1)  # RSN number, page head
    return letters(htmlmod.unescape(re.sub(r'<[^>]+>', ' ', body)))


NE_BASE = 'https://rsn.ne.ch/DATA/program/books/rsne/htm/'


def ne_constitution(docs_date):
    slug = 'neuchatel'
    url = NE_BASE + '101.htm'
    raw = get(slug, url)
    units, edition = parse_ne_doc(raw)
    m = re.search(r'(\d{1,2})(?:er)?\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+(\d{4})', edition or '')
    months = 'janvier février mars avril mai juin juillet août septembre octobre novembre décembre'.split()
    frm = f'{m.group(3)}-{months.index(m.group(2)) + 1:02d}-{int(m.group(1)):02d}'
    title = 'Constitution de la République et Canton de Neuchâtel'
    act = current_only_act(slug, units, url, hashlib.sha256(raw).hexdigest(), frm, title, 'Cst. NE', '101',
                           f'Text as the Recueil systématique neuchâtelois gives it, "Etat au" {frm}; no earlier wording is held.')
    act['earlier_laws'] = ['ne-101-2000-09-24']
    pub = 'Chancellerie d\'Etat de Neuchâtel, Recueil systématique de la législation neuchâteloise (RSN)'
    part = {'country': country_block(slug, pub, url),
            'sources': [{'name': 'Recueil systématique de la législation neuchâteloise (RSN)', 'url': 'https://rsn.ne.ch/',
                         'retrieved': docs_date, 'licence': 'Art. 5 para. 1 let. a URG (SR 231.1): no copyright in acts.',
                         'notes': 'Current consolidated text of each act (HTML), "Etat au" date.'}],
            'laws': {'ne-101-2000-09-24': {
                'label': 'Cst. NE du 24 septembre 2000', 'title': title + ' du 24 septembre 2000',
                'kind': 'referendum', 'enacted': '2000-09-24', 'published': None, 'url': url,
                'temporary_until': None, 'restores': None, 'note': None}},
            'acts': [act], 'decisions': [
                'The RSN publishes only the current consolidated text, so each act has one version, the oldest version '
                'available, dated by its "Etat au" date and credited to the publisher.',
                'Each article\'s margin title (marginale) is printed after its number on the first line; section '
                'headings are kept together in gliederung.md; the title, date and preamble in ingress.md. Footnote '
                'markers and the footnotes are left out.'], 'ai_use': AI_USE}
    write_part(folder(slug) / 'corpus.d' / '10-constitution.json', part)
    return act


SOURCE_DOCS['neuchatel'] = {
    'holds': 'The RSN publishes only the current text of each act, so each act has one version: the text as the collection gives it on its "Etat au" date. It holds the constitution, the laws (lois) and the règlements in force, in the order of the systematic collection, added in parts; arrêtés, decrees, agreements and repealed acts are not included yet.',
    'source': 'The Recueil systématique de la législation neuchâteloise (RSN), published by the Chancellerie d\'Etat at <https://rsn.ne.ch/>, as the HTML edition of each act.',
    'dates': 'Each act\'s single version is dated by the "Etat au" date the RSN prints on it; it is the "oldest version available" and is credited to the publisher. Earlier wording is not held.',
    'author': 'The author of each act\'s first commit is the publisher (RSN), because the text is the current consolidation rather than the act as adopted, with an e-mail address that cannot exist.',
    'limits': 'The binding text is the one published in the Feuille officielle and the Recueil de la législation neuchâteloise. Only the current wording is held. Footnotes (which name the amending acts) are not included. Only the acts listed above are included.',
    'licence_src': 'Taken from the Recueil systématique de la législation neuchâteloise (https://rsn.ne.ch/), Chancellerie d\'Etat.',
}


def pdf_text_for_check(raw):
    raise NotImplementedError


def _vaud_letters(raw):
    import ch_vaud
    return ch_vaud.vd_source_letters(raw)


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'ge-constitution':
        a = ge_constitution(sys.argv[2])
        print(a['slug'], a['versions'][0]['from'], len(a['versions'][0]['units']))
    elif cmd == 'ne-constitution':
        a = ne_constitution(sys.argv[2])
        print(a['slug'], a['versions'][0]['from'], len(a['versions'][0]['units']))
    elif cmd == 'letters':
        pr = letters_check(sys.argv[2], sys.argv[3])
        print('\n'.join(pr[:30]) or 'clean', len(pr))
    elif cmd == 'publish':
        print(publish(sys.argv[2], sys.argv[3], sys.argv[4]))
    elif cmd == 'scaffold':
        print(C.scaffold(sys.argv[2]))
