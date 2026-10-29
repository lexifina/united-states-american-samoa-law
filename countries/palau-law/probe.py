"""Probe archives for official Palau hosts: list archive.org CDX captures by prefix (one request per host).

    python -X utf8 scripts/palau-law/probe.py palausupremecourt.net palaujudiciary.org ...
Writes .cache/probe-<host>.json with every capture (status 200, collapsed by digest).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common')
import wayback  # noqa: E402

CACHE = Path(__file__).resolve().parent / '.cache'

for host in sys.argv[1:]:
    caps = wayback.captures(host + '/', match='prefix', cache=CACHE)
    (CACHE / f'probe-{host.replace("/", "_")}.json').write_text(json.dumps(caps, indent=0), encoding='utf-8')
    pdfs = [c for c in caps if c['original'].lower().split('?')[0].endswith('.pdf') or 'pdf' in c['mimetype']]
    print(host, 'captures', len(caps), 'pdfs', len(pdfs))
