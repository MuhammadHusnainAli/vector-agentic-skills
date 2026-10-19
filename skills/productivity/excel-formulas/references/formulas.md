# XLSX Formula Writing

## Syntax Rules

Every formula must follow these rules:

| Rule | Requirement | Example |
|------|-------------|---------|
| Start with `=` | All formulas begin with equal sign | `=SUM(A1:A10)` |
| Balanced parentheses | Every `(` must have matching `)` | `=IF(A1>0, (B1+C1), 0)` |
| Comma separators | Use `,` not `;` for arguments | `=SUM(A1, B1, C1)` |
| English function names | Always use English names | `=SUMME` wrong, `=SUM` correct |
| Colon for ranges | Use `:` between start and end cells | `=SUM(A1:A10)` |

### Cell Reference Types

| Type | Syntax | Behavior |
|------|--------|----------|
| Relative | `A1` | Changes when copied |
| Absolute | `$A$1` | Never changes |
| Mixed (column locked) | `$A1` | Column fixed, row changes |
| Mixed (row locked) | `A$1` | Row fixed, column changes |

## Pre-Flight Validation Checklist

Before outputting any formula, verify:

```
- [ ] Starts with =
- [ ] Parentheses are balanced (count opening = count closing)
- [ ] Function names are English and correctly spelled
- [ ] Arguments separated by commas
- [ ] Cell references use valid notation (A1, not 1A)
- [ ] Column letters A-XFD, row numbers 1-1048576
- [ ] No circular references (formula doesn't reference its own cell)
- [ ] Data types match function expectations
- [ ] Ranges use colon notation (A1:B10)
- [ ] Text values wrapped in double quotes ("text")
```

## Error Types and Prevention

| Error | Cause | Prevention |
|-------|-------|------------|
| `#REF!` | Invalid cell reference | Check references exist before using |
| `#VALUE!` | Data type mismatch | Ensure numeric functions get numbers |
| `#DIV/0!` | Division by zero | Use `=IFERROR(A1/B1, 0)` |
| `#N/A` | Lookup value not found | Use XLOOKUP with if_not_found parameter |
| `#NAME?` | Unrecognized function | Check function name spelling |
| `#NUM!` | Invalid numeric value | Validate numeric inputs |
| `#NULL!` | Incorrect range intersection | Use proper range operators |
| `#SPILL!` | Spill range blocked | Clear cells in spill area |

### Error Handling Pattern

Wrap formulas with IFERROR when errors are possible:

```
=IFERROR(formula, fallback_value)
```

For specific error handling:

```
=IFNA(lookup_formula, "Not Found")
```

## Function Categories

| Category | Functions | Purpose |
|----------|-----------|---------|
| Math | SUM, AVERAGE, ROUND, ABS, MOD, POWER | Arithmetic operations |
| Logical | IF, AND, OR, NOT, IFS, SWITCH | Conditional logic |
| Lookup | VLOOKUP, HLOOKUP, INDEX, MATCH, XLOOKUP, XMATCH | Data retrieval |
| Text | CONCAT, LEFT, RIGHT, MID, TRIM, UPPER, LOWER, LEN | String manipulation |
| Date/Time | TODAY, NOW, DATE, YEAR, MONTH, DAY, DATEDIF | Date calculations |
| Statistical | COUNT, COUNTA, COUNTIF, COUNTIFS, SUMIF, SUMIFS | Conditional aggregation |
| Dynamic Array | FILTER, SORT, SORTBY, UNIQUE, SEQUENCE, RANDARRAY | Modern spill formulas |

For detailed function reference, see [functions-reference.md](functions-reference.md).

## Formula Templates

### Basic Aggregation

Sum values:
```
=SUM(range)
=SUM(A1:A100)
```

Average values:
```
=AVERAGE(range)
=AVERAGE(B1:B50)
```

Count numbers:
```
=COUNT(range)
=COUNTA(range)  // counts non-empty cells
```

### Conditional Logic

Single condition:
```
=IF(condition, value_if_true, value_if_false)
=IF(A1>100, "High", "Low")
```

Multiple conditions (modern):
```
=IFS(condition1, value1, condition2, value2, TRUE, default)
=IFS(A1>=90, "A", A1>=80, "B", A1>=70, "C", TRUE, "F")
```

Combined conditions:
```
=IF(AND(condition1, condition2), result_if_both, result_otherwise)
=IF(OR(condition1, condition2), result_if_either, result_otherwise)
```

### Conditional Aggregation

Sum with single condition:
```
=SUMIF(criteria_range, criteria, sum_range)
=SUMIF(A:A, "Product A", B:B)
```

Sum with multiple conditions:
```
=SUMIFS(sum_range, criteria_range1, criteria1, criteria_range2, criteria2)
=SUMIFS(C:C, A:A, "East", B:B, ">1000")
```

