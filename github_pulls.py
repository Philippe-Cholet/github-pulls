import asyncio
import datetime
import itertools as it
import json
from http import HTTPStatus
from time import perf_counter
from traceback import format_exc
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Set, Tuple

import aiohttp
import bs4  # It will import lxml.
import click

__VERSION__ = '2.0.0'
GITHUB = 'https://github.com'
GITHUB_API = 'https://api.github.com'
USER_AGENT = f'github-pulls {__VERSION__}'
API_ERRORS = {
    401: 'Wrong token authentication?',
    403: '''You probably reached the rate limit of the github API:
  * 60 requests per hour (IP related) if you're not authenticated.
  * 5000 requests per hour (account related) if you are.
This tool does a request for every hundred repositories that users have so:
  * JSON file maybe have too much users or you use this tool too much.
  * you can authenticate with a personal token or wait some time.''',
    404: 'Maybe one user does not exists.',
}

JSONConfig = Dict[str, List[str]]
Repo = Tuple[str, str]

nb_requests = 0  # global variable
now = datetime.datetime.now().replace(microsecond=0)


def recent_enough(since: datetime.timedelta, days: Optional[int]) -> bool:
    """Say if it is less than the given days."""
    return days is None or since.total_seconds() < 60 * 60 * 24 * days


class GithubData(NamedTuple):
    """Data about a pull request or an issue extracted from a github page."""

    user: str
    repo: str
    title: str
    link: str
    author: str
    since: datetime.timedelta
    # Labels and milestones: ((text, link), ...)
    labels: Tuple[Tuple[str, str], ...]
    milestones: Tuple[Tuple[str, str], ...]

    def opening_key(self):
        return self.since

    def repo_key(self):
        return self.user, self.repo, self.since

    def author_key(self):
        return self.author, self.since

    def tr_line(self, show_labels: bool, show_milestones: bool) -> str:
        """Display the data in a line of a html table."""
        labels, milestones = (
            '<br>'.join(f'<a href="{GITHUB}{a}">{t}</a>' for t, a in L)
            for L in (self.labels, self.milestones)
        )
        td_labels = f'<td>{labels}</td>' if show_labels else ''
        td_milestones = f'<td>{milestones}</td>' if show_milestones else ''
        return f'''
    <tr>
        <td><a href="{GITHUB}/{self.user}">{self.user}</a></td>
        <td><a href="{GITHUB}/{self.user}/{self.repo}">{self.repo}</a></td>
        <td><a href="{GITHUB}{self.link}">{self.title}</a></td>
        {td_labels}
        {td_milestones}
        <td><a href="{GITHUB}/{self.author}">{self.author}</a></td>
        <td>{self.since}</td>
    </tr>'''


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


def html_table(datas: List[GithubData], what: str) -> str:
    """Display datas in a html table."""
    if not datas:
        return ''
    assert what in ('pull request', 'issue')
    any_label = any(data.labels for data in datas)
    any_milestone = any(data.milestones for data in datas)
    tr_lines = ''.join(
        data.tr_line(any_label, any_milestone)
        for data in datas
    )
    return f'''
<table>
    <caption>Opened {what.lower()}s</caption>
    <thead>
        <th>Username</th>
        <th>Repository</th>
        <th>{what.capitalize()}</th>
        {'<th>Labels</th>' if any_label else ''}
        {'<th>Milestones</th>' if any_milestone else ''}
        <th>Opened by</th>
        <th>Since</th>
    </thead>
    {tr_lines}
</table>'''


def html_template(
    pulls: List[GithubData],
    issues: List[GithubData],
    seconds: float,
) -> str:
    """Create full html source code for found pulls/issues."""
    return f'''<!DOCTYPE html>
<html>
    <head>
        <title>Opened pull requests and issues (sorted)</title>
        <style>{CSS}</style>
    </head>
    <body>
        <p>
            Took {seconds:.1f} seconds to do {nb_requests} web requests,
            obtain {len(pulls)} opened pull request(s)
            and {len(issues)} opened issue(s).
        </p>
        {html_table(pulls, 'pull request')}
        <br>
        {html_table(issues, 'issue')}
    </body>
</html>
'''


# ----------------------- Analyze github source code ----------------------- #
def github_div_search(tag: bs4.Tag) -> bool:
    """Say if it is a div tag for a pull request or an issue."""
    # <div id="issue_1234" ...>
    return (
        tag.name == 'div'
        and tag.has_attr('id')
        and tag.attrs['id'].startswith('issue_')
        and tag.attrs['id'][6:].isdigit()
    )


