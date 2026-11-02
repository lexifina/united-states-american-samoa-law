import cProfile, pstats, sys, time, io, os
D = r'C:/Users/alany/Documents/lexifina/scripts/ireland-law'
sys.path.insert(0, D); os.chdir(D)
import build
build.ACTS[:] = build.acts_from_alpha(True)
left = build.left_out_acts()
acts = [a for a in build.ACTS if a['eli'] not in left][::10]
pr = cProfile.Profile(); t = time.perf_counter(); pr.enable()
for a in acts:
    try: build.build_act(a, True)
    except Exception as e: print('err', a['eli'], e)
pr.disable(); print('acts', len(acts), 'secs', round(time.perf_counter() - t, 1))
for key in ('tottime', 'cumulative'):
    s = io.StringIO(); pstats.Stats(pr, stream=s).sort_stats(key).print_stats(28); print(s.getvalue()[:9500])
