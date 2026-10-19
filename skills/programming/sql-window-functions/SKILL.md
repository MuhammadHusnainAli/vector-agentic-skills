---
name: sql-window-functions
description: Write window/analytic SQL — ROW_NUMBER, RANK, DENSE_RANK, NTILE, LAG/LEAD, FIRST_VALUE/LAST_VALUE, running totals, moving averages and frame clauses (ROWS/RANGE). Use for rankings, top-N per group, period-over-period comparisons, cumulative sums or deduplication with window functions.
metadata:
  category: programming
  version: "1.0.0"
---

# SQL Window Functions

Master window functions for advanced analytics, rankings, running calculations, and row comparisons.

## Trigger Conditions

Activate this skill when the user:
- Needs rankings (rank, row number, dense rank)
- Asks for running totals or moving averages
- Wants to compare rows (previous/next values)
- Needs percentiles or distributions
- Asks about PARTITION BY or OVER clause
- Wants to calculate differences between rows

## Window Function Fundamentals

### Basic Syntax

```sql
function_name(arguments) OVER (
    [PARTITION BY partition_columns]
    [ORDER BY sort_columns]
    [frame_clause]
)
```

### Components

| Component | Purpose | Required |
|-----------|---------|----------|
| PARTITION BY | Groups rows for calculation (like GROUP BY but keeps all rows) | Optional |
| ORDER BY | Determines row order for calculation | Depends on function |
| Frame | Defines which rows to include in calculation | Optional (has default) |

### Key Difference from GROUP BY

```sql
GROUP BY:  Many rows -> One row per group (aggregates collapse)
OVER:      Many rows -> Same rows, adds calculated column (no collapse)
```

## Ranking Functions

### ROW_NUMBER()

Assigns unique sequential numbers.

```sql
SELECT 
    name,
    department,
    salary,
    ROW_NUMBER() OVER (ORDER BY salary DESC) AS rank_overall,
    ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC) AS rank_in_dept
FROM employees;
```

Output:
```
name    | department | salary  | rank_overall | rank_in_dept
--------|------------|---------|--------------|-------------
Alice   | Sales      | 90000   | 1            | 1
Bob     | Sales      | 85000   | 2            | 2
Carol   | IT         | 80000   | 3            | 1
```

### RANK()

Assigns same rank for ties, skips numbers.

```sql
SELECT 
    name,
    score,
    RANK() OVER (ORDER BY score DESC) AS rank
FROM players;
```

Output:
```
name    | score | rank
--------|-------|-----
Alice   | 100   | 1
Bob     | 100   | 1
Carol   | 95    | 3    -- Skips 2
```

### DENSE_RANK()

Assigns same rank for ties, no gaps.

```sql
SELECT 
    name,
    score,
    DENSE_RANK() OVER (ORDER BY score DESC) AS rank
FROM players;
```

Output:
```
name    | score | rank
--------|-------|-----
Alice   | 100   | 1
Bob     | 100   | 1
Carol   | 95    | 2    -- No skip
```

### NTILE(n)

Divides rows into n equal buckets.

```sql
SELECT 
    name,
    salary,
    NTILE(4) OVER (ORDER BY salary) AS quartile
FROM employees;
```

### PERCENT_RANK() and CUME_DIST()

```sql
SELECT 
    name,
    salary,
    PERCENT_RANK() OVER (ORDER BY salary) AS percentile_rank,
    CUME_DIST() OVER (ORDER BY salary) AS cumulative_dist
FROM employees;
```

## Value Functions

### LAG() and LEAD()

Access previous/next row values.

```sql
SELECT 
    date,
    sales,
    LAG(sales, 1) OVER (ORDER BY date) AS previous_day,
    LEAD(sales, 1) OVER (ORDER BY date) AS next_day,
    sales - LAG(sales, 1) OVER (ORDER BY date) AS day_over_day_change
FROM daily_sales;
```

With default value:
```sql
LAG(sales, 1, 0) OVER (ORDER BY date)  -- Returns 0 if no previous row
```

### FIRST_VALUE() and LAST_VALUE()

Get first/last value in frame.

```sql
SELECT 
    date,
    price,
    FIRST_VALUE(price) OVER (
        PARTITION BY product_id 
        ORDER BY date
        ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
    ) AS first_price,
    LAST_VALUE(price) OVER (
        PARTITION BY product_id 
        ORDER BY date
        ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
    ) AS last_price
FROM prices;
```

### NTH_VALUE()

Get value at specific position.

```sql
SELECT 
    name,
    salary,
    NTH_VALUE(name, 2) OVER (
        PARTITION BY department 
        ORDER BY salary DESC
        ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
    ) AS second_highest_paid
FROM employees;
```

## Aggregate Window Functions

### Running Total

```sql
SELECT 
    date,
    amount,
    SUM(amount) OVER (ORDER BY date) AS running_total
FROM transactions;
```

### Running Average

```sql
SELECT 
    date,
    amount,
    AVG(amount) OVER (ORDER BY date) AS running_avg
FROM transactions;
```

### Cumulative Count

```sql
SELECT 
    date,
    COUNT(*) OVER (ORDER BY date) AS cumulative_count
FROM events;
```

### Partition Aggregates

```sql
SELECT 
    department,
    employee_name,
    salary,
    SUM(salary) OVER (PARTITION BY department) AS dept_total,
    AVG(salary) OVER (PARTITION BY department) AS dept_avg,
    salary / SUM(salary) OVER (PARTITION BY department) * 100 AS pct_of_dept
FROM employees;
```

## Frame Specifications

### Frame Syntax

