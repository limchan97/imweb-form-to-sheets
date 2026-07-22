"""일회성 진단: 시트 47~52행 값을 그대로 출력해 중복 추가 여부를 확인한다."""

from sync_form_to_sheet import open_worksheet

worksheet = open_worksheet()
values = worksheet.get_values("A47:F52")
for i, row in enumerate(values, start=47):
    print(i, row)
