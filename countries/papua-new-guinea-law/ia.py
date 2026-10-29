"""Fetch one archive.org id_ capture into .cache and print its cache path: python ia.py <url> <ts>"""
import sys, hashlib
sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common'); import wayback
from pathlib import Path
CACHE = Path(__file__).parent / '.cache'
b = wayback.get(sys.argv[1], ts=sys.argv[2], cache=CACHE)
out = Path(sys.argv[3]) if len(sys.argv) > 3 else None
print(len(b) if b else None)
if out and b: out.write_bytes(b)
