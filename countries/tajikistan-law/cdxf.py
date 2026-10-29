import sys, json, urllib.parse; sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common'); import wayback
from pathlib import Path
C = Path(__file__).parent / '.cache'
host, flt = sys.argv[1], sys.argv[2]
q = f'https://web.archive.org/cdx/search/cdx?url={host}&matchType=domain&output=json&fl=timestamp,original,mimetype,statuscode,length,digest&filter=statuscode:200&collapse=digest&filter=original:{flt}'
raw = wayback.fetch(q, C)
rows = json.loads(raw or b'[]')[1:]
print('##', host, flt, len(rows), flush=True)
for r in rows: print(' ', r[0], urllib.parse.unquote(r[1])[:160], r[2], r[4], flush=True)
