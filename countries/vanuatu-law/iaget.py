import sys
sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common'); import wayback
from pathlib import Path
CACHE = Path(__file__).parent / '.cache'
b = wayback.get(sys.argv[2], ts=sys.argv[1], cache=CACHE)
sys.stdout.buffer.write(b or b'NONE')
