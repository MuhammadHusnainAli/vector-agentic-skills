---
name: sql-debugger
description: Debug failing SQL or queries returning wrong results — interpret error messages, find causes of duplicates, missing rows, NULL surprises, fan-out joins and type mismatches, and produce a fixed query. Use when SQL throws an error, returns unexpected results, or the user asks why a query is failing.
metadata:
  category: programming
  version: "1.0.0"
---

# SQL Debugger

Diagnose and fix SQL queries that produce errors, incorrect results, or unexpected behavior.

## Trigger Conditions

Activate this skill when the user:
- Has a SQL error message they don't understand
- Says "this query returns wrong results"
- Gets unexpected NULL values or empty results
- Has a query that worked before but now fails
- Needs help troubleshooting data inconsistencies

## Debugging Workflow

```
1. REPRODUCE   -> Understand the exact issue
2. ISOLATE     -> Break query into testable parts
3. IDENTIFY    -> Find the root cause
4. FIX         -> Apply the correction
5. VERIFY      -> Confirm the fix works
6. PREVENT     -> Add safeguards if needed
```

## Error Categories

### Category 1: Syntax Errors

**Characteristics**: Query won't execute at all

**Common Causes**:
- Typos in keywords or identifiers
- Missing or extra commas, parentheses
- Wrong clause order
- Incorrect quotes

### Category 2: Runtime Errors

**Characteristics**: Query starts but fails during execution

**Common Causes**:
- Division by zero
- Type conversion failures
- Constraint violations
- NULL in unexpected places

### Category 3: Logic Errors

**Characteristics**: Query runs but produces wrong results

**Common Causes**:
- Incorrect JOIN conditions
- Wrong filter logic
- Missing GROUP BY columns
- Aggregate function misuse

### Category 4: Data Errors

**Characteristics**: Query logic is correct but data isn't

**Common Causes**:
- Duplicate records
- Missing related data
- Data type mismatches
- Encoding issues

## Common Error Messages and Solutions

### PostgreSQL Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `column "X" does not exist` | Typo or wrong table alias | Check column name and alias |
| `column "X" must appear in GROUP BY` | Non-aggregated column in SELECT | Add to GROUP BY or aggregate |
| `operator does not exist: X = Y` | Type mismatch | Cast types appropriately |
| `null value in column "X" violates not-null constraint` | INSERT/UPDATE with NULL | Provide value or change constraint |
| `duplicate key value violates unique constraint` | Inserting duplicate | Handle with ON CONFLICT |
| `relation "X" does not exist` | Table doesn't exist | Check table name and schema |
| `permission denied for table "X"` | User lacks privileges | GRANT appropriate permissions |
| `deadlock detected` | Concurrent conflicting locks | Retry transaction |
| `division by zero` | Dividing by zero value | Add NULLIF or CASE check |
| `invalid input syntax for type X` | Type conversion failure | Validate or cast input |

### MySQL Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Unknown column 'X'` | Column doesn't exist | Verify column name |
| `Column 'X' in field list is ambiguous` | Column exists in multiple tables | Add table alias |
| `Duplicate entry 'X' for key` | Unique constraint violation | Use INSERT IGNORE or ON DUPLICATE KEY |
| `Data truncated for column` | Value too large | Increase column size or truncate |
| `Incorrect datetime value` | Invalid date format | Use correct format |
| `Expression #N of SELECT list is not in GROUP BY` | Non-aggregated column | Add to GROUP BY |

### SQL Server Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Invalid column name 'X'` | Column doesn't exist | Check spelling |
| `Ambiguous column name 'X'` | Multiple tables have column | Add table prefix |
| `Divide by zero error` | Division by zero | Add NULLIF check |
| `String or binary data would be truncated` | Value too long | Check length or truncate |
| `Conversion failed` | Type conversion error | Validate data |
| `Subquery returned more than 1 value` | Subquery returns multiple rows | Use IN or TOP 1 |

## Debugging Techniques

### Technique 1: Simplify the Query

Start with the most basic version and add complexity:

Original (broken):
```sql
SELECT c.name, COUNT(o.id), SUM(oi.quantity * oi.price)
FROM customers c
LEFT JOIN orders o ON c.id = o.customer_id
LEFT JOIN order_items oi ON o.id = oi.order_id
WHERE o.status = 'completed'
GROUP BY c.name;
```

Step 1 - Test base table:
```sql
SELECT * FROM customers LIMIT 5;
```

Step 2 - Add first join:
```sql
SELECT c.id, c.name, o.id AS order_id
FROM customers c
LEFT JOIN orders o ON c.id = o.customer_id
LIMIT 10;
```

Step 3 - Add filter:
```sql
SELECT c.id, c.name, o.id AS order_id
FROM customers c
LEFT JOIN orders o ON c.id = o.customer_id
WHERE o.status = 'completed' OR o.id IS NULL
LIMIT 10;
```

### Technique 2: Check Intermediate Results

Use CTEs to inspect each step:

```sql
WITH step1 AS (
    SELECT * FROM orders WHERE status = 'completed'
),
step2 AS (
    SELECT customer_id, COUNT(*) AS order_count
    FROM step1
    GROUP BY customer_id
)
SELECT * FROM step2 WHERE order_count > 1;
```

### Technique 3: Compare Expected vs Actual

