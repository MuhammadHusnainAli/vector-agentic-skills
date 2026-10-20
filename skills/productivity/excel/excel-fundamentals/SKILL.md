---
name: excel-fundamentals
description: Excel workbook fundamentals — cells, ranges, absolute/relative references, named ranges, number formats, conditional formatting, sheets and views, sorting, filtering, tables and keyboard shortcuts. Use when the user asks how to organise, format, sort, filter or navigate spreadsheet data rather than write a formula.
metadata:
  category: productivity
  subcategory: excel
  version: "1.0.0"
---

# XLSX Fundamentals

Foundational Excel knowledge for working with spreadsheets, cells, formatting, and data organization.

## Workbook Fundamentals

### Terminology

| Term | Definition |
|------|------------|
| Workbook | The Excel file (.xlsx) containing one or more sheets |
| Worksheet | A single sheet/tab within a workbook |
| Cell | Intersection of a row and column (e.g., A1) |
| Range | A group of cells (e.g., A1:C10) |
| Active Cell | Currently selected cell |

### Limits

| Element | Maximum |
|---------|---------|
| Rows per sheet | 1,048,576 |
| Columns per sheet | 16,384 (A to XFD) |
| Sheets per workbook | Limited by memory |
| Characters per cell | 32,767 |
| Cell width | 255 characters |

### File Formats

| Format | Extension | Description |
|--------|-----------|-------------|
| Excel Workbook | .xlsx | Default format, XML-based |
| Excel Macro-Enabled | .xlsm | Contains VBA macros |
| Excel Binary | .xlsb | Faster for large files |
| Excel 97-2003 | .xls | Legacy format |
| CSV | .csv | Comma-separated values, text only |
| Tab-delimited | .txt | Tab-separated values |

## Cell Basics

### A1 Notation

Cells are addressed by column letter + row number:

```
A1   = Column A, Row 1
B5   = Column B, Row 5
AA1  = Column AA, Row 1
XFD1048576 = Last cell in sheet
```

### Reference Types

| Type | Syntax | Behavior When Copied |
|------|--------|---------------------|
| Relative | A1 | Adjusts to new position |
| Absolute | $A$1 | Never changes |
| Mixed (column) | $A1 | Column fixed, row adjusts |
| Mixed (row) | A$1 | Row fixed, column adjusts |

### Range Notation

| Notation | Meaning |
|----------|---------|
| A1:C10 | Rectangle from A1 to C10 |
| A:A | Entire column A |
| 1:1 | Entire row 1 |
| A:C | Columns A through C |
| 1:10 | Rows 1 through 10 |
| A1:A10,C1:C10 | Non-contiguous ranges |

### Named Ranges

Give meaningful names to cell ranges:

| Name | Refers To | Usage |
|------|-----------|-------|
| SalesData | =Sheet1!$A$1:$D$100 | =SUM(SalesData) |
| TaxRate | =$B$1 | =A1*TaxRate |
| Headers | =Sheet1!$A$1:$D$1 | Reference in formulas |

Rules for names:
- Start with letter or underscore
- No spaces (use underscores)
- Max 255 characters
- Cannot match cell references (e.g., "A1" invalid)

## Data Types

### Automatic Type Detection

Excel automatically detects data types when entering:

| Input | Detected As | Stored Value |
|-------|-------------|--------------|
| 123 | Number | 123 |
| 123.45 | Number | 123.45 |
| Hello | Text | "Hello" |
| 1/15/2024 | Date | 45306 (serial number) |
| 10:30 AM | Time | 0.4375 (fraction of day) |
| TRUE | Boolean | TRUE |
| =A1+B1 | Formula | Calculated result |

### Force Text Entry

Prefix with apostrophe to force text:
```
'123     -> Stored as text "123"
'01234   -> Preserves leading zero
'=SUM    -> Displays as text, not formula
```

### Date Serial Numbers

Excel stores dates as numbers:
- January 1, 1900 = 1
- January 1, 2024 = 45292
- Date + Time = Integer + Decimal

### Error Values

| Error | Meaning |
|-------|---------|
| #VALUE! | Wrong data type |
| #REF! | Invalid reference |
| #NAME? | Unrecognized name |
| #DIV/0! | Division by zero |
| #N/A | Value not available |
| #NUM! | Invalid number |
| #NULL! | Invalid intersection |
| #SPILL! | Spill range blocked |
| #CALC! | Calculation error |

## Formatting Essentials

### Number Formats

| Category | Example | Display |
|----------|---------|---------|
| General | 1234.5 | 1234.5 |
| Number | 1234.50 | 1,234.50 |
| Currency | $1234.50 | $1,234.50 |
| Accounting | $1234.50 | $ 1,234.50 (aligned) |
| Percentage | 0.15 | 15% |
| Fraction | 0.5 | 1/2 |
| Scientific | 1234.5 | 1.23E+03 |
| Date | 45292 | 1/1/2024 |
| Time | 0.5 | 12:00:00 PM |

### Common Format Codes

| Code | Meaning | Example |
|------|---------|---------|
| 0 | Display digit or zero | 00.00 -> 01.50 |
| # | Display digit or nothing | #.## -> 1.5 |
| , | Thousands separator | #,##0 -> 1,234 |
| . | Decimal point | 0.00 -> 1.50 |
| % | Percentage | 0% -> 15% |
| $ | Currency symbol | $#,##0 -> $1,234 |
| @ | Text placeholder | @ "units" -> "5 units" |

