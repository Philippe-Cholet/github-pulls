# GitHub Pulls
This personal command line tool allow to efficiently go through a lot of github repositories (from given users or given repos in a json file) to find pull requests and issues, and render results in a single webpage with links to them.

You can restrict the search to the lastest days, and sort the results according to opening dates, (owner, repo), or author.

### Current help message
```
usage: github_pulls.py [-h] [-u USER [USER ...]] [-j JSON] [-d DAYS]
                       [-s {opening,repo,author}]

Parse github repositories for opened pull requests & issues.

optional arguments:
  -h, --help            show this help message and exit
  -u USER [USER ...], --user USER [USER ...]
                        Look users' repositories.
  -j JSON, --json JSON  JSON file with repositories (default: first json file
                        found in current folder).
  -d DAYS, --days DAYS  only ones opened in the last ... days (default: all).
  -s {opening,repo,author}, --sort {opening,repo,author}
                        sorting output (default: by opening)

Give github usernames or a json file {user: [repository, ...]}.
```

### Requirements
- `python 3.6+` because I like f-strings.
- `aiohttp` to load webpages in an asynchronous way for efficiency.
- `beautifulsoup4` to parse html source code.

### Upcoming improvements
- Use github api to filter repositories given in json file to parse only ones with issues/pulls, it should increase speed.
- Fix the issue "**Only get the last 25 open issues/pulls of each repository.**"
- Make the script installable with `py -m pîp install [-e] .` to be able to do `github-pulls ...` in any folder.
- Eventually add it to PyPi, but it's not my current goal.

### Examples
- **Basic use:** if you want to look issues and pull requests opened in the last 7 days in some user's repositories, just write `github_pulls.py -u username -d 7`.
- The python/javascript code platform [CheckiO](https://checkio.org) allows users to create their own code mission with a github repository. Then, it's hard to follow all pull requests and issues since they are in more than 300 differents repositories. This command line tool is useful to keep track of potential changes in these repositories. It only needs a json file of the repos to watch, [this one](example/CheckiO.json) for example. **Customizable use with json file:** `github_pulls.py -j example/CheckiO.json -d 31` will look issues and pulls opened in the last month in the repositories given in `example/CheckiO.json` ; or you can do `github_pulls.py -d 31` if you are in `example` folder and `CheckiO.json` is the only json in it.

![Rendering example](example/rendering_example.png "Rendering example")