```sql
WITH expected AS (
    SELECT 'Customer A' AS name, 5 AS expected_orders
    UNION ALL
    SELECT 'Customer B', 3
),
actual AS (
    SELECT c.name, COUNT(o.id) AS actual_orders
    FROM customers c
    JOIN orders o ON c.id = o.customer_id
    GROUP BY c.name
)
SELECT 
    e.name,
    e.expected_orders,
    COALESCE(a.actual_orders, 0) AS actual_orders,
    e.expected_orders - COALESCE(a.actual_orders, 0) AS difference
FROM expected e
LEFT JOIN actual a ON e.name = a.name
WHERE e.expected_orders != COALESCE(a.actual_orders, 0);
```

### Technique 4: Add Diagnostic Columns

```sql
SELECT 
    c.id,
    c.name,
    o.id AS order_id,
    o.status,
    o.customer_id,
    CASE WHEN o.customer_id = c.id THEN 'Match' ELSE 'Mismatch' END AS join_check,
    CASE WHEN o.status = 'completed' THEN 'Included' ELSE 'Filtered' END AS filter_check
FROM customers c
LEFT JOIN orders o ON c.id = o.customer_id
WHERE c.id IN (1, 2, 3);
```

### Technique 5: Check for NULLs

```sql
SELECT 
    COUNT(*) AS total_rows,
    COUNT(column_name) AS non_null_count,
    COUNT(*) - COUNT(column_name) AS null_count,
    COUNT(*) FILTER (WHERE column_name IS NULL) AS null_check
FROM table_name;
```

### Technique 6: Validate Data Types

```sql
SELECT 
    pg_typeof(column1) AS col1_type,
    pg_typeof(column2) AS col2_type,
    column1,
    column2
FROM table_name
WHERE column1::text != column2::text
LIMIT 10;
```

### Technique 7: Check for Duplicates

```sql
SELECT column1, column2, COUNT(*)
FROM table_name
GROUP BY column1, column2
HAVING COUNT(*) > 1
ORDER BY COUNT(*) DESC;
```

## Common Logic Errors

### Error: Wrong JOIN Type

**Symptom**: Missing rows in results

Problem:
```sql
SELECT c.name, o.total
FROM customers c
JOIN orders o ON c.id = o.customer_id;
```

Fix (to include customers without orders):
```sql
SELECT c.name, COALESCE(o.total, 0) AS total
FROM customers c
LEFT JOIN orders o ON c.id = o.customer_id;
```

### Error: Filter in WHERE vs JOIN

**Symptom**: LEFT JOIN behaves like INNER JOIN

Problem:
```sql
SELECT c.name, o.total
FROM customers c
LEFT JOIN orders o ON c.id = o.customer_id
WHERE o.status = 'completed';
```

Fix:
```sql
SELECT c.name, o.total
FROM customers c
LEFT JOIN orders o ON c.id = o.customer_id AND o.status = 'completed';
```

### Error: Cartesian Product

**Symptom**: Way more rows than expected

Problem:
```sql
SELECT * FROM table_a, table_b;
```

Fix:
```sql
SELECT * FROM table_a a
JOIN table_b b ON a.id = b.a_id;
```

### Error: Double Counting with Multiple JOINs

**Symptom**: Aggregates are too high

Problem:
```sql
SELECT c.name, SUM(o.total), COUNT(p.id)
FROM customers c
JOIN orders o ON c.id = o.customer_id
JOIN payments p ON c.id = p.customer_id
GROUP BY c.name;
```

Fix:
```sql
SELECT 
    c.name,
    (SELECT SUM(total) FROM orders WHERE customer_id = c.id) AS order_total,
    (SELECT COUNT(*) FROM payments WHERE customer_id = c.id) AS payment_count
FROM customers c;
```

Or:
```sql
SELECT 
    c.name,
    o.order_total,
    p.payment_count
FROM customers c
LEFT JOIN (
    SELECT customer_id, SUM(total) AS order_total
    FROM orders GROUP BY customer_id
) o ON c.id = o.customer_id
LEFT JOIN (
    SELECT customer_id, COUNT(*) AS payment_count
    FROM payments GROUP BY customer_id
) p ON c.id = p.customer_id;
```

### Error: NULL Comparison

**Symptom**: Rows with NULL excluded unexpectedly

Problem:
```sql
SELECT * FROM users WHERE role != 'admin';
```

Fix (to include NULL roles):
```sql
SELECT * FROM users WHERE role != 'admin' OR role IS NULL;
```

Or:
```sql
SELECT * FROM users WHERE COALESCE(role, '') != 'admin';
```

### Error: String vs Number Comparison

**Symptom**: Sorting or comparison doesn't work as expected

Problem:
```sql
SELECT * FROM products ORDER BY price;
```

Check:
```sql
SELECT price, pg_typeof(price) FROM products LIMIT 1;
```

Fix:
```sql
SELECT * FROM products ORDER BY price::numeric;
```

## Output Format

When debugging a query, provide:

1. **Issue Identified**: What's wrong
2. **Root Cause**: Why it's happening
3. **Fixed Query**: Corrected version
4. **Explanation**: What was changed
5. **Verification**: How to confirm the fix

## Additional Resources

| File | Content |
|------|---------|
| [examples.md](references/examples.md) | Common debugging scenarios with solutions |
