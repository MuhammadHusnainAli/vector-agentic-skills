---
name: excel-formulas
description: Write error-free Excel formulas — syntax rules, cell references, math, logical, lookup (VLOOKUP, INDEX/MATCH, XLOOKUP), text, date/time and conditional aggregation (SUMIFS, COUNTIFS) with error handling. Use when the user asks for an Excel or spreadsheet formula, a calculation in a workbook, or help fixing #REF!, #VALUE!, #N/A or #NAME? errors.
metadata:
  category: productivity
  version: "1.0.0"
---

# XLSX Formulas

Standard Excel formula writing skill covering syntax, functions, error handling, and common patterns.

## Overview

This skill provides guidance for writing error-free Excel formulas with proper syntax and best practices. Use when creating spreadsheet calculations, data analysis formulas, or any formula-based operations in Excel.

## What's Covered

| Topic | Description |
|-------|-------------|
| Syntax Rules | Equal sign, parentheses, separators, cell references |
| Validation | Pre-flight checklist before outputting formulas |
| Error Handling | Common errors and prevention strategies |
| Function Categories | Math, Logical, Lookup, Text, Date/Time, Statistical |
| Formula Patterns | Templates for common calculations |

## Function Categories Quick Reference

| Category | Key Functions | Use Cases |
|----------|---------------|-----------|
| Math | SUM, AVERAGE, ROUND, ABS | Arithmetic operations |
| Logical | IF, AND, OR, IFS, SWITCH | Conditional logic |
| Lookup | VLOOKUP, INDEX, MATCH, XLOOKUP | Data retrieval |
| Text | CONCAT, LEFT, RIGHT, MID, TRIM | String manipulation |
| Date/Time | TODAY, NOW, DATE, DATEDIF | Date calculations |
| Statistical | COUNT, COUNTIF, SUMIF, SUMIFS | Conditional aggregation |
| Dynamic Array | FILTER, SORT, UNIQUE, SEQUENCE | Modern spill formulas |

## Common Formula Patterns

**Aggregation:**
```
=SUM(range)
=AVERAGE(range)
=COUNT(range)
```

**Conditional:**
```
=IF(condition, true_value, false_value)
=IFS(cond1, val1, cond2, val2, TRUE, default)
```

**Lookup:**
```
=XLOOKUP(lookup, search_range, return_range)
=INDEX(range, MATCH(value, lookup_range, 0))
```

**Conditional Sum/Count:**
```
=SUMIF(range, criteria, sum_range)
=SUMIFS(sum_range, range1, criteria1, range2, criteria2)
=COUNTIF(range, criteria)
```

**Error Handling:**
```
=IFERROR(formula, fallback_value)
=IFNA(lookup_formula, "Not Found")
```

## Validation Checklist

Before outputting any formula:

- Starts with `=`
- Parentheses are balanced
- Function names are English
- Arguments use commas (not semicolons)
- Cell references are valid (A1 notation)
- No circular references
- Data types match function expectations

## Error Prevention

| Error | Cause | Solution |
|-------|-------|----------|
| #REF! | Invalid reference | Verify cell exists |
| #VALUE! | Type mismatch | Check data types |
| #DIV/0! | Division by zero | Use IFERROR wrapper |
| #N/A | Not found | Add fallback value |
| #NAME? | Unknown function | Check spelling |

## Scripts

Lint formulas before giving them to the user:

```bash
python scripts/check_formula.py '=IFERROR(VLOOKUP(A2,Data!A:C,3,FALSE),"Not found")'
python scripts/check_formula.py --file formulas.txt --json
```

Reports missing `=`, unbalanced parentheses, unterminated strings, smart quotes, nesting over 64 levels, unknown function names (#NAME? risk), volatile functions and VLOOKUP/HLOOKUP calls without an explicit match mode. Exit code `1` means at least one formula has errors.

## Skill Files

| File | Content |
|------|---------|
| [formulas.md](references/formulas.md) | Complete syntax rules, templates, and patterns |
| [functions-reference.md](references/functions-reference.md) | Detailed function documentation by category |
| [examples.md](references/examples.md) | Production-ready formula examples |

## When to Use

Use this skill when:
- Writing Excel formulas for calculations
- Creating lookup or conditional logic
- Aggregating data with criteria
- Handling formula errors
- Building formula templates

For advanced features (LAMBDA, LET, GROUPBY), see the `excel-advanced-formulas` skill.
