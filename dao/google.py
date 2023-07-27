# Copyright 2023 UW-IT, University of Washington
# SPDX-License-Identifier: Apache-2.0

import github_inventory_settings as settings
from threading import local
from utils import stringify
import gspread


class GoogleSheet_DAO():
    def __init__(self):
        self._local = local()

    @property
    def client(self):
        if not hasattr(self._local, 'client'):
            credentials = getattr(settings, 'GS_CREDENTIALS', '')
            self._local.client = gspread.service_account(filename=credentials)
        return self._local.client

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
