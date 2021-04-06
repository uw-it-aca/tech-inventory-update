from .base_settings import *

GITHUB_ORG = 'uw-it-aca'
GITHUB_OK_STATUS = [200, 404, 409]
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

GOOGLE_SHEET_ID = os.getenv('GOOGLE_SHEET_ID')
WORKSHEET_NAME = 'GitHub'

if os.getenv('ENV', 'localdev') == 'localdev':
    DEBUG = True
else:
    GS_CREDENTIALS = '/gcs/credentials.json'
