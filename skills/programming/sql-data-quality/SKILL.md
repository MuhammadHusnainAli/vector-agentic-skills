---
name: sql-data-quality
description: Profile and validate data with SQL — NULL analysis, duplicate detection, referential integrity, range and format checks, outliers, constraints and cleansing queries. Use when the user wants to audit data quality, find duplicates or bad records, or add validation rules to a database.
metadata:
  category: programming
  version: "1.0.0"
---

# SQL Data Quality

Validate, cleanse, and ensure data integrity with SQL queries for NULL handling, duplicate detection, constraint validation, and data profiling.

## Trigger Conditions

Activate this skill when the user:
- Asks about data validation or quality checks
- Needs to find or handle duplicates
- Wants to check for NULL values
- Asks about constraints or data integrity
- Needs data cleansing queries
- Wants to profile data quality

## Data Quality Workflow

```
1. PROFILE     -> Understand data characteristics
2. VALIDATE    -> Check against rules/constraints
3. IDENTIFY    -> Find quality issues
4. CLEANSE     -> Fix or flag problems
5. PREVENT     -> Add constraints/triggers
6. MONITOR     -> Ongoing quality checks
```

## Data Profiling

### Column Statistics

```sql
SELECT 
    COUNT(*) AS total_rows,
    COUNT(column_name) AS non_null_count,
    COUNT(*) - COUNT(column_name) AS null_count,
    ROUND(100.0 * (COUNT(*) - COUNT(column_name)) / COUNT(*), 2) AS null_pct,
    COUNT(DISTINCT column_name) AS distinct_values,
    MIN(column_name) AS min_value,
    MAX(column_name) AS max_value,
    AVG(LENGTH(column_name::text)) AS avg_length
FROM table_name;
```

### Value Distribution

```sql
SELECT 
    column_name,
    COUNT(*) AS frequency,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS percentage
FROM table_name
GROUP BY column_name
ORDER BY frequency DESC
LIMIT 20;
```

### Data Type Validation

```sql
SELECT 
    column_name,
    COUNT(*) AS total,
    SUM(CASE WHEN column_name ~ '^[0-9]+$' THEN 1 ELSE 0 END) AS numeric_count,
    SUM(CASE WHEN column_name ~ '^[a-zA-Z]+$' THEN 1 ELSE 0 END) AS alpha_count,
    SUM(CASE WHEN column_name ~ '^[a-zA-Z0-9]+$' THEN 1 ELSE 0 END) AS alphanumeric_count
FROM table_name;
```

### Complete Data Profile

```sql
WITH column_stats AS (
    SELECT 
        'column_name' AS column_name,
        COUNT(*) AS total_rows,
        COUNT(column_name) AS non_null,
        COUNT(DISTINCT column_name) AS distinct_values,
        MIN(column_name::text) AS min_value,
        MAX(column_name::text) AS max_value
    FROM table_name
)
SELECT 
    column_name,
    total_rows,
    non_null,
    total_rows - non_null AS nulls,
    ROUND(100.0 * (total_rows - non_null) / total_rows, 2) AS null_pct,
    distinct_values,
    ROUND(100.0 * distinct_values / NULLIF(non_null, 0), 2) AS uniqueness_pct,
    min_value,
    max_value
FROM column_stats;
```

## NULL Handling

### Find NULLs

```sql
SELECT * FROM table_name
WHERE column1 IS NULL 
   OR column2 IS NULL
   OR column3 IS NULL;
```

### Count NULLs per Column

```sql
SELECT 
    SUM(CASE WHEN column1 IS NULL THEN 1 ELSE 0 END) AS column1_nulls,
    SUM(CASE WHEN column2 IS NULL THEN 1 ELSE 0 END) AS column2_nulls,
    SUM(CASE WHEN column3 IS NULL THEN 1 ELSE 0 END) AS column3_nulls,
    COUNT(*) AS total_rows
FROM table_name;
```

### NULL Patterns

```sql
SELECT 
    CASE WHEN column1 IS NULL THEN 'NULL' ELSE 'NOT NULL' END AS col1_status,
    CASE WHEN column2 IS NULL THEN 'NULL' ELSE 'NOT NULL' END AS col2_status,
    CASE WHEN column3 IS NULL THEN 'NULL' ELSE 'NOT NULL' END AS col3_status,
    COUNT(*) AS pattern_count
FROM table_name
GROUP BY 
    CASE WHEN column1 IS NULL THEN 'NULL' ELSE 'NOT NULL' END,
    CASE WHEN column2 IS NULL THEN 'NULL' ELSE 'NOT NULL' END,
    CASE WHEN column3 IS NULL THEN 'NULL' ELSE 'NOT NULL' END
ORDER BY pattern_count DESC;
```

### Replace NULLs

```sql
UPDATE table_name
SET column_name = COALESCE(column_name, 'default_value');

UPDATE table_name
SET column_name = COALESCE(column_name, (SELECT AVG(column_name) FROM table_name));
```

