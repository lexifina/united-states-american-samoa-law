"""Probe archive.org for official São Tomé and Príncipe domains (one CDX request each)."""
import sys, json
sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common')
import wayback
CACHE = r'C:/Users/alany/Documents/lexifina/scripts/sao-tome-and-principe-law/.cache'
for dom in sys.argv[1:]:
    caps = wayback.captures(dom, match='domain', cache=CACHE)
    pdfs = [c for c in caps if 'pdf' in c['mimetype'] or c['original'].lower().endswith('.pdf')]
    print(dom, len(caps), 'pdfs', len(pdfs))
    for c in pdfs:
        print('  ', c['timestamp'], c['length'], c['original'])
