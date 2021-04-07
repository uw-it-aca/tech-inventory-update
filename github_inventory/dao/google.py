# Copyright 2021 UW-IT, University of Washington
# SPDX-License-Identifier: Apache-2.0

from django.conf import settings
from github_inventory.utils import stringify
import gspread


def GoogleSheet_DAO():
    @property
    def client(self):
        credentials_path = getattr(settings, 'GS_CREDENTIALS', '')
        return gspread.service_account(filename=credentials_path)

    # def get_sheet_values(self, sheet_id, ws_name):
    #    ws = self.client.open_by_key(sheet_id).worksheet(ws_name)
    #    return ws.get_all_values()

    def update_sheet(self, sheet_id, ws_name, repo_list):
        ws = self.client.open_by_key(sheet_id).worksheet(ws_name)
        sheet_values = ws.get_all_values()
        col_names = sheet_values.pop(0)
        data_start_row = 2

        max_row = max(len(sheet_values), len(repo_list))
        cell_list = ws.range(
            data_start_row, 1, max_row + (data_start_row - 1), len(col_names))

        for cell in cell_list:
            try:
                row_data = repo_list[cell.row - data_start_row]
                value = row_data.get(col_names[cell.col - 1], '')
            except IndexError:
                value = ''
            cell.value = stringify(value)

        ws.update_cells(cell_list, value_input_option='RAW')
