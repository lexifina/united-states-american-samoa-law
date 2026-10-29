"""Fetch one archive.org id_ capture into the cache and copy it to .cache/dl/<name>."""
import sys, shutil
sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common')
import wayback
CACHE = r'C:/Users/alany/Documents/lexifina/scripts/sao-tome-and-principe-law/.cache'
url, ts, name = sys.argv[1:4]
b = wayback.get(url, ts=ts, cache=CACHE)
print(len(b) if b else None)
if b:
    open(CACHE + '/dl/' + name, 'wb').write(b)
