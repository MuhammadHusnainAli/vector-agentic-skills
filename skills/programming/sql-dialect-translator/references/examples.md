# SQL Dialect Translator Examples

Complete query translations between major database dialects.

## Example 1: Complex Report Query

### PostgreSQL (Source)

```sql
WITH monthly_sales AS (
    SELECT 
        DATE_TRUNC('month', order_date) AS month,
        customer_id,
        SUM(total) AS monthly_total
    FROM orders
    WHERE order_date >= CURRENT_DATE - INTERVAL '1 year'
      AND status = 'completed'
    GROUP BY DATE_TRUNC('month', order_date), customer_id
),
ranked AS (
    SELECT 
        month,
        customer_id,
        monthly_total,
        ROW_NUMBER() OVER (PARTITION BY month ORDER BY monthly_total DESC) AS rank
    FROM monthly_sales
)
SELECT 
    TO_CHAR(month, 'YYYY-MM') AS month,
    customer_id,
    monthly_total,
    rank
FROM ranked
WHERE rank <= 10
ORDER BY month DESC, rank;
```

### MySQL Translation

```sql
WITH monthly_sales AS (
    SELECT 
        DATE_FORMAT(order_date, '%Y-%m-01') AS month,
        customer_id,
        SUM(total) AS monthly_total
    FROM orders
    WHERE order_date >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)
      AND status = 'completed'
    GROUP BY DATE_FORMAT(order_date, '%Y-%m-01'), customer_id
),
ranked AS (
    SELECT 
        month,
        customer_id,
        monthly_total,
        ROW_NUMBER() OVER (PARTITION BY month ORDER BY monthly_total DESC) AS `rank`
    FROM monthly_sales
)
SELECT 
    DATE_FORMAT(month, '%Y-%m') AS month,
    customer_id,
    monthly_total,
    `rank`
FROM ranked
WHERE `rank` <= 10
ORDER BY month DESC, `rank`;
```

**Changes**:
- `DATE_TRUNC` -> `DATE_FORMAT` with first day of month
- `CURRENT_DATE - INTERVAL '1 year'` -> `DATE_SUB(CURDATE(), INTERVAL 1 YEAR)`
- `TO_CHAR` -> `DATE_FORMAT`
- `rank` quoted with backticks (reserved word in MySQL 8.0+)

### SQL Server Translation

```sql
WITH monthly_sales AS (
    SELECT 
        DATEFROMPARTS(YEAR(order_date), MONTH(order_date), 1) AS month,
        customer_id,
        SUM(total) AS monthly_total
    FROM orders
    WHERE order_date >= DATEADD(year, -1, GETDATE())
      AND status = 'completed'
    GROUP BY DATEFROMPARTS(YEAR(order_date), MONTH(order_date), 1), customer_id
),
ranked AS (
    SELECT 
        month,
        customer_id,
        monthly_total,
        ROW_NUMBER() OVER (PARTITION BY month ORDER BY monthly_total DESC) AS [rank]
    FROM monthly_sales
)
SELECT 
    FORMAT(month, 'yyyy-MM') AS month,
    customer_id,
    monthly_total,
    [rank]
FROM ranked
WHERE [rank] <= 10
ORDER BY month DESC, [rank];
```

**Changes**:
- `DATE_TRUNC` -> `DATEFROMPARTS(YEAR(...), MONTH(...), 1)`
- `CURRENT_DATE - INTERVAL` -> `DATEADD(year, -1, GETDATE())`
- `TO_CHAR` -> `FORMAT`
- `rank` quoted with square brackets

### Oracle Translation

```sql
WITH monthly_sales AS (
    SELECT 
        TRUNC(order_date, 'MM') AS month,
        customer_id,
        SUM(total) AS monthly_total
    FROM orders
    WHERE order_date >= ADD_MONTHS(SYSDATE, -12)
      AND status = 'completed'
    GROUP BY TRUNC(order_date, 'MM'), customer_id
),
ranked AS (
    SELECT 
        month,
        customer_id,
        monthly_total,
        ROW_NUMBER() OVER (PARTITION BY month ORDER BY monthly_total DESC) AS rnk
    FROM monthly_sales
)
SELECT 
    TO_CHAR(month, 'YYYY-MM') AS month,
    customer_id,
    monthly_total,
    rnk
FROM ranked
WHERE rnk <= 10
ORDER BY month DESC, rnk;
```

**Changes**:
- `DATE_TRUNC` -> `TRUNC(..., 'MM')`
- `CURRENT_DATE - INTERVAL '1 year'` -> `ADD_MONTHS(SYSDATE, -12)`
- `rank` renamed to `rnk` (RANK is a reserved word)

## Example 2: Upsert Operation

