import pymupdf, json, sys
d=pymupdf.open('src/cn.pdf')
out=[]; stats={'drop':0,'strike':0,'under_space':0}
for pn in range(25):
    p=d[pn]
    rects=[x['rect'] for x in p.get_drawings() if x['rect'].height<=1.6 and x['rect'].width>2 and x.get('fill') and sum(x['fill'])<1]
    raw=p.get_text('rawdict')
    for b in raw['blocks']:
        if b['type']!=0: continue
        for ln in b['lines']:
            x0,y0,x1,y1=ln['bbox']; h=y1-y0
            chars=[]; bold=False
            for sp in ln['spans']:
                if sp['flags']&16 or 'Bold' in sp['font']: bold=True
                for c in sp['chars']:
                    cx=(c['bbox'][0]+c['bbox'][2])/2; ch=c['c']
                    under=strike=False
                    by=c['origin'][1]
                    for r in rects:
                        if r.x0-0.5<=cx<=r.x1+0.5:
                            dl=r.y0-by
                            if 0.3<=dl<=4: under=True
                            elif -6<=dl<=-1.2: strike=True
                    chars.append((ch,under,strike))
            txt=''
            for ch,u,s in chars:
                if u and ch.strip(): stats['drop']+=1; continue
                if u: stats['under_space']+=1
                txt+=ch
            out.append({'page':pn+1,'y':round(y0,1),'x':round(x0,1),'bold':bold,'text':txt,'had_under':any(u for _,u,_ in chars),'had_strike':any(s for _,_,s in chars)})
json.dump(out,open('lines.json','w',encoding='utf8'),ensure_ascii=False,indent=0)
print(stats,len(out))
