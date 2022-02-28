# Copyright 2022 UW-IT, University of Washington
# SPDX-License-Identifier: Apache-2.0

import os

GITHUB_ORG = 'uw-it-aca'
GITHUB_OK_STATUS = [200, 404, 409]
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

GOOGLE_SHEET_ID = os.getenv('GOOGLE_SHEET_ID')
WORKSHEET_NAME = 'GitHub'
GS_CREDENTIALS = '/gcs/credentials.json'
