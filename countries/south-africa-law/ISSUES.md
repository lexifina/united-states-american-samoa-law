# Issues for the coordinator (gitlaw-ZA)

## 1. gov.za and justice.gov.za terms say "non-commercial" — CLOSED 2026-10-28

Resolved by the coordinator: the user decided to proceed despite the source terms; South African legislation has no
copyright (Copyright Act s. 12(8)(a)). The coordinator wrote PUBLISH. The terms are stated in the README's Licence
section and in LICENSE.

Original note:

Both government sites carry the same GCIS-style notice (read 2026-10-28):

- gov.za, /terms-and-conditions-use-0: "Users may view, copy, download to a local drive, print and distribute the
  content of this website, or any part thereof only for non-commercial informational or reference purposes. Users who
  wish to use content from this site for commercial purposes may only do so with the prior written permission obtained
  from the web manager ... electronic@gcis.gov.za." Notice: "© GCIS2018: ALL RIGHTS RESERVED."
- justice.gov.za, /about_web/terms_conditions.htm: same wording; permission from webmaster@justice.gov.za; notice
  "©Department of Justice and Constitutional Development: ALL RIGHTS RESERVED."

Both robots.txt files allow the pages we read. The texts we take from them are Acts of Parliament and gazette
notices; Copyright Act 98 of 1978 s. 12(8)(a): "No copyright shall subsist in official texts of a legislative,
administrative or legal nature". So the law text itself is free, but the sites' terms of use still limit use of
"the content of this website" to non-commercial purposes, and GCIS's consolidation (its HTML) and the DoJ PDF are
editorial works. Every ZA source we have is one of these two sites (or Wayback copies of gov.za / info.gov.za).

I have kept going (private repo, no PUBLISH yet) and recorded the terms in PROGRESS.md. Please decide whether
lexifina's use counts as non-commercial reference here, or whether someone should email electronic@gcis.gov.za and
webmaster@justice.gov.za for written permission. I will not write PUBLISH until you answer.

## 2. lawlibrary.org.za (Laws.Africa Peachjam LII for South Africa)

Not fetched beyond robots.txt and the terms page: every /akn/za/ page answered 403 with a Cloudflare challenge;
robots.txt has Content-Signal ai-input=no and blocks ClaudeBot; terms s. 4 forbid scraping and bulk downloading;
content CC BY-NC 4.0. Following your update, Wayback captures of it would be allowed for gaps, but I have not needed
them so far.

Update (later the same day): following your update I now use 11 pinned Wayback captures of LawLibrary point-in-time
expressions of the Constitution, only for wordings that no government source gives (listed in corpus decisions and
the README, with the CC BY-NC 4.0 licence and attribution). Note that this licence is non-commercial too, so it falls
under the same question as #1.
