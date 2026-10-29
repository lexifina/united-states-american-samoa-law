"""Fetch (or reuse from .cache/) every source Senegal's parse.py reads. Resumable: cached URLs are not refetched.

- Journal officiel (jo.gouv.sn, SPIP site, offline since about 2019): Internet Archive `id_` captures only, through
  scripts/gitlaw_common/wayback.py (shared machine-wide rate). Capture timestamps are pinned below.
- Conseil constitutionnel (conseilconstitutionnel.sn): direct, 1 request per second (robots.txt allows all but /wp-admin/).
- Vie Publique Sénégal (www.vie-publique.sn, robots.txt "Allow: /"): direct, 1 request per second; used for the laws
  that fix the default entry-into-force rule and to check that nothing later replaced the acts built.
- Commission de Protection des Données Personnelles (cdp.sn): Internet Archive captures only (the live site serves a
  bot challenge, which is never touched).

    python -X utf8 scripts/senegal-law/fetch.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sncache  # noqa: E402

# (capture timestamp, original URL) of archived pages; the Wayback `id_` form is fetched.
ARCHIVED = [
    ('20150609214903', 'http://www.jo.gouv.sn/spip.php?article6663'),      # Loi 2008-12, JO n° 6406 du 3 mai 2008
    ('20150609185104', 'http://www.jo.gouv.sn/spip.php?rubrique437'),      # JO n° 6406: table of contents
    ('20170301071202', 'http://www.cdp.sn:80/sites/default/files/protection.pdf'),  # CDP's copy of Loi 2008-12
    ('20250124135414', 'http://www.cdp.sn/content/loi-n%C2%B0-2008-12-du-25-janvier-2008-portant-sur-la-protection-des-donn%C3%A9es-%C3%A0-caract%C3%A8re'),
]
DIRECT = [
    'https://conseilconstitutionnel.sn/la-loi-organique/',
    'https://conseilconstitutionnel.sn/la-constitution/',
    'https://www.vie-publique.sn/sitemap.xml',
    'https://www.vie-publique.sn/documents/438/loi-protection-donnees-a-caractere-personnel',
    'https://www.vie-publique.sn/docs/b1d86a17-d452-4546-a8a4-3fff87c1b05a/loi-protection-donnees-a-caractere-personnel.pdf',
    'https://www.vie-publique.sn/docs/03ff08a9-aad5-46ed-b92c-db9e89e5ef53/loi-n-70-014-du-06-fevrier-1970.pdf',
    'https://www.vie-publique.sn/docs/76560e9e-ddaf-4103-8a98-90b10be2afec/loi-n-2021-21-du-02-mars-2021-fixant-les-regles-dapplicabilite-des-lois-des-actes-administratifs-a-caractere.pdf',
]


def main() -> None:
    for ts, orig in ARCHIVED:
        b = sncache.get(sncache.raw(ts, orig))
        print(len(b), ts, orig)
    for u in DIRECT:
        b = sncache.get(u)
        print(len(b), u)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
