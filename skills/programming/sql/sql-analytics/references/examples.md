# Analytics SQL Examples

Advanced analytics queries for business intelligence and data analysis.

## Revenue Analytics

### Revenue by Multiple Dimensions

```sql
SELECT 
    COALESCE(d.region, 'All Regions') AS region,
    COALESCE(d.country, 'All Countries') AS country,
    COALESCE(p.category, 'All Categories') AS category,
    COUNT(DISTINCT o.id) AS orders,
    COUNT(DISTINCT o.customer_id) AS customers,
    SUM(oi.quantity) AS units,
    SUM(oi.quantity * oi.unit_price) AS revenue,
    ROUND(AVG(oi.quantity * oi.unit_price), 2) AS avg_item_value
FROM orders o
JOIN order_items oi ON o.id = oi.order_id
JOIN products p ON oi.product_id = p.id
JOIN customers c ON o.customer_id = c.id
JOIN demographics d ON c.demographic_id = d.id
WHERE o.order_date >= '2024-01-01'
  AND o.status = 'completed'
GROUP BY CUBE(d.region, d.country, p.category)
ORDER BY 
    GROUPING(d.region), d.region,
    GROUPING(d.country), d.country,
    GROUPING(p.category), p.category;
```

### Revenue Trend with Seasonality

```sql
WITH daily_revenue AS (
    SELECT 
        DATE(order_date) AS date,
        SUM(total) AS revenue
    FROM orders
    WHERE status = 'completed'
    GROUP BY DATE(order_date)
),
with_components AS (
    SELECT 
        date,
        revenue,
        EXTRACT(DOW FROM date) AS day_of_week,
        EXTRACT(MONTH FROM date) AS month,
        AVG(revenue) OVER (ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS ma_7,
        AVG(revenue) OVER (ORDER BY date ROWS BETWEEN 29 PRECEDING AND CURRENT ROW) AS ma_30,
        AVG(revenue) OVER (
            PARTITION BY EXTRACT(DOW FROM date)
            ORDER BY date 
            ROWS BETWEEN 3 PRECEDING AND CURRENT ROW
        ) AS dow_ma
    FROM daily_revenue
)
SELECT 
    date,
    revenue,
    ROUND(ma_7, 2) AS weekly_trend,
    ROUND(ma_30, 2) AS monthly_trend,
    ROUND(dow_ma, 2) AS day_of_week_avg,
    ROUND(revenue / NULLIF(dow_ma, 0) * 100, 1) AS pct_of_dow_avg,
    CASE 
        WHEN revenue > ma_7 * 1.2 THEN 'Spike'
        WHEN revenue < ma_7 * 0.8 THEN 'Dip'
        ELSE 'Normal'
    END AS anomaly_flag
FROM with_components
ORDER BY date DESC;
```

## Customer Analytics

### Customer Segmentation

```sql
WITH customer_stats AS (
    SELECT 
        c.id AS customer_id,
        c.created_at AS signup_date,
        COUNT(DISTINCT o.id) AS order_count,
        SUM(o.total) AS total_spent,
        AVG(o.total) AS avg_order_value,
        MAX(o.order_date) AS last_order,
        MIN(o.order_date) AS first_order,
        CURRENT_DATE - MAX(o.order_date)::date AS days_since_last_order
    FROM customers c
    LEFT JOIN orders o ON c.id = o.customer_id AND o.status = 'completed'
    GROUP BY c.id, c.created_at
),
percentiles AS (
    SELECT 
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY total_spent) AS spend_p75,
        PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY total_spent) AS spend_p50,
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY order_count) AS orders_p75
    FROM customer_stats
    WHERE order_count > 0
)
SELECT 
    cs.*,
    CASE 
        WHEN cs.order_count = 0 THEN 'Never Purchased'
        WHEN cs.total_spent >= p.spend_p75 AND cs.days_since_last_order <= 30 THEN 'VIP Active'
        WHEN cs.total_spent >= p.spend_p75 AND cs.days_since_last_order <= 90 THEN 'VIP At Risk'
        WHEN cs.total_spent >= p.spend_p75 THEN 'VIP Churned'
        WHEN cs.total_spent >= p.spend_p50 AND cs.days_since_last_order <= 60 THEN 'Regular Active'
        WHEN cs.total_spent >= p.spend_p50 THEN 'Regular Inactive'
        WHEN cs.order_count >= 2 THEN 'Developing'
        ELSE 'New/One-time'
    END AS segment
FROM customer_stats cs, percentiles p;
```

