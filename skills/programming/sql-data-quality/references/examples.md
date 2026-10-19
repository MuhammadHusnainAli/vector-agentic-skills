# SQL Data Quality Examples

Real-world data quality scenarios with detection and remediation queries.

## Scenario 1: Customer Data Quality Audit

### Profile the Data

```sql
WITH customer_profile AS (
    SELECT 
        COUNT(*) AS total_records,
        COUNT(email) AS has_email,
        COUNT(DISTINCT email) AS unique_emails,
        COUNT(phone) AS has_phone,
        COUNT(address_line1) AS has_address,
        COUNT(city) AS has_city,
        COUNT(state) AS has_state,
        COUNT(zip_code) AS has_zip
    FROM customers
)
SELECT 
    'email' AS field,
    has_email AS populated,
    total_records - has_email AS missing,
    ROUND(100.0 * has_email / total_records, 1) AS completeness_pct,
    total_records - unique_emails AS duplicates
FROM customer_profile

UNION ALL

SELECT 
    'phone',
    has_phone,
    total_records - has_phone,
    ROUND(100.0 * has_phone / total_records, 1),
    NULL
FROM customer_profile

UNION ALL

SELECT 
    'full_address',
    LEAST(has_address, has_city, has_state, has_zip),
    total_records - LEAST(has_address, has_city, has_state, has_zip),
    ROUND(100.0 * LEAST(has_address, has_city, has_state, has_zip) / total_records, 1),
    NULL
FROM customer_profile;
```

### Validate Email Format

```sql
SELECT 
    id,
    email,
    CASE 
        WHEN email IS NULL THEN 'Missing'
        WHEN email !~ '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$' THEN 'Invalid Format'
        WHEN email LIKE '%@example.com' OR email LIKE '%@test.com' THEN 'Test Email'
        WHEN email LIKE '%..' OR email LIKE '..%' THEN 'Suspicious'
        ELSE 'Valid'
    END AS email_status
FROM customers
WHERE email IS NULL 
   OR email !~ '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
   OR email LIKE '%@example.com' 
   OR email LIKE '%@test.com';
```

### Find and Merge Duplicates

```sql
WITH duplicate_customers AS (
    SELECT 
        email,
        COUNT(*) AS count,
        MIN(id) AS primary_id,
        ARRAY_AGG(id ORDER BY created_at) AS all_ids,
        MAX(last_order_date) AS most_recent_order,
        SUM(total_orders) AS combined_orders,
        SUM(lifetime_value) AS combined_value
    FROM customers
    WHERE email IS NOT NULL
    GROUP BY LOWER(TRIM(email))
    HAVING COUNT(*) > 1
)
SELECT 
    dc.email,
    dc.count AS duplicate_count,
    dc.primary_id AS keep_record,
    dc.all_ids AS merge_records,
    dc.combined_orders,
    dc.combined_value,
    c.name AS primary_name,
    c.created_at AS primary_created
FROM duplicate_customers dc
JOIN customers c ON dc.primary_id = c.id
ORDER BY dc.count DESC, dc.combined_value DESC;
```

### Clean Customer Data

```sql
UPDATE customers
SET 
    email = LOWER(TRIM(email)),
    phone = REGEXP_REPLACE(phone, '[^0-9+]', '', 'g'),
    name = INITCAP(TRIM(REGEXP_REPLACE(name, '\s+', ' ', 'g'))),
    address_line1 = INITCAP(TRIM(address_line1)),
    city = INITCAP(TRIM(city)),
    state = UPPER(TRIM(state)),
    zip_code = TRIM(zip_code)
WHERE 
    email != LOWER(TRIM(email))
    OR phone != REGEXP_REPLACE(phone, '[^0-9+]', '', 'g')
    OR name != INITCAP(TRIM(REGEXP_REPLACE(name, '\s+', ' ', 'g')));
```

## Scenario 2: Order Data Validation

### Check for Orphan Records

```sql
SELECT 'Orders without customers' AS issue, COUNT(*) AS count
FROM orders o
LEFT JOIN customers c ON o.customer_id = c.id
WHERE c.id IS NULL

UNION ALL

SELECT 'Order items without orders', COUNT(*)
FROM order_items oi
LEFT JOIN orders o ON oi.order_id = o.id
WHERE o.id IS NULL

UNION ALL

SELECT 'Order items without products', COUNT(*)
FROM order_items oi
LEFT JOIN products p ON oi.product_id = p.id
WHERE p.id IS NULL;
```

