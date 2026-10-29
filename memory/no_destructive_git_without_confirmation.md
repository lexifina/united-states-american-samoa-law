---
name: no-destructive-git-without-confirmation
description: "Never rewrite history, force-push, delete, move, transfer or change the visibility of a GitHub repo or branch without first warning of every consequence and getting explicit confirmation naming the repo (user, 2026-10-29)"
metadata:
  node_type: memory
  type: feedback
  originSessionId: bf2c37ff-5368-4758-a217-51eee3902b94
  modified: 2026-10-29T17:35:26.156Z
---

On 2026-10-29 the git-for-law privacy purge rewrote and force-pushed about 120 lexifina/*-law repos, and global-law was disabled while being moved. The user said: "we lost all our git stars etc doing that >>>> write a memory ... not to fucking do that again without warning and explicit confirmation > especially for ABSOLUTELY CRITICAL REPOS."

**Why:** stars, watchers, forks, issues, links, other people's clones and submodule pins belong to the repo. Some of it can't be restored from a git archive. The user approved "the purge", not the loss of the repo's standing.

**How to apply:**
- **Before any of these on GitHub, stop and ask:**
  - history rewrites (filter-repo, filter-branch, rebase plus push);
  - `push --force` or `--force-with-lease`;
  - deleting a branch or repo;
  - renaming, transferring or moving a repo;
  - changing a repo's visibility (public to private removes stars and watchers);
  - recreating a repo;
  - bulk operations across many repos.
- **The warning lists the exact repos and branches, and every consequence:**
  - stars and watchers;
  - forks;
  - open PRs and issues;
  - links and SHAs other people use;
  - clones that would then diverge;
  - submodule and pinned-tag pointers (global-law pins country commits);
  - Pages and CI.
- **It also names what can't be undone.**
- **Then wait for an explicit yes naming those repos.** A general "do it" or "everything" given earlier is not enough. Confirm again for each critical repo, and again if the scope grows.
- **Critical repos are always asked about one by one, never in a batch:**
  - lexifina/global-law;
  - any public repo, and any repo with stars or outside users, such as alan-yahya/status, alan-yahya/grundgesetz, alan-yahya/us-code-history and the alan-yahya/lexifina app repo;
  - the org profile and .github repo.
- **Prefer non-destructive routes:** a new commit instead of a rewrite, a new branch instead of a force-push, archive first.
- **Never change a repo's visibility yourself.** Tell the user what it would cost and let them do it.
- Related: [[world-law-max-speed-repo]], [[git-for-law]], [[global-law-repo]], [[commits-by-hand]].
