"""Checks the git repository against the official texts: for every text in data/versions.json (the act as published,
then every consolidated version), the XML's sha256 must match, and on the day the text applies from, the repository
(read with tools/en_vigueur_au.py's own lookup) must hold exactly that text's articles, each file byte for byte the
article rebuilt from the XML. A second check confirms that every word of every article in the XML, apart from
struck-through text and notes, is in the article's lines, in order.

    python -X utf8 scripts/luxembourg-law/check_repo.py [--repo ../luxembourg-law] [--no-record]

The result is written to verification.json beside this file, which REPRODUCE.md quotes on the next build.
"""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build as B  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', default=str(B.ROOT.parent / 'luxembourg-law'))
    ap.add_argument('--no-record', action='store_true')
    args = ap.parse_args()
    repo = Path(args.repo)
    spec = importlib.util.spec_from_file_location('en_vigueur_au', repo / 'tools' / 'en_vigueur_au.py')
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    manifest = json.loads((repo / 'data' / 'versions.json').read_text(encoding='utf-8'))
    texts = articles = bad = words = wbad = 0
    for act in manifest['acts']:
        for v in act['versions']:
            xml = B.fetch(v['xml'], offline=True)
            texts += 1
            if hashlib.sha256(xml).hexdigest() != v['sha256']:
                bad += 1
                print(f'SHA256 {act["slug"]} {v["from"]}')
                continue
            parsed = B.read_version(xml)
            want = {f'{act["path"]}/{k}.md': B.render(u) for k, u in parsed['units'].items() if u['lines']}
            commit = tool.commit_on(v['from'], act['path'], cwd=repo)
            if not commit:
                bad += 1
                print(f'NO COMMIT {act["slug"]} {v["from"]}')
                continue
            have = [f for f in tool.git('ls-tree', '-r', '--name-only', commit, act['path'] + '/', cwd=repo).split('\n')
                    if f.endswith('.md') and not f.endswith('/README.md')]
            for f in sorted(set(have) - set(want)):
                bad += 1
                print(f'EXTRA {act["slug"]} {v["from"]} {f}')
            for f, text in sorted(want.items()):
                articles += 1
                got = subprocess.run(['git', 'show', f'{commit}:{f}'], cwd=repo, capture_output=True).stdout.decode('utf-8')
                if got != text:
                    bad += 1
                    if bad <= 10:
                        print(f'MISMATCH {act["slug"]} {v["from"]} {f}')
            # Every word of every article in the XML, in order, is in the lines read from it.
            root = B.etree.fromstring(xml)
            for art in root.find('.//a:body', B.NS).iter(f'{{{B.AKN}}}article'):
                if any(B.tag(a) == 'article' for a in art.iterancestors()):
                    continue
                u = parsed['units'][B.unit_key(art)]
                if not u['lines'] or u['id'] != art.get('id'):
                    continue
                words += 1
                expect = B.clean(B.inline(art)).replace(' ', '')
                ours = (u['label'] + u['heading'] + ''.join(l.get('bullet', '') + l['text'][len(l.get('marker', '')):]
                                                           for l in u['lines'])).replace(' ', '')
                if expect != ours:
                    wbad += 1
                    print(f'WORDS {act["slug"]} {v["from"]} {u["key"]}')
    tip = subprocess.run(['git', 'rev-parse', 'HEAD~1'], cwd=repo, capture_output=True, text=True).stdout.strip()
    print(f'{texts} texts checked ({articles} article files compared byte for byte), {bad} mismatches; '
          f'{words} articles checked word for word against the XML, {wbad} mismatches')
    if not args.no_record:
        p = HERE / 'verification.json'
        rec = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
        rec['check'] = {'versions': texts, 'articles': articles, 'mismatches': bad, 'words_articles': words,
                        'words_mismatches': wbad, 'history_tip': tip, 'run': dt.date.today().isoformat()}
        p.write_text(json.dumps(rec, indent=1) + '\n', encoding='utf-8', newline='\n')
    raise SystemExit(1 if bad or wbad else 0)


if __name__ == '__main__':
    main()
