---
name: sql-reporting
description: Build business reporting SQL — KPIs, dashboard datasets, period comparisons (MoM/YoY), executive, sales and financial reports and scheduled-report queries. Use when the user asks for a report, KPI query, dashboard feed or recurring business summary in SQL.
metadata:
  category: programming
  version: "1.0.0"
---

# SQL Reporting

Build business reports, dashboards queries, KPI calculations, and scheduled report generation with SQL.

## Trigger Conditions

Activate this skill when the user:
- Needs business reports or dashboard queries
- Asks for KPI or metric calculations
- Wants periodic reports (daily, weekly, monthly)
- Needs executive summaries or scorecards
- Asks for comparison reports (YoY, MoM)
- Wants formatted output for presentations

## Report Types

### 1. Summary Reports

High-level aggregations for executive dashboards.

### 2. Detail Reports

Transaction-level data with filtering and sorting.

### 3. Trend Reports

Time-series analysis showing changes over periods.

### 4. Comparison Reports

Side-by-side comparisons (period over period, entity vs entity).

### 5. Exception Reports

Highlight anomalies or items requiring attention.

### 6. Operational Reports

Day-to-day business operations tracking.

## Report Building Workflow

```
1. REQUIREMENTS  -> Understand what metrics/data needed
2. SCOPE         -> Define date ranges, filters, dimensions
3. METRICS       -> Calculate KPIs and aggregations
4. FORMAT        -> Structure output for readability
5. OPTIMIZE      -> Ensure performance for scheduled runs
6. VALIDATE      -> Verify numbers against source
```

## Common KPI Calculations

### Revenue Metrics

```sql
SELECT 
    DATE_TRUNC('month', order_date) AS month,
    
    COUNT(DISTINCT id) AS total_orders,
    COUNT(DISTINCT customer_id) AS unique_customers,
    
    SUM(total) AS gross_revenue,
    SUM(total) - SUM(discount) AS net_revenue,
    SUM(CASE WHEN status = 'refunded' THEN total ELSE 0 END) AS refunds,
    SUM(total) - SUM(CASE WHEN status = 'refunded' THEN total ELSE 0 END) AS adjusted_revenue,
    
    ROUND(AVG(total), 2) AS average_order_value,
    ROUND(SUM(total) / COUNT(DISTINCT customer_id), 2) AS revenue_per_customer,
    
    SUM(total) - LAG(SUM(total)) OVER (ORDER BY DATE_TRUNC('month', order_date)) AS revenue_change,
    ROUND(100.0 * (SUM(total) - LAG(SUM(total)) OVER (ORDER BY DATE_TRUNC('month', order_date))) / 
        NULLIF(LAG(SUM(total)) OVER (ORDER BY DATE_TRUNC('month', order_date)), 0), 2) AS revenue_growth_pct

FROM orders
WHERE status NOT IN ('cancelled')
  AND order_date >= DATE_TRUNC('year', CURRENT_DATE) - INTERVAL '1 year'
GROUP BY DATE_TRUNC('month', order_date)
ORDER BY month;
```

### Customer Metrics

```sql
WITH customer_metrics AS (
    SELECT 
        DATE_TRUNC('month', c.created_at) AS cohort_month,
        COUNT(DISTINCT c.id) AS new_customers,
        COUNT(DISTINCT CASE WHEN o.id IS NOT NULL THEN c.id END) AS converted_customers,
        COUNT(DISTINCT o.id) AS orders_from_new,
        SUM(o.total) AS revenue_from_new
    FROM customers c
    LEFT JOIN orders o ON c.id = o.customer_id 
        AND o.order_date BETWEEN c.created_at AND c.created_at + INTERVAL '30 days'
    WHERE c.created_at >= DATE_TRUNC('year', CURRENT_DATE)
    GROUP BY DATE_TRUNC('month', c.created_at)
)
SELECT 
    cohort_month,
    new_customers,
    converted_customers,
    ROUND(100.0 * converted_customers / NULLIF(new_customers, 0), 2) AS conversion_rate,
    ROUND(revenue_from_new / NULLIF(converted_customers, 0), 2) AS avg_first_order_value,
    SUM(new_customers) OVER (ORDER BY cohort_month) AS cumulative_customers
FROM customer_metrics
ORDER BY cohort_month;
```