### Cohort Analysis

```sql
WITH cohorts AS (
    SELECT 
        customer_id,
        DATE_TRUNC('month', MIN(order_date)) AS cohort_month
    FROM orders
    WHERE status = 'completed'
    GROUP BY customer_id
),
monthly_activity AS (
    SELECT 
        c.cohort_month,
        DATE_TRUNC('month', o.order_date) AS activity_month,
        COUNT(DISTINCT o.customer_id) AS active_customers,
        SUM(o.total) AS revenue
    FROM orders o
    JOIN cohorts c ON o.customer_id = c.customer_id
    WHERE o.status = 'completed'
    GROUP BY c.cohort_month, DATE_TRUNC('month', o.order_date)
),
cohort_sizes AS (
    SELECT cohort_month, COUNT(*) AS cohort_size
    FROM cohorts
    GROUP BY cohort_month
)
SELECT 
    ma.cohort_month,
    cs.cohort_size,
    EXTRACT(MONTH FROM AGE(ma.activity_month, ma.cohort_month)) AS months_since_first,
    ma.active_customers,
    ROUND(100.0 * ma.active_customers / cs.cohort_size, 1) AS retention_rate,
    ma.revenue,
    ROUND(ma.revenue / ma.active_customers, 2) AS revenue_per_active
FROM monthly_activity ma
JOIN cohort_sizes cs ON ma.cohort_month = cs.cohort_month
WHERE ma.cohort_month >= '2023-01-01'
ORDER BY ma.cohort_month, months_since_first;
```

### Customer Journey Analysis

```sql
WITH ordered_events AS (
    SELECT 
        session_id,
        user_id,
        event_name,
        event_time,
        ROW_NUMBER() OVER (PARTITION BY session_id ORDER BY event_time) AS event_order,
        LEAD(event_name) OVER (PARTITION BY session_id ORDER BY event_time) AS next_event,
        LEAD(event_time) OVER (PARTITION BY session_id ORDER BY event_time) - event_time AS time_to_next
    FROM events
),
journeys AS (
    SELECT 
        session_id,
        STRING_AGG(event_name, ' -> ' ORDER BY event_order) AS journey_path,
        COUNT(*) AS journey_length,
        MAX(CASE WHEN event_name = 'purchase' THEN 1 ELSE 0 END) AS converted
    FROM ordered_events
    GROUP BY session_id
)
SELECT 
    journey_path,
    COUNT(*) AS sessions,
    SUM(converted) AS conversions,
    ROUND(100.0 * SUM(converted) / COUNT(*), 2) AS conversion_rate,
    ROUND(AVG(journey_length), 1) AS avg_journey_length
FROM journeys
WHERE journey_length >= 2
GROUP BY journey_path
HAVING COUNT(*) >= 100
ORDER BY conversions DESC
LIMIT 20;
```

## Product Analytics

### Product Performance Matrix

