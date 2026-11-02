import re, timeit, json, gzip, glob, os, random
HY = chr(1)
files = sorted(glob.glob(r'C:/Users/alany/Documents/lexifina/scripts/ireland-law/.cache/parsed26-*.json'))
random.seed(1); files = random.sample(files, 60)
texts = [u['text'] for f in files for u in json.load(open(f, encoding='utf-8'))['units'].values()]
print(len(texts), 'units', sum(map(len, texts)) // 1000, 'k chars', sum(t.count(HY) for t in texts), 'HY marks')
old = re.compile(r"([\w'-]*\w)" + HY + r'(\w+)')
new = re.compile(r"(?<![\w'-])([\w'-]*\w)" + HY + r'(\w+)')
pre = lambda t: HY in t
f = lambda m: m.group(1) + '-' + m.group(2)
for name, fn in [('as built', lambda: [old.sub(f, t) for t in texts]),
                 ('word-start anchor', lambda: [new.sub(f, t) for t in texts]),
                 ('skip units without the mark', lambda: [old.sub(f, t) if HY in t else t for t in texts])]:
    print(name, round(min(timeit.repeat(fn, number=1, repeat=3)), 3), 's')
assert [old.sub(f, t) for t in texts] == [new.sub(f, t) for t in texts]
print('same output')
