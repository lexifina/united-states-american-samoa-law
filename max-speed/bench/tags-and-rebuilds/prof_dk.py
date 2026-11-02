import cProfile, pstats, sys, time, io
D = r'C:/Users/alany/Documents/lexifina/scripts/denmark-law'
sys.path.insert(0, D)
import os; os.chdir(D)
import build
build.TODAY = '2026-10-28'
acts = build.load_acts()[::14]
pr = cProfile.Profile(); t = time.perf_counter(); pr.enable()
for a in acts: build.act_worker((a, True))
pr.disable(); print('acts', len(acts), 'secs', round(time.perf_counter() - t, 1))
s = io.StringIO(); pstats.Stats(pr, stream=s).sort_stats('tottime').print_stats(25); print(s.getvalue()[:9000])
s = io.StringIO(); pstats.Stats(pr, stream=s).sort_stats('cumulative').print_stats(30); print(s.getvalue()[:9000])
