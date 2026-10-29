"""List archive.org CDX captures under a prefix (gitlaw-SB probe). Usage: probe_ia.py URL [match]"""
import json, sys, os
sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common')
import wayback
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.cache')
caps = wayback.captures(sys.argv[1], match=sys.argv[2] if len(sys.argv) > 2 else 'prefix', cache=CACHE)
out = os.path.join(CACHE, 'ia-' + sys.argv[1].replace('/', '_').replace(':', '') + '.json')
json.dump(caps, open(out, 'w'), indent=0)
print(len(caps), out)
