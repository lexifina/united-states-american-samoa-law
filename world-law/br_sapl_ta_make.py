"""Private. Writes scripts/<folder>/parse.py and check_letters.py for a Câmara whose SAPL keeps the Lei Orgânica as a
Texto Articulado, from the Fortaleza build (gitlaw-scraper-dell, municipal tier, 2026-10-31).

    python -X utf8 scripts/world-law/br_sapl_ta_make.py <spec.json>

spec: folder, host, norma (5353), ta (641), city (Boa Vista), code (BR-RR-BOA-VISTA), slug (brazil-boa-vista-city),
tz (America/Boa_Vista), email_domain, lom_date (1992-07-11), lom_year (1992), lom_label, lom_title, adt_note.
"""
import json, re, shutil, sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
s = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
src = (SCRIPTS / 'brazil-fortaleza-city-law' / 'parse.py').read_text(encoding='utf-8')
EN = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November',
      'December']
y, m, d = s['lom_date'].split('-')
en_date = f'{int(d)} {EN[int(m) - 1]} {y}'
rep = [
    ('for the Município de Fortaleza from', f"for the Município de {s['city']} from"),
    ('SAPL keeps the Lei Orgânica (2006) as a "Texto Articulado" (TA 44)',
     f'SAPL keeps the Lei Orgânica ({s["lom_year"]}) as a "Texto Articulado" (TA {s["ta"]})'),
    ('("/ta/44/text/vigencia/', f'("/ta/{s["ta"]}/text/vigencia/'),
    ("r'/ta/44/text/vigencia/", f"r'/ta/{s['ta']}/text/vigencia/"),
    ("'code': 'BR-CE-FORTALEZA', 'name': 'Fortaleza', 'slug': 'brazil-fortaleza-city'",
     f"'code': '{s['code']}', 'name': '{s['city']}', 'slug': '{s['slug']}'"),
    ("'tz': 'America/Fortaleza'", f"'tz': '{s['tz']}'"),
    ("'Câmara Municipal de Fortaleza (SAPL)', 'email': 'sapl@cmfor.ce.gov.br.invalid'",
     f"'Câmara Municipal de {s['city']} (SAPL)', 'email': 'sapl@{s['email_domain']}.invalid'"),
    ("https://sapl.fortaleza.ce.leg.br/norma/5257", f"https://{s['host']}/norma/{s['norma']}"),
    ("'Text: Câmara Municipal de Fortaleza, SAPL", f"'Text: Câmara Municipal de {s['city']}, SAPL"),
    ("'do Município de Fortaleza, sapl.fortaleza.ce.leg.br.", f"'do Município de {s['city']}, {s['host']}."),
    ("'(from 15 December 2006) is credited", f"'(from {en_date}) is credited"),
    ("""    'The last version is the text SAPL shows as in force now (the norma page, "Vigência a partir de 30 de Junho de 2025", '
    '"Dada por" Emenda à Lei Orgânica nº 25). Where SAPL starts a period without naming an amending act (from 27 August '
    '2021), the units that changed are left uncredited and committed as publisher commits, not guessed.',""",
     """    'When the text SAPL shows as in force now (the norma page, with its "Vigência a partir de" day and "Dada por" '
    'act) starts after the last view, it is the last version. Where SAPL starts a period without naming an amending '
    'act, the units that changed are left uncredited and committed as publisher commits, not guessed.',"""),
    ("'/norma/5257'", f"'/norma/{s['norma']}'"),
    ("'lom-2006'", f"'lom-{s['lom_year']}'"),
    ("'Lei Orgânica do Município de Fortaleza, de 15 de dezembro de 2006'", repr(s['lom_label'])),
    ("'Dispõe sobre a Lei Orgânica do Município de Fortaleza.'", repr(s['lom_title'])),
    ("'enacted': '2006-12-15', 'published': '2006-12-15'", f"'enacted': '{s['lom_date']}', 'published': None"),
    ("startswith('Lei Orgânica nº 1')", "startswith('Lei Orgânica')"),
    ("'short': 'LOM-Fortaleza', 'title': 'Lei Orgânica do Município de Fortaleza'",
     f"'short': 'LOM-{s['city'].replace(' ', '-')}', 'title': 'Lei Orgânica do Município de {s['city']}'"),
    ("'Câmara Municipal de Fortaleza, SAPL: Texto Articulado", f"'Câmara Municipal de {s['city']}, SAPL: Texto Articulado"),
    ("BASE = 'https://sapl.fortaleza.ce.leg.br'", f"BASE = 'https://{s['host']}'"),
    # other Câmaras word the amending acts "Emenda a/- Lei Orgânica Municipal nº ..." (2026-11-01)
    ("r'Emenda à Lei Orgânica nº", r"r'Emenda\s*(?:à|a|-)?\s*Lei Org[âa]nica(?:\s+Municipal|\s+do\s+Munic[íi]pio)?(?:-\w+)?\s+nº"),
]
# Some Câmaras amend the Lei Orgânica by other acts too ("Lei Ordinária nº 1.012, de 15 de março de 1994", Santa Cruz
# do Capibaribe, 2026-11-01): SAPL names that act as the one that gave the period, so it is credited, keyed by its kind.
rep.append(("""    if not m:
        return None, None
    d = f'{m.group(5)}""", """    if not m:
        g = re.search(r'^(Lei Complementar|Lei Ordinária|Lei Municipal|Lei|Resolução|Decreto Legislativo)\\s*(?:-\\w+)?\\s+'
                      r'nº\\s*([\\d.]+), de (\\d{1,2}) de (\\w+) de (\\d{4})', label)
        if not g or g.group(4).lower() not in MONTHS:
            return None, None
        kind = {'Lei Complementar': 'lc', 'Resolução': 'res', 'Decreto Legislativo': 'dl'}.get(g.group(1), 'lei')
        d = f'{g.group(5)}-{MONTHS[g.group(4).lower()]:02d}-{int(g.group(3)):02d}'
        return f'ta-{kind}-{g.group(5)}-{int(g.group(2).replace(".", "")):05d}', d  # own key: laws.py labels differ
    d = f'{m.group(5)}"""))
