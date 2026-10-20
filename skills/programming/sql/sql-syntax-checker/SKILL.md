---
name: sql-syntax-checker
description: Validate SQL syntax and structure before execution and point out errors with corrected versions, dialect-aware (PostgreSQL, MySQL, SQL Server, Oracle, SQLite). Use when the user asks to check, lint, validate or review a SQL statement, or pastes SQL that may not parse. Includes a script that parses SQL with sqlglot.
metadata:
  category: programming
  subcategory: sql
  version: "1.0.0"
---

# SQL Syntax Checker

Validate SQL syntax, identify errors, and ensure queries are structurally correct before execution.

## Trigger Conditions

Activate this skill when the user:
- Says "check this SQL", "validate my query", "is this correct"
- Pastes SQL and asks if it will work
- Gets a syntax error and needs help understanding it
- Wants to verify SQL before running on production
- Asks about SQL syntax rules

## Validation Workflow

```
1. PARSE       -> Analyze query structure
2. IDENTIFY    -> Detect the SQL dialect
3. CHECK       -> Validate against syntax rules
4. REPORT      -> List errors with line numbers
5. FIX         -> Provide corrected version
```

## Pre-Flight Checklist

Before validating any query:

```
- [ ] Identified target database dialect
- [ ] Checked for complete query (no truncation)
- [ ] Noted any placeholders or parameters
```

## Common Syntax Rules

### Universal Rules (All Dialects)

| Rule | Correct | Incorrect |
|------|---------|-----------|
| Keywords | Case-insensitive | N/A |
| Identifiers | Letters, numbers, underscores | Starting with numbers |
| String literals | Single quotes | Double quotes (most dialects) |
| Statement terminator | Semicolon | None (depends on context) |
| Comments | -- or /* */ | # (MySQL only) |

### SELECT Statement Structure

```sql
SELECT [DISTINCT | ALL]
    column_list
FROM table_reference
    [JOIN clause]
[WHERE condition]
[GROUP BY expression_list]
[HAVING condition]
[ORDER BY expression_list [ASC | DESC]]
[LIMIT count [OFFSET start]]
```

Common errors:
- Columns in SELECT not in GROUP BY (when not aggregated)
- ORDER BY position number exceeding column count
- HAVING without GROUP BY
- Missing table alias with ambiguous column names

### Clause Order Validation

```
Required order:
1. SELECT
2. FROM
3. WHERE
4. GROUP BY
5. HAVING
6. ORDER BY
7. LIMIT/OFFSET
```

## Syntax Error Patterns

### Missing or Mismatched Parentheses

Error:
```sql
SELECT * FROM users WHERE (status = 'active' AND (role = 'admin')
```

Fixed:
```sql
SELECT * FROM users WHERE (status = 'active' AND role = 'admin')
```

### Incorrect String Quotes

Error (most dialects):
```sql
SELECT * FROM users WHERE name = "John"
```

Fixed:
```sql
SELECT * FROM users WHERE name = 'John'
```

### Missing Commas in Column List

Error:
```sql
SELECT id name email FROM users
```

Fixed:
```sql
SELECT id, name, email FROM users
```

### Invalid Column Reference in ORDER BY

Error:
```sql
SELECT name, COUNT(*) FROM users GROUP BY name ORDER BY email
```

Fixed:
```sql
SELECT name, COUNT(*) FROM users GROUP BY name ORDER BY name
```

### Missing JOIN Condition

Error:
```sql
SELECT * FROM orders o JOIN customers c
```

Fixed:
```sql
SELECT * FROM orders o JOIN customers c ON o.customer_id = c.id
```

### Aggregate Without GROUP BY

Error:
```sql
SELECT department, name, COUNT(*) FROM employees
```

Fixed:
```sql
SELECT department, COUNT(*) FROM employees GROUP BY department
```

### Invalid NULL Comparison

Error:
```sql
SELECT * FROM users WHERE deleted_at = NULL
```

Fixed:
```sql
SELECT * FROM users WHERE deleted_at IS NULL
```

### Ambiguous Column Reference

Error:
```sql
SELECT id, name FROM users u JOIN orders o ON u.id = o.user_id
```

Fixed:
```sql
SELECT u.id, u.name FROM users u JOIN orders o ON u.id = o.user_id
```

## Dialect-Specific Validation

### PostgreSQL Specifics

| Feature | PostgreSQL Syntax |
|---------|-------------------|
| String concat | `'a' || 'b'` or `CONCAT('a', 'b')` |
| Case sensitivity | Identifiers lowercase unless quoted |
| Boolean | `TRUE`, `FALSE`, `'t'`, `'f'` |
| Array access | `array_col[1]` (1-indexed) |
| JSON access | `json_col->>'key'` or `json_col->'key'` |
| Type cast | `value::type` or `CAST(value AS type)` |

### MySQL Specifics