### Product Metrics

```sql
SELECT 
    p.category,
    p.name AS product,
    
    COUNT(DISTINCT oi.order_id) AS orders,
    SUM(oi.quantity) AS units_sold,
    SUM(oi.quantity * oi.unit_price) AS revenue,
    
    ROUND(AVG(oi.unit_price), 2) AS avg_selling_price,
    ROUND(SUM(oi.quantity * (oi.unit_price - p.cost)) / NULLIF(SUM(oi.quantity * oi.unit_price), 0) * 100, 2) AS margin_pct,
    
    ROUND(100.0 * SUM(oi.quantity * oi.unit_price) / 
        SUM(SUM(oi.quantity * oi.unit_price)) OVER (), 2) AS pct_of_total_revenue,
    
    RANK() OVER (ORDER BY SUM(oi.quantity * oi.unit_price) DESC) AS revenue_rank,
    RANK() OVER (PARTITION BY p.category ORDER BY SUM(oi.quantity) DESC) AS category_rank

FROM products p
JOIN order_items oi ON p.id = oi.product_id
JOIN orders o ON oi.order_id = o.id
WHERE o.status = 'completed'
  AND o.order_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY p.category, p.id, p.name, p.cost
ORDER BY revenue DESC;
```

## Executive Dashboard Reports

### Daily Business Summary

```sql
WITH today_metrics AS (
    SELECT 
        COUNT(DISTINCT o.id) AS orders,
        COUNT(DISTINCT o.customer_id) AS customers,
        SUM(o.total) AS revenue,
        COUNT(DISTINCT c.id) FILTER (WHERE c.created_at::date = CURRENT_DATE) AS new_customers
    FROM orders o
    LEFT JOIN customers c ON o.customer_id = c.id
    WHERE o.order_date::date = CURRENT_DATE
      AND o.status NOT IN ('cancelled')
),
yesterday_metrics AS (
    SELECT 
        COUNT(DISTINCT id) AS orders,
        SUM(total) AS revenue
    FROM orders
    WHERE order_date::date = CURRENT_DATE - 1
      AND status NOT IN ('cancelled')
),
same_day_last_week AS (
    SELECT 
        COUNT(DISTINCT id) AS orders,
        SUM(total) AS revenue
    FROM orders
    WHERE order_date::date = CURRENT_DATE - 7
      AND status NOT IN ('cancelled')
)
SELECT 
    'Today' AS period,
    t.orders,
    t.customers,
    t.revenue,
    t.new_customers,
    
    ROUND(100.0 * (t.revenue - y.revenue) / NULLIF(y.revenue, 0), 1) AS vs_yesterday_pct,
    ROUND(100.0 * (t.revenue - w.revenue) / NULLIF(w.revenue, 0), 1) AS vs_last_week_pct,
    
    ROUND(t.revenue / NULLIF(t.orders, 0), 2) AS avg_order_value
FROM today_metrics t, yesterday_metrics y, same_day_last_week w;
```

### Weekly Scorecard

```sql
WITH weekly_data AS (
    SELECT 
        DATE_TRUNC('week', order_date) AS week,
        COUNT(DISTINCT id) AS orders,
        COUNT(DISTINCT customer_id) AS customers,
        SUM(total) AS revenue,
        COUNT(DISTINCT CASE WHEN is_first_order THEN customer_id END) AS new_customers,
        AVG(total) AS avg_order_value
    FROM orders
    WHERE order_date >= CURRENT_DATE - INTERVAL '12 weeks'
      AND status = 'completed'
    GROUP BY DATE_TRUNC('week', order_date)
)
SELECT 
    TO_CHAR(week, 'YYYY-MM-DD') AS week_start,
    orders,
    customers,
    new_customers,
    customers - new_customers AS returning_customers,
    ROUND(revenue, 2) AS revenue,
    ROUND(avg_order_value, 2) AS aov,
    
    LAG(orders) OVER (ORDER BY week) AS prev_week_orders,
    ROUND(100.0 * (orders - LAG(orders) OVER (ORDER BY week)) / 
        NULLIF(LAG(orders) OVER (ORDER BY week), 0), 1) AS orders_wow_pct,
    
    LAG(revenue) OVER (ORDER BY week) AS prev_week_revenue,
    ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY week)) / 
        NULLIF(LAG(revenue) OVER (ORDER BY week), 0), 1) AS revenue_wow_pct,
    
    AVG(revenue) OVER (ORDER BY week ROWS BETWEEN 3 PRECEDING AND CURRENT ROW) AS rolling_4wk_avg
FROM weekly_data
ORDER BY week DESC;
```