### Validate Order Totals

```sql
WITH calculated_totals AS (
    SELECT 
        o.id AS order_id,
        o.total AS stored_total,
        o.subtotal AS stored_subtotal,
        o.tax AS stored_tax,
        o.shipping AS stored_shipping,
        SUM(oi.quantity * oi.unit_price) AS calculated_subtotal,
        SUM(oi.quantity * oi.unit_price) * 0.08 AS calculated_tax,
        o.shipping AS shipping
    FROM orders o
    JOIN order_items oi ON o.id = oi.order_id
    GROUP BY o.id, o.total, o.subtotal, o.tax, o.shipping
)
SELECT 
    order_id,
    stored_total,
    calculated_subtotal + calculated_tax + shipping AS expected_total,
    stored_total - (calculated_subtotal + calculated_tax + shipping) AS discrepancy,
    ABS(stored_total - (calculated_subtotal + calculated_tax + shipping)) > 0.01 AS has_error
FROM calculated_totals
WHERE ABS(stored_total - (calculated_subtotal + calculated_tax + shipping)) > 0.01
ORDER BY ABS(stored_total - (calculated_subtotal + calculated_tax + shipping)) DESC;
```

### Check Date Consistency

```sql
SELECT 
    id,
    order_date,
    ship_date,
    delivery_date,
    CASE 
        WHEN order_date > CURRENT_DATE THEN 'Future order date'
        WHEN ship_date < order_date THEN 'Ship before order'
        WHEN delivery_date < ship_date THEN 'Delivered before shipped'
        WHEN delivery_date < order_date THEN 'Delivered before ordered'
        WHEN status = 'delivered' AND delivery_date IS NULL THEN 'Missing delivery date'
        WHEN status = 'shipped' AND ship_date IS NULL THEN 'Missing ship date'
        ELSE 'OK'
    END AS date_issue
FROM orders
WHERE 
    order_date > CURRENT_DATE
    OR ship_date < order_date
    OR delivery_date < ship_date
    OR (status = 'delivered' AND delivery_date IS NULL)
    OR (status = 'shipped' AND ship_date IS NULL);
```

### Find Pricing Anomalies

```sql
WITH product_stats AS (
    SELECT 
        product_id,
        AVG(unit_price) AS avg_price,
        STDDEV(unit_price) AS stddev_price,
        MIN(unit_price) AS min_price,
        MAX(unit_price) AS max_price
    FROM order_items
    GROUP BY product_id
)
SELECT 
    oi.order_id,
    oi.product_id,
    p.name AS product_name,
    oi.unit_price AS charged_price,
    ps.avg_price AS average_price,
    ROUND((oi.unit_price - ps.avg_price) / NULLIF(ps.stddev_price, 0), 2) AS z_score,
    CASE 
        WHEN oi.unit_price <= 0 THEN 'Zero or negative price'
        WHEN oi.unit_price < ps.avg_price * 0.5 THEN 'Suspicious discount'
        WHEN oi.unit_price > ps.avg_price * 2 THEN 'Overcharge'
        ELSE 'Normal'
    END AS issue
FROM order_items oi
JOIN products p ON oi.product_id = p.id
JOIN product_stats ps ON oi.product_id = ps.product_id
WHERE 
    oi.unit_price <= 0
    OR oi.unit_price < ps.avg_price * 0.5
    OR oi.unit_price > ps.avg_price * 2
ORDER BY ABS(oi.unit_price - ps.avg_price) DESC;
```

## Scenario 3: Product Catalog Quality

### Find Missing Product Information

```sql
SELECT 
    id,
    sku,
    name,
    CASE WHEN description IS NULL OR LENGTH(description) < 50 THEN 'Missing/Short' ELSE 'OK' END AS description_status,
    CASE WHEN category_id IS NULL THEN 'Missing' ELSE 'OK' END AS category_status,
    CASE WHEN price IS NULL OR price <= 0 THEN 'Invalid' ELSE 'OK' END AS price_status,
    CASE WHEN image_url IS NULL THEN 'Missing' ELSE 'OK' END AS image_status,
    CASE 
        WHEN (description IS NULL OR LENGTH(description) < 50) AND category_id IS NULL AND image_url IS NULL 
        THEN 'Critical'
        WHEN (description IS NULL OR LENGTH(description) < 50) OR category_id IS NULL OR image_url IS NULL 
        THEN 'Warning'
        ELSE 'Complete'
    END AS overall_status
FROM products
WHERE 
    description IS NULL 
    OR LENGTH(description) < 50
    OR category_id IS NULL
    OR price IS NULL 
    OR price <= 0
    OR image_url IS NULL
ORDER BY 
    CASE 
        WHEN (description IS NULL OR LENGTH(description) < 50) AND category_id IS NULL AND image_url IS NULL THEN 1
        ELSE 2
    END,
    id;
```

