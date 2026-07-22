"""일회성 진단: 실제로 쓰지는 않고, dedupe 판정 과정만 그대로 재현해서 출력한다."""

from sync_form_to_sheet import (
    COLUMN_MAP,
    DEDUPE_SHEET_COLUMNS,
    download_form_excel,
    existing_keys,
    filter_recent,
    next_empty_row,
    open_worksheet,
)

df = download_form_excel()
print(f"엑셀 전체 {len(df)}건")
df = filter_recent(df)
print(f"최근 필터링 {len(df)}건")

worksheet = open_worksheet()
seen = existing_keys(worksheet)
print(f"시트에서 읽은 기존 키 개수: {len(seen)}")

dedupe_excel_cols = dict(COLUMN_MAP)
excel_cols_for_key = [dedupe_excel_cols[c] for c in DEDUPE_SHEET_COLUMNS]

for _, row in df.iterrows():
    key = tuple(str(row.get(col, "")).strip() for col in excel_cols_for_key)
    print(f"엑셀에서 계산한 key: {key!r}")
    print(f"seen에 있음? {key in seen}")
    matched = [k for k in seen if k[0] == key[0] and k[1] == key[1]]
    print(f"시트에 있는 비슷한 키(성함/연락처 일치): {matched}")
    row_values = [str(row.get(excel_col, "")) for _, excel_col in COLUMN_MAP]
    print(f"실제로 쓸 값: {row_values}")

print(f"next_empty_row: {next_empty_row(worksheet)}")
