"""
아임웹 입력폼("대학 제휴 DB") 데이터를 구글시트로 동기화.

아임웹은 입력폼 데이터에 대한 공식 API/웹훅을 제공하지 않으므로,
관리자 페이지에 자동 로그인해 "내보내기(엑셀)"로 데이터를 받아온 뒤
구글시트에 없는 새 행만 추가하는 방식으로 동작한다.

대상 시트("대학 제휴 DB" 탭)는 1행이 아니라 2행이 헤더이고,
G~I열("1차"/"2차"/"예약 여부")은 콜팀이 수기로 관리하는 칸이라
동기화 시 절대 건드리지 않고 A~F열만 채운다.

환경 변수 (GitHub Actions Secrets로 주입):
  IMWEB_ADMIN_ID              아임웹 관리자 로그인 아이디
  IMWEB_ADMIN_PW              아임웹 관리자 로그인 비밀번호
  GOOGLE_SERVICE_ACCOUNT_JSON 구글 서비스 계정 키(JSON) 전체 내용
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

# ── 사이트/시트 설정 ──────────────────────────────────────────────
ADMIN_FORM_URL = "https://dearchungdam.imweb.me/admin/contents/form?board_code=b2025031493a703dc00363"
SPREADSHEET_ID = "1-V6-SzJc3wBKnAB_elUA2wNMnK-lFTjSLmf6xza0fUs"
WORKSHEET_GID = 1385031413  # "대학 제휴 DB" 탭
HEADER_ROW = 2  # 이 탭은 1행이 아니라 2행이 헤더

# 엑셀의 작성시각 컬럼명 (예: "2026-07-22 10:56:07", 한국시간 기준)
TIMESTAMP_EXCEL_COLUMN = "응답시간"
KST = timezone(timedelta(hours=9))
# 백필용 임시 확대. 정상화 후 3으로 되돌릴 것.
LOOKBACK_HOURS = 6

# (시트 컬럼명, 엑셀 컬럼명) 순서쌍. 시트의 A~F열에 그대로 대응한다.
# G~I열("1차"/"2차"/"예약 여부")은 콜팀 수기 입력란이라 여기 포함하지 않는다.
COLUMN_MAP = [
    ("학교명", "학교명"),
    ("성함", "성함"),
    ("연락처", "연락처"),
    ("당일 시술 희망 여부", "당일 시술 희망 여부"),
    ("방문 희망일", "방문 희망일 (월~금 10:00~19:00, 토~일 및 공휴일 10:00~16:00)"),
    ("피부 고민 및 원하는 시술", "피부 고민이나 원하시는 시술이 있으시면 기재해주세요."),
]

# 새 데이터인지 판별할 때 기준으로 삼는 시트 컬럼명 (중복 신청 방지용 키)
DEDUPE_SHEET_COLUMNS = ["성함", "연락처", "방문 희망일"]


def _normalize_key_value(column_name: str, value) -> str:
    """dedupe 키 비교용 정규화.

    "연락처"는 엑셀을 다시 내보낼 때마다 텍스트("010-1234-5678")로 나올 때와
    숫자로 인식되어 앞자리 0과 대시가 사라진 값("1012345678")으로 나올 때가 섞여
    있어서, 숫자만 남기고 10자리(0 없이 시작)면 앞에 0을 붙여 맞춘다.
    """
    text = str(value).strip()
    if column_name != "연락처":
        return text
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) == 10 and not digits.startswith("0"):
        digits = "0" + digits
    return digits


# ── 셀렉터 ──────────────────────────────────────────────────────
LOGIN_ID_SELECTOR = 'input[name="uid"]'
LOGIN_PW_SELECTOR = 'input[name="passwd"]'
LOGIN_SUBMIT_SELECTOR = 'button[type="submit"]'
EXPORT_OPEN_SELECTOR = 'text=내보내기'
GENERATE_BUTTON_SELECTOR = 'button:has-text("파일 생성")'
GENERATED_FILE_LINK_SELECTOR = 'a[href*="download_excel_contents"]'


def download_form_excel() -> pd.DataFrame:
    imweb_id = os.environ["IMWEB_ADMIN_ID"]
    imweb_pw = os.environ["IMWEB_ADMIN_PW"]

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        page.goto(ADMIN_FORM_URL)

        # 로그인이 안 되어 있으면 아임웹이 로그인 페이지로 리다이렉트한다.
        if page.locator(LOGIN_ID_SELECTOR).count() > 0:
            page.fill(LOGIN_ID_SELECTOR, imweb_id)
            page.fill(LOGIN_PW_SELECTOR, imweb_pw)
            page.click(LOGIN_SUBMIT_SELECTOR)
            page.wait_for_load_state("networkidle")
            page.goto(ADMIN_FORM_URL)
            page.wait_for_load_state("networkidle")

        try:
            # "내보내기" 클릭은 즉시 다운로드하지 않고 모달을 연다.
            page.click(EXPORT_OPEN_SELECTOR)
            # 모달 안의 "파일 생성" 버튼을 눌러야 서버가 엑셀 파일을 비동기로 생성한다.
            page.click(GENERATE_BUTTON_SELECTOR)
            # 파일 생성이 끝나면 목록에 다운로드 링크가 나타난다.
            file_link = page.locator(GENERATED_FILE_LINK_SELECTOR).first
            file_link.wait_for(state="visible", timeout=60000)
            with page.expect_download() as download_info:
                file_link.click()
            download = download_info.value
        except Exception:
            debug_dir = os.environ.get("DEBUG_ARTIFACT_DIR", ".")
            page.screenshot(path=os.path.join(debug_dir, "debug.png"), full_page=True)
            with open(os.path.join(debug_dir, "debug.html"), "w", encoding="utf-8") as f:
                f.write(page.content())
            print(f"현재 페이지 URL: {page.url}", file=sys.stderr)
            browser.close()
            raise

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            download.save_as(tmp.name)
            excel_path = tmp.name

        browser.close()

    df = pd.read_excel(excel_path)
    os.unlink(excel_path)
    return df


def filter_recent(df: pd.DataFrame) -> pd.DataFrame:
    """작성시각이 LOOKBACK_HOURS 이내인 행만 남긴다."""
    if TIMESTAMP_EXCEL_COLUMN not in df.columns:
        print(f"엑셀에 '{TIMESTAMP_EXCEL_COLUMN}' 컬럼이 없습니다. 실제 컬럼: {list(df.columns)}", file=sys.stderr)
        sys.exit(1)

    timestamps = pd.to_datetime(df[TIMESTAMP_EXCEL_COLUMN], errors="coerce")
    cutoff = (datetime.now(KST) - timedelta(hours=LOOKBACK_HOURS)).replace(tzinfo=None)
    return df[timestamps >= cutoff]


def open_worksheet() -> gspread.Worksheet:
    creds_info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    return spreadsheet.get_worksheet_by_id(WORKSHEET_GID)


def existing_keys(worksheet: gspread.Worksheet) -> set:
    records = worksheet.get_all_records(head=HEADER_ROW)
    return {
        tuple(_normalize_key_value(col, record.get(col, "")) for col in DEDUPE_SHEET_COLUMNS)
        for record in records
    }


def next_empty_row(worksheet: gspread.Worksheet) -> int:
    # B열("성함")에 값이 있는 마지막 행 다음 줄에 이어서 쓴다.
    col_b = worksheet.col_values(2)
    return max(len(col_b) + 1, HEADER_ROW + 1)


def main():
    print("아임웹에서 입력폼 데이터 내려받는 중...")
    df = download_form_excel()
    print(f"엑셀에서 전체 {len(df)}건 확인")

    df = filter_recent(df)
    print(f"최근 {LOOKBACK_HOURS}시간 이내 작성분 {len(df)}건으로 필터링")

    if df.empty:
        print("최근 작성된 데이터가 없습니다.")
        return

    missing = [excel_col for _, excel_col in COLUMN_MAP if excel_col not in df.columns]
    if missing:
        print(f"엑셀에 예상 컬럼이 없습니다: {missing}. 실제 컬럼: {list(df.columns)}", file=sys.stderr)
        sys.exit(1)

    worksheet = open_worksheet()
    seen = existing_keys(worksheet)

    dedupe_excel_cols = dict(COLUMN_MAP)
    excel_cols_for_key = [dedupe_excel_cols[c] for c in DEDUPE_SHEET_COLUMNS]

    new_rows = []
    for _, row in df.iterrows():
        key = tuple(
            _normalize_key_value(sheet_col, row.get(excel_col, ""))
            for sheet_col, excel_col in zip(DEDUPE_SHEET_COLUMNS, excel_cols_for_key)
        )
        if key in seen:
            continue
        seen.add(key)
        new_rows.append([str(row.get(excel_col, "")) for _, excel_col in COLUMN_MAP])

    if not new_rows:
        print("새로 추가할 데이터가 없습니다.")
        return

    start_row = next_empty_row(worksheet)
    end_row = start_row + len(new_rows) - 1
    end_col_letter = chr(ord("A") + len(COLUMN_MAP) - 1)  # F
    worksheet.update(
        range_name=f"A{start_row}:{end_col_letter}{end_row}",
        values=new_rows,
        value_input_option="USER_ENTERED",
    )
    print(f"{len(new_rows)}건을 구글시트 {start_row}행부터 추가했습니다.")


if __name__ == "__main__":
    main()
