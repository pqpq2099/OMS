import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials


def get_spreadsheet():

    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    creds_dict = st.secrets["gcp_service_account"]

    creds = Credentials.from_service_account_info(
        creds_dict,
        scopes=scope
    )

    client = gspread.authorize(creds)

    sheet = client.open(st.secrets["spreadsheet_name"])

    return sheet


def load_table(sheet_name):

    sheet = get_spreadsheet().worksheet(sheet_name)

    data = sheet.get_all_records()

    return pd.DataFrame(data)


def append_rows_by_header(sheet_name, rows):

    sheet = get_spreadsheet().worksheet(sheet_name)

    headers = sheet.row_values(1)

    values = []

    for r in rows:
        row = [r.get(h, "") for h in headers]
        values.append(row)

    sheet.append_rows(values)
