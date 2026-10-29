"""List every archive.org capture under one host (any type), summarised."""
import sys, collections
sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common')
import wayback
CACHE = r'C:/Users/alany/Documents/lexifina/scripts/sao-tome-and-principe-law/.cache'
dom = sys.argv[1]
caps = wayback.captures(dom, match='domain', cache=CACHE)
print(dom, len(caps))
for c in caps:
    print(c['timestamp'], c['mimetype'][:20], c['length'], c['original'])
