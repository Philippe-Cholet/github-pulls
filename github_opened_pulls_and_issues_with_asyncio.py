# Not stdlib
import aiohttp
import bs4
# Stdlib
import asyncio
from datetime import datetime
from os import startfile
from time import perf_counter
from itertools import chain
# Awesome decorator inspired by Veky (from CheckiO).
from functools import partial
aggregate = partial(partial, lambda f, g: lambda *a, **kw: f(g(*a, **kw)))

GITHUB = 'https://github.com'

# Write the repositories to watch in REPOS = {username: list of repos to watch}
REPOS = {
    'Philippe-Cholet': [
        'checkio-mission-filling',
        'checkio-mission-inertia',
        'checkio-mission-light-up',
        'checkio-mission-net-game',
        'checkio-mission-range',
        'checkio-mission-signpost',
        'checkio-mission-text-formatting',
        ],
    'CheckiO': [
        'checkio-mission-ascending-list',
        'checkio-mission-chicken-hunt',
        'checkio-mission-create-zigzag-array',
        'checkio-mission-escher-01-ship-teams',
        'checkio-mission-escher-02-square-ground-pieces',
        'checkio-mission-escher-03-compass',
        'checkio-mission-escher-04-stone-wall',
        'checkio-mission-escher-05-wild-dogs',
        'checkio-mission-escher-06-secret-room',
        'checkio-mission-escher-07-keys-and-locks',
        'checkio-mission-escher-08-safe-code',
        'checkio-mission-escher-09-treasures',
        'checkio-mission-escher-10-stones',
        'checkio-mission-escher-11-card-game',
        'checkio-mission-escher-12-buttons',
        'checkio-mission-escher-13-graphical-key',
        'checkio-mission-escher-14-hypercube',
        'checkio-mission-escher-15-tower',
        'checkio-mission-isometric-strings',
        'checkio-mission-ryerson-letter-grade',
        'checkio-mission-template',
        'checkio-mission-tutorial',
        'checkio-task-all-in-row',
        'checkio-task-fizz-buzz',
        'checkio-task-hamming-distance',
        'checkio-task-house-password',
        'checkio-task-most-wanted-letter',
        'checkio-task-runner',
        'checkio-task-tester',
    ],
    'oduvan': [
        'checkio-mission-a-words',
        'checkio-mission-all-in-row-iter',
        'checkio-mission-all-the-same',
        'checkio-mission-best-stock',
        'checkio-mission-between-markers',
        'checkio-mission-between-markers-simplified',
        'checkio-mission-bigger-price',
        'checkio-mission-bigger-together',
        'checkio-mission-can-balance',
        'checkio-mission-caps-lock',
        'checkio-mission-cheapest-flight',
        'checkio-mission-class-Person',
        'checkio-mission-completely-empty',
        'checkio-mission-convert-to-flatten',
        'checkio-mission-correct-sentence',
        'checkio-mission-count-consecutive-summers',
        'checkio-mission-create-intervals',
        'checkio-mission-currency-style',
        'checkio-mission-cut-sentence',
        'checkio-mission-domino-chain',
        'checkio-mission-double-substring',
        'checkio-mission-elementary-unpack',
        'checkio-mission-expand-intervals',
        'checkio-mission-fast-train',
        'checkio-mission-find-quotes',
        'checkio-mission-first-word',
        'checkio-mission-first-word-simplified',
        'checkio-mission-follow-instruction-move',
        'checkio-mission-frequency-sort',
        'checkio-mission-frequency-sorting',
        'checkio-mission-group-equal',
        'checkio-mission-how-deep',
        'checkio-mission-identify-block',
        'checkio-mission-index-power',
        'checkio-mission-isometric-strings',
        'checkio-mission-lists-overlap',
        'checkio-mission-long-non-repeat',
        'checkio-mission-long-repeat',
        'checkio-mission-long-repeat-inside',
        'checkio-mission-making-change',
        'checkio-mission-median-of-three',
        'checkio-mission-merge-intervals',
        'checkio-mission-most-frequent-weekdays',
        'checkio-mission-my-new-mission',
        'checkio-mission-neares-value',
        'checkio-mission-nearest-square-number',
        'checkio-mission-node-crucial',
        'checkio-mission-node-disconnected-users',
        'checkio-mission-node-subnetworks',
        'checkio-mission-nonogram-row',
        'checkio-mission-oneshot',
        'checkio-mission-popular-words',
        'checkio-mission-rectangles-union',
        'checkio-mission-remove-brackets',
        'checkio-mission-reverse-ascending-sublists',
        'checkio-mission-reverse-roman-numerals',
        'checkio-mission-say-history',
        'checkio-mission-second-index',
        'checkio-mission-sendgrid-it-vs-fr',
        'checkio-mission-sendgrid-sendone',
        'checkio-mission-sendgrid-spam-report',
        'checkio-mission-signpost',
        'checkio-mission-simplify-unix-path',
        'checkio-mission-stressful-subject',
        'checkio-mission-string-in-string',
        'checkio-mission-swap-nodes',
        'checkio-mission-test',
        'checkio-mission-text-reformating',
        'checkio-mission-the-most-frequent',
        'checkio-mission-time-converter-12h-to-24h',
        'checkio-mission-type-diff-sum',
        'checkio-mission-unfair-districts',
        'checkio-mission-unix-match',
        'checkio-mission-unlucky-days',
        'checkio-mission-useless-flight',
        'checkio-mission-word-search',
        'checkio-task-all-in-row',
        'checkio-task-count-area',
        'checkio-task-diffie-hellman',
        'checkio-task-fizz-buzz',
        'checkio-task-friendly-number',
        'checkio-task-how-much-gold',
        'checkio-task-int-filter',
        'checkio-task-making-change',
        'checkio-task-median',
        'checkio-task-numerical-string-sort',
        'checkio-task-probably-dice',
        'checkio-task-remove-accents',
        'checkio-task-ring-dimensioning',
        'checkio-task-runner',
        'checkio-task-simple-areas',
        'checkio-task-simple-hashlib',
        'checkio-task-simplest',
        'checkio-task-summarization',
        'checkio-task-x-o-referee',
        ],
    }
