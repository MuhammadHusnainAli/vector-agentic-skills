# SQL Query Explainer Examples

Complex query explanations with detailed breakdowns.

## Example 1: Customer Segmentation Query

### Query

```sql
WITH customer_metrics AS (
    SELECT 
        c.id AS customer_id,
        c.name,
        c.email,
        COUNT(DISTINCT o.id) AS order_count,
        COALESCE(SUM(o.total_amount), 0) AS lifetime_value,
        MAX(o.order_date) AS last_order_date,
        MIN(o.order_date) AS first_order_date
    FROM customers c
    LEFT JOIN orders o ON c.id = o.customer_id 
        AND o.status = 'completed'
    WHERE c.created_at >= '2023-01-01'
    GROUP BY c.id, c.name, c.email
),
segmented_customers AS (
    SELECT 
        *,
        CASE 
            WHEN lifetime_value >= 10000 THEN 'VIP'
            WHEN lifetime_value >= 5000 THEN 'Gold'
            WHEN lifetime_value >= 1000 THEN 'Silver'
            WHEN order_count > 0 THEN 'Bronze'
            ELSE 'Prospect'
        END AS segment,
        CURRENT_DATE - last_order_date AS days_since_last_order
    FROM customer_metrics
)
SELECT 
    segment,
    COUNT(*) AS customer_count,
    ROUND(AVG(lifetime_value), 2) AS avg_lifetime_value,
    ROUND(AVG(order_count), 1) AS avg_orders,
    ROUND(AVG(days_since_last_order), 0) AS avg_days_inactive
FROM segmented_customers
GROUP BY segment
ORDER BY 
    CASE segment 
        WHEN 'VIP' THEN 1 
        WHEN 'Gold' THEN 2 
        WHEN 'Silver' THEN 3 
        WHEN 'Bronze' THEN 4 
        ELSE 5 
    END;
```

### Purpose

Segments customers into tiers (VIP, Gold, Silver, Bronze, Prospect) based on their lifetime value and provides aggregate statistics for each segment.

### Step-by-Step Breakdown

**CTE 1: customer_metrics**
1. `FROM customers c LEFT JOIN orders o` - Start with all customers, attach their completed orders (LEFT JOIN keeps customers even without orders)
2. `AND o.status = 'completed'` - Only count completed orders (in JOIN condition to preserve LEFT JOIN behavior)
3. `WHERE c.created_at >= '2023-01-01'` - Only customers created in 2023 or later
4. `GROUP BY c.id, c.name, c.email` - One row per customer
5. Aggregations:
   - `COUNT(DISTINCT o.id)` - Number of orders
   - `COALESCE(SUM(o.total_amount), 0)` - Total spent (0 if no orders)
   - `MAX(o.order_date)` - Most recent order
   - `MIN(o.order_date)` - First order

**CTE 2: segmented_customers**
1. Takes all columns from customer_metrics
2. `CASE WHEN...` - Assigns segment based on lifetime value thresholds
3. `CURRENT_DATE - last_order_date` - Calculates days since last purchase

**Final Query**
1. `GROUP BY segment` - Aggregate by customer segment
2. `COUNT(*)` - Customers in each segment
3. `AVG(...)` - Average metrics per segment
4. `ORDER BY CASE...` - Custom sort order (VIP first)

### Data Flow

```
customers (all) ──┬──> LEFT JOIN with completed orders
                  │
                  ▼
          customer_metrics
          (one row per customer with aggregates)
                  │
                  ▼
          segmented_customers
          (add segment label + days inactive)
                  │
                  ▼
          Final aggregation by segment
```

### Key Concepts

- CTEs for multi-step logic
- LEFT JOIN to keep customers without orders
- COALESCE for NULL handling
- CASE expressions for categorization
- Custom ORDER BY with CASE

## Example 2: Running Balance Query

### Query

