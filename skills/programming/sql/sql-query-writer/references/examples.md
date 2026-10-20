# SQL Query Writer Examples

Production-ready query examples organized by common business scenarios.

## E-Commerce Queries

### Get Customer Order Summary

```sql
SELECT 
    c.id AS customer_id,
    c.name AS customer_name,
    c.email,
    COUNT(DISTINCT o.id) AS total_orders,
    COALESCE(SUM(o.total_amount), 0) AS lifetime_value,
    MIN(o.order_date) AS first_order_date,
    MAX(o.order_date) AS last_order_date,
    COALESCE(AVG(o.total_amount), 0) AS avg_order_value
FROM customers c
LEFT JOIN orders o ON c.id = o.customer_id AND o.status != 'cancelled'
GROUP BY c.id, c.name, c.email
ORDER BY lifetime_value DESC;
```

### Find Abandoned Carts

```sql
SELECT 
    c.id AS cart_id,
    c.customer_id,
    cu.email,
    c.created_at,
    COUNT(ci.id) AS item_count,
    SUM(ci.quantity * ci.unit_price) AS cart_value,
    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - c.updated_at)) / 3600 AS hours_since_update
FROM carts c
JOIN customers cu ON c.customer_id = cu.id
JOIN cart_items ci ON c.id = ci.cart_id
WHERE c.status = 'active'
  AND c.updated_at < CURRENT_TIMESTAMP - INTERVAL '24 hours'
  AND NOT EXISTS (
      SELECT 1 FROM orders o 
      WHERE o.customer_id = c.customer_id 
        AND o.created_at > c.created_at
  )
GROUP BY c.id, c.customer_id, cu.email, c.created_at, c.updated_at
HAVING SUM(ci.quantity * ci.unit_price) > 50
ORDER BY cart_value DESC;
```

### Product Inventory Check

```sql
SELECT 
    p.id,
    p.sku,
    p.name,
    p.category_id,
    cat.name AS category_name,
    COALESCE(inv.quantity_on_hand, 0) AS current_stock,
    COALESCE(inv.reorder_point, 10) AS reorder_point,
    COALESCE(pending.quantity_ordered, 0) AS pending_orders,
    CASE 
        WHEN COALESCE(inv.quantity_on_hand, 0) <= 0 THEN 'Out of Stock'
        WHEN COALESCE(inv.quantity_on_hand, 0) <= COALESCE(inv.reorder_point, 10) THEN 'Low Stock'
        ELSE 'In Stock'
    END AS stock_status
FROM products p
LEFT JOIN categories cat ON p.category_id = cat.id
LEFT JOIN inventory inv ON p.id = inv.product_id
LEFT JOIN (
    SELECT product_id, SUM(quantity) AS quantity_ordered
    FROM order_items oi
    JOIN orders o ON oi.order_id = o.id
    WHERE o.status IN ('pending', 'processing')
    GROUP BY product_id
) pending ON p.id = pending.product_id
WHERE p.is_active = true
ORDER BY 
    CASE 
        WHEN COALESCE(inv.quantity_on_hand, 0) <= 0 THEN 1
        WHEN COALESCE(inv.quantity_on_hand, 0) <= COALESCE(inv.reorder_point, 10) THEN 2
        ELSE 3
    END,
    p.name;
```

### Best Selling Products by Category

```sql
WITH product_sales AS (
    SELECT 
        p.id AS product_id,
        p.name AS product_name,
        p.category_id,
        SUM(oi.quantity) AS units_sold,
        SUM(oi.quantity * oi.unit_price) AS revenue,
        COUNT(DISTINCT o.customer_id) AS unique_customers
    FROM products p
    JOIN order_items oi ON p.id = oi.product_id
    JOIN orders o ON oi.order_id = o.id
    WHERE o.status = 'completed'
      AND o.order_date >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY p.id, p.name, p.category_id
),
ranked_products AS (
    SELECT 
        *,
        ROW_NUMBER() OVER (PARTITION BY category_id ORDER BY revenue DESC) AS rank_in_category
    FROM product_sales
)
SELECT 
    c.name AS category_name,
    rp.product_name,
    rp.units_sold,
    rp.revenue,
    rp.unique_customers,
    rp.rank_in_category
FROM ranked_products rp
JOIN categories c ON rp.category_id = c.id
WHERE rp.rank_in_category <= 5
ORDER BY c.name, rp.rank_in_category;
```

