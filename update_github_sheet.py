from utils import (get_google_sheet_id, get_google_client, get_github_client)
import json

SHEET_NAME = 'GitHub'


def get_github_urls_from_sheet(sheet_id):
    client = get_google_client()
    ws = client.open_by_key(sheet_id).worksheet(SHEET_NAME)
    urls = {}
    index = 0
    for row in ws.col_values(2):
        index += 1
        if len(row):
            url = re.sub('/$', '', row[0])
            urls[url] = index
    return urls


def get_column_names(sheet_id):
    client = get_google_client()
    ws = client.open_by_key(sheet_id).worksheet(SHEET_NAME)
    names = {}
    index = 0
    for col in ws.row_values(1):
        index += 1
        names[col] = index
    return names


def get_repositories_for_org(org):
    client = get_github_client()
    url = 'https://api.github.com/orgs/{}/repos?per_page=100'.format(org)
    repos = []

    resp = client.get(url)
    repos.append(json.loads(resp.content))
    next_url = resp.links.get('next')

    while next_url is not None:
        resp = client.get(next_url)
        repos.append(json.loads(resp.content))
        next_url = resp.links.get('next')

    return repos


def main(*args, **kwargs):
    sheet_id = get_google_sheet_id()
    col_names = get_column_names(sheet_id)
    existing_urls = get_github_urls_from_sheet(sheet_id)
    all_repos = get_repositories_for_org('uw-it-aca')
    last_row_index = max(existing_urls.values())

    client = get_google_client()
    ws = client.open_by_key(sheet_id).worksheet(SHEET_NAME)

    cell_data = []
    for repo in all_repos:
        row_data = {}
        url = repo['html_url']
        if url in existing_urls:
            row_index = existing_urls[url]
        else:
            last_row_index += 1
            row_index = last_row_index

        row_data['URL'] = url
        row_data['Name'] = repo['name']
        row_data['Language'] = repo['language']
        row_data['Last Updated'] = repo['updated_at']

        for key in row_data:
            col_index = col_names[key]
            cell = ws.cell(row_index, col_index)
            cell.value = row_data[key]
            cell_data.append(cell)

    ws.update_cells(cell_data, value_input_option='RAW')

if __name__ == '__main__':
    main()