```sql
WITH product_metrics AS (
    SELECT 
        p.id AS product_id,
        p.name AS product_name,
        p.category,
        COUNT(DISTINCT oi.order_id) AS orders,
        SUM(oi.quantity) AS units_sold,
        SUM(oi.quantity * oi.unit_price) AS revenue,
        COUNT(DISTINCT o.customer_id) AS unique_buyers,
        AVG(r.rating) AS avg_rating,
        COUNT(r.id) AS review_count
    FROM products p
    LEFT JOIN order_items oi ON p.id = oi.product_id
    LEFT JOIN orders o ON oi.order_id = o.id AND o.status = 'completed'
    LEFT JOIN reviews r ON p.id = r.product_id
    WHERE o.order_date >= CURRENT_DATE - INTERVAL '90 days' OR o.order_date IS NULL
    GROUP BY p.id, p.name, p.category
),
category_totals AS (
    SELECT 
        category,
        SUM(revenue) AS category_revenue,
        SUM(units_sold) AS category_units
    FROM product_metrics
    GROUP BY category
)
SELECT 
    pm.*,
    ROUND(100.0 * pm.revenue / NULLIF(ct.category_revenue, 0), 2) AS pct_of_category_revenue,
    ROUND(pm.revenue / NULLIF(pm.unique_buyers, 0), 2) AS revenue_per_buyer,
    NTILE(4) OVER (ORDER BY pm.revenue) AS revenue_quartile,
    NTILE(4) OVER (ORDER BY pm.avg_rating) AS rating_quartile,
    CASE 
        WHEN NTILE(4) OVER (ORDER BY pm.revenue) = 4 AND NTILE(4) OVER (ORDER BY pm.avg_rating) >= 3 THEN 'Star'
        WHEN NTILE(4) OVER (ORDER BY pm.revenue) = 4 AND NTILE(4) OVER (ORDER BY pm.avg_rating) < 3 THEN 'Cash Cow'
        WHEN NTILE(4) OVER (ORDER BY pm.revenue) <= 2 AND NTILE(4) OVER (ORDER BY pm.avg_rating) >= 3 THEN 'Hidden Gem'
        ELSE 'Question Mark'
    END AS product_quadrant
FROM product_metrics pm
JOIN category_totals ct ON pm.category = ct.category
ORDER BY pm.revenue DESC;
```

### Market Basket Analysis

```sql
WITH order_products AS (
    SELECT 
        order_id,
        product_id,
        product_name
    FROM order_items oi
    JOIN products p ON oi.product_id = p.id
),
product_pairs AS (
    SELECT 
        op1.product_name AS product_a,
        op2.product_name AS product_b,
        COUNT(DISTINCT op1.order_id) AS co_occurrence
    FROM order_products op1
    JOIN order_products op2 ON op1.order_id = op2.order_id 
        AND op1.product_id < op2.product_id
    GROUP BY op1.product_name, op2.product_name
),
product_counts AS (
    SELECT product_name, COUNT(DISTINCT order_id) AS product_orders
    FROM order_products
    GROUP BY product_name
),
total_orders AS (
    SELECT COUNT(DISTINCT order_id) AS total FROM order_products
)
SELECT 
    pp.product_a,
    pp.product_b,
    pp.co_occurrence,
    pc_a.product_orders AS orders_with_a,
    pc_b.product_orders AS orders_with_b,
    ROUND(100.0 * pp.co_occurrence / pc_a.product_orders, 2) AS support_a,
    ROUND(100.0 * pp.co_occurrence / pc_b.product_orders, 2) AS support_b,
    ROUND(
        (pp.co_occurrence::float / t.total) / 
        ((pc_a.product_orders::float / t.total) * (pc_b.product_orders::float / t.total)),
        2
    ) AS lift
FROM product_pairs pp
JOIN product_counts pc_a ON pp.product_a = pc_a.product_name
JOIN product_counts pc_b ON pp.product_b = pc_b.product_name
CROSS JOIN total_orders t
WHERE pp.co_occurrence >= 50
ORDER BY lift DESC
LIMIT 50;
```

## Marketing Analytics

### Attribution Analysis (Multi-Touch)

