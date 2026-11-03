"""The name published repositories give check.py (tools/check_repo.py). append.py imports the checker under that name;
in gitlaw_common the checker is check.py, so this file only re-exports it. Not shipped: build.py publishes check.py
itself as tools/check_repo.py."""
from check import Cat, all_commits_by_act, blob_oid, check, commits_by_act, git, state_on, tree_files, tree_oids  # noqa: F401

if __name__ == '__main__':
    from check import main
    main()
