# Git for law: South America plan

Written on 2026-10-28. This is the tracker for building every South American country to the git-for-law standard. Tick items here as they finish, so any session can pick up the work.

- Shared rules: `memory/git_for_law.md`.
- Model builders:
  - `scripts/swiss-law` for dated official versions.
  - `scripts/estonia-law`, `liechtenstein-law` and `luxembourg-law` for small corpora.
  - `scripts/uk-law-git` for effects and commencement.
  - `scripts/grundgesetz` for a history rebuilt from a gazette.
- Scaffold repos already exist as private `lexifina/<country>-law` repos, each with sources only (`scripts/world-law/countries.json`).

## Countries

| ISO | Country | Language | Register verdict | Best official source | Kind of build |
|---|---|---|---|---|---|
| CL | Chile | es | scrape | BCN LeyChile: dated versions since 1998, links between norms, RDF/JSON. The legacy XML returns 401. | A, versions |
| UY | Uruguay | es | partial | IMPO: per article "Redacción dada por: Ley …", with the original text beside it | A, versions per article |
| BR | Brazil | pt | partial | Planalto compiled text keeps superseded wording struck through, with "(Redação dada pela Lei …)". LexML gives identifiers through OAI-PMH. | B, unpick the struck-through text |
| CO | Colombia | es | partial | SUIN-Juriscol: per-article "Modificado/Adicionado por", plus Constitutional Court rulings | B, plus a court layer |
| AR | Argentina | es | gazette | InfoLEG: "modifica / modificada por" graph plus updated text; bulk ZIP on datos.gob.ar (2023). Boletín Oficial for the amending text. | B, replay |
| PE | Peru | es | gazette | El Peruano (gazette). SPIJ consolidation is paid, so it is excluded. | C, replay from the gazette |
| PY | Paraguay | es | gazette | BACN, partly consolidated, plus Gaceta Oficial | C |
| EC | Ecuador | es | gazette | Registro Oficial PDFs only | C |
| BO | Bolivia | es | gazette | Gaceta Oficial (live only in archive copies) | C |
| VE | Venezuela | es | gazette | Imprenta Nacional / Gaceta Oficial (gaps) | C |
| GY | Guyana | en | gazette | Laws of Guyana (consolidated revisions), Official Gazette | C, revisions |
| SR | Suriname | nl | gazette | DNA wetgeving, partly consolidated; Staatsblad | C |

Not separate countries: French Guiana is part of France, so it belongs in `france-law`. The Falklands are a UK Overseas Territory, have no scaffold, and are out of scope unless asked.

Prior art to check and reconcile, never to copy text from:
- pisanvs/ley-chile (AGPL, all Chilean law)
- ypsoftware/leyes-paraguayas
- Duvet05/Constitucion-Politica-del-Peru
- Evaldoes/legislacao-br (CC0)
- datos-justicia-argentina Infoleg dataset

Also check whether any legalize-dev repo covers these countries, and look at its first commits.

## Scope

- **Phase 1 (every country):** the Constitution plus 2 core acts. Use the Civil Code, plus the Penal Code or the data protection law, whichever has the better dated source. This matches the Estonia, Liechtenstein and Luxembourg model and gets all 12 countries to "law in git" quickly.
  - Constitutions have few, well-documented amendments.
  - Even gazette-only countries can be replayed by hand-indexing the amending acts.
- **Phase 2 (where the source allows):** all national law.
  - Chile: all of LeyChile.
  - Uruguay: all of IMPO's leyes.
  - Brazil: Planalto federal leis plus the CF/88 ECs.
  - Colombia: SUIN leyes.
  - Argentina: the InfoLEG graph.
  - Gazette-only countries stay at Phase 1 until a gazette index exists.

## Functionality that must not be dropped (checklist per country)

Repo:
- [ ] One commit per law per in-force date. The author is the law, with a `.invalid` email (`ley-19628@leychile.invalid`). The committer is `Lexifina <<country>-law@lexifina.com>`.
- [ ] Author and committer date = the in-force date at noon local time (Santiago, Brasília, …). Clamp anything before 1970 to 1970-01-01, one second apart, and keep the real date in a trailer.
- [ ] ASCII trailers only: `In-force`, `Enacted`, `Published`, `Effect-id`, `Applies:` (groups OR'd, conditions AND'd), `Temporary-until`, `Restores`, `Words-changed`. Check each country's trailers with `git interpret-trailers --parse`.
- [ ] One file per provision, one unit per line, with paths from official identifiers (`constitucion/art-019.md`).
- [ ] No silent folding. Text that no law explains gets a labelled publisher commit. Court rulings that remove or condition text are their own commits, authored by the ruling (Colombia C-xxx/yy inexequible; Brazil STF ADI). Temporary measures and their expiry are commits too (Brazil Medidas Provisórias lapsing; Argentina DNU).
- [ ] Laws adopted but not yet in force go on a `futuro` branch. Tools use `--no-merges`.
- [ ] Renumbering: pair unmatched provisions by at least half of their words shared.
- [ ] README in the standard shape: the lawyer's questions as git commands, the dates used, checks, what "author" means, what it does not show, how it is built, and the licence with the exact attribution. The date idiom is `--before="YYYY-MM-DDT23:59:59Z"`, with a PowerShell form, `--word-diff` and `fetch --force --tags`.
- [ ] `tools/en_vigor_el.py DATE PATH` (Brazil: `vigente_em.py`; Guyana: `in_force_on.py`; Suriname: `geldend_op.py`). It uses the standard library only and picks the version by the `In-force` trailer.
- [ ] `REPRODUCE.md` generated by the builder, with these filled in at build time:
  - sources and retrieval dates
  - request counts
  - commands
  - tool versions
  - script blob hash and data sha256
  - the hash-for-hash rebuild result
  - decisions made by hand
  - AI disclosure: Claude Opus 5.5 builds, and no model writes legal text or runs at git-build time
