# Copyright 2021 UW-IT, University of Washington
# SPDX-License-Identifier: Apache-2.0

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from github_inventory.dao.github import GitHub_DAO
from github_inventory.dao.google import GoogleSheet_DAO
from github_inventory.utils import get_repo_values


class Command(BaseCommand):
    help = 'Updates spreadsheet with latest repo attributes'

    def handle(self, *args, **options):
        github_org = settings.get('GITHUB_ORG')

        repo_list = []
        for repo in GitHub_DAO().get_repositories_for_org(github_org):
            if not repo.get('archived'):  # Active repos only
                repo_list.append(get_repo_values(repo))

        GoogleSheet_DAO().update_sheet_values(settings.get('GOOGLE_SHEET_ID'),
                                              settings.get('WORKSHEET_NAME'),
                                              repo_list)
