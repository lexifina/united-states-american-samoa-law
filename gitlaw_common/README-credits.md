# Credits proposed by a model (CORPUS-STANDARD.md §5b)

Where a source names no amending law, the builder credits the change to the publisher. `credits.py` lets a model
propose the law, and publishes a proposal only once a rule has checked it and a reviewer has signed it off.

1. **Propose.** Put the proposals in `<country folder>/credits-proposed.tsv`, one row per changed provision in one
   version: `path`, `version_from`, `proposed_law` (a key of the corpus's `laws`), `evidence` (one line quoted from
   the source), `evidence_url`, `model`, `confidence`, and `checked` (leave it empty).
2. **Check.** `python -X utf8 gitlaw_common/credits.py check <folder> --write` fills `checked` with `yes` or
   `no: <reason>`. A row passes only when all of these hold:
   - the provision changed in that version and has no credit yet;
   - the law exists and was published or enacted by that day;
   - that day is the law's commencement **as the corpus's own data gives it**: the law's `in_force` or `commenced`
     day, which the builder reads from the official source. The quoted evidence never establishes a commencement
     (three reviews found wordings a text filter takes for one: other languages, negations, a word after the day, a
     day from a neighbouring clause); a law with no such day in the corpus is refused. The evidence can only
     disqualify a row, when it states another commencement day. That day must be unambiguous: every definition of
     the law (corpus.json and every part, as written) gives the same calendar day as `in_force` and `commenced`, and no
     value is malformed (a field that is present must be a calendar day: `null` and `""` are refused); otherwise the row is
     refused;
   - no corpus file (corpus.json or any part) gives any key twice, at any depth: a parser keeps only one of the two,
     so such a file makes the whole corpus ambiguous and **every** row is refused until it is fixed (emit then writes no
     credit, only the counts-only `ai-use` part and its `.PUBLISH.pending`, as for any run that read proposals);
   - every day involved (`version_from`, the law's `in_force`/`commenced`/`published`/`enacted` in every definition,
     `--date`) is a real calendar day, `YYYY-MM-DD`; an empty `--date` is refused, only an absent one means today;
   - the evidence names the provision, a provision word and its number with no other number or suffix (`s. 1` is
     not `s. 10` or `s. 1A`), and the law by its whole label (`Act 7 of 2015` is not `Act 17 of 2015`);
   - the evidence URL is on a host the corpus already uses.
3. **Emit.** `python -X utf8 gitlaw_common/credits.py emit <folder>` writes one emission's parts, named
   `corpus.d/95-credits-<day>-<nn>-*.json` (`nn` counts the day's emissions). The whole emission is planned and
   checked before any file is written: every part it writes must sort after every part already in `corpus.d`, so it
   loads after the parts it corrects (a source part named `99-*` or `zz-*`, or a `--date` earlier than the last
   emission's, needs a later `--prefix`; the run is refused, with nothing written, until it has one). A part is never
   written over; a later emission corrects the latest part that holds each act, so earlier credits carry forward,
   and two current owners with one stem get distinct names. Limitation: part names that collide once NFC-normalised
   and case-folded (with each other or with an existing part) are refused, with nothing written; they are not
   disambiguated.
   - `...-ai-use.json`, on every run that read proposals, even when none passed: its `ai_use` line gives how many
     credits each model proposed, how many were checked and rejected, and that the law text is unchanged. This line
     is what reaches REPRODUCE.md.
   - `...-<part>.json`, one per part holding a credited act: it replaces those acts whole, sets the checked credits
     in the versions' own `credits`, and marks each such version
     `correction: {metadata_only: true, reason: "credit found by a checked model proposal: <law> (<evidence URL>)"}`.

   Rejected rows are never published, as credits or otherwise; only their count is. Each part gets a
   `<part>.PUBLISH.pending` review request with its sha256. `emit` never writes `<part>.PUBLISH`: a separate reviewer
   signs each part off (`publish_marker.write`), and the main-branch build loads only signed-off parts.
4. **Append.** `append.py --corrections` then appends labelled correction commits. The law text is unchanged, nothing is
   rewritten, the published main stays an ancestor, and a repeat run adds nothing.

Tests: `python -X utf8 gitlaw_common/test_credits.py` (29). They include the appender's own validation of the emitted
correction metadata, and the review findings on b191625: numbers alone, a missing commencement day, a second emission
writing over the first, an all-rejected run leaving no disclosure, a missing review request; and on 918f755: a
publication or retrieval day taken for the commencement, a correction sorting before its target, and two owners
sharing one output name; on 2923c82: commencement read from the evidence's wording at all; on 7d8ac2a: malformed days, ambiguous structured
commencement, and names that collide only after Unicode normalisation; on 185bd76: a repeated `laws` container,
null or empty days, unvalidated publication days and an empty `--date`; on b579062: duplicate keys a parser
discards before any check can see them.

**Not yet published, by design: no credit reaches a published repository until append.py writes the `Credits:`
trailer.** That is the agreed handoff after the corpus-standard bundle merges. Until then the appender's correction
commit is made by Lexifina, names the law only in `Reason`, and blame does not name the credited law, so signed-off
credit parts should not be appended. The proposal is a `Credits: <file> = <law label> <<url>>` trailer on metadata-only credit corrections
(CORPUS-STANDARD.md §3.3), which `tools/law.py` would read as that file's author for the corrected days.
