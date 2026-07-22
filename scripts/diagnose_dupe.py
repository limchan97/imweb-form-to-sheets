"""일회성 진단: 시트 47~52행 값을 그대로 출력해 중복 추가 여부를 확인한다."""

from sync_form_to_sheet import open_worksheet

worksheet = open_worksheet()
col_b = worksheet.col_values(2)
print(f"B열 길이: {len(col_b)}, 마지막 5개: {col_b[-5:]}")
values = worksheet.get_values("A45:F55")
for i, row in enumerate(values, start=45):
    print(i, row)
