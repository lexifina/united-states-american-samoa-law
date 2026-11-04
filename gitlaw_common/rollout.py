"""Append standard indexes to an own-builder repository without replacing its tools.

The own builder supplies its normalized, source-backed corpus input. This command
only indexes versions already published: it cannot emit law, corrections or tags.
Shared-builder repositories use build.py --append --refresh-docs instead.
"""
import argparse
import json
from pathlib import Path

import append as A
import build as B
import corpus_jurisdiction as J


def refresh(folder, repo, docs_date, expected_head):
    head = B.git(repo, 'rev-parse', 'main').strip()
    if head != expected_head:
        raise B.CorpusError('rollout: published head changed; inspect the new input before retrying')
    old = json.loads(B.git(repo, 'show', head + ':corpus.json'))
    c, _ = B.load(folder)
    if old.get('acts') != len(c['acts']):
        raise B.CorpusError('rollout requires the complete published act inventory')
    c['_docs_date'], c['_repo'] = docs_date, str(repo)
    state = A.published_state(repo, c)
    for act in c['acts']:
        if any(v['from'] > state.get(act['slug'], '') for v in act['versions']):
            raise B.CorpusError('rollout only indexes published versions: ' + act['slug'])
    tip = A.H.check(repo, c, docs_date)
    if tip['tip_errors'] or tip['tip_warnings']:
        raise B.CorpusError('rollout input differs from published current text: ' + repr(tip['tip_details']))
    B.M.load(c, folder, repo)
    records = B.I.commit_records(repo, c['country'].get('future_branch') or 'futuro')
    slugs = {a['slug'] for a in c['acts']}
    law_keys = {law['label']: key for key, law in c['laws'].items()}
    log = [{'day': r['day'], 'kind': r['kind'], 'law': law_keys.get(r['law']),
            'acts': sorted({p.split('/')[0] for p in r['files']} & slugs),
            'units': len(r['files']), 'branch': r['branch'], 'clamped': r['day'] < '1970-01-01'}
           for r in records]
    files = {p: text for p, text in B.tables(c, log).items() if p.startswith('data/')}
    descriptor = {**old, **B.corpus_descriptor(c, log, docs_date)}
    if old.get('coverage'):
        descriptor['coverage'] = old['coverage']
    jurisdiction = json.loads(B.git(repo, 'show', head + ':jurisdiction.json'))
    files['corpus.json'] = json.dumps(descriptor, ensure_ascii=False, indent=1) + '\n'
    files['jurisdiction.json'] = json.dumps(J.document(c['country'], descriptor['path'], jurisdiction),
                                          ensure_ascii=False, indent=1) + '\n'
    if c['acts']:
        files['.gitattributes'] = c['acts'][0]['_image_attributes']
    # Keep native reproduction tools, source manifests, root prose and act READMEs.
    B.check_documentation_paths(c, files)
    cat = A.K.Cat(repo)
    try:
        files = {p: text for p, text in files.items()
                 if cat.read(head + ':' + p) != (text.encode('utf-8') if text is not None else None)}
    finally:
        cat.close()
    if not files:
        return {'before': head, 'main': head, 'documentation_commits': 0, 'changed_files': []}
    if B.git(repo, 'rev-parse', 'main').strip() != expected_head:
        raise B.CorpusError('rollout: main changed while preparing documentation')
    stamps = B.git(repo, 'log', '-1', '--format=%ct %ci', head).split()
    when = B.Clock(c['country']['tz']).docs_stamp(docs_date)
    writer = A.Appender(repo, head, int(stamps[0]), stamps[-1], committer_ceiling=int(when.split()[0]))
    identity = ('Lexifina', c['country']['slug'] + '-law@lexifina.com')
    writer.commit(identity, when, identity,
                  'Corpus standard: indexes and descriptor\n\nKind: documentation\n', files, committer_when=when)
    writer.finish()
    after = B.git(repo, 'rev-parse', 'main').strip()
    B.git(repo, 'merge-base', '--is-ancestor', head, after)
    return {'before': head, 'main': after, 'documentation_commits': 1, 'changed_files': sorted(files)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('folder', type=Path)
    ap.add_argument('--repo', type=Path, required=True)
    ap.add_argument('--docs-date', required=True)
    ap.add_argument('--expected-head', required=True)
    args = ap.parse_args()
    print(json.dumps(refresh(args.folder, args.repo, args.docs_date, args.expected_head), indent=2))


if __name__ == '__main__':
    main()
