# Data Quality Report Queries

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
