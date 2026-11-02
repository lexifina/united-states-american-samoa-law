"""Private. Writes scripts/<folder>/laws.py, check_laws.py and br_lib.py for a SAPL Câmara (gitlaw-scraper-dell,
municipal SAPL wave, 2026-11-01).

    python -X utf8 scripts/world-law/br_sapl_city_make.py <spec.json>

spec (sapl-spec.json): folder, host, city, code, slug, tz, email_domain.
"""
import json, shutil, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent
s = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
cfg = {k: s[k] for k in ('host', 'city', 'code', 'slug', 'tz', 'email_domain')}
out = SCRIPTS / s['folder']
src = (HERE / 'br_sapl_laws_tpl.py').read_text(encoding='utf-8')
src = src.replace('@CITY@', s['city']).replace('@CONFIG@', json.dumps(cfg, ensure_ascii=False))
(out / 'laws.py').write_text(src, encoding='utf-8', newline='\n')
shutil.copy(HERE / 'br_sapl_check_laws_tpl.py', out / 'check_laws.py')
shutil.copy(HERE / 'br_lib.py', out / 'br_lib.py')
print('wrote', out / 'laws.py')