## User Management Queries

### Find Inactive Users

```sql
SELECT 
    u.id,
    u.email,
    u.name,
    u.created_at AS registration_date,
    u.last_login_at,
    CURRENT_DATE - u.last_login_at::date AS days_since_login,
    COALESCE(activity.total_actions, 0) AS total_actions_30d
FROM users u
LEFT JOIN (
    SELECT user_id, COUNT(*) AS total_actions
    FROM user_activities
    WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY user_id
) activity ON u.id = activity.user_id
WHERE u.status = 'active'
  AND (u.last_login_at IS NULL OR u.last_login_at < CURRENT_DATE - INTERVAL '30 days')
ORDER BY u.last_login_at NULLS FIRST;
```

### User Role Permissions Summary

```sql
SELECT 
    u.id AS user_id,
    u.email,
    u.name,
    STRING_AGG(DISTINCT r.name, ', ' ORDER BY r.name) AS roles,
    STRING_AGG(DISTINCT p.name, ', ' ORDER BY p.name) AS permissions
FROM users u
JOIN user_roles ur ON u.id = ur.user_id
JOIN roles r ON ur.role_id = r.id
JOIN role_permissions rp ON r.id = rp.role_id
JOIN permissions p ON rp.permission_id = p.id
WHERE u.status = 'active'
GROUP BY u.id, u.email, u.name
ORDER BY u.name;
```

### Find Users with Specific Permission

```sql
SELECT DISTINCT 
    u.id,
    u.email,
    u.name,
    r.name AS role_name
FROM users u
JOIN user_roles ur ON u.id = ur.user_id
JOIN roles r ON ur.role_id = r.id
JOIN role_permissions rp ON r.id = rp.role_id
JOIN permissions p ON rp.permission_id = p.id
WHERE p.name = 'admin.users.delete'
  AND u.status = 'active'
ORDER BY u.name;
```

## Financial Queries

### Monthly Revenue Report

```sql
SELECT 
    DATE_TRUNC('month', transaction_date) AS month,
    COUNT(*) AS transaction_count,
    SUM(CASE WHEN type = 'credit' THEN amount ELSE 0 END) AS total_credits,
    SUM(CASE WHEN type = 'debit' THEN amount ELSE 0 END) AS total_debits,
    SUM(CASE WHEN type = 'credit' THEN amount ELSE -amount END) AS net_amount,
    AVG(amount) AS avg_transaction_amount
FROM transactions
WHERE transaction_date >= DATE_TRUNC('year', CURRENT_DATE)
  AND status = 'completed'
GROUP BY DATE_TRUNC('month', transaction_date)
ORDER BY month;
```

### Account Balance Calculation

```sql
WITH running_balance AS (
    SELECT 
        account_id,
        transaction_date,
        description,
        type,
        amount,
        SUM(
            CASE WHEN type = 'credit' THEN amount ELSE -amount END
        ) OVER (
            PARTITION BY account_id 
            ORDER BY transaction_date, id
            ROWS UNBOUNDED PRECEDING
        ) AS balance
    FROM transactions
    WHERE account_id = 12345
      AND status = 'completed'
)
SELECT 
    a.account_number,
    a.account_name,
    COALESCE(a.opening_balance, 0) AS opening_balance,
    rb.transaction_date,
    rb.description,
    rb.type,
    rb.amount,
    COALESCE(a.opening_balance, 0) + rb.balance AS current_balance
FROM accounts a
JOIN running_balance rb ON a.id = rb.account_id
ORDER BY rb.transaction_date, rb.balance;
```

### Overdue Invoices

```sql
SELECT 
    i.invoice_number,
    i.customer_id,
    c.name AS customer_name,
    c.email,
    i.amount,
    i.due_date,
    CURRENT_DATE - i.due_date AS days_overdue,
    COALESCE(p.total_paid, 0) AS amount_paid,
    i.amount - COALESCE(p.total_paid, 0) AS balance_due,
    CASE 
        WHEN CURRENT_DATE - i.due_date > 90 THEN 'Critical'
        WHEN CURRENT_DATE - i.due_date > 60 THEN 'Severe'
        WHEN CURRENT_DATE - i.due_date > 30 THEN 'Warning'
        ELSE 'Notice'
    END AS severity
FROM invoices i
JOIN customers c ON i.customer_id = c.id
LEFT JOIN (
    SELECT invoice_id, SUM(amount) AS total_paid
    FROM payments
    WHERE status = 'completed'
    GROUP BY invoice_id
) p ON i.id = p.invoice_id
WHERE i.status = 'sent'
  AND i.due_date < CURRENT_DATE
  AND i.amount > COALESCE(p.total_paid, 0)
ORDER BY days_overdue DESC, balance_due DESC;
```

