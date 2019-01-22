from google.auth.transport.requests import AuthorizedSession
import google.auth
import gspread
import requests
import string
import base64
import boto3
import os

GOOGLE_SCOPES = 'https://www.googleapis.com/auth/spreadsheets'
GOOGLE_KEY_PATH = '/tmp/key.json'
GOOGLE_CLIENT = None
GITHUB_CLIENT = None
GITHUB_OK_STATUS = [200, 404, 409]
COVERALLS_CLIENT = None
KMS_CLIENT = boto3.client('kms', region_name='us-west-2')


def get_google_sheet_id():
    sheet_id = os.environ.get('GOOGLE_SHEET_ID', None)
    if not sheet_id:
        raise Exception('Missing ENV: GOOGLE_SHEET_ID')
    return sheet_id


def get_google_client():
    global GOOGLE_CLIENT
    if GOOGLE_CLIENT is None:
        if 'GOOGLE_CREDENTIALS_ENC' in os.environ:
            raw = base64.b64decode(os.environ['GOOGLE_CREDENTIALS_ENC'])
            text = KMS_CLIENT.decrypt(CiphertextBlob=raw)['Plaintext']

            with open(GOOGLE_KEY_PATH, 'wb') as f:
                f.write(text)

            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = GOOGLE_KEY_PATH

        # export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
        credentials, project_id = google.auth.default(scopes=[GOOGLE_SCOPES])

        if not credentials:
            raise Exception('Need a GOOGLE_APPLICATION_CREDENTIALS env var')

        try:
            os.remove(GOOGLE_KEY_PATH)
        except OSError:
            pass

        GOOGLE_CLIENT = gspread.Client(auth=credentials)
        GOOGLE_CLIENT.session = AuthorizedSession(credentials)
    return GOOGLE_CLIENT


def github_request(url, headers={}):
    global GITHUB_CLIENT
    if GITHUB_CLIENT is None:
        if 'GITHUB_AUTH_ENC' in os.environ:
            raw = base64.b64decode(os.environ['GITHUB_AUTH_ENC'])
            access_token = KMS_CLIENT.decrypt(CiphertextBlob=raw)['Plaintext']
        else:
            access_token = os.environ.get('GITHUB_AUTH', None)

        if not access_token:
            raise Exception(
                'Need a GITHUB_AUTH env var, containing an access token')

        GITHUB_CLIENT = requests.Session()
        GITHUB_CLIENT.headers.update({
            'Authorization': 'token {}'.format(access_token.decode('utf-8')),
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'uw-it-aca/tech-inventory-updater'})

    resp = GITHUB_CLIENT.get(url, headers=headers)
    if resp.status_code in GITHUB_OK_STATUS:
        return resp

    raise Exception(
        'GitHub request failed, URL: {}, Status: {}, Response: {}'.format(
            url, resp.status_code, resp.content))


def get_coveralls_client():
    global COVERALLS_CLIENT
    if COVERALLS_CLIENT is None:
        COVERALLS_CLIENT = requests.Session()
    return COVERALLS_CLIENT
