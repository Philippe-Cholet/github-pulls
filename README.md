# GitHub Pulls
This command line tool allow to efficiently go through a lot of github _public_ repositories (from given users and given repos in a json file) to find pull requests and issues, and render results in a single webpage with links to them.

You can restrict the search to the latest days, and sort the results according to opening dates, (owner, repo), or author.

### Requirements
- `python 3.7+` because `asyncio.run` has been added to version 3.7.
- `aiohttp` to load webpages in an asynchronous way for efficiency.
- `beautifulsoup4` and `lxml` to [efficiently](https://www.crummy.com/software/BeautifulSoup/bs4/doc/#installing-a-parser) parse html source code.
- `click` for a better command line interface.

This has been tested with `python 3.7.4` and:
```
setuptools==49.3.1
aiohttp==3.6.2
beautifulsoup4==4.9.1
click==7.1.2
lxml==4.5.2
```

### Without installation
If `aiohttp`, `bs4`, `click` and `lxml` are already installed, download `github_pulls.py`, then use `github_pulls.py ...` in the terminal (and in the folder where the file is).

### Installation
<!-- https://pip.pypa.io/en/stable/reference/pip_install/#examples -->
Once installed, you can write `github-pulls ...` in a terminal and in any folder.

#### With pip
It is not available on PyPi at the moment so `py -m pip install github-pulls` will not work. But the github url is enough:

`py -m pip install git+https://github.com/Philippe-Cholet/github-pulls@master`

#### With [pipx](https://pipxproject.github.io/pipx/ "my favorite way"), which installs it in an isolated environment
`pipx install git+https://github.com/Philippe-Cholet/github-pulls@master`

Or if you just want to test it for yourself without installing it:

`pipx run --spec git+https://github.com/Philippe-Cholet/github-pulls@master github-pulls [YOUR_OPTIONS]`

### Current help message
```
Usage: github-pulls [OPTIONS]

  Parse github repositories for opened pull requests & issues.

Options:
  -u, --user TEXT                 Look all repositories of given users.
  -j, --json FILE                 JSON file with specific repositories.
  -t, --token TEXT                Token to authenticate to the Github API.
  -d, --days INTEGER RANGE        Only keep the ones opened in the last given
                                  days.  [default: all]

  -s, --sort [opening|repo|author]
                                  Sort the pull requests and the issues for a
                                  better visualization.  [default: opening]

  -o, --html FILE                 Path to the html result page.  [default:
                                  github-pulls.html]

  -h, --help                      Show this message and exit.

  Give github usernames or a json file {user: repositories}. Authenticate if
  you had an error message for (repeated?) big requests (auth needs a token
  created at "https://github.com/settings/tokens").
```

### Examples
**Example:** `github-pulls -d 90 -s repo -j repos-selections.json -u pallets` will look in all repositories of [pallets](https://github.com/pallets) and the selections of repos given in the json file for pull requests and issues opened in the last 90 days, and they will be sorted by user/repository.

The python/javascript code platform [CheckiO](https://checkio.org) allows users to create their own code mission with a github repository. Then, it's hard to follow all pull requests and issues since they are in more than 400 different repositories. This command line tool is useful to keep track of potential changes in these repositories. It only needs a json file of the repos to watch, [this one](example/CheckiO.json) for example.

**CheckiO example:** `github-pulls --user oduvan --json example/CheckiO.json -days 31` will look issues and pulls opened in the last month in the repositories given in `example/CheckiO.json` and all oduvan's repositories.

#### What does the result webpage look like?
![Rendering example](example/rendering_example.png "Rendering example")
