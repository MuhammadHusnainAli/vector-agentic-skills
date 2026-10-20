# SQL Window Functions Examples

Advanced examples demonstrating window function patterns.

## Ranking Examples

### Top Products Per Category

```sql
WITH ranked_products AS (
    SELECT 
        p.category_id,
        c.name AS category_name,
        p.id AS product_id,
        p.name AS product_name,
        SUM(oi.quantity * oi.unit_price) AS revenue,
        ROW_NUMBER() OVER (
            PARTITION BY p.category_id 
            ORDER BY SUM(oi.quantity * oi.unit_price) DESC
        ) AS rank_in_category
    FROM products p
    JOIN categories c ON p.category_id = c.id
    JOIN order_items oi ON p.id = oi.product_id
    JOIN orders o ON oi.order_id = o.id
    WHERE o.status = 'completed'
      AND o.order_date >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY p.category_id, c.name, p.id, p.name
)
SELECT 
    category_name,
    product_name,
    revenue,
    rank_in_category
FROM ranked_products
WHERE rank_in_category <= 5
ORDER BY category_name, rank_in_category;
```

### Employee Salary Rankings

```sql
SELECT 
    department,
    name,
    salary,
    ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC) AS row_num,
    RANK() OVER (PARTITION BY department ORDER BY salary DESC) AS rank,
    DENSE_RANK() OVER (PARTITION BY department ORDER BY salary DESC) AS dense_rank,
    PERCENT_RANK() OVER (PARTITION BY department ORDER BY salary) AS pct_rank,
    NTILE(4) OVER (PARTITION BY department ORDER BY salary) AS quartile
FROM employees
ORDER BY department, salary DESC;
```

### Median Calculation

```sql
SELECT DISTINCT
    department,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY salary) OVER (PARTITION BY department) AS median_salary
FROM employees;
```

Or using row numbers:
```sql
WITH ranked AS (
    SELECT 
        department,
        salary,
        ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary) AS rn,
        COUNT(*) OVER (PARTITION BY department) AS cnt
    FROM employees
)
SELECT 
    department,
    AVG(salary) AS median_salary
FROM ranked
WHERE rn IN (FLOOR((cnt + 1) / 2.0), CEIL((cnt + 1) / 2.0))
GROUP BY department;
```

## Running Calculations

### Running Total with Reset

Running total that resets each month:
```sql
SELECT 
    date,
    amount,
    SUM(amount) OVER (
        PARTITION BY DATE_TRUNC('month', date)
        ORDER BY date
    ) AS monthly_running_total,
    SUM(amount) OVER (
        ORDER BY date
    ) AS all_time_running_total
FROM transactions;
```

### Running Count of Distinct Values

```sql
SELECT 
    date,
    customer_id,
    COUNT(DISTINCT customer_id) OVER (ORDER BY date) AS cumulative_customers
FROM orders;
```

Note: This doesn't work directly. Use:
```sql
WITH first_orders AS (
    SELECT 
        customer_id,
        MIN(order_date) AS first_order_date
    FROM orders
    GROUP BY customer_id
)
SELECT 
    o.date,
    COUNT(fo.customer_id) OVER (ORDER BY o.date) AS cumulative_customers
FROM (SELECT DISTINCT date FROM orders) o
LEFT JOIN first_orders fo ON fo.first_order_date <= o.date;
```

### Compound Growth Calculation

```sql
WITH monthly_growth AS (
    SELECT 
        month,
        revenue,
        LAG(revenue) OVER (ORDER BY month) AS prev_revenue,
        (revenue - LAG(revenue) OVER (ORDER BY month)) / 
            NULLIF(LAG(revenue) OVER (ORDER BY month), 0) AS growth_rate
    FROM monthly_revenue
)
SELECT 
    month,
    revenue,
    growth_rate,
    EXP(SUM(LN(1 + COALESCE(growth_rate, 0))) OVER (ORDER BY month)) - 1 AS cumulative_growth
FROM monthly_growth;
```

## Moving Calculations

### Exponential Moving Average (Approximation)

```sql
WITH ema AS (
    SELECT 
        date,
        price,
        price AS ema_10,
        ROW_NUMBER() OVER (ORDER BY date) AS rn
    FROM stock_prices
    WHERE rn = 1
    
    UNION ALL
    
    SELECT 
        sp.date,
        sp.price,
        (sp.price * (2.0 / 11) + e.ema_10 * (1 - 2.0 / 11))::numeric(10,2),
        e.rn + 1
    FROM stock_prices sp
    JOIN ema e ON sp.date = (SELECT MIN(date) FROM stock_prices WHERE date > e.date)
)
SELECT * FROM ema;
```

Simple moving average (easier):
```sql
SELECT 
    date,
    price,
    AVG(price) OVER (ORDER BY date ROWS BETWEEN 9 PRECEDING AND CURRENT ROW) AS sma_10
FROM stock_prices;
```

