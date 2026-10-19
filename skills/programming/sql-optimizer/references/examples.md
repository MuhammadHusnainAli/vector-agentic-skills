# SQL Optimizer Examples

Before and after optimization examples with explanations.

## Example 1: Removing Correlated Subquery

### Before (Slow)

```sql
SELECT 
    p.id,
    p.name,
    p.price,
    (SELECT COUNT(*) FROM order_items oi WHERE oi.product_id = p.id) AS order_count,
    (SELECT SUM(quantity) FROM order_items oi WHERE oi.product_id = p.id) AS total_sold,
    (SELECT AVG(rating) FROM reviews r WHERE r.product_id = p.id) AS avg_rating
FROM products p
WHERE p.category_id = 5;
```

**Problem**: Three correlated subqueries execute once per product row.

### After (Fast)

```sql
SELECT 
    p.id,
    p.name,
    p.price,
    COALESCE(oi_stats.order_count, 0) AS order_count,
    COALESCE(oi_stats.total_sold, 0) AS total_sold,
    r_stats.avg_rating
FROM products p
LEFT JOIN (
    SELECT 
        product_id,
        COUNT(*) AS order_count,
        SUM(quantity) AS total_sold
    FROM order_items
    GROUP BY product_id
) oi_stats ON p.id = oi_stats.product_id
LEFT JOIN (
    SELECT 
        product_id,
        AVG(rating) AS avg_rating
    FROM reviews
    GROUP BY product_id
) r_stats ON p.id = r_stats.product_id
WHERE p.category_id = 5;
```

**Improvement**: Subqueries execute once total, then join. ~100x faster for large tables.

### Recommended Indexes

```sql
CREATE INDEX idx_order_items_product ON order_items(product_id);
CREATE INDEX idx_reviews_product ON reviews(product_id);
CREATE INDEX idx_products_category ON products(category_id);
```

## Example 2: Fixing OR Conditions

### Before (Slow)

```sql
SELECT * FROM users 
WHERE email = 'john@example.com' 
   OR phone = '555-1234'
   OR username = 'johndoe';
```

**Problem**: OR prevents efficient index usage; may cause full table scan.

### After (Fast)

```sql
SELECT * FROM users WHERE email = 'john@example.com'
UNION
SELECT * FROM users WHERE phone = '555-1234'
UNION
SELECT * FROM users WHERE username = 'johndoe';
```

**Improvement**: Each query uses its own index, results combined.

### Alternative with Index

```sql
CREATE INDEX idx_users_search ON users(email, phone, username);
```

## Example 3: Optimizing Date Range Queries

### Before (Slow)

```sql
SELECT * FROM events
WHERE YEAR(event_date) = 2024
  AND MONTH(event_date) = 6;
```

**Problem**: Functions on indexed columns prevent index usage.

### After (Fast)

```sql
SELECT * FROM events
WHERE event_date >= '2024-06-01'
  AND event_date < '2024-07-01';
```

**Improvement**: Direct range comparison uses index efficiently.

### Recommended Index

```sql
CREATE INDEX idx_events_date ON events(event_date);
```

## Example 4: Pagination Optimization

### Before (Slow - Large Offset)

```sql
SELECT id, title, created_at
FROM articles
ORDER BY created_at DESC
LIMIT 20 OFFSET 100000;
```

**Problem**: Database must scan and discard 100,000 rows.

### After (Fast - Keyset Pagination)

```sql
SELECT id, title, created_at
FROM articles
WHERE created_at < '2024-01-15 10:30:00'
   OR (created_at = '2024-01-15 10:30:00' AND id < 50000)
ORDER BY created_at DESC, id DESC
LIMIT 20;
```

**Improvement**: Uses index to start at correct position. Requires passing last seen values.

### Recommended Index

```sql
CREATE INDEX idx_articles_created_id ON articles(created_at DESC, id DESC);
```

## Example 5: Replacing NOT IN with NOT EXISTS

### Before (Slow/Dangerous with NULLs)