if s.get('laws'):  # the folder also has laws.py (SAPL municipal wave, 2026-11-01): one rule for both
    rep.append(("this record dates each version by the first day of vigência SAPL gives it.'",
                "this record dates each version by the first day of vigência SAPL gives it. Municipal laws: '\n"
                "                'Decreto-Lei 4.657/1942 (LINDB) art. 1 gives 45 days unless a law says otherwise; this record '\n"
                "                'takes in only laws whose vigência clause says they take effect on their publication (or '\n"
                "                'signature) and dates each by the publication date SAPL records for it (else by its date).'"))
for a, b in rep:
    if a not in src:
        sys.exit(f'template text not found: {a[:70]!r}')
    src = src.replace(a, b)
if 'adt_note' in s:
    src = src.replace(
        """    'One file per Art.; headings stand above the first article under them; the "Ato das Disposições Orgânicas '
    'Transitórias", numbered from 1 again, is adt-*. "000-titulo" holds the preamble.',""", s['adt_note'])
# Some Câmaras type their own amendment notes into the text ("(Redação dada pela Emenda à Lei Orgânica nº 93/2025)",
# São Vicente, 2026-11-01): editorial notes, never law text. Left out in parse.py and in check_letters.py alike.
NOTE_RE = (r"r'\(\s*(?:Reda[çc][ãa]o\s+dada|Reda[çc][ãa]o\s+alterada|Inclu[íi]d[oa]s?|Acrescid[oa]s?|"
           r"Acrescentad[oa]s?|Revogad[oa]s?|Alterad[oa]s?|Suprimid[oa]s?|Renumerad[oa]s?|Vide)\b[^()]*?"
           r"(?:Emenda|Lei|ELO|Resolu|n\.?\s*[º°o])[^()]*\)'")
a = "            ls = [l for l in ls if l and re.search(r'\\w', l)]\n"
if a not in src:
    sys.exit('template text not found: flush lines')
src = src.replace(a, "            ls = [norm(EDNOTE.sub(' ', l)).strip() for l in ls]  # the Câmara's typed amendment notes\n" + a)
src = src.replace("BLOCK = {", f"EDNOTE = re.compile({NOTE_RE}, re.I)\nBLOCK = {{", 1)
a = "    'provisions it marks as superseded and the amending acts own blocks it shows inside the text are left out.',"
if a not in src:
    sys.exit('template text not found: decision on notes')
src = src.replace(a, "    'provisions it marks as superseded, the amending acts own blocks it shows inside the text and the amendment '\n"
                     "    'notes typed into the text (\"(Redação dada pela Emenda ...)\", \"(Incluído pela ...)\") are left out.',")
left = [w for w in ('Fortaleza', '5257', 'ta/44') if w in src]
if left:
    sys.exit(f'Fortaleza-specific text left: {left}')
out = SCRIPTS / s['folder']
(out / 'parse.py').write_text(src, encoding='utf-8', newline='\n')
ck = (SCRIPTS / 'brazil-fortaleza-city-law' / 'check_letters.py').read_text(encoding='utf-8')
a = "    return html.unescape(re.sub(r'<[^>]+>', ' ', ' '.join(out)))\n"
if a not in ck:
    sys.exit('check_letters template text not found')
ck = ck.replace(a, "    t = html.unescape(re.sub(r'<[^>]+>', ' ', ' '.join(out)))\n"
                   f"    return re.sub({NOTE_RE}, ' ', t, flags=re.I)  # the Câmara's typed amendment notes\n")
ck = ck.replace("and SAPL's \"nota-alteracao\" links.", "and SAPL's \"nota-alteracao\" links, and amendment notes typed into the text\n(\"(Redação dada pela Emenda ...)\").")
(out / 'check_letters.py').write_text(ck, encoding='utf-8', newline='\n')
shutil.copy(SCRIPTS / 'world-law' / 'br_lib.py', out / 'br_lib.py')
print('wrote', out / 'parse.py')
