# LAMBDA Functions Reference

Complete reference for Excel's LAMBDA ecosystem including helper functions.

## LAMBDA

Create custom functions without VBA or macros.

### Syntax

```
=LAMBDA([parameter1, parameter2, ...], calculation)
```

### Inline Usage

Call immediately by appending arguments:
```
=LAMBDA(x, x^2)(5)                              // Returns 25
=LAMBDA(a, b, a + b)(10, 20)                    // Returns 30
=LAMBDA(text, UPPER(LEFT(text, 1)) & LOWER(MID(text, 2, 999)))("hELLO")  // Returns "Hello"
```

### Named LAMBDA (Reusable Functions)

1. Open Name Manager: Formulas > Name Manager
2. Click "New"
3. Name: Your function name (e.g., `COMPOUND`)
4. Refers to: `=LAMBDA(principal, rate, years, principal * (1 + rate) ^ years)`
5. Click OK

Usage:
```
=COMPOUND(1000, 0.05, 10)                       // Returns 1628.89
```

### Parameters

- Up to 253 parameters allowed
- Parameters are positional
- No default values (use ISOMITTED for optional behavior)
- Names must be valid identifiers

### Optional Parameters

Use ISOMITTED to check if parameter was provided:
```
=LAMBDA(value, [precision],
  LET(
    p, IF(ISOMITTED(precision), 2, precision),
    ROUND(value, p)
  )
)
```

### Recursive LAMBDA

LAMBDA can call itself for recursive operations. Must be named first.

Factorial example (name as `FACTORIAL`):
```
=LAMBDA(n,
  IF(n <= 1, 1, n * FACTORIAL(n - 1))
)
```

Fibonacci (name as `FIB`):
```
=LAMBDA(n,
  IF(n <= 2, 1, FIB(n-1) + FIB(n-2))
)
```

## ISOMITTED

Check if optional LAMBDA parameter was provided.

### Syntax

```
=ISOMITTED(argument)
```

### Returns

- TRUE if argument was not provided
- FALSE if argument was provided (including empty string or 0)

### Example

```
=LAMBDA(required, [optional1], [optional2],
  LET(
    opt1, IF(ISOMITTED(optional1), "default1", optional1),
    opt2, IF(ISOMITTED(optional2), "default2", optional2),
    CONCAT(required, "-", opt1, "-", opt2)
  )
)
```

## MAP

Apply a LAMBDA function to each element of one or more arrays.

### Syntax

```
=MAP(array1, [array2, ...], LAMBDA(param1, [param2, ...], calculation))
```

### Single Array

Transform each element:
```
=MAP(A1:A10, LAMBDA(x, x * 2))                  // Double each value
=MAP(A1:A10, LAMBDA(x, x^2))                    // Square each value
=MAP(A1:A10, LAMBDA(x, IF(x > 0, x, 0)))        // Replace negatives with 0
=MAP(A1:A10, LAMBDA(x, UPPER(x)))               // Uppercase each text
```

### Multiple Arrays

Combine corresponding elements:
```
=MAP(A1:A10, B1:B10, LAMBDA(a, b, a * b))       // Multiply pairs
=MAP(A1:A10, B1:B10, LAMBDA(a, b, a & "-" & b)) // Concatenate pairs
=MAP(A1:A10, B1:B10, C1:C10, LAMBDA(a, b, c, a + b + c))  // Sum triplets
```

### With Conditional Logic

```
=MAP(A1:A10, B1:B10, LAMBDA(price, qty,
  LET(
    subtotal, price * qty,
    IF(subtotal > 100, subtotal * 0.9, subtotal)
  )
))
```

### Nested MAP

Apply to 2D array element by element:
```
=MAP(A1:C10, LAMBDA(cell, IF(ISNUMBER(cell), cell * 1.1, cell)))
```

## REDUCE

Accumulate array values into a single result.

### Syntax

```
=REDUCE(initial_value, array, LAMBDA(accumulator, value, calculation))
```