### Moving Sum with Date Range

7-day rolling sum:
```sql
SELECT 
    date,
    amount,
    SUM(amount) OVER (
        ORDER BY date
        RANGE BETWEEN INTERVAL '6 days' PRECEDING AND CURRENT ROW
    ) AS rolling_7day_sum
FROM daily_transactions;
```

### Moving Standard Deviation

```sql
SELECT 
    date,
    price,
    AVG(price) OVER w AS moving_avg,
    STDDEV(price) OVER w AS moving_stddev,
    (price - AVG(price) OVER w) / NULLIF(STDDEV(price) OVER w, 0) AS z_score
FROM stock_prices
WINDOW w AS (ORDER BY date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW);
```

## Row Comparison Examples

### Detect Changes

```sql
SELECT 
    id,
    status,
    updated_at,
    LAG(status) OVER (PARTITION BY user_id ORDER BY updated_at) AS previous_status,
    CASE 
        WHEN status != LAG(status) OVER (PARTITION BY user_id ORDER BY updated_at) 
        THEN 'Changed'
        ELSE 'Same'
    END AS change_indicator
FROM user_status_log;
```

### Time Between Events

```sql
SELECT 
    user_id,
    event_name,
    event_time,
    LAG(event_time) OVER (PARTITION BY user_id ORDER BY event_time) AS prev_event_time,
    event_time - LAG(event_time) OVER (PARTITION BY user_id ORDER BY event_time) AS time_since_last,
    LEAD(event_time) OVER (PARTITION BY user_id ORDER BY event_time) AS next_event_time,
    LEAD(event_time) OVER (PARTITION BY user_id ORDER BY event_time) - event_time AS time_to_next
FROM user_events;
```

### First and Last Values in Group

```sql
SELECT DISTINCT
    customer_id,
    FIRST_VALUE(order_date) OVER w AS first_order_date,
    LAST_VALUE(order_date) OVER w AS last_order_date,
    FIRST_VALUE(total) OVER w AS first_order_total,
    LAST_VALUE(total) OVER w AS last_order_total,
    COUNT(*) OVER (PARTITION BY customer_id) AS total_orders
FROM orders
WINDOW w AS (
    PARTITION BY customer_id 
    ORDER BY order_date
    ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
);
```

## Complex Analytics

### Cohort Retention

```sql
WITH user_cohorts AS (
    SELECT 
        user_id,
        DATE_TRUNC('month', MIN(event_date)) AS cohort_month
    FROM user_events
    GROUP BY user_id
),
monthly_activity AS (
    SELECT 
        uc.cohort_month,
        DATE_TRUNC('month', ue.event_date) AS activity_month,
        COUNT(DISTINCT ue.user_id) AS active_users
    FROM user_events ue
    JOIN user_cohorts uc ON ue.user_id = uc.user_id
    GROUP BY uc.cohort_month, DATE_TRUNC('month', ue.event_date)
),
cohort_sizes AS (
    SELECT 
        cohort_month,
        COUNT(DISTINCT user_id) AS cohort_size
    FROM user_cohorts
    GROUP BY cohort_month
)
SELECT 
    ma.cohort_month,
    cs.cohort_size,
    EXTRACT(MONTH FROM AGE(ma.activity_month, ma.cohort_month)) AS months_after,
    ma.active_users,
    ROUND(100.0 * ma.active_users / cs.cohort_size, 2) AS retention_pct,
    ROUND(100.0 * ma.active_users / 
        FIRST_VALUE(ma.active_users) OVER (
            PARTITION BY ma.cohort_month 
            ORDER BY ma.activity_month
        ), 2) AS retention_from_month0
FROM monthly_activity ma
JOIN cohort_sizes cs ON ma.cohort_month = cs.cohort_month
ORDER BY ma.cohort_month, ma.activity_month;
```

### Funnel Analysis with Window Functions

```sql
WITH event_sequence AS (
    SELECT 
        session_id,
        event_name,
        event_time,
        ROW_NUMBER() OVER (PARTITION BY session_id ORDER BY event_time) AS event_order,
        LEAD(event_name) OVER (PARTITION BY session_id ORDER BY event_time) AS next_event,
        LEAD(event_time) OVER (PARTITION BY session_id ORDER BY event_time) AS next_event_time
    FROM events
    WHERE event_name IN ('page_view', 'add_to_cart', 'checkout', 'purchase')
),
funnel_transitions AS (
    SELECT 
        event_name,
        next_event,
        COUNT(*) AS transitions,
        AVG(EXTRACT(EPOCH FROM (next_event_time - event_time))) AS avg_time_seconds
    FROM event_sequence
    WHERE next_event IS NOT NULL
    GROUP BY event_name, next_event
)
SELECT * FROM funnel_transitions
ORDER BY event_name, transitions DESC;
```

