# Copyright 2025 UW-IT, University of Washington
# SPDX-License-Identifier: Apache-2.0

from threading import local
import requests
import json


class Coveralls_DAO():
    def __init__(self):
        self._local = local()

    @property
    def client(self):
        if not hasattr(self._local, 'client'):
            self._local.client = requests.Session()
        return self._local.client

    def get_coverage(self, repo_url, has_js=False):
        coveralls_url = repo_url.replace(
            'https://github.com', 'https://coveralls.io/github')
        coveralls_url += '.json'
        coverage = None
        has_js_coverage = False

        resp = self.client.get(coveralls_url)
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
                resp = self.client.get(build_url)

                if resp.status_code == 200:
                    data = json.loads(resp.content)
                    if data.get('selected_source_files_count', 0) > 0:
                        has_js_coverage = data.get(
                            'paths_covered_percent', 0) > 0

        return (coverage, has_js_coverage)
