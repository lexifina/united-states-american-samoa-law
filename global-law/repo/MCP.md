# Using the tree from an AI model (MCP)

`tools/mcp_server.py` is a Model Context Protocol server for this repository. It answers the questions
`tools/law.py` answers, with the limits of each record stated on every answer. It uses only Python's standard library
and git, reads the repository and changes nothing.

## Set up

```sh
git clone --recurse-submodules https://github.com/lexifina/global-law && cd global-law
claude mcp add global-law -- python tools/mcp_server.py
```

The repository also carries a project `.mcp.json`, so Claude Code offers the server in any clone without that
second command; approve it when asked.

Any other MCP client works the same way: the server speaks newline-delimited JSON-RPC over stdio. For a project file:

```json
{ "mcpServers": { "global-law": { "command": "python", "args": ["/path/to/global-law/tools/mcp_server.py"] } } }
```

## Tools

| Tool | What it answers |
| --- | --- |
| `list_jurisdictions` | Every jurisdiction and body of law, how far each record reaches, how many provisions, and an example path. Start here. |
| `find_provision` | The path of a provision from its number ("1182", "Art. 16a", "reg 13"), a popular name from `aliases.json` ("Schuldenbremse", "automatic stay", "EHC plan") or a topic found in the text. |
| `list_provisions` | The provisions under a corpus or folder, with headings, as in force on a date. |
| `read_law` | A provision's text on a date, with the law that last changed it, the next change, sources to cite and the record's limits. It adds "not the whole answer" notes where a later law reaches back over the date, or an effect changes how the provision applies without changing its words (`Modifies:`). |
| `world_on_date` | Every jurisdiction on one date: the last change in force in each, and the next. |
| `who_wrote` | Which law wrote each word (or line), with words per law. |
| `compare_dates` | A word-level diff between two dates and the laws that took effect in between. |
| `provision_history` | Every law that changed a provision, with its in-force, enacted or made, and published dates and its sources. |
| `laws_between` | Every law that took effect in a window, with how many provisions each changed. |
| `search_law` | Search the text of all the law in force on a date. |
| `changes_between` | Every provision whose text differs between two dates, with the laws that changed them. |
| `search_changes` | Search the record of changes (the commit messages) rather than the text. |
| `phrase_history` | When words came into the law and when they left it, at any date: for things no longer in force. |
| `applies_to_case` | For a case commenced on a date, which later changes reach it, from any scope the record holds. |
| `law_details` | The full record of one law's change: every trailer and every provision it changed. |

Resources: `global-law://README.md`, `REPRODUCE.md`, `CHANGELOG.md` and `manifest.json`.

## What to tell the user

Coverage is partial. Each corpus holds only the law its description names, over a stated period, so "nothing found"
means nothing in the record. Every answer carries notes where a date falls before a record starts or after it ends;
pass them on. Dates are the dates each record gives a change: the day it took effect, or for a first version the day it
was enacted or made. `applies_to_case` uses the scope a record holds; where none is recorded it says so and follows the
general rule that a change applies from its in-force date.

## Tests

```sh
python -m unittest tests.test_mcp -v
```

The tests speak to the server the way a client does: the handshake, every tool, errors, resources, and the
applicability rules on their own. The server was also tested blind, in four rounds: a model given only these tools answered 26 of 26 questions correctly, including
adversarial ones, and said where the record could not answer.
