"""Speed experiment B3b: does paging a whole month of El Peruano's search (one law type) lose or repeat cards?

peru-law split every range into single days because long ranges dropped and repeated cards, which cost it 2,088
requests. This pages one month per type and compares with peru-law's own day-by-day cards (read-only).
    python -X utf8 speedb_peru_paging.py <cache_dir>
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common')
import wayback  # noqa: E402

CACHE = Path(sys.argv[1])
PE = Path(r'C:/Users/alany/Documents/lexifina/scripts/peru-law')
cards = [json.loads(l) for l in (PE / 'penal/.tmp/daycards_2026.jsonl').read_text(encoding='utf-8').splitlines() if l]
out = {'date': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'runs': []}
for tipo, ini, fin in [('LEY', '20260301', '20260331'), ('LEY', '20260401', '20260630'),
                       ('DECRETO LEGISLATIVO', '20260101', '20261028'), ('DECRETO DE URGENCIA', '20260301', '20260531')]:
    want = {c['op'] for c in cards if c['tipo'] == tipo and c['pub'] == 'NL' and ini <= c['day'] <= fin}
    got, seen_rows, req, t, total = set(), 0, 0, time.time(), None
    start = 0
    while True:
        u = (f'https://busquedas.elperuano.pe/?fechaIni={ini}&fechaFin={fin}&tipoPublicacion=NL&ci=ONLY&start={start}'
             f'&tipoDispositivo={quote(tipo)}')
        b = wayback.host_get(u, CACHE)
        req += 1
        if not b:
            break
        s = b.decode('utf-8', 'replace')
        m = re.search(r'totalHits\\",(\d+)', s)
        total = int(m.group(1)) if m else total
        ops = list(dict.fromkeys(re.findall(r'\\"op\\",\\"(\d+-\d+)\\"', s) + re.findall(r'/dispositivo/NL/(\d+-\d+)', s)))
        seen_rows += len(ops)
        got |= set(ops)
        start += 20
        if not ops or (total is not None and start >= total) or req > 60:
            break
    out['runs'].append({'tipo': tipo, 'from': ini, 'to': fin, 'requests': req, 'seconds': round(time.time() - t, 1),
                        'total_hits': total, 'rows': seen_rows, 'distinct': len(got), 'day_cards': len(want),
                        'in_both': len(want & got), 'missed': sorted(want - got)[:10], 'extra': sorted(got - want)[:10],
                        'day_requests_peru_law_would_use': len({c['day'] for c in cards if ini <= c['day'] <= fin})})
    print(json.dumps(out['runs'][-1]), flush=True)
Path(__file__).with_suffix('.json').write_bytes(json.dumps(out, indent=1, ensure_ascii=False).encode('utf-8'))