```sql
SELECT 
    t.id,
    t.transaction_date,
    t.description,
    t.type,
    t.amount,
    SUM(
        CASE 
            WHEN t.type = 'credit' THEN t.amount 
            ELSE -t.amount 
        END
    ) OVER (
        PARTITION BY t.account_id 
        ORDER BY t.transaction_date, t.id
        ROWS UNBOUNDED PRECEDING
    ) AS running_balance
FROM transactions t
WHERE t.account_id = 12345
  AND t.status = 'posted'
ORDER BY t.transaction_date, t.id;
```

### Purpose

Shows all transactions for an account with a running balance that accumulates from the first transaction to each row.

### Step-by-Step Breakdown

1. `FROM transactions t WHERE account_id = 12345 AND status = 'posted'`
   - Get all posted transactions for account 12345

2. `SELECT t.id, t.transaction_date, ...`
   - Basic transaction details

3. `CASE WHEN t.type = 'credit' THEN t.amount ELSE -t.amount END`
   - Convert debits to negative values for balance calculation

4. `SUM(...) OVER (...)`
   - Window function to calculate cumulative sum

5. `PARTITION BY t.account_id`
   - Calculate separately for each account (redundant here with WHERE, but useful in general)

6. `ORDER BY t.transaction_date, t.id`
   - Process transactions in chronological order, use ID as tiebreaker

7. `ROWS UNBOUNDED PRECEDING`
   - Sum all rows from the first row up to the current row

### Data Flow

```
Transaction   Date        Type    Amount    Running Balance
─────────────────────────────────────────────────────────
1001          2024-01-01  credit  1000.00   1000.00
1002          2024-01-05  debit   250.00    750.00
1003          2024-01-10  credit  500.00    1250.00
1004          2024-01-15  debit   100.00    1150.00
```

### Key Concepts

- Window functions with OVER clause
- Running/cumulative aggregations
- Frame specification (ROWS UNBOUNDED PRECEDING)
- CASE for conditional calculations
- Multiple ORDER BY columns

## Example 3: Hierarchical Organization Query

### Query

```sql
WITH RECURSIVE org_hierarchy AS (
    SELECT 
        id,
        name,
        title,
        manager_id,
        1 AS level,
        name AS path,
        ARRAY[id] AS ancestors
    FROM employees
    WHERE manager_id IS NULL
    
    UNION ALL
    
    SELECT 
        e.id,
        e.name,
        e.title,
        e.manager_id,
        oh.level + 1,
        oh.path || ' > ' || e.name,
        oh.ancestors || e.id
    FROM employees e
    JOIN org_hierarchy oh ON e.manager_id = oh.id
)
SELECT 
    REPEAT('  ', level - 1) || name AS name_indented,
    title,
    level,
    path
FROM org_hierarchy
ORDER BY ancestors;
```

### Purpose

Displays the entire organizational hierarchy as a tree, showing each employee's level and reporting path.

### Step-by-Step Breakdown

**Base Case (Anchor)**
```sql
SELECT ... FROM employees WHERE manager_id IS NULL
```
- Find all top-level employees (no manager = CEO/executives)
- Initialize level at 1
- Start path with just their name
- Start ancestors array with their ID

**Recursive Case**
```sql
SELECT ... FROM employees e JOIN org_hierarchy oh ON e.manager_id = oh.id
```
- Find employees whose manager is already in the result
- Increment level by 1
- Append current name to path
- Append current ID to ancestors array

**Termination**
- Recursion stops when no more employees have a manager in the current result set

**Final SELECT**
- `REPEAT('  ', level - 1)` - Indentation based on level
- `ORDER BY ancestors` - Orders by path from root, maintaining tree structure

### Data Flow

```
Iteration 0 (Base):
┌────┬───────────┬───────┬──────────────┐
│ id │ name      │ level │ ancestors    │
├────┼───────────┼───────┼──────────────┤
│ 1  │ CEO       │ 1     │ [1]          │
└────┴───────────┴───────┴──────────────┘

Iteration 1:
┌────┬───────────┬───────┬──────────────┐
│ id │ name      │ level │ ancestors    │
├────┼───────────┼───────┼──────────────┤
│ 1  │ CEO       │ 1     │ [1]          │
│ 2  │ VP Sales  │ 2     │ [1,2]        │
│ 3  │ VP Eng    │ 2     │ [1,3]        │
└────┴───────────┴───────┴──────────────┘

Final Output:
CEO
  VP Sales
    Sales Manager
      Sales Rep 1
  VP Engineering
    Dev Manager
      Developer 1
```