### Parameters

- initial_value: Starting value for accumulator
- array: Values to process
- LAMBDA with exactly 2 parameters:
  - accumulator: Running result
  - value: Current array element

### Basic Examples

Sum (equivalent to SUM):
```
=REDUCE(0, A1:A10, LAMBDA(acc, val, acc + val))
```

Product:
```
=REDUCE(1, A1:A10, LAMBDA(acc, val, acc * val))
```

Maximum (equivalent to MAX):
```
=REDUCE(-9E307, A1:A10, LAMBDA(acc, val, IF(val > acc, val, acc)))
```

Concatenate all:
```
=REDUCE("", A1:A10, LAMBDA(acc, val, acc & val))
```

Concatenate with delimiter:
```
=REDUCE("", A1:A10, LAMBDA(acc, val,
  IF(acc = "", val, acc & ", " & val)
))
```

### Advanced Examples

Count matching criteria:
```
=REDUCE(0, A1:A10, LAMBDA(acc, val,
  acc + IF(val > 100, 1, 0)
))
```

Running product with condition:
```
=REDUCE(1, A1:A10, LAMBDA(acc, val,
  IF(val > 0, acc * val, acc)
))
```

Build array of unique values:
```
=REDUCE("", A1:A100, LAMBDA(acc, val,
  IF(ISERROR(FIND(val, acc)), acc & "|" & val, acc)
))
```

## SCAN

Like REDUCE but returns array showing accumulator at each step.

### Syntax

```
=SCAN(initial_value, array, LAMBDA(accumulator, value, calculation))
```

### Basic Examples

Running total:
```
=SCAN(0, A1:A10, LAMBDA(acc, val, acc + val))
```

Running product:
```
=SCAN(1, A1:A10, LAMBDA(acc, val, acc * val))
```

Running maximum:
```
=SCAN(-9E307, A1:A10, LAMBDA(acc, val, MAX(acc, val)))
```

Running count:
```
=SCAN(0, A1:A10, LAMBDA(acc, val, acc + 1))
```

### Advanced Examples

Running average (needs row number):
```
=LET(
  data, A1:A10,
  n, ROWS(data),
  sums, SCAN(0, data, LAMBDA(a, v, a + v)),
  counts, SEQUENCE(n),
  sums / counts
)
```

Running percentage of total:
```
=LET(
  data, A1:A10,
  total, SUM(data),
  running, SCAN(0, data, LAMBDA(a, v, a + v)),
  running / total
)
```

## MAKEARRAY

Generate array using custom logic for each cell position.

### Syntax

```
=MAKEARRAY(rows, columns, LAMBDA(row, col, calculation))
```

### Parameters

- rows: Number of rows to generate
- columns: Number of columns to generate
- LAMBDA with exactly 2 parameters:
  - row: Current row number (1-based)
  - col: Current column number (1-based)

### Basic Examples

Multiplication table:
```
=MAKEARRAY(10, 10, LAMBDA(r, c, r * c))
```

Identity matrix:
```
=MAKEARRAY(5, 5, LAMBDA(r, c, IF(r = c, 1, 0)))
```

Sequential numbers:
```
=MAKEARRAY(5, 4, LAMBDA(r, c, (r - 1) * 4 + c))
```

### Advanced Examples

Custom pattern:
```
=MAKEARRAY(5, 5, LAMBDA(r, c,
  IF(r = c, "X",
    IF(r + c = 6, "O", "-")
  )
))
```

Distance matrix:
```
=MAKEARRAY(5, 5, LAMBDA(r, c, ABS(r - c)))
```

Random values in range:
```
=MAKEARRAY(10, 5, LAMBDA(r, c, RANDBETWEEN(1, 100)))
```

Checkerboard:
```
=MAKEARRAY(8, 8, LAMBDA(r, c, IF(MOD(r + c, 2) = 0, "B", "W")))
```

## BYROW

Apply LAMBDA to each row, returning column of results.

### Syntax

