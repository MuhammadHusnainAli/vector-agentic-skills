# Array Manipulation Functions Reference

Functions for combining, reshaping, and extracting portions of arrays in Excel 365/2024+.

## HSTACK

Combine arrays horizontally (side by side).

### Syntax

```
=HSTACK(array1, [array2], ...)
```

### Basic Examples

Combine two columns:
```
=HSTACK(A1:A10, B1:B10)
```

Combine multiple ranges:
```
=HSTACK(A1:A10, C1:C10, E1:E10)
```

Add calculated column:
```
=HSTACK(A1:B10, A1:A10 * B1:B10)
```

### With Different Row Counts

Arrays with different heights are padded with #N/A:
```
=HSTACK(A1:A5, B1:B10)
```

Use IFERROR to replace padding:
```
=IFERROR(HSTACK(A1:A5, B1:B10), "")
```

### Practical Examples

Add row numbers:
```
=HSTACK(SEQUENCE(ROWS(A1:C10)), A1:C10)
```

Combine data with lookup results:
```
=HSTACK(A1:A10, XLOOKUP(A1:A10, D:D, E:E))
```

Create table with headers:
```
=VSTACK(
  HSTACK("ID", "Name", "Value"),
  HSTACK(A2:A10, B2:B10, C2:C10)
)
```

## VSTACK

Combine arrays vertically (top to bottom).

### Syntax

```
=VSTACK(array1, [array2], ...)
```

### Basic Examples

Stack two ranges:
```
=VSTACK(A1:C5, A10:C15)
```

Add header row:
```
=VSTACK({"Name", "Age", "City"}, A2:C100)
```

Combine multiple tables:
```
=VSTACK(Sheet1!A1:C10, Sheet2!A1:C10, Sheet3!A1:C10)
```

### With Different Column Counts

Arrays with different widths are padded with #N/A:
```
=VSTACK(A1:B5, A10:D15)
```

### Practical Examples

Append summary row:
```
=VSTACK(A1:C10, HSTACK("Total", "", SUM(C1:C10)))
```

Union of filtered results:
```
=VSTACK(
  FILTER(A1:C100, B1:B100 = "East"),
  FILTER(A1:C100, B1:B100 = "West")
)
```

Combine with transformation:
```
=VSTACK(
  HSTACK(A1:A10, "Source1"),
  HSTACK(B1:B10, "Source2")
)
```

## TAKE

Extract rows and/or columns from start or end of array.

### Syntax

```
=TAKE(array, [rows], [columns])
```

### Parameters

- Positive numbers: Take from start
- Negative numbers: Take from end
- Omit or 0: Take all

### Row Examples

First 5 rows:
```
=TAKE(A1:D100, 5)
```

Last 5 rows:
```
=TAKE(A1:D100, -5)
```

First and last (combine with VSTACK):
```
=VSTACK(TAKE(A1:D100, 3), TAKE(A1:D100, -3))
```

### Column Examples

First 2 columns:
```
=TAKE(A1:D100, , 2)
```

Last column:
```
=TAKE(A1:D100, , -1)
```

### Combined Row and Column

Top-left corner (5 rows, 2 columns):
```
=TAKE(A1:D100, 5, 2)
```

Bottom-right corner:
```
=TAKE(A1:D100, -5, -2)
```

Top-right corner:
```
=TAKE(A1:D100, 5, -2)
```

### Practical Examples

Top N by value:
```
=TAKE(SORT(A1:D100, 3, -1), 10)
```

Preview data:
```
=TAKE(A:D, 20)
```

Extract last entry:
```
=TAKE(FILTER(A1:D100, A1:A100 <> ""), -1)
```

## DROP

Remove rows and/or columns from start or end of array.

### Syntax

```
=DROP(array, [rows], [columns])
```

### Parameters

- Positive numbers: Drop from start
- Negative numbers: Drop from end

### Row Examples

Remove header row:
```
=DROP(A1:D100, 1)
```

Remove last row:
```
=DROP(A1:D100, -1)
```

Remove first and last:
```
=DROP(DROP(A1:D100, 1), -1)
```

### Column Examples

Remove first column:
```
=DROP(A1:D100, , 1)
```

Remove last 2 columns:
```
=DROP(A1:D100, , -2)
```

### Combined

Remove header and first column:
```
=DROP(A1:D100, 1, 1)
```

### Practical Examples

Skip header in calculations:
```
=SUM(DROP(A1:A100, 1))
```