## Analytics Queries

### Cohort Retention Analysis

```sql
WITH user_cohorts AS (
    SELECT 
        id AS user_id,
        DATE_TRUNC('month', created_at) AS cohort_month
    FROM users
),
user_activities AS (
    SELECT 
        user_id,
        DATE_TRUNC('month', activity_date) AS activity_month
    FROM activities
    GROUP BY user_id, DATE_TRUNC('month', activity_date)
),
cohort_data AS (
    SELECT 
        uc.cohort_month,
        ua.activity_month,
        EXTRACT(YEAR FROM AGE(ua.activity_month, uc.cohort_month)) * 12 +
        EXTRACT(MONTH FROM AGE(ua.activity_month, uc.cohort_month)) AS months_since_signup,
        COUNT(DISTINCT uc.user_id) AS active_users
    FROM user_cohorts uc
    JOIN user_activities ua ON uc.user_id = ua.user_id
    WHERE ua.activity_month >= uc.cohort_month
    GROUP BY uc.cohort_month, ua.activity_month
),
cohort_sizes AS (
    SELECT cohort_month, COUNT(*) AS cohort_size
    FROM user_cohorts
    GROUP BY cohort_month
)
SELECT 
    cd.cohort_month,
    cs.cohort_size,
    cd.months_since_signup,
    cd.active_users,
    ROUND(100.0 * cd.active_users / cs.cohort_size, 2) AS retention_rate
FROM cohort_data cd
JOIN cohort_sizes cs ON cd.cohort_month = cs.cohort_month
ORDER BY cd.cohort_month, cd.months_since_signup;
```

### Funnel Analysis

```sql
WITH funnel_steps AS (
    SELECT 
        session_id,
        MAX(CASE WHEN event_name = 'page_view' THEN 1 ELSE 0 END) AS viewed_page,
        MAX(CASE WHEN event_name = 'add_to_cart' THEN 1 ELSE 0 END) AS added_to_cart,
        MAX(CASE WHEN event_name = 'begin_checkout' THEN 1 ELSE 0 END) AS began_checkout,
        MAX(CASE WHEN event_name = 'purchase' THEN 1 ELSE 0 END) AS completed_purchase
    FROM events
    WHERE event_date >= CURRENT_DATE - INTERVAL '7 days'
    GROUP BY session_id
)
SELECT 
    'Page View' AS step,
    1 AS step_order,
    COUNT(*) AS sessions,
    100.0 AS percentage
FROM funnel_steps WHERE viewed_page = 1

UNION ALL

SELECT 
    'Add to Cart',
    2,
    COUNT(*),
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM funnel_steps WHERE viewed_page = 1), 2)
FROM funnel_steps WHERE added_to_cart = 1

UNION ALL

SELECT 
    'Begin Checkout',
    3,
    COUNT(*),
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM funnel_steps WHERE viewed_page = 1), 2)
FROM funnel_steps WHERE began_checkout = 1

UNION ALL

SELECT 
    'Purchase',
    4,
    COUNT(*),
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM funnel_steps WHERE viewed_page = 1), 2)
FROM funnel_steps WHERE completed_purchase = 1

ORDER BY step_order;
```

### Geographic Distribution

```sql
SELECT 
    COALESCE(c.country, 'Unknown') AS country,
    COALESCE(c.region, 'Unknown') AS region,
    COUNT(DISTINCT u.id) AS user_count,
    COUNT(DISTINCT o.id) AS order_count,
    COALESCE(SUM(o.total_amount), 0) AS total_revenue,
    ROUND(COALESCE(AVG(o.total_amount), 0), 2) AS avg_order_value
FROM users u
LEFT JOIN addresses a ON u.id = a.user_id AND a.is_primary = true
LEFT JOIN countries c ON a.country_code = c.code
LEFT JOIN orders o ON u.id = o.customer_id AND o.status = 'completed'
GROUP BY COALESCE(c.country, 'Unknown'), COALESCE(c.region, 'Unknown')
ORDER BY total_revenue DESC
LIMIT 20;
```

