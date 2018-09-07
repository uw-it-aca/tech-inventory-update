from utils import (get_google_sheet_id, get_google_client, get_github_client)
import requests
import yaml
import json

SHEET_NAME = 'GitHub'


def get_column_names(sheet_id):
    client = get_google_client()
    ws = client.open_by_key(sheet_id).worksheet(SHEET_NAME)
    return ws.row_values(1)


def get_repositories_for_org(org):
    client = get_github_client()
    url = 'https://api.github.com/orgs/{}/repos?per_page=100'.format(org)

    resp = client.get(url)
    repos = json.loads(resp.content)
    next_link = resp.links.get('next')

    while next_link is not None:
        resp = client.get(next_link['url'])
        repos.extend(json.loads(resp.content))
        next_link = resp.links.get('next')

    return sorted(repos, key=lambda item: item['id'])


def parse_travis_config(url):
    git_file_url = url.replace(
        'https://github.com', 'https://raw.githubusercontent.com')
    travis_url = git_file_url + '/master/.travis.yml'

    values = {
        'Travis CI': False,
        'Pycodestyle': False,
        'PyPI': False,
        'Coveralls': False,
        'JSHint': False,
        'Python': None,
    }

    client = get_github_client()
    resp = client.get(travis_url)

    if resp.status_code != requests.codes.ok:
        return values

    config = yaml.load(resp.content)

    values['Python'] = ','.join(config.get('python', []))

    for step in config.get('script', []):
        if 0 == step.find('pycodestyle'):
            values['Pycodestyle'] = True
        elif 0 == step.find('jshint'):
            values['JSHint'] = True

    for step in config.get('after_script', []):
        if 0 == step.find('coveralls'):
            values['Coveralls'] = True

    if config.get('deploy', {}).get('provider', '') == 'pypi':
        values['PyPI'] = True

    values['Travis CI'] = True
    return values


def main(*args, **kwargs):
    sheet_id = get_google_sheet_id()
    col_names = get_column_names(sheet_id)
    all_repos = get_repositories_for_org('uw-it-aca')

    repo_list = []
    for repo in all_repos:
        row_data = {
            'URL': repo['html_url'],
            'Name': repo['name'],
            'Language': repo['language'],
            'Last Updated': repo['updated_at'],
        }
        row_data.update(parse_travis_config(repo['html_url']))
        repo_list.append(row_data)

    client = get_google_client()
    ws = client.open_by_key(sheet_id).worksheet(SHEET_NAME)
    cell_list = ws.range(2, 1, len(all_repos), 12)

    for cell in cell_list:
        value = repo_list[cell.row-1].get(col_names[cell.col-1], '')
        if value is True:
            value = 'Yes'
        elif value is False:
            value = 'No'
        elif value is None:
            value = ''
        cell.value = value

    ws.update_cells(cell_list, value_input_option='RAW')

if __name__ == '__main__':
    main()