def github_number_of_issues(
    soup: bs4.BeautifulSoup,
    user: str,
    repo: str,
) -> int:
    """Find the number of issues in soup of '/user/repo/pulls'."""
    # <a ... href="/USER/REPO/issues" ...>
    #     <svg ...>...</svg>
    #     <span itemprop="name">Issues</span>
    #     <span title="1,313" class="Counter">1.3k</span>
    #     <meta itemprop="position" content="2">
    # </a>
    link = soup.find('a', {'href': f'/{user}/{repo}/issues'})
    if link is None:
        return 0
    try:
        span = link.find('span', {'class': 'Counter'})
        return int(span['title'].replace(',', ''))
    except Exception:  # span can be None, do not have 'title', or not an int.
        click.secho('Unexpected error:', err=True, fg='red', bold=True)
        click.echo(format_exc(), err=True)
        return 0


def github_parser(
    html_text: str,
    user: str,
    repo: str,
    days: Optional[int],
) -> Tuple[List[GithubData], str, bool]:
    """
    Parse github source code to detect datas, next url and if there are issues.
    """
    soup = bs4.BeautifulSoup(html_text, 'lxml')

    datas = []
    next_url = ''
    has_issues = bool(github_number_of_issues(soup, user, repo))

    for div in soup.find_all(github_div_search):
        opened_by = div.find('span', {'class': 'opened-by'})
        when = opened_by.find('relative-time')['datetime']
        since = now - datetime.datetime.strptime(when, '%Y-%m-%dT%H:%M:%SZ')
        if not recent_enough(since, days):
            # Sorted by newest so no need to continue when one is too old.
            # Stop the search and don't give the link to the next page.
            break
        link = div.a
        labels = div.find_all('a', {'class': 'IssueLabel'})
        milestones = div.find_all('a', {'class': 'milestone-link'})
        data = GithubData(
            user,
            repo,
            link.text,
            link['href'],
            opened_by.a.text,
            since,
            tuple((tag.text, tag['href']) for tag in labels),
            tuple((tag.text, tag['href']) for tag in milestones),
        )
        datas.append(data)
    else:
        # The search will stop if there is no link to the next page.
        next_attrs = {'class': 'next_page', 'rel': 'next'}
        link = soup.find('a', next_attrs, text='Next')
        if link:
            next_url = GITHUB + link['href']
    return datas, next_url, has_issues


# ---------- Asynchronous way to get github api/pulls/issues pages ---------- #
async def get_html_text(session: aiohttp.ClientSession, url: str) -> str:
    """Get html text from the url."""
    global nb_requests
    nb_requests += 1
    async with session.get(url) as response:
        return await response.text()


async def get_html_json(session: aiohttp.ClientSession, url: str) -> Any:
    """Get json from the url."""
    global nb_requests
    nb_requests += 1
    async with session.get(url, raise_for_status=True) as response:
        return await response.json()


async def get_repos_to_watch_from(
    users: List[str],
    token: Optional[str],
) -> Set[Repo]:
    """Get all repositories of all users, thanks to the Github API."""
    repos: Set[Repo] = set()
    if not users:
        return repos

    async def task(user: str) -> None:
        for page in it.count(1):
            url = f'{GITHUB_API}/users/{user}/repos?per_page=100&page={page}'
            data = await get_html_json(session, url)
            for repo in data:
                if repo['open_issues']:  # or open pull requests
                    new = repo['full_name'].split('/')
                    assert len(new) == 2
                    repos.add(tuple(new))  # type: ignore
            if len(data) < 100:
                break

    headers = {'User-Agent': USER_AGENT}
    if token is not None:
        headers['Authorization'] = f'token {token}'

    async with aiohttp.ClientSession(
        headers=headers,
        raise_for_status=True,
    ) as session:
        await asyncio.gather(*map(task, users))
        return repos


async def get_repos(
    users: List[str],
    config: Optional[JSONConfig],
    token: Optional[str],
) -> List[Repo]:
    """List repos to watch according to given users/config."""
    repos = await get_repos_to_watch_from(users, token)
    if config is not None:
        # Remove users from config if we previously look for all its repos.
        conf_users = config.keys() - set(users)
        conf_repos = {
            (user, repo)
            for user, repos_selection in config.items()
            if user in conf_users
            for repo in repos_selection
        }
        # Only parse the ones with issues/pulls, thanks to github api.
        conf_repos &= await get_repos_to_watch_from(list(conf_users), token)
        repos |= conf_repos
    return list(repos)