## Duplicate Detection

### Find Exact Duplicates

```sql
SELECT column1, column2, column3, COUNT(*) AS duplicate_count
FROM table_name
GROUP BY column1, column2, column3
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC;
```

### Find Duplicate Records with Details

```sql
WITH duplicates AS (
    SELECT 
        *,
        ROW_NUMBER() OVER (
            PARTITION BY column1, column2 
            ORDER BY id
        ) AS dup_number,
        COUNT(*) OVER (PARTITION BY column1, column2) AS total_dups
    FROM table_name
)
SELECT * FROM duplicates
WHERE total_dups > 1
ORDER BY column1, column2, dup_number;
```

### Fuzzy Duplicate Detection

```sql
SELECT 
    a.id AS id_a,
    b.id AS id_b,
    a.name AS name_a,
    b.name AS name_b,
    similarity(a.name, b.name) AS name_similarity
FROM customers a
JOIN customers b ON a.id < b.id
WHERE similarity(a.name, b.name) > 0.8
   OR LOWER(a.email) = LOWER(b.email)
ORDER BY name_similarity DESC;
```

### Remove Duplicates (Keep First)

```sql
WITH ranked AS (
    SELECT 
        *,
        ROW_NUMBER() OVER (
            PARTITION BY column1, column2 
            ORDER BY created_at ASC
        ) AS rn
    FROM table_name
)
DELETE FROM table_name
WHERE id IN (SELECT id FROM ranked WHERE rn > 1);
```

### Merge Duplicate Records

```sql
WITH duplicate_groups AS (
    SELECT 
        MIN(id) AS primary_id,
        ARRAY_AGG(id) AS all_ids,
        column1,
        column2
    FROM table_name
    GROUP BY column1, column2
    HAVING COUNT(*) > 1
)
UPDATE related_table r
SET foreign_key = dg.primary_id
FROM duplicate_groups dg
WHERE r.foreign_key = ANY(dg.all_ids)
  AND r.foreign_key != dg.primary_id;
```

## Data Validation Rules

### Email Validation

```sql
SELECT *
FROM users
WHERE email !~ '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$';
```

### Phone Number Validation

```sql
SELECT *
FROM contacts
WHERE phone !~ '^\+?[0-9]{10,15}$';
```

### Date Range Validation

```sql
SELECT *
FROM orders
WHERE order_date > CURRENT_DATE
   OR order_date < '1900-01-01'
   OR ship_date < order_date;
```

### Numeric Range Validation

```sql
SELECT *
FROM products
WHERE price < 0
   OR price > 1000000
   OR quantity < 0;
```

### Referential Integrity Check

```sql
SELECT o.*
FROM orders o
LEFT JOIN customers c ON o.customer_id = c.id
WHERE c.id IS NULL;
```

### Cross-Field Validation

```sql
SELECT *
FROM employees
WHERE end_date IS NOT NULL 
  AND end_date < start_date;

SELECT *
FROM discounts
WHERE discount_percent < 0 
   OR discount_percent > 100
   OR (discount_amount > 0 AND discount_percent > 0);
```

### Uniqueness Validation

```sql
SELECT email, COUNT(*) AS occurrences
FROM users
WHERE status = 'active'
GROUP BY email
HAVING COUNT(*) > 1;
```

## Data Cleansing

### Standardize Text

```sql
UPDATE table_name
SET 
    name = INITCAP(TRIM(name)),
    email = LOWER(TRIM(email)),
    phone = REGEXP_REPLACE(phone, '[^0-9]', '', 'g');
```

### Fix Encoding Issues

```sql
UPDATE table_name
SET column_name = REPLACE(column_name, 'Ã©', 'e')
WHERE column_name LIKE '%Ã©%';

UPDATE table_name
SET column_name = convert_from(convert_to(column_name, 'LATIN1'), 'UTF8')
WHERE column_name ~ '[^\x00-\x7F]';
```

### Standardize Dates

```sql
UPDATE table_name
SET date_column = 
    CASE 
        WHEN date_string ~ '^\d{4}-\d{2}-\d{2}$' THEN date_string::date
        WHEN date_string ~ '^\d{2}/\d{2}/\d{4}$' THEN TO_DATE(date_string, 'MM/DD/YYYY')
        WHEN date_string ~ '^\d{2}-\d{2}-\d{4}$' THEN TO_DATE(date_string, 'DD-MM-YYYY')
        ELSE NULL
    END;
```

### Remove Special Characters

```sql
UPDATE table_name
SET column_name = REGEXP_REPLACE(column_name, '[^a-zA-Z0-9\s]', '', 'g');
```

### Trim Whitespace

```sql
UPDATE table_name
SET 
    column1 = TRIM(column1),
    column2 = REGEXP_REPLACE(TRIM(column2), '\s+', ' ', 'g');
```