### PostgreSQL (Source)

```sql
INSERT INTO products (sku, name, price, updated_at)
VALUES ('ABC123', 'Widget', 29.99, CURRENT_TIMESTAMP)
ON CONFLICT (sku) 
DO UPDATE SET 
    name = EXCLUDED.name,
    price = EXCLUDED.price,
    updated_at = CURRENT_TIMESTAMP
WHERE products.price != EXCLUDED.price;
```

### MySQL Translation

```sql
INSERT INTO products (sku, name, price, updated_at)
VALUES ('ABC123', 'Widget', 29.99, CURRENT_TIMESTAMP)
ON DUPLICATE KEY UPDATE 
    name = VALUES(name),
    price = VALUES(price),
    updated_at = CURRENT_TIMESTAMP;
```

**Notes**:
- MySQL doesn't support WHERE clause in ON DUPLICATE KEY UPDATE
- MySQL 8.0.19+ supports `VALUES(col)` or alias syntax

### SQL Server Translation

```sql
MERGE INTO products AS target
USING (SELECT 'ABC123' AS sku, 'Widget' AS name, 29.99 AS price) AS source
ON target.sku = source.sku
WHEN MATCHED AND target.price != source.price THEN
    UPDATE SET 
        name = source.name,
        price = source.price,
        updated_at = GETDATE()
WHEN NOT MATCHED THEN
    INSERT (sku, name, price, updated_at)
    VALUES (source.sku, source.name, source.price, GETDATE());
```

### Oracle Translation

```sql
MERGE INTO products target
USING (SELECT 'ABC123' AS sku, 'Widget' AS name, 29.99 AS price FROM dual) source
ON (target.sku = source.sku)
WHEN MATCHED THEN
    UPDATE SET 
        target.name = source.name,
        target.price = source.price,
        target.updated_at = SYSTIMESTAMP
    WHERE target.price != source.price
WHEN NOT MATCHED THEN
    INSERT (sku, name, price, updated_at)
    VALUES (source.sku, source.name, source.price, SYSTIMESTAMP);
```

## Example 3: Window Functions with Aggregates

### PostgreSQL (Source)

```sql
SELECT 
    department,
    employee_name,
    salary,
    SUM(salary) OVER (PARTITION BY department) AS dept_total,
    salary::float / SUM(salary) OVER (PARTITION BY department) * 100 AS pct_of_dept,
    salary - AVG(salary) OVER (PARTITION BY department) AS diff_from_avg,
    STRING_AGG(employee_name, ', ' ORDER BY salary DESC) 
        OVER (PARTITION BY department) AS all_employees
FROM employees
ORDER BY department, salary DESC;
```

### MySQL Translation

```sql
SELECT 
    department,
    employee_name,
    salary,
    SUM(salary) OVER (PARTITION BY department) AS dept_total,
    salary / SUM(salary) OVER (PARTITION BY department) * 100 AS pct_of_dept,
    salary - AVG(salary) OVER (PARTITION BY department) AS diff_from_avg,
    GROUP_CONCAT(employee_name ORDER BY salary DESC SEPARATOR ', ') 
        OVER (PARTITION BY department) AS all_employees
FROM employees
ORDER BY department, salary DESC;
```

**Notes**: MySQL 8.0+ required for window functions. GROUP_CONCAT with OVER requires MySQL 8.0.14+.

### SQL Server Translation

```sql
SELECT 
    department,
    employee_name,
    salary,
    SUM(salary) OVER (PARTITION BY department) AS dept_total,
    CAST(salary AS float) / SUM(salary) OVER (PARTITION BY department) * 100 AS pct_of_dept,
    salary - AVG(CAST(salary AS float)) OVER (PARTITION BY department) AS diff_from_avg,
    STRING_AGG(employee_name, ', ') WITHIN GROUP (ORDER BY salary DESC)
        OVER (PARTITION BY department) AS all_employees
FROM employees
ORDER BY department, salary DESC;
```

**Notes**: STRING_AGG with OVER requires SQL Server 2017+.

### Oracle Translation

```sql
SELECT 
    department,
    employee_name,
    salary,
    SUM(salary) OVER (PARTITION BY department) AS dept_total,
    salary / SUM(salary) OVER (PARTITION BY department) * 100 AS pct_of_dept,
    salary - AVG(salary) OVER (PARTITION BY department) AS diff_from_avg,
    LISTAGG(employee_name, ', ') WITHIN GROUP (ORDER BY salary DESC)
        OVER (PARTITION BY department) AS all_employees
FROM employees
ORDER BY department, salary DESC;
```

## Example 4: Recursive CTE

### PostgreSQL (Source)

