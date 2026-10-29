---
name: world-law-max-speed-repo
description: "Git-for-law speed-up methods and benchmarks live only in the private repo lexifina/world-law-max-speed, never in shared repos or their history (user, 2026-10-29)"
metadata:
  node_type: memory
  type: feedback
  originSessionId: bf2c37ff-5368-4758-a217-51eee3902b94
  modified: 2026-10-29T15:36:55.366Z
---

On 2026-10-29 the user stopped a push of speed benchmarks to lexifina/global-law: "wait rm implementation info like that > we should put that in a private lexifina repo called "world-law-max-speed" > make a note of that, rm it from the git history (we dont need to rm all implementation info, but speedups in particular)".

**Why:** how we get law data fast is the user's edge. Ordinary build code may be shared; the speed-up methods may not.

**How to apply:**
- **Speed-ups go only to lexifina/world-law-max-speed.** That covers fetch tactics, rate settings, source shortcuts, the bulk-source lists and the benchmark results.
- **Everything else internal goes to the private lexifina/world-law-ops.** On 2026-10-29 the user said: "privatise all of those ... we can always unprivatise later ... just move them to the private repo, dont discard ANYTHING". That covers:
  1. personal emails and machine paths;
  2. notes on bot checks and blocks;
  3. legal and licence assessments;
  4. correspondence drafts;
  5. memory notes;
  6. the agent playbook (briefs, queues);
  7. source research (register, census, bridges);
  8. push tooling;
  9. per-country PROGRESS/ISSUES.
  world-law-ops also archives every original branch and tag as archive/<repo>/<ref>.
- **What stays in the country repos:** law data and provenance (corpus.json and its sources), parse/verify scripts, README, LICENSE and REPRODUCE.
- **They go nowhere else.** Not to global-law (any branch), the country repos, the coordinator backups, or this memory folder: write only pointers here, never the methods.
- **Ordinary implementation info** (builders, parsers, schema, REPRODUCE) may stay where it is.
- **Removing speed-up material from existing history is a force-push rewrite.** Confirm the exact scope with the user first; on 2026-10-29 both sessions agreed to wait for that confirmation.
- Related: [[git-for-law]], [[global-law-repo]].
