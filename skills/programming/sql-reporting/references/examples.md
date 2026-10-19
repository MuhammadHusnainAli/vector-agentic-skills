# SQL Reporting Examples

Complete report templates for common business reporting needs.

## Executive Reports

### CEO Dashboard Query

```sql
WITH current_metrics AS (
    SELECT 
        COUNT(DISTINCT o.id) AS orders,
        SUM(o.total) AS revenue,
        COUNT(DISTINCT o.customer_id) AS active_customers,
        COUNT(DISTINCT c.id) FILTER (WHERE c.created_at >= DATE_TRUNC('month', CURRENT_DATE)) AS new_customers
    FROM orders o
    LEFT JOIN customers c ON o.customer_id = c.id
    WHERE o.order_date >= DATE_TRUNC('month', CURRENT_DATE)
      AND o.status = 'completed'
),
prior_month AS (
    SELECT 
        COUNT(DISTINCT id) AS orders,
        SUM(total) AS revenue,
        COUNT(DISTINCT customer_id) AS active_customers
    FROM orders
    WHERE order_date >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month'
      AND order_date < DATE_TRUNC('month', CURRENT_DATE)
      AND status = 'completed'
),
ytd_metrics AS (
    SELECT 
        SUM(total) AS ytd_revenue,
        COUNT(DISTINCT customer_id) AS ytd_customers
    FROM orders
    WHERE order_date >= DATE_TRUNC('year', CURRENT_DATE)
      AND status = 'completed'
),
targets AS (
    SELECT 
        monthly_revenue_target,
        monthly_order_target,
        annual_revenue_target
    FROM business_targets
    WHERE year = EXTRACT(YEAR FROM CURRENT_DATE)
)
SELECT 
    TO_CHAR(CURRENT_DATE, 'Month YYYY') AS report_period,
    
    c.revenue AS mtd_revenue,
    t.monthly_revenue_target AS revenue_target,
    ROUND(100.0 * c.revenue / t.monthly_revenue_target, 1) AS revenue_attainment_pct,
    ROUND(100.0 * (c.revenue - p.revenue) / NULLIF(p.revenue, 0), 1) AS revenue_mom_growth,
    
    c.orders AS mtd_orders,
    ROUND(100.0 * (c.orders - p.orders) / NULLIF(p.orders, 0), 1) AS orders_mom_growth,
    ROUND(c.revenue / NULLIF(c.orders, 0), 2) AS avg_order_value,
    
    c.active_customers,
    c.new_customers,
    ROUND(100.0 * c.new_customers / NULLIF(c.active_customers, 0), 1) AS new_customer_pct,
    
    y.ytd_revenue,
    t.annual_revenue_target,
    ROUND(100.0 * y.ytd_revenue / t.annual_revenue_target, 1) AS annual_attainment_pct,
    
    CASE 
        WHEN c.revenue >= t.monthly_revenue_target THEN 'ON TRACK'
        WHEN c.revenue >= t.monthly_revenue_target * 0.9 THEN 'AT RISK'
        ELSE 'BEHIND'
    END AS status

FROM current_metrics c, prior_month p, ytd_metrics y, targets t;
```

### Board Meeting Summary