```sql
WITH RECURSIVE org_tree AS (
    SELECT 
        id,
        name,
        manager_id,
        1 AS level,
        name::text AS path
    FROM employees
    WHERE manager_id IS NULL
    
    UNION ALL
    
    SELECT 
        e.id,
        e.name,
        e.manager_id,
        ot.level + 1,
        ot.path || ' > ' || e.name
    FROM employees e
    JOIN org_tree ot ON e.manager_id = ot.id
)
SELECT * FROM org_tree
ORDER BY path;
```

### MySQL Translation

```sql
WITH RECURSIVE org_tree AS (
    SELECT 
        id,
        name,
        manager_id,
        1 AS level,
        CAST(name AS CHAR(1000)) AS path
    FROM employees
    WHERE manager_id IS NULL
    
    UNION ALL
    
    SELECT 
        e.id,
        e.name,
        e.manager_id,
        ot.level + 1,
        CONCAT(ot.path, ' > ', e.name)
    FROM employees e
    JOIN org_tree ot ON e.manager_id = ot.id
)
SELECT * FROM org_tree
ORDER BY path;
```

### SQL Server Translation

```sql
WITH org_tree AS (
    SELECT 
        id,
        name,
        manager_id,
        1 AS level,
        CAST(name AS VARCHAR(MAX)) AS path
    FROM employees
    WHERE manager_id IS NULL
    
    UNION ALL
    
    SELECT 
        e.id,
        e.name,
        e.manager_id,
        ot.level + 1,
        ot.path + ' > ' + e.name
    FROM employees e
    JOIN org_tree ot ON e.manager_id = ot.id
)
SELECT * FROM org_tree
ORDER BY path
OPTION (MAXRECURSION 100);
```

**Notes**: SQL Server doesn't use RECURSIVE keyword but requires OPTION (MAXRECURSION) for deep trees.

### Oracle Translation

```sql
WITH org_tree (id, name, manager_id, level, path) AS (
    SELECT 
        id,
        name,
        manager_id,
        1 AS level,
        name AS path
    FROM employees
    WHERE manager_id IS NULL
    
    UNION ALL
    
    SELECT 
        e.id,
        e.name,
        e.manager_id,
        ot.level + 1,
        ot.path || ' > ' || e.name
    FROM employees e
    JOIN org_tree ot ON e.manager_id = ot.id
)
SELECT * FROM org_tree
ORDER BY path;
```

## Example 5: JSON Operations

### PostgreSQL (Source)

```sql
SELECT 
    id,
    data->>'name' AS name,
    data->'address'->>'city' AS city,
    (data->>'age')::int AS age,
    jsonb_array_length(data->'tags') AS tag_count
FROM users
WHERE data @> '{"status": "active"}'
  AND (data->>'age')::int >= 18;
```

### MySQL Translation

```sql
SELECT 
    id,
    JSON_UNQUOTE(JSON_EXTRACT(data, '$.name')) AS name,
    JSON_UNQUOTE(JSON_EXTRACT(data, '$.address.city')) AS city,
    CAST(JSON_EXTRACT(data, '$.age') AS UNSIGNED) AS age,
    JSON_LENGTH(JSON_EXTRACT(data, '$.tags')) AS tag_count
FROM users
WHERE JSON_CONTAINS(data, '"active"', '$.status')
  AND CAST(JSON_EXTRACT(data, '$.age') AS UNSIGNED) >= 18;
```

Or with arrow syntax (MySQL 8.0+):
```sql
SELECT 
    id,
    data->>'$.name' AS name,
    data->>'$.address.city' AS city,
    CAST(data->>'$.age' AS UNSIGNED) AS age,
    JSON_LENGTH(data->'$.tags') AS tag_count
FROM users
WHERE JSON_CONTAINS(data, '"active"', '$.status')
  AND CAST(data->>'$.age' AS UNSIGNED) >= 18;
```

### SQL Server Translation

```sql
SELECT 
    id,
    JSON_VALUE(data, '$.name') AS name,
    JSON_VALUE(data, '$.address.city') AS city,
    CAST(JSON_VALUE(data, '$.age') AS int) AS age,
    (SELECT COUNT(*) FROM OPENJSON(data, '$.tags')) AS tag_count
FROM users
WHERE JSON_VALUE(data, '$.status') = 'active'
  AND CAST(JSON_VALUE(data, '$.age') AS int) >= 18;
```

## Example 6: Date Range Query

### PostgreSQL (Source)

```sql
SELECT 
    DATE_TRUNC('week', created_at) AS week,
    COUNT(*) AS signups,
    COUNT(*) FILTER (WHERE status = 'active') AS active_signups
FROM users
WHERE created_at >= DATE_TRUNC('quarter', CURRENT_DATE)
GROUP BY DATE_TRUNC('week', created_at)
ORDER BY week;
```

