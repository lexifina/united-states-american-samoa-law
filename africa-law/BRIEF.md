# Brief for every African git-for-law agent

Everything in `scripts/south-america-law/BRIEF.md` applies here: the steps, the rules, "Known pitfalls", and "Changed after the restart". Read it in full first. It covers:
- autopush owns every push, and you never push;
- the `PUBLISH` and `<part>.PUBLISH` gates;
- `changes` deltas, `same_day` and the law `note` field;
- no OCR;
- the anachronism rule;
- never killing a process you didn't start;
- curl with `--compressed` at 1 request per second per host;
- sourced dates only, never general knowledge.

Then read `scripts/gitlaw_common/SCHEMA.md`.

## Scope

English-language countries first. Right-to-left scripts are out of scope for now, so there's no Arabic. French- and Portuguese-language countries come later.

## Sources

Laws.Africa Peachjam LIIs publish legislation as Akoma Ntoso with dated point-in-time versions. These are the best free history sources in Africa:

| Country | LII |
|---|---|
| Kenya | new.kenyalaw.org |
| Uganda | ulii.org |
| Zambia | zambialii.org |
| Malawi | malawilii.org |
| Zimbabwe | zimlii.org |
| Namibia | namiblii.org |
| Lesotho | lesotholii.org |
| Sierra Leone | sierralii.gov.sl |
| Ghana | ghalii.org |
| Tanzania | tanzlii.go.tz |
| Eswatini | eswatinilii.org |
| Seychelles | seylii.org |

Each act lives at `/akn/<cc>/act/<year>/<num>`, with expressions `@<date>`.

**One shared adapter, `scripts/africa-law/peachjam.py`, serves every LII.** Country folders only configure it: the host, the acts, the language and the time zone.

**Licences:**
- Check each LII's terms and robots.txt before fetching, and record them.
- The full Laws.Africa API is paid, so don't use it. Use only the public website pages and files.
- Legislation text is generally public, but follow each site's attribution line exactly.

**"Not yet applied" amendments.** LIIs sometimes list an amendment as not yet applied to the consolidated text (GhaLII especially). Never treat such a version as complete. List those amendments in `decisions`, and leave them out of the text unless an official text-layer source gives the wording.

## Your folder

Your folder is `scripts/<slug>-law/`. The repo is `lexifina/<slug>-law`, which already exists as a private scaffold, so clone it if you need to read it. The builder writes the clone at `C:/Users/alany/Documents/<slug>-law`, and autopush pushes it. Never push, and never build into the clone yourself; test in `scripts/<slug>-law/.tmp/`.

Phase 1 is the Constitution plus 2 core acts, typically:
- Penal Code
- Data Protection Act
- Companies Act
- Employment Act
- Civil Procedure

Choose acts by what the source supports. After Phase 1, keep adding acts while time allows.
