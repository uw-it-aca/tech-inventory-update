# Copyright 2021 UW-IT, University of Washington
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

    values = {
        'URL': url,
        'Name': repo.get('name'),
        'Language': lang,
        'Last Updated': repo.get('updated_at'),
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
        'JS Coverage': False if has_js else 'N/A',
        'JSHint': False if has_js else 'N/A',
        'Version': None,
    }

    ga_url = '{}/{}/.github/workflows/cicd.yml'.format(
        git_file_url, default_branch)

    resp = ghclient.get(ga_url)
    if resp.status_code == 200:
        values['CI/CD'] = 'github-actions'
        values.update(parse_github_action_values(repo, resp.content))
    else:
        travis_url = '{}/{}/.travis.yml'.format(git_file_url, default_branch)
        resp = ghclient.get(travis_url)
        if resp.status_code == 200:
            values['CI/CD'] = 'travis-ci'
            values.update(parse_travis_values(repo, resp.content))

    values['Version'] = ghclient.get_current_version(repo['releases_url'])

    if ((lang is not None and lang.startswith('Python')) or (
            values['Pycodestyle'])):
        values.update(ghclient.get_install_values(url, default_branch))

        if (values['Django'] is not None and values['Django'] != 'N/A'):
            values.update(ghclient.get_docker_values(url, default_branch))

    if values['Coveralls']:
        (coverage, has_js_coverage) = Coveralls_DAO().get_coverage(url, has_js)
        values['Coverage'] = coverage
        if has_js:
            values['JS Coverage'] = has_js_coverage

    return values