Remove totals row:
```
=DROP(A1:D101, , -1)
```

Process data portion only:
```
=SORT(DROP(A1:D100, 1), 2)
```

## CHOOSEROWS

Select specific rows from array by index.

### Syntax

```
=CHOOSEROWS(array, row_num1, [row_num2], ...)
```

### Parameters

- Positive indices count from start (1 = first row)
- Negative indices count from end (-1 = last row)

### Basic Examples

Select specific rows:
```
=CHOOSEROWS(A1:D100, 1, 5, 10, 20)
```

Select last 3 rows:
```
=CHOOSEROWS(A1:D100, -1, -2, -3)
```

Reorder rows:
```
=CHOOSEROWS(A1:D10, 3, 1, 2)
```

Reverse row order:
```
=CHOOSEROWS(A1:D5, -1, -2, -3, -4, -5)
```

### Dynamic Row Selection

Using SEQUENCE:
```
=CHOOSEROWS(A1:D100, SEQUENCE(5))
```

Every other row:
```
=CHOOSEROWS(A1:D100, SEQUENCE(50, 1, 1, 2))
```

Random sample of rows:
```
=CHOOSEROWS(A1:D100, SORTBY(SEQUENCE(100), RANDARRAY(100)))
```

### Practical Examples

Header + specific rows:
```
=VSTACK(
  TAKE(A1:D100, 1),
  CHOOSEROWS(A1:D100, 5, 10, 15)
)
```

Select rows matching criteria (with helper):
```
=LET(
  data, A2:D100,
  criteria, B2:B100 > 1000,
  matches, FILTER(SEQUENCE(ROWS(data)), criteria),
  CHOOSEROWS(data, matches)
)
```

## CHOOSECOLS

Select specific columns from array by index.

### Syntax

```
=CHOOSECOLS(array, col_num1, [col_num2], ...)
```

### Parameters

- Positive indices count from start
- Negative indices count from end

### Basic Examples

Select columns 1, 3, 4:
```
=CHOOSECOLS(A1:E100, 1, 3, 4)
```

Reorder columns:
```
=CHOOSECOLS(A1:E100, 5, 1, 2, 3, 4)
```

Last column first:
```
=CHOOSECOLS(A1:E100, -1, 1, 2, 3)
```

### Practical Examples

Remove middle column:
```
=CHOOSECOLS(A1:E100, 1, 2, 4, 5)
```

Duplicate column:
```
=CHOOSECOLS(A1:D100, 1, 2, 2, 3, 4)
```

Select by column names (with MATCH):
```
=LET(
  headers, A1:E1,
  data, A1:E100,
  wanted, {"Name", "Total", "Status"},
  cols, MAP(wanted, LAMBDA(h, MATCH(h, headers, 0))),
  CHOOSECOLS(data, cols)
)
```

## TOCOL

Flatten array into single column.

### Syntax

```
=TOCOL(array, [ignore], [scan_by_column])
```

### Parameters

- ignore: 0 = keep all (default), 1 = ignore blanks, 2 = ignore errors, 3 = ignore both
- scan_by_column: FALSE = row by row (default), TRUE = column by column

### Basic Examples

Flatten to column:
```
=TOCOL(A1:D10)
```

Ignore blanks:
```
=TOCOL(A1:D10, 1)
```

Ignore errors:
```
=TOCOL(A1:D10, 2)
```

Ignore blanks and errors:
```
=TOCOL(A1:D10, 3)
```

### Scan Order

Row by row (default):
```
=TOCOL(A1:C2)
```
From A1,B1,C1,A2,B2,C2 to single column.

Column by column:
```
=TOCOL(A1:C2, , TRUE)
```
From A1,A2,B1,B2,C1,C2 to single column.

### Practical Examples

Unique values from 2D range:
```
=UNIQUE(TOCOL(A1:D10, 1))
```

Count non-empty in 2D:
```
=COUNTA(TOCOL(A1:D10, 1))
```

Sum all numbers in mixed range:
```
=SUM(TOCOL(A1:D10, 2))
```

## TOROW

Flatten array into single row.

### Syntax

```
=TOROW(array, [ignore], [scan_by_column])
```

### Parameters

Same as TOCOL.

### Examples

Flatten to row:
```
=TOROW(A1:D10)
```

Ignore blanks:
```
=TOROW(A1:D10, 1)
```

Column by column order:
```
=TOROW(A1:D10, , TRUE)
```

