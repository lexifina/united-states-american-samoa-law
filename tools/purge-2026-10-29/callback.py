# git filter-repo --file-info-callback body. Moves private material out of every commit (it is archived first):
# handoffs/notes/correspondence/logs, fetch helpers by name, scripts that use the fast-fetch tooling; scrubs this
# machine's home path; drops bot-challenge lines from READMEs; rewrites REPRODUCE's fetch wording. Law files untouched.
import re
NAME = re.compile(rb'^(PROGRESS\.md|ISSUES\.md|PERMISSION[^/]*|NOTES\.md|[^/]*\.log|wayback[^/]*\.py|fetch[^/]*\.(py|sh)|crawl[^/]*\.py|grab[^/]*\.py|probe[^/]*\.py|discover[^/]*\.py|ia\.py|cc_[^/]*\.py|download[^/]*\.py|harvest[^/]*\.py|[^/]*push[^/]*\.sh|peachjam\.py|lii\.py)$', re.I)
MARK = re.compile(rb'host_get|cc_get|cc_captures|import wayback|wayback\.|ThreadPoolExecutor|requests a second|Crawl-delay|adaptive rate', re.I)
HOME = re.compile(rb'(?i)(?:[A-Z]:(?:\\|\|/)+Users(?:\\|\|/)+alany|/c/Users/alany|/home/alany)')
NOTE = re.compile(rb'^(PROGRESS\.md|ISSUES\.md|NOTES\.md|PERMISSION_REQUEST[^/]*\.md)$')  # case-sensitive: a law's notes.md is law content
CODE = re.compile(rb'^(wayback[^/]*|fetch[^/]*|crawl[^/]*|grab[^/]*|probe[^/]*|discover[^/]*|ia|cc_[^/]*|download[^/]*|harvest[^/]*|[^/]*push[^/]*|peachjam|lii)\.(py|sh)$', re.I)
BLOCK = re.compile(rb'(?i)cloudflare|bot challenge|captcha|\bwaf\b|firewall page|bot check')
R1 = (b"Every request went through curl, at no more than one per second per host, and every response is cached by the sha256 of its URL. `tools/fetch.py` fills the cache.",
      b"Every response is cached by the sha256 of its URL, and the table above lists every source with its retrieval date. Lexifina keeps its fetch scripts privately;")
R2 = (b"python -X utf8 tools/fetch.py                  # fills the cache (network)",
      b"# fill the cache from the sources listed above (network; Lexifina's fetch scripts are kept privately)")
base = filename.rsplit(b'/', 1)[-1]
scoped = filename.startswith((b'wip/', b'tools/'))
DOCS = (b'README.md', b'REPRODUCE.md', b'SOURCES.md', b'REPRODUCE.template.md')
top = filename.count(b'/') == 0 or (filename.startswith((b'wip/', b'tools/')) and filename.count(b'/') == 1)
if (NOTE.match(base) and top) or (CODE.match(base) and base.endswith((b'.py', b'.sh'))):
    return (None, mode, blob_id)
text_like = base.endswith((b'.py', b'.sh', b'.md', b'.json', b'.csv', b'.txt', b'.toml', b'.yml', b'.yaml'))
if not text_like or not (scoped or b'/' not in filename or filename.startswith(b'data/') or base in DOCS or base.endswith((b'.py', b'.sh'))):
    return (filename, mode, blob_id)
data = value.get_contents_by_identifier(blob_id)
if base.endswith((b'.py', b'.sh')) and MARK.search(data):
    return (None, mode, blob_id)
new = HOME.sub(b'~', data)
if base in DOCS:
    new = b'\n'.join(l for l in new.split(b'\n') if not BLOCK.search(l))
if base in (b'REPRODUCE.md', b'REPRODUCE.template.md'):
    new = new.replace(*R1).replace(*R2)
if new != data:
    blob_id = value.insert_file_with_contents(new)
return (filename, mode, blob_id)
