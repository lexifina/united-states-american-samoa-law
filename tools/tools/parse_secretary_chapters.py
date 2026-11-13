"""Extract selected whole chapters from official native-text Code PDFs unchanged."""
import argparse, ctypes, hashlib, json, os, re
from pathlib import Path
import fitz

SELECTED={
    (2,3):('1987-08-04','Government Records Management','eff 4 Aug. 87'),
    (3,1):('1985-05-02','Election Contributions and Expenses','eff 2 May 85'),
    (5,2):('1987-10-12','Economic Development Planning Commission','eff 12 Oct 87'),
    (6,2):('1983-07-01','Rental Space of Market Place for Bingo Games','eff 1 Jul 83'),
    (13,1):('1988-05-25','Student Financial Aid','eff 25 May 88'),
    (13,2):('1983-12-28','Tuition Rates and Fees at American Samoa Community College','eff 28 Dec 83'),
    (19,1):('2023-07-19','Commercial Transportation','eff 19 July 2023'),
    (19,2):('2023-07-19','Commercial Transportation Chapter 2','eff 19 July 2023'),
}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--job',required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
    job=Path(a.job).resolve();e=job/'agency-evidence'
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),0x4000)
    with (job/'pids.txt').open('a') as f:f.write(f'{os.getpid()} parse_secretary_chapters.py\n')
    docs=json.loads((e/'secretary-documents.json').read_text(encoding='utf-8'))
    part={'sources':[],'laws':{},'acts':[],'decisions':[],'ai_use':['A model wrote the native-text extraction and validation scripts. No legal words were authored, corrected or transcribed from images.']};manifest=[]
    for d in docs:
        if not any(r['page'].endswith('/asac-2024') for r in d['references']):continue
        data=(e/d['file']).read_bytes();assert hashlib.sha256(data).hexdigest()==d['sha256']
        groups={}
        with fitz.open(stream=data,filetype='pdf') as pdf:
            for n,p in enumerate(pdf,1):
                text=p.get_text();m=re.search(r'ASAC TITLE\s+(\d+)\s*[–-]\s*CHAPTER\s+(\d+)',text)
                if not m:continue
                key=tuple(map(int,m.groups()))
                if key not in SELECTED:continue
                assert not p.get_images(),f'image in selected chapter {key}, page {n}'
                groups.setdefault(key,[]).append((n,text))
        for key,ps in groups.items():
            date,title,quote=SELECTED[key];norm=' '.join(' '.join(t for _,t in ps).split())
            assert quote in norm,(key,quote)
            slug=f'asac-{key[0]:02d}-{key[1]:02d}'
            units={f'page-{n:03d}':{'label':f'Official PDF page {n}','kind':'section','text':t} for n,t in ps}
            part['acts'].append({'slug':slug,'short':f'ASAC {key[0]}.{key[1]:02d}','title':f'American Samoa Administrative Code, Title {key[0]}, Chapter {key[1]} – {title}','url':d['url'],'first_law':None,'earlier_laws':[],'versions':[{'from':date,'source_url':d['url'],'sha256':d['sha256'],'source_images':0,'units':units}]})
            part['decisions'].append(f'{slug}: one chapter snapshot from the Secretary\'s 2024 Code edition, dated {date} from the chapter\'s express history note "{quote}". Earlier wording is not reconstructed. Source front matter, history notes and native wording are retained. Source images 0, referenced 0, omitted 0.')
            manifest.append({'act':slug,'url':d['url'],'sha256':d['sha256'],'source_file':d['file'],'pages':[n for n,_ in ps],'from':date,'basis_quote':quote,'title':title})
        if groups:part['sources'].append({'name':'Secretary of American Samoa: American Samoa Administrative Code, 2024 edition','url':d['url'],'retrieved':'2026-11-13','licence':'Official government rules text; no reuse terms stated on source pages.'})
    assert len(part['acts'])==len(SELECTED),(len(part['acts']),len(SELECTED))
    Path(a.output).write_text(json.dumps(part,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (e/'chapter-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'acts':len(part['acts']),'pages':sum(len(m['pages']) for m in manifest),'sha256':hashlib.sha256(Path(a.output).read_bytes()).hexdigest()}))
if __name__=='__main__':main()
