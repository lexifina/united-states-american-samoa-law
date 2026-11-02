import sys, re
sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/world-law')
import ar_provinces as E
B = 'https://sibom.slyt.gba.gob.ar'
cid = int(sys.argv[1]); pages = [int(x) for x in sys.argv[2:]]
q = f'q%5Bterms%5D%5Bbulletin.city_id%5D={cid}&q%5Bterms%5D%5Btype%5D=Ordinance'
RX = (r'content-title"><a href="(/bulletins/\d+/contents/\d+)">Ordenanza N[º°o]?\s*([^<\s]*)( en el bolet[íi]n [^<]*)</a>'
      r'</p></div><div class="col-md-1"></div></div><div><span class="text-muted">([0-9/]+)')
for p in pages:
    s = E.decode(E.get(f'{B}/advanced_search?{q}') if p == 1 else E.get(f'{B}/advanced_search?page={p}&{q}') or b'')
    ps = [int(x) for x in re.findall(r'advanced_search\?page=(\d+)&', s.replace('&amp;', '&'))]
    rows = re.findall(RX, s)
    print('page', p, 'maxpage', max(ps or [1]), 'rows', len(rows), 'titles', s.count('content-title'))
    for r in rows: print('  ', r[1], r[3], r[2][:40])
