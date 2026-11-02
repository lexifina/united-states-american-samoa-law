"""Same 103-act Denmark sample, timed as built and with two memo caches patched in from outside (no builder edit):
lines_of keyed by the html string, commencement keyed by (the article dict's identity, article, item, published).
Checks the results are equal."""
import sys, time, os, json, hashlib
D = r'C:/Users/alany/Documents/lexifina/scripts/denmark-law'
sys.path.insert(0, D); os.chdir(D)
import build, dkparse as P
build.TODAY = '2026-10-28'
acts = build.load_acts()[::14]
def run():
    t = time.perf_counter(); r = [build.act_worker((a, True)) for a in acts]; return time.perf_counter() - t, r
t0, r0 = run()
_lines, _comm = P.lines_of, P.commencement
LC, CC, hits = {}, {}, [0, 0, 0, 0]
def lines_of(h):
    k = hashlib.blake2b(h.encode(), digest_size=16).digest()
    if k in LC: hits[0] += 1
    else: hits[1] += 1; LC[k] = _lines(h)
    return list(LC[k])
def commencement(arts, n, i, pub):
    k = (id(arts), n, i, pub)
    if k in CC and CC[k][0] is arts: hits[2] += 1
    else: hits[3] += 1; CC[k] = (arts, _comm(arts, n, i, pub))
    return CC[k][1]
P.lines_of = lines_of; P.commencement = commencement
t1, r1 = run()
same = json.dumps(r0, sort_keys=True, default=str) == json.dumps(r1, sort_keys=True, default=str)
print(json.dumps({'acts': len(acts), 'as_built_s': round(t0, 1), 'memo_s': round(t1, 1), 'same_results': same,
                  'lines_of_hits_misses': hits[:2], 'commencement_hits_misses': hits[2:]}))
