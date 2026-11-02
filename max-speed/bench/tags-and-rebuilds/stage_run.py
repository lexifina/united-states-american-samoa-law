"""Per-stage timers around a law builder's main(), without editing the builder.

    python -X utf8 stage_run.py <scripts/<country>-law dir> <out.json> -- <builder args...>

Wraps the builder module's top-level stage functions (listed in STAGES, when present) with wall-clock timers,
counts calls, runs main(), and writes {stage: [calls, seconds]} plus the total. The pool workers (spawned processes)
import the module fresh, so time spent inside workers shows up as the wall time of the stage that waits on the pool.
"""
import functools
import json
import os
import subprocess
import sys
import time
from pathlib import Path

T: dict = {}


def main():
    d = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2])
    args = sys.argv[sys.argv.index('--') + 1:]
    sys.path.insert(0, str(d))
    os.chdir(d)
    sys.argv = [str(d / 'build.py'), *args]
    import build  # noqa: E402

    STAGES = ['load_acts', 'acts_from_alpha', 'preparse', 'build_all', 'build_act', 'write_repo', 'plan', 'compose',
              'fill_readme', 'write_tables', 'gate', 'write_manifest', 'write_reproduce', 'history', 'parse_to_cache',
              'read_parsed', 'diff_units', 'units_of_version', 'fetch', 'fetch_all', 'load_versions', 'plan_commits',
              'gate_published', 'read_version', 'left_out_acts', 'act_worker', 'act_events', 'read_act', 'analyse_act']
    T: dict[str, list] = {}
    DEPTH = {'n': 0}


    def wrap(name, fn):
        @functools.wraps(fn)
        def w(*a, **k):
            t = time.perf_counter()
            try:
                return fn(*a, **k)
            finally:
                e = T.setdefault(name, [0, 0.0])
                e[0] += 1
                e[1] += time.perf_counter() - t
        return w


    for name in STAGES:
        if callable(getattr(build, name, None)):
            setattr(build, name, wrap(name, getattr(build, name)))

    # time every git subprocess the builder starts, by its first argument (fast-import, reset, add, commit ...)
    _run = subprocess.run


    def run(cmd, *a, **k):
        t = time.perf_counter()
        try:
            return _run(cmd, *a, **k)
        finally:
            if isinstance(cmd, (list, tuple)) and cmd and cmd[0] == 'git':
                key = 'git ' + next((c for c in cmd[1:] if not c.startswith('-')), '?')
                e = T.setdefault(key, [0, 0.0])
                e[0] += 1
                e[1] += time.perf_counter() - t


    subprocess.run = run
    build.subprocess.run = run

    t0 = time.perf_counter()
    try:
        build.main()
    finally:
        total = time.perf_counter() - t0
        out.write_text(json.dumps({'total': round(total, 1), 'stages': {k: [v[0], round(v[1], 2)] for k, v in
                                    sorted(T.items(), key=lambda kv: -kv[1][1])}}, indent=1), encoding='utf-8')
        print('STAGES', out.read_text(encoding='utf-8'), flush=True)


if __name__ == '__main__':
    main()