```sql
WITH quarterly_metrics AS (
    SELECT 
        DATE_TRUNC('quarter', order_date) AS quarter,
        SUM(total) AS revenue,
        SUM(total - cost) AS gross_profit,
        COUNT(DISTINCT id) AS orders,
        COUNT(DISTINCT customer_id) AS customers
    FROM orders
    WHERE status = 'completed'
      AND order_date >= DATE_TRUNC('year', CURRENT_DATE) - INTERVAL '2 years'
    GROUP BY DATE_TRUNC('quarter', order_date)
),
customer_metrics AS (
    SELECT 
        DATE_TRUNC('quarter', created_at) AS quarter,
        COUNT(*) AS new_customers,
        SUM(CASE WHEN source = 'organic' THEN 1 ELSE 0 END) AS organic_customers,
        SUM(CASE WHEN source = 'paid' THEN 1 ELSE 0 END) AS paid_customers
    FROM customers
    WHERE created_at >= DATE_TRUNC('year', CURRENT_DATE) - INTERVAL '2 years'
    GROUP BY DATE_TRUNC('quarter', created_at)
)
SELECT 
    TO_CHAR(qm.quarter, 'YYYY "Q"Q') AS quarter,
    
    ROUND(qm.revenue / 1000000, 2) AS revenue_millions,
    ROUND(qm.gross_profit / 1000000, 2) AS gross_profit_millions,
    ROUND(100.0 * qm.gross_profit / qm.revenue, 1) AS gross_margin_pct,
    
    qm.orders,
    ROUND(qm.revenue / qm.orders, 2) AS aov,
    
    qm.customers AS active_customers,
    cm.new_customers,
    ROUND(100.0 * cm.organic_customers / cm.new_customers, 1) AS organic_pct,
    
    ROUND(100.0 * (qm.revenue - LAG(qm.revenue, 4) OVER (ORDER BY qm.quarter)) / 
        NULLIF(LAG(qm.revenue, 4) OVER (ORDER BY qm.quarter), 0), 1) AS yoy_growth,
    
    ROUND(100.0 * (qm.revenue - LAG(qm.revenue) OVER (ORDER BY qm.quarter)) / 
        NULLIF(LAG(qm.revenue) OVER (ORDER BY qm.quarter), 0), 1) AS qoq_growth

FROM quarterly_metrics qm
LEFT JOIN customer_metrics cm ON qm.quarter = cm.quarter
ORDER BY qm.quarter DESC
LIMIT 8;
```

## Sales Reports

### Sales Team Performance

```sql
WITH sales_data AS (
    SELECT 
        sr.id AS rep_id,
        sr.name AS rep_name,
        sr.team,
        sr.quota AS monthly_quota,
        
        COUNT(DISTINCT o.id) AS deals_closed,
        SUM(o.total) AS revenue,
        COUNT(DISTINCT o.customer_id) AS customers_won,
        AVG(o.total) AS avg_deal_size,
        
        SUM(CASE WHEN o.is_new_customer THEN o.total ELSE 0 END) AS new_business,
        SUM(CASE WHEN NOT o.is_new_customer THEN o.total ELSE 0 END) AS expansion
        
    FROM sales_reps sr
    LEFT JOIN orders o ON sr.id = o.sales_rep_id
        AND o.order_date >= DATE_TRUNC('month', CURRENT_DATE)
        AND o.status = 'completed'
    GROUP BY sr.id, sr.name, sr.team, sr.quota
),
pipeline AS (
    SELECT 
        sales_rep_id,
        SUM(expected_value) AS pipeline_value,
        SUM(CASE WHEN stage = 'negotiation' THEN expected_value ELSE 0 END) AS late_stage
    FROM opportunities
    WHERE status = 'open'
    GROUP BY sales_rep_id
)
SELECT 
    sd.rep_name,
    sd.team,
    
    sd.deals_closed,
    ROUND(sd.revenue, 2) AS revenue,
    sd.monthly_quota AS quota,
    ROUND(100.0 * sd.revenue / NULLIF(sd.monthly_quota, 0), 1) AS attainment_pct,
    
    ROUND(sd.avg_deal_size, 2) AS avg_deal,
    sd.customers_won AS new_logos,
    
    ROUND(sd.new_business, 2) AS new_business,
    ROUND(sd.expansion, 2) AS expansion,
    
    ROUND(p.pipeline_value, 2) AS pipeline,
    ROUND(p.late_stage, 2) AS late_stage_pipeline,
    
    RANK() OVER (ORDER BY sd.revenue DESC) AS rank,
    
    CASE 
        WHEN sd.revenue >= sd.monthly_quota THEN 'EXCEEDING'
        WHEN sd.revenue >= sd.monthly_quota * 0.8 THEN 'ON TRACK'
        WHEN sd.revenue >= sd.monthly_quota * 0.5 THEN 'AT RISK'
        ELSE 'BEHIND'
    END AS status

FROM sales_data sd
LEFT JOIN pipeline p ON sd.rep_id = p.sales_rep_id
ORDER BY sd.revenue DESC;
```

