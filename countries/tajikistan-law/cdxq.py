import sys, json; sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common'); import wayback
from pathlib import Path
C = Path(__file__).parent / '.cache'
url, flt = sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else ''
q = f'https://web.archive.org/cdx/search/cdx?url={url}&matchType=prefix&output=json&fl=timestamp,original,mimetype,statuscode,length&filter=statuscode:200&collapse=urlkey&limit=5000'
if flt: q += '&filter=original:' + flt
raw = wayback.fetch(q, C)
rows = json.loads(raw or b'[]')[1:]
print(url, len(rows))
for r in rows[:int(sys.argv[3]) if len(sys.argv) > 3 else 40]: print(' ', *r)