### Cell Alignment

| Horizontal | Vertical |
|------------|----------|
| Left | Top |
| Center | Middle |
| Right | Bottom |
| Fill | Justify |
| Justify | Distributed |

### Text Control

| Option | Effect |
|--------|--------|
| Wrap Text | Display on multiple lines within cell |
| Shrink to Fit | Reduce font size to fit |
| Merge Cells | Combine cells into one |
| Orientation | Rotate text angle |
| Indent | Add left margin |

### Borders

| Style | Usage |
|-------|-------|
| Thin | Standard cell borders |
| Medium | Section dividers |
| Thick | Outer boundaries |
| Double | Totals/summaries |
| Dashed | Draft/temporary |

### Fill Colors

- Solid fills for emphasis
- Pattern fills for printing
- Gradient fills for visual appeal
- Use consistent color scheme

## Data Organization

### Sorting

Single column:
- Select data range
- Sort A-Z (ascending) or Z-A (descending)

Multi-level sort:
1. Primary: Sort by first column
2. Secondary: Then by second column
3. Tertiary: Then by third column

Sort options:
- Case sensitive
- Sort left to right (by rows)
- Custom sort order (months, days)

### Filtering (AutoFilter)

Enable filter dropdowns on headers:
- Select header row
- Enable AutoFilter
- Click dropdown to filter

Filter types:
| Type | Examples |
|------|----------|
| Text | Contains, Begins with, Ends with |
| Number | Greater than, Between, Top 10 |
| Date | Today, This month, Before, After |
| Color | By cell color or font color |

### Tables

Convert range to table for:
- Automatic filter buttons
- Structured references ([@Column])
- Auto-expanding formulas
- Built-in styles
- Total row with functions

Create table:
1. Select data with headers
2. Insert > Table
3. Confirm range has headers

### Data Validation

Restrict cell input:

| Type | Restricts To |
|------|--------------|
| Whole number | Integers only |
| Decimal | Numbers with decimals |
| List | Dropdown selection |
| Date | Date range |
| Time | Time range |
| Text length | Character count |
| Custom | Formula-based rule |

## View and Layout

### Freeze Panes

Keep rows/columns visible while scrolling:

| Option | Freezes |
|--------|---------|
| Freeze Top Row | Row 1 |
| Freeze First Column | Column A |
| Freeze Panes | Above and left of active cell |

Common patterns:
- Freeze row 1 for headers
- Freeze column A for labels
- Freeze A1:B3 for both headers and labels

### Split View

Divide window into panes:
- Each pane scrolls independently
- Useful for comparing distant parts of sheet
- Drag split bars to resize

### Hide/Show

Rows and columns:
- Right-click > Hide
- Select surrounding > Right-click > Unhide

Sheets:
- Right-click tab > Hide
- Right-click tab > Unhide

### Print Setup

| Setting | Options |
|---------|---------|
| Print Area | Define specific range |
| Page Orientation | Portrait or Landscape |
| Scaling | Fit to page, percentage |
| Margins | Normal, Wide, Narrow, Custom |
| Headers/Footers | Page numbers, dates, file name |
| Gridlines | Print cell borders |
| Row/Column Headings | Print A, B, C and 1, 2, 3 |

Print titles:
- Rows to repeat at top
- Columns to repeat at left

## Keyboard Shortcuts Quick Reference

| Action | Windows | Mac |
|--------|---------|-----|
| Select all | Ctrl+A | Cmd+A |
| Copy | Ctrl+C | Cmd+C |
| Paste | Ctrl+V | Cmd+V |
| Cut | Ctrl+X | Cmd+X |
| Undo | Ctrl+Z | Cmd+Z |
| Redo | Ctrl+Y | Cmd+Shift+Z |
| Find | Ctrl+F | Cmd+F |
| Replace | Ctrl+H | Cmd+H |
| Go to cell | Ctrl+G | Cmd+G |
| Bold | Ctrl+B | Cmd+B |
| Italic | Ctrl+I | Cmd+I |
| Underline | Ctrl+U | Cmd+U |
| New line in cell | Alt+Enter | Option+Enter |
| Fill down | Ctrl+D | Cmd+D |
| Fill right | Ctrl+R | Cmd+R |
| Insert row/column | Ctrl++ | Cmd++ |
| Delete row/column | Ctrl+- | Cmd+- |
| Select to end | Ctrl+Shift+End | Cmd+Shift+End |
| Select column | Ctrl+Space | Ctrl+Space |
| Select row | Shift+Space | Shift+Space |

## Scripts

Inspect a workbook the user shares before answering questions about it:

```bash
python scripts/inspect_workbook.py report.xlsx
python scripts/inspect_workbook.py report.xlsx --sheet Data --sample 10
```

It reports sheets (including hidden ones), used ranges, formula and error counts, frozen panes, merged cells, Excel tables, data validation, conditional formatting, defined names (flagging broken `#REF!` names), external links and macros, using only the Python standard library.

## Additional Resources

- For cells and ranges, see [cells-and-ranges.md](references/cells-and-ranges.md)
- For formatting and styles, see [formatting-and-styles.md](references/formatting-and-styles.md)
- For sorting, filtering, and tables, see [sorting-filtering-tables.md](references/sorting-filtering-tables.md)
- For sheets and views, see [sheets-and-views.md](references/sheets-and-views.md)
- For a structural report of any .xlsx, run [scripts/inspect_workbook.py](scripts/inspect_workbook.py)
