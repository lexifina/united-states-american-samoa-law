"""Corpus standard v1: canonical output and explicit historical read adapters."""
KINDS = frozenset({'law', 'baseline', 'correction', 'uncredited', 'printing', 'court', 'treaty', 'documentation'})
LAW_KINDS = frozenset({'constitution', 'constitutional-amendment', 'act', 'code', 'decree', 'decree-law',
                       'regulation', 'ordinance', 'legal-notice', 'referendum', 'other'})


def instrument_kind(law):
    explicit = law.get('law_kind')
    if explicit:
        if explicit not in LAW_KINDS:
            raise ValueError(f'unknown law_kind: {explicit!r}')
        return explicit
    old = law.get('kind', 'law').replace(' ', '-')
    return old if old in LAW_KINDS else 'act' if old in ('law', 'act') else 'other'


def law_commit_kind(law):
    value = law.get('kind', 'law')
    return value if value in ('court', 'treaty', 'printing', 'uncredited') else 'law'


def legacy_kind(value, subject='', author='', words_changed='', corrects=''):
    """Section 6 read-only mapping; never used to write new trailers."""
    k = (value or '').strip().lower()
    if author == 'Lexifina' or k == 'documentation':
        return 'documentation'
    if k == 'correction':
        return 'correction' if corrects else 'law'
    if k == 'publisher':
        if 'oldest version available' in subject.lower():
            return 'baseline'
        if '(unexplained)' in subject.lower() or words_changed == 'yes':
            return 'uncredited'
    if k.startswith(('baseline', 'first published')) or k in (
            'consolidated', 'current', 'current-only', 'current-text', 'consolidation',
            'tekst jednolity (current text)'):
        return 'baseline'
    if k in ('unexplained', 'change no law explains') or k.startswith((
            'editorial', 'notes only', 'style only', 'no act named')) or k.endswith(' (not credited)'):
        return 'uncredited'
    if k.startswith('court'):
        return 'court'
    return k if k in KINDS else 'law'


def planned_kind(corpus, entry):
    if entry['kind'] == 'start':
        law = entry['act'].get('first_law')
        return law_commit_kind(corpus['laws'][law]) if law else 'baseline'
    if entry['kind'] == 'law':
        return law_commit_kind(corpus['laws'][entry['law']])
    return 'uncredited' if entry['kind'] == 'unexplained' else entry['kind']
