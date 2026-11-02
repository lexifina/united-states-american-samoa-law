"""cProfile a builder script in-process: python prof.py <out.prof> <script.py> args...; prints the top 25 by cumtime
and by tottime."""
import cProfile
import pstats
import runpy
import sys

out, script, *args = sys.argv[1:]
sys.argv = [script, *args]
pr = cProfile.Profile()
try:
    pr.runcall(runpy.run_path, script, run_name='__main__')
except SystemExit:
    pass
pr.dump_stats(out)
s = pstats.Stats(out, stream=sys.stderr)
s.sort_stats('cumulative').print_stats(25)
s.sort_stats('tottime').print_stats(20)
