"""Print the visible text of a cached HTML file (probe helper): python -X utf8 txt.py FILE [start-word] [chars]."""
import html
import re
import sys

t = open(sys.argv[1], encoding="utf-8", errors="replace").read()
t = re.sub(r"(?s)<script.*?</script>|<style.*?</style>", "", t)
t = html.unescape(re.sub(r"<[^>]+>", " ", t))
t = re.sub(r"\s+", " ", t)
i = t.find(sys.argv[2]) if len(sys.argv) > 2 else 0
n = int(sys.argv[3]) if len(sys.argv) > 3 else 4000
print(t[max(i, 0): max(i, 0) + n])
