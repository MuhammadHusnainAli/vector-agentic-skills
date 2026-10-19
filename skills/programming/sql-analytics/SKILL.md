---
name: sql-analytics
description: Analytical and aggregation SQL — GROUP BY, ROLLUP, CUBE, GROUPING SETS, pivots, cohorts, funnels, retention, percentiles and statistical functions. Use when the user needs metrics, business analysis, OLAP-style summaries, or customer/revenue/product analytics in SQL.
metadata:
  category: programming
  version: "1.0.0"
---

# Analytics SQL

Advanced SQL for data analysis, aggregations, OLAP operations, metrics calculations, and business intelligence queries.

## Trigger Conditions

Activate this skill when the user:
- Needs aggregation or summary queries
- Asks for ROLLUP, CUBE, or GROUPING SETS
- Wants to pivot or unpivot data
- Needs statistical calculations
- Asks about OLAP operations
- Wants metrics or KPI calculations

## Analytics Query Patterns

### Basic Aggregation

```sql
SELECT 
    category,
    COUNT(*) AS count,
    SUM(amount) AS total,
    AVG(amount) AS average,
    MIN(amount) AS minimum,
    MAX(amount) AS maximum,
    STDDEV(amount) AS std_deviation
FROM transactions
GROUP BY category;
```

### Multi-Level Aggregation

```sql
SELECT 
    region,
    category,
    SUM(sales) AS total_sales,
    SUM(SUM(sales)) OVER (PARTITION BY region) AS region_total,
    SUM(SUM(sales)) OVER () AS grand_total,
    ROUND(100.0 * SUM(sales) / SUM(SUM(sales)) OVER (PARTITION BY region), 2) AS pct_of_region,
    ROUND(100.0 * SUM(sales) / SUM(SUM(sales)) OVER (), 2) AS pct_of_total
FROM sales
GROUP BY region, category
ORDER BY region, total_sales DESC;
```

## ROLLUP, CUBE, and GROUPING SETS

### ROLLUP

Creates subtotals from left to right:

```sql
SELECT 
    COALESCE(region, 'All Regions') AS region,
    COALESCE(category, 'All Categories') AS category,
    SUM(sales) AS total_sales
FROM sales
GROUP BY ROLLUP(region, category)
ORDER BY region NULLS LAST, category NULLS LAST;
```

Output:
```
region  | category    | total_sales
--------|-------------|------------
East    | Electronics | 50000
East    | Clothing    | 30000
East    | All Categories | 80000  -- subtotal
West    | Electronics | 45000
West    | Clothing    | 25000
West    | All Categories | 70000  -- subtotal
All Regions | All Categories | 150000  -- grand total
```

### CUBE

Creates all possible subtotal combinations:

```sql
SELECT 
    COALESCE(region, 'All') AS region,
    COALESCE(category, 'All') AS category,
    SUM(sales) AS total_sales
FROM sales
GROUP BY CUBE(region, category);
```

### GROUPING SETS

Explicit control over groupings:

```sql
SELECT 
    region,
    category,
    SUM(sales) AS total_sales
FROM sales
GROUP BY GROUPING SETS (
    (region, category),
    (region),
    (category),
    ()
);
```

### GROUPING() Function

Identify aggregation level:

```sql
SELECT 
    CASE WHEN GROUPING(region) = 1 THEN 'All Regions' ELSE region END AS region,
    CASE WHEN GROUPING(category) = 1 THEN 'All Categories' ELSE category END AS category,
    GROUPING(region) AS is_region_total,
    GROUPING(category) AS is_category_total,
    SUM(sales) AS total_sales
FROM sales
GROUP BY ROLLUP(region, category);
```

## Pivot and Unpivot

### Pivot (Rows to Columns)

Manual pivot:
```sql
SELECT 
    product_id,
    SUM(CASE WHEN month = 1 THEN sales ELSE 0 END) AS jan,
    SUM(CASE WHEN month = 2 THEN sales ELSE 0 END) AS feb,
    SUM(CASE WHEN month = 3 THEN sales ELSE 0 END) AS mar,
    SUM(CASE WHEN month = 4 THEN sales ELSE 0 END) AS apr
FROM monthly_sales
GROUP BY product_id;
```

PostgreSQL crosstab:
```sql
SELECT * FROM crosstab(
    'SELECT product_id, month, sales 
     FROM monthly_sales 
     ORDER BY 1, 2',
    'SELECT DISTINCT month FROM monthly_sales ORDER BY 1'
) AS ct(product_id int, jan numeric, feb numeric, mar numeric, apr numeric);
```

SQL Server PIVOT:
```sql
SELECT product_id, [1] AS jan, [2] AS feb, [3] AS mar, [4] AS apr
FROM monthly_sales
PIVOT (SUM(sales) FOR month IN ([1], [2], [3], [4])) AS pvt;
```

### Unpivot (Columns to Rows)

