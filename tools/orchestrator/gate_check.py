"""One corpus gate for the pointer loop: global-law's tools/check_corpus.py checks at a candidate commit.

    python -X utf8 gate_check.py <tools dir> <bare repo> <new sha> <old sha or -> <wip 0|1> <until YYYY-MM-DD>

Prints one JSON line: {"fatal_new": [...], "stale_new": n, "fatal_old": [...] | null, "stale_old": n | null, "stale_eg": ""}.
check_corpus reads HEAD, so HEAD of the bare gate clone is pointed at each commit in turn (the clone is the loop's own
cache; nothing else reads its HEAD). The old pin is checked only when the new commit has a problem, so a corpus is held
for what got worse, not for what was already true at the pin (the stale-HEAD check, "check 11", and every fatal check).
Read-only apart from that HEAD file; the caller caps the time.
"""
import json
import re
import sys
from pathlib import Path

tools, repo, new, old, wip, until = sys.argv[1:7]
repo = Path(repo)
sys.path.insert(0, tools)
import check_corpus as cc  # noqa: E402

STALE = re.compile(r'^(\d+) file\(s\) hold an older version at HEAD')


def at(sha, pin):
    (repo / 'HEAD').write_text(sha + '\n', encoding='ascii')
    fatal, warn = cc.problems(repo, until, pin, work_in_progress=wip == '1')
    stale = [w for w in warn if STALE.match(w)]
    return fatal, (int(STALE.match(stale[0]).group(1)) if stale else 0), (stale[0] if stale else '')


out = {'fatal_new': None, 'stale_new': None, 'fatal_old': None, 'stale_old': None, 'stale_eg': ''}
out['fatal_new'], out['stale_new'], out['stale_eg'] = at(new, None if old == '-' else old)
if old != '-' and (out['fatal_new'] or out['stale_new']):
    out['fatal_old'], out['stale_old'], _ = at(old, None)
print(json.dumps(out))