REPOS = [(user, repo) for user, repos in REPOS.items() for repo in repos]
repos_with_issues = []


def parser(html_text: str, user: str, repo: str, look_issues: bool):
    CLASSES = {'float-left', 'lh-condensed', 'p-2'}

    def search(tag: bs4.Tag) -> bool:
        """ Is it a div tag for a pull request or an issue ? """
        return (tag.name == 'div' and tag.has_attr('class') and
                CLASSES <= set(tag.attrs['class']))

    soup = bs4.BeautifulSoup(html_text, 'html.parser')
    divs = soup.findAll(search)
    if look_issues:
        # Not right for all repos!
        count_issues = soup.find('span', {'class': 'Counter'})
        if count_issues is not None and int(count_issues.text):
            repos_with_issues.append((user, repo))
    for div in divs:
        link, opened_by = div.a, div.find('span', {'class': 'opened-by'})
        since = now - datetime.strptime(
            opened_by.find('relative-time')['datetime'],
            '%Y-%m-%dT%H:%M:%SZ')
        yield since, user, repo, link.text, link['href'], opened_by.a.text


async def get_html_text(session: aiohttp.ClientSession, url: str) -> str:
    async with session.get(url) as response:
        return await response.text()


@aggregate(asyncio.run)
async def opened(repos: list, what: str, look_issues: bool = False) -> list:
    """ Look "what" in the given repositories,
        and issues count when look_issues to know if there are issues to look.
        If it's the case, add the repo to repos_with_issues. """
    async def parser_what_from(github_repo) -> list:
        user, repo = github_repo
        text = await get_html_text(session, f'{GITHUB}/{user}/{repo}/{what}')
        return list(parser(text, user, repo, look_issues))

    async with aiohttp.ClientSession() as session:
        tasks = map(parser_what_from, repos)
        results = await asyncio.gather(*tasks)
        return sorted(chain.from_iterable(results))


CSS = '''
body { background-color: #CAEBFB; }
table { border-collapse: collapse; }
caption { color: #163E69; font-size: 24px; font-weight: bold; }
th, td { padding: 8px; text-align: left; }
th { color: #0C64B4; }
tr:nth-child(even), th { background-color: #eee; }
tr:nth-child(odd) { background-color: #ddd; }
tr:hover { background-color: #0C64B4; color: #CAEBFB; }
a { text-decoration: none; color: inherit; }
'''


@aggregate(''.join)
def html_table(list_opened: list, what: str):
    yield f'''
<table>
    <caption>Opened {what.lower()}s</caption>
    <thead>
        <th>Username</th>
        <th>Repository</th>
        <th>{what.capitalize()}</th>
        <th>Opened by</th>
        <th>Since</th>
    </thead>'''
    for since, user, repo, title, link, opened_by in list_opened:
        yield f'''
    <tr>
        <td><a href="{GITHUB}/{user}">{user}</a></td>
        <td><a href="{GITHUB}/{user}/{repo}">{repo}</a></td>
        <td><a href="{GITHUB}{link}">{title}</a></td>
        <td><a href="{GITHUB}/{opened_by}">{opened_by}</a></td>
        <td>{since}</td>
    </tr>'''
    yield '''
</table>'''


filename = 'opened_pulls_and_issues.html'
now = datetime.now().replace(microsecond=0)

timing = - perf_counter()
# Look pulls pages of all repositories: looking for pull requests,
# and the number of issues (update `repos_with_issues`).
pulls = opened(REPOS, 'pulls', look_issues=True)
# Then look issues pages when there are issues.
issues = opened(repos_with_issues, 'issues')
timing += perf_counter()

nb_webpages = len(REPOS) + len(repos_with_issues)
table_pulls = '' if not pulls else html_table(pulls, 'pull request')
nb_pulls = table_pulls.count('<tr>')
table_issues = '' if not issues else html_table(issues, 'issue')
nb_issues = table_issues.count('<tr>')

if nb_pulls or nb_issues:
    # Otherwise, there is nothing to see so we don't show anything.
    with open(filename, 'w') as file:
        file.write(f'''<!DOCTYPE html>
<html>
    <head>
        <title>Opened pull requests and issues (sorted)</title>
        <style>{CSS}</style>
    </head>
    <body>
        <p>
            Took {timing:.1f} seconds
            to open & parse {nb_webpages} github pages,
            obtain {nb_pulls} opened pull request(s)
            and {nb_issues} opened issue(s).
        </p>
        {table_pulls}
        <br>
        {table_issues}
    </body>
</html>''')
    startfile(filename)