Manual unpivot:
```sql
SELECT product_id, 'jan' AS month, jan AS sales FROM pivoted_sales
UNION ALL
SELECT product_id, 'feb', feb FROM pivoted_sales
UNION ALL
SELECT product_id, 'mar', mar FROM pivoted_sales;
```

SQL Server UNPIVOT:
```sql
SELECT product_id, month, sales
FROM pivoted_sales
UNPIVOT (sales FOR month IN (jan, feb, mar, apr)) AS unpvt;
```

## Time Series Analysis

### Period-over-Period Comparison

```sql
WITH monthly_data AS (
    SELECT 
        DATE_TRUNC('month', order_date) AS month,
        SUM(total) AS revenue
    FROM orders
    GROUP BY DATE_TRUNC('month', order_date)
)
SELECT 
    month,
    revenue,
    LAG(revenue, 1) OVER (ORDER BY month) AS prev_month,
    LAG(revenue, 12) OVER (ORDER BY month) AS same_month_last_year,
    ROUND(100.0 * (revenue - LAG(revenue, 1) OVER (ORDER BY month)) / 
        NULLIF(LAG(revenue, 1) OVER (ORDER BY month), 0), 2) AS mom_growth,
    ROUND(100.0 * (revenue - LAG(revenue, 12) OVER (ORDER BY month)) / 
        NULLIF(LAG(revenue, 12) OVER (ORDER BY month), 0), 2) AS yoy_growth
FROM monthly_data
ORDER BY month;
```

### Year-to-Date Calculations

```sql
SELECT 
    order_date,
    daily_revenue,
    SUM(daily_revenue) OVER (
        PARTITION BY DATE_TRUNC('year', order_date)
        ORDER BY order_date
    ) AS ytd_revenue,
    SUM(daily_revenue) OVER (
        PARTITION BY DATE_TRUNC('quarter', order_date)
        ORDER BY order_date
    ) AS qtd_revenue,
    SUM(daily_revenue) OVER (
        PARTITION BY DATE_TRUNC('month', order_date)
        ORDER BY order_date
    ) AS mtd_revenue
FROM (
    SELECT 
        DATE(order_date) AS order_date,
        SUM(total) AS daily_revenue
    FROM orders
    GROUP BY DATE(order_date)
) daily;
```

### Moving Averages

```sql
SELECT 
    date,
    value,
    AVG(value) OVER (ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS ma_7,
    AVG(value) OVER (ORDER BY date ROWS BETWEEN 29 PRECEDING AND CURRENT ROW) AS ma_30,
    AVG(value) OVER (ORDER BY date ROWS BETWEEN 89 PRECEDING AND CURRENT ROW) AS ma_90
FROM daily_metrics;
```

### Growth Rate Calculations

```sql
WITH periods AS (
    SELECT 
        period_start,
        revenue,
        LAG(revenue) OVER (ORDER BY period_start) AS prev_revenue
    FROM revenue_by_period
)
SELECT 
    period_start,
    revenue,
    prev_revenue,
    ROUND(100.0 * (revenue - prev_revenue) / NULLIF(prev_revenue, 0), 2) AS growth_rate,
    ROUND(LN(revenue / NULLIF(prev_revenue, 0)), 4) AS log_growth,
    POWER(revenue / NULLIF(FIRST_VALUE(revenue) OVER (ORDER BY period_start), 0), 
        1.0 / ROW_NUMBER() OVER (ORDER BY period_start)) - 1 AS cagr
FROM periods;
```

## Statistical Functions

### Percentiles and Distributions

```sql
SELECT 
    category,
    COUNT(*) AS count,
    AVG(amount) AS mean,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY amount) AS median,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY amount) AS p25,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY amount) AS p75,
    PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY amount) AS p90,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY amount) AS p99,
    MODE() WITHIN GROUP (ORDER BY amount) AS mode,
    STDDEV(amount) AS std_dev,
    VARIANCE(amount) AS variance
FROM transactions
GROUP BY category;
```

### Correlation and Regression

```sql
SELECT 
    CORR(x, y) AS correlation,
    REGR_SLOPE(y, x) AS slope,
    REGR_INTERCEPT(y, x) AS intercept,
    REGR_R2(y, x) AS r_squared,
    REGR_COUNT(y, x) AS sample_count
FROM data_points;
```

### Histogram Buckets

```sql
SELECT 
    WIDTH_BUCKET(amount, 0, 1000, 10) AS bucket,
    MIN(amount) AS bucket_min,
    MAX(amount) AS bucket_max,
    COUNT(*) AS count
FROM transactions
GROUP BY WIDTH_BUCKET(amount, 0, 1000, 10)
ORDER BY bucket;
```

Or with CASE:
```sql
SELECT 
    CASE 
        WHEN amount < 100 THEN '0-99'
        WHEN amount < 500 THEN '100-499'
        WHEN amount < 1000 THEN '500-999'
        ELSE '1000+'
    END AS range,
    COUNT(*) AS count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS percentage
FROM transactions
GROUP BY 1
ORDER BY 1;
```

## Metrics Calculations

