---
name: sql-optimizer
description: Rewrite slow SQL queries for performance — read execution plans (EXPLAIN / EXPLAIN ANALYZE), remove anti-patterns, make predicates sargable, choose JOIN/EXISTS strategies and suggest indexes. Use when the user says a query is slow, times out, or asks to optimise or speed up specific SQL.
metadata:
  category: programming
  version: "1.0.0"
---

# SQL Query Optimizer

Analyze and optimize SQL queries for better performance through query rewriting, index suggestions, and execution plan analysis.

## Trigger Conditions

Activate this skill when the user:
- Says "this query is slow", "optimize this query"
- Asks about query performance or execution time
- Wants to understand why a query is slow
- Needs help with execution plans (EXPLAIN)
- Asks about index usage or missing indexes

## Optimization Workflow

```
1. ANALYZE    -> Understand query structure and intent
2. IDENTIFY   -> Find performance bottlenecks
3. MEASURE    -> Review execution plan if available
4. REWRITE    -> Apply optimization techniques
5. VALIDATE   -> Ensure results remain correct
6. RECOMMEND  -> Suggest indexes or schema changes
```

## Pre-Flight Checklist

Before optimizing:

```
- [ ] Understand the query's purpose
- [ ] Know the approximate data volumes
- [ ] Identify current indexes
- [ ] Have execution plan if possible
- [ ] Verify correctness requirements
```

## Reading Execution Plans

### PostgreSQL EXPLAIN

```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) SELECT ...;
```

Key metrics:
- **actual time**: Real execution time in ms
- **rows**: Estimated vs actual row counts
- **loops**: Number of iterations
- **buffers**: Disk I/O (shared hit = cached, read = disk)

### MySQL EXPLAIN

```sql
EXPLAIN SELECT ...;
EXPLAIN ANALYZE SELECT ...;  -- MySQL 8.0.18+
```

Key columns:
- **type**: Access method (ALL = bad, ref/range/const = good)
- **possible_keys**: Indexes that could be used
- **key**: Index actually used
- **rows**: Estimated rows to examine
- **Extra**: Additional info (Using filesort, Using temporary = warnings)

### SQL Server

```sql
SET STATISTICS IO ON;
SET STATISTICS TIME ON;
-- Run query
SET SHOWPLAN_ALL ON;
```

Key metrics:
- **logical reads**: Pages read from cache
- **physical reads**: Pages read from disk
- **CPU time**: Processing time

## Common Performance Issues

### Issue 1: Full Table Scan

**Symptom**: Seq Scan/TABLE ACCESS FULL on large table

**Causes**:
- No index on WHERE/JOIN columns
- Function applied to indexed column
- Type mismatch in comparison
- LIKE with leading wildcard

**Solutions**:

