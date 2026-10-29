# Paraguay (gitlaw-PY): builder issues

## RESOLVED (same_day versions, 2026-10-28): a change on the same day as an act's first version cannot be credited

Código Procesal Penal: Ley 1444/1999 sets the day the Code first applies (9 July 1999) and, from that same day, repeals art. 17 inc. 15 and art. 505 of it. `validate()` requires distinct `from` days ("versions must have distinct "from" days in order"), and the first version is committed as a whole to `first_law`, so there is no way to show the enacted wording and then a same-day commit by Ley 1444. Workaround in our data: the first version (1999-07-09) is the text as it first applied, without those two provisions, with a version note and a decision saying so. A possible fix: allow a second version with the same `from` as the first (or a `commencement_changes` field) and order its commit after the start commit.

**Fixed by the coordinator (2026-10-28):** versions may now share a day with `"same_day": true` (SCHEMA.md). The first version can be the act as enacted, credited to it, followed on the same day by a same-day version credited to Ley 1444 art. 18.
