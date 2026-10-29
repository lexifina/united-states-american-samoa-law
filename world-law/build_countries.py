"""Build one law-history scaffold repo per country from the World Law Sources register. Standard library only.

  python scripts/world-law/build_countries.py <out-dir> [--push] [--only slug,slug]

Reads register.json (the register's rows, exported from the World Law Sources research of 28 October 2026) and writes,
for every UN member state and the other jurisdictions in the register, a repo <out-dir>/<slug>-law with one commit:
README.md, SOURCES.md, jurisdiction.json and REPRODUCE.md. It also writes countries.json beside this script, the list
global-law reads its jurisdiction tree from. Commits are dated 2026-10-28 (the register's date), so rebuilds give the
same hashes. --push creates each repo as private under the lexifina organisation (gh CLI) and pushes it; repos that
already exist on GitHub are left alone. No AI runs here, and no legal text is written: the files only describe sources.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORG = 'lexifina'
DATE = '2026-10-28T12:00:00+00:00'
AUTHOR = ('Lexifina', 'world-law@lexifina.com')
REGISTER_URL = 'https://claude.ai/artifact/DdS9F6yqpPZtV2i7FGQhYZ'

# Every UN member state, then the 16 other jurisdictions the register covers. (register name, ISO 3166-1 alpha-2)
UN = [
    ('Afghanistan', 'AF'), ('Albania', 'AL'), ('Algeria', 'DZ'), ('Andorra', 'AD'), ('Angola', 'AO'),
    ('Antigua and Barbuda', 'AG'), ('Argentina', 'AR'), ('Armenia', 'AM'), ('Australia', 'AU'), ('Austria', 'AT'),
    ('Azerbaijan', 'AZ'), ('Bahamas', 'BS'), ('Bahrain', 'BH'), ('Bangladesh', 'BD'), ('Barbados', 'BB'),
    ('Belarus', 'BY'), ('Belgium', 'BE'), ('Belize', 'BZ'), ('Benin', 'BJ'), ('Bhutan', 'BT'), ('Bolivia', 'BO'),
    ('Bosnia and Herzegovina', 'BA'), ('Botswana', 'BW'), ('Brazil', 'BR'), ('Brunei', 'BN'), ('Bulgaria', 'BG'),
    ('Burkina Faso', 'BF'), ('Burundi', 'BI'), ('Cabo Verde', 'CV'), ('Cambodia', 'KH'), ('Cameroon', 'CM'),
    ('Canada', 'CA'), ('Central African Republic', 'CF'), ('Chad', 'TD'), ('Chile', 'CL'), ('China', 'CN'),
    ('Colombia', 'CO'), ('Comoros', 'KM'), ('Republic of Congo', 'CG'), ('DR Congo', 'CD'), ('Costa Rica', 'CR'),
    ('Côte d’Ivoire', 'CI'), ('Croatia', 'HR'), ('Cuba', 'CU'), ('Cyprus', 'CY'), ('Czechia', 'CZ'),
    ('North Korea', 'KP'), ('Denmark', 'DK'), ('Djibouti', 'DJ'), ('Dominica', 'DM'), ('Dominican Republic', 'DO'),
    ('Ecuador', 'EC'), ('Egypt', 'EG'), ('El Salvador', 'SV'), ('Equatorial Guinea', 'GQ'), ('Eritrea', 'ER'),
    ('Estonia', 'EE'), ('Eswatini', 'SZ'), ('Ethiopia', 'ET'), ('Fiji', 'FJ'), ('Finland', 'FI'), ('France', 'FR'),
    ('Gabon', 'GA'), ('Gambia', 'GM'), ('Georgia', 'GE'), ('Germany', 'DE'), ('Ghana', 'GH'), ('Greece', 'GR'),
    ('Grenada', 'GD'), ('Guatemala', 'GT'), ('Guinea', 'GN'), ('Guinea-Bissau', 'GW'), ('Guyana', 'GY'), ('Haiti', 'HT'),
    ('Honduras', 'HN'), ('Hungary', 'HU'), ('Iceland', 'IS'), ('India', 'IN'), ('Indonesia', 'ID'), ('Iran', 'IR'),
    ('Iraq', 'IQ'), ('Ireland', 'IE'), ('Israel', 'IL'), ('Italy', 'IT'), ('Jamaica', 'JM'), ('Japan', 'JP'),
    ('Jordan', 'JO'), ('Kazakhstan', 'KZ'), ('Kenya', 'KE'), ('Kiribati', 'KI'), ('Kuwait', 'KW'), ('Kyrgyzstan', 'KG'),
    ('Laos', 'LA'), ('Latvia', 'LV'), ('Lebanon', 'LB'), ('Lesotho', 'LS'), ('Liberia', 'LR'), ('Libya', 'LY'),
    ('Liechtenstein', 'LI'), ('Lithuania', 'LT'), ('Luxembourg', 'LU'), ('Madagascar', 'MG'), ('Malawi', 'MW'),
    ('Malaysia', 'MY'), ('Maldives', 'MV'), ('Mali', 'ML'), ('Malta', 'MT'), ('Marshall Islands', 'MH'),
    ('Mauritania', 'MR'), ('Mauritius', 'MU'), ('Mexico', 'MX'), ('Micronesia', 'FM'), ('Moldova', 'MD'),
    ('Monaco', 'MC'), ('Mongolia', 'MN'), ('Montenegro', 'ME'), ('Morocco', 'MA'), ('Mozambique', 'MZ'),
    ('Myanmar', 'MM'), ('Namibia', 'NA'), ('Nauru', 'NR'), ('Nepal', 'NP'), ('Netherlands', 'NL'),
    ('New Zealand', 'NZ'), ('Nicaragua', 'NI'), ('Niger', 'NE'), ('Nigeria', 'NG'), ('North Macedonia', 'MK'),
    ('Norway', 'NO'), ('Oman', 'OM'), ('Pakistan', 'PK'), ('Palau', 'PW'), ('Panama', 'PA'), ('Papua New Guinea', 'PG'),
    ('Paraguay', 'PY'), ('Peru', 'PE'), ('Philippines', 'PH'), ('Poland', 'PL'), ('Portugal', 'PT'), ('Qatar', 'QA'),
    ('South Korea', 'KR'), ('Romania', 'RO'), ('Russia', 'RU'), ('Rwanda', 'RW'), ('Saint Kitts and Nevis', 'KN'),
    ('Saint Lucia', 'LC'), ('Saint Vincent and the Grenadines', 'VC'), ('Samoa', 'WS'), ('San Marino', 'SM'),
    ('São Tomé and Príncipe', 'ST'), ('Saudi Arabia', 'SA'), ('Senegal', 'SN'), ('Serbia', 'RS'), ('Seychelles', 'SC'),
    ('Sierra Leone', 'SL'), ('Singapore', 'SG'), ('Slovakia', 'SK'), ('Slovenia', 'SI'), ('Solomon Islands', 'SB'),
    ('Somalia', 'SO'), ('South Africa', 'ZA'), ('South Sudan', 'SS'), ('Spain', 'ES'), ('Sri Lanka', 'LK'),
    ('Sudan', 'SD'), ('Suriname', 'SR'), ('Sweden', 'SE'), ('Switzerland', 'CH'), ('Syria', 'SY'),
    ('Tajikistan', 'TJ'), ('Tanzania', 'TZ'), ('Thailand', 'TH'), ('Timor-Leste', 'TL'), ('Togo', 'TG'), ('Tonga', 'TO'),
    ('Trinidad and Tobago', 'TT'), ('Tunisia', 'TN'), ('Turkey', 'TR'), ('Turkmenistan', 'TM'), ('Tuvalu', 'TV'),
    ('Uganda', 'UG'), ('Ukraine', 'UA'), ('United Arab Emirates', 'AE'), ('United Kingdom', 'GB'),
    ('United States', 'US'), ('Uruguay', 'UY'), ('Uzbekistan', 'UZ'), ('Vanuatu', 'VU'), ('Venezuela', 'VE'),
    ('Vietnam', 'VN'), ('Yemen', 'YE'), ('Zambia', 'ZM'), ('Zimbabwe', 'ZW'),
]
OTHER = [
    ('Vatican City', 'VA', 'UN observer state'), ('Palestine', 'PS', 'UN observer state'),
    ('Taiwan', 'TW', 'not a UN member'), ('Kosovo', 'XK', 'not a UN member; XK is a user-assigned code'),
    ('Hong Kong', 'HK', 'special administrative region of China'), ('Macau', 'MO', 'special administrative region of China'),
    ('Jersey', 'JE', 'British Crown dependency'), ('Guernsey', 'GG', 'British Crown dependency'),
    ('Isle of Man', 'IM', 'British Crown dependency'), ('Gibraltar', 'GI', 'British overseas territory'),
    ('Bermuda', 'BM', 'British overseas territory'), ('Cayman Islands', 'KY', 'British overseas territory'),
    ('British Virgin Islands', 'VG', 'British overseas territory'), ('Greenland', 'GL', 'part of the Kingdom of Denmark'),
    ('Faroe Islands', 'FO', 'part of the Kingdom of Denmark'), ('Puerto Rico', 'PR', 'territory of the United States'),
]
# Countries whose law history already lives in a corpus repo, or whose repo another session has already made.
EXISTING = {
    'DE': 'grundgesetz', 'GB': 'uk-law-history', 'US': 'us-code-history', 'CH': 'swiss-law',
    'EE': 'estonia-law', 'LI': 'liechtenstein-law', 'LU': 'luxembourg-law', 'MT': 'malta-law',
}
# Register rows that name several countries at once.
SHARED = {'South Africa, Kenya, Zambia and others': ['ZA', 'KE', 'ZM'], 'UK and Ireland': ['GB', 'IE'],
          'Southern Africa': ['ZA'], 'European Union': [], 'US states': ['US']}
YES = {'y': 'yes', 'p': 'partly', 'n': 'no', '': 'n/a'}


def slug(name: str) -> str:
    s = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', s.replace('’', '').replace("'", '')).strip('-')


def git(*args: str, cwd: Path, env: dict | None = None) -> str:
    done = subprocess.run(['git', *args], cwd=cwd, capture_output=True, encoding='utf-8',
                          env={**os.environ, **(env or {})})
    if done.returncode:
        raise SystemExit(f"git {' '.join(args)} failed in {cwd}:\n{done.stderr}")
    return done.stdout


def rows_for(sources: list[dict], name: str, iso: str) -> list[dict]:
    out = []
    for s in sources:
        c = s.get('c') or ''
        if c == name or c.startswith(name + ' (') or iso in SHARED.get(c, []):
            out.append(s)
    return out


def readiness(rows: list[dict]) -> tuple[str, str]:
    official = [r for r in rows if r['k'] in ('official', 'lii') and not r['n'].startswith('None found')]
    if not official:
        return 'none', 'No official legislation is online. A history would have to be built from printed or archived gazettes.'
    if any(r['pit'] == 'y' and r['api'] == 'y' for r in official):
        return 'ready', 'Ready to build: an official source has past versions by date and an API or bulk download.'
    if any(r['pit'] == 'y' for r in official):
        return 'scrape', 'Past versions by date are online, but with no API or bulk download, so a build has to read the site page by page.'
    if any(r['pit'] == 'p' for r in official):
        return 'partial', 'Some past versions are online. A full history needs those plus the gazette.'
    return 'gazette', 'Only current text or the gazette is online, so a history has to be rebuilt by applying each amending act.'


def cell(v: str) -> str:
    return (v or '').replace('|', '\\|').replace('\n', ' ')


def sources_md(name: str, rows: list[dict], kinds: dict) -> str:
    lines = [f'# Sources for {name}', '',
             f'From the World Law Sources register, 28 October 2026. Each row was checked against the source’s own pages, '
             f'an official description, or an Internet Archive copy where a site blocks automated readers. '
             f'“Unconfirmed” rows could not be checked that way.', '',
             '| Source | Kind | Past versions by date | Names the amending act | API or bulk | Format and licence | Notes | Checked |',
             '|---|---|---|---|---|---|---|---|']
    for r in rows:
        links = [f"[{cell(r['n'])}]({r['u']})"] + [f"[{cell(l)}]({u})" for l, u in r.get('extra', [])]
        lines.append('| ' + ' · '.join(links) + f" | {kinds.get(r['k'], r['k'])}{' (' + cell(r['c']) + ')' if '(' in (r.get('c') or '') else ''}"
                     f" | {YES[r.get('pit', '')]} | {YES[r.get('amend', '')]} | {YES[r.get('api', '')]} | {cell(r.get('f', ''))}"
                     f" | {cell(r.get('note', ''))} | {'yes' if r.get('facts') == 'checked' else 'unconfirmed'} |")
    if not rows:
        lines.append('| No source found | | | | | | | |')
    lines += ['', 'Research guides that cover every country: [GlobaLex](https://www.nyulawglobal.org/globalex/) and the '
              '[Law Library of Congress Guide to Law Online](https://www.loc.gov/research-centers/law-library-of-congress/researcher-resources/guide-to-law-online/).', '']
    return '\n'.join(lines)


def readme_md(name: str, iso: str, repo: str, note: str, verdict: str, rows: list[dict]) -> str:
    best = [r for r in rows if r['k'] in ('official', 'lii') and not r['n'].startswith('None found')]
    prior = [r for r in rows if r['k'] == 'prior']
    out = [f'# {name}: law history', '',
           f'This repository will hold the legislation of {name} ({iso}{", " + note if note else ""}) as a history: '
           'one file per provision and one commit per law taking effect, dated by the day it took force, with the law '
           'that made each change as the commit author. It follows the shared design of '
           '[lexifina/global-law](https://github.com/lexifina/global-law), which places it at '
           f'`{iso.lower()}/` in the world tree.', '',
           '**Status:** no law yet. This first commit records where the law of ' + name + ' can be read and what a build '
           'would need.', '', f'**Can it be built?** {verdict}', '',
           '**This commit is a placeholder.** The first real build must replace this history from scratch and force-push. '
           'It must never append law commits on top of it: they are dated by when each law took effect, often decades '
           'earlier, so dates in `main` would run backwards and break every on-date lookup. Builders should refuse to '
           'append when the root commit is this placeholder (its subject ends "sources, before any law").', '']
    if best:
        out += ['**Official sources**', ''] + [f"- [{r['n']}]({r['u']}){': ' + r['note'] if r.get('note') else ''}" for r in best] + ['']
    if prior:
        out += ['**Existing open projects to check first**', ''] + [f"- [{r['n']}]({r['u']}): {r.get('note', '')}" for r in prior] + [
            '', 'These are volunteer projects. Reconcile any of them against the official text before relying on it: '
            'a transcription is not the law (c3e/grundgesetz, for example, differs from the official gazette in 43 '
            'article texts on 20 July 2017).', '']
    out += ['All sources, with their status, are in [SOURCES.md](SOURCES.md). How these files were made is in '
            '[REPRODUCE.md](REPRODUCE.md).', '',
            'This repository describes sources; it is not legal advice and holds no legal text yet.', '']
    return '\n'.join(out)


def reproduce_md(script_hash: str, register_hash: str) -> str:
    return '\n'.join([
        '# How this repository was made', '',
        f'1. The World Law Sources register ({REGISTER_URL}, private to Lexifina) was compiled on 28 October 2026 by '
        'Claude Code running Claude Opus 5.5 (`claude-opus-5-5`), with research sub-agents on the same model. They read '
        'each source’s own pages, official descriptions, and Internet Archive copies for sites that block automated '
        'readers. Links were checked with curl.',
        '2. The register rows were exported to `scripts/world-law/register.json` in the Lexifina repository '
        f'(sha256 `{register_hash}`).',
        f'3. `python scripts/world-law/build_countries.py <out> --push` (script blob `{script_hash}`) wrote README.md, '
        'SOURCES.md, jurisdiction.json and this file for every country, committed them as one commit dated '
        f'{DATE} by {AUTHOR[0]} <{AUTHOR[1]}>, and pushed each to a private repository under the lexifina organisation.', '',
        'No AI model runs in step 3, and no AI wrote legal text. Rebuilding from the same register gives the same commit '
        'hashes.', '',
        'When the first law history is built for this country, that build replaces this placeholder history entirely '
        '(a fresh history, force-pushed) and records its own steps here. It never appends to the placeholder commit.', ''])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--push', action='store_true')
    ap.add_argument('--only', default='')
    a = ap.parse_args()
    reg_path = HERE / 'register.json'
    reg = json.loads(reg_path.read_text(encoding='utf-8'))
    sources, kinds = reg['sources'], reg['kinds']
    script_hash = git('hash-object', str(Path(__file__).resolve()), cwd=HERE).strip()
    register_hash = hashlib.sha256(reg_path.read_bytes()).hexdigest()
    out = Path(a.out).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    only = set(filter(None, a.only.split(',')))
    countries = []
    for name, iso, *rest in [(n, i, '') for n, i in UN] + OTHER:
        note = rest[0] if rest else ''
        rows = rows_for(sources, name, iso)
        status, verdict = readiness(rows)
        repo = EXISTING.get(iso, f'{slug(name)}-law')
        entry = {'path': iso.lower(), 'code': iso, 'name': name, 'level': 'country', 'note': note or None,
                 'repo': f'https://github.com/{ORG}/{repo}', 'existing': iso in EXISTING, 'build': status,
                 'sources': len(rows)}
        countries.append({k: v for k, v in entry.items() if v is not None})
        if iso in EXISTING or (only and repo not in only):
            continue
        d = out / repo
        if (d / '.git').exists():
            if a.push:
                push(d, repo, name)
            continue
        d.mkdir(parents=True, exist_ok=True)
        if any(d.iterdir()):
            raise SystemExit(f'{d} is not empty; refusing to build into it')
        jur = {'path': iso.lower(), 'code': iso, 'name': name, 'level': 'country', **({'note': note} if note else {}),
               'repo': entry['repo'], 'build': status, 'register': REGISTER_URL, 'register_date': '2026-10-28'}
        files = {'README.md': readme_md(name, iso, repo, note, verdict, rows), 'SOURCES.md': sources_md(name, rows, kinds),
                 'jurisdiction.json': json.dumps(jur, ensure_ascii=False, indent=2) + '\n',
                 'REPRODUCE.md': reproduce_md(script_hash, register_hash)}
        for f, text in files.items():
            (d / f).write_bytes(text.encode('utf-8'))
        git('init', '-q', '-b', 'main', cwd=d)
        git('add', '-A', cwd=d)
        env = {'GIT_AUTHOR_NAME': AUTHOR[0], 'GIT_AUTHOR_EMAIL': AUTHOR[1], 'GIT_AUTHOR_DATE': DATE,
               'GIT_COMMITTER_NAME': AUTHOR[0], 'GIT_COMMITTER_EMAIL': AUTHOR[1], 'GIT_COMMITTER_DATE': DATE}
        git('-c', 'commit.gpgsign=false', 'commit', '-q', '-m', f'{name}: sources, before any law\n\n{verdict}\n',
            cwd=d, env=env)
        if a.push:
            push(d, repo, name)
    (HERE / 'countries.json').write_bytes((json.dumps({'date': '2026-10-28', 'register': REGISTER_URL,
                                                       'countries': countries}, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    print(f'{len(countries)} jurisdictions; {sum(1 for c in countries if not c["existing"])} new repos under {out}')


def push(d: Path, repo: str, name: str) -> None:
    marker = d.parent / f'.pushed-{repo}'
    if marker.exists():
        return
    exists = subprocess.run(['gh', 'repo', 'view', f'{ORG}/{repo}', '--json', 'name'], capture_output=True).returncode == 0
    if not exists:
        r = subprocess.run(['gh', 'repo', 'create', f'{ORG}/{repo}', '--private', '--disable-wiki',
                            '--description', f'{name}: law history, one commit per law taking effect (sources so far)'],
                           capture_output=True, encoding='utf-8')
        if r.returncode:
            print(f'create {repo} failed: {r.stderr.strip()}', file=sys.stderr)
            return
        time.sleep(1.5)  # stay well under GitHub's content-creation rate limits
    remote = f'https://github.com/{ORG}/{repo}.git'
    if 'origin' not in git('remote', cwd=d).split():
        git('remote', 'add', 'origin', remote, cwd=d)
    r = subprocess.run(['git', 'push', '-q', 'origin', 'main'], cwd=d, capture_output=True, encoding='utf-8')
    if r.returncode:
        print(f'push {repo} failed: {r.stderr.strip()}', file=sys.stderr)
        return
    marker.write_text('', encoding='utf-8')
    print(f'pushed {repo}', flush=True)


if __name__ == '__main__':
    main()