```sql
WITH touchpoints AS (
    SELECT 
        conversion_id,
        channel,
        touch_time,
        ROW_NUMBER() OVER (PARTITION BY conversion_id ORDER BY touch_time) AS touch_order,
        COUNT(*) OVER (PARTITION BY conversion_id) AS total_touches,
        ROW_NUMBER() OVER (PARTITION BY conversion_id ORDER BY touch_time DESC) AS reverse_order
    FROM marketing_touches
),
attribution AS (
    SELECT 
        conversion_id,
        channel,
        touch_order,
        total_touches,
        CASE WHEN touch_order = 1 THEN 1.0 ELSE 0.0 END AS first_touch,
        CASE WHEN reverse_order = 1 THEN 1.0 ELSE 0.0 END AS last_touch,
        1.0 / total_touches AS linear,
        CASE 
            WHEN touch_order = 1 THEN 0.4
            WHEN reverse_order = 1 THEN 0.4
            ELSE 0.2 / (total_touches - 2)
        END AS position_based,
        POWER(2, total_touches - touch_order) / (POWER(2, total_touches) - 1) AS time_decay
    FROM touchpoints
)
SELECT 
    channel,
    COUNT(DISTINCT conversion_id) AS conversions,
    ROUND(SUM(first_touch), 1) AS first_touch_credit,
    ROUND(SUM(last_touch), 1) AS last_touch_credit,
    ROUND(SUM(linear), 1) AS linear_credit,
    ROUND(SUM(position_based), 1) AS position_based_credit,
    ROUND(SUM(time_decay), 1) AS time_decay_credit
FROM attribution
GROUP BY channel
ORDER BY linear_credit DESC;
```

### Campaign Performance

```sql
WITH campaign_metrics AS (
    SELECT 
        c.campaign_id,
        c.campaign_name,
        c.channel,
        c.start_date,
        c.end_date,
        c.budget,
        COUNT(DISTINCT v.visitor_id) AS visitors,
        COUNT(DISTINCT l.lead_id) AS leads,
        COUNT(DISTINCT CASE WHEN o.status = 'completed' THEN o.id END) AS conversions,
        SUM(CASE WHEN o.status = 'completed' THEN o.total ELSE 0 END) AS revenue
    FROM campaigns c
    LEFT JOIN campaign_visits v ON c.campaign_id = v.campaign_id
    LEFT JOIN leads l ON v.visitor_id = l.visitor_id AND l.source_campaign = c.campaign_id
    LEFT JOIN orders o ON l.lead_id = o.lead_id
    GROUP BY c.campaign_id, c.campaign_name, c.channel, c.start_date, c.end_date, c.budget
)
SELECT 
    campaign_name,
    channel,
    budget,
    visitors,
    leads,
    conversions,
    revenue,
    ROUND(100.0 * leads / NULLIF(visitors, 0), 2) AS visitor_to_lead_rate,
    ROUND(100.0 * conversions / NULLIF(leads, 0), 2) AS lead_to_customer_rate,
    ROUND(budget / NULLIF(visitors, 0), 2) AS cost_per_visitor,
    ROUND(budget / NULLIF(leads, 0), 2) AS cost_per_lead,
    ROUND(budget / NULLIF(conversions, 0), 2) AS cost_per_acquisition,
    ROUND((revenue - budget) / NULLIF(budget, 0) * 100, 2) AS roi_pct,
    ROUND(revenue / NULLIF(budget, 0), 2) AS roas
FROM campaign_metrics
ORDER BY roi_pct DESC;
```

## Financial Analytics

### P&L Statement Query

```sql
WITH monthly_figures AS (
    SELECT 
        DATE_TRUNC('month', transaction_date) AS month,
        account_type,
        account_category,
        SUM(CASE WHEN type = 'credit' THEN amount ELSE -amount END) AS amount
    FROM transactions t
    JOIN accounts a ON t.account_id = a.id
    WHERE transaction_date >= DATE_TRUNC('year', CURRENT_DATE)
    GROUP BY DATE_TRUNC('month', transaction_date), account_type, account_category
)
SELECT 
    month,
    SUM(CASE WHEN account_type = 'Revenue' THEN amount ELSE 0 END) AS revenue,
    SUM(CASE WHEN account_category = 'Cost of Goods Sold' THEN -amount ELSE 0 END) AS cogs,
    SUM(CASE WHEN account_type = 'Revenue' THEN amount ELSE 0 END) - 
        SUM(CASE WHEN account_category = 'Cost of Goods Sold' THEN -amount ELSE 0 END) AS gross_profit,
    SUM(CASE WHEN account_category = 'Operating Expense' THEN -amount ELSE 0 END) AS operating_expenses,
    SUM(CASE WHEN account_type = 'Revenue' THEN amount ELSE 0 END) - 
        SUM(CASE WHEN account_category IN ('Cost of Goods Sold', 'Operating Expense') THEN -amount ELSE 0 END) AS operating_income,
    SUM(CASE WHEN account_category = 'Other Income' THEN amount ELSE 0 END) AS other_income,
    SUM(CASE WHEN account_category = 'Other Expense' THEN -amount ELSE 0 END) AS other_expenses,
    SUM(CASE 
        WHEN account_type = 'Revenue' THEN amount 
        WHEN account_type = 'Expense' THEN -amount
        WHEN account_category = 'Other Income' THEN amount
        WHEN account_category = 'Other Expense' THEN -amount
        ELSE 0 
    END) AS net_income
FROM monthly_figures
GROUP BY month
ORDER BY month;
```

