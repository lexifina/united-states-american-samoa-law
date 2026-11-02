"""Shared helper for phase-2 statute parsers (PDF text layer -> numbered article units). No network, deterministic."""
import hashlib, json, re
import pymupdf

HEAD = re.compile(r'^\s*(LIVRE|TITRE|CHAPITRE|SECTION|SOUS-SECTION|PARTIE)|^\s*(Livre|Titre|Chapitre|Section|Sous-section|Partie)\s+(\d+|préliminaire|premier|unique|[IVXLC]+)|^\s*§')
ART = re.compile(r'^\s*(?:ARTICLES?|Articles?|ART|Art)\s*\.?\s*(premier|1er|1ER|PREMIER|\d+)\s*(bis|ter|quater|quinquies)?\s*(?:[.:\-–—)]+)?\s*(.*)$')


def norm(s):
    s = s.replace('\u00a0', ' ').replace('\u2019', "'").replace('\u2018', "'").replace('\u2013', '-').replace('\u2014', '-')
    s = s.replace('‐', '-').replace('‑', '-').replace('−', '-').replace('­', '').replace('﻿', '')
    return re.sub(r'\s{2,}', ' ', s).strip()


INLINE = re.compile(r'\s(?=Art\.\s?(?:\d+|1er)(?:\s?(?:bis|ter|quater|quinquies|sexies))?\s?\.\s?-)')


def pdf_lines(path, skip=lambda l: False, first_page=0, last_page=None, inline=False):
    d = pymupdf.open(path)
    out = []
    for p in list(d)[first_page:last_page]:
        for l in p.get_text().split('\n'):
            n = norm(l)
            for n in (INLINE.sub(chr(10), n).split(chr(10)) if inline else [n]):
                if n and not skip(n):
                    out.append(n)
    merged = []
    for n in out:
        if merged and merged[-1] in ('-', '•', '', ''):
            merged[-1] = '- ' + n
        else:
            merged.append(n)
    return merged


def paragraphs(lines):
    out, cur = [], ''
    for ln in lines:
        if re.match(r'^(-|\d+[-.)°]|[a-z][-.)]|[ivx]+[-.)]) ', ln) and cur:
            out.append(cur); cur = ''
        cur = (cur + ' ' + ln).strip()
        if len(ln) < 70 and ln[-1:] in '.;:':
            out.append(cur); cur = ''
    if cur:
        out.append(cur)
    return out


def articles(lines, start_after=0, expect_first=1, max_gap=12):
    """Return ordered [(num, suffix, first_text, body_lines)] for the longest ascending run of article markers."""
    cands = []
    for i, l in enumerate(lines):
        if i < start_after:
            continue
        m = ART.match(l)
        if m and not re.match(r"^(à|au|et|a)\s+(l')?[Aa]rt", m.group(3)):
            g = m.group(1)
            n = 1 if g.lower() in ('premier', '1er') else int(g)
            cands.append((i, n, m.group(2) or '', re.sub(r'^[-–—]+\s*', '', m.group(3))))
    # greedy chain from the first candidate numbered expect_first (last such candidate that yields the longest chain)
    best = []
    for s, c in enumerate(cands):
        if c[1] != expect_first or c[2]:
            continue
        chain, last = [c], c[1]
        for d in cands[s + 1:]:
            if d[1] == last and d[2] and not any(x[1] == d[1] and x[2] == d[2] for x in chain):
                chain.append(d); continue
            if last < d[1] <= last + max_gap:
                chain.append(d); last = d[1]
        if len(chain) > len(best):
            best = chain
    res = []
    for k, (i, n, suf, rest) in enumerate(best):
        j = best[k + 1][0] if k + 1 < len(best) else len(lines)
        body = [rest] if rest else []
        body += lines[i + 1:j]
        for t, l in enumerate(body):
            if HEAD.match(l) and t > 0 or (t == 0 and HEAD.match(l)):
                body = body[:t]; break
        res.append((n, suf, body))
    return res


def units_from(arts, last_label_fn=None):
    units = {}
    for n, suf, body in arts:
        key = f'art-{n:03d}' + (f'-{suf}' if suf else '')
        label = f'Art. {n}' + (f' {suf}' if suf else '')
        if key in units:
            continue
        ps = paragraphs([b for b in body if b])
        units[key] = {'label': label, 'kind': 'art', 'text': f'# Article {n}' + (f' {suf}' if suf else '') + '\n' + '\n'.join(ps) + '\n'}
    return units


def gaps(arts):
    nums = sorted({n for n, s, b in arts})
    return [x for x in range(nums[0], nums[-1] + 1) if x not in set(nums)]


def sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def write_part(path, act, source, decisions, ai_use=None):
    """Write one corpus.d part holding a single act."""
    import pathlib
    part = {'acts': [act], 'sources': [source], 'decisions': decisions,
            'ai_use': ai_use or ['Claude Code wrote the code and chose the source; it did not write or alter any legal text. The code is deterministic and runs no model.']}
    pathlib.Path(path).parent.mkdir(exist_ok=True)
    open(path, 'w', encoding='utf-8', newline=chr(10)).write(json.dumps(part, ensure_ascii=False, indent=1) + chr(10))


def make_act(slug, short, title, url, frm, units, sha256, note):
    return {'slug': slug, 'short': short, 'title': title, 'url': url, 'first_law': None, 'earlier_laws': [],
            'versions': [{'from': frm, 'source_url': url, 'sha256': sha256, 'units': units, 'credits': {}, 'note': note}]}


def update_docs(folder, slug, folder_label, act_row, source_row, bullet=None, license_text=None, build_note=None):
    """Idempotently add an act row, a source row, a limits bullet and a LICENSE paragraph to repo/ docs."""
    import pathlib
    nl = chr(10)
    repo = pathlib.Path(folder) / 'repo'
    rd = repo / 'README.md'
    t = open(rd, encoding='utf-8', newline='').read().replace(chr(13) + nl, nl)
    if f'| `{slug}/` |' not in t:
        # act row after the last row of the "What is in it now" table
        i = t.index('| Folder | Act |')
        j = t.index(nl + nl, i)
        t = t[:j] + nl + act_row + t[j:]
    if source_row not in t:
        i = t.index('| Source | What | Notes |')
        j = t.index(nl + nl, i)
        t = t[:j] + nl + source_row + t[j:]
    if bullet and bullet not in t:
        k = t.index('## How it is built')
        t = t[:k].rstrip(nl) + nl + bullet + nl + nl + t[k:]
    t = t.replace('; no statute is built yet.', '; statutes are added below.').replace('- **Statutes.** No Mauritanian statute is included yet.' + nl, '')
    open(rd, 'w', encoding='utf-8', newline=nl).write(t)
    if license_text:
        lp = repo / 'LICENSE'
        lt = open(lp, encoding='utf-8', newline='').read().replace(chr(13) + nl, nl)
        if license_text not in lt:
            k = lt.find('Changes made by Lexifina')
            lt = (lt[:k] + license_text + nl + nl + lt[k:]) if k >= 0 else lt.rstrip(nl) + nl + nl + license_text + nl
            open(lp, 'w', encoding='utf-8', newline=nl).write(lt)
    jp = repo / 'jurisdiction.json'
    j = json.load(open(jp, encoding='utf-8'))
    if build_note:
        j['build'] = build_note
    j['sources'] = sum(1 for l in t.split(nl) if l.startswith('| ['))
    open(jp, 'w', encoding='utf-8', newline=nl).write(json.dumps(j, ensure_ascii=False, indent=2) + nl)
