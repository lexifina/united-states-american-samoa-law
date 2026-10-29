import json,re,hashlib
L=json.load(open('lines.json',encoding='utf8'))
FOOT=re.compile(r'^(Note: New language|\d+ of 20)')
start=next(i for i,l in enumerate(L) if l['page']==8 and l['text'].strip()=='Preamble')
body=[l for l in L[start:] if not FOOT.match(l['text'].strip())]
SEC=re.compile(r'^Section (\d+|I)\.')
paras=[];cur=None;prev=None
def flush():
    global cur
    if cur and cur['text'].strip(): paras.append(cur)
    cur=None
for l in body:
    s=re.sub(r'\s+',' ',l['text']).strip()
    if not s:
        if not l['had_under'] and l['y']<720: flush()
        prev=l; continue
    ishead=l['bold'] or bool(SEC.match(s) and l['x']<80)
    brk=cur is None or ishead or cur['head'] or \
        (prev is not None and prev['page']==l['page'] and l['y']-prev['y']>17.5) or \
        (re.match(r'^(\d+\.|\([a-z0-9]+\))\s',s) and l['x']>=100) or \
        s.startswith('Representative District No.') or cur['text'].startswith('Representative District No.')
    if brk:
        flush(); cur={'head':ishead,'text':s}
    else:
        if cur['text'].endswith('-') and s[:1].islower(): cur['text']=cur['text'][:-1]+s
        else: cur['text']+=' '+s
    prev=l
flush()
def fix(t):
    t=re.sub(r'\s+',' ',t)
    t=re.sub(r' +([,;.:])',r'\1',t)
    t=t.replace('Faganeanea,:','Faganeanea:')
    t=t.replace('Ta’u, two one senators','Ta’u, two senators')
    t=t.replace('for his approval If he','for his approval. If he')
    t=re.sub(r'\s+',' ',t).strip()
    t=t.replace('I,, of do','I, ____, of ____ do')
    return t
cut=next(i for i,p in enumerate(paras) if p['text'].startswith('We the undersigned'))
paras=paras[:cut]
ENDFIX=[];units={};order=[];labels={}
roman={'Article I':1,'Article II':2,'Article III':3,'Article IV':4,'Article V':5}
art=0;key=None;buf=[]
def put(k,label,kind,head,lines):
    if kind=='section' and lines:
        z=fix(lines[-1])
        if z and not z.startswith('Stewart') and z[-1] not in '.:;)”': lines=lines[:-1]+[z.rstrip(',')+'.']; ENDFIX.append(k)
    units[k]={'label':label,'kind':kind,'text':'# '+head+'\n'+''.join(fix(x)+'\n' for x in lines if fix(x))}
i=0;pend=None
items=[]
def closeunit():
    if pend: put(*pend,items[:])
for p in paras:
    t=p['text']
    if t=='Preamble':
        closeunit(); pend=('preamble','Preamble','preamble','Preamble'); items=[]; continue
    if t in roman:
        closeunit(); art=roman[t]; pend=('art-%02d-heading'%art,t,'article',t); items=[]; continue
    m=SEC.match(t) if p['head'] else None
    if m:
        closeunit(); n=1 if m.group(1)=='I' else int(m.group(1))
        pend=('art-%02d-sec-%02d'%(art,n),'Art. %s, Sec. %d'%({1:'I',2:'II',3:'III',4:'IV',5:'V'}[art],n),'section',fix(t)); items=[]; continue
    items.append(t)
closeunit()
# article titles belong in heading units: bold lines were collected as items of the article heading unit already
pdf=open('src/cn.pdf','rb').read()
corpus={
 'country':{'code':'AS','name':'American Samoa','slug':'united-states-american-samoa','lang':'en','tz':'Pacific/Pago_Pago','future_branch':'future',
  'publisher':{'name':'American Samoa Government','email':'asg@americansamoa.invalid'},
  'default_in_force_rule':{'text':'The Revised Constitution took effect on 1 July 1967 (Art. V, Sec. 11); this text is the in-force Constitution as it stood when the 2022 Constitutional Convention marked its proposed amendments.','source':'https://www.americansamoa.gov/_files/ugd/4bfff9_637c7079564f4812ae2c848e48753e7d.pdf'},
  'licence_note':'Source: American Samoa Government, americansamoa.gov.'},
 'sources':[{'name':'American Samoa Government: Revised Constitution with the 2022 Constitutional Convention proposed amendments (marked draft, 6 Sept 2022)','url':'https://www.americansamoa.gov/_files/ugd/4bfff9_637c7079564f4812ae2c848e48753e7d.pdf','retrieved':'2026-10-29','licence':'Official government text; no reuse terms stated on the page. U.S. government works and official legislative texts are not subject to copyright protection.','notes':'Only the in-force text is taken: struck-through (current) and unmarked words are kept, underlined (proposed new) words are dropped.'}],
 'laws':{},
 'acts':[{'slug':'constitution','short':'ASCONST','title':'Revised Constitution of American Samoa','url':'https://www.americansamoa.gov/_files/ugd/4bfff9_637c7079564f4812ae2c848e48753e7d.pdf','first_law':None,'earlier_laws':[],
  'versions':[{'from':'2022-09-06','source_url':'https://www.americansamoa.gov/_files/ugd/4bfff9_637c7079564f4812ae2c848e48753e7d.pdf','sha256':hashlib.sha256(pdf).hexdigest(),'units':units,'credits':{},
   'note':'In-force text reconstructed from the 6 September 2022 marked draft; the proposals of the 2022 Constitutional Convention are not included.'}]}],
 'applies':[],
 'decisions':[
  'The source is a marked draft: new language underlined, language to be deleted struck through. The in-force text is the unmarked words plus the struck-through words; underlined words were dropped. Marks were read from the PDF drawing geometry (thin filled rectangles beside the text baseline: just below it is an underline, above it a strike-through), not from the text layer.',
  'The version is dated 2022-09-06, the date printed on the draft, as the oldest version available; the text was in force then, so far as the draft shows, and the proposals were unratified drafts.',
  'Front matter (table of contents, the Convention summary of amendments) and the draft certificate of the 2022 Convention delegates were left out; the attestation of the Secretary of the Interior is kept.',
  'Three places where the marks left a stray word or mark were repaired by hand against the rendered page: Art. II Sec. 4 "two one senators" became "two senators" (the new word "one" was not underlined), Art. II Sec. 2 "Faganeanea, :" became "Faganeanea:", and Art. II Sec. 9 "for his approval If" became "for his approval. If".',
  'Hyphenation at line ends was joined; spacing left by dropped words was closed up; sections are one unit each, with the preamble and each article heading as their own units. Source typos (for example "Section I." for Section 1) are kept.',
  'Where dropping an underlined run removed a paragraph end, the lost closing full stop was restored on the last paragraph of these sections: '+', '.join(ENDFIX)+'. The blanks of the oath (Art. V Sec. 6) were underlined spaces and are shown as ____.',
  'The 2022 proposals are recorded only as a pending note in the README; whether Congress or the Secretary of the Interior has approved any of them was not confirmed.'],
 'ai_use':['none']}
json.dump(corpus,open('corpus.json','w',encoding='utf8'),ensure_ascii=False,indent=1)
print(len(units)); 
for k,u in units.items(): print(k,'|',u['label'],'|',len(u['text']))