### Customer Lifetime Value

```sql
WITH customer_metrics AS (
    SELECT 
        customer_id,
        COUNT(*) AS order_count,
        SUM(total) AS total_revenue,
        MIN(order_date) AS first_order,
        MAX(order_date) AS last_order,
        AVG(total) AS avg_order_value
    FROM orders
    GROUP BY customer_id
)
SELECT 
    customer_id,
    order_count,
    total_revenue AS historical_ltv,
    avg_order_value,
    EXTRACT(DAYS FROM (last_order - first_order)) / NULLIF(order_count - 1, 0) AS avg_days_between_orders,
    avg_order_value * (365.0 / NULLIF(EXTRACT(DAYS FROM (last_order - first_order)) / NULLIF(order_count - 1, 0), 0)) AS projected_annual_value
FROM customer_metrics
WHERE order_count > 1;
```

### Churn Analysis

```sql
WITH customer_activity AS (
    SELECT 
        customer_id,
        MAX(order_date) AS last_order_date,
        COUNT(*) AS total_orders
    FROM orders
    GROUP BY customer_id
)
SELECT 
    CASE 
        WHEN last_order_date >= CURRENT_DATE - INTERVAL '30 days' THEN 'Active'
        WHEN last_order_date >= CURRENT_DATE - INTERVAL '90 days' THEN 'At Risk'
        WHEN last_order_date >= CURRENT_DATE - INTERVAL '180 days' THEN 'Churning'
        ELSE 'Churned'
    END AS status,
    COUNT(*) AS customer_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS percentage
FROM customer_activity
GROUP BY 1
ORDER BY 
    CASE 
        WHEN last_order_date >= CURRENT_DATE - INTERVAL '30 days' THEN 1
        WHEN last_order_date >= CURRENT_DATE - INTERVAL '90 days' THEN 2
        WHEN last_order_date >= CURRENT_DATE - INTERVAL '180 days' THEN 3
        ELSE 4
    END;
```

### Conversion Funnel

```sql
WITH funnel AS (
    SELECT 
        COUNT(DISTINCT CASE WHEN event = 'page_view' THEN user_id END) AS views,
        COUNT(DISTINCT CASE WHEN event = 'add_to_cart' THEN user_id END) AS cart_adds,
        COUNT(DISTINCT CASE WHEN event = 'checkout' THEN user_id END) AS checkouts,
        COUNT(DISTINCT CASE WHEN event = 'purchase' THEN user_id END) AS purchases
    FROM events
    WHERE event_date >= CURRENT_DATE - INTERVAL '7 days'
)
SELECT 
    'Page Views' AS step,
    views AS users,
    100.0 AS conversion_rate,
    100.0 AS rate_from_prev
FROM funnel
UNION ALL
SELECT 'Add to Cart', cart_adds, ROUND(100.0 * cart_adds / views, 2), ROUND(100.0 * cart_adds / views, 2) FROM funnel
UNION ALL
SELECT 'Checkout', checkouts, ROUND(100.0 * checkouts / views, 2), ROUND(100.0 * checkouts / cart_adds, 2) FROM funnel
UNION ALL
SELECT 'Purchase', purchases, ROUND(100.0 * purchases / views, 2), ROUND(100.0 * purchases / checkouts, 2) FROM funnel;
```

### RFM Analysis

```sql
WITH rfm_base AS (
    SELECT 
        customer_id,
        CURRENT_DATE - MAX(order_date)::date AS recency_days,
        COUNT(*) AS frequency,
        SUM(total) AS monetary
    FROM orders
    WHERE order_date >= CURRENT_DATE - INTERVAL '2 years'
    GROUP BY customer_id
),
rfm_scores AS (
    SELECT 
        customer_id,
        recency_days,
        frequency,
        monetary,
        NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
        NTILE(5) OVER (ORDER BY frequency) AS f_score,
        NTILE(5) OVER (ORDER BY monetary) AS m_score
    FROM rfm_base
)
SELECT 
    customer_id,
    r_score,
    f_score,
    m_score,
    r_score * 100 + f_score * 10 + m_score AS rfm_score,
    CASE 
        WHEN r_score >= 4 AND f_score >= 4 THEN 'Champions'
        WHEN r_score >= 4 AND f_score >= 2 THEN 'Loyal Customers'
        WHEN r_score >= 3 AND f_score <= 2 THEN 'Potential Loyalist'
        WHEN r_score <= 2 AND f_score >= 4 THEN 'At Risk'
        WHEN r_score <= 2 AND f_score <= 2 THEN 'Lost'
        ELSE 'Others'
    END AS segment
FROM rfm_scores;
```

## Output Format

When writing analytics queries:

1. **Purpose**: What metric/insight is being calculated
2. **Query**: Well-formatted SQL
3. **Explanation**: How the calculation works
4. **Assumptions**: Any data assumptions made
5. **Usage**: How to interpret results

## Additional Resources

| File | Content |
|------|---------|
| [examples.md](references/examples.md) | Advanced analytics examples |