### Check SKU Format and Uniqueness

```sql
WITH sku_analysis AS (
    SELECT 
        sku,
        COUNT(*) AS occurrences,
        CASE 
            WHEN sku IS NULL THEN 'Missing'
            WHEN LENGTH(sku) < 5 THEN 'Too short'
            WHEN sku !~ '^[A-Z]{2,3}-[0-9]{4,6}$' THEN 'Invalid format'
            ELSE 'Valid'
        END AS format_status
    FROM products
    GROUP BY sku
)
SELECT 
    sku,
    occurrences,
    format_status,
    CASE WHEN occurrences > 1 THEN 'Duplicate' ELSE 'Unique' END AS uniqueness
FROM sku_analysis
WHERE occurrences > 1 OR format_status != 'Valid'
ORDER BY occurrences DESC, sku;
```

### Category Hierarchy Validation

```sql
WITH RECURSIVE category_tree AS (
    SELECT id, name, parent_id, 1 AS depth, ARRAY[id] AS path
    FROM categories
    WHERE parent_id IS NULL
    
    UNION ALL
    
    SELECT c.id, c.name, c.parent_id, ct.depth + 1, ct.path || c.id
    FROM categories c
    JOIN category_tree ct ON c.parent_id = ct.id
    WHERE NOT (c.id = ANY(ct.path))
)
SELECT 
    c.id,
    c.name,
    c.parent_id,
    CASE 
        WHEN c.parent_id IS NOT NULL AND p.id IS NULL THEN 'Orphan - parent not found'
        WHEN c.id = c.parent_id THEN 'Self-referencing'
        WHEN ct.id IS NULL AND c.parent_id IS NOT NULL THEN 'Circular reference'
        ELSE 'Valid'
    END AS status
FROM categories c
LEFT JOIN categories p ON c.parent_id = p.id
LEFT JOIN category_tree ct ON c.id = ct.id
WHERE 
    (c.parent_id IS NOT NULL AND p.id IS NULL)
    OR c.id = c.parent_id
    OR (ct.id IS NULL AND c.parent_id IS NOT NULL);
```

## Scenario 4: Time Series Data Quality

### Detect Gaps in Time Series

```sql
WITH date_series AS (
    SELECT generate_series(
        (SELECT MIN(date) FROM daily_metrics),
        (SELECT MAX(date) FROM daily_metrics),
        '1 day'::interval
    )::date AS expected_date
),
gaps AS (
    SELECT 
        ds.expected_date,
        dm.date AS actual_date,
        LAG(dm.date) OVER (ORDER BY ds.expected_date) AS prev_date
    FROM date_series ds
    LEFT JOIN daily_metrics dm ON ds.expected_date = dm.date
)
SELECT 
    expected_date AS missing_date,
    prev_date AS last_data_date,
    expected_date - prev_date - 1 AS gap_days
FROM gaps
WHERE actual_date IS NULL
ORDER BY expected_date;
```

### Detect Outliers in Metrics

```sql
WITH stats AS (
    SELECT 
        metric_name,
        AVG(value) AS mean,
        STDDEV(value) AS stddev,
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY value) AS q1,
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY value) AS q3
    FROM metrics
    GROUP BY metric_name
),
iqr_bounds AS (
    SELECT 
        metric_name,
        mean,
        stddev,
        q1,
        q3,
        q3 - q1 AS iqr,
        q1 - 1.5 * (q3 - q1) AS lower_bound,
        q3 + 1.5 * (q3 - q1) AS upper_bound
    FROM stats
)
SELECT 
    m.date,
    m.metric_name,
    m.value,
    b.mean,
    b.lower_bound,
    b.upper_bound,
    CASE 
        WHEN m.value < b.lower_bound THEN 'Below lower bound'
        WHEN m.value > b.upper_bound THEN 'Above upper bound'
        WHEN ABS(m.value - b.mean) > 3 * b.stddev THEN '3+ std deviations'
        ELSE 'Normal'
    END AS outlier_status,
    (m.value - b.mean) / NULLIF(b.stddev, 0) AS z_score
FROM metrics m
JOIN iqr_bounds b ON m.metric_name = b.metric_name
WHERE 
    m.value < b.lower_bound 
    OR m.value > b.upper_bound
    OR ABS(m.value - b.mean) > 3 * b.stddev
ORDER BY ABS((m.value - b.mean) / NULLIF(b.stddev, 0)) DESC;
```