### Practical Examples

Create comma-separated list:
```
=TEXTJOIN(", ", TRUE, TOROW(A1:C10, 1))
```

Horizontal unique values:
```
=UNIQUE(TOROW(A1:D10, 1))
```

## WRAPROWS

Convert 1D array into 2D array by filling rows.

### Syntax

```
=WRAPROWS(vector, wrap_count, [pad_with])
```

### Parameters

- vector: 1D array to wrap
- wrap_count: Values per row
- pad_with: Value for incomplete last row (default #N/A)

### Examples

12 values into 4 columns:
```
=WRAPROWS(A1:A12, 4)
```

Result: 3 rows x 4 columns

Pad with empty:
```
=WRAPROWS(A1:A10, 4, "")
```

Pad with zero:
```
=WRAPROWS(A1:A10, 4, 0)
```

### Practical Examples

Create calendar layout:
```
=WRAPROWS(SEQUENCE(28), 7, "")
```

Display products in grid:
```
=WRAPROWS(A1:A20, 5, "-")
```

Reshape for display:
```
=WRAPROWS(TOCOL(A1:E10), 10)
```

## WRAPCOLS

Convert 1D array into 2D array by filling columns.

### Syntax

```
=WRAPCOLS(vector, wrap_count, [pad_with])
```

### Parameters

- vector: 1D array to wrap
- wrap_count: Values per column
- pad_with: Value for incomplete last column (default #N/A)

### Examples

12 values, 4 per column:
```
=WRAPCOLS(A1:A12, 4)
```

Result: 4 rows x 3 columns

### Practical Examples

Phone book style layout:
```
=WRAPCOLS(SORT(A1:A100), 25, "")
```

Multi-column list:
```
=WRAPCOLS(UNIQUE(A1:A100), 20)
```

## EXPAND

Resize array to specified dimensions with padding.

### Syntax

```
=EXPAND(array, rows, [columns], [pad_with])
```

### Parameters

- rows: Target row count (cannot be less than current)
- columns: Target column count (cannot be less than current)
- pad_with: Value for new cells (default #N/A)

### Examples

Expand to 10x5:
```
=EXPAND(A1:B3, 10, 5)
```

Expand with zeros:
```
=EXPAND(A1:B3, 10, 5, 0)
```

Expand with empty:
```
=EXPAND(A1:B3, 10, 5, "")
```

### Practical Examples

Pad arrays for HSTACK:
```
=HSTACK(
  EXPAND(A1:A5, 10, , 0),
  EXPAND(B1:B10, 10, , 0)
)
```

Create fixed-size output:
```
=EXPAND(FILTER(A1:C10, B1:B10 > 0), 10, 3, "")
```

Ensure minimum dimensions:
```
=EXPAND(A1:B2, MAX(ROWS(A1:B2), 5), MAX(COLUMNS(A1:B2), 5))
```

## Combining Functions

### Create Paginated View

```
=LET(
  data, A2:D100,
  page_size, 10,
  page_num, E1,
  start_row, (page_num - 1) * page_size + 1,
  CHOOSEROWS(data, SEQUENCE(page_size, 1, start_row))
)
```

### Transpose and Reshape

```
=WRAPROWS(TOCOL(TRANSPOSE(A1:E10)), 5)
```

### Dynamic Column Selection

```
=LET(
  data, A1:J100,
  cols_to_show, {1, 3, 5, 7},
  CHOOSECOLS(data, cols_to_show)
)
```

### Split and Rejoin

```
=VSTACK(
  TAKE(A1:D100, 50),
  {"---", "---", "---", "---"},
  DROP(A1:D100, 50)
)
```

### Create Matrix from Vectors

```
=LET(
  row_labels, A2:A10,
  col_labels, B1:E1,
  values, B2:E10,
  VSTACK(
    HSTACK("", col_labels),
    HSTACK(row_labels, values)
  )
)
```

## Error Handling

### Handle Mismatched Dimensions

```
=IFERROR(HSTACK(A1:A5, B1:B10), "")
```

### Safe TAKE/DROP

```
=LET(
  data, A1:D100,
  n, 5,
  actual_rows, ROWS(data),
  safe_n, MIN(n, actual_rows),
  TAKE(data, safe_n)
)
```

### Handle Empty Results

```
=LET(
  result, FILTER(A1:D100, B1:B100 > 1000, ""),
  IF(result = "", "No data", result)
)
```