### Sales Pipeline Report

```sql
WITH pipeline_stages AS (
    SELECT 
        stage,
        stage_order,
        COUNT(*) AS opportunity_count,
        SUM(expected_value) AS total_value,
        AVG(probability) AS avg_probability,
        SUM(expected_value * probability / 100) AS weighted_value,
        AVG(EXTRACT(DAYS FROM (CURRENT_DATE - created_at))) AS avg_age_days
    FROM opportunities
    WHERE status = 'open'
    GROUP BY stage, stage_order
),
conversion_rates AS (
    SELECT 
        from_stage,
        to_stage,
        COUNT(*) FILTER (WHERE converted) * 100.0 / COUNT(*) AS conversion_rate
    FROM stage_transitions
    WHERE transition_date >= CURRENT_DATE - INTERVAL '90 days'
    GROUP BY from_stage, to_stage
)
SELECT 
    ps.stage,
    ps.opportunity_count AS opps,
    ROUND(ps.total_value, 0) AS total_value,
    ROUND(ps.avg_probability, 0) AS avg_prob_pct,
    ROUND(ps.weighted_value, 0) AS weighted_value,
    ROUND(ps.avg_age_days, 0) AS avg_days_in_stage,
    
    ROUND(cr.conversion_rate, 1) AS stage_conversion_rate,
    
    ROUND(100.0 * ps.total_value / SUM(ps.total_value) OVER (), 1) AS pct_of_pipeline,
    
    SUM(ps.weighted_value) OVER (ORDER BY ps.stage_order) AS cumulative_weighted

FROM pipeline_stages ps
LEFT JOIN conversion_rates cr ON ps.stage = cr.from_stage
ORDER BY ps.stage_order;
```

## Marketing Reports

### Campaign ROI Report

```sql
WITH campaign_performance AS (
    SELECT 
        c.id AS campaign_id,
        c.name AS campaign_name,
        c.channel,
        c.start_date,
        c.budget,
        c.spend,
        
        COUNT(DISTINCT v.visitor_id) AS unique_visitors,
        COUNT(DISTINCT l.id) AS leads_generated,
        COUNT(DISTINCT CASE WHEN l.status = 'qualified' THEN l.id END) AS qualified_leads,
        COUNT(DISTINCT o.id) AS conversions,
        SUM(o.total) AS attributed_revenue
        
    FROM campaigns c
    LEFT JOIN campaign_visits v ON c.id = v.campaign_id
    LEFT JOIN leads l ON v.visitor_id = l.visitor_id AND l.source_campaign_id = c.id
    LEFT JOIN orders o ON l.id = o.lead_id AND o.status = 'completed'
    
    WHERE c.start_date >= DATE_TRUNC('quarter', CURRENT_DATE)
    GROUP BY c.id, c.name, c.channel, c.start_date, c.budget, c.spend
)
SELECT 
    campaign_name,
    channel,
    TO_CHAR(start_date, 'YYYY-MM-DD') AS started,
    
    ROUND(budget, 0) AS budget,
    ROUND(spend, 0) AS spend,
    ROUND(100.0 * spend / NULLIF(budget, 0), 1) AS budget_utilized_pct,
    
    unique_visitors AS visitors,
    leads_generated AS leads,
    ROUND(100.0 * leads_generated / NULLIF(unique_visitors, 0), 2) AS visitor_to_lead_pct,
    
    qualified_leads,
    ROUND(100.0 * qualified_leads / NULLIF(leads_generated, 0), 1) AS lead_qualification_rate,
    
    conversions,
    ROUND(100.0 * conversions / NULLIF(qualified_leads, 0), 1) AS close_rate,
    
    ROUND(attributed_revenue, 0) AS revenue,
    ROUND(spend / NULLIF(leads_generated, 0), 2) AS cost_per_lead,
    ROUND(spend / NULLIF(conversions, 0), 2) AS cost_per_acquisition,
    
    ROUND((attributed_revenue - spend) / NULLIF(spend, 0) * 100, 1) AS roi_pct,
    ROUND(attributed_revenue / NULLIF(spend, 0), 2) AS roas

FROM campaign_performance
ORDER BY attributed_revenue DESC;
```

