"""일회성 진단 스크립트: 스프레드시트의 탭 목록과 각 탭의 1~2행을 출력한다."""

import json
import os

import gspread
from google.oauth2.service_account import Credentials

SPREADSHEET_ID = "1-V6-SzJc3wBKnAB_elUA2wNMnK-lFTjSLmf6xza0fUs"


def main():
    creds_info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SPREADSHEET_ID)

    for ws in spreadsheet.worksheets():
        print(f"=== 탭: '{ws.title}' (gid={ws.id}, rows={ws.row_count}, cols={ws.col_count}) ===")
        values = ws.get_values("A1:N3")
        for i, row in enumerate(values, start=1):
            print(f"  row{i}: {row}")


if __name__ == "__main__":
    main()
