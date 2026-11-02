"""private: count CRs in HEAD files, merges, commits of a build."""
import subprocess, sys
b = sys.argv[1]
def g(*a): return subprocess.run(['git', '-C', b, *a], capture_output=True).stdout
fs = g('ls-tree', '-r', '--name-only', 'HEAD').decode().split('\n')
cr = sum(1 for f in fs if f and b'\r' in g('show', 'HEAD:' + f))
print('CR files:', cr, ' merges:', len(g('rev-list', '--merges', 'HEAD').split()), ' commits:', len(g('rev-list', 'HEAD').split()))