Count with conditions:
```
=COUNTIF(range, criteria)
=COUNTIFS(range1, criteria1, range2, criteria2)
```

### Lookup Patterns

Modern lookup (Excel 365/2021+):
```
=XLOOKUP(lookup_value, lookup_array, return_array, [if_not_found], [match_mode], [search_mode])
=XLOOKUP(E1, A:A, B:B, "Not Found", 0)
```

Legacy vertical lookup:
```
=VLOOKUP(lookup_value, table_array, col_index, [range_lookup])
=VLOOKUP(E1, A1:C100, 2, FALSE)
```

Flexible lookup (any direction):
```
=INDEX(return_range, MATCH(lookup_value, lookup_range, 0))
=INDEX(B:B, MATCH(E1, A:A, 0))
```

Two-dimensional lookup:
```
=INDEX(data_range, MATCH(row_lookup, row_headers, 0), MATCH(col_lookup, col_headers, 0))
```

### Text Operations

Combine text:
```
=CONCAT(text1, text2, ...)
=CONCAT(A1, " ", B1)
=A1 & " " & B1
```

Extract text:
```
=LEFT(text, num_chars)
=RIGHT(text, num_chars)
=MID(text, start_num, num_chars)
```

Clean text:
```
=TRIM(text)
=CLEAN(text)
=SUBSTITUTE(text, old_text, new_text)
```

### Date Calculations

Current date/time:
```
=TODAY()
=NOW()
```

Extract date parts:
```
=YEAR(date)
=MONTH(date)
=DAY(date)
```

Date difference:
```
=DATEDIF(start_date, end_date, "Y")  // years
=DATEDIF(start_date, end_date, "M")  // months
=DATEDIF(start_date, end_date, "D")  // days
```

Add months:
```
=EDATE(start_date, months)
=EOMONTH(start_date, months)  // end of month
```

### Dynamic Array Formulas (Excel 365/2021+)

Filter data:
```
=FILTER(array, include, [if_empty])
=FILTER(A2:C100, B2:B100>1000, "No results")
```

Sort data:
```
=SORT(array, [sort_index], [sort_order], [by_col])
=SORT(A2:C100, 2, -1)  // sort by column 2 descending
```

Unique values:
```
=UNIQUE(array, [by_col], [exactly_once])
=UNIQUE(A2:A100)
```

Generate sequence:
```
=SEQUENCE(rows, [cols], [start], [step])
=SEQUENCE(10, 1, 1, 1)  // 1 to 10
```

## Formula Construction Workflow

```
1. IDENTIFY   -> Determine what calculation is needed
2. SELECT     -> Choose appropriate function(s) from categories
3. DRAFT      -> Build formula using template patterns
4. VALIDATE   -> Run pre-flight checklist
5. PROTECT    -> Add error handling (IFERROR/IFNA) if needed
6. TEST       -> Consider edge cases (empty, zero, missing data)
```

## Common Pitfalls

| Pitfall | Wrong | Correct |
|---------|-------|---------|
| Text in numbers | `=SUM(A1, "5")` | `=SUM(A1, 5)` |
| Missing quotes | `=IF(A1=Yes, 1, 0)` | `=IF(A1="Yes", 1, 0)` |
| Wrong separator | `=SUM(A1;B1;C1)` | `=SUM(A1, B1, C1)` |
| Hardcoded values | `=A1*0.15` | `=A1*$B$1` (tax rate in B1) |
| Nested IF overuse | 10+ nested IFs | Use IFS, SWITCH, or XLOOKUP |
| VLOOKUP last column | Not found | Use INDEX/MATCH or XLOOKUP |

## Operator Precedence

Evaluated in order (highest to lowest):

1. `:` (range), ` ` (intersection), `,` (union)
2. `-` (negation)
3. `%` (percent)
4. `^` (exponentiation)
5. `*` and `/` (multiplication, division)
6. `+` and `-` (addition, subtraction)
7. `&` (concatenation)
8. `=`, `<`, `>`, `<=`, `>=`, `<>` (comparison)

Use parentheses to override precedence.

## Comparison Operators

| Operator | Meaning |
|----------|---------|
| `=` | Equal to |
| `<>` | Not equal to |
| `>` | Greater than |
| `<` | Less than |
| `>=` | Greater than or equal |
| `<=` | Less than or equal |

## Wildcard Characters (in COUNTIF, SUMIF, etc.)

| Wildcard | Matches |
|----------|---------|
| `*` | Any number of characters |
| `?` | Any single character |
| `~*` | Literal asterisk |
| `~?` | Literal question mark |

Example: `=COUNTIF(A:A, "A*")` counts cells starting with "A"

## Additional Resources

- For complete function documentation, see [functions-reference.md](functions-reference.md)
- For complex formula examples, see [examples.md](examples.md)