```sql
SELECT * FROM products
WHERE id NOT IN (
    SELECT product_id FROM discontinued_products
);
```

**Problem**: If discontinued_products.product_id contains NULL, returns no rows. Also may be slow.

### After (Fast and NULL-safe)

```sql
SELECT p.* FROM products p
WHERE NOT EXISTS (
    SELECT 1 FROM discontinued_products dp
    WHERE dp.product_id = p.id
);
```

**Improvement**: Handles NULLs correctly, often faster execution plan.

### Alternative (Anti-Join)

```sql
SELECT p.* FROM products p
LEFT JOIN discontinued_products dp ON p.id = dp.product_id
WHERE dp.product_id IS NULL;
```

## Example 6: Aggregation with FILTER

### Before (Multiple Scans)

```sql
SELECT 
    (SELECT COUNT(*) FROM orders WHERE status = 'pending') AS pending_count,
    (SELECT COUNT(*) FROM orders WHERE status = 'completed') AS completed_count,
    (SELECT COUNT(*) FROM orders WHERE status = 'cancelled') AS cancelled_count,
    (SELECT SUM(total) FROM orders WHERE status = 'completed') AS completed_revenue;
```

**Problem**: Four separate table scans.

### After (Single Scan - PostgreSQL)

```sql
SELECT 
    COUNT(*) FILTER (WHERE status = 'pending') AS pending_count,
    COUNT(*) FILTER (WHERE status = 'completed') AS completed_count,
    COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled_count,
    SUM(total) FILTER (WHERE status = 'completed') AS completed_revenue
FROM orders;
```

### After (Single Scan - Standard SQL)

```sql
SELECT 
    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS pending_count,
    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed_count,
    SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled_count,
    SUM(CASE WHEN status = 'completed' THEN total ELSE 0 END) AS completed_revenue
FROM orders;
```

**Improvement**: Single table scan instead of four.

## Example 7: EXISTS vs COUNT for Existence Check

### Before (Inefficient)

```sql
SELECT c.* FROM customers c
WHERE (SELECT COUNT(*) FROM orders o WHERE o.customer_id = c.id) > 0;
```

**Problem**: Counts all orders even though we only need to know if any exist.

### After (Efficient)

```sql
SELECT c.* FROM customers c
WHERE EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id);
```

**Improvement**: Stops at first match instead of counting all.

## Example 8: Selective Column Retrieval

### Before (Fetches Everything)

```sql
SELECT * FROM products
WHERE category_id = 5
ORDER BY name;
```

**Problem**: Retrieves all columns including large text/blob fields.

### After (Covering Index Possible)

```sql
SELECT id, name, price, stock_quantity
FROM products
WHERE category_id = 5
ORDER BY name;
```

### With Covering Index

```sql
CREATE INDEX idx_products_category_name ON products(category_id, name) 
INCLUDE (id, price, stock_quantity);
```

**Improvement**: Index-only scan, no table access needed.

## Example 9: JOIN Order Optimization

### Before (Large Table First)

```sql
SELECT c.name, COUNT(o.id) AS order_count
FROM orders o
JOIN customers c ON o.customer_id = c.id
JOIN order_items oi ON o.id = oi.order_id
JOIN products p ON oi.product_id = p.id
WHERE p.category_id = 5
GROUP BY c.name;
```

**Problem**: Joins in suboptimal order based on write order.

### After (Filter Early)

```sql
WITH category_products AS (
    SELECT id FROM products WHERE category_id = 5
),
relevant_items AS (
    SELECT oi.order_id
    FROM order_items oi
    WHERE oi.product_id IN (SELECT id FROM category_products)
)
SELECT c.name, COUNT(DISTINCT o.id) AS order_count
FROM relevant_items ri
JOIN orders o ON ri.order_id = o.id
JOIN customers c ON o.customer_id = c.id
GROUP BY c.name;
```

**Improvement**: Filters to relevant products first, reducing join sizes.

## Example 10: Window Function vs Self-Join

