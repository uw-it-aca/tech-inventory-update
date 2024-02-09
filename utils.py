# Copyright 2024 UW-IT, University of Washington
# SPDX-License-Identifier: Apache-2.0

from dao.github import GitHub_DAO
from dao.coveralls import Coveralls_DAO
import yaml
import re

PYCODESTYLE_RE = re.compile(r'.*--exclude=(.*)')


def stringify(value):
    if value is None:
        value = ''
    elif value is True:
        value = 'Yes'
    elif value is False:
        value = 'No'
    return value


def parse_github_action_values(repo, data):
    values = {}
    config = yaml.full_load(data)
    for step in config.get('jobs', {}).get('test', {}).get('steps', []):
        if 'run' in step:
            if step.get('run').startswith('pycodestyle'):
                values['Pycodestyle'] = True
            elif step.get('run').startswith('coveralls'):
                values['Coveralls'] = True
        if 'with' in step and 'python-version' in step.get('with'):
            values['Language'] = 'Python{}'.format(
                str(step.get('with').get('python-version')))
        if ('uses' in step and
                'uw-it-aca/actions/python-linters' in step.get('uses')):
            values['Pycodestyle'] = True
            if repo.get('license'):
                values['License'] = (
                    repo.get('license').get('name') + ' with src headers')

    for step in config.get('jobs', {}).get('build', {}).get('steps', []):
        if ('run' in step and ('docker/test.sh' in step.get('run') or
                               'docker/test_python.sh' in step.get('run'))):
            values['Pycodestyle'] = True
            values['JSHint'] = True
            values['Coveralls'] = True
        if 'with' in step and 'python-version' in step.get('with'):
            values['Language'] = 'Python{}'.format(
                str(step.get('with').get('python-version')))
        if ('uses' in step and
                'uw-it-aca/actions/python-linters' in step.get('uses') and
                repo.get('license')):
            values['License'] = (
                repo.get('license').get('name') + ' with src headers')

    for step in config.get('jobs', {}).get('publish', {}).get('steps', []):
        if ('uses' in step and
                'uw-it-aca/actions/publish-pypi' in step.get('uses')):
            values['PyPI'] = True

    if config.get('env', {}).get('COVERAGE_PYTHON_VERSION'):
        values['Language'] = 'Python{}'.format(
            str(config.get('env').get('COVERAGE_PYTHON_VERSION')))

    return values


def parse_travis_values(repo, data):
    values = {}
    config = yaml.full_load(data)
    python_versions = [str(x) for x in config.get('python', [])]
    values['Language'] = 'Python{}'.format(','.join(
        sorted(python_versions, reverse=True)))

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


def get_repo_values(repo):
    ghclient = GitHub_DAO()
    url = repo['html_url']
    lang = repo['language']
    default_branch = repo['default_branch']
    git_file_url = url.replace(
        'https://github.com', 'https://raw.githubusercontent.com')
    (has_js, has_css) = ghclient.get_has_statics(
        repo['trees_url'], default_branch)

    repo_values = {
        'URL': url,
        'Name': repo.get('name'),
        'Language': lang,
        'Last Updated': repo.get('pushed_at'),
        'License': repo.get('license').get('name') if (
            repo.get('license') is not None) else 'N/A',
        'CI/CD': 'N/A',
        'Default Branch': default_branch,
        'Pycodestyle': False if (lang == 'Python') else 'N/A',
        'PyPI': False if (lang == 'Python') else 'N/A',
        'Django': None if (lang == 'Python') else 'N/A',
        'django-container': 'N/A',
        'Coveralls': False,
        'Coverage': 0,
        'Version': None,
    }

    webapp_values = {
        'URL': url,
        'Name': repo.get('name'),
        'Django': None if (lang == 'Python') else 'N/A',
        'Vue': None,
        'Vite': None,
        'Webpack': None,
        'django-compressor': None,
        'axdd-components': None,
        'Bootstrap': None,
        'Bootstrap Icons': None,
        'Prettier': None,
        'ESLint': None,
        'Stylint': None,
        'JSHint': False if has_js else 'N/A',
        'Coverage': False if has_js else 'N/A',
    }

    ga_url = '{}/{}/.github/workflows/cicd.yml'.format(
        git_file_url, default_branch)

    resp = ghclient.get(ga_url)
    if resp.status_code == 200:
        repo_values['CI/CD'] = 'github-actions'
        repo_values.update(parse_github_action_values(repo, resp.content))
    else:
        travis_url = '{}/{}/.travis.yml'.format(git_file_url, default_branch)
        resp = ghclient.get(travis_url)
        if resp.status_code == 200:
            repo_values['CI/CD'] = 'travis-ci'
            repo_values.update(parse_travis_values(repo, resp.content))

    repo_values['Version'] = ghclient.get_current_version(repo['releases_url'])

    if ((lang is not None and lang.startswith('Python')) or (
            repo_values['Pycodestyle'])):
        repo_values.update(ghclient.get_install_values(url, default_branch))
        webapp_values['Django'] = repo_values['Django']

        if (repo_values['Django'] is not None and
                repo_values['Django'] != 'N/A'):
            repo_values.update(ghclient.get_docker_values(url, default_branch))

    if repo_values['Coveralls']:
        (coverage, js_coverage) = Coveralls_DAO().get_coverage(url, has_js)
        repo_values['Coverage'] = coverage
        if has_js:
            webapp_values['Coverage'] = js_coverage

    webapp_values['JSHint'] = repo_values.get('JSHint')
    webapp_values['django-compressor'] = repo_values.get('django-compressor')
    try:
        del repo_values['JSHint']
        del repo_values['django-compressor']
    except KeyError:
        pass

    if has_js and has_css:
        webapp_values.update(ghclient.get_webapp_values(url, default_branch))
        return repo_values, webapp_values
    else:
        return repo_values, None
