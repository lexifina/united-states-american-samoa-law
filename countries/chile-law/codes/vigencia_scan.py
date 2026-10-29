"""Lists acts whose own text defers their entry into force while LeyChile dates their first version from publication.

    python -X utf8 scripts/chile-law/codes/vigencia_scan.py [slug...]      # default: every act in fetch_codes.CHAINS

For each act's first LeyChile norm it prints the publication day (metadatos), LeyChile's first version day, and every
sentence of the original text (first version) that speaks of the act's own entry into force ("entrará en vigencia",
"comenzará a regir", "regirá", "vigencia" with a time phrase). Reading the hits is a manual step; parse_codes.py
VIGENCIA records the acts where the text gives a later day, with the quoted words.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import fetch  # noqa: E402
import parse  # noqa: E402
from fetch_codes import CHAINS  # noqa: E402

CLAUSE = re.compile(r'(?i)[^.]*\b(entrar[aá]n? en vigencia|entrar[aá]n? a regir|comenzar[aá]n? a regir|'
                    r'regir[aá]n? (?:desde|a contar|a partir)|empezar[aá]n? a regir|vigencia\b[^.]{0,40}'
                    r'(?:meses|d[ií]as|a[nñ]os|a contar|a partir|desde))[^.]*\.')


def scan(slug: str) -> None:
    idn = CHAINS[slug][0]
    vs = fetch.versions(idn, offline=True)
    raw = fetch.fetch(fetch.version_url(idn, vs[0]['@vigenteDesde']), offline=True)
    meta = json.loads(raw).get('metadatos') or {}
    units = parse.read_version(raw, 4)['units']
    hits = []
    for k, u in units.items():
        for m in CLAUSE.finditer(u['text'].replace('\n', ' ')):
            s = m.group(0).strip()
            if re.search(r'(?i)(presente|esta) (ley|c[oó]digo|decreto)|este c[oó]digo|la presente', s):
                hits.append(f'{k}: {s[:300]}')
    print(json.dumps({'act': slug, 'norm': idn, 'published': meta.get('fecha_publicacion'),
                      'leychile_first': vs[0]['@vigenteDesde'], 'second': vs[1]['@vigenteDesde'] if len(vs) > 1 else None,
                      'clauses': hits[:6]}, ensure_ascii=False))


if __name__ == '__main__':
    for s in (sys.argv[1:] or list(CHAINS)):
        scan(s)
