"""Reads rate_sheet_2026-27.xlsx (tabs: READ ME, Settings, Seasons, Tours, Hotels, Transport).

The workbook is read-only input - never modified. Normalisation/cleaning happens here.
"""

from pathlib import Path

import openpyxl


def load_workbook(path: Path):
    return openpyxl.load_workbook(path, data_only=True, read_only=True)
