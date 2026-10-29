"""Write corpus.d/50-codes.json: the codes SILEP publishes as consolidated text, read from Internet Archive captures.

Reads only the cache (.cache/, filled by wayback.get through fetch_codes.py); no network.

    python -X utf8 parse_codes.py          # writes corpus.d/50-codes.json atomically (tmp + rename)
    python -X utf8 parse_codes.py --dry    # parse and report only

Acts (see CODES): the Código Civil (SILEP norma 4451). SILEP's Código Penal page (norma 4368) is parsed for the
report only: it does not carry Ley 1390 of 2021, so it is not today's text and is not built (see DECISIONS).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import silep  # noqa: E402

CACHE = HERE / '.cache'
OUT = HERE / 'corpus.d' / '50-codes.json'
SILEP = 'http://www.silep.gob.bo/norma/{id}/ley_actualizada'
RETRIEVED = '2026-10-29'


def raw_url(norma: int, ts: str) -> str:
    return f'https://web.archive.org/web/{ts}id_/{SILEP.format(id=norma)}'


def cached(url: str) -> bytes:
    p = CACHE / hashlib.sha256(url.encode('utf-8')).hexdigest()
    if not p.exists():
        raise SystemExit(f'not in cache (run fetch_codes.py): {url}')
    return p.read_bytes()


# The act's own publisher (SCHEMA.md, "Per-act publisher"): its "oldest version available" commit and any unexplained
# change are authored by SILEP, not by the country publisher (the Gaceta Oficial, which publishes the CPE).
SILEP_PUBLISHER = {'name': 'SILEP (Vicepresidencia del Estado)', 'email': 'silep@silep.invalid'}

# One entry per act built. `capture` is the Internet Archive timestamp of the SILEP page used (pinned).
CODES = [
    {
        'slug': 'codigo-civil', 'short': 'CC', 'norma': 4451, 'capture': '20240224013706',
        'title': 'Código Civil (Decreto Ley N° 12760 de 6 de agosto de 1975)',
        'first_law': None, 'base_law': 'dl-12760',
        'expect_articles': 1570,
    },
]

# Laws SILEP names on the Código Civil page, with the promulgation dates SILEP prints.
LAWS = {
    'dl-12760': {'label': 'DL 12760', 'title': 'Decreto Ley N° 12760 de 6 de agosto de 1975, Código Civil',
                 'kind': 'decree', 'enacted': '1975-08-06'},
}
LAW_TITLES = {}  # law key -> title, when SILEP gives one


def law_key(info: dict) -> str:
    n, d = info['number'], info['date']
    if info['kind'] == 'scp':
        return f'scp-{n:04d}-{d[:4]}'
    year = d[:4] if d else None
    if year is None:
        raise SystemExit(f'no date for law {n}')
    return f'ley-{n:03d}-{year}' if n < 1000 or int(year) >= 2010 else f'ley-{n}-{year}'


def law_entry(info: dict, key: str) -> dict:
    n, d = info['number'], info['date']
    dd = f'{int(d[8:10])}/{int(d[5:7]):02d}/{d[:4]}'
    if info['kind'] == 'scp':
        return {'label': f'SCP {n}/{d[:4]}', 'title': f'Sentencia Constitucional Plurinacional {n}/{d[:4]} de {dd}',
                'kind': 'court', 'enacted': d}
    label = f'Ley {n:03d}' if n < 1000 else f'Ley {n}'
    return {'label': label, 'title': f'Ley N° {n:03d} de {dd}' if n < 1000 else f'Ley N° {n} de {dd}',
            'kind': 'law', 'enacted': d}


ART_RX = re.compile(r'^(?:EL\s+)?ART[IÍ]CULO\s+(\d+)\s*[º°]?\s*(BIS|TER|QUATER|QUINQUIES|SEXIES|SEPTIES|OCTIES|NONIES)?\b', re.I)
SUFFIX = {'bis': 2, 'ter': 3, 'quater': 4, 'quinquies': 5, 'sexies': 6, 'septies': 7, 'octies': 8, 'nonies': 9}


def art_key(first: str) -> tuple[str, str, int] | None:
    m = ART_RX.match(first)
    if not m:
        return None
    n = int(m.group(1))
    suf = (m.group(2) or '').lower()
    key = f'art-{n:04d}' + (f'-{SUFFIX[suf]}-{suf}' if suf else '')
    label = f'Art. {n}' + (f' {suf}' if suf else '')
    return key, label, n


def text_of(head: str, paras: list[str]) -> str:
    return '\n'.join([f'# {head}', *paras]) + '\n'


def build_code(code: dict, laws: dict, report: dict) -> dict:
    url = raw_url(code['norma'], code['capture'])
    raw = cached(url)
    doc = silep.parse(raw)
    units: dict[str, dict] = {}
    struct: list[str] = []
    pending: list[str] = []
    mods_by_law: dict[str, list[str]] = {}
    earlier: list[str] = [code['base_law']]
    nums: list[int] = []
    for kind, item in doc['items']:
        if kind == 'heading':
            pending += item['paras']
            if item['mods']:
                raise SystemExit(f'{code["slug"]}: a heading carries a SILEP note; handle it: {item}')
            continue
        paras = item['paras']
        if not paras:
            raise SystemExit(f'{code["slug"]}: empty block {item["id"]}')
        k = art_key(paras[0])
        if k is None:
            # SILEP replaced a repealed article's text by a note without its number ("Artículo DEROGADO por ...").
            # It takes the next number; the sequence check below confirms the gap it fills.
            if not paras[0].startswith('Artículo DEROGADO') or not nums:
                raise SystemExit(f'{code["slug"]}: block {item["id"]} has no article number: {paras[0][:80]!r}')
            n = nums[-1] + 1
            k = (f'art-{n:04d}', f'Art. {n}', n)
            report.setdefault('unnumbered_blocks', []).append({'block': item['id'], 'assigned': k[1], 'text': paras[0]})
        key, label, n = k
        if key in units:
            raise SystemExit(f'{code["slug"]}: duplicate {key}')
        if pending:
            struct += [f'{h}  [{label.lower()}]' for h in pending]
            pending = []
        nums.append(n)
        units[key] = {'label': label, 'kind': 'art', 'text': text_of(label.replace('Art.', 'Artículo'), paras)}
        for msg in item['mods']:
            info = silep.mod_info(msg)
            lk = law_key(info)
            if lk not in laws:
                laws[lk] = law_entry(info, lk)
            if info.get('title'):
                LAW_TITLES[lk] = info['title']
            mods_by_law.setdefault(lk, []).append(label)
            if lk not in earlier:
                earlier.append(lk)
    if pending:
        struct += [f'{h}  [end]' for h in pending]
    units['estructura'] = {'label': 'Estructura', 'kind': 'structure', 'text': text_of('Estructura', struct)}
    # Sequence check: every article number 1..N appears, in order (suffixed articles repeat their number).
    seq = sorted(set(nums))
    missing = sorted(set(range(1, seq[-1] + 1)) - set(seq))
    ordered = nums == sorted(nums)
    report[code['slug']] = {'source': url, 'sha256': hashlib.sha256(raw).hexdigest(), 'meta': doc['meta'],
                            'articles': len(nums), 'max_article': seq[-1], 'missing_numbers': missing,
                            'in_order': ordered, 'headings': len(struct),
                            'silep_notes': {k: v for k, v in mods_by_law.items()}}
    if missing or not ordered or (code.get('expect_articles') and seq[-1] != code['expect_articles']):
        raise SystemExit(f'{code["slug"]}: article sequence problem: {report[code["slug"]]}')
    first_from = f'{code["capture"][:4]}-{code["capture"][4:6]}-{code["capture"][6:8]}'
    notes = '; '.join(f'{laws[k]["label"]}: {", ".join(v)}' for k, v in
                      sorted(mods_by_law.items(), key=lambda kv: laws[kv[0]]['enacted']))
    earlier.sort(key=lambda k: laws[k]['enacted'])
    return {
        'slug': code['slug'], 'short': code['short'], 'title': code['title'],
        'url': SILEP.format(id=code['norma']),
        'publisher': SILEP_PUBLISHER,
        'first_law': code['first_law'], 'earlier_laws': earlier,
        'versions': [{
            'from': first_from, 'source_url': url, 'sha256': hashlib.sha256(raw).hexdigest(),
            'units': units, 'credits': {},
            'note': ('SILEP consolidated text as captured by the Internet Archive on '
                     f'{first_from}. SILEP marks these articles as last changed by: {notes}.'),
        }],
    }


def penal_report(report: dict) -> None:
    """The Código Penal page, for the record: its text and the last law SILEP lists on it."""
    caps = ['20200907201025', '20210510203809', '20211107212007', '20220610234911', '20230825213055', '20240124074843']
    texts, last = [], 0
    for ts in caps:
        doc = silep.parse(cached(raw_url(4368, ts)))
        texts.append([x['paras'] for _, x in doc['items']])
        for _, x in doc['items']:
            for m in x['mods']:
                info = silep.mod_info(m)
                if info['kind'] != 'scp' and (info['date'] or '') > str(last):
                    last = info['date']
    report['codigo-penal (not built)'] = {
        'captures': caps, 'text_identical_across_captures': all(t == texts[0] for t in texts),
        'latest_dated_law_note': last,
        'ley_1390_note': 'Ley 1390 of 27/08/2021 (SILEP norma 15931, capture 20231004042425) arts. 2-3 and '
                         'disposición derogatoria única modify, insert and repeal Código Penal articles '
                         '(34, 105, 142-147, 150-154, 157, 158, 163, 173, 174, 177, 221-225, 229; 5 bis, 23 bis/ter, '
                         '26 bis-octies, 146 ter; repeal 36, 96, 149, 150 bis, 173 bis, 228, 228 bis); '
                         'SILEP\'s Código Penal page does not show any of it.',
    }
    d = silep.parse(cached(raw_url(15931, '20231004042425')))
    report['codigo-penal (not built)']['ley_1390_checked'] = any(
        'MODIFICACIONES AL CÓDIGO PENAL' in ' '.join(x['paras']) for _, x in d['items'])


DECISIONS = [
    'Código Civil: the text is SILEP\'s consolidated page (Vicepresidencia del Estado, norma 4451), read from the '
    'Internet Archive raw capture of 2024-02-24 (silep.gob.bo does not resolve from here; Common Crawl\'s index was '
    'unreachable). It is the only consolidated Código Civil published by a Bolivian state body that we found with a '
    'text layer; the 1975 Gaceta edition exists only as scans, which the no-OCR rule excludes.',
    'Código Civil: one version only, credited to the publisher as the oldest version available. SILEP shows the '
    'current text and, per article, only the last law that changed it, never the earlier wording, so no earlier '
    'version can be rebuilt from it.',
    'Código Civil: the version is dated from the capture day (2024-02-24), the earliest day the source attests this '
    'text. SILEP\'s last recorded change is Ley 060 of 25/11/2010, but its Gaceta publication day (the in-force day '
    'under CPE art. 164.II) is not in any source we hold, so the version is not back-dated to it.',
    'Código Civil: SILEP\'s own placeholder lines for repealed articles (for example "EL ARTICULO 910 ESTA EROGADO '
    'POR LA LEY Nº 060.", arts. 909-915) are kept as printed, typo included.',
    'Código Civil: Ley 1071 of 18/06/2018 raised the Code to the rank of law without changing its words (reported '
    'in secondary sources); SILEP does not list it on the page, so it is not recorded as an event.',
    'Código Civil: SILEP stopped applying amendments to its consolidated codes around 2019-2020 (its Código Penal '
    'page lacks Ley 1390 of 2021). We know of no later law that changes the Código Civil\'s words, but a change '
    'SILEP did not record would be missing here; the README says so.',
    'Código Civil: the act names its own publisher, SILEP (Vicepresidencia del Estado), which authors its "oldest '
    'version available" commit; the country publisher (the Gaceta Oficial) authors only the CPE\'s. SILEP\'s page is '
    'headed "Datos de la Gaceta Oficial" and names "Fuente: Gaceta", but the consolidated text is SILEP\'s.',
    'Código Penal: not built. SILEP\'s page (norma 4368) is identical in every complete capture from 2020-09-07 to '
    '2024-01-24 and lacks Ley 1390 of 27/08/2021, which rewrote or added about 35 articles (SILEP\'s own page for '
    'Ley 1390, capture 2023-10-04, shows them). With no current official consolidated text, a replay could not be '
    'checked, so the Code would not be today\'s text.',
]


def main() -> None:
    dry = '--dry' in sys.argv
    laws = {k: dict(v) for k, v in LAWS.items()}
    report: dict = {}
    acts = [build_code(c, laws, report) for c in CODES]
    penal_report(report)
    for k, t in LAW_TITLES.items():
        laws[k]['title'] = t
    for v in laws.values():
        v.setdefault('published', None)
        v.setdefault('url', None)
        v.setdefault('temporary_until', None)
        v.setdefault('restores', None)
        v.setdefault('note', None)
    for a in acts:
        for k in a['earlier_laws']:
            if k == 'dl-12760':
                laws[k]['url'] = SILEP.format(id=4451)
    requests = sum(1 for line in (CACHE / 'requests.jsonl').read_text(encoding='utf-8').splitlines()
                   if 'silep.gob.bo' in line)
    part = {
        'laws': laws,
        'sources': [{
            'name': 'SILEP - Sistema de Información Legal del Estado Plurinacional (Vicepresidencia del Estado), '
                    'Internet Archive raw captures',
            'url': 'http://www.silep.gob.bo/',
            'retrieved': RETRIEVED, 'requests': requests,
            'licence': 'No licence stated. SILEP\'s footer: "Los documentos aquí presentados no pueden de ninguna '
                       'manera ser utilizados como referencia legal, pues dicha atribución corresponde a la Gaceta '
                       'Oficial de Estado." Captures read via the Internet Archive (web.archive.org, id_ form).',
            'notes': 'Pinned captures: ' + ', '.join(f'{c["slug"]} norma {c["norma"]} at {c["capture"]}' for c in CODES)
                     + '; Código Penal norma 4368 (6 captures 2020-2024) and Ley 1390 norma 15931 at 20231004042425 '
                       'read for the decision not to build the Código Penal.',
        }],
        'acts': acts,
        'decisions': DECISIONS,
        'ai_use': ['parse_codes.py and silep.py were written with a model\'s help (Claude); the legal text is copied '
                   'from the SILEP pages by the parser, never written or edited by a model.'],
    }
    (HERE / 'codes_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({k: ({kk: vv for kk, vv in v.items() if kk != 'silep_notes'} if isinstance(v, dict) else v)
                      for k, v in report.items()}, ensure_ascii=False, indent=1))
    if dry:
        return
    OUT.parent.mkdir(exist_ok=True)
    tmp = OUT.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(part, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    tmp.replace(OUT)
    print('wrote', OUT)


if __name__ == '__main__':
    main()
