"""Checks the corpus's text on the retrieval day against LEGI, act by act. Reads only the cache and the corpus.

    python -X utf8 verify.py [slug ...]

For each act it compares, provision by provision, the corpus as in force on DOCS_DATE with:
1. the LEGI article versions in force that day (DATE_DEBUT <= day < DATE_FIN), text normalised as parse.py does, and
   every version LEGI marks ETAT VIGUEUR (the current text Légifrance shows);
2. the act's own table of contents in LEGI (texte/struct and its sections' LIEN_ART entries in force that day), an
   independent list of which article versions are current, by id.
Writes .tmp-build/verify-<slug>.json and exits non-zero on any difference.
"""
from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import parse

HERE = Path(__file__).resolve().parent


def corpus_acts() -> dict[str, dict]:
    acts = {}
    files = [HERE / 'corpus.json'] + sorted((HERE / 'corpus.d').glob('*.json'))
    for p in files:
        if p.exists():
            for a in json.loads(p.read_text('utf-8')).get('acts', []):
                acts[a['slug']] = a
    return acts


def state_on(act: dict, day: str) -> dict[str, str]:
    units: dict[str, dict] = {}
    for v in act['versions']:
        if v['from'] > day:
            break
        if 'units' in v:
            units = dict(v['units'])
        for k, u in (v.get('changes') or {}).items():
            if u is None:
                units.pop(k, None)
            else:
                units[k] = u
    return {k: u['text'] for k, u in units.items()}


def struct_ids(spec: dict, day: str) -> set[str]:
    """Article version ids in force on `day` per the act's table of contents (texte/struct + section_ta)."""
    root = parse.LEGI / spec['dir']
    ids = set()
    rx = re.compile(r'<LIEN_ART debut="([^"]*)" etat="[^"]*" fin="([^"]*)" id="([^"]*)"')
    for p in list((root / 'texte' / 'struct').glob('*.xml')) + list((root / 'section_ta').glob('**/*.xml')):
        for d, f, i in rx.findall(p.read_text('utf-8')):
            if d <= day < f:
                ids.add(i)
    return ids


def check(spec: dict, act: dict, day: str) -> dict:
    vs = [v for v in parse.read_act(spec) if v.d < v.f]
    width = max(3, max(len(re.match(r'\D*(\d*)', v.num).group(1)) for v in vs))
    live = [v for v in vs if v.d <= day < v.f]
    want = {}
    for v in live:
        want[parse.unit_key(v.num, width)] = v.text or parse.PLACEHOLDER
    got = state_on(act, day)
    diff = {'missing': sorted(set(want) - set(got)), 'extra': sorted(set(got) - set(want)),
            'text': sorted(k for k in set(want) & set(got) if want[k] != got[k])}
    vigueur = {v.id for v in vs if v.etat == 'VIGUEUR'}
    live_ids = {v.id for v in live}
    diff['vigueur_not_in_force'] = sorted(vigueur - live_ids)
    sids = struct_ids(spec, day)
    diff['struct_not_in_force'] = sorted(sids - live_ids)
    diff['in_force_not_in_struct'] = sorted(live_ids - sids)
    return {'day': day, 'provisions': len(got), 'legi_in_force': len(live), 'vigueur': len(vigueur),
            'struct': len(sids), **diff}


def main(argv: list[str]) -> int:
    acts = corpus_acts()
    bad = 0
    for spec in parse.ACTS:
        if argv and spec['slug'] not in argv or spec['slug'] not in acts:
            continue
        r = check(spec, acts[spec['slug']], parse.DOCS_DATE)
        (HERE / '.tmp-build').mkdir(exist_ok=True)
        (HERE / '.tmp-build' / f'verify-{spec["slug"]}.json').write_text(json.dumps(r, indent=1), 'utf-8')
        n = {k: len(v) for k, v in r.items() if isinstance(v, list)}
        print(spec['slug'], r['day'], 'provisions', r['provisions'], 'LEGI in force', r['legi_in_force'],
              'VIGUEUR', r['vigueur'], 'struct', r['struct'], n)
        bad += sum(n.values())
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
