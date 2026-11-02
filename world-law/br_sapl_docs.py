"""Private. Writes docs-spec.json and repo/README.md, LICENSE, jurisdiction.json for a SAPL wave city from its
sapl-spec.json and the corpus.d parts that have .PUBLISH (gitlaw-scraper-dell, 2026-11-01).

    python -X utf8 scripts/world-law/br_sapl_docs.py <folder>
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from br_city_docs import write  # noqa: E402

SCRIPTS = Path(__file__).resolve().parents[1]
STATES = {'SP': 'São Paulo', 'MG': 'Minas Gerais', 'RJ': 'Rio de Janeiro', 'PR': 'Paraná', 'PE': 'Pernambuco',
          'BA': 'Bahia', 'CE': 'Ceará', 'MS': 'Mato Grosso do Sul', 'PA': 'Pará',
          'GO': 'Goiás', 'ES': 'Espírito Santo', 'RS': 'Rio Grande do Sul', 'SC': 'Santa Catarina',
          'RN': 'Rio Grande do Norte', 'PB': 'Paraíba', 'SE': 'Sergipe', 'MA': 'Maranhão', 'RO': 'Rondônia',
          'TO': 'Tocantins', 'AP': 'Amapá', 'AM': 'Amazonas', 'MT': 'Mato Grosso', 'AC': 'Acre', 'AL': 'Alagoas'}
STATE_REPO = {'SP': 'brazil-sao-paulo-law', 'MG': 'brazil-minas-gerais-law',  # RJ, PE: no public state repo yet
              'PR': 'brazil-parana-law', 'BA': 'brazil-bahia-law',
              'CE': 'brazil-ceara-law', 'MS': 'brazil-mato-grosso-do-sul-law', 'PA': 'brazil-para-law',
              'GO': 'brazil-goias-law', 'RO': 'brazil-rondonia-law', 'TO': 'brazil-tocantins-law', 'AL': 'brazil-alagoas-law'}


def main(folder):
    F = SCRIPTS / folder
    s = json.loads((F / 'sapl-spec.json').read_text(encoding='utf-8'))
    parts = [p for p in sorted((F / 'corpus.d').glob('*.json')) if p.with_suffix('.PUBLISH').exists()]
    lom_versions, laws = 0, 0
    for p in parts:
        c = json.loads(p.read_text(encoding='utf-8'))
        for a in c['acts']:
            if a['slug'] == 'lei-organica':
                lom_versions = len(a['versions'])
            else:
                laws += 1
    city, uf, host = s['city'], s['uf'], s['host']
    rows = ['| Folder | Act | Versions |', '| --- | --- | ---: |']
    pdf = s.get('lom_pdf')
    if lom_versions and pdf:
        rows.append(f'| `lei-organica/` | {pdf["label"]} | 1 ({"as promulgated" if pdf["mode"] == "enacted" else "text in force as compiled"}) |')
    elif lom_versions:
        rows.append(f'| `lei-organica/` | Lei Orgânica do Município de {city} ({s["lom_year"]}) and every amendment the '
                    f"Câmara's SAPL records | one per period of vigência ({lom_versions}) |")
    if laws:
        rows.append(f'| `lei-*/`, `lc-*/` | Municipal laws (Leis and Leis Complementares), newest first | one each, '
                    f'as enacted ({laws}) |')
    what = []
    if lom_versions and pdf:
        what.append(f'**The Lei Orgânica.** {pdf["decisions"][0]}')
    elif lom_versions:
        what.append("**The Lei Orgânica with its history.** The Câmara's SAPL keeps the Lei Orgânica as a structured "
                    'text with a view of the text in force for each period between amendments, so each amendment is a '
                    'commit on the day its period starts, credited to the Emenda à Lei Orgânica that gave it.')
    if laws:
        what.append("**Municipal laws, newest first.** Each law the Câmara's SAPL lists with a PDF that has a text layer "
                    'of its own, as enacted, credited to itself. Laws are added in parts, working back in time; later '
                    'amendments by other laws are not worked into earlier laws. Scans and laws that take effect on '
                    'another day than their publication are left out.')
    sr = STATE_REPO.get(uf)
    holds = '\n'.join(rows) + '\n\n' + '\n\n'.join(what) + (
        (f'\n\nState law is in [{sr}](https://github.com/lexifina/{sr}); federal' if sr else '\n\nFederal')
        + ' law is in [brazil-law](https://github.com/lexifina/brazil-law).')
    dates = []
    if lom_versions and pdf:
        dates.append(pdf['rule'])
    elif lom_versions:
        dates.append(f'The first version of the Lei Orgânica is the text SAPL gives in force from {s["lom_date"]}. Each '
                     'later version is dated by the first day of the period of vigência SAPL gives it and credited to the '
                     'act SAPL names for it ("Dada por ..."); a period SAPL starts without naming an act is committed as '
                     'a publisher commit, not guessed.')
    if laws:
        dates.append('Each law is dated by the publication date SAPL records for it (else by its own date), and only laws '
                     'whose own vigência clause says they take effect on their publication (or signature) are taken in '
                     '(Decreto-Lei 4.657/1942, art. 1, would otherwise give 45 days).')
    dates.append(f'Commits are at noon in {city}.')
    built = []
    if lom_versions and pdf:
        built.append(pdf['decisions'][-1])
    elif lom_versions:
        built.append('Each SAPL view of the Lei Orgânica becomes one file per Art.; each provision is one line, its label '
                     'followed by its text; headings stand above the first article under them. The notes SAPL keeps under '
                     'a provision or links into it ("Inclusão feita pelo ..."), provisions it marks as superseded, the '
                     "amending acts' own blocks it shows inside the text and amendment notes typed into the text "
                     '("(Redação dada pela Emenda ...)") are left out.')
    if laws:
        built.append("Each law's PDF is read from its heading to the closing line that ends in its date (signatures after "
                     'it are left out); lines repeated at the top or bottom of two or more pages and page numbers are '
                     'left out; lines are joined into paragraphs, one file per Art.')
    spec = {
        'name': f'{city} (city)', 'full': f'the Município de {city}, {STATES[uf]}', 'code': s['code'],
        'slug': s['slug'], 'parent': f'br-{uf.lower()}', 'official': f'Diário Oficial do Município de {city}',
        'publisher': f'Câmara Municipal de {city}', 'site': f'Câmara Municipal de {city}, SAPL',
        'site_url': f'https://{host}/' + (f'norma/{s.get("norma") or (pdf or {}).get("norma")}' if lom_versions else 'norma/pesquisar'),
        'holds': holds, 'dates': ' '.join(dates), 'built': ' '.join(built),
        'limits': ("The record is SAPL's: a version is only as exact as the Câmara's text for it. "
                   + ('Only the newest laws are in so far; older ones follow in later parts. ' if laws else
                      'Ordinary and complementary laws are not in yet. ')
                   + 'The text is not the official version: only the Diário Oficial do Município is authoritative.'),
        'build': f'built: the law of {city} from the Câmara Municipal\'s SAPL',
        'terms': ('- SAPL (the source): "Conteúdo e dados sob licença Creative Commons 4.0 Atribuir Fonte - '
                  'Compartilhar Igual" (CC BY-SA 4.0): source credited above.\n'),
    }
    (F / 'docs-spec.json').write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
    write(str(F), spec)
    print('docs', folder, 'lom', lom_versions, 'laws', laws)


if __name__ == '__main__':
    main(sys.argv[1])