### Key Concepts

- Recursive CTEs for hierarchical data
- UNION ALL to combine base and recursive cases
- Array building for path tracking
- String concatenation for readable paths
- Ordered output preserving tree structure

## Example 4: Gap Analysis Query

### Query

```sql
WITH daily_sales AS (
    SELECT 
        DATE(order_date) AS sale_date,
        SUM(total_amount) AS daily_total
    FROM orders
    WHERE order_date >= '2024-01-01' 
      AND order_date < '2024-02-01'
      AND status = 'completed'
    GROUP BY DATE(order_date)
),
date_series AS (
    SELECT generate_series(
        '2024-01-01'::date,
        '2024-01-31'::date,
        '1 day'::interval
    )::date AS date
),
complete_data AS (
    SELECT 
        ds.date,
        COALESCE(s.daily_total, 0) AS daily_total,
        EXTRACT(DOW FROM ds.date) AS day_of_week,
        CASE 
            WHEN EXTRACT(DOW FROM ds.date) IN (0, 6) THEN 'Weekend'
            ELSE 'Weekday'
        END AS day_type
    FROM date_series ds
    LEFT JOIN daily_sales s ON ds.date = s.sale_date
)
SELECT 
    date,
    daily_total,
    day_type,
    AVG(daily_total) OVER (
        ORDER BY date 
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS rolling_7day_avg,
    daily_total - LAG(daily_total) OVER (ORDER BY date) AS day_over_day_change
FROM complete_data
ORDER BY date;
```

### Purpose

Analyzes daily sales for January 2024, filling in gaps for days with no sales, and calculating rolling averages and day-over-day changes.

### Step-by-Step Breakdown

**CTE 1: daily_sales**
- Aggregates orders by date for completed orders in January 2024

**CTE 2: date_series**
- `generate_series()` creates a row for every date in January
- This ensures no gaps in the output

**CTE 3: complete_data**
- LEFT JOIN ensures every date appears, even without sales
- `COALESCE(..., 0)` replaces NULL with 0 for missing days
- Extracts day of week and categorizes as weekend/weekday

**Final Query**
- `AVG(...) OVER (ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)` - 7-day rolling average
- `LAG(daily_total) OVER (ORDER BY date)` - Previous day's total for comparison

### Data Flow

```
date_series:          daily_sales:           complete_data:
2024-01-01            2024-01-01: $1000      2024-01-01: $1000
2024-01-02            2024-01-03: $1500      2024-01-02: $0 (gap filled)
2024-01-03            ...                    2024-01-03: $1500
...                                          ...
```

### Key Concepts

- generate_series for date ranges
- Gap filling with LEFT JOIN
- COALESCE for NULL replacement
- Window function frames for rolling calculations
- LAG for row comparisons

## Example 5: Deduplication with Ranking

### Query

```sql
WITH ranked_duplicates AS (
    SELECT 
        *,
        ROW_NUMBER() OVER (
            PARTITION BY email 
            ORDER BY 
                CASE WHEN email_verified THEN 0 ELSE 1 END,
                last_login_at DESC NULLS LAST,
                created_at ASC
        ) AS dup_rank
    FROM users
    WHERE status != 'deleted'
)
SELECT 
    id,
    email,
    name,
    email_verified,
    last_login_at,
    created_at,
    CASE 
        WHEN dup_rank = 1 THEN 'Keep'
        ELSE 'Duplicate'
    END AS action
FROM ranked_duplicates
ORDER BY email, dup_rank;
```

### Purpose

Identifies duplicate user accounts by email and marks which one to keep based on verification status, login recency, and creation date.

