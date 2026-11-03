# Append-only correction metadata

`append.py --corrections` reads replacement acts selected by the `corrects` part
format in SCHEMA.md. It never rewrites the original commits or moves tags.

An act or version may carry a `correction` object. Version values override act
defaults. Supported fields are:

| Field | Meaning |
| --- | --- |
| `reason` | The exact one-line `Reason:` trailer, overriding the CLI/default reason. |
| `in_force_basis` | The one-line `In-force-basis:` trailer. |
| `text_as_of` | The source capture date, `YYYY-MM-DD`; requires `in_force_basis`. |
| `supersedes` | A full commit ID in this act's published ordinary/correction history. |
| `metadata_only` | Boolean; explicitly requests a correction even with unchanged unit blobs. |

Version-level `in_force_basis` and `text_as_of` are also accepted. The existing
`editorial_date_correction` act metadata supplies defaults for the same fields.
For the older delivery format only, the exact assertion “Retrieval day retained
because exact commencement is unknown.” in `in_force_basis` identifies the
version's `from` as `Text-as-of`. A metadata-only correction by itself never
implies an unknown commencement date. New inputs should supply `text_as_of`.

A `corpus_withdrawal.reason` becomes “corpus withdrawal, not legislative repeal:
<reason>”; an explicit `correction.reason` overrides this. Withdrawal retains
the supplied empty units and historical dates and does not assert a repeal.

Source URLs are carried as `Source:` and `Text-source:` when supplied. Values
must be single lines, dates must be valid ISO days, and supplied superseded
commits must belong to the act's published history. Invalid metadata stops
planning. Surrounding trailer whitespace is trimmed as Git does. Existing
corrections with matching provenance and applicable ranges
are recognized so that a repeat append emits nothing.

Metadata-only corrections list the existing unit paths in `Files:` and reuse
their exact text. Their Git tree may equal their parent's tree, as permitted by
CORPUS-STANDARD.md §3.3.

An open canonical interval is split at later ordinary historical rows. Each
block keeps the source `In-force:` date; only `Corrects:` starts at the historical
boundary. Earlier blocks have explicit ends and the last stays open. Thus a
stale historical row cannot erase a correction, and a genuinely later ordinary
version still ends the final open block. `check_corrected()` tests ordinary and
correction boundaries as well as canonical version starts and the physical tip.

Run `python -X utf8 gitlaw_common/test_correction_gaps.py`. Its fixtures retain
unchanged Micronesia/Garissa delivery act objects and independently captured
published law rows. `fixtures/correction-gaps/manifest.json` pins fixture bytes,
original delivery file hashes, published baseline commits and gate JSON hashes.
The small scratch histories remap original commit IDs only; they preserve the
published row dates and law bytes. Full corpus appends are a separate gate.
