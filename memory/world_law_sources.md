---
name: world-law-sources
description: "World law project research (2026-10-28): artifact register of official legislation sources, standards, git-for-law prior art (legalize.dev is the big one), datasets, and the HN critique of our post"
metadata:
  node_type: memory
  type: project
  originSessionId: e7729470-b6e7-44b2-863f-701f129cba2f
  modified: 2026-10-28T13:39:51.967Z
---

On 2026-10-28 the user set a goal to research every useful resource for a "world law" project, starting from the HN thread on our post (item 50268380, 173 comments).

The result is the artifact "World Law Sources", https://claude.ai/artifact/DdS9F6yqpPZtV2i7FGQhYZ. Version 2 has 155 sources (73 countries with an official source) with filters, and each source says whether it has point-in-time versions, amendment links and an API. A local copy was saved in that session's scratchpad.

**Key findings**
- **legalize.dev** (github.com/legalize-dev) is the closest prior art: one Markdown file per law and one git commit per reform.
  - 38 repos covering about 31 countries; legalize-es has about 2k stars.
  - MIT tooling, a REST API, and an MCP tool `law_at_date`.
  - Commits are dated by publication, not by in-force date, which is our point of difference.
  - Check it before writing any new country parser.
- **LawVM** (eliask/lawvm, MIT) is an amendment compiler with the same replay-vs-consolidation method as ours. Finland is done and Estonia is partial.
- The sources most ready for per-provision history:
  - UK (legislation.gov.uk)
  - France (LEGI dumps, Etalab 2.0)
  - Spain (BOE API)
  - Austria (RIS)
  - Finland (Finlex)
  - NZ API
  - Canada point-in-time XML
  - Japan e-Gov API v2
  - HK e-Legislation
  - eCFR versioner
  - EUR-Lex/CELLAR, for EU amendment graphs
- Use ELI and Akoma Ntoso as the identifier and storage standards.

**HN critique to act on**
- The post linked nowhere to try it ("can't git-clone this").
- Readers said the text read as AI-written.
- A lawyer said commercial tools already give point-in-time text.
- Following renumbering is the hard part.

**Link checks:** Python's urllib fails on this machine with a self-signed cert in the chain (some proxy or antivirus), so use curl. URL lists written on Windows need `tr -d '\r'` before a bash `while read` loop.

The register feeds [[global-law-repo]] (the private superproject, built the same day). Related: [[us-code-history]], [[grundgesetz-watch]], [[uk-law-history]], [[git-for-the-us-code-blog]].

**Verification (v2, same day):** three passes read each source's own pages. 17 rows remain unconfirmed and are listed on the page.

Corrections found:
- blawx.com is hijacked; use github.com/Lexpedite/blawx.
- Legilux is CC BY, not CC0.
- Romania has a SOAP API, and Lithuania publishes open data at data.gov.lt/datasets/2613.
- Hungary's register moved to njt.jog.gov.hu.
- AustLII bans AI and dataset use.
- FAOLEX has bulk CSV under CC BY-NC-SA 3.0 IGO.
- Costa Rica's SCIJ now redirects to sinalevi.go.cr.

**v3 (same day):** 363 rows covering 189 countries and territories, including every UN member state, the Canadian provinces and the Australian states. It also adds about 75 GitHub and Hugging Face repos found per jurisdiction. Only 2 rows remain unconfirmed (Thailand OCS and Tajikistan).

Notable findings:
- **legalize-kr** puts all Korean statutes in git, one commit per amendment. It has 1.5k stars and is separate from legalize.dev.
- Volunteer one-commit-per-amendment repos exist for many countries: Chile, Mexico, Italy, Japan, NZ, Norway, Lithuania, Hungary, Poland, Switzerland, Luxembourg, Paraguay, Pakistan and North Korea.
- **Open APIs:**
  - BC Laws (CiviX) has point-in-time XML.
  - Queensland is the only Australian state with an API.
  - Ukraine's data.rada.gov.ua API (CC BY 4.0) covers texts and their revisions.
- The ten Laws.Africa Peachjam LIIs are Africa's only point-in-time sources. The full Laws.Africa API is paid (from ZAR 42k per country per month).
- **No official online law:** Cambodia, North Korea, Haiti, CAR, Guinea-Bissau, São Tomé, Niger, Yemen, Eritrea and Ethiopia.
- **Blocked sites:** the Wayback Machine (archive.org/wayback/available) confirmed most sites that block live readers.

**Correction (gitlaw-GER, 2026-10-28):** legalize-de was bootstrapped on 2026-04-03 with every law as "versión original 2026", so it has no earlier history. Check the first commits of each legalize-xx repo before counting it as history. The only open history of all German federal law is QuantLaw's data branch (real history from 2019-06-10; the 2018 init commit is empty; it has gaps, e.g. 3,646 files missing for one day in May 2026). The artifact (v5) is updated.

**Publishing (2026-10-28):** after the account switch, republishing the artifact returns HTTP 403, because this CLI account is not its owner (Taketomo). The local file has the latest fixes; republish from the owner account.

**Analysis agenda (2026-10-28):** artifact "World Law Analysis Agenda", https://claude.ai/artifact/Rq7VnJZHbjCiQCSTp9iHzd. It reviews 13 research strands (growth, networks, readability, survival, constitutional amendment, diffusion, topic coding with CAP, temporary law, EU transposition, omnibus, RegData-style obligation counts, hub provisions, tools and temporal KG models). Run first: survival of provision wording, temporary-law catalogue, legal stock index by topic, readability of amended vs original text, data-protection diffusion, EU transposition delay. The real-data story page "Law in Motion" is https://claude.ai/artifact/KeSEY8EpbVw3zZracyGnHo, and its scripts are stories.py and story_data.py in that session's scratchpad only.