- [ ] The builder takes a required `--docs-date`, refuses a non-empty target, keeps `origin` and is deterministic: two builds give an identical HEAD.

Verification:
- [ ] check_repo two-sided: the after-text is present on the in-force day and the before-text on the day before, after normalising dashes, quotes, spaces and old footnote marks.
- [ ] Repo against the official consolidated text today: 0 mismatches.
- [ ] Health checks: no merges on main, `%ct` monotonic, nothing dated in the future.
- [ ] Blind agent test: give a sub-agent the clone and 7 lawyer questions with known answers.

Integration:
- [ ] Each country's default in-force rule is coded and cited (to verify per country):
  - BR: LINDB art. 1, 45 days after publication.
  - AR: CCyC art. 5, 8 days after publication.
  - PE: Const. art. 109, the day after publication.
  - CO: Ley 4/1913 art. 52.
  - CL: Código Civil art. 7.
  - UY, PY, EC, BO, VE, GY, SR: to research.
- [ ] Applicability groups from transitional articles (disposiciones transitorias) as `Applies:` trailers.
- [ ] global-law: added in one coordinated rebuild that reads countries.json and pins published heads. After pinning, add commits rather than force-pushing. law.py and MCP cross-check tests for every country through its on-date tool.
- [ ] /watch: one data-driven country reader (see bottleneck 6) with a list as well as the timeline. `REPO_PUBLIC = false`, noindex.
- [ ] A memory per country, a line in git_for_law.md, a CHANGELOG.md entry in global-law, and an update to the tracker (`collect.py` CORPORA).

## Bottlenecks and their fixes

1. **The WebSearch cap (200 per session, shared by all sub-agents).**
   - Run each country as its own Claude session (gitlaw-CL, gitlaw-BR, …) rather than as sub-agents of one session, so each gets its own cap and context.
   - Start every brief from the register's URLs (WebFetch has no cap).
   - Give each country at most 25 searches.
   - Optionally set `CLAUDE_CODE_MAX_WEB_SEARCHES_PER_SESSION` higher before starting.
2. **Twelve copies of a 900-line builder.** Before fanning out, extract the shared parts of the swiss, estonia and liechtenstein builders into `scripts/gitlaw_common/`:
   - a streamed `git fast-import` Writer, and a `git cat-file --batch` reader
   - the trailer builder and checker
   - the sha256 URL cache over curl
   - the REPRODUCE.md and README template renderer
   - the normalise-and-compare check harness
   - the on-date tool template
   - the health checks and the determinism compare

   Each country then writes only fetch, parse and attribute. About one hour, done once.
3. **Fetching.**
   - Python urllib fails TLS on government chains, so shell out to curl.
   - Keep a polite per-host rate (1 to 2 requests per second, cached on disk, resumable).
   - Use the Wayback fallback (`archive.org/wayback/available`) for geoblocked portals. Planalto, SUIN, BOs and Venezuela need probing on day 1.
   - Bulk where possible: the InfoLEG ZIP, LexML OAI-PMH and LeyChile RDF.
4. **Gazette-only countries (PE, PY, EC, BO, VE, GY, SR).** The amending acts have to be indexed by hand.
   - Phase 1 keeps this small: constitutions have a handful of amendments.
   - Run these sessions from the start rather than last, because they take longest.
5. **global-law rebuilds are serial and change hashes.** One owner (gitlaw-global) does a single rebuild once all 12 countries have pushed. Countries never force-push after they are pinned.
6. **The shared `/watch` rail and twelve bespoke readers.**
   - Build one `/watch/[country]` reader driven by each corpus's site JSON, which is emitted by `build.py --site-data`.
   - One coordinator owns the rail edit and adds all 12 items in one change.
7. **Session handoff.** This machine has no local clones, Docker is stopped and gh isn't installed.
   - Builders need only Python, git and curl, and HTTPS pushes to lexifina work.
   - Clone the scaffolds into `~/Documents/<country>-law`.
   - Models at data-build time are avoided. If summaries are wanted later, they need the backend container, and they must be disclosed.
8. **Coordination noise.** Each session keeps `scripts/<country>-law/PROGRESS.md` (resumable) and messages findings to the coordinator, who records them in git_for_law.md and CHANGELOG.md. The tracker dashboard is refreshed every 30 min.

## Order and timing (wall clock, all in parallel)

| Step | What | Who | Time |
|---|---|---|---|
| 0 | `gitlaw_common` extraction plus tests; a probe script that hits every source once and records status, format, licence and robots | coordinator | ~1–2 h |
| 1 | Twelve country sessions start together, A and B tiers first, then C. Each does: source study → fetch → parse → attribute → build → check → push → PROGRESS | 12 sessions | A: 3–5 h; B: 5–8 h; C: 6–10 h |
| 2 | Shared /watch country reader; rail items | coordinator, during step 1 | ~2 h |
| 3 | global-law rebuild with all 12 countries, plus law.py and MCP tests per country | gitlaw-global | ~1 h after the last push |
| 4 | Blind agent tests, memories, tracker, a summary for the user. The user commits the main repo by hand; repos stay private. | coordinator | ~1 h |
| 5 | Phase 2 full corpora for CL, UY, BR, CO and AR | 5 sessions | days |
