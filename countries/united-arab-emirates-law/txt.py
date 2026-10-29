import re, html, sys
t = open(sys.argv[1], encoding='utf8').read()
t = re.sub(r'<script.*?</script>|<style.*?</style>', '', t, flags=re.S)
t = re.sub(r'<(br|/p|/div|/li|/h\d)[^>]*>', '\n', t)
t = html.unescape(re.sub(r'<[^>]+>', ' ', t))
t = re.sub(r'[ \t\xa0]+', ' ', t); t = re.sub(r'\n\s*\n+', '\n', t)
print(t)
