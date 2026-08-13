# Copyright 2026 UW-IT, University of Washington
# SPDX-License-Identifier: Apache-2.0

import json
import logging
from threading import local

import github_inventory_settings as settings
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class Coveralls_DAO:
    def __init__(self):
        self._local = local()

    @property
    def client(self):
        if not hasattr(self._local, 'client'):
            github_org = getattr(settings, 'GITHUB_ORG', '')

            client = requests.Session()
            client.headers.update({
                'User-Agent': f'{github_org}/github-inventory-updater',
            })
            self._local.client = client
        return self._local.client

    def get_coverage(self, repo_url, default_branch, has_js=False):
        coveralls_url = repo_url.replace(
            'https://github.com', 'https://coveralls.io/repos/github')
        coveralls_url += f'/badge.svg?branch={default_branch}'
        coverage = 0
        has_js_coverage = False

        resp = self.client.get(coveralls_url)
        if resp.status_code == 200:
            html = resp.content.decode('utf-8')
            soup = BeautifulSoup(html, 'lxml')
            try:
                raw_percent = soup.find_all('text')[-1].text or '0'
                covered_percent = raw_percent.replace('%', '')
                # covered_percent = html.split('coveralls_')[1].split('.svg')[0] or 0
                coverage = int(float(covered_percent) * 10) / 10.0
            except (AttributeError, IndexError) as err:
                logger.error(f'Error determining coverage for {coveralls_url}: '
                             f'{err}, response: {html}')
                return (coverage, has_js_coverage)

            if has_js:
                commit_id = '' # data.get('commit_sha')
                build_url = (
                    f'https://coveralls.io/builds/{commit_id}.json?paths=*%2Fstatic%2F*'
                )
                resp = self.client.get(build_url)

                if resp.status_code == 200:
                    data = json.loads(resp.content)
                    if data.get('selected_source_files_count', 0) > 0:
                        has_js_coverage = data.get('paths_covered_percent', 0) > 0
        else:
            logger.error(f'Error fetching {coveralls_url}: {resp}')

        return (coverage, has_js_coverage)
