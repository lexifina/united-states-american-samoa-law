"""Extract the files of the texts we build from the cached LEGI dumps into .cache/legi/<text dir id>/.

Reads only .cache/ (plan.json and the cached archives fetch.py wrote): the full dump first, then every daily increment
in order. For each increment the deletions in liste_suppression_legi.dat are applied first, then its files are written
over the tree, which gives the LEGI database as of the last increment. Only paths under one of the text directories in
TEXTS are kept; the path is cut to start at that directory, so a text that moves between the "en vigueur" and
"non vigueur" trees keeps one place.

    python -X utf8 extract.py            # all texts in TEXTS
    python -X utf8 extract.py --titles   # then: the title records of every text their amendment links name
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
OUT = CACHE / 'legi'

# directory id in the dump -> what it is. Codes sit under code_en_vigueur/LEGI/TEXT/../LEGITEXT…; texts that are not
# codes (TNC) under TNC_en_vigueur/JORF/TEXT/../JORFTEXT… (the id of the text as published in the Journal officiel).
TEXTS = {
    'JORFTEXT000000571356': 'Constitution du 4 octobre 1958',
    'LEGITEXT000006070721': 'Code civil',
    'LEGITEXT000006070719': 'Code pénal',
    'JORFTEXT000000886460': 'Loi n° 78-17 du 6 janvier 1978 (Informatique et Libertés)',
    'LEGITEXT000006072050': 'Code du travail',
    'LEGITEXT000006070716': 'Code de procédure civile',
}
RX = re.compile(r'/(' + '|'.join(TEXTS) + r')/(.*)$')


def cached(url: str) -> Path:
    return CACHE / (hashlib.sha256(url.encode()).hexdigest() + '.bin')


def rel(name: str) -> str | None:
    m = RX.search('/' + name)
    return f'{m.group(1)}/{m.group(2)}' if m and m.group(2) else None


def apply(archive: Path, first: bool, stats: dict) -> None:
    with tarfile.open(archive, 'r:gz') as tf:
        members = []
        for m in tf:
            if m.name.endswith('liste_suppression_legi.dat') and not first:
                for line in tf.extractfile(m).read().decode('utf-8').splitlines():
                    r = rel(line.strip())
                    if r:
                        p = OUT / (r + '.xml')
                        if p.exists():
                            p.unlink()
                            stats['deleted'] += 1
                continue
            if m.isfile():
                r = rel(m.name)
                if r and first:  # the full dump has no deletions: write at once
                    p = OUT / r
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_bytes(tf.extractfile(m).read())
                    stats['written'] += 1
                elif r:
                    members.append((r, tf.extractfile(m).read()))
        # deletions first (above, the list comes first in each archive), then the files of this archive
        for r, data in members:
            p = OUT / r
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
            stats['written'] += 1


TITLES = CACHE / 'legi-texts'
LINK_TYPES = ('CREATION', 'CREE', 'MODIFICATION', 'MODIFIE', 'ABROGATION', 'ABROGE', 'TRANSFERT', 'TRANSFERE',
              'DEPLACEMENT', 'DEPLACE')


def linked_cids() -> set[str]:
    """Every text the extracted articles name in an amendment link (creation, modification, abrogation, transfer)."""
    rx = re.compile(r'<LIEN cidtexte="(JORFTEXT\d{12}|LEGITEXT\d{12})"[^>]*typelien="(' + '|'.join(LINK_TYPES) + ')"')
    cids = set()
    for p in OUT.glob('*/article/**/*.xml'):
        cids.update(m.group(1) for m in rx.finditer(p.read_text('utf-8')))
    return cids


def titles() -> None:
    """Keep the texte/version records (title, nature, number, dates) of every text the articles' amendment links name,
    replayed like the articles: global dump first, then each increment over it. Written to .cache/legi-texts/<cid>/."""
    plan = json.loads((CACHE / 'plan.json').read_text('utf-8'))
    cids = linked_cids()
    rx = re.compile(r'/((?:JORF|LEGI)TEXT\d{12})/texte/version/([A-Z]+TEXT\d{12})\.xml$')
    if TITLES.exists():
        shutil.rmtree(TITLES)
    TITLES.mkdir()
    n = 0
    for i, name in enumerate(plan['files']):
        with tarfile.open(cached(plan['base'] + name), 'r:gz') as tf:
            for m in tf:
                if m.isfile() and '/texte/version/' in m.name:
                    g = rx.search(m.name)
                    if g and g.group(1) in cids:
                        p = TITLES / g.group(1) / (g.group(2) + '.xml')
                        p.parent.mkdir(parents=True, exist_ok=True)
                        p.write_bytes(tf.extractfile(m).read())
                        n += 1
        if i == 0 or (i + 1) % 50 == 0:
            print(f'{i + 1}/{len(plan["files"])} {name} written {n}', flush=True)
    found = {p.name for p in TITLES.iterdir()}
    (CACHE / 'legi-texts.json').write_text(json.dumps({'linked': sorted(cids), 'found': sorted(found),
                                                       'missing': sorted(cids - found)}, indent=1), 'utf-8')
    print('titles done', len(found), 'of', len(cids))


def main() -> None:
    if '--titles' in sys.argv:
        return titles()
    plan = json.loads((CACHE / 'plan.json').read_text('utf-8'))
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    stats = {'written': 0, 'deleted': 0}
    log = []
    files = plan['files']
    if '--global-only' in sys.argv:  # exploration: the full dump alone
        files = files[:1]
    for i, name in enumerate(files):
        p = cached(plan['base'] + name)
        if not p.exists():
            sys.exit(f'missing from cache: {name} (run fetch.py)')
        before = dict(stats)
        apply(p, i == 0, stats)
        log.append({'file': name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
                    'written': stats['written'] - before['written'], 'deleted': stats['deleted'] - before['deleted']})
        if i == 0 or (i + 1) % 50 == 0:
            print(f'{i + 1}/{len(files)} {name} {stats}', flush=True)
    (CACHE / 'extract.json').write_text(json.dumps({'texts': TEXTS, 'archives': log, 'stats': stats}, indent=1), 'utf-8')
    print('done', stats)


if __name__ == '__main__':
    main()