### MySQL Translation

```sql
SELECT 
    DATE(DATE_SUB(created_at, INTERVAL WEEKDAY(created_at) DAY)) AS week,
    COUNT(*) AS signups,
    SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active_signups
FROM users
WHERE created_at >= MAKEDATE(YEAR(CURDATE()), 1) + INTERVAL QUARTER(CURDATE())-1 QUARTER
GROUP BY DATE(DATE_SUB(created_at, INTERVAL WEEKDAY(created_at) DAY))
ORDER BY week;
```

### SQL Server Translation

```sql
SELECT 
    DATETRUNC(week, created_at) AS week,
    COUNT(*) AS signups,
    COUNT(CASE WHEN status = 'active' THEN 1 END) AS active_signups
FROM users
WHERE created_at >= DATETRUNC(quarter, GETDATE())
GROUP BY DATETRUNC(week, created_at)
ORDER BY week;
```

**Note**: DATETRUNC requires SQL Server 2022+. For earlier versions:
```sql
SELECT 
    DATEADD(week, DATEDIFF(week, 0, created_at), 0) AS week,
    COUNT(*) AS signups,
    COUNT(CASE WHEN status = 'active' THEN 1 END) AS active_signups
FROM users
WHERE created_at >= DATEADD(quarter, DATEDIFF(quarter, 0, GETDATE()), 0)
GROUP BY DATEADD(week, DATEDIFF(week, 0, created_at), 0)
ORDER BY week;
```

### Oracle Translation

```sql
SELECT 
    TRUNC(created_at, 'IW') AS week,
    COUNT(*) AS signups,
    COUNT(CASE WHEN status = 'active' THEN 1 END) AS active_signups
FROM users
WHERE created_at >= TRUNC(SYSDATE, 'Q')
GROUP BY TRUNC(created_at, 'IW')
ORDER BY week;
```

## Example 7: Full-Text Search

### PostgreSQL (Source)

```sql
SELECT 
    id,
    title,
    ts_rank(search_vector, query) AS rank
FROM articles,
     to_tsquery('english', 'database & performance') AS query
WHERE search_vector @@ query
ORDER BY rank DESC
LIMIT 20;
```

### MySQL Translation

```sql
SELECT 
    id,
    title,
    MATCH(title, content) AGAINST('database performance' IN NATURAL LANGUAGE MODE) AS relevance
FROM articles
WHERE MATCH(title, content) AGAINST('database performance' IN NATURAL LANGUAGE MODE)
ORDER BY relevance DESC
LIMIT 20;
```

**Prerequisites**: MySQL requires FULLTEXT index on (title, content).

### SQL Server Translation

```sql
SELECT TOP 20
    id,
    title,
    KEY_TBL.RANK AS rank
FROM articles
INNER JOIN CONTAINSTABLE(articles, (title, content), 'database AND performance') AS KEY_TBL
    ON articles.id = KEY_TBL.[KEY]
ORDER BY KEY_TBL.RANK DESC;
```

**Prerequisites**: SQL Server requires Full-Text Search feature enabled and catalog created.

## Quick Reference Cheat Sheet

| Feature | PostgreSQL | MySQL | SQL Server | Oracle |
|---------|------------|-------|------------|--------|
| Get current date | CURRENT_DATE | CURDATE() | CAST(GETDATE() AS DATE) | TRUNC(SYSDATE) |
| Add days | date + 7 | DATE_ADD(d, INTERVAL 7 DAY) | DATEADD(day, 7, d) | d + 7 |
| First day of month | DATE_TRUNC('month', d) | DATE_FORMAT(d, '%Y-%m-01') | DATEFROMPARTS(YEAR(d), MONTH(d), 1) | TRUNC(d, 'MM') |
| String concat | a \|\| b | CONCAT(a, b) | a + b | a \|\| b |
| ILIKE (case-insensitive) | col ILIKE '%x%' | col LIKE '%x%' | col LIKE '%x%' COLLATE... | UPPER(col) LIKE '%X%' |
| Return inserted ID | RETURNING id | LAST_INSERT_ID() | SCOPE_IDENTITY() | RETURNING id INTO |
| Generate series | generate_series(1,10) | (recursive CTE) | (recursive CTE) | CONNECT BY LEVEL |
| Random | RANDOM() | RAND() | NEWID() | DBMS_RANDOM.VALUE |
| Type cast | value::type | CAST(value AS type) | CAST(value AS type) | CAST(value AS type) |
| Boolean true | TRUE | TRUE or 1 | 1 | 1 |
| Array | ARRAY[1,2,3] | JSON_ARRAY(1,2,3) | N/A | N/A |
