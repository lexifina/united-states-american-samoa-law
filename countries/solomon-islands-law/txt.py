"""Debug helper: strip HTML of a cached file to text. Usage: txt.py CACHEFILE"""
import re, html, sys
s = open(sys.argv[1], 'rb').read().decode('utf-8', 'replace')
t = re.sub(r'<script.*?</script>|<style.*?</style>', '', s, flags=re.S | re.I)
t = html.unescape(re.sub(r'<[^>]+>', '', t))
sys.stdout.write(re.sub(r'\n\s*\n+', '\n', t))
