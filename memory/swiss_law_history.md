---
name: swiss-law-history
description: "Swiss federal law git-for-law corpus (BV, DSG, SchKG) from Fedlex: build.py, /watch/swiss-law reader, private repo lexifina/swiss-law; uncommitted site + scripts"
metadata:
  node_type: memory
  type: project
  originSessionId: 300c25f7-92a1-4a97-bc93-84db643ec8b5
  modified: 2026-10-28T14:14:17.826Z
---

Built 2026-10-28 by session gitlaw-SWISS. It follows the shared rules in [[git-for-law]].

**Source.** Fedlex, from two places:
- The SPARQL endpoint `https://fedlex.data.admin.ch/sparqlendpoint` (JOLux ontology).
- Akoma Ntoso XML of each consolidated version (`jolux:isEmbodiedBy`, user-format xml).

XML exists only for some versions: from 2021 for the BV, and from 2019 for the SchKG. Older versions are PDF/doc only and are not used.

**Causes.**
- `jolux:LegalResourceImpact` gives the amending act (eli/oc/…), the article (`art_10_a`, or `text` for the whole act), the in-force date and the type.
- The impacts must be read through `?to jolux:legalResourceSubdivisionIsPartOf <act>`. A STRSTARTS filter on the target scans every impact, and the BIT firewall answers HTTP 400.
- Footnotes (`authorialNote`) carry "Fassung gemäss / Eingefügt durch / Angenommen in der Volksabstimmung … in Kraft seit … (AS …)". They name the cause per paragraph and credit pre-record text.
- A change with no cause is labelled a publisher's correction, never a law. Typesetting differences ("..." vs "…", "[tab]", `<sup>1)</sup>` markers) are normalised away.

**Files.**
- `scripts/swiss-law/build.py`: build site data and repo; `--today` makes it deterministic.
- `scripts/swiss-law/reproduce.py`: writes REPRODUCE.md and `data/versionen.json`.
- `scripts/swiss-law/check_repo.py`: git versus site, 736/736 match.
- `scripts/swiss-law/repo/`: the repo's README, LICENSE and `tools/stand_am.py`.
- The cache is `scripts/swiss-law/.cache` and self-gitignores.

**Site.** `saas-webpage/app/watch/swiss-law/`:
- the hub, `[act]` and `[act]/[article]` pages, each article with SwissReader (Read / Who wrote it / Compare dates), the official footnotes, Relies (citations plus DSG "Begriffe" terms matched with inflection) and Follow (localStorage key `lexifina-watch-swiss-following`)
- `as/` and `as/[id]`, the amending acts with the dates adopted / vote / published / in force
- `method`

`_data/load.ts` has `REPO_CREATED = true` and `REPO_PUBLIC = false`. Another session added those flags.

**Repo.** github.com/lexifina/swiss-law (PRIVATE), local at `C:/Users/alany/Documents/swiss-law`.
- One commit per act per amending act per in-force day.
- Commits are dated noon Zurich.
- Authors are `AS 2021 310 <as-2021-310@fedlex.invalid>`; the first versions and the corrections are by `Bundeskanzlei (Fedlex)`.
- `kuenftig` is the upcoming-changes branch (BV Art. 127 in 2029).
- Tags are `bv/2024-03-03` and `as/2023-628`.
- A rebuild gives the same hashes.
- Push with `git push -f origin main kuenftig --tags` after a rebuild; the build keeps the remote. `--today` is required (it dates the docs commit and splits main from kuenftig).
- **Tell gitlaw-global before any force-push.** global-law pins this repo as a submodule, and gitlaw-global asked for notice. The pushed tools/build.py predates the `--today required` change, so the next rebuild changes the docs commit.

**Why:** the user's goal (2026-10-28) was a Swiss counterpart of the US record with all its semantics, plus a repo that will be made public.

**How to apply:** add acts by appending to `ACTS` in build.py, then rebuild, run check_repo, and force-push. Make it public only when the user says.

**Full-SR scale (2026-10-28, in progress).**
- `fetch_all.py` fills the cache: SPARQL by year slices (a single query gives HTTP 500), metadata 150 acts per query, impacts 60 per query, about 12k XML files at 4 workers. Output is `catalogue.json` and `impacts.json`; progress is in `.cache/PROGRESS.md`.
- `bulk.py` writes the site bundles (`_data/acts/<SR>.json.gz`) and the repo via git fast-import.
  - Folders are SR numbers.
  - Tags are `as/<year>-<n>` only.
  - Site pages render on demand, and `next.config.js` has `outputFileTracingIncludes` for `_data`.

**Scope (transitional rules), not done yet.** The amending acts' AS XML exists (`eli/oc/YYYY/N/de/xml`). Use the agreed shape:
- `scope = [{conditions: [{kind, date}], words, set_by}]`; groups are OR'd and conditions within a group are AND'ed.
- Kinds are commenced_on_or_after, commenced_before, pending_on and subset.
- Trailer: `Applies: <provision> | … | set-by …`.
- "Für hängige Verfahren gilt bisheriges Recht" becomes commenced_on_or_after <Inkrafttreten>. See [[git-for-law]].