### Sessionization

```sql
WITH event_gaps AS (
    SELECT 
        user_id,
        event_time,
        event_name,
        LAG(event_time) OVER (PARTITION BY user_id ORDER BY event_time) AS prev_time,
        CASE 
            WHEN LAG(event_time) OVER (PARTITION BY user_id ORDER BY event_time) IS NULL THEN 1
            WHEN event_time - LAG(event_time) OVER (PARTITION BY user_id ORDER BY event_time) > INTERVAL '30 minutes' THEN 1
            ELSE 0
        END AS new_session
    FROM events
),
sessions AS (
    SELECT 
        *,
        SUM(new_session) OVER (PARTITION BY user_id ORDER BY event_time) AS session_id
    FROM event_gaps
)
SELECT 
    user_id,
    session_id,
    MIN(event_time) AS session_start,
    MAX(event_time) AS session_end,
    COUNT(*) AS event_count,
    MAX(event_time) - MIN(event_time) AS session_duration
FROM sessions
GROUP BY user_id, session_id
ORDER BY user_id, session_start;
```

### Gap and Island Detection

Find consecutive date ranges:
```sql
WITH date_groups AS (
    SELECT 
        user_id,
        activity_date,
        activity_date - (ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY activity_date) * INTERVAL '1 day') AS grp
    FROM user_activity
)
SELECT 
    user_id,
    MIN(activity_date) AS streak_start,
    MAX(activity_date) AS streak_end,
    COUNT(*) AS streak_length
FROM date_groups
GROUP BY user_id, grp
HAVING COUNT(*) >= 3
ORDER BY user_id, streak_start;
```

### Customer Lifetime Value Calculation

```sql
WITH customer_orders AS (
    SELECT 
        customer_id,
        order_date,
        total,
        ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date) AS order_num,
        SUM(total) OVER (PARTITION BY customer_id ORDER BY order_date) AS cumulative_spend,
        COUNT(*) OVER (PARTITION BY customer_id) AS total_orders,
        SUM(total) OVER (PARTITION BY customer_id) AS lifetime_value
    FROM orders
    WHERE status = 'completed'
)
SELECT 
    customer_id,
    order_date,
    total,
    order_num,
    cumulative_spend,
    lifetime_value,
    CASE 
        WHEN order_num = 1 THEN 'First Purchase'
        WHEN cumulative_spend >= lifetime_value * 0.5 AND 
             LAG(cumulative_spend) OVER (PARTITION BY customer_id ORDER BY order_date) < lifetime_value * 0.5 
        THEN '50% LTV Milestone'
        ELSE NULL
    END AS milestone
FROM customer_orders
ORDER BY customer_id, order_date;
```

### Attribution Modeling (Last Touch)

```sql
WITH touchpoints AS (
    SELECT 
        conversion_id,
        channel,
        touch_time,
        ROW_NUMBER() OVER (
            PARTITION BY conversion_id 
            ORDER BY touch_time DESC
        ) AS reverse_order
    FROM marketing_touches
)
SELECT 
    channel,
    COUNT(*) AS last_touch_conversions,
    SUM(conversion_value) AS attributed_revenue
FROM touchpoints t
JOIN conversions c ON t.conversion_id = c.id
WHERE t.reverse_order = 1
GROUP BY channel
ORDER BY attributed_revenue DESC;
```

### Inventory Movement Analysis

```sql
SELECT 
    product_id,
    transaction_date,
    transaction_type,
    quantity,
    SUM(
        CASE 
            WHEN transaction_type = 'IN' THEN quantity 
            ELSE -quantity 
        END
    ) OVER (
        PARTITION BY product_id 
        ORDER BY transaction_date, id
    ) AS running_inventory,
    MIN(
        SUM(
            CASE 
                WHEN transaction_type = 'IN' THEN quantity 
                ELSE -quantity 
            END
        ) OVER (
            PARTITION BY product_id 
            ORDER BY transaction_date, id
        )
    ) OVER (PARTITION BY product_id) AS min_inventory_level
FROM inventory_transactions
ORDER BY product_id, transaction_date;
```

### Time-Weighted Average

```sql
WITH intervals AS (
    SELECT 
        metric_name,
        value,
        timestamp AS start_time,
        LEAD(timestamp) OVER (PARTITION BY metric_name ORDER BY timestamp) AS end_time,
        LEAD(timestamp) OVER (PARTITION BY metric_name ORDER BY timestamp) - timestamp AS duration
    FROM metrics
)
SELECT 
    metric_name,
    SUM(value * EXTRACT(EPOCH FROM duration)) / SUM(EXTRACT(EPOCH FROM duration)) AS time_weighted_avg
FROM intervals
WHERE duration IS NOT NULL
GROUP BY metric_name;
```
