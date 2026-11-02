"""gitlaw-scraper-dell (private): one fetch process for several Pakistani provinces, one thread per host (each host is
still fetched one request at a time, >= 3.2 s apart, by pkmy_fetch.py's per-host lock).

    python -X utf8 pk_fetch_driver.py pakistan-khyber-pakhtunkhwa-law pakistan-balochistan-law
"""
import importlib.util
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run(folder):
    p = HERE.parent / folder / 'fetch.py'
    spec = importlib.util.spec_from_file_location(f'fetch_{folder.replace("-", "_")}', p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    sys.argv = [str(p)]
    m.main()


ts = [threading.Thread(target=run, args=(f,), name=f) for f in sys.argv[1:]]
for t in ts:
    t.start()
for t in ts:
    t.join()