### Before (Self-Join for Running Total)

```sql
SELECT 
    t1.id,
    t1.amount,
    SUM(t2.amount) AS running_total
FROM transactions t1
JOIN transactions t2 
    ON t2.account_id = t1.account_id 
    AND t2.transaction_date <= t1.transaction_date
WHERE t1.account_id = 123
GROUP BY t1.id, t1.amount, t1.transaction_date
ORDER BY t1.transaction_date;
```

**Problem**: O(n^2) complexity with self-join.

### After (Window Function)

```sql
SELECT 
    id,
    amount,
    SUM(amount) OVER (
        ORDER BY transaction_date 
        ROWS UNBOUNDED PRECEDING
    ) AS running_total
FROM transactions
WHERE account_id = 123
ORDER BY transaction_date;
```

**Improvement**: O(n) single pass through data.

## Example 11: Batch Delete Optimization

### Before (Long-Running Delete)

```sql
DELETE FROM logs WHERE created_at < '2023-01-01';
```

**Problem**: Locks table for duration, may run for hours on large tables.

### After (Batched Delete)

```sql
DO $$
DECLARE
    rows_deleted INT;
BEGIN
    LOOP
        DELETE FROM logs
        WHERE id IN (
            SELECT id FROM logs
            WHERE created_at < '2023-01-01'
            LIMIT 10000
        );
        
        GET DIAGNOSTICS rows_deleted = ROW_COUNT;
        
        EXIT WHEN rows_deleted = 0;
        
        COMMIT;
        PERFORM pg_sleep(0.1);
    END LOOP;
END $$;
```

**Improvement**: Smaller transactions, allows other queries to proceed.

## Example 12: Index-Aware LIKE Queries

### Before (No Index Usage)

```sql
SELECT * FROM products WHERE name LIKE '%widget%';
```

**Problem**: Leading wildcard prevents B-tree index usage.

### After (Trigram Index - PostgreSQL)

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_products_name_trgm ON products USING GIN (name gin_trgm_ops);

SELECT * FROM products WHERE name LIKE '%widget%';
```

### Alternative (Full-Text Search)

```sql
ALTER TABLE products ADD COLUMN search_vector tsvector;
UPDATE products SET search_vector = to_tsvector('english', name || ' ' || description);
CREATE INDEX idx_products_fts ON products USING GIN(search_vector);

SELECT * FROM products WHERE search_vector @@ to_tsquery('widget');
```

**Improvement**: Trigram or FTS indexes enable substring/word search.

## Example 13: Reducing Memory Usage

### Before (Large Intermediate Result)

```sql
SELECT DISTINCT customer_id
FROM orders
WHERE order_date >= '2024-01-01'
ORDER BY customer_id;
```

**Problem**: DISTINCT may sort/hash millions of rows in memory.

### After (Using EXISTS)

```sql
SELECT id FROM customers c
WHERE EXISTS (
    SELECT 1 FROM orders o
    WHERE o.customer_id = c.id
      AND o.order_date >= '2024-01-01'
);
```

**Improvement**: Returns unique customers without full deduplication of orders.

### Alternative (GROUP BY)

```sql
SELECT customer_id
FROM orders
WHERE order_date >= '2024-01-01'
GROUP BY customer_id
ORDER BY customer_id;
```

## Query Performance Checklist

| Check | Issue Indicator | Solution |
|-------|-----------------|----------|
| EXPLAIN shows Seq Scan | Missing index | Add appropriate index |
| High row estimates | Statistics outdated | ANALYZE table |
| Multiple subqueries | Correlated execution | Rewrite as JOINs |
| OR in WHERE | Can't use single index | UNION or multi-column index |
| Functions on columns | Index not used | Move function to value side |
| Large OFFSET | Scanning many rows | Use keyset pagination |
| SELECT * | Extra I/O | Select specific columns |
| NOT IN with subquery | NULL issues, slow | Use NOT EXISTS |
| DISTINCT on large set | Memory pressure | Use EXISTS or GROUP BY |
