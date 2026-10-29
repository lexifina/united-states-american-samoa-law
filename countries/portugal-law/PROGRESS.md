# Portugal (gitlaw-PT): stopped on coordinator's instruction, 2026-10-28

## Status

Stopped before building. The coordinator said to stop because `lexifina/portugal-law` main already holds another session's
full build. No `corpus.json`, `corpus.d/` or `PUBLISH` was written, so autopush does not pick up this folder.

## What the existing repo holds (lexifina/portugal-law, main, read from a fresh clone on 2026-10-28)

- Head: `88c02e7` "Documentação, tabelas, ferramentas e REPRODUCE.md", dated 2026-10-28. There are 149 commits and 250 tags,
  and no `futuro` branch. Remote branches are `main` and `sync/main` (`0ec7e99`, the scaffold commit).
- It covers three acts from the DR Legislação Consolidada:
  - Constituição (`decreto-aprovacao-constituicao/1976-34520775`, from 1976-04-25): 10 commits.
  - Código Civil (`decreto-lei/1966-34509075`, from 1967-06-01): 109 commits. The DR timeline only starts in 1975.
  - Código do Trabalho (`lei/2009-34546475`, from 2009-02-17): 29 commits.
- It was built by a bespoke builder, not the shared `gitlaw_common` builder. That builder ships in the repo's `tools/`
  (`build.py`, `model.py`, `source.py`, `templates/`, `check_repo.py`, `em_vigor.py`, `test_repo.py`, `reproduce.py`). It reads
  the DR's OutSystems screen-service JSON calls: act record, amendment timeline, and the full text per day.
- Its REPRODUCE.md reports:
  - 111 days checked with 0 mismatches, plus a word-for-word check against the DR text;
  - a hash-for-hash rebuild that came out identical;
  - 6 of 6 smoke tests passed.
- Its source folder (`scripts/portugal-law/` in the lexifina repo, per its REPRODUCE.md) is not on this machine, and not in
  the lexifina git history.
- **Not in it:** the Código Penal and Lei n.º 58/2019, the two acts this wave's brief asked for.

## What this session left here (useful if Portugal is extended later)

- `source.py` and `model.py` are copied from the repo's `tools/`. `source.py` was changed to call curl only, at 3 requests a
  second with 3 workers, and to log every request to `.cache/requests.jsonl`. `templates/` holds copies of the request
  templates. Line endings are LF.
- The DR API still works with the shipped version and CSRF tokens (checked 2026-10-28, about 22:15 UTC).
- Verified DR keys:
  - Código Penal: `decreto-lei/1995-34437675`, Decreto-Lei n.º 48/95, published 1995-03-15, DiplomaLegisId 185720.
  - The guess `lei/2019-123815982` for Lei n.º 58/2019 is **wrong**: the DR returned an empty record. The right key is still
    to be found.
- `.cache/` holds about 5 cached calls and is gitignored.
- WebSearch calls used: 0.

## Next step, if the coordinator wants it

Add the Código Penal, and Lei 58/2019 once its key is found, to `ACTS` in the existing repo's `tools/build.py`. It is written
for any act the DR consolidates. This needs coordinating with the session or person who owns that builder.
