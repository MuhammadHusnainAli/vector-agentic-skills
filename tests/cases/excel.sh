# Excel skill script cases. Syntax: see tests/run_tests.sh.

t 'check_formula: unbalanced' 1 "unclosed '('" \
  "$XL/excel-formulas/scripts/check_formula.py" '=SUM(A1:A10'
t 'check_compat: version' 1 'Excel 2021+' \
  "$XL/excel-advanced-formulas/scripts/check_compat.py" --target 2019 '=XLOOKUP(A1,B:B,C:C)'
t 'inspect_workbook: structure' 0 'table Sales A1:D4' \
  "$XL/excel-fundamentals/scripts/inspect_workbook.py" "$FX/test.xlsx"
