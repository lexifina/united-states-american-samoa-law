"""Finds the versions LeyChile did not reconstruct faithfully, and so the oldest day from which a code's history holds.

    python -X utf8 scripts/chile-law/codes/anachronism.py slug [slug...]     # one line per version

A version in force from day D cannot carry an amendment note naming a norm published after D. LeyChile's oldest
versions of the 19th-century codes do: their "texto original" is the text of the 1980s or 1990s with the notes of
the norms that changed it. Two tests, both from the source's own notes:
  - a note's Diario Oficial date ("D.O. 23.07.1986") is later than D;
  - a note names a Ley whose number is at least that of a Ley which LeyChile's versions lists (get_versiones of every
    act we fetch) show published more than SLACK days after D. Chilean law numbers are given in order, so that Ley
    is later than D too.
When LeyChile's oldest version of a code holds no article text, its old versions are reconstructions and the code's
history starts after the last anachronistic version (`start_day`). Otherwise each anachronistic note is a defect of
one provision, disclosed in the version notes (`defects`).
"""
from __future__ import annotations

import datetime as dt
import sys
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import fetch  # noqa: E402
import parse  # noqa: E402
from fetch_codes import CHAINS  # noqa: E402

SLACK = 60
# Act slugs whose versions lists are left out of ley_dates (parse_codes sets it): a part published before these acts
# were added must regenerate byte-identical, and their lists date Leyes (e.g. Ley 18.838) that part 80-batch4 names
# without a day.
EXCLUDE: set[str] = set()


@lru_cache(maxsize=1)
def ley_dates() -> list[tuple[int, str]]:
    """(Ley number, publication day) for every Ley in the versions lists of every act, sorted by number."""
    seen: dict[int, str] = {}
    for slug, chain in list(fetch.ACTS.items()) + list(CHAINS.items()):
        if slug in EXCLUDE:
            continue
        for idn in chain:
            try:
                vs = fetch.versions(idn, offline=True)
            except FileNotFoundError:
                continue
            for v in vs:
                for m in fetch.as_list(v.get('Modificatorias', {}).get('Modificatoria')):
                    if (m.get('@tipoNorma') or '').upper().startswith('LEY') and str(m.get('@nroNorma')).isdigit():
                        pub = parse.pub_date(m.get('@fechaPublicacion', ''))
                        if pub:
                            seen[int(m['@nroNorma'])] = pub
    return sorted(seen.items())


def first_ley_after(day: str) -> int | None:
    """The smallest Ley number known to be published more than SLACK days after `day`."""
    lim = (dt.date.fromisoformat(day) + dt.timedelta(days=SLACK)).isoformat()
    later = [n for n, pub in ley_dates() if pub > lim]
    return min(later) if later else None


def late_notes(raw: bytes, day: str, part=None, dated: frozenset = frozenset()) -> list[tuple[str, str, str]]:
    """(why, unit, note) for every note that names a norm published after `day`, except norms LeyChile's versions list
    itself puts in force on `day` (`dated`: a law published later with retroactive effect, e.g. Ley 21.827, published
    2026-08-12, in force 2026-07-01 for Ley 20.529)."""
    r = parse.read_version(raw, 4, part)
    cap = first_ley_after(day)
    out = []
    for k, u in r['units'].items():
        for n in u['notes']:
            refs, dates = parse.note_refs([n])
            if refs and refs <= dated:
                continue
            late = [d for d in dates if d > day]
            if late:
                out.append((f'D.O. {max(late)}', k, n))
                continue
            big = [num for t, num in refs if t == 'ley' and cap is not None and num >= cap]
            if big:
                out.append((f'Ley {max(big)} >= Ley {cap}', k, n))
    return sorted(out)


@lru_cache(maxsize=None)
def scan(slug: str) -> list[tuple[int, str, list]]:
    rows = []
    for idn in CHAINS[slug]:
        prev = None
        for v in fetch.versions(idn, offline=True):
            day = v['@vigenteDesde']
            dated = frozenset(
                (parse.norm_type(m.get('@tipoNorma') or ''), int(m['@nroNorma']))
                for m in fetch.as_list(((prev or {}).get('Modificatorias') or {}).get('Modificatoria'))
                if m.get('@inicioVigencia') == day and str(m.get('@nroNorma') or '').isdigit())
            prev = v
            if day >= '2222':
                continue
            raw = fetch.fetch(fetch.version_url(idn, day), offline=True)
            rows.append((idn, day, late_notes(raw, day, dated=dated)))
    return rows


def original_has_text(slug: str) -> bool:
    """Whether LeyChile's oldest version of the code holds any article (CCom's "Texto Original" is only a PDF link)."""
    idn = CHAINS[slug][0]
    v = fetch.versions(idn, offline=True)[0]
    r = parse.read_version(fetch.fetch(fetch.version_url(idn, v['@vigenteDesde']), offline=True), 4)
    return any(k.startswith('art-') for k in r['units'])


def start_day(slug: str) -> tuple[str | None, list[str]]:
    """Where a code's history must start (None: from LeyChile's first version), and the evidence.

    Only when LeyChile's oldest version holds no article text are its later old versions reconstructions rather
    than texts LeyChile had: then the history starts after the last anachronistic version. Elsewhere anachronistic
    notes are single-provision defects, disclosed per version (`defects`), not a reason to drop history."""
    if original_has_text(slug):
        return None, []
    rows = scan(slug)
    bad = [i for i, r in enumerate(rows) if r[2]]
    if not bad:
        return None, []
    last = bad[-1]
    ev = [f'{rows[i][1]}: {len(rows[i][2])} notes, e.g. {rows[i][2][-1][1]} "{rows[i][2][-1][2][:80]}" ({rows[i][2][-1][0]})'
          for i in bad]
    return (rows[last + 1][1] if last + 1 < len(rows) else None), ev


def defects(slug: str) -> dict[str, list[tuple[str, str, str]]]:
    """{version day: [(why, unit, note)]} for every version whose notes name a norm published after its day."""
    return {day: late for _idn, day, late in scan(slug) if late}


if __name__ == '__main__':
    for s in sys.argv[1:]:
        for idn, day, late in scan(s):
            print(s, idn, day, len(late), (late[-1][0] + ' ' + late[-1][1] + ' ' + late[-1][2][:80]) if late else '')
        print(s, 'start', start_day(s)[0])