## Constraint Management

### Add NOT NULL Constraint

```sql
UPDATE table_name SET column_name = 'default' WHERE column_name IS NULL;
ALTER TABLE table_name ALTER COLUMN column_name SET NOT NULL;
```

### Add Check Constraint

```sql
ALTER TABLE products
ADD CONSTRAINT chk_price_positive CHECK (price >= 0);

ALTER TABLE employees
ADD CONSTRAINT chk_dates CHECK (end_date IS NULL OR end_date >= start_date);
```

### Add Unique Constraint

```sql
ALTER TABLE users
ADD CONSTRAINT uq_users_email UNIQUE (email);
```

### Add Foreign Key

```sql
ALTER TABLE orders
ADD CONSTRAINT fk_orders_customer
FOREIGN KEY (customer_id) REFERENCES customers(id);
```

## Data Quality Reports

### Comprehensive Quality Report

```sql
WITH quality_checks AS (
    SELECT 
        'Null Check' AS check_type,
        'email' AS column_name,
        COUNT(*) FILTER (WHERE email IS NULL) AS failed_count,
        COUNT(*) AS total_count
    FROM users
    
    UNION ALL
    
    SELECT 
        'Format Check',
        'email',
        COUNT(*) FILTER (WHERE email !~ '^[^@]+@[^@]+\.[^@]+$'),
        COUNT(*)
    FROM users
    
    UNION ALL
    
    SELECT 
        'Uniqueness Check',
        'email',
        COUNT(*) - COUNT(DISTINCT email),
        COUNT(*)
    FROM users
    
    UNION ALL
    
    SELECT 
        'Range Check',
        'age',
        COUNT(*) FILTER (WHERE age < 0 OR age > 150),
        COUNT(*)
    FROM users
)
SELECT 
    check_type,
    column_name,
    failed_count,
    total_count,
    ROUND(100.0 * failed_count / NULLIF(total_count, 0), 2) AS failure_rate,
    CASE 
        WHEN failed_count = 0 THEN 'PASS'
        WHEN failed_count * 100.0 / total_count < 1 THEN 'WARNING'
        ELSE 'FAIL'
    END AS status
FROM quality_checks
ORDER BY failure_rate DESC;
```

### Data Completeness Score

```sql
SELECT 
    id,
    (CASE WHEN column1 IS NOT NULL THEN 1 ELSE 0 END +
     CASE WHEN column2 IS NOT NULL THEN 1 ELSE 0 END +
     CASE WHEN column3 IS NOT NULL THEN 1 ELSE 0 END +
     CASE WHEN column4 IS NOT NULL THEN 1 ELSE 0 END +
     CASE WHEN column5 IS NOT NULL THEN 1 ELSE 0 END
    ) * 100.0 / 5 AS completeness_score
FROM table_name;
```

### Anomaly Detection

```sql
WITH stats AS (
    SELECT 
        AVG(amount) AS mean,
        STDDEV(amount) AS stddev
    FROM transactions
)
SELECT t.*
FROM transactions t, stats s
WHERE ABS(t.amount - s.mean) > 3 * s.stddev;
```

## Monitoring Queries

### Track Data Quality Over Time

```sql
INSERT INTO data_quality_log (check_date, table_name, check_name, pass_count, fail_count)
SELECT 
    CURRENT_DATE,
    'users',
    'email_format',
    COUNT(*) FILTER (WHERE email ~ '^[^@]+@[^@]+\.[^@]+$'),
    COUNT(*) FILTER (WHERE email !~ '^[^@]+@[^@]+\.[^@]+$' OR email IS NULL)
FROM users;
```

### Alert on Quality Degradation

```sql
WITH current_quality AS (
    SELECT 
        COUNT(*) FILTER (WHERE column_name IS NULL) * 100.0 / COUNT(*) AS null_rate
    FROM table_name
),
historical_avg AS (
    SELECT AVG(fail_count * 100.0 / (pass_count + fail_count)) AS avg_rate
    FROM data_quality_log
    WHERE table_name = 'table_name'
      AND check_date >= CURRENT_DATE - 30
)
SELECT 
    CASE 
        WHEN c.null_rate > h.avg_rate * 1.5 THEN 'ALERT: Quality degradation detected'
        ELSE 'OK'
    END AS status,
    c.null_rate AS current_rate,
    h.avg_rate AS historical_rate
FROM current_quality c, historical_avg h;
```

## Output Format

When performing data quality analysis:

1. **Issue Summary**: Overview of quality problems found
2. **Detailed Findings**: Specific records or patterns
3. **Root Cause**: Why the issues likely occurred
4. **Remediation**: SQL to fix the issues
5. **Prevention**: Constraints or rules to add

## Additional Resources

| File | Content |
|------|---------|
| [examples.md](references/examples.md) | Data quality scenarios and solutions |
