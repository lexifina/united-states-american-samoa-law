---
name: caselaw-comment-figures
description: "2026-10-10 @ a CourtListener case in a comment graphic: judgment captured (ops_ snapshot), figures quote it, click opens Modern JudgmentPreviewDialog at the words; video ordinary/134; uncommitted"
metadata:
  type: project
---

User (2026-10-10): comments can use public data, "what about caselaw refs? ... we already have all of the plumbing ... do it and video when rdy". Built on [[public-data-sources]] and the CourtListener research plumbing. Uncommitted.

**Backend**
- `services/caselaw_mentions.py`:
  - `search(q)`: CourtListener search; most cited first; zero-cited orders dropped; official reporter cite (no LEXIS); 1 h cache; court names remembered.
  - `source_row("<cluster>:<opinion>")`: fetches the opinion, stores `normalise_text` of it as the `ops_` snapshot, so figure offsets equal snapshot offsets (the captured preview route demands quote == text[start:end]).
- Route `GET /changes/{id}/comment-visual/cases?q=`, declared in `security/route_permissions.py`.
- `mentioned_context` takes `{type: "case"}`. A prompt rule covers judgments.
- `utils/comment_figures.py`: CASE_KEYS / CAPTURED_KINDS keep opinion/snapshot/start/end; a URL is kept only if on courtlistener.com.
- The captured opinion preview now returns retrieved_at + normalized_text_hash.

**Frontend**
- MentionTextarea `onSearch`/`onChoose`/`searchingLabel` (shared; parity-synced).
- Composer keeps picked cases and sends `label`.
- CommentFigures `kind: case_law` gives `target.opinion`.
- figureSourceNavigation opens a new **JudgmentPreviewDialog** (components/shared/References, with `judgmentPreview.js` helpers and shared `previewParts.js`):
  - pin cite from star pages ("517 U.S. at 582");
  - court from SCOTUS reporters when missing;
  - Opinion/Source tabs and a suggested citation;
  - "Open on CourtListener" with a text fragment.

**Gotchas**
- The shared backend is gunicorn without reload: SIGHUP pid 1 via python (no `kill` binary) after backend edits.
- CourtListener serves headless browsers an empty bot page (202), so the link can't be filmed.
- Charts animate bars in: wait for the label to stop moving before clicking.

**Video:** ordinary/134-caselaw-in-comment-graphics.mp4. Fixture: scripts/caselaw-figures/fixture.py (Reyes v. Calder Motors exposure note; `take`/`probe`). Recorder: scratchpad dsdialog/casevideo.cjs, low-memory 720p on the shared stack ([[low-memory-capture]]).

**Advert 2026-10-10.** User: start with the Gore example, then 4 researched case graphics, in the style of comment-graphics-ad-v12.
- Output: saas/caselaw-graphics-ad.mp4 (+ -1440p), 26.5 s, Mixkit #1147 "Midnight Funk" (unused; collab-ad-v2 runner-up), PIECES [(0,8)]. Pipeline: scripts/caselaw-graphics-ad (README), take-20261010T190524 in features/136.
- The four: Exxon v. Baker waterfall, State Farm guideposts flow chart, Texaco v. Pennzoil money flow, Peevyhouse bars. The opening Gore chart is Haslip 4 / TXO 10 / Gore 500 / Reyes 2,000; a click opens the judgment at 517 U.S. at 582.
- Product fixes found on the way:
  - flow-chart arrows "Yes"/"No" only;
  - spaced dashes in graphic labels become ": " (`_plain_dashes`);
  - decision diamonds wrap to 4 lines, not clip;
  - bar labels wrap (overflow 'break');
  - sankey nodes get localY beside their sources;
  - a middle splitting node is labelled on its left, wrapped to the gap, 10px.
- Model output varies take to take: name the items wanted in the description.

## 10 case-law figures (2026-10-10)
User wanted richer kinds than bar charts, as stills not a video. scripts/caselaw-figures-10: fixture.py `probe-all` draws each case through the real drafting path, final.json is the picked set, build.cjs + harness.jsx bundle the product CommentVisual, shoot.cjs writes DPR-3 PNGs to product-videos/figures/caselaw-10/ (fig.wide = 900 px card for timelines/swimlanes). Matrix/flow/swimlane content is not quote-checked: verify against the opinion by hand (Booker matrix was wrong until columns were named). Drop cases whose opinion never states the numbers (Apple trade dress gave invented figures).
Renderer fixes from the review: wide graphics wrap timeline/swimlane/arc labels longer (arcs up to 6 labels); swimlane hand-offs stop at the edge of a name under the dot; sankey gives a tiny node 30 px for its name only when the column still fits.

## Ad v2/v3: gentler music (2026-10-10)
User loved the ad but found #1147 Midnight Funk too intense. v2 rescored on #868 "Dry Gin" (atempo 120->118 BPM): user said
it "still sounds slightly out of tune". Measured: Dry Gin raw and v2 were both in tune (piptrack pitch-centre histogram,
~0 c), so it was the track's own sound, not the stretch. librosa.estimate_tuning on short windows is NOISE (gave "+21 c
sharp", wrong) - don't reason from it; a varispeed "fix" built on it came out 30 c flat and was deleted unshipped.
v3 = back to #1147 untouched: intro (track bars 0-7) under Gore, bar-line splice to the softer groove (bars 20-25, top
~4 dB down) at the cut, highshelf -2.5 dB @5k, fixed levels (groove 2.5 dB under v1, intro lifted up to 7 dB tapering,
light alimiter -1.5 dBFS) - not loudnorm, which pushed the groove up to compensate for the quiet intro.
scripts/caselaw-graphics-ad-v3, saas/caselaw-graphics-ad-v3(-1440p).mp4.
**How to apply:** for "less intense" on a liked track, use its calmer sections + level/EQ before swapping tracks; never
time-stretch or varispeed music under these ads (most Mixkit tracks are 120 BPM, films cut on the track's own grid).
v4 (user: "cut the music again from scratch, something safer, some violin too"): #617 "Wind Leaves" (corporate strings +
violin, 96 BPM), one unedited stretch from track 31.83 s: plucked opening under Gore, bowed violins enter (bar 19.1,
48.11 s) exactly on the film's cut at 16.27 s; -16 LUFS. A track off the film's tempo is fine if its one section change is
placed on the film's one cut (novelty curve over per-bar chroma+MFCC finds the boundary). scripts/caselaw-graphics-ad-v4.
v5 (user: v4 "a tiny bit too much, something similar but different"): #657 "Wedding 01" (violin/strings/piano, ~1 %
percussion vs 617's 16 %, in tune 0 c), from track 1.5 s: soft piano under Gore, violin swell from film 14.8 s through
the cut, -17 LUFS. Direction of travel across v1-v5: the user keeps wanting gentler; start softer next time.
