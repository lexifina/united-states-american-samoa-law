import json,re,hashlib
L=json.load(open('lines.json'))
FOOT=re.compile(r'^(Note: New language|\d+ of 20)')
body=[l for l in L if l['page']>=8 and not FOOT.match(l['text'].strip())]
# paragraphs
paras=[]  # (bold, text, page_start)
cur=None; prev=None
def flush():
    global cur
    if cur and cur['text'].strip(): paras.append(cur)
    cur=None
for l in body:
    t=l['text']; s=re.sub(r'\s+',' ',t).strip()
    blank=not s
    trueblank = blank and not l['had_under']
    if blank:
        if trueblank: flush()
        prev=l; continue
    brk=False
    if cur is None: brk=True
    else:
        if l['bold']!=cur['bold']: brk=True
        elif prev is not None and prev['page']==l['page'] and l['y']-prev['y']>17.5: brk=True
        elif l['x']<cur['lastx']-5: brk=True
        elif re.match(r'^(\d+\.|\([a-z0-9]+\))\s',s) and l['x']>=100 and not l['bold']: brk=True
        elif re.match(r'^Representative District No\.',s) or re.match(r'^Representative District No\.',cur['text']) and len(cur['text'])<35: brk=True
    if brk:
        flush(); cur={'bold':l['bold'],'text':s,'page':l['page'],'lastx':l['x']}
    else:
        if cur['text'].endswith('-') and s[:1].islower(): cur['text']=cur['text'][:-1]+s; cur['dehyph']=cur.get('dehyph',[])+[s.split()[0]]
        else: cur['text']+=' '+s
        cur['lastx']=l['x']
    prev=l
flush()
json.dump(paras,open('paras.json','w',encoding='utf8'),ensure_ascii=False,indent=1)
for p in paras: print(p['page'],'B' if p['bold'] else ' ',p['text'][:110], '| DEHYPH' if p.get('dehyph') else '')
