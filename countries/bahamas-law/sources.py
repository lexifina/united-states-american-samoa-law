"""Every request parse.py reads, as (url, POST body or None). fetch.py --plan fetches them; parse.py reads the cache.

laws.bahamas.gov.bs ("Bahamas Laws On-line", the Government of The Bahamas):
- the act index is a form posted per letter, with a point-in-time date ("pointintime_post"): it lists each act's
  consolidation that was current on that day, with the amending acts made since that consolidation ("amended by...")
  and each one's "Date Commenced";
- "Acts by Year" (a form posted per year) gives each principal and amending act's title and commencement date;
- the consolidations are numbered PDFs, /cms/images/LEGISLATION/PRINCIPAL/<yyyy>/<yyyy-nnnn>/<yyyy-nnnn>_<k>.pdf,
  one per revised edition (k = 1, 2, ...); the next number answers 403.
"""
SITE = 'https://laws.bahamas.gov.bs'
INDEX = SITE + '/cms/legislation/acts_only/by-alphabetical-order.html'
YEARS = SITE + '/cms/legislation/acts_only/acts-by-year.html'
COPYRIGHT = SITE + '/cms/?view=article&id=115:copyright&catid=14:general-articles'
PDF = SITE + '/cms/images/LEGISLATION/PRINCIPAL/{y}/{n}/{n}_{k}.pdf'
AMENDING_PDF = SITE + '/cms/images/LEGISLATION/AMENDING/2017/2017-0020A/2017-0020A.pdf'

RETRIEVED = '2026-10-29'  # the day every request below was made (UTC)


def index_post(letter: str, day: str) -> str:
    return f'pointintime_post={day}+00%3A00%3A00&submit4={letter}'


def pdf(number: str, k: int) -> str:
    return PDF.format(y=number[:4], n=number, k=k)


# The index on the retrieval day (current consolidations), and on the last day the Penal Code's 2010 edition was
# current and the first day of its 2017 edition (found by bisecting the point-in-time date).
INDEX_PAGES = {
    ('T', RETRIEVED): (INDEX, index_post('T', RETRIEVED)),
    ('P', RETRIEVED): (INDEX, index_post('P', RETRIEVED)),
    ('D', RETRIEVED): (INDEX, index_post('D', RETRIEVED)),
    ('P', '2016-12-30'): (INDEX, index_post('P', '2016-12-30')),
    ('P', '2016-12-31'): (INDEX, index_post('P', '2016-12-31')),
}
YEAR_PAGES = {y: (YEARS, f'year={y}') for y in (1973, 2003, 2007, 2008, 2010, 2011, 2014)}

PDFS = {
    'constitution': [pdf('1973-1080', 1)],
    'penal-code': [pdf('1873-0015', 1), pdf('1873-0015', 2)],
    'data-protection': [pdf('2003-0003', 1)],
}

PLAN = (list(INDEX_PAGES.values()) + list(YEAR_PAGES.values()) + [(COPYRIGHT, None), (AMENDING_PDF, None)]
        + [(u, None) for us in PDFS.values() for u in us])