### Channel Attribution Report

```sql
WITH touchpoint_attribution AS (
    SELECT 
        channel,
        
        COUNT(DISTINCT conversion_id) AS total_conversions,
        SUM(conversion_value) AS total_revenue,
        
        SUM(first_touch_credit) AS first_touch_conversions,
        SUM(last_touch_credit) AS last_touch_conversions,
        SUM(linear_credit) AS linear_conversions,
        
        SUM(first_touch_credit * conversion_value) AS first_touch_revenue,
        SUM(last_touch_credit * conversion_value) AS last_touch_revenue,
        SUM(linear_credit * conversion_value) AS linear_revenue
        
    FROM (
        SELECT 
            mt.channel,
            mt.conversion_id,
            c.value AS conversion_value,
            CASE WHEN mt.touch_order = 1 THEN 1.0 ELSE 0.0 END AS first_touch_credit,
            CASE WHEN mt.is_last_touch THEN 1.0 ELSE 0.0 END AS last_touch_credit,
            1.0 / mt.touches_in_journey AS linear_credit
        FROM marketing_touches mt
        JOIN conversions c ON mt.conversion_id = c.id
        WHERE c.conversion_date >= DATE_TRUNC('month', CURRENT_DATE)
    ) attributed
    GROUP BY channel
)
SELECT 
    channel,
    
    total_conversions,
    ROUND(total_revenue, 0) AS total_revenue,
    
    ROUND(first_touch_conversions, 1) AS first_touch_conv,
    ROUND(first_touch_revenue, 0) AS first_touch_rev,
    
    ROUND(last_touch_conversions, 1) AS last_touch_conv,
    ROUND(last_touch_revenue, 0) AS last_touch_rev,
    
    ROUND(linear_conversions, 1) AS linear_conv,
    ROUND(linear_revenue, 0) AS linear_rev,
    
    ROUND(100.0 * linear_revenue / SUM(linear_revenue) OVER (), 1) AS pct_of_revenue

FROM touchpoint_attribution
ORDER BY linear_revenue DESC;
```

## Financial Reports

### Profit and Loss Statement

```sql
WITH monthly_pl AS (
    SELECT 
        DATE_TRUNC('month', transaction_date) AS month,
        
        SUM(CASE WHEN category = 'Revenue' THEN amount ELSE 0 END) AS revenue,
        SUM(CASE WHEN category = 'Cost of Goods Sold' THEN amount ELSE 0 END) AS cogs,
        SUM(CASE WHEN category IN ('Sales & Marketing') THEN amount ELSE 0 END) AS sales_marketing,
        SUM(CASE WHEN category IN ('Research & Development') THEN amount ELSE 0 END) AS rd,
        SUM(CASE WHEN category IN ('General & Administrative') THEN amount ELSE 0 END) AS ga,
        SUM(CASE WHEN category = 'Other Income' THEN amount ELSE 0 END) AS other_income,
        SUM(CASE WHEN category = 'Interest Expense' THEN amount ELSE 0 END) AS interest,
        SUM(CASE WHEN category = 'Taxes' THEN amount ELSE 0 END) AS taxes
        
    FROM transactions
    WHERE transaction_date >= DATE_TRUNC('year', CURRENT_DATE)
    GROUP BY DATE_TRUNC('month', transaction_date)
)
SELECT 
    TO_CHAR(month, 'Mon YYYY') AS period,
    
    ROUND(revenue, 0) AS revenue,
    ROUND(cogs, 0) AS cogs,
    ROUND(revenue - cogs, 0) AS gross_profit,
    ROUND(100.0 * (revenue - cogs) / NULLIF(revenue, 0), 1) AS gross_margin_pct,
    
    ROUND(sales_marketing, 0) AS sales_marketing,
    ROUND(rd, 0) AS rd,
    ROUND(ga, 0) AS ga,
    ROUND(sales_marketing + rd + ga, 0) AS total_opex,
    
    ROUND(revenue - cogs - sales_marketing - rd - ga, 0) AS operating_income,
    ROUND(100.0 * (revenue - cogs - sales_marketing - rd - ga) / NULLIF(revenue, 0), 1) AS operating_margin_pct,
    
    ROUND(other_income - interest, 0) AS net_other,
    ROUND(revenue - cogs - sales_marketing - rd - ga + other_income - interest, 0) AS ebt,
    ROUND(taxes, 0) AS taxes,
    
    ROUND(revenue - cogs - sales_marketing - rd - ga + other_income - interest - taxes, 0) AS net_income,
    ROUND(100.0 * (revenue - cogs - sales_marketing - rd - ga + other_income - interest - taxes) / 
        NULLIF(revenue, 0), 1) AS net_margin_pct

FROM monthly_pl
ORDER BY month;
```

