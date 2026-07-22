from sync_form_to_sheet import open_worksheet

worksheet = open_worksheet()
col_b = worksheet.col_values(2)
print(f"B열 길이: {len(col_b)}, 마지막 3개: {col_b[-3:]}")
