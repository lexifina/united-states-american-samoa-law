# world-law-ops (private)

Git-for-law operations, kept private by the user's rule (2026-10-29):

- `world-law/`: the agent playbook and queues, plus the source research (`register.json`, `countries.json`).
- `global-law/`: the census, the bridges and the competitor analysis (`competitors/`, open the HTML in a browser).
- the shared builder and the push tooling (fast-forward only since 2026-11-02; `tools/append-only/` appends new acts without rewriting history).
- `tools/orchestrator/`: the detached global-law repoint loop, push watch and CPU logger (see its RESUME.md).
- `memory/`: the git-for-law memory notes.
- `countries/`: every country's handoffs, issue lists, correspondence drafts, licence notes and scripts.

Speed-ups live in `max-speed/`: experiments, benchmarks, patches, the speed rules and tools. They were merged in from lexifina/world-law-max-speed (2026-11-02, full history kept; that repo is archived).

Branches:

- `main`: this readable tree.
- `coordinator`: the coordinator backup.
- `archive/<repo>/<ref>`: every original branch and tag of each country repo and of global-law, kept before the 2026-10-29 history rewrite so nothing was discarded.
- `archive2/<repo>/<ref>`: the newer states of refs that moved after their first archive.
