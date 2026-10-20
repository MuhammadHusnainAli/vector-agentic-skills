---
name: excel-advanced-formulas
description: Modern Excel 365/2021+ formulas — LAMBDA and LAMBDA helpers (MAP, REDUCE, SCAN, BYROW, BYCOL), LET, dynamic arrays (FILTER, SORT, UNIQUE, HSTACK, VSTACK, TAKE, DROP), TEXTSPLIT, REGEX functions, GROUPBY and PIVOTBY. Use when the user needs custom reusable functions, array reshaping, regex text parsing, or formulas beyond classic Excel.
metadata:
  category: productivity
  subcategory: excel
  version: "1.0.0"
---

# Advanced XLSX Formulas

Modern Excel 365/2024+ formula capabilities for custom functions, array manipulation, and advanced data processing.

## Version Requirements

| Function Group | Minimum Version |
|----------------|-----------------|
| LET | Excel 365, Excel 2021 |
| LAMBDA and helpers (MAP, REDUCE, SCAN, etc.) | Excel 365, Excel 2024 |
| Array Functions (HSTACK, TAKE, TEXTSPLIT, etc.) | Excel 365, Excel 2024 |
| GROUPBY, PIVOTBY | Excel 365 (Preview) |
| Regex Functions | Excel 365 (Preview) |

## Pre-Flight Validation Checklist

Before outputting advanced formulas, verify:

```
- [ ] Excel version supports the function (check table above)
- [ ] LAMBDA parameters use valid identifiers (letters, numbers, underscores)
- [ ] LET variable names don't conflict with cell references (avoid single letters)
- [ ] Array dimensions are compatible for operations
- [ ] Spill range has sufficient empty cells for output
- [ ] Regex patterns follow PCRE2 syntax
- [ ] Nested functions don't exceed 64 levels
```

## LAMBDA Function System

Create custom reusable functions without VBA.

### Basic LAMBDA Syntax

```
=LAMBDA([parameter1, parameter2, ...], calculation)
```

Inline usage:
```
=LAMBDA(x, x^2)(5)
```
Returns: 25

### Named LAMBDA (Reusable)

Define in Name Manager (Formulas > Name Manager):
- Name: `SQUARE`
- Refers to: `=LAMBDA(x, x^2)`

Then use anywhere:
```
=SQUARE(5)
```

### LAMBDA with Multiple Parameters

```
=LAMBDA(base, rate, years, base * (1 + rate) ^ years)
```

### Optional Parameters with ISOMITTED

```
=LAMBDA(value, [decimals],
  IF(ISOMITTED(decimals),
    ROUND(value, 2),
    ROUND(value, decimals)
  )
)
```

## LAMBDA Helper Functions

| Function | Purpose | Returns |
|----------|---------|---------|
| MAP | Apply function to each element | Array (same size) |
| REDUCE | Accumulate to single value | Single value |
| SCAN | Accumulate showing each step | Array (same size) |
| MAKEARRAY | Generate array with custom logic | New array |
| BYROW | Apply function to each row | Column array |
| BYCOL | Apply function to each column | Row array |

### MAP - Transform Each Element

```
=MAP(array, LAMBDA(x, transformation))
=MAP(A1:A10, LAMBDA(x, x * 1.1))
```

Multiple arrays:
```
=MAP(A1:A10, B1:B10, LAMBDA(a, b, a * b))
```

### REDUCE - Accumulate Values

```
=REDUCE(initial_value, array, LAMBDA(accumulator, current, operation))
=REDUCE(0, A1:A10, LAMBDA(acc, val, acc + val))
```

Product of all values:
```
=REDUCE(1, A1:A10, LAMBDA(acc, val, acc * val))
```

### SCAN - Running Accumulation

```
=SCAN(initial_value, array, LAMBDA(accumulator, current, operation))
=SCAN(0, A1:A10, LAMBDA(acc, val, acc + val))
```

Returns running total at each position.

### MAKEARRAY - Generate Custom Array

```
=MAKEARRAY(rows, cols, LAMBDA(row, col, calculation))
=MAKEARRAY(5, 5, LAMBDA(r, c, r * c))
```

