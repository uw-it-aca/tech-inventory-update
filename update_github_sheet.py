from utils import (
    get_google_sheet_id, get_google_client, github_request,
    get_coveralls_client)
import yaml
import toml
import json
import re

SHEET_NAME = 'GitHub'
START_ROW = 2
DJANGO_RE = re.compile(r'[\'"]django([~=>].*)?[\'"]', re.I)
PYCODESTYLE_RE = re.compile(r'.*--exclude=(.*)')
JS_RE = re.compile(r'.*\.js$')
CSS_RE = re.compile(r'.*\.(?:css|less)$')
DJANGO_CONTAINER_RE = re.compile(r'FROM .*:(.*) as .*')


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


def get_has_statics(url, default_branch):
    url = url.replace('{/sha}', '/{}?recursive=1'.format(default_branch))
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
            covered_percent = data.get('covered_percent', 0) or 0
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


def get_docker_values(url, default_branch):
    git_file_url = url.replace(
        'https://github.com', 'https://raw.githubusercontent.com')
    dockerfile_url = '{}/{}/Dockerfile'.format(git_file_url, default_branch)
    values = {}

    resp = github_request(dockerfile_url)
    if resp.status_code == 200:
        matches = DJANGO_CONTAINER_RE.match(resp.content.decode('utf-8'))
        if matches:
            values['django-container'] = matches.group(1)

    return values


def get_install_values(url, default_branch):
    git_file_url = url.replace(
        'https://github.com', 'https://raw.githubusercontent.com')
    setup_url = '{}/{}/setup.py'.format(git_file_url, default_branch)
    values = {}

    resp = github_request(setup_url)
    if resp.status_code == 200:
        values['Language'] = 'Python'
        values['Install'] = 'setup.py'
        values['Django'] = 'N/A'

        results = DJANGO_RE.findall(resp.content.decode('utf-8'))
        if len(results):
            values['Django'] = results[0] if (len(results[0])) else 'Unpinned'
    elif resp.status_code == 404:
        pyproject_url = '{}/{}/pyproject.toml'.format(
            git_file_url, default_branch)
        resp = github_request(pyproject_url)
        if resp.status_code == 200:
            values['Language'] = 'Python'
            values['Install'] = 'pyproject.toml'
            values['Django'] = 'N/A'

            config = toml.loads(resp.content.decode('utf-8'))
            values['Python'] = config.get('Python', config.get('python'))
            values['Django'] = config.get(
                'Django', config.get('django', 'N/A'))

        requirements_url = '{}/{}/requirements.txt'.format(
            git_file_url, default_branch)
        resp = github_request(requirements_url)
        if resp.status_code == 200:
            values['Install'] = 'requirements.txt'

    return values


def get_github_action_values(repo, data):
    values = {}
    config = yaml.full_load(data)
    for step in config.get('jobs', {}).get('test', {}).get('steps', []):
        if 'run' in step:
            if step.get('run').startswith('pycodestyle'):
                values['Pycodestyle'] = True
            elif step.get('run').startswith('coveralls'):
                values['Coveralls'] = True
        if 'with' in step and 'python-version' in step.get('with'):
            values['Python'] = str(step.get('with').get('python-version'))

    for step in config.get('jobs', {}).get('build', {}).get('steps', []):
        if 'run' in step and 'docker/test.sh' in step.get('run'):
            values['Pycodestyle'] = True
            values['JSHint'] = True
            values['Coveralls'] = True
        if 'with' in step and 'python-version' in step.get('with'):
            values['Python'] = str(step.get('with').get('python-version'))

    for step in config.get('jobs', {}).get('publish', {}).get('steps', []):
       if ('uses' in step and
               'uw-it-aca/actions/publish-pypi' in step.get('uses')):
           values['PyPI'] = True

    return values


def get_travis_values(repo, data):
    values = {}
    config = yaml.full_load(data)
    python_versions = [str(x) for x in config.get('python', [])]
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
        elif 0 == step.find('docker run'):
            values['Pycodestyle'] = True

    for step in (config.get('after_success', []) +
                 config.get('after_script', [])):
        if 0 == step.find('coveralls'):
            for bstep in config.get('before_script', []):
                if 0 == bstep.find('pip install python-coveralls'):
                    values['Coveralls'] = 'python-coveralls'
                elif 0 == bstep.find('pip install coveralls'):
                    values['Coveralls'] = True

    try:
        if config.get('deploy', {}).get('provider', '') == 'pypi':
            values['PyPI'] = True
    except AttributeError:
        pass

    return values


def get_cicd_values(repo):
    url = repo['html_url']
    lang = repo['language']
    default_branch = repo['default_branch']
    git_file_url = url.replace(
        'https://github.com', 'https://raw.githubusercontent.com')
    (has_js, has_css) = get_has_statics(repo['trees_url'], default_branch)

    values = {
        'CI/CD': 'N/A',
        'Pycodestyle': False if (lang == 'Python') else 'N/A',
        'PyPI': False if (lang == 'Python') else 'N/A',
        'Python': None if (lang == 'Python') else 'N/A',
        'Django': None if (lang == 'Python') else 'N/A',
        'django-container': 'N/A',
        'Install': None if (lang == 'Python') else 'N/A',
        'Coveralls': False,
        'Coverage': 0,
        'JS Coverage': False if has_js else 'N/A',
        'JSHint': False if has_js else 'N/A',
        'Version': None,
    }

    ga_url = '{}/{}/.github/workflows/cicd.yml'.format(
        git_file_url, default_branch)

    resp = github_request(ga_url)
    if resp.status_code == 200:
        values['CI/CD'] = 'github-actions'
        values.update(get_github_action_values(repo, resp.content))
    else:
        travis_url = '{}/{}/.travis.yml'.format(git_file_url, default_branch)
        resp = github_request(travis_url)
        if resp.status_code == 200:
            values['CI/CD'] = 'travis-ci'
            values.update(get_travis_values(repo, resp.content))

    values['Version'] = get_current_version(repo['releases_url'])

    if (lang == 'Python' or (values['Python'] is None or
            values['Python'] != 'N/A') or values['Pycodestyle']):
        values.update(get_install_values(url, default_branch))

        if (values['Django'] is not None and values['Django'] != 'N/A'):
            values.update(get_docker_values(url, default_branch))

    if values['Coveralls']:
        (coverage, has_js_coverage) = get_coverage(url, has_js)
        values['Coverage'] = coverage
        if has_js:
            values['JS Coverage'] = has_js_coverage

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
            row_data.update(get_cicd_values(repo))
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