### Step-by-Step Breakdown

**CTE: ranked_duplicates**
1. `PARTITION BY email` - Group duplicates by email
2. `ORDER BY` prioritization:
   - `CASE WHEN email_verified...` - Verified accounts first (0 before 1)
   - `last_login_at DESC NULLS LAST` - Most recent login, NULLs at end
   - `created_at ASC` - Older account preferred (first created)
3. `ROW_NUMBER()` - Assigns 1 to the "best" record, 2+ to duplicates

**Final Query**
- dup_rank = 1 means "Keep" (the primary record)
- dup_rank > 1 means "Duplicate" (can be merged/deleted)

### Data Flow

```
email: john@example.com
┌────┬─────────────────┬──────────┬─────────────┬──────────┐
│ id │ email           │ verified │ last_login  │ dup_rank │
├────┼─────────────────┼──────────┼─────────────┼──────────┤
│ 42 │ john@example.com│ true     │ 2024-01-15  │ 1 (Keep) │
│ 15 │ john@example.com│ false    │ 2024-01-10  │ 2 (Dup)  │
│ 78 │ john@example.com│ false    │ NULL        │ 3 (Dup)  │
└────┴─────────────────┴──────────┴─────────────┴──────────┘
```

### Key Concepts

- ROW_NUMBER for deduplication
- Complex ORDER BY with CASE
- NULLS LAST handling
- PARTITION BY for grouping without aggregation

## Example 6: Pivot/Cross-Tab Query

### Query

```sql
SELECT 
    product_category,
    SUM(CASE WHEN sale_month = 1 THEN revenue ELSE 0 END) AS jan_revenue,
    SUM(CASE WHEN sale_month = 2 THEN revenue ELSE 0 END) AS feb_revenue,
    SUM(CASE WHEN sale_month = 3 THEN revenue ELSE 0 END) AS mar_revenue,
    SUM(CASE WHEN sale_month = 4 THEN revenue ELSE 0 END) AS apr_revenue,
    SUM(revenue) AS total_revenue,
    COUNT(DISTINCT order_id) AS total_orders
FROM (
    SELECT 
        p.category AS product_category,
        EXTRACT(MONTH FROM o.order_date) AS sale_month,
        oi.quantity * oi.unit_price AS revenue,
        o.id AS order_id
    FROM order_items oi
    JOIN orders o ON oi.order_id = o.id
    JOIN products p ON oi.product_id = p.id
    WHERE o.order_date >= '2024-01-01' 
      AND o.order_date < '2024-05-01'
      AND o.status = 'completed'
) sales_data
GROUP BY product_category
ORDER BY total_revenue DESC;
```

### Purpose

Creates a pivot table showing revenue by product category for each month, transforming rows into columns.

### Step-by-Step Breakdown

**Subquery: sales_data**
- Joins orders, order_items, and products
- Calculates revenue per line item
- Extracts month number for pivoting

**Outer Query**
- `GROUP BY product_category` - One row per category
- `SUM(CASE WHEN sale_month = N...)` - Conditional aggregation creates columns
- Each month becomes a separate column

### Data Flow

```
Raw data (rows):
┌───────────┬───────┬─────────┐
│ category  │ month │ revenue │
├───────────┼───────┼─────────┤
│ Electronics│ 1    │ 500     │
│ Electronics│ 1    │ 300     │
│ Electronics│ 2    │ 450     │
│ Clothing  │ 1     │ 200     │
└───────────┴───────┴─────────┘

Pivoted (columns):
┌───────────┬─────┬─────┬───────┐
│ category  │ Jan │ Feb │ Total │
├───────────┼─────┼─────┼───────┤
│ Electronics│ 800│ 450 │ 1250  │
│ Clothing  │ 200 │ 0   │ 200   │
└───────────┴─────┴─────┴───────┘
```

### Key Concepts

- Conditional aggregation for pivoting
- CASE expressions inside aggregate functions
- Subquery for data preparation
- Manual pivot (vs. PIVOT operator in some dialects)
