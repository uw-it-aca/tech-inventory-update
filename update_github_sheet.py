#!/usr/bin/env python3
# Copyright 2022 UW-IT, University of Washington
# SPDX-License-Identifier: Apache-2.0

import github_inventory_settings as settings
from dao.github import GitHub_DAO
from dao.google import GoogleSheet_DAO
from utils import get_repo_values
import logging
import sys


# setup basic logging
logging.basicConfig(level=logging.INFO,
                    format=('%(asctime)s %(levelname)s %(module)s.'
                            '%(funcName)s():%(lineno)d:'
                            ' %(message)s'),
                    handlers=(logging.StreamHandler(sys.stdout),))

logger = logging.getLogger(__name__)


if __name__ == '__main__':
    try:
        github_org = getattr(settings, 'GITHUB_ORG', '')

        repo_list = []
        for repo in GitHub_DAO().get_repositories_for_org(github_org):
            if not repo.get('archived'):  # Active repos only
                repo_list.append(get_repo_values(repo))

        GoogleSheet_DAO().update_sheet(
            getattr(settings, 'GOOGLE_SHEET_ID', ''),
            getattr(settings, 'WORKSHEET_NAME', ''),
            repo_list)

    except Exception as e:
        logger.exception(e)
        logger.critical(e)