### Detect Sudden Changes

```sql
WITH changes AS (
    SELECT 
        date,
        value,
        LAG(value) OVER (ORDER BY date) AS prev_value,
        AVG(value) OVER (ORDER BY date ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING) AS avg_prev_7d
    FROM daily_metrics
)
SELECT 
    date,
    value,
    prev_value,
    avg_prev_7d,
    ROUND(100.0 * (value - prev_value) / NULLIF(prev_value, 0), 2) AS day_over_day_pct,
    ROUND(100.0 * (value - avg_prev_7d) / NULLIF(avg_prev_7d, 0), 2) AS vs_7d_avg_pct
FROM changes
WHERE 
    ABS(value - prev_value) / NULLIF(prev_value, 0) > 0.5
    OR ABS(value - avg_prev_7d) / NULLIF(avg_prev_7d, 0) > 0.5
ORDER BY ABS(value - prev_value) DESC;
```

## Scenario 5: Automated Data Quality Checks

### Create Quality Check Framework

```sql
CREATE TABLE data_quality_rules (
    id SERIAL PRIMARY KEY,
    rule_name VARCHAR(100) NOT NULL,
    table_name VARCHAR(100) NOT NULL,
    check_query TEXT NOT NULL,
    severity VARCHAR(20) DEFAULT 'warning',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE data_quality_results (
    id SERIAL PRIMARY KEY,
    rule_id INTEGER REFERENCES data_quality_rules(id),
    run_date DATE DEFAULT CURRENT_DATE,
    passed INTEGER,
    failed INTEGER,
    execution_time_ms INTEGER,
    sample_failures JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Sample Quality Rules

```sql
INSERT INTO data_quality_rules (rule_name, table_name, check_query, severity) VALUES
('customer_email_not_null', 'customers', 
 'SELECT id, email FROM customers WHERE email IS NULL', 'critical'),

('customer_email_valid_format', 'customers',
 'SELECT id, email FROM customers WHERE email !~ ''^[^@]+@[^@]+\.[^@]+$''', 'warning'),

('order_total_positive', 'orders',
 'SELECT id, total FROM orders WHERE total <= 0', 'critical'),

('order_dates_consistent', 'orders',
 'SELECT id, order_date, ship_date FROM orders WHERE ship_date < order_date', 'critical'),

('product_has_category', 'products',
 'SELECT id, name FROM products WHERE category_id IS NULL', 'warning');
```

### Run All Quality Checks

```sql
WITH rule_results AS (
    SELECT 
        r.id AS rule_id,
        r.rule_name,
        r.table_name,
        r.severity,
        CURRENT_DATE AS run_date
    FROM data_quality_rules r
    WHERE r.is_active = true
)
INSERT INTO data_quality_results (rule_id, run_date, passed, failed, sample_failures)
SELECT 
    rule_id,
    run_date,
    total_count - failed_count AS passed,
    failed_count AS failed,
    sample_json AS sample_failures
FROM rule_results;
```

### Quality Dashboard Query

```sql
SELECT 
    r.table_name,
    r.rule_name,
    r.severity,
    res.run_date,
    res.passed,
    res.failed,
    ROUND(100.0 * res.passed / NULLIF(res.passed + res.failed, 0), 2) AS pass_rate,
    CASE 
        WHEN res.failed = 0 THEN 'PASS'
        WHEN r.severity = 'critical' AND res.failed > 0 THEN 'CRITICAL FAIL'
        WHEN res.failed * 100.0 / (res.passed + res.failed) > 5 THEN 'FAIL'
        ELSE 'WARNING'
    END AS status,
    LAG(res.failed) OVER (PARTITION BY res.rule_id ORDER BY res.run_date) AS prev_failed,
    res.failed - LAG(res.failed) OVER (PARTITION BY res.rule_id ORDER BY res.run_date) AS trend
FROM data_quality_results res
JOIN data_quality_rules r ON res.rule_id = r.id
WHERE res.run_date >= CURRENT_DATE - 7
ORDER BY 
    CASE r.severity WHEN 'critical' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END,
    res.failed DESC;
```
