"""
아임웹 입력폼(울써마지 대학 제휴 DB) 데이터를 구글시트로 동기화.

아임웹은 입력폼 데이터에 대한 공식 API/웹훅을 제공하지 않으므로,
관리자 페이지에 자동 로그인해 "내보내기(엑셀)"로 데이터를 받아온 뒤
구글시트에 없는 새 행만 추가하는 방식으로 동작한다.

환경 변수 (GitHub Actions Secrets로 주입):
  IMWEB_ADMIN_ID              아임웹 관리자 로그인 아이디
  IMWEB_ADMIN_PW              아임웹 관리자 로그인 비밀번호
  GOOGLE_SERVICE_ACCOUNT_JSON 구글 서비스 계정 키(JSON) 전체 내용
"""

import io
import json
import os
import sys
import tempfile

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

# ── 사이트/시트 설정 ──────────────────────────────────────────────
ADMIN_FORM_URL = "https://dearchungdam.imweb.me/admin/contents/form?board_code=b2025031493a703dc00363"
SPREADSHEET_ID = "1-V6-SzJc3wBKnAB_elUA2wNMnK-lFTjSLmf6xza0fUs"
WORKSHEET_GID = 1385031413

# 새 데이터인지 판별할 때 기준으로 삼는 컬럼들 (엑셀/시트에 모두 존재해야 함)
DEDUPE_COLUMNS = ["성함", "연락처", "방문 희망일 (월~금 10:00~19:00, 토~일 및 공휴일 10:00~16:00)"]

# ── 셀렉터 (⚠ 최초 1회 실제 페이지에서 반드시 확인/수정 필요) ──────
# 아임웹 로그인 폼 인풋/버튼의 실제 name·id·class는 사이트마다 다를 수 있어
# 아래 값은 일반적인 아임웹 관리자 로그인 폼 구조를 기준으로 한 최선의 추정치다.
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
            # 파일 생성이 끝나면 목록에 .xlsx로 끝나는 파일명 링크가 나타난다.
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


def open_worksheet() -> gspread.Worksheet:
    creds_info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    return spreadsheet.get_worksheet_by_id(WORKSHEET_GID)


def existing_keys(worksheet: gspread.Worksheet) -> tuple[set, list]:
    records = worksheet.get_all_records()
    keys = {
        tuple(str(record.get(col, "")).strip() for col in DEDUPE_COLUMNS)
        for record in records
    }
    header = worksheet.row_values(1)
    return keys, header


def main():
    print("아임웹에서 입력폼 데이터 내려받는 중...")
    df = download_form_excel()
    print(f"엑셀에서 {len(df)}건 확인")

    missing = [c for c in DEDUPE_COLUMNS if c not in df.columns]
    if missing:
        print(f"엑셀에 예상 컬럼이 없습니다: {missing}. 실제 컬럼: {list(df.columns)}", file=sys.stderr)
        sys.exit(1)

    worksheet = open_worksheet()
    print(f"[디버그] 시트 헤더: {worksheet.row_values(1)}", file=sys.stderr)
    seen, header = existing_keys(worksheet)

    new_rows = []
    for _, row in df.iterrows():
        key = tuple(str(row.get(col, "")).strip() for col in DEDUPE_COLUMNS)
        if key in seen:
            continue
        seen.add(key)
        new_rows.append([str(row.get(col, "")) for col in header])

    if not new_rows:
        print("새로 추가할 데이터가 없습니다.")
        return

    worksheet.append_rows(new_rows, value_input_option="USER_ENTERED")
    print(f"{len(new_rows)}건을 구글시트에 추가했습니다.")


if __name__ == "__main__":
    main()