### Monthly Business Review

```sql
WITH monthly_summary AS (
    SELECT 
        DATE_TRUNC('month', order_date) AS month,
        
        COUNT(DISTINCT id) AS orders,
        COUNT(DISTINCT customer_id) AS customers,
        SUM(total) AS revenue,
        SUM(total - cost) AS gross_profit,
        
        COUNT(DISTINCT CASE WHEN customer_order_num = 1 THEN customer_id END) AS new_customers,
        COUNT(DISTINCT CASE WHEN customer_order_num > 1 THEN customer_id END) AS repeat_customers
        
    FROM (
        SELECT 
            o.*,
            ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date) AS customer_order_num
        FROM orders o
        WHERE status = 'completed'
    ) numbered
    WHERE order_date >= DATE_TRUNC('year', CURRENT_DATE)
    GROUP BY DATE_TRUNC('month', order_date)
)
SELECT 
    TO_CHAR(month, 'YYYY-MM') AS month,
    orders,
    customers,
    new_customers,
    repeat_customers,
    ROUND(100.0 * repeat_customers / NULLIF(customers, 0), 1) AS repeat_rate,
    
    ROUND(revenue, 2) AS revenue,
    ROUND(gross_profit, 2) AS gross_profit,
    ROUND(100.0 * gross_profit / NULLIF(revenue, 0), 1) AS margin_pct,
    
    ROUND(revenue / NULLIF(orders, 0), 2) AS aov,
    ROUND(revenue / NULLIF(customers, 0), 2) AS revenue_per_customer,
    
    ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY month)) / 
        NULLIF(LAG(revenue) OVER (ORDER BY month), 0), 1) AS mom_growth,
    
    ROUND(100.0 * (revenue - LAG(revenue, 12) OVER (ORDER BY month)) / 
        NULLIF(LAG(revenue, 12) OVER (ORDER BY month), 0), 1) AS yoy_growth
        
FROM monthly_summary
ORDER BY month DESC;
```

## Operational Reports

### Inventory Status Report

```sql
SELECT 
    p.sku,
    p.name,
    c.name AS category,
    
    i.quantity_on_hand,
    i.reorder_point,
    i.reorder_quantity,
    
    COALESCE(s.units_sold_7d, 0) AS sold_last_7d,
    COALESCE(s.units_sold_30d, 0) AS sold_last_30d,
    ROUND(COALESCE(s.units_sold_30d, 0) / 30.0, 1) AS daily_velocity,
    
    CASE 
        WHEN i.quantity_on_hand <= 0 THEN 0
        WHEN COALESCE(s.units_sold_30d, 0) = 0 THEN 999
        ELSE ROUND(i.quantity_on_hand / (s.units_sold_30d / 30.0), 0)
    END AS days_of_stock,
    
    CASE 
        WHEN i.quantity_on_hand <= 0 THEN 'OUT OF STOCK'
        WHEN i.quantity_on_hand <= i.reorder_point THEN 'REORDER NOW'
        WHEN i.quantity_on_hand <= i.reorder_point * 1.5 THEN 'LOW STOCK'
        WHEN i.quantity_on_hand > s.units_sold_30d * 6 THEN 'OVERSTOCK'
        ELSE 'OK'
    END AS status,
    
    CASE 
        WHEN i.quantity_on_hand <= i.reorder_point THEN i.reorder_quantity
        ELSE 0
    END AS suggested_order

FROM products p
JOIN inventory i ON p.id = i.product_id
JOIN categories c ON p.category_id = c.id
LEFT JOIN (
    SELECT 
        product_id,
        SUM(CASE WHEN order_date >= CURRENT_DATE - 7 THEN quantity ELSE 0 END) AS units_sold_7d,
        SUM(CASE WHEN order_date >= CURRENT_DATE - 30 THEN quantity ELSE 0 END) AS units_sold_30d
    FROM order_items oi
    JOIN orders o ON oi.order_id = o.id
    WHERE o.status = 'completed'
    GROUP BY product_id
) s ON p.id = s.product_id

WHERE p.is_active = true
ORDER BY 
    CASE 
        WHEN i.quantity_on_hand <= 0 THEN 1
        WHEN i.quantity_on_hand <= i.reorder_point THEN 2
        WHEN i.quantity_on_hand <= i.reorder_point * 1.5 THEN 3
        ELSE 4
    END,
    p.name;
```

