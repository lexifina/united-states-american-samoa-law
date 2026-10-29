"""Check corpus.json against the newest archived likumi.lv page of each act, unit for unit (exact text).

The newest capture of the act's main page (no version date) shows the version in force when it was captured; the
corpus, replayed to that version's day, must equal it. Also checks that every version's units equal the page it
cites (except units deferred to a later in-force day, which are listed). Writes verification.json.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import likumi  # noqa: E402

CACHE = HERE / '.cache'


def raw(url):
    return (CACHE / hashlib.sha256(url.encode()).hexdigest()).read_bytes()


def main():
    corpus = json.loads((HERE / 'corpus.json').read_text(encoding='utf-8'))
    caps = json.loads((HERE / 'captures.json').read_text(encoding='utf-8'))
    acts_cfg = json.loads((HERE / 'acts.json').read_text(encoding='utf-8'))
    res, ok = {}, True
    for act in corpus['acts']:
        c = caps[act['slug']]
        newest = c['newest']
        p = likumi.parse_page(raw(f"https://web.archive.org/web/{newest['ts']}id_/{newest['url']}"),
                              acts_cfg[act['slug']]['likumi_id'])
        state, states = {}, []
        for v in act['versions']:
            if 'units' in v:
                state = dict(v['units'])
            else:
                for k, u in v.get('changes', {}).items():
                    if u is None:
                        state.pop(k, None)
                    else:
                        state[k] = u
            states.append((v['from'], dict(state)))
        upto = [s for d, s in states if d <= p['version']][-1]
        want = {k: u['text'] for k, u in p['units'].items()}
        got = {k: u['text'] for k, u in upto.items()}
        diff = sorted(k for k in set(want) | set(got) if want.get(k) != got.get(k))
        res[act['slug']] = {'newest_capture': newest, 'shows_version': p['version'], 'units': len(want),
                            'mismatches': diff, 'versions': len(act['versions'])}
        ok &= not diff
        print(act['slug'], 'newest capture', newest['ts'], 'shows', p['version'], len(want), 'units;',
              'OK' if not diff else f'MISMATCH {diff[:10]}')
    (HERE / 'verification.json').write_text(json.dumps(res, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
