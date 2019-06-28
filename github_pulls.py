# Not stdlib
import aiohttp  # ClientSession
import bs4  # BeautifulSoup
# Stdlib
import asyncio  # run, gather
from datetime import datetime
import os  # listdir, startfile
from time import perf_counter
import itertools as it  # chain, count
import json  # load
from argparse import ArgumentParser
# Awesome decorator inspired by Veky (from py.checkio.org).
from functools import partial
aggregate = partial(partial, lambda f, g: lambda *a, **kw: f(g(*a, **kw)))


# ---------------------- Constants & Global variables ---------------------- #
GITHUB = 'https://github.com'
GITHUB_API = 'https://api.github.com'

now = datetime.now().replace(microsecond=0)
nb_web_requests = 0
repos_with_issues = []

# ----------------------------- ArgumentParser ----------------------------- #
parser = ArgumentParser(
    description='Parse github repositories for opened pull requests & issues.',
    epilog="Give github usernames or a json file {user: [repository, ...]}.")
# Simple use: by github usernames.
parser.add_argument('-u', '--user', nargs='+',
                    help="Look users' repositories.")
# Customizable use with a json file.
parser.add_argument('-j', '--json',
                    help='JSON file with repositories '
                    '(default: first json file found in current folder).')
# Simple filter of results: useful to get only latest results, if there has.
days_default = None  # or 7 for a simple weekly/daily use.
parser.add_argument('-d', '--days', type=int,
                    default=days_default,
                    help='only ones opened in the last ... days'
                    f' (default: {days_default or "all"}).')
# Sort the results for a better visualization.
parser.add_argument('-s', '--sort',
                    choices=['opening', 'repo', 'author'], default='opening',
                    help='sorting output (default: by %(default)s)')
args = parser.parse_args()


def get_repos() -> list:
    if args.user:
        data = get_repos_to_watch_from(args.user)
    else:
        file = args.json or next(f for f in os.listdir('.')
                                 if f.endswith('.json'))
        with open(file) as f:
            data = json.load(f)
    return [(user, repo) for user, repos in data.items() for repo in repos]


def recent_enough(timedelta) -> bool:
    return args.days is None or timedelta.total_seconds() < 60*60*24*args.days


def sorting_key(x) -> tuple:
    # x = (since, user, repo, title, link, opened_by)
    if args.sort == 'opening':
        return x
    if args.sort == 'repo':
        return x[1].casefold(), x[2].casefold(), x[0]
    if args.sort == 'author':
        return x[-1].casefold(), x[0]


# ----------------------- Analyze github source code ----------------------- #
def github_div_search(tag: bs4.Tag) -> bool:
    """ Is it a div tag for a pull request or an issue ? """
    return (tag.name == 'div' and tag.has_attr('class') and
            {'float-left', 'lh-condensed', 'p-2'} <= set(tag.attrs['class']))


def github_number_of_issues(soup: bs4.BeautifulSoup,
                            user: str, repo: str) -> int:
    # <a ... href="/USER/REPOSITORY_NAME/issues" ...>
    #     <svg class="octicon octicon-issue-opened" ...>...</svg>
    #     <span itemprop="name">Issues</span>
    #     <span class="Counter">NUMBER WE WANT</span>
    #     <meta itemprop="position" content="2">
    # </a>
    link = soup.find('a', {'href': f'/{user}/{repo}/issues'})
    try:
        span = link.find('span', {'class': 'Counter'})
        return int(span.text)
    except AttributeError:  # link or span can be None.
        return 0


def github_parser(html_text: str, user: str, repo: str, look_issues: bool):
    """ Parse github source code to detect pulls/issues
        and generate useful contents, when there are recent enough.
        Add the repo to repos_with_issues when
        look_issues is True and there are issues. """
    soup = bs4.BeautifulSoup(html_text, 'html.parser')
    if look_issues and github_number_of_issues(soup, user, repo):
        repos_with_issues.append((user, repo))
    for div in soup.findAll(github_div_search):
        link, opened_by = div.a, div.find('span', {'class': 'opened-by'})
        opening_time = opened_by.find('relative-time')['datetime']
        since = now - datetime.strptime(opening_time, '%Y-%m-%dT%H:%M:%SZ')
        if recent_enough(since):
            yield since, user, repo, link.text, link['href'], opened_by.a.text


# ---------- Asynchronous way to get github api/pulls/issues pages ---------- #
async def get_html_json(session: aiohttp.ClientSession, url: str) -> str:
    global nb_web_requests
    nb_web_requests += 1
    async with session.get(url) as response:
        return await response.json()


async def get_html_text(session: aiohttp.ClientSession, url: str) -> str:
    global nb_web_requests
    nb_web_requests += 1
    async with session.get(url) as response:
        return await response.text()


@aggregate(asyncio.run)
async def get_repos_to_watch_from(users: list) -> dict:
    async def task(user: str):
        repos = []
        for page in it.count(1):
            url = f'{GITHUB_API}/users/{user}/repos?per_page=100&page={page}'
            new_data = await get_html_json(session, url)
            repos.extend(repo['name'] for repo in new_data
                         if repo['open_issues'])  # or open pull requests
            if len(new_data) < 100:
                return user, repos

    async with aiohttp.ClientSession() as session:
        return dict(await asyncio.gather(*map(task, users)))


@aggregate(asyncio.run)
async def opened(repos: list, what: str, look_issues: bool = False) -> list:
    """ Look "what" in the given repositories, in an efficient way.
        Return sorted list of generated contents. """
    async def parser_what_from(github_repo) -> list:
        user, repo = github_repo
        text = await get_html_text(session, f'{GITHUB}/{user}/{repo}/{what}')
        return list(github_parser(text, user, repo, look_issues))

    async with aiohttp.ClientSession() as session:
        tasks = map(parser_what_from, repos)
        results = await asyncio.gather(*tasks)
        return sorted(it.chain.from_iterable(results), key=sorting_key)


# ----------------------------- HTML/CSS output ----------------------------- #
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
    """ Previously generated content presented in an html table. """
    if list_opened:  # Otherwise, it would be an empty table, so yield nothing.
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


def main(filename: str):
    """ Looking for opened pulls and issues.
        Write and open a great html file with them,
        only when there is something to show. """
    timing = - perf_counter()
    # Look pulls pages of all repositories: looking for pull requests,
    # and the number of issues (update `repos_with_issues`).
    pulls = opened(get_repos(), 'pulls', look_issues=True)
    # Then look issues pages when there are issues.
    issues = opened(repos_with_issues, 'issues')
    timing += perf_counter()

    if pulls or issues:
        with open(filename, 'w', encoding='utf-8') as file:
            file.write(f'''<!DOCTYPE html>
<html>
    <head>
        <title>Opened pull requests and issues (sorted)</title>
        <style>{CSS}</style>
    </head>
    <body>
        <p>
            Took {timing:.1f} seconds to do {nb_web_requests} web requests,
            obtain {len(pulls)} opened pull request(s)
            and {len(issues)} opened issue(s).
        </p>
        {html_table(pulls, 'pull request')}
        <br>
        {html_table(issues, 'issue')}
    </body>
</html>''')
        os.startfile(filename)


if __name__ == '__main__':
    main('opened_pulls_and_issues.html')