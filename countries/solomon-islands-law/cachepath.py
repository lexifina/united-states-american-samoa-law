"""Print the cache path the shared client uses for a key (gitlaw-SB helper)."""
import sys
from pathlib import Path
sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common')
import wayback
for k in sys.argv[1:]:
    print(wayback._cached(Path(r'C:/Users/alany/Documents/lexifina/scripts/solomon-islands-law/.cache'), k))
