# SIBOM correction-part fixtures

Full fixtures, not reduced: 113 original Pilar acts and the 70 proposed withdrawals.
The original parts are byte-for-byte copies from `jobs/sibom-fix/loader-probes/argentina-pilar-city-law/corpus.d/`,
verified against that job's `published-inventory.json`. `withdrawals.json` is the unmodified
`delivery/argentina-pilar-city-law/corpus.d/zz-sibom-completeness-corrections-20261103.json`.
Their SHA-256 hashes are pinned in `test_correction_parts.py`. The local `.gitattributes` preserves their original
line-ending bytes across Git checkouts.

The tests split the supplied withdrawal acts by the original containing part and add only the `corrects` field to
temporary part files. Replacement expectations come from the supplied delivery; unaffected acts and dates come
from the unchanged published parts. The identity test copies the supplied corrected title onto one original act
and checks that its historical slug, version dates and legal text remain unchanged. No law text is authored here.

These are held review candidates. A loader test does not verify source completeness, authorize publication,
or establish legislative repeal. No publication markers are included.