Bad (can't use index):
```sql
SELECT * FROM users WHERE LOWER(email) = 'john@example.com';
SELECT * FROM users WHERE YEAR(created_at) = 2024;
SELECT * FROM orders WHERE customer_id::text = '12345';
```

Good (index-friendly):
```sql
SELECT * FROM users WHERE email = 'john@example.com';  -- case-insensitive collation
SELECT * FROM users WHERE created_at >= '2024-01-01' AND created_at < '2025-01-01';
SELECT * FROM orders WHERE customer_id = 12345;
```

### Issue 2: Inefficient JOINs

**Symptom**: Nested loop join with high row counts

**Solutions**:

Ensure join columns are indexed:
```sql
CREATE INDEX idx_orders_customer_id ON orders(customer_id);
```

Use appropriate join type:
```sql
SELECT * FROM large_table l
JOIN small_table s ON l.key = s.key;
```

### Issue 3: Subquery vs JOIN

**Symptom**: Correlated subquery executes once per row

Bad (executes subquery for each order):
```sql
SELECT o.*,
    (SELECT name FROM customers WHERE id = o.customer_id) AS customer_name
FROM orders o;
```

Good (single join operation):
```sql
SELECT o.*, c.name AS customer_name
FROM orders o
JOIN customers c ON o.customer_id = c.id;
```

### Issue 4: IN vs EXISTS

**For checking existence (large subquery result)**:

Less efficient:
```sql
SELECT * FROM products 
WHERE category_id IN (SELECT id FROM categories WHERE active = true);
```

More efficient:
```sql
SELECT * FROM products p
WHERE EXISTS (SELECT 1 FROM categories c WHERE c.id = p.category_id AND c.active = true);
```

**For small, known value lists, IN is fine**:
```sql
SELECT * FROM products WHERE category_id IN (1, 2, 3, 4, 5);
```

### Issue 5: SELECT *

**Problem**: Retrieves unnecessary columns, can't use covering index

Bad:
```sql
SELECT * FROM orders WHERE customer_id = 123;
```

Good:
```sql
SELECT id, order_date, total FROM orders WHERE customer_id = 123;
```

With covering index:
```sql
CREATE INDEX idx_orders_customer_covering ON orders(customer_id) INCLUDE (id, order_date, total);
```

### Issue 6: ORDER BY Without Index

**Symptom**: "Using filesort" in execution plan

Bad (sorts in memory/disk):
```sql
SELECT * FROM products ORDER BY created_at DESC LIMIT 10;
```

Good (with index):
```sql
CREATE INDEX idx_products_created_at ON products(created_at DESC);
SELECT * FROM products ORDER BY created_at DESC LIMIT 10;
```

### Issue 7: Pagination with Large Offset

**Problem**: OFFSET scans and discards rows

Bad (scans 10,010 rows):
```sql
SELECT * FROM products ORDER BY id LIMIT 10 OFFSET 10000;
```

Good (keyset/cursor pagination):
```sql
SELECT * FROM products WHERE id > 10000 ORDER BY id LIMIT 10;
```

### Issue 8: OR Conditions

**Problem**: OR often prevents index usage

Bad:
```sql
SELECT * FROM users WHERE email = 'a@b.com' OR phone = '1234567890';
```

Good (if both columns indexed):
```sql
SELECT * FROM users WHERE email = 'a@b.com'
UNION
SELECT * FROM users WHERE phone = '1234567890';
```

### Issue 9: Redundant DISTINCT

**Problem**: DISTINCT requires sorting/hashing all rows

Bad (if relationship guarantees uniqueness):
```sql
SELECT DISTINCT c.id, c.name 
FROM customers c 
JOIN orders o ON c.id = o.customer_id;
```

Good:
```sql
SELECT c.id, c.name 
FROM customers c 
WHERE EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id);
```

### Issue 10: Functions in WHERE

**Problem**: Functions prevent index usage

Bad:
```sql
SELECT * FROM events WHERE DATE(event_time) = '2024-01-15';
```

Good:
```sql
SELECT * FROM events 
WHERE event_time >= '2024-01-15 00:00:00' 
  AND event_time < '2024-01-16 00:00:00';
```

## Optimization Techniques

### Technique 1: Query Rewriting

**Split complex queries**:
```sql
WITH filtered_orders AS (
    SELECT * FROM orders WHERE status = 'completed' AND order_date >= '2024-01-01'
)
SELECT c.name, COUNT(*) 
FROM filtered_orders fo
JOIN customers c ON fo.customer_id = c.id
GROUP BY c.name;
```

**Materialize intermediate results**:
```sql
CREATE TEMP TABLE recent_orders AS
SELECT * FROM orders WHERE order_date >= '2024-01-01';

CREATE INDEX idx_temp_customer ON recent_orders(customer_id);

SELECT c.name, COUNT(*)
FROM recent_orders ro
JOIN customers c ON ro.customer_id = c.id
GROUP BY c.name;
```

### Technique 2: Index Optimization

**Composite index for multiple columns**:
```sql
CREATE INDEX idx_orders_status_date ON orders(status, order_date);
```

**Partial/filtered index**:
```sql
CREATE INDEX idx_active_users ON users(email) WHERE status = 'active';
```

**Covering index**:
```sql
CREATE INDEX idx_orders_covering ON orders(customer_id) INCLUDE (order_date, total);
```

### Technique 3: Batch Processing

**Process in chunks instead of one large query**:
```sql
DO $$
DECLARE
    batch_size INT := 10000;
    last_id INT := 0;
BEGIN
    LOOP
        UPDATE large_table 
        SET processed = true 
        WHERE id > last_id 
          AND id <= last_id + batch_size
          AND processed = false;
        
        EXIT WHEN NOT FOUND;
        
        SELECT MAX(id) INTO last_id FROM large_table WHERE processed = true;
        COMMIT;
    END LOOP;
END $$;
```

### Technique 4: Denormalization

**Add redundant data to avoid joins**:
```sql
ALTER TABLE orders ADD COLUMN customer_name VARCHAR(100);

UPDATE orders o
SET customer_name = (SELECT name FROM customers c WHERE c.id = o.customer_id);
```

### Technique 5: Materialized Views

```sql
CREATE MATERIALIZED VIEW sales_summary AS
SELECT 
    product_id,
    DATE_TRUNC('month', order_date) AS month,
    SUM(quantity) AS total_quantity,
    SUM(total_amount) AS total_revenue
FROM order_items oi
JOIN orders o ON oi.order_id = o.id
WHERE o.status = 'completed'
GROUP BY product_id, DATE_TRUNC('month', order_date);

CREATE INDEX idx_sales_summary_product ON sales_summary(product_id);

REFRESH MATERIALIZED VIEW sales_summary;
```

## Index Recommendations

### When to Create Indexes

| Scenario | Index Type |
|----------|------------|
| WHERE clause equality | B-tree (default) |
| WHERE clause range | B-tree |
| Full-text search | GIN/Full-text |
| Array/JSON containment | GIN |
| Geospatial queries | GiST/SP-GiST |
| Multiple columns in WHERE | Composite |
| Frequently updated columns | Consider carefully |

### Index Creation Guidelines

1. **Index selective columns** - High cardinality (many unique values)
2. **Index foreign keys** - Used in JOINs
3. **Index ORDER BY columns** - For sorted queries
4. **Consider write overhead** - Indexes slow down INSERT/UPDATE
5. **Monitor unused indexes** - Remove if not used

## Output Format

When optimizing a query, provide:

1. **Analysis**: What makes the query slow
2. **Optimized Query**: Rewritten version
3. **Explanation**: What changed and why
4. **Index Recommendations**: Indexes to create
5. **Expected Improvement**: Estimated performance gain

## Additional Resources

| File | Content |
|------|---------|
| [examples.md](references/examples.md) | Before/after optimization examples |
