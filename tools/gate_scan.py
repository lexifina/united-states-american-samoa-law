import json, sys, time
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
root = Path('scripts')
rows = []
for f in sorted(root.glob('*-law')):
    if not f.is_dir(): continue
    corpus = (f/'corpus.json').exists() or (f/'corpus.d').is_dir()
    if not corpus: continue
    pub = (f/'PUBLISH').exists()
    parts = sorted((f/'corpus.d').glob('*.json')) if (f/'corpus.d').is_dir() else []
    upub = [p.name for p in parts if not p.with_suffix('.PUBLISH').exists()]
    st = {}
    try: st = json.loads((f/'BUILD_STATUS.json').read_text(encoding='utf-8'))
    except Exception: pass
    age = (time.time() - (f/'BUILD_STATUS.json').stat().st_mtime)/60 if (f/'BUILD_STATUS.json').exists() else -1
    m = str(st.get('main', st.get('error', 'NO BUILD_STATUS')))
    print(f"{f.name[:-4]:26} pub={int(pub)} parts={len(parts)} unverified_parts={len(upub)} status_age={age:5.0f}m | wip={str(st.get('wip',''))[:30]:30} | {m[:110]}")
