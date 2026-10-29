---
name: country-law-repos
description: "Private lexifina/<country>-law repo for every jurisdiction (201 new, 2026-10-28), each a sources scaffold made by scripts/world-law/build_countries.py; countries.json feeds global-law's tree"
metadata:
  node_type: memory
  type: project
  originSessionId: e7729470-b6e7-44b2-863f-701f129cba2f
  modified: 2026-10-28T15:41:28.738Z
---

On 2026-10-28 the user asked, "very high priority", for a private law-history repo for every country, added to global-law. That replaced my proposal to create repos only for build-ready countries.

**What exists:**
- 201 new private repos named `lexifina/<slug>-law`, where the slug is the ASCII English name (`france-law`, `cote-divoire-law`, `sao-tome-and-principe-law`).
- 8 jurisdictions keep the repos they already had:
  - DE `grundgesetz`
  - GB `uk-law-history`
  - US `us-code-history`
  - CH `swiss-law`
  - EE, LI, LU and MT: `<name>-law`, made by other sessions
- In total, 209 jurisdictions: the 193 UN states plus 16 others (VA, PS, TW, XK, HK, MO, JE, GG, IM, GI, BM, KY, VG, GL, FO, PR).

**What's in each repo:** one commit, "<Name>: sources, before any law", dated 2026-10-28T12:00Z by `Lexifina <world-law@lexifina.com>`, holding four files:
- **README.md**: has a "Can it be built?" verdict, the official sources, and existing open projects (with a warning that volunteer transcriptions must be reconciled against the official text).
- **SOURCES.md**: the register rows.
- **jurisdiction.json**: `path` = ISO lowercase, `build` status.
- **REPRODUCE.md**: script blob, register sha256, and the models used.

Build status counts: ready 23, scrape 34, partial 22, gazette 120, none 10.

**Files:**
- `scripts/world-law/register.json`: the register exported from the artifact.
- `scripts/world-law/build_countries.py`: run it as `python scripts/world-law/build_countries.py ~/Documents/world-law-repos [--push] [--only slug]`.
  - It is deterministic, and it refuses a non-empty target.
  - Push markers are `.pushed-<repo>` in the out dir. Repos that already exist are left alone.
- `scripts/world-law/countries.json`: every jurisdiction with its repo URL and build status. gitlaw-global's `scripts/global-law/build.py` should read it instead of its hard-coded JURISDICTIONS. That builder change and the global-law rebuild belong to gitlaw-global.
- Local checkouts are in `~/Documents/world-law-repos/`. All of this is uncommitted in the main repo ([[commits-by-hand]]).

**Design (user agreed):** global-law keeps one root commit per law taking effect. Country folders get jurisdiction.json and SOURCES.md. A country repo becomes a corpus submodule only once it holds a law commit with an In-force trailer.

Related: [[global-law-repo]], [[world-law-sources]], [[git-for-law]].

**Visibility (user, 2026-10-29):** country repos are **meant to be public**. Exceptions kept private on purpose: global-law, every sub-national repo (`australia-*-law`, `canada-*-law`, `united-states-*-law`), plus `app` and `publish-test`. On 2026-10-29 I made those 21 private, after the alan-yahya account had made them public on 10-28. Still public, pending a decision: aland-law, armenia-sublaws and malta-acts. New sub-national repos must be created private.

**Security scan (2026-10-29):** gitleaks and trufflehog over the full history of 228 repos. No Lexifina credential. The one real key was BOPA's public Azure Functions key in andorra-law tools/build/fetch.py. The scan was killed for low RAM before russia-law, spain-law and global-law, and before the trufflehog pass on armenia-sublaws, costa-rica-law, czechia-law and united-states-california-law. Secret scanning and push protection are now on for all 214 public repos and as org defaults; Dependabot alerts are an org default too. The org does not require 2FA yet; that is a web-only setting. Personal email in commits: see [[commit-guard-no-personal-data]].