| Feature | MySQL Syntax |
|---------|--------------|
| String concat | `CONCAT('a', 'b')` |
| Identifier quotes | Backticks: \`table_name\` |
| Limit with offset | `LIMIT offset, count` or `LIMIT count OFFSET offset` |
| Auto increment | `AUTO_INCREMENT` |
| Boolean | `1`, `0`, `TRUE`, `FALSE` |

### SQL Server Specifics

| Feature | SQL Server Syntax |
|---------|-------------------|
| String concat | `'a' + 'b'` or `CONCAT('a', 'b')` |
| Identifier quotes | Square brackets: `[table_name]` |
| Top N rows | `SELECT TOP 10 *` |
| Identity | `IDENTITY(1,1)` |
| Date functions | `GETDATE()`, `DATEADD()`, `DATEDIFF()` |

### Oracle Specifics

| Feature | Oracle Syntax |
|---------|---------------|
| String concat | `'a' || 'b'` |
| Row limiting | `FETCH FIRST 10 ROWS ONLY` (12c+) |
| Sequence | `sequence_name.NEXTVAL` |
| From dual | Required for SELECT without table |
| NVL | Use `NVL(col, default)` for null handling |

### SQLite Specifics

| Feature | SQLite Syntax |
|---------|---------------|
| Auto increment | `INTEGER PRIMARY KEY` (automatic) |
| Boolean | `0` and `1` (no boolean type) |
| Type affinity | Flexible typing |
| Limit | `LIMIT count OFFSET start` |
| Date functions | `date()`, `datetime()`, `strftime()` |

## Validation Checklist

### Structure Validation

```
- [ ] All keywords spelled correctly
- [ ] Clauses in correct order
- [ ] Required clauses present (SELECT, FROM for queries)
- [ ] Parentheses balanced and matched
- [ ] All expressions complete
```

### Reference Validation

```
- [ ] All column names valid or aliased
- [ ] All table names valid or aliased
- [ ] Aliases used consistently
- [ ] No ambiguous references
- [ ] Subquery columns accessible
```

### Type Validation

```
- [ ] Comparison types compatible
- [ ] Function arguments correct type
- [ ] Literals properly quoted
- [ ] Date/time formats valid
- [ ] Numeric precision appropriate
```

### Logic Validation

```
- [ ] JOINs have ON conditions
- [ ] WHERE conditions make sense
- [ ] GROUP BY includes all non-aggregated columns
- [ ] HAVING uses aggregate functions
- [ ] No circular references
```

## Error Message Interpretation

### PostgreSQL Errors

| Error | Meaning | Solution |
|-------|---------|----------|
| `syntax error at or near "X"` | Unexpected token | Check syntax before token X |
| `column "X" does not exist` | Unknown column | Verify column name/alias |
| `relation "X" does not exist` | Unknown table | Verify table name |
| `column "X" must appear in GROUP BY` | Missing grouping | Add column to GROUP BY or aggregate |
| `operator does not exist: X` | Type mismatch | Cast types appropriately |

### MySQL Errors

| Error | Meaning | Solution |
|-------|---------|----------|
| `You have an error in your SQL syntax` | Parse error | Check near indicated position |
| `Unknown column 'X'` | Column not found | Verify column/alias |
| `Table 'X' doesn't exist` | Table not found | Verify table name |
| `Mixing of GROUP columns` | Invalid grouping | Fix GROUP BY |
| `Duplicate entry 'X' for key` | Unique violation | Handle duplicates |

### SQL Server Errors

| Error | Meaning | Solution |
|-------|---------|----------|
| `Incorrect syntax near 'X'` | Parse error | Check syntax |
| `Invalid column name 'X'` | Unknown column | Verify column |
| `Invalid object name 'X'` | Unknown table | Verify table |
| `Column 'X' is invalid in the select list` | Missing GROUP BY | Fix grouping |
| `Conversion failed` | Type error | Cast appropriately |

## Output Format

When validating SQL, provide:

1. **Status**: Valid or Invalid
2. **Errors Found**: List with line numbers
3. **Warnings**: Non-critical issues
4. **Corrected Query**: If errors found
5. **Explanation**: What was wrong and why

Example output:

```
Status: INVALID

Errors Found:
1. Line 3: Missing comma between columns
2. Line 5: Unclosed parenthesis
3. Line 7: Unknown column 'user_name' - did you mean 'username'?

Warnings:
1. SELECT * is discouraged - specify columns explicitly
2. Missing table alias may cause ambiguity with JOINs

Corrected Query:
[corrected SQL here]

Explanation:
[detailed explanation]
```

## Scripts

Run the checker before reporting a verdict, then explain its findings in the output format above:

```bash
python scripts/check_sql.py query.sql --dialect postgres   # or mysql, tsql, oracle, sqlite
echo "SELECT a, FROM t" | python scripts/check_sql.py - --dialect mysql --json
```

- Always runs structural checks: unbalanced parentheses, unterminated quotes, trailing commas, `= NULL`, UPDATE/DELETE without WHERE, `SELECT *`, implicit cartesian joins.
- If `sqlglot` is installed (`pip install sqlglot`), also parses every statement with the dialect's grammar.
- Exit code `1` means errors were found. The script cannot see the schema, so still verify table and column names yourself.

## Additional Resources

| File | Content |
|------|---------|
| [examples.md](references/examples.md) | Common syntax errors and corrections |
