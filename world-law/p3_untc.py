"""Phase 3 helper (private): treaty-action act for one state from the cached UN Treaty Collection status pages."""
import re, html, glob, os, json
from datetime import datetime
SP = r'C:/Users/alany/AppData/Local/Temp/claude/C--Users-alany-Documents-lexifina/bf2c37ff-5368-4758-a217-51eee3902b94/scratchpad'
CHAP = {'I':1,'II':2,'III':3,'IV':4,'V':5,'VI':6,'VII':7,'VIII':8,'IX':9,'X':10,'XI':11,'XII':12,'XIII':13,'XIV':14,'XV':15,'XVI':16,'XVII':17,'XVIII':18,'XIX':19,'XX':20,'XXI':21,'XXII':22,'XXIII':23,'XXIV':24,'XXV':25,'XXVI':26,'XXVII':27,'XXVIII':28,'XXIX':29}
KIND = {'a': 'Accession', 'd': 'Succession', 'A': 'Acceptance', 'AA': 'Approval', '': 'Ratification'}
def clean(s): return re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]+>', ' ', s))).replace('\xa0', ' ').strip()
def iso(d): return datetime.strptime(d, '%d %b %Y').strftime('%Y-%m-%d')

def load(state):
    out = {}
    for f in sorted(glob.glob(SP + '/untc/*.html')):
        tid = os.path.basename(f)[:-5]
        if '.' in tid: continue
        t = open(f, encoding='utf8', errors='replace').read()
        i = t.find('STATUS AS AT'); seg = t[i:i + 6000]; j = seg.find('class="heading-four"')
        title = clean(seg[j:j + 2500]).split(' <')[0]
        title = re.sub(r'^class="heading-four">\s*', '', title)
        title = re.sub(r'^\d+\.\s*([a-z]\s)?', '', title).strip()
        if not title: continue
        row = None
        for m in re.finditer(r'<tr[^>]*>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*</tr>', t, re.S):
            n = re.sub(r'\s*\d+\s*$', '', clean(m.group(1)))
            if n == state: row = [clean(m.group(2)), clean(m.group(3))]
        if row:
            ch = tid.split('-')[0]
            out[tid] = {'title': title, 'row': row,
                        'url': f'https://treaties.un.org/Pages/ViewDetails.aspx?src=TREATY&mtdsg_no={tid}&chapter={CHAP[ch]}&clang=_en'}
    return out

def treaties_act(state, retrieved='2026-10-30'):
    tr = load(state)
    ev = []
    for tid, v in tr.items():
        sig, rat = v['row']
        _ok = lambda x: bool(re.match(r'\d{1,2} [A-Z][a-z]{2} \d{4}', x or ''))  # skip bracketed (not the state's own) and non-date cells
        sig = sig if _ok(sig) else ''; rat = rat if _ok(rat) else ''
        if sig:
            ev.append((iso(' '.join(sig.split()[:3])), tid, 'Signature'))
        if rat:
            p = rat.split(); ev.append((iso(' '.join(p[:3])), tid, KIND.get(''.join(p[3:]), 'Ratification')))
    ev.sort()
    laws = {}; versions = []; hist = {}; units = {}
    days = sorted({e[0] for e in ev})
    for d in days:
        credits = {}
        for _, tid, kind in [e for e in ev if e[0] == d]:
            key = re.sub(r'[^a-z0-9]+', '-', 'untc-' + tid.lower()).strip('-')
            lk = f'{key}-{d}-{kind.lower()}'
            laws[lk] = {'label': f'{kind}: {tr[tid]["title"][:90]}', 'title': f'{tr[tid]["title"]}: {kind.lower()} on {d}', 'kind': 'treaty', 'enacted': d, 'published': None,
                        'url': tr[tid]['url'], 'temporary_until': None, 'restores': None,
                        'note': f'A treaty action recorded by the UN Treaty Collection ({kind.lower()} on {d}); it is a fact about treaty membership and changes no law text.'}
            hist.setdefault(tid, []).append((kind, d))
            lines = [f'# {tr[tid]["title"]}', f'UN Treaty Collection reference: {tid}.', *(['Depositary: Secretary-General of the United Nations.'] if tid not in ('XXV-2', 'XXV-3') else [])] + [f'{k}: {dd}.' for k, dd in hist[tid]]
            units[key] = {'label': tr[tid]['title'][:90], 'kind': 'treaty', 'text': '\n'.join(lines) + '\n'}
            credits[key] = [lk]
        versions.append({'from': d, 'source_url': 'https://treaties.un.org/', 'sha256': 'untc-status-pages-2026-10-29', 'units': {k: dict(v) for k, v in units.items()},
                         'credits': credits, 'note': 'Treaty actions of this day.'})
    act = {'slug': 'treaties', 'short': 'Treaties', 'title': f'Treaty actions of {state} (UN Treaty Collection)', 'url': 'https://treaties.un.org/',
           'first_law': None, 'earlier_laws': [], 'versions': versions}
    # first version: no first_law -> "oldest version available"; credit it explicitly instead
    src = {'name': 'UN Treaty Collection (MTDSG status pages)', 'url': 'https://treaties.un.org/', 'retrieved': '2026-10-29', 'licence': 'Facts only (treaty action, date, depositary); no text copied',
           'notes': 'Status pages of selected multilateral treaties deposited with the UN Secretary-General.'}
    return act, laws, src, len(tr)
