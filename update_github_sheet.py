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
JS_RE = re.compile(r'.*\.js$')
CSS_RE = re.compile(r'.*\.(?:css|less)$')


def stringify(value):
    if value is None:
        value = ''
    elif value is True:
        value = 'Yes'
    elif value is False:
        value = 'No'
    return value


def get_sheet_values(sheet_id):
    client = get_google_client()
    ws = client.open_by_key(sheet_id).worksheet(SHEET_NAME)
    return ws.get_all_values()


def get_repositories_for_org(org):
    url = 'https://api.github.com/orgs/{}/repos?per_page=100'.format(org)

    resp = github_request(url)
    repos = json.loads(resp.content)
    next_link = resp.links.get('next')

    while next_link is not None:
        resp = github_request(next_link['url'])
        repos.extend(json.loads(resp.content))
        next_link = resp.links.get('next')

    return sorted(repos, key=lambda item: item['updated_at'], reverse=True)


def get_current_version(url):
    url = url.replace('{/id}', '/latest')
    resp = github_request(url)
    if resp.status_code == 200:
        data = json.loads(resp.content)
        return data.get('tag_name')


def get_has_statics(url):
    url = url.replace('{/sha}', '/master?recursive=1')
    resp = github_request(url)
    has_js = False
    has_css = False
    if resp.status_code == 200:
        data = json.loads(resp.content)
        for item in data.get('tree', []):
            path = item.get('path', '')
            if JS_RE.match(path):
                has_js = True
            elif CSS_RE.match(path):
                has_css = True
    return (has_js, has_css)


def get_coverage(url, has_js=False):
    coveralls_url = url.replace(
        'https://github.com', 'https://coveralls.io/github')
    coveralls_url += '.json'
    coverage = None
    has_js_coverage = False

    client = get_coveralls_client()
    resp = client.get(coveralls_url)

    if resp.status_code == 200:
        data = json.loads(resp.content)
        try:
            covered_percent = data.get('covered_percent', 0)
            coverage = int(float(covered_percent) * 10) / 10.0
        except AttributeError:
            return (coverage, has_js_coverage)

        if has_js:
            commit_id = data.get('commit_sha')
            build_url = ('https://coveralls.io/builds/{}.json?'
                         'paths=*%2Fstatic%2F*').format(commit_id)
            resp = client.get(build_url)

            if resp.status_code == 200:
                data = json.loads(resp.content)
                if data.get('selected_source_files_count', 0) > 0:
                    has_js_coverage = data.get('paths_covered_percent', 0) > 0

    return (coverage, has_js_coverage)


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
            values['Django'] = results[0] if (len(results[0])) else 'Unpinned'
    elif resp.status_code == 404:
        requirements_url = git_file_url + '/master/requirements.txt'
        resp = github_request(requirements_url)
        if resp.status_code == 200:
            values['setup.py'] = 'requirements.txt'

    return values


def get_travis_values(repo):
    url = repo['html_url']
    lang = repo['language']
    git_file_url = url.replace(
        'https://github.com', 'https://raw.githubusercontent.com')
    travis_url = git_file_url + '/master/.travis.yml'
    (has_js, has_css) = get_has_statics(repo['trees_url'])
    python_versions = []

    values = {
        'Travis CI': False,
        'Pycodestyle': False if (lang == 'Python') else 'N/A',
        'PyPI': False if (lang == 'Python') else 'N/A',
        'Python': None if (lang == 'Python') else 'N/A',
        'Django': None if (lang == 'Python') else 'N/A',
        'setup.py': False if (lang == 'Python') else 'N/A',
        'Coveralls': False,
        'Coverage': 0,
        'JS Coverage': False if has_js else 'N/A',
        'JSHint': False if has_js else 'N/A',
        'Version': None,
    }

    resp = github_request(travis_url)
    if resp.status_code == 200:
        config = yaml.load(resp.content)
        python_versions = config.get('python', [])
        values['Python'] = ', '.join(sorted(python_versions, reverse=True))

        for step in config.get('script', []):
            if 0 == step.find('pycodestyle'):
                values['Pycodestyle'] = True
                matches = PYCODESTYLE_RE.match(step)
                if matches:
                    excludes = matches.group(1).split(',')
                    for path in excludes:
                        if path.find('migrations') == -1:
                            values['Pycodestyle'] = 'Excludes'
            elif 0 == step.find('pep8'):
                values['Pycodestyle'] = 'Pep8'
            elif 0 == step.find('jshint'):
                values['JSHint'] = True

        for step in (config.get('after_success', []) +
                     config.get('after_script', [])):
            if 0 == step.find('coveralls'):
                for bstep in config.get('before_script', []):
                    if 0 == bstep.find('pip install python-coveralls'):
                        values['Coveralls'] = 'python-coveralls'
                    elif 0 == bstep.find('pip install coveralls'):
                        values['Coveralls'] = True

                (coverage, has_js_coverage) = get_coverage(url, has_js)
                values['Coverage'] = coverage
                if has_js:
                    values['JS Coverage'] = has_js_coverage

        if config.get('deploy', {}).get('provider', '') == 'pypi':
            values['PyPI'] = True

        values['Version'] = get_current_version(repo['releases_url'])
        values['Travis CI'] = True

    if lang == 'Python' or len(python_versions):
        values.update(get_setup_values(url))

    return values


def main(*args, **kwargs):
    sheet_id = get_google_sheet_id()
    sheet_values = get_sheet_values(sheet_id)
    col_names = sheet_values.pop(0)
    all_repos = get_repositories_for_org('uw-it-aca')

    repo_list = []
    for repo in all_repos:
        if not repo['archived']:  # Active repos only
            row_data = {
                'URL': repo['html_url'],
                'Name': repo['name'],
                'Language': repo['language'],
                'Last Updated': repo['updated_at'],
            }
            row_data.update(get_travis_values(repo))
            repo_list.append(row_data)

    max_row = max(len(sheet_values), len(repo_list))

    client = get_google_client()
    ws = client.open_by_key(sheet_id).worksheet(SHEET_NAME)
    cell_list = ws.range(
        START_ROW, 1, max_row+(START_ROW-1), len(col_names))

    for cell in cell_list:
        try:
            row_data = repo_list[cell.row-START_ROW]
            value = row_data.get(col_names[cell.col-1], '')
        except IndexError:
            value = ''
        cell.value = stringify(value)

    ws.update_cells(cell_list, value_input_option='RAW')


if __name__ == '__main__':
    main()
