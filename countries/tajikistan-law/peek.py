import sys,re; sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common'); import wayback
from pathlib import Path
url, ts = sys.argv[1], sys.argv[2]
n = int(sys.argv[3]) if len(sys.argv) > 3 else 3000
b=wayback.get(url, ts=ts, cache=Path(__file__).parent/'.cache')
print(len(b) if b else None)
t=None
for enc in ('utf-8','cp1251'):
  try: t=b.decode(enc); print(enc); break
  except Exception: pass
t=re.sub(r'(?is)<script.*?</script>|<style.*?</style>','',t)
print(re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',t))[:n])
print(re.findall(r'href="([^"]+)"',t)[:40])
