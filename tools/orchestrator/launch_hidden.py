"""Start one orchestrator loop with a hidden console, so neither it nor any git/python/cmd child opens a window.

    pythonw.exe launch_hidden.py <program> [args...]

start.ps1 runs this through Win32_Process.Create (outside any session's job object). pythonw has no console itself;
the loop gets CREATE_NO_WINDOW, a hidden console its children inherit (memory note detached_no_console_windows:
never DETACHED_PROCESS, whose children each open a visible window). Prints nothing; the loop's pid goes to
launch_hidden.last.
"""
import subprocess, sys
from pathlib import Path

CREATE_NO_WINDOW, NEW_GROUP, BREAKAWAY = 0x08000000, 0x00000200, 0x01000000
here = Path(__file__).resolve().parent
try:
    p = subprocess.Popen(sys.argv[1:], cwd=here, creationflags=CREATE_NO_WINDOW | NEW_GROUP | BREAKAWAY,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
except OSError:  # a job that forbids breakaway
    p = subprocess.Popen(sys.argv[1:], cwd=here, creationflags=CREATE_NO_WINDOW | NEW_GROUP,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
(here / 'launch_hidden.last').write_text(str(p.pid))
