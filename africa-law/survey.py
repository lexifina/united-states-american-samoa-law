"""Which acts can a Peachjam country build? Compare each work's History with what the Internet Archive holds.

    python -X utf8 -u scripts/africa-law/survey.py <slug> <work> [<work> ...]     e.g. zambia 1991/1 1930/42
    python -X utf8 -u scripts/africa-law/survey.py <slug> --top 40                 best-archived works (1 CDX query)

Reads the LII configuration from scripts/<slug>-law/acts.json and caches into scripts/<slug>-law/.cache (shared with
fetch.py, same rate limits). Per work it prints the title, then every History date: `+` the LII lists an expression
for it, `-` an event without an expression, the event kinds, and `*` if the archive holds that expression.
A work is buildable without gaps when every `+` also has `*` (the check of the page itself happens in fetch.py).
"""
import collections
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import peachjam as pj  # noqa: E402

slug = sys.argv[1]
folder = HERE.parent / f"{slug}-law"
cfg = pj.load_config(folder)
lii = cfg["lii"]
c = pj.Cache(folder)

if sys.argv[2] == "--top":
    n = int(sys.argv[3])
    ex = collections.defaultdict(set)
    for host in lii["hosts"]:
        for pre in lii.get("path_prefixes", [""]):
            u = pj.cdx_url(f"{host}{pre}/akn/{lii['cc']}/act/") + "&collapse=urlkey&limit=200000"
            for ts, orig, st, mt in json.loads(c.get(u))[1:]:
                m = re.search(rf"/akn/{lii['cc']}/act/([^@?#]+?)/eng@(\d{{4}}-\d{{2}}-\d{{2}})/?$", orig)
                if m:
                    ex[m.group(1)].add(m.group(2))
    for w, d in sorted(ex.items(), key=lambda kv: -len(kv[1]))[:n]:
        print(f"{w:32} {len(d):3} archived  {min(d)} .. {max(d)}")
    sys.exit()

for work in sys.argv[2:]:
    caps = pj.captures(cfg, c, work)
    if not caps:
        print(work, "NO CAPTURES")
        continue
    info = None
    for day in sorted(caps, reverse=True):
        for ts, orig in caps[day][:3]:
            b = c.get(pj.raw(ts, orig))
            if pj.good_expression_page(b, f"{pj.work_uri(cfg, work)}/eng@{day}"):
                info = pj.page_info(b)
                break
        if info:
            break
    if not info:
        print(work, "no usable archived page")
        continue
    last = max(caps)
    tl = [(t["date"], "+" if (t["read"] or t["date"] == last) else "-", "/".join(e["kind"][:4] for e in t["events"]))
          for t in info["timeline"] if t["date"]]
    listed = [d for d, r, _ in tl if r == "+"]
    print(f"{work} | {info.get('title')} | listed {len(listed)} archived {len(set(listed) & set(caps))}"
          f" | unapplied {info['unapplied_notice'][:1]}")
    print("   ", " ".join(f"{d}{r}{k}{'*' if d in caps else ''}" for d, r, k in sorted(tl)))
