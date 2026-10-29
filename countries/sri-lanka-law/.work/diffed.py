import re,sys,difflib
def load(e):
    d={};k=None
    for l in open('ed%s.txt'%e,encoding='utf-8'):
        if l.startswith('##### '):
            k=l.split()[1]; d[k]=[]
        else: d[k].append(l.rstrip('\n'))
    return d
a,b=load(sys.argv[1]),load(sys.argv[2])
ch=[k for k in sorted(set(a)|set(b)) if a.get(k)!=b.get(k)]
print(len(ch),'changed of',len(set(a)|set(b)))
print(' '.join(ch))
if len(sys.argv)>3:
    for k in ch[:int(sys.argv[3])]:
        print('=====',k)
        for l in difflib.unified_diff(a.get(k,[]),b.get(k,[]),lineterm='',n=0): print(l[:400])