```
=BYROW(array, LAMBDA(row, calculation))
```

### Examples

Sum each row:
```
=BYROW(A1:D10, LAMBDA(row, SUM(row)))
```

Average each row:
```
=BYROW(A1:D10, LAMBDA(row, AVERAGE(row)))
```

Max of each row:
```
=BYROW(A1:D10, LAMBDA(row, MAX(row)))
```

Count non-empty per row:
```
=BYROW(A1:D10, LAMBDA(row, COUNTA(row)))
```

Concatenate row values:
```
=BYROW(A1:D10, LAMBDA(row, TEXTJOIN("-", TRUE, row)))
```

First non-empty in row:
```
=BYROW(A1:D10, LAMBDA(row,
  INDEX(row, 1, MATCH(TRUE, row <> "", 0))
))
```

### Complex Row Operations

Row passes validation:
```
=BYROW(A1:D10, LAMBDA(row,
  AND(
    SUM(row) > 0,
    COUNTA(row) = COLUMNS(row),
    MAX(row) < 1000
  )
))
```

Custom row score:
```
=BYROW(A1:D10, LAMBDA(row,
  LET(
    avg, AVERAGE(row),
    mx, MAX(row),
    mn, MIN(row),
    avg * 0.5 + mx * 0.3 + mn * 0.2
  )
))
```

## BYCOL

Apply LAMBDA to each column, returning row of results.

### Syntax

```
=BYCOL(array, LAMBDA(column, calculation))
```

### Examples

Sum each column:
```
=BYCOL(A1:D10, LAMBDA(col, SUM(col)))
```

Average each column:
```
=BYCOL(A1:D10, LAMBDA(col, AVERAGE(col)))
```

Standard deviation per column:
```
=BYCOL(A1:D10, LAMBDA(col, STDEV.S(col)))
```

Count unique per column:
```
=BYCOL(A1:D10, LAMBDA(col, COUNTA(UNIQUE(col))))
```

### Column Statistics Row

Generate statistics for each column:
```
=VSTACK(
  BYCOL(A2:D100, LAMBDA(c, SUM(c))),
  BYCOL(A2:D100, LAMBDA(c, AVERAGE(c))),
  BYCOL(A2:D100, LAMBDA(c, MIN(c))),
  BYCOL(A2:D100, LAMBDA(c, MAX(c)))
)
```

## Combining LAMBDA Functions

### MAP + REDUCE

Count elements meeting condition:
```
=REDUCE(0, MAP(A1:A100, LAMBDA(x, IF(x > 50, 1, 0))), LAMBDA(a, v, a + v))
```

### BYROW + VSTACK

Process rows and combine results:
```
=LET(
  data, A1:D10,
  processed, BYROW(data, LAMBDA(row, SUM(row))),
  VSTACK(data, TRANSPOSE(processed))
)
```

### MAKEARRAY + MAP

Generate then transform:
```
=MAP(
  MAKEARRAY(5, 5, LAMBDA(r, c, r * c)),
  LAMBDA(x, x^2)
)
```

### Nested BYROW

Process 2D structure:
```
=BYROW(A1:D10, LAMBDA(row,
  REDUCE(0, row, LAMBDA(acc, val,
    acc + IF(val > 0, val, 0)
  ))
))
```

## Error Handling in LAMBDA

Wrap calculations with error handling:
```
=LAMBDA(a, b,
  IFERROR(a / b, 0)
)(A1, B1)
```

Named with error handling:
```
=LAMBDA(lookup_val, data_range,
  LET(
    result, XLOOKUP(lookup_val, INDEX(data_range,,1), INDEX(data_range,,2)),
    IFERROR(result, "Not Found")
  )
)
```

## Performance Considerations

- LAMBDA functions have overhead; avoid for simple operations
- Use LET inside LAMBDA to cache repeated calculations
- Prefer built-in functions when available (SUM vs REDUCE for summing)
- Limit recursion depth to avoid stack overflow
- Test with small datasets before applying to large ranges
