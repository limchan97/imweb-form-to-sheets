"""일회성 진단: '대학 제휴 DB' 탭에서 (성함, 연락처) 기준 중복 행을 찾는다."""

import json
import os
from collections import defaultdict

import gspread
from google.oauth2.service_account import Credentials

SPREADSHEET_ID = "1-V6-SzJc3wBKnAB_elUA2wNMnK-lFTjSLmf6xza0fUs"
WORKSHEET_GID = 1385031413
HEADER_ROW = 2


def main():
    creds_info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    ws = spreadsheet.get_worksheet_by_id(WORKSHEET_GID)

    col_b = ws.col_values(2)  # 성함
    col_c = ws.col_values(3)  # 연락처
    last_row = max(len(col_b), len(col_c))

    groups = defaultdict(list)
    for r in range(HEADER_ROW + 1, last_row + 1):
        name = col_b[r - 1] if r - 1 < len(col_b) else ""
        phone = col_c[r - 1] if r - 1 < len(col_c) else ""
        if not name and not phone:
            continue
        key = (name.strip(), phone.strip())
        groups[key].append(r)

    dupes = {k: v for k, v in groups.items() if len(v) > 1}
    print(f"전체 데이터 행: {last_row - HEADER_ROW}건, 중복 (성함+연락처) 그룹: {len(dupes)}개")
    for key, rows in list(dupes.items())[:50]:
        print(f"  {key} -> 행 {rows}")


if __name__ == "__main__":
    main()
