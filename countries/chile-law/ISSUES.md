# Chile: issues for the shared builder

## on.py: a bare article number is ambiguous when transitional provisions share the number (2026-10-28)

`python tools/on.py 2020-01-01 constitucion 19` prints "constitucion/19 was not in the text on 2020-01-01": the
pattern `[a-z-]*0*19` in `resolve()` matches both `art-019.md` and `disp-transitoria-019.md` (and in Ley 19.628,
`art-002.md` and `art-transitorio-002.md`), so `len(hits) == 1` fails. Suggest preferring `art-` hits when several
match. Worked around in `repo/tools/en_vigor_el.py`, which maps a bare number to `art-NNN` before calling on.py.

**Fixed by the coordinator (2026-10-28):** on.py now resolves a bare number to the art- file when a transitional provision shares the number, and reports an ambiguity otherwise. Takes effect on the next build.