## Search and Filter Queries

### Full-Text Search (PostgreSQL)

```sql
SELECT 
    id,
    title,
    description,
    ts_rank(search_vector, query) AS rank
FROM products,
     to_tsquery('english', 'wireless & headphone') AS query
WHERE search_vector @@ query
ORDER BY rank DESC
LIMIT 20;
```

### Dynamic Filtering with Optional Parameters

```sql
SELECT *
FROM products p
WHERE 
    (p.category_id = :category_id OR :category_id IS NULL)
    AND (p.price >= :min_price OR :min_price IS NULL)
    AND (p.price <= :max_price OR :max_price IS NULL)
    AND (p.brand = :brand OR :brand IS NULL)
    AND (p.is_active = true)
ORDER BY 
    CASE WHEN :sort_by = 'price_asc' THEN p.price END ASC,
    CASE WHEN :sort_by = 'price_desc' THEN p.price END DESC,
    CASE WHEN :sort_by = 'newest' THEN p.created_at END DESC,
    p.name ASC
LIMIT :limit OFFSET :offset;
```

### Fuzzy Name Matching (PostgreSQL)

```sql
SELECT 
    id,
    name,
    email,
    similarity(name, 'John Smith') AS name_similarity
FROM customers
WHERE similarity(name, 'John Smith') > 0.3
   OR name ILIKE '%john%smith%'
   OR name ILIKE '%smith%john%'
ORDER BY name_similarity DESC
LIMIT 10;
```

## Data Migration Queries

### Copy Data Between Tables

```sql
INSERT INTO new_users (id, email, full_name, status, created_at)
SELECT 
    id,
    email,
    CONCAT(first_name, ' ', last_name) AS full_name,
    CASE 
        WHEN is_active = true THEN 'active'
        ELSE 'inactive'
    END AS status,
    created_at
FROM old_users
WHERE NOT EXISTS (
    SELECT 1 FROM new_users nu WHERE nu.id = old_users.id
);
```

### Merge Duplicate Records

```sql
WITH duplicates AS (
    SELECT 
        email,
        MIN(id) AS primary_id,
        ARRAY_AGG(id) FILTER (WHERE id != MIN(id)) AS duplicate_ids
    FROM customers
    GROUP BY email
    HAVING COUNT(*) > 1
)
UPDATE orders o
SET customer_id = d.primary_id
FROM duplicates d
WHERE o.customer_id = ANY(d.duplicate_ids);
```

### Archive Old Data

```sql
WITH archived AS (
    INSERT INTO orders_archive (id, customer_id, total, status, created_at, archived_at)
    SELECT id, customer_id, total, status, created_at, CURRENT_TIMESTAMP
    FROM orders
    WHERE created_at < CURRENT_DATE - INTERVAL '2 years'
      AND status IN ('completed', 'cancelled')
    RETURNING id
)
DELETE FROM orders
WHERE id IN (SELECT id FROM archived);
```

## Batch Processing Queries

### Update in Batches

```sql
WITH batch AS (
    SELECT id
    FROM large_table
    WHERE needs_update = true
      AND processed_at IS NULL
    ORDER BY id
    LIMIT 1000
    FOR UPDATE SKIP LOCKED
)
UPDATE large_table lt
SET 
    processed_at = CURRENT_TIMESTAMP,
    status = 'processed'
FROM batch
WHERE lt.id = batch.id;
```

### Process Records Sequentially

```sql
DO $$
DECLARE
    batch_size INT := 5000;
    affected INT;
BEGIN
    LOOP
        WITH batch AS (
            DELETE FROM staging_table
            WHERE id IN (
                SELECT id FROM staging_table
                ORDER BY id
                LIMIT batch_size
            )
            RETURNING *
        )
        INSERT INTO target_table
        SELECT * FROM batch;
        
        GET DIAGNOSTICS affected = ROW_COUNT;
        
        EXIT WHEN affected = 0;
        
        COMMIT;
    END LOOP;
END $$;
```
