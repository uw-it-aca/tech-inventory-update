from utils import (
    get_google_sheet_id, get_google_client, github_request,
    get_coveralls_client)
import yaml
import json
import re

SHEET_NAME = 'GitHub'
START_ROW = 2
DJANGO_RE = re.compile(r'[\'"]django([=>].*)?[\'"]', re.I)
PYCODESTYLE_RE = re.compile(r'.*--exclude=(.*)')


def stringify(value):
    if value is None:
        value = ''
    elif value is True:
        value = 'Yes'
    elif value is False:
        value = 'No'
    return value


def get_column_names(sheet_id):
    client = get_google_client()
    ws = client.open_by_key(sheet_id).worksheet(SHEET_NAME)
    return ws.row_values(1)


def get_repositories_for_org(org):
    url = 'https://api.github.com/orgs/{}/repos?per_page=100'.format(org)

    resp = github_request(url)
    repos = json.loads(resp.content)
    next_link = resp.links.get('next')

    while next_link is not None:
        resp = github_request(next_link['url'])
        repos.extend(json.loads(resp.content))
        next_link = resp.links.get('next')

    return sorted(repos, key=lambda item: item['id'])


def get_current_version(url):
    url = url.replace('{/id}', '/latest')
    resp = github_request(url)
    if resp.status_code == 200:
        data = json.loads(resp.content)
        return data.get('tag_name')


def get_coverage(url):
    coveralls_url = url.replace(
        'https://github.com', 'https://coveralls.io/github')
    coveralls_url += '.json'

    client = get_coveralls_client()
    resp = client.get(coveralls_url)

    if resp.status_code == 200:
        data = json.loads(resp.content)
        try:
            coverage = data.get('covered_percent', 0)
            return int(float(coverage) * 10) / 10.0
        except AttributeError:
            pass


def get_setup_values(url):
    git_file_url = url.replace(
        'https://github.com', 'https://raw.githubusercontent.com')
    setup_url = git_file_url + '/master/setup.py'
    values = {}

    resp = github_request(setup_url)
    if resp.status_code == 200:
        values['setup.py'] = True
        values['Django'] = 'N/A'

        results = DJANGO_RE.findall(resp.content.decode('utf-8'))
        if len(results):
            values['Django'] = results[0]
    return values


def get_travis_values(repo):
    url = repo['html_url']
    lang = repo['language']
    git_file_url = url.replace(
        'https://github.com', 'https://raw.githubusercontent.com')
    travis_url = git_file_url + '/master/.travis.yml'

    values = {
        'Travis CI': False,
        'Pycodestyle': False if (lang == 'Python') else 'N/A',
        'PyPI': False if (lang == 'Python') else 'N/A',
        'Python': None if (lang == 'Python') else 'N/A',
        'Django': None if (lang == 'Python') else 'N/A',
        'setup.py': False if (lang == 'Python') else 'N/A',
        'Coveralls': False,
        'Coverage': None,
        'JSHint': False,
        'Version': None,
    }

    resp = github_request(travis_url)
    if resp.status_code == 200:
        config = yaml.load(resp.content)
        pythons = config.get('python', [])
        values['Python'] = ', '.join(sorted(pythons, reverse=True))

        if lang == 'Python' or len(pythons):
            values.update(get_setup_values(url))

        for step in config.get('script', []):
            if 0 == step.find('pycodestyle'):
                values['Pycodestyle'] = True
                matches = PYCODESTYLE_RE.match(step)
                if matches:
                    excludes = matches.group(1).split(',')
                    for path in excludes:
                        if path.find('migrations') == -1:
                            values['Pycodestyle'] = 'Excludes'

            elif 0 == step.find('jshint'):
                values['JSHint'] = True

        for step in (config.get('after_success', []) +
                     config.get('after_script', [])):
            if 0 == step.find('coveralls'):
                values['Coveralls'] = True
                values['Coverage'] = get_coverage(url)

        if config.get('deploy', {}).get('provider', '') == 'pypi':
            values['PyPI'] = True

        values['Version'] = get_current_version(repo['releases_url'])
        values['Travis CI'] = True
    return values


def main(*args, **kwargs):
    sheet_id = get_google_sheet_id()
    col_names = get_column_names(sheet_id)
    all_repos = get_repositories_for_org('uw-it-aca')

    repo_list = []
    for repo in all_repos:
        row_data = {
            'URL': repo['html_url'],
            'Name': repo['name'],
            'Language': repo['language'],
            'Last Updated': repo['updated_at'],
        }
        row_data.update(get_travis_values(repo))
        repo_list.append(row_data)

    client = get_google_client()
    ws = client.open_by_key(sheet_id).worksheet(SHEET_NAME)
    cell_list = ws.range(
        START_ROW, 1, len(all_repos)+(START_ROW-1), len(col_names))

    for cell in cell_list:
        value = repo_list[cell.row-START_ROW].get(col_names[cell.col-1], '')
        cell.value = stringify(value)

    ws.update_cells(cell_list, value_input_option='RAW')


if __name__ == '__main__':
    main()