### Order Fulfillment Report

```sql
SELECT 
    DATE(order_date) AS order_date,
    
    COUNT(*) AS total_orders,
    COUNT(*) FILTER (WHERE status = 'pending') AS pending,
    COUNT(*) FILTER (WHERE status = 'processing') AS processing,
    COUNT(*) FILTER (WHERE status = 'shipped') AS shipped,
    COUNT(*) FILTER (WHERE status = 'delivered') AS delivered,
    
    ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'delivered') / COUNT(*), 1) AS fulfillment_rate,
    
    ROUND(AVG(EXTRACT(EPOCH FROM (ship_date - order_date)) / 3600) 
        FILTER (WHERE ship_date IS NOT NULL), 1) AS avg_hours_to_ship,
    
    ROUND(AVG(EXTRACT(EPOCH FROM (delivery_date - ship_date)) / 86400) 
        FILTER (WHERE delivery_date IS NOT NULL), 1) AS avg_days_in_transit,
    
    COUNT(*) FILTER (WHERE ship_date > order_date + INTERVAL '2 days') AS late_shipments,
    
    SUM(total) FILTER (WHERE status NOT IN ('cancelled', 'refunded')) AS fulfilled_revenue

FROM orders
WHERE order_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(order_date)
ORDER BY order_date DESC;
```

### Customer Service Report

```sql
SELECT 
    DATE_TRUNC('week', created_at) AS week,
    
    COUNT(*) AS total_tickets,
    COUNT(*) FILTER (WHERE status = 'open') AS open_tickets,
    COUNT(*) FILTER (WHERE status = 'resolved') AS resolved_tickets,
    
    ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'resolved') / COUNT(*), 1) AS resolution_rate,
    
    ROUND(AVG(EXTRACT(EPOCH FROM (first_response_at - created_at)) / 3600) 
        FILTER (WHERE first_response_at IS NOT NULL), 1) AS avg_first_response_hours,
    
    ROUND(AVG(EXTRACT(EPOCH FROM (resolved_at - created_at)) / 3600) 
        FILTER (WHERE resolved_at IS NOT NULL), 1) AS avg_resolution_hours,
    
    COUNT(*) FILTER (WHERE priority = 'high') AS high_priority,
    COUNT(*) FILTER (WHERE category = 'refund') AS refund_requests,
    COUNT(*) FILTER (WHERE category = 'shipping') AS shipping_issues,
    
    ROUND(AVG(satisfaction_score) FILTER (WHERE satisfaction_score IS NOT NULL), 2) AS avg_csat

FROM support_tickets
WHERE created_at >= CURRENT_DATE - INTERVAL '12 weeks'
GROUP BY DATE_TRUNC('week', created_at)
ORDER BY week DESC;
```

## Comparison Reports

### Year-over-Year Comparison

