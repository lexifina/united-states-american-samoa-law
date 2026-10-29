"""Checks corpus.json against the official CNLEGIS texts, independently of the article parser.

For every version read straight from an official text (not replayed), the letters and digits of the source between
the parse's start and stop lines must equal the letters and digits of the units put back in source order (preamble,
then each article's headings, number and body). For the two replayed versions, the changed unit's words must equal
the amending act's quoted words and every other unit must be unchanged. Writes verification.json.

    python -X utf8 verify.py
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import parse as PA  # noqa: E402

ALNUM = re.compile(r'[^0-9a-zà-öø-ÿœæ]+')


def stream(s: str) -> str:
    return ALNUM.sub('', s.lower())


def window(lines, start, stop):
    i = next(k for k, l in enumerate(lines) if re.fullmatch(start, l))
    j = next(k for k in range(i + 1, len(lines)) if re.match(stop, lines[k]))
    return lines[i:j]


def reassemble(units: dict) -> str:
    heads = {}
    for l in (units.get('structure', {}).get('text', '')).splitlines():
        m = re.fullmatch(r'(.*) \[article ([0-9.]+)\]', l)
        heads.setdefault(m.group(2), []).append(m.group(1))
    out = [units['preambule']['text']] if 'preambule' in units else []
    for k, u in units.items():
        if not k.startswith('art-'):
            continue
        first, _, body = u['text'].partition('\n')
        printed = first[len('# Article '):]
        key = '1' if printed == 'premier' else printed.replace(' ', '')
        out += heads.get(key, []) + ['Article ' + printed, body]
    return stream('\n'.join(out))


def main():
    c = json.loads((HERE / 'corpus.json').read_text(encoding='utf-8'))
    acts = {a['slug']: a for a in c['acts']}
    res = []
    checks = [
        ('constitution', 0, PA.S_CONST, '34738', r'PREAMBULE', r'Vu pour être annexé à la loi constitutionnelle n°98-001'),
        ('constitution', 1, PA.S_CONST, '39326', r'PREAMBULE', r'Vu pour être annexé à la Loi constitutionnelle n°2007-001'),
        ('constitution', 3, PA.S_CONST, '51445', r'PRÉAMBULE', r'Promulguée à Antananarivo, le 11 décembre 2010'),
        ('loi-2014-006', 0, PA.S_2014_006, '43046', r'PROMULGUE LA LOI DONT LA TENEUR SUIT ?:?',
         r'^(Promulguée à Antananarivo|Antananarivo, le)'),
        ('loi-2014-038', 0, PA.S_2014_038, '43521', r'PROMULGUE LA LOI DONT LA TENEUR SUIT ?:?',
         r'^(Promulguée à Antananarivo|Antananarivo, le)'),
    ]
    for slug, vi, search, rid, start, stop in checks:
        rows = [r for r in PA.F.search(*search, offline=True) if str(r['id']) == rid]
        src = window([PA.norm(l) for l in PA.P.lines(rows[0]['html_fichier_fr'])], start, stop)
        a = stream('\n'.join(src))
        if start.startswith('PROMULGUE'):
            a = a[len(stream(src[0])):]
        b = reassemble(acts[slug]['versions'][vi]['units'])
        ok = a == b
        res.append({'act': slug, 'from': acts[slug]['versions'][vi]['from'], 'record': rid, 'chars': len(a),
                    'equal': ok, **({} if ok else {'first_difference': next(
                        (i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))})})
    ct = acts.get('code-du-travail')
    if ct:
        rows = [r for r in PA.F.search(*PA.S_CT, offline=True) if str(r['id']) == '38022']
        src = window([PA.norm(l) for l in PA.P.lines(rows[0]['html_fichier_fr'])], checks[3][4], checks[3][5])
        a = stream('\n'.join(src))[len(stream(src[0])):]
        b = reassemble(ct['versions'][0]['units'])
        res.append({'act': 'code-du-travail', 'from': ct['versions'][0]['from'], 'record': '38022', 'chars': len(a),
                    'equal': a == b})
        # 2024: the raw pdftotext output (page-number lines dropped, "Art. 40." read as "Article 40"), not pdf_lines
        raw = PA.P.pdf_text(PA.F.CACHE / PA.hashlib.sha256(PA.CT_2024_PDF.encode()).hexdigest())
        raw = '\n'.join(re.sub(r'^Art\. (\d+)', r'Article \1', PA.norm(l)) for l in raw.replace('\f', '\n').split('\n')
                        if not re.fullmatch(r'\s*\d{1,3}\s*', l))
        i = raw.index('PROMULGUE LA LOI DONT LA TENEUR SUIT')
        j = raw.index('Promulguée à Antananarivo, le 14 août 2024')
        a = stream(raw[i:j])[len(stream('PROMULGUE LA LOI DONT LA TENEUR SUIT :')):]
        b = reassemble(ct['versions'][1]['units'])
        res.append({'act': 'code-du-travail', 'from': ct['versions'][1]['from'], 'record': '55500 (PDF)',
                    'chars': len(a), 'equal': a == b, **({} if a == b else {'first_difference': next(
                        (i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))})})
    # replayed versions: only the target unit differs, and it holds exactly the quoted words
    for slug, vi, key, rid, search, quote_re in [
            ('constitution', 2, 'art-015', '40058', PA.S_2009, r'^Article 15 \(nouveau\)\.?\s*"(.*)"$'),
            ('loi-2014-006', 1, 'art-020', '44983', PA.S_2016_031, None)]:
        v, p = acts[slug]['versions'][vi], acts[slug]['versions'][vi - 1]
        others = [k for k in set(v['units']) | set(p['units']) if k != key and
                  (v['units'].get(k) or {}).get('text') != (p['units'].get(k) or {}).get('text')]
        rows = [r for r in PA.F.search(*search, offline=True) if str(r['id']) == rid]
        lines = [PA.norm(l) for l in PA.P.lines(rows[0]['html_fichier_fr'])]
        if quote_re:
            quoted = next(re.match(quote_re, l).group(1) for l in lines if re.match(quote_re, l))
        else:
            i = next(k for k, l in enumerate(lines) if l.startswith('« Article 20 (nouveau).'))
            j = next(k for k in range(i, len(lines)) if lines[k].endswith('»'))
            quoted = '\n'.join(lines[i:j + 1])[len('« Article 20 (nouveau).'):-1]
        unit = v['units'][key]['text'].partition('\n')[2]
        res.append({'act': slug, 'from': v['from'], 'record': rid, 'replayed': key, 'other_units_changed': others,
                    'equal': stream(unit) == stream(quoted) and not others})
    out = {'checked': '2026-10-28', 'results': res, 'all_equal': all(r['equal'] for r in res)}
    (HERE / 'verification.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n', encoding='utf-8',
                                            newline='\n')
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
