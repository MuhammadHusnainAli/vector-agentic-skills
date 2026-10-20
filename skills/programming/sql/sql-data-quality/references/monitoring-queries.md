# Data Quality Monitoring Queries

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
