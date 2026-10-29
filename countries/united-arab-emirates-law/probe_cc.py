import sys, json, collections
sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common'); import wayback
CACHE = r'C:/Users/alany/Documents/lexifina/scripts/united-arab-emirates-law/.cache'
crawls = wayback.cc_crawls(CACHE)
print(crawls[:6])
n = int(sys.argv[1]) if len(sys.argv) > 1 else 2
recs = wayback.cc_captures('uaelegislation.gov.ae/', match='prefix', crawls=crawls[:n], cache=CACHE)
print(len(recs))
c = collections.Counter('/'.join(r['url'].split('/')[3:5]) for r in recs)
for k, v in c.most_common(40): print(v, k)
json.dump(recs, open(CACHE + '/cc_recs.json', 'w'))