Generates multiplication table.

### BYROW / BYCOL - Row/Column Operations

Sum each row:
```
=BYROW(A1:C10, LAMBDA(row, SUM(row)))
```

Max of each column:
```
=BYCOL(A1:C10, LAMBDA(col, MAX(col)))
```

## LET Function for Optimization

Define named variables within formulas to improve performance and readability.

### Basic Syntax

```
=LET(name1, value1, [name2, value2, ...], calculation)
```

### Eliminate Duplicate Calculations

Before (calculates XLOOKUP twice):
```
=IF(XLOOKUP(A1, B:B, C:C) > 100, XLOOKUP(A1, B:B, C:C) * 0.1, 0)
```

After (calculates once):
```
=LET(
  price, XLOOKUP(A1, B:B, C:C),
  IF(price > 100, price * 0.1, 0)
)
```

### Multi-Step Calculations

```
=LET(
  sales, SUM(B2:B100),
  costs, SUM(C2:C100),
  profit, sales - costs,
  margin, profit / sales,
  TEXT(margin, "0.0%")
)
```

### Variable Naming Rules

- Must start with letter
- Can contain letters, numbers, underscores
- Cannot match cell references (avoid: `A1`, `R1C1`, single letters)
- Case-insensitive

## Modern Array Functions

### Combining Arrays

HSTACK (horizontal):
```
=HSTACK(A1:A10, B1:B10, C1:C10)
```

VSTACK (vertical):
```
=VSTACK(A1:C1, A10:C10, A20:C20)
```

### Extracting Portions

TAKE (from start/end):
```
=TAKE(A1:D100, 5)           // first 5 rows
=TAKE(A1:D100, -5)          // last 5 rows
=TAKE(A1:D100, 5, 2)        // first 5 rows, first 2 cols
=TAKE(A1:D100, , -1)        // last column only
```

DROP (remove from start/end):
```
=DROP(A1:D100, 1)           // remove header row
=DROP(A1:D100, , 1)         // remove first column
=DROP(A1:D100, 1, -1)       // remove first row and last column
```

### Selecting Specific Rows/Columns

CHOOSEROWS:
```
=CHOOSEROWS(A1:D100, 1, 5, 10)       // rows 1, 5, 10
=CHOOSEROWS(A1:D100, -1, -2, -3)     // last 3 rows reversed
```

CHOOSECOLS:
```
=CHOOSECOLS(A1:D100, 4, 1, 2)        // columns D, A, B in that order
```

### Reshaping Arrays

TOCOL (flatten to column):
```
=TOCOL(A1:C10)                       // all values in one column
=TOCOL(A1:C10, 1)                    // ignore blanks
=TOCOL(A1:C10, 2)                    // ignore errors
=TOCOL(A1:C10, 3)                    // ignore blanks and errors
```

TOROW (flatten to row):
```
=TOROW(A1:C10)
```

WRAPROWS (1D to 2D by rows):
```
=WRAPROWS(A1:A12, 4)                 // 12 values into 3 rows x 4 cols
=WRAPROWS(A1:A10, 4, "-")            // pad incomplete row with "-"
```

WRAPCOLS (1D to 2D by columns):
```
=WRAPCOLS(A1:A12, 3)                 // 12 values into 3 rows x 4 cols
```

EXPAND (resize with padding):
```
=EXPAND(A1:B2, 5, 5)                 // expand to 5x5 with #N/A
=EXPAND(A1:B2, 5, 5, 0)              // expand to 5x5 with 0
```

## Advanced Text Functions

### TEXTSPLIT

Split by delimiter:
```
=TEXTSPLIT(A1, " ")                  // split by space
=TEXTSPLIT(A1, ", ")                 // split by comma-space
=TEXTSPLIT(A1, {",", ";"})           // split by comma OR semicolon
```

Split into rows and columns:
```
=TEXTSPLIT(A1, ",", ";")             // comma for cols, semicolon for rows
```

### TEXTBEFORE / TEXTAFTER