### Accounts Receivable Aging

```sql
WITH ar_aging AS (
    SELECT 
        c.name AS customer,
        i.invoice_number,
        i.invoice_date,
        i.due_date,
        i.amount,
        COALESCE(p.paid, 0) AS paid,
        i.amount - COALESCE(p.paid, 0) AS balance,
        CURRENT_DATE - i.due_date AS days_overdue
    FROM invoices i
    JOIN customers c ON i.customer_id = c.id
    LEFT JOIN (
        SELECT invoice_id, SUM(amount) AS paid
        FROM payments
        WHERE status = 'completed'
        GROUP BY invoice_id
    ) p ON i.id = p.invoice_id
    WHERE i.status != 'paid'
      AND i.amount > COALESCE(p.paid, 0)
)
SELECT 
    customer,
    
    SUM(CASE WHEN days_overdue <= 0 THEN balance ELSE 0 END) AS current,
    SUM(CASE WHEN days_overdue BETWEEN 1 AND 30 THEN balance ELSE 0 END) AS "1-30_days",
    SUM(CASE WHEN days_overdue BETWEEN 31 AND 60 THEN balance ELSE 0 END) AS "31-60_days",
    SUM(CASE WHEN days_overdue BETWEEN 61 AND 90 THEN balance ELSE 0 END) AS "61-90_days",
    SUM(CASE WHEN days_overdue > 90 THEN balance ELSE 0 END) AS "over_90_days",
    SUM(balance) AS total_outstanding,
    
    MAX(days_overdue) AS oldest_days,
    COUNT(DISTINCT invoice_number) AS open_invoices

FROM ar_aging
GROUP BY customer
ORDER BY SUM(balance) DESC;
```

## Customer Reports

### Customer Health Scorecard

```sql
WITH customer_activity AS (
    SELECT 
        c.id AS customer_id,
        c.name,
        c.created_at AS customer_since,
        c.tier,
        
        COUNT(DISTINCT o.id) AS total_orders,
        SUM(o.total) AS lifetime_value,
        MAX(o.order_date) AS last_order,
        AVG(o.total) AS avg_order_value,
        
        COUNT(DISTINCT o.id) FILTER (WHERE o.order_date >= CURRENT_DATE - 90) AS orders_90d,
        SUM(o.total) FILTER (WHERE o.order_date >= CURRENT_DATE - 90) AS revenue_90d
        
    FROM customers c
    LEFT JOIN orders o ON c.id = o.customer_id AND o.status = 'completed'
    GROUP BY c.id, c.name, c.created_at, c.tier
),
support_activity AS (
    SELECT 
        customer_id,
        COUNT(*) AS tickets_90d,
        AVG(satisfaction_score) AS avg_csat
    FROM support_tickets
    WHERE created_at >= CURRENT_DATE - 90
    GROUP BY customer_id
),
engagement AS (
    SELECT 
        customer_id,
        COUNT(*) AS logins_30d
    FROM user_sessions
    WHERE session_start >= CURRENT_DATE - 30
    GROUP BY customer_id
)
SELECT 
    ca.name AS customer,
    ca.tier,
    ROUND(ca.lifetime_value, 0) AS ltv,
    
    ca.orders_90d,
    ROUND(ca.revenue_90d, 0) AS revenue_90d,
    CURRENT_DATE - ca.last_order::date AS days_since_order,
    
    COALESCE(sa.tickets_90d, 0) AS support_tickets,
    ROUND(sa.avg_csat, 1) AS csat_score,
    
    COALESCE(e.logins_30d, 0) AS logins_30d,
    
    CASE 
        WHEN ca.orders_90d >= 3 AND COALESCE(sa.avg_csat, 5) >= 4 THEN 100
        WHEN ca.orders_90d >= 2 AND COALESCE(sa.avg_csat, 5) >= 3 THEN 80
        WHEN ca.orders_90d >= 1 THEN 60
        WHEN CURRENT_DATE - ca.last_order::date <= 180 THEN 40
        ELSE 20
    END AS health_score,
    
    CASE 
        WHEN ca.orders_90d >= 3 AND COALESCE(sa.avg_csat, 5) >= 4 THEN 'Healthy'
        WHEN ca.orders_90d >= 1 AND CURRENT_DATE - ca.last_order::date <= 60 THEN 'Active'
        WHEN CURRENT_DATE - ca.last_order::date <= 180 THEN 'At Risk'
        ELSE 'Churned'
    END AS status

FROM customer_activity ca
LEFT JOIN support_activity sa ON ca.customer_id = sa.customer_id
LEFT JOIN engagement e ON ca.customer_id = e.customer_id
WHERE ca.lifetime_value > 0
ORDER BY ca.lifetime_value DESC;
```

