import httplib2
import yaml
import os
import re
import json
import boto3
import base64
import string

from apiclient import discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage
from oauth2client.service_account import ServiceAccountCredentials

SCOPES = 'https://www.googleapis.com/auth/spreadsheets'
CLIENT_SECRET_FILE = 'client_secret.json'
GITHUB_AUTH = None
GOOGLE_JSON = None


if 'GITHUB_AUTH_ENC' in os.environ:
    kms = boto3.client('kms')
    ENCRYPTED = os.environ['GITHUB_AUTH_ENC']
    raw = base64.b64decode(ENCRYPTED)
    GITHUB_AUTH = kms.decrypt(CiphertextBlob=raw)['Plaintext']

    ENCRYPTED = os.environ['GOOGLE_CREDENTIALS_ENC']
    raw = base64.b64decode(ENCRYPTED)
    GOOGLE_JSON = kms.decrypt(CiphertextBlob=raw)['Plaintext']


def get_credentials():
    if GOOGLE_JSON:
        json_data = json.loads(GOOGLE_JSON)
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(
            json_data, SCOPES)
    else:
        credentials = ServiceAccountCredentials.from_json_keyfile_name(
            'client_secret.json', SCOPES)
    return credentials


def get_coveralls_data(url):
    coveralls_path = url.replace('https://github.com',
                                 'https://coveralls.io/github/')
    coveralls_path += ".json"
    (headers, content) = httplib2.Http().request(coveralls_path, 'GET')

    status = headers['status']
    if '200' != status:
        return (0, False)

    data = json.loads(content)
    raw = data['covered_percent']
    coverage = int(float(raw) * 10) / 10.0

    # Look for static content in the build...
    commit_id = data['commit_sha']
    details_url = ("https://coveralls.io/builds/"+commit_id+"/source_files.js"
                   "?filter=all&sSearch=%2Fstatic%2F")
    (headers, content) = httplib2.Http().request(details_url, 'GET')

    data = json.loads(content)
    has_js_coverage = False
    if data['iTotalRecords'] > 0:
        has_js_coverage = True

    return (coverage, has_js_coverage)


def get_has_statics(url):
    api_path = url.replace('https://github.com/',
                           'https://api.github.com/repos/')
    api_path += '/git/trees/master?recursive=1'

    if GITHUB_AUTH:
        access_token = GITHUB_AUTH
    else:
        access_token = os.environ.get('GITHUB_AUTH', None)

    if not access_token:
        raise Exception("Need a GITHUB_AUTH env var.  Should be formatted "
                        " as <username>:<personal access token>")
    auth = base64.encodestring(access_token)
    request_headers = {'Authorization': 'Basic ' + auth}
    (headers, content) = httplib2.Http().request(api_path, 'GET',
                                                 headers=request_headers)

    data = json.loads(content)
    has_js = False
    has_css = False
    for item in data['tree']:
        path = item['path']

        if re.match('.*\.js$', path):
            has_js = True

        if re.match('.*\.css$', path):
            has_css = True

        if re.match('.*\.less$', path):
            has_css = True

    return(has_js, has_css)


def get_travis_config_values(repos):
    travis_path = repos.replace('https://github.com',
                                'https://raw.githubusercontent.com')
    travis_path = travis_path + '/master/.travis.yml'

    (headers, content) = httplib2.Http().request(travis_path, 'GET')

    config = yaml.load(content)

    values = {
        'Python 2.7': False,
        'Python 3.6': False,
        'PEP 8': False,
        'No (non migration) PEP8 exclusions': False,
        'JSHint': False,
        'Recess': False,
        'Coveralls': False,
    }

    status = headers['status']
    if '200' != status:
        return values

    python_versions = config['python']
    for version in python_versions:
        if "2.7" == version:
            values['Python 2.7'] = True
        if "3.6" == version:
            values['Python 3.6'] = True

    for step in config['script']:
        if 0 == step.find('pep8'):
            values['PEP 8'] = True

            clean_pep8 = True
            matches = re.match('.*--exclude=(.*)', step)
            if matches:
                excludes = matches.group(1).split(",")
                for path in excludes:
                    if path.find('migrations') == -1:
                        clean_pep8 = False

            values['No (non migration) PEP8 exclusions'] = clean_pep8
        if 0 == step.find('jshint'):
            values['JSHint'] = True

        if 0 == step.find('if recess'):
            values['Recess'] = True

    for step in config.get('after_script', []):
        if 0 == step.find('coveralls'):
            values['Coveralls'] = True
    return values


def get_sheets_service():
    credentials = get_credentials()
    http = credentials.authorize(httplib2.Http())
    discoveryUrl = ('https://sheets.googleapis.com/$discovery/rest?'
                    'version=v4')
    service = discovery.build('sheets', 'v4', http=http,
                              discoveryServiceUrl=discoveryUrl)

    return service


def get_column_lookup(sheet_id):
    service = get_sheets_service()
    cell_index = {}
    rangeName = 'Sheet1!E2:BA2'
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=rangeName).execute()
    values = result.get('values', [])
    if not values:
        raise Exception("Can't find column headers")
    else:
        index = 5
        for row in values[0]:
            cell_index[row] = index
            index += 1

    return cell_index


def get_github_urls(sheet_id):
    service = get_sheets_service()
    rangeName = 'Sheet1!C1:C100'
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=rangeName).execute()
    values = result.get('values', [])
    if not values:
        raise Exception("Can't get github urls")

    github_urls = []
    index = 0
    for row in values:
        index += 1
        if not len(row):
            continue
        url = row[0]
        if url.find('https://github.com') != 0:
            continue

        url = re.sub('/$', '', url)
        github_urls.append({'url': url, 'row': index})

    return github_urls


def _build_cell_names():
    cells = [None]
    for c1 in ('', 'A', 'B'):
        for c2 in (list(string.ascii_uppercase)):
            cells.append(c1+c2)
    return cells


_cell_names = _build_cell_names()


def get_cell_name(row, col):
    return "%s%s" % (_cell_names[col], row)


def main(*args, **kwargs):
    sheet_id = os.environ.get('GOOGLE_SHEET_ID', None)
    if not sheet_id:
        raise Exception("Missing ENV: GOOGLE_SHEET_ID")

    column_lookup = get_column_lookup(sheet_id)

    github_urls = get_github_urls(sheet_id)

    service = get_sheets_service()

    all_update_cells = []

    for project in github_urls:
        url = project['url']
        index = project['row']
        travis_data = get_travis_config_values(url)
        (coverage, js_coverage) = get_coveralls_data(url)
        (has_js, has_css) = get_has_statics(url)

        travis_data['Coverage %'] = coverage
        travis_data['Has Javascript Coverage'] = js_coverage

        if not has_js:
            travis_data['Has Javascript Coverage'] = 'N/A'
            travis_data['JSHint'] = 'N/A'

        if not has_css:
            travis_data['Recess'] = 'N/A'

        for key in travis_data:
            col = column_lookup[key]
            value = ""
            if travis_data[key] is True:
                value = "Yes"
            elif travis_data[key] is False:
                value = "No"
            elif travis_data[key] is None:
                value = ""
            else:
                value = travis_data[key]

            cell_name = get_cell_name(index, col)
            all_update_cells.append({'range': cell_name,
                                     'values': [[value]]})
    body = {
        'valueInputOption': 'RAW',
        'data': all_update_cells,
    }

    sheets = service.spreadsheets()
    request = sheets.values().batchUpdate(spreadsheetId=sheet_id, body=body)
    response = request.execute()


if __name__ == '__main__':
    main()