```sql
ROWS BETWEEN frame_start AND frame_end
RANGE BETWEEN frame_start AND frame_end
GROUPS BETWEEN frame_start AND frame_end
```

### Frame Boundaries

| Boundary | Meaning |
|----------|---------|
| UNBOUNDED PRECEDING | First row of partition |
| n PRECEDING | n rows before current |
| CURRENT ROW | Current row |
| n FOLLOWING | n rows after current |
| UNBOUNDED FOLLOWING | Last row of partition |

### ROWS vs RANGE vs GROUPS

**ROWS**: Physical row count
```sql
ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
```

**RANGE**: Logical value range (requires ORDER BY)
```sql
RANGE BETWEEN INTERVAL '7 days' PRECEDING AND CURRENT ROW
```

**GROUPS**: Groups of peers (rows with same ORDER BY value)
```sql
GROUPS BETWEEN 1 PRECEDING AND 1 FOLLOWING
```

### Default Frame

When ORDER BY is specified:
```sql
RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
```

When no ORDER BY:
```sql
RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
```

### Moving Averages

3-day moving average:
```sql
SELECT 
    date,
    amount,
    AVG(amount) OVER (
        ORDER BY date 
        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ) AS moving_avg_3
FROM daily_sales;
```

7-day centered moving average:
```sql
SELECT 
    date,
    amount,
    AVG(amount) OVER (
        ORDER BY date 
        ROWS BETWEEN 3 PRECEDING AND 3 FOLLOWING
    ) AS centered_avg_7
FROM daily_sales;
```

## Common Patterns

### Top N Per Group

```sql
WITH ranked AS (
    SELECT 
        *,
        ROW_NUMBER() OVER (PARTITION BY category ORDER BY sales DESC) AS rn
    FROM products
)
SELECT * FROM ranked WHERE rn <= 3;
```

### Percentage of Total

```sql
SELECT 
    product,
    sales,
    ROUND(100.0 * sales / SUM(sales) OVER (), 2) AS pct_of_total,
    ROUND(100.0 * sales / SUM(sales) OVER (PARTITION BY category), 2) AS pct_of_category
FROM products;
```

### Gap Detection

Find gaps in sequential IDs:
```sql
SELECT 
    id,
    LEAD(id) OVER (ORDER BY id) AS next_id,
    LEAD(id) OVER (ORDER BY id) - id - 1 AS gap_size
FROM records
HAVING gap_size > 0;
```

### Island Detection

Group consecutive values:
```sql
WITH numbered AS (
    SELECT 
        *,
        ROW_NUMBER() OVER (ORDER BY date) AS rn,
        ROW_NUMBER() OVER (PARTITION BY status ORDER BY date) AS status_rn
    FROM events
)
SELECT 
    *,
    rn - status_rn AS island_id
FROM numbered;
```

### Year-Over-Year Comparison

```sql
SELECT 
    year,
    month,
    revenue,
    LAG(revenue, 12) OVER (ORDER BY year, month) AS revenue_last_year,
    revenue - LAG(revenue, 12) OVER (ORDER BY year, month) AS yoy_change,
    ROUND(100.0 * (revenue - LAG(revenue, 12) OVER (ORDER BY year, month)) / 
          NULLIF(LAG(revenue, 12) OVER (ORDER BY year, month), 0), 2) AS yoy_pct
FROM monthly_revenue;
```

### Running Balance

```sql
SELECT 
    transaction_date,
    description,
    CASE WHEN type = 'credit' THEN amount ELSE -amount END AS signed_amount,
    SUM(CASE WHEN type = 'credit' THEN amount ELSE -amount END) 
        OVER (ORDER BY transaction_date, id) AS balance
FROM transactions
WHERE account_id = 123;
```

### Sessionization

Group events into sessions (30-min gap):
```sql
WITH event_gaps AS (
    SELECT 
        *,
        EXTRACT(EPOCH FROM (timestamp - LAG(timestamp) OVER (PARTITION BY user_id ORDER BY timestamp))) / 60 AS minutes_since_last
    FROM events
),
session_starts AS (
    SELECT 
        *,
        CASE WHEN minutes_since_last > 30 OR minutes_since_last IS NULL THEN 1 ELSE 0 END AS is_new_session
    FROM event_gaps
)
SELECT 
    *,
    SUM(is_new_session) OVER (PARTITION BY user_id ORDER BY timestamp) AS session_id
FROM session_starts;
```

## Named Windows

Define reusable window specifications:

```sql
SELECT 
    date,
    amount,
    SUM(amount) OVER w AS running_total,
    AVG(amount) OVER w AS running_avg,
    COUNT(*) OVER w AS running_count
FROM transactions
WINDOW w AS (ORDER BY date ROWS UNBOUNDED PRECEDING);
```

Multiple named windows:
```sql
SELECT 
    department,
    employee,
    salary,
    SUM(salary) OVER dept AS dept_total,
    AVG(salary) OVER dept AS dept_avg,
    RANK() OVER (PARTITION BY department ORDER BY salary DESC) AS dept_rank
FROM employees
WINDOW dept AS (PARTITION BY department);
```

## Performance Considerations

1. **Index on ORDER BY columns**: Speeds up window calculations
2. **PARTITION BY reduces memory**: Smaller partitions = less memory
3. **Avoid large frames**: `ROWS BETWEEN 1000 PRECEDING` can be slow
4. **Named windows**: Can improve readability but not necessarily performance
5. **Materialize intermediate results**: CTEs can help complex window chains

## Additional Resources

| File | Content |
|------|---------|
| [examples.md](references/examples.md) | Advanced window function examples |
