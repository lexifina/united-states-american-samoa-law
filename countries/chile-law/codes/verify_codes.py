"""Runs the main agent's verify.py on a codes part (corpus.d/50-codes.json, or --corpus PATH): the text of each act
in force on --date must equal LeyChile's current text unit by unit, and every version must carry the sha256 of a
cached LeyChile response.

    python -X utf8 scripts/chile-law/codes/verify_codes.py [--corpus PATH] [--date YYYY-MM-DD] [--offline]

The part stores versions as `changes` (SCHEMA.md, "Large acts"); they are expanded to full `units`, as the builder
reads them, into .tmp-build/codes/verify-expanded.json, which verify.py then checks.

One documented exception: when LeyChile's unversioned page (idVersion empty) shows a version that waits for an event
(dated 2222-02-02, left out of the corpus) instead of the text in force, the act passes if it equals the dated version
in force on --date and the unversioned page equals that 2222-02-02 version unit by unit. The line then says so.
"""
import contextlib
import io
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import fetch  # noqa: E402
import parse  # noqa: E402
import parse_codes  # noqa: E402
import verify  # noqa: E402
from fetch_codes import current_url  # noqa: E402


class ActMeta(dict):
    """parse.ACT_META that records which act verify.py is reading (parse_codes.CURRENT), so a norm read for several
    acts (DFL 1 of 2000) gives each act its own article."""
    def __getitem__(self, slug):
        parse_codes.CURRENT['act'] = slug
        return super().__getitem__(slug)


def pending_event_page(slug: str, width: int) -> bool:
    parse_codes.CURRENT['act'] = slug
    norm = fetch.ACTS[slug][-1]
    raw_cur = fetch.fetch(current_url(norm), offline=True)
    try:
        raw_ev = fetch.fetch(fetch.version_url(norm, '2222-02-02'), offline=True)
    except FileNotFoundError:
        return False
    part = parse.ACT_META[slug].get('part')
    a = parse.read_version(raw_cur, width, part)['units']
    b = parse.read_version(raw_ev, width, part)['units']
    return {k: u['text'] for k, u in a.items()} == {k: u['text'] for k, u in b.items()}


if __name__ == '__main__':
    if '--corpus' not in sys.argv:
        sys.argv += ['--corpus', str(parse_codes.OUT)]
    i = sys.argv.index('--corpus') + 1
    part = parse_codes.expand(json.loads(Path(sys.argv[i]).read_text(encoding='utf-8')))
    tmp = HERE.parent / '.tmp-build' / 'codes' / 'verify-expanded.json'
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps(part, ensure_ascii=False), encoding='utf-8', newline='\n')
    sys.argv[i] = str(tmp)
    parse_codes.setup([a['slug'] for a in part['acts']])
    parse.ACT_META = ActMeta(parse.ACT_META)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        verify.main()
    bad = 0
    for line in out.getvalue().splitlines():
        d = json.loads(line)
        ok = not d['differences'] and not d['versions_without_cached_source']
        if ok and d['differences_vs_current_page']:
            act = next(a for a in part['acts'] if a['slug'] == d['act'])
            width = len(next(k for k in act['versions'][-1]['units'] if k.startswith('art-')).split('-')[1])
            if pending_event_page(d['act'], width):
                d['current_page_note'] = ('the unversioned page shows the version waiting for an event (2222-02-02, '
                                          'not in force, left out); the text in force equals the corpus')
            else:
                ok = False
        bad += not ok
        print(json.dumps(d, ensure_ascii=False))
    sys.exit(1 if bad else 0)