async def opened(
    repos: List[Repo],
    days: Optional[int],
) -> Tuple[List[GithubData], List[GithubData]]:
    """List recent pull requests and issues in the given repositories."""
    repos_with_issues: List[Repo] = []

    async def task(github_repo: Repo, what: str) -> List[GithubData]:
        user, repo = github_repo
        url = f'{GITHUB}/{user}/{repo}/{what}'
        datas: List[GithubData] = []
        while True:
            text = await get_html_text(session, url)
            new_datas, url, has_issues = github_parser(text, user, repo, days)
            if has_issues and what == 'pulls':
                repos_with_issues.append(github_repo)
            datas.extend(new_datas)
            if not url:
                break
        return datas

    async with aiohttp.ClientSession(raise_for_status=True) as session:
        tasks = (task(repo, 'pulls') for repo in repos)
        results = await asyncio.gather(*tasks)
        pulls = list(it.chain.from_iterable(results))

        tasks = (task(repo, 'issues') for repo in repos_with_issues)
        results = await asyncio.gather(*tasks)
        issues = list(it.chain.from_iterable(results))

    return pulls, issues


def error_type(status: int) -> str:
    """
    >>> error_type(404)
    'NOT FOUND'
    """
    for message, code in HTTPStatus.__members__.items():
        if code == status:
            return message.replace('_', ' ')
    return ''


async def main(
    users: List[str],
    config: Optional[JSONConfig],
    token: Optional[str],
    days: Optional[int],
) -> Tuple[List[GithubData], List[GithubData]]:
    """Search repositories and list recent pull requests and issues in them."""
    try:
        repos = await get_repos(users, config, token)
        if not repos:
            raise click.Abort('Nothing to do without users or json file.')
        pulls, issues = await opened(repos, days)
        return pulls, issues
    except aiohttp.ClientResponseError as error:
        url = error.request_info.url.human_repr()
        code = error.status
        message = f'ERROR {code} {error_type(code)}: {url}\n{error.message}'
        click.echo(message, err=True)
        if code in API_ERRORS:
            click.echo(API_ERRORS[code], err=True)
        raise click.Abort()


# ------------------------------ Command line ------------------------------- #
def load_config(ctx, param, config: Optional[str]) -> Optional[JSONConfig]:
    """Extract and valid config from a JSON file."""
    if config is None:
        return config
    with open(config) as fp:
        data = json.load(fp)
    if not (
        isinstance(data, dict)
        and all(
            isinstance(user, str)
            and isinstance(repos, list)
            and all(isinstance(repo, str) for repo in repos)
            for user, repos in data.items()
        )
    ):
        raise click.BadParameter(
            'The given json file does not have the expected structure: '
            '{user1: [repo1, ...], ...}.'
        )
    return data


epilog = '''
Give github usernames or a json file {user: repositories}.
Authenticate if you had an error message for (repeated?) big requests
(auth needs a token created at "https://github.com/settings/tokens").
'''


@click.command(
    context_settings={'help_option_names': ['-h', '--help']},
    epilog=epilog,
)
@click.option(
    '--user',
    '-u',
    'users',
    multiple=True,
    help='Look all repositories of given users.',
)
@click.option(
    '--json',
    '-j',
    'config',
    type=click.Path(exists=True, dir_okay=False),
    callback=load_config,
    help='JSON file with specific repositories.',
)
@click.option(
    '--token',
    '-t',
    help='Token to authenticate to the Github API.',
)
@click.option(
    '--days',
    '-d',
    type=click.IntRange(min=1),
    help='Only keep the ones opened in the last given days.  [default: all]',
)
@click.option(
    '--sort',
    '-s',
    type=click.Choice(('opening', 'repo', 'author')),
    default='opening',
    show_default=True,
    help='Sort the pull requests and the issues for a better visualization.',
)
@click.option(
    '--html',
    '-o',
    type=click.Path(writable=True, dir_okay=False),
    default='github-pulls.html',
    show_default=True,
    help='Path to the html result page.',
)
def cli(users, config, token, days, sort, html):
    """Parse github repositories for opened pull requests & issues."""
    if not users and not config:
        click.echo('No users and no config.', err=True)
        return

    start_time = perf_counter()
    pulls, issues = asyncio.run(main(users, config, token, days))
    elapsed_time = perf_counter() - start_time

    if not pulls and not issues:
        click.echo('No pull requests and no issues.', err=True)
        return

    key: Callable[['GithubData'], Any] = getattr(GithubData, f'{sort}_key')
    pulls.sort(key=key)
    issues.sort(key=key)

    text = html_template(pulls, issues, elapsed_time)
    with open(html, 'w', encoding='utf-8') as file:
        file.write(text)
    click.launch(html)


if __name__ == '__main__':
    cli()