Extract portions:
```
=TEXTBEFORE("John Smith", " ")       // "John"
=TEXTAFTER("John Smith", " ")        // "Smith"
=TEXTBEFORE("a-b-c-d", "-", 2)       // "a-b" (before 2nd delimiter)
=TEXTAFTER("a-b-c-d", "-", -1)       // "d" (after last delimiter)
```

### Regex Functions (Preview)

REGEXTEST (check pattern):
```
=REGEXTEST(A1, "\d{3}-\d{4}")        // TRUE if phone pattern
=REGEXTEST(A1, "^[A-Z]")             // TRUE if starts with uppercase
```

REGEXEXTRACT (extract matches):
```
=REGEXEXTRACT(A1, "\d+")             // extract first number
=REGEXEXTRACT(A1, "\d+", 0)          // extract all numbers (array)
```

REGEXREPLACE (replace pattern):
```
=REGEXREPLACE(A1, "\s+", " ")        // normalize whitespace
=REGEXREPLACE(A1, "[^0-9]", "")      // keep only digits
```

## Aggregation Functions (Preview)

### GROUPBY

Group and aggregate data:
```
=GROUPBY(row_fields, values, function)
=GROUPBY(A2:A100, C2:C100, SUM)
```

Multiple grouping fields:
```
=GROUPBY(HSTACK(A2:A100, B2:B100), C2:C100, SUM)
```

With options:
```
=GROUPBY(A2:A100, C2:C100, SUM, 3, 0, 0, 1)
```

### PIVOTBY

Create pivot-style summary:
```
=PIVOTBY(row_fields, col_fields, values, function)
=PIVOTBY(A2:A100, B2:B100, C2:C100, SUM)
```

## IMAGE Function

Embed image from URL:
```
=IMAGE(url, [alt_text], [sizing], [height], [width])
=IMAGE("https://example.com/logo.png", "Logo", 0)
```

Sizing options:
- 0 = Fit cell, maintain aspect ratio
- 1 = Fill cell, ignore aspect ratio
- 2 = Original size
- 3 = Custom dimensions

## Formula Construction Workflow

```
1. IDENTIFY   -> Determine if standard functions suffice or advanced needed
2. OPTIMIZE   -> Use LET to cache repeated calculations
3. MODULARIZE -> Extract reusable logic into named LAMBDA
4. TRANSFORM  -> Use array functions for data reshaping
5. VALIDATE   -> Check version compatibility and spill requirements
6. DOCUMENT   -> Use meaningful LET variable names for clarity
```

## Common Patterns Quick Reference

| Task | Formula Pattern |
|------|-----------------|
| Apply function to each cell | `=MAP(range, LAMBDA(x, ...))` |
| Running total | `=SCAN(0, range, LAMBDA(a,b, a+b))` |
| Custom aggregation | `=REDUCE(init, range, LAMBDA(a,b, ...))` |
| Sum each row | `=BYROW(range, LAMBDA(r, SUM(r)))` |
| Combine arrays side-by-side | `=HSTACK(arr1, arr2)` |
| Get top N rows | `=TAKE(SORT(range, col, -1), N)` |
| Split text to columns | `=TEXTSPLIT(text, delimiter)` |
| Extract with regex | `=REGEXEXTRACT(text, pattern)` |
| Group and sum | `=GROUPBY(categories, values, SUM)` |

## Scripts

Check which Excel version a formula needs before recommending it:

```bash
python scripts/check_compat.py '=LET(x,A2:A100,SUM(FILTER(x,x>0)))'
python scripts/check_compat.py --target 2019 '=XLOOKUP(A1,B:B,C:C)'   # exit 1 if too new
```

If the user's version is older than the formula requires, offer a fallback built from functions their version has.

## Additional Resources

- For complete LAMBDA reference, see [lambda-functions.md](references/lambda-functions.md)
- For array manipulation details, see [array-manipulation.md](references/array-manipulation.md)
- For text parsing and regex, see [text-parsing.md](references/text-parsing.md)
- For complex patterns and examples, see [advanced-patterns.md](references/advanced-patterns.md)
