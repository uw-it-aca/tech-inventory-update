# Copyright 2022 UW-IT, University of Washington
# SPDX-License-Identifier: Apache-2.0

import github_inventory_settings as settings
from threading import local
import requests
import json
import toml
import re

JS_RE = re.compile(r'.*\.js$')
CSS_RE = re.compile(r'.*\.(?:css|less)$')
DJANGO_RE = re.compile(r'[\'"]django([~=>].*)?[\'"]', re.I)
COMPRESSOR_RE = re.compile(r'[\'"]django-compressor([~=>].*)?[\'"]', re.I)
DJANGO_CONTAINER_RE = re.compile(r'FROM .*:(.*) as .*')
DJANGO_CONTAINER_VERSION_RE = re.compile(r'ARG DJANGO_CONTAINER_VERSION=(.*)')


class GitHub_DAO():
    def __init__(self):
        self._local = local()

    @property
    def client(self):
        if not hasattr(self._local, 'client'):
            access_token = getattr(settings, 'GITHUB_TOKEN', '')

            if not access_token:
                raise Exception(
                    'Need a GITHUB_TOKEN with access to github org')

            client = requests.Session()
            client.headers.update({
                'Authorization': 'token {}'.format(access_token),
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': '{}/github-inventory-updater'.format(
                    getattr(settings, 'GITHUB_ORG', ''))})
            self._local.client = client
        return self._local.client

    def get(self, url, headers={}):
        resp = self.client.get(url, headers=headers)
        if resp.status_code in getattr(settings, 'GITHUB_OK_STATUS', []):
            return resp

        raise Exception(
            'GitHub request failed, URL: {}, Status: {}, Response: {}'.format(
                url, resp.status_code, resp.content))

    def get_current_version(self, url):
        url = url.replace('{/id}', '/latest')
        resp = self.get(url)
        if resp.status_code == 200:
            data = json.loads(resp.content)
            return data.get('tag_name')

    def get_has_statics(self, url, default_branch):
        url = url.replace('{/sha}', '/{}?recursive=1'.format(default_branch))
        resp = self.get(url)
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

    def get_webapp_values(self, url, default_branch):
        git_file_url = url.replace(
            'https://github.com', 'https://raw.githubusercontent.com')
        package_url = '{}/{}/package.json'.format(
            git_file_url, default_branch)
        values = {}

        resp = self.get(package_url)
        if resp.status_code == 200:
            data = json.loads(resp.content)

            dependencies = data.get('dependencies')
            if dependencies:
                values['Vue'] = dependencies.get('vue')
                values['Webpack'] = dependencies.get('webpack')
                values['axdd-components'] = dependencies.get('axdd-components')
                values['Bootstrap'] = dependencies.get('bootstrap')
                values['Bootstrap Icons'] = dependencies.get('bootstrap-icons')

            dev_dependencies = data.get('devDependencies')
            if dev_dependencies:
                values['Vite'] = dev_dependencies.get('vite')
                values['Prettier'] = dev_dependencies.get('prettier')
                values['ESLint'] = dev_dependencies.get('eslint')
                values['Stylelint'] = dev_dependencies.get('stylelint')
        return values

    def get_docker_values(self, url, default_branch):
        git_file_url = url.replace(
            'https://github.com', 'https://raw.githubusercontent.com')
        dockerfile_url = '{}/{}/Dockerfile'.format(
            git_file_url, default_branch)
        values = {}

        resp = self.get(dockerfile_url)
        if resp.status_code == 200:
            content = resp.content.decode('utf-8')
            matches = (DJANGO_CONTAINER_VERSION_RE.match(content) or
                       DJANGO_CONTAINER_RE.match(content))
            if matches:
                values['django-container'] = matches.group(1)

        return values

    def get_install_values(self, url, default_branch):
        git_file_url = url.replace(
            'https://github.com', 'https://raw.githubusercontent.com')
        setup_url = '{}/{}/setup.py'.format(git_file_url, default_branch)
        values = {}

        resp = self.get(setup_url)
        if resp.status_code == 200:
            content = resp.content.decode('utf-8')
            values['Django'] = 'N/A'

            results = DJANGO_RE.findall(content)
            if len(results):
                values['Django'] = results[0] if (
                    len(results[0])) else 'Unpinned'

            results = COMPRESSOR_RE.findall(content)
            if len(results):
                values['django-compressor'] = results[0] if (
                    len(results[0])) else 'Unpinned'

        elif resp.status_code == 404:
            pyproject_url = '{}/{}/pyproject.toml'.format(
                git_file_url, default_branch)
            resp = self.get(pyproject_url)
            if resp.status_code == 200:
                values['Django'] = 'N/A'

                config = toml.loads(resp.content.decode('utf-8'))
                python_version = config.get('Python', config.get('python'))
                if python_version:
                    values['Language'] = 'Python{}'.format(python_version)
                values['Django'] = config.get(
                    'Django', config.get('django', 'N/A'))
                if config.get('django-compressor'):
                    values['django-compressor'] = True
        return values

    def get_repositories_for_org(self, org):
        url = 'https://api.github.com/orgs/{}/repos?per_page=100'.format(org)

        resp = self.get(url)
        repos = json.loads(resp.content)
        next_link = resp.links.get('next')

        while next_link is not None:
            resp = self.get(next_link['url'])
            repos.extend(json.loads(resp.content))
            next_link = resp.links.get('next')

        return sorted(repos, key=lambda item: item['pushed_at'], reverse=True)
