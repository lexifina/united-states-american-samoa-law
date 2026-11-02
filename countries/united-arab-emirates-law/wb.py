"""Tiny CLI around the shared archive.org client: wb.py get URL [ts] | wb.py cdx URL [prefix]."""
import sys, json
sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common'); import wayback
CACHE = r'C:/Users/alany/Documents/lexifina/scripts/united-arab-emirates-law/.cache'
if sys.argv[1] == 'get':
    b = wayback.get(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else '2', cache=CACHE)
    sys.stdout.buffer.write(b or b'')
else:
    for r in wayback.captures(sys.argv[2], match=sys.argv[3] if len(sys.argv) > 3 else 'exact', cache=CACHE, collapse=None):
        print(r['timestamp'], r['statuscode'], r['mimetype'], r['length'], r['original'])
