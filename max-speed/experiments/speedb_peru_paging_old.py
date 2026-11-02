"""Speed experiment B3c: one whole older year of laws through El Peruano's search, paged 20 at a time.
No day cards exist for it, so the check is internal: rows read vs distinct ops vs the page's own totalHits.
    python -X utf8 speedb_peru_paging_old.py <cache_dir>
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
out = {'date': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'runs': []}
for tipo, ini, fin in [('LEY', '20190101', '20191231'), ('DECRETO LEGISLATIVO', '20160601', '20181231')]:
    got, rows, req, fails, t, total, start = set(), 0, 0, 0, time.time(), None, 0
    while True:
        u = (f'https://busquedas.elperuano.pe/?fechaIni={ini}&fechaFin={fin}&tipoPublicacion=NL&ci=ONLY&start={start}'
             f'&tipoDispositivo={quote(tipo)}')
        b = wayback.host_get(u, CACHE)
        req += 1
        if not b:
            fails += 1
            if fails > 3:
                break
            continue
        s = b.decode('utf-8', 'replace')
        m = re.search(r'totalHits\\",(\d+)', s)
        total = int(m.group(1)) if m else total
        ops = list(dict.fromkeys(re.findall(r'\\"op\\",\\"(\d+-\d+)\\"', s) + re.findall(r'/dispositivo/NL/(\d+-\d+)', s)))
        rows += len(ops)
        got |= set(ops)
        start += 20
        if not ops or (total is not None and start >= total) or req > 80:
            break
    out['runs'].append({'tipo': tipo, 'from': ini, 'to': fin, 'requests': req, 'failed': fails,
                        'seconds': round(time.time() - t, 1), 'total_hits': total, 'rows': rows, 'distinct': len(got)})
    print(json.dumps(out['runs'][-1]), flush=True)
Path(__file__).with_suffix('.json').write_bytes(json.dumps(out, indent=1, ensure_ascii=False).encode('utf-8'))
