"""What never leaves this machine for a shared repo (user's rule, 2026-10-29).

Speed-up methods go to the private lexifina/world-law-max-speed; operational notes (handoffs, issues, correspondence,
licence assessments, logs) go to the private lexifina/world-law-ops. The builder (tools/ in each country repo) and
autopush's wip snapshots both skip these files, and scrub this machine's home path from what they do publish.
"""
import re
from pathlib import Path

PRIVATE_NAME = re.compile(
    r'^(PROGRESS\.md|ISSUES\.md|PERMISSION[^/]*|NOTES\.md|[^/]*\.log|wayback[^/]*\.py|fetch[^/]*\.(py|sh)|crawl[^/]*\.py|'
    r'grab[^/]*\.py|probe[^/]*\.py|discover[^/]*\.py|ia\.py|cc_[^/]*\.py|download[^/]*\.py|harvest[^/]*\.py)$', re.I)
SPEED_MARK = re.compile(rb'host_get|cc_get|cc_captures|import wayback|wayback\.|ThreadPoolExecutor|requests a second|'
                        rb'Crawl-delay|adaptive rate', re.I)
HOME = re.compile(r'(?i)(?:[A-Z]:[\\/]+Users[\\/]+alany|/c/Users/alany|/home/alany)')


def is_private(path: Path) -> bool:
    """True for a file that must stay private: a handoff, issue list, correspondence draft or log, a fetch helper by
    name, or a script that uses the fast-fetch tooling."""
    if PRIVATE_NAME.match(path.name):
        return True
    if path.suffix in ('.py', '.sh'):
        try:
            return bool(SPEED_MARK.search(path.read_bytes()))
        except OSError:
            return True
    return False


def scrub(text: str) -> str:
    """This machine's home path replaced by ~, so published files name no user or machine."""
    return HOME.sub('~', text)