### Cash Flow Analysis

```sql
WITH daily_cash AS (
    SELECT 
        DATE(transaction_date) AS date,
        SUM(CASE WHEN type = 'credit' THEN amount ELSE -amount END) AS net_cash_flow
    FROM transactions
    WHERE account_type = 'Cash'
    GROUP BY DATE(transaction_date)
)
SELECT 
    date,
    net_cash_flow,
    SUM(net_cash_flow) OVER (ORDER BY date) AS running_balance,
    AVG(net_cash_flow) OVER (ORDER BY date ROWS BETWEEN 29 PRECEDING AND CURRENT ROW) AS avg_daily_30d,
    MIN(SUM(net_cash_flow) OVER (ORDER BY date)) OVER () AS min_balance_ever,
    CASE 
        WHEN SUM(net_cash_flow) OVER (ORDER BY date) < 0 THEN 'Negative Balance'
        WHEN net_cash_flow < AVG(net_cash_flow) OVER (ORDER BY date ROWS BETWEEN 29 PRECEDING AND CURRENT ROW) * 0.5 THEN 'Below Average'
        ELSE 'Normal'
    END AS cash_status
FROM daily_cash
ORDER BY date DESC;
```

## Operational Analytics

### Inventory Turnover

```sql
WITH inventory_metrics AS (
    SELECT 
        p.id AS product_id,
        p.name,
        p.category,
        i.quantity_on_hand,
        i.unit_cost,
        i.quantity_on_hand * i.unit_cost AS inventory_value,
        COALESCE(s.units_sold_30d, 0) AS units_sold_30d,
        COALESCE(s.units_sold_90d, 0) AS units_sold_90d
    FROM products p
    JOIN inventory i ON p.id = i.product_id
    LEFT JOIN (
        SELECT 
            product_id,
            SUM(CASE WHEN order_date >= CURRENT_DATE - 30 THEN quantity ELSE 0 END) AS units_sold_30d,
            SUM(CASE WHEN order_date >= CURRENT_DATE - 90 THEN quantity ELSE 0 END) AS units_sold_90d
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        WHERE o.status = 'completed'
        GROUP BY product_id
    ) s ON p.id = s.product_id
)
SELECT 
    product_id,
    name,
    category,
    quantity_on_hand,
    inventory_value,
    units_sold_30d,
    units_sold_90d,
    ROUND(units_sold_30d / 30.0 * 365, 0) AS annual_velocity,
    ROUND(quantity_on_hand / NULLIF(units_sold_30d / 30.0, 0), 0) AS days_of_stock,
    ROUND((units_sold_90d / 90.0 * 365) / NULLIF(inventory_value, 0) * 100, 1) AS inventory_turnover,
    CASE 
        WHEN quantity_on_hand <= 0 THEN 'Out of Stock'
        WHEN quantity_on_hand / NULLIF(units_sold_30d / 30.0, 0) < 7 THEN 'Critical Low'
        WHEN quantity_on_hand / NULLIF(units_sold_30d / 30.0, 0) < 30 THEN 'Low Stock'
        WHEN quantity_on_hand / NULLIF(units_sold_30d / 30.0, 0) > 180 THEN 'Overstock'
        ELSE 'Healthy'
    END AS stock_status
FROM inventory_metrics
ORDER BY inventory_value DESC;
```
