# Alternative hosted archives (coordinator, 2026-10-29): check these before fetching a country page by page

The user asked us to use every hosted archive, including our competitors', where we're allowed to. Checked today:

## 1. legalize.dev (github.com/legalize-dev): reconstructed histories, open data. Use them as a source.
One repo per country, one Markdown file per law and one commit per reform, built by an MIT pipeline from official sources. **Their data licences are open or public domain** (each repo's LICENSE, under "LEGISLATIVE CONTENT"). Their commits are dated by **publication** of the amending law, not by in-force day, so take the text from them, re-date each version from the amending law's own in-force clause, and check today's text against the official source.

| Repo | Commits | Data licence | Useful for |
|---|---|---|---|
| legalize-be | 40,495 | Belgian federal open data (CC0 by default) | **Belgium: Justel's archived consolidated versions**, which robots.txt kept us from crawling. The Constitution from 1994, laws from 1831. |
| legalize-gr | 6,851 | public domain (official state texts) | **Finding amending laws only.** Checked 10-29: 6,805 commits only add a file per ΦΕΚ issue as published, never amended, and the text is lossy (4624/2019: 53 of 87 articles verbatim, 4 missing, 30 garbled). |
| legalize-ro | 450 | public domain (Legea 8/1996 art. 9) | Romania: cross-check and Phase 2 acts |
| legalize-ad | 3,625 | public domain (Llei drets d'autor art. 4.2) | Andorra: BOPA texts since 1989 (not consolidated) |
| legalize-uy | 10,158 | Uruguay open-data licence (attribution required) | Uruguay: cross-check and acts IMPO makes slow |
| legalize-ar | 38,153 | CC BY 4.0 (attribution to SAIJ) | Argentina: SAIJ-based history, Código Aduanero |
| legalize-co | 79,199 | Ley 23/1982 art. 41 | Colombia: cross-check |
| legalize-cl | 6,401 | public domain | Chile: cross-check |
| legalize-lt, -lv | 73k, 16.5k | CC BY 4.0 / public domain | **Lithuania and Latvia: source** (being built by the fork's agents) |
| legalize-fr, -pt, -it, -nl, -cz, -ie, -at | 16k–427k | Etalab / open / CC0 / CC BY | countries other sessions built; cross-check only |
| legalize-dk | 0 | – | empty |

Record each as a source in corpus.json, with the legalize repo, commit hash, its data licence and the original official source named in the file's YAML `source` field. Attribution goes in the README. Check each repo's first commits: some (legalize-de, legalize-cl, legalize-cz, legalize-pt) started from a 2026 snapshot, with no real earlier history. **Check its text too:** compare a sample of articles word for word with the official text before you trust a legalize repo as a text source (legalize-gr failed this check). Commit count alone proves nothing: a repo can have many commits that only add files.

## 2. Volunteer one-commit-per-amendment repos (World Law Sources register v3)
Chile, Mexico, Italy, Japan, NZ, Norway, Lithuania, Hungary, Poland, Switzerland, Luxembourg, Paraguay and Pakistan. Check each repo's licence and source. MIT or CC0 repos built from official texts can serve like legalize. The rest are for reconciliation only.

## 3. Constitute Project (constituteproject.org): discovery and checking only
It has an open JSON API (`/service/constitutions?lang=en&historic=true`), with 240 texts, and for English-language countries these are the original English. Recent ones: Nigeria 2023, Sierra Leone 2022, Lesotho 2025, Barbados 2026, Belize 2022, Botswana 2021, Dominica 2014, Bangladesh 2018, Malawi 2017, Seychelles 2025, Guyana 2016, Jamaica 2023. **Its terms forbid commercial use, so never copy its text into a corpus.** Use it to learn which amendments exist and what today's text should say, then find the official text for each.

## 4. FAOLEX (bulk CSV, CC BY-NC-SA 3.0 IGO): discovery only
Its metadata names amending acts and dates for many countries. The licence is non-commercial, so don't copy text from it.

## 5. Laws.Africa / Peachjam LIIs: archived captures only (see africa-law/PEACHJAM.md)
There is no open bulk dump (commons.laws.africa returns 404, and the paid API costs ZAR 42k a month per country). Read pages through Common Crawl (wayback.cc_captures, which now works without the index server) and archive.org.

## 6. Common Crawl and archive.org
See SPEED RULE 2 in south-america-law/BRIEF.md: Common Crawl's index files are now read directly, with no rate limit; archive.org is last.

Never: AustLII (it bans AI and dataset use), bot challenges, logins or paywalls.
