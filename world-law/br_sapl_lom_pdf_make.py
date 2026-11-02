"""Private. Writes scripts/<folder>/parse.py (Lei Orgânica from its PDF, current or enacted text) and check_letters.py
for a SAPL wave city whose SAPL keeps no Texto Articulado history (gitlaw-scraper-dell, 2026-11-01).

    python -X utf8 scripts/world-law/br_sapl_lom_pdf_make.py <folder>/sapl-spec.json

sapl-spec.json "lom_pdf": url, norma, after, start, end, note, void, law_key, label, title, enacted, published,
from, mode (enacted|consolidated), rule, vnote, source_name, decisions.
"""
import json, shutil, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
s = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
cfg = {k: s[k] for k in ('host', 'city', 'code', 'slug', 'tz', 'email_domain')}
cfg.update(s['lom_pdf'])
out = HERE.parent / s['folder']
src = (HERE / 'br_sapl_lom_pdf_tpl.py').read_text(encoding='utf-8')
src = src.replace('@CITY@', s['city']).replace('@CONFIG@', repr(cfg))
(out / 'parse.py').write_text(src, encoding='utf-8', newline='\n')
shutil.copy(HERE / 'br_sapl_check_lom_pdf_tpl.py', out / 'check_letters.py')
shutil.copy(HERE / 'br_lib.py', out / 'br_lib.py')
print('wrote', out / 'parse.py')