### Customer Cohort Report

```sql
WITH cohorts AS (
    SELECT 
        customer_id,
        DATE_TRUNC('month', MIN(order_date)) AS cohort_month
    FROM orders
    WHERE status = 'completed'
    GROUP BY customer_id
),
monthly_revenue AS (
    SELECT 
        c.cohort_month,
        DATE_TRUNC('month', o.order_date) AS order_month,
        COUNT(DISTINCT o.customer_id) AS customers,
        SUM(o.total) AS revenue
    FROM orders o
    JOIN cohorts c ON o.customer_id = c.customer_id
    WHERE o.status = 'completed'
    GROUP BY c.cohort_month, DATE_TRUNC('month', o.order_date)
),
cohort_sizes AS (
    SELECT cohort_month, COUNT(*) AS size FROM cohorts GROUP BY cohort_month
)
SELECT 
    TO_CHAR(mr.cohort_month, 'YYYY-MM') AS cohort,
    cs.size AS cohort_size,
    EXTRACT(MONTH FROM AGE(mr.order_month, mr.cohort_month)) AS month_number,
    mr.customers AS active_customers,
    ROUND(100.0 * mr.customers / cs.size, 1) AS retention_pct,
    ROUND(mr.revenue, 0) AS revenue,
    ROUND(mr.revenue / mr.customers, 2) AS revenue_per_customer

FROM monthly_revenue mr
JOIN cohort_sizes cs ON mr.cohort_month = cs.cohort_month
WHERE mr.cohort_month >= DATE_TRUNC('year', CURRENT_DATE) - INTERVAL '1 year'
ORDER BY mr.cohort_month, month_number;
```

## Report Scheduling Helpers

### Generate Report Parameters

```sql
SELECT 
    DATE_TRUNC('month', CURRENT_DATE) AS current_month_start,
    DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month' - INTERVAL '1 day' AS current_month_end,
    DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month' AS prior_month_start,
    DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 day' AS prior_month_end,
    DATE_TRUNC('quarter', CURRENT_DATE) AS current_quarter_start,
    DATE_TRUNC('year', CURRENT_DATE) AS current_year_start,
    DATE_TRUNC('year', CURRENT_DATE) - INTERVAL '1 year' AS prior_year_start;
```

### Create Report Snapshot

```sql
INSERT INTO report_snapshots (
    report_name,
    snapshot_date,
    parameters,
    data
)
SELECT 
    'monthly_summary',
    CURRENT_DATE,
    jsonb_build_object(
        'period_start', DATE_TRUNC('month', CURRENT_DATE),
        'period_end', CURRENT_DATE
    ),
    (
        SELECT jsonb_agg(row_to_json(t))
        FROM (
            SELECT * FROM monthly_summary_view
        ) t
    );
```