```sql
WITH current_period AS (
    SELECT 
        EXTRACT(MONTH FROM order_date) AS month,
        COUNT(*) AS orders,
        SUM(total) AS revenue,
        COUNT(DISTINCT customer_id) AS customers
    FROM orders
    WHERE order_date >= DATE_TRUNC('year', CURRENT_DATE)
      AND status = 'completed'
    GROUP BY EXTRACT(MONTH FROM order_date)
),
prior_period AS (
    SELECT 
        EXTRACT(MONTH FROM order_date) AS month,
        COUNT(*) AS orders,
        SUM(total) AS revenue,
        COUNT(DISTINCT customer_id) AS customers
    FROM orders
    WHERE order_date >= DATE_TRUNC('year', CURRENT_DATE) - INTERVAL '1 year'
      AND order_date < DATE_TRUNC('year', CURRENT_DATE)
      AND status = 'completed'
    GROUP BY EXTRACT(MONTH FROM order_date)
)
SELECT 
    TO_CHAR(DATE '2024-01-01' + (c.month - 1) * INTERVAL '1 month', 'Month') AS month,
    
    c.orders AS current_orders,
    p.orders AS prior_orders,
    c.orders - p.orders AS orders_change,
    ROUND(100.0 * (c.orders - p.orders) / NULLIF(p.orders, 0), 1) AS orders_yoy_pct,
    
    ROUND(c.revenue, 2) AS current_revenue,
    ROUND(p.revenue, 2) AS prior_revenue,
    ROUND(c.revenue - p.revenue, 2) AS revenue_change,
    ROUND(100.0 * (c.revenue - p.revenue) / NULLIF(p.revenue, 0), 1) AS revenue_yoy_pct,
    
    c.customers AS current_customers,
    p.customers AS prior_customers,
    ROUND(100.0 * (c.customers - p.customers) / NULLIF(p.customers, 0), 1) AS customers_yoy_pct

FROM current_period c
LEFT JOIN prior_period p ON c.month = p.month
ORDER BY c.month;
```

### Regional Comparison

```sql
WITH regional_metrics AS (
    SELECT 
        r.name AS region,
        COUNT(DISTINCT o.id) AS orders,
        COUNT(DISTINCT o.customer_id) AS customers,
        SUM(o.total) AS revenue,
        AVG(o.total) AS avg_order_value
    FROM orders o
    JOIN customers c ON o.customer_id = c.id
    JOIN regions r ON c.region_id = r.id
    WHERE o.order_date >= DATE_TRUNC('quarter', CURRENT_DATE)
      AND o.status = 'completed'
    GROUP BY r.name
)
SELECT 
    region,
    orders,
    customers,
    ROUND(revenue, 2) AS revenue,
    ROUND(avg_order_value, 2) AS aov,
    
    ROUND(100.0 * revenue / SUM(revenue) OVER (), 2) AS pct_of_total,
    
    RANK() OVER (ORDER BY revenue DESC) AS revenue_rank,
    
    ROUND(revenue / NULLIF(customers, 0), 2) AS revenue_per_customer,
    
    CASE 
        WHEN revenue > AVG(revenue) OVER () * 1.2 THEN 'Above Average'
        WHEN revenue < AVG(revenue) OVER () * 0.8 THEN 'Below Average'
        ELSE 'Average'
    END AS performance

FROM regional_metrics
ORDER BY revenue DESC;
```

## Formatting Best Practices

### Currency Formatting

```sql
SELECT 
    TO_CHAR(revenue, 'FM$999,999,999.00') AS revenue_formatted,
    TO_CHAR(growth_rate, 'FM990.0%') AS growth_formatted
FROM metrics;
```

### Date Formatting

```sql
SELECT 
    TO_CHAR(date, 'Mon DD, YYYY') AS date_formatted,
    TO_CHAR(date, 'YYYY-MM') AS month_formatted,
    TO_CHAR(date, 'Day') AS day_of_week
FROM data;
```

### Conditional Formatting Hints

```sql
SELECT 
    metric,
    value,
    CASE 
        WHEN value > 0 THEN 'positive'
        WHEN value < 0 THEN 'negative'
        ELSE 'neutral'
    END AS style_class,
    CASE 
        WHEN value > threshold * 1.1 THEN 'green'
        WHEN value < threshold * 0.9 THEN 'red'
        ELSE 'yellow'
    END AS status_color
FROM metrics;
```

## Output Format

When creating reports:

1. **Purpose**: What question does this report answer
2. **Query**: Optimized SQL with formatting
3. **Metrics Explained**: Definition of each calculated field
4. **Filters**: Date range and other parameters
5. **Usage Notes**: How to interpret or modify

## Additional Resources

| File | Content |
|------|---------|
| [examples.md](references/examples.md) | Complete report templates |
