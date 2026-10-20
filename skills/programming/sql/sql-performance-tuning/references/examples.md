# SQL Performance Tuning Examples

Real-world performance tuning case studies with before/after analysis.

## Case Study 1: Slow Customer Search

### Problem

Query takes 15+ seconds:
```sql
SELECT * FROM customers 
WHERE LOWER(email) LIKE '%john%' 
   OR LOWER(name) LIKE '%john%';
```

### Analysis

```sql
EXPLAIN ANALYZE SELECT * FROM customers WHERE LOWER(email) LIKE '%john%' OR LOWER(name) LIKE '%john%';
```

Output shows:
```
Seq Scan on customers (cost=0.00..25000.00 rows=1000 width=200)
  Filter: ((lower(email) ~~ '%john%') OR (lower(name) ~~ '%john%'))
  Rows Removed by Filter: 999000
```

### Solution

Create trigram indexes for substring search:
```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX idx_customers_email_trgm ON customers USING GIN (email gin_trgm_ops);
CREATE INDEX idx_customers_name_trgm ON customers USING GIN (name gin_trgm_ops);
```

Rewrite query (if case-insensitive needed):
```sql
SELECT * FROM customers 
WHERE email ILIKE '%john%' 
   OR name ILIKE '%john%';
```

### Result

- Before: 15 seconds, Seq Scan
- After: 50ms, Bitmap Index Scan
- Improvement: 300x faster

## Case Study 2: Expensive JOIN on Large Tables

### Problem

```sql
SELECT o.id, o.order_date, c.name, c.email
FROM orders o
JOIN customers c ON o.customer_id = c.id
WHERE o.order_date >= '2024-01-01';
```

10 million orders, 1 million customers. Query takes 45 seconds.

### Analysis

```sql
EXPLAIN (ANALYZE, BUFFERS) SELECT ...;
```

Output shows:
```
Hash Join (actual time=45123.456..45123.456 rows=500000)
  -> Seq Scan on orders (actual time=0.01..30000.00 rows=10000000)
       Filter: (order_date >= '2024-01-01')
       Rows Removed by Filter: 9500000
  -> Hash (actual time=5000.00 rows=1000000)
       -> Seq Scan on customers (actual time=0.01..3000.00 rows=1000000)
```

### Solution

1. Add index on orders.order_date:
```sql
CREATE INDEX idx_orders_date ON orders(order_date);
```

2. Add index on orders.customer_id:
```sql
CREATE INDEX idx_orders_customer ON orders(customer_id);
```

3. Create covering index:
```sql
CREATE INDEX idx_orders_date_covering ON orders(order_date) 
INCLUDE (customer_id, id);
```

### Result

- Before: 45 seconds
- After: 800ms
- Improvement: 56x faster

## Case Study 3: N+1 Query Problem

### Problem

Application executes:
```sql
SELECT * FROM orders WHERE customer_id = 1;
SELECT * FROM orders WHERE customer_id = 2;
SELECT * FROM orders WHERE customer_id = 3;
... (1000 queries)
```

### Solution

Batch into single query:
```sql
SELECT * FROM orders 
WHERE customer_id IN (1, 2, 3, ..., 1000)
ORDER BY customer_id;
```

Or use JOIN:
```sql
SELECT c.id, c.name, o.*
FROM customers c
LEFT JOIN orders o ON c.id = o.customer_id
WHERE c.id IN (1, 2, 3, ..., 1000);
```

### Result

- Before: 1000 queries, 5 seconds total
- After: 1 query, 50ms
- Improvement: 100x faster

## Case Study 4: Missing Index on Foreign Key

### Problem

```sql
DELETE FROM customers WHERE id = 12345;
```

Takes 30 seconds due to foreign key check.

### Analysis

```sql
EXPLAIN ANALYZE DELETE FROM customers WHERE id = 12345;
```

Shows sequential scan on orders table checking FK constraint.

### Solution

```sql
CREATE INDEX idx_orders_customer_id ON orders(customer_id);
```

### Result

- Before: 30 seconds
- After: 5ms
- Improvement: 6000x faster

## Case Study 5: Inefficient Pagination

### Problem

```sql
SELECT * FROM products 
ORDER BY created_at DESC 
LIMIT 20 OFFSET 100000;
```

Takes 10 seconds for deep pagination.

### Analysis

Database must scan and sort 100,020 rows, discard 100,000.

### Solution

Keyset pagination:
```sql
SELECT * FROM products 
WHERE created_at < '2024-01-15 10:30:00'
  AND (created_at < '2024-01-15 10:30:00' OR 
       (created_at = '2024-01-15 10:30:00' AND id < 50000))
ORDER BY created_at DESC, id DESC
LIMIT 20;
```

With index:
```sql
CREATE INDEX idx_products_created_id ON products(created_at DESC, id DESC);
```

### Result

- Before: 10 seconds
- After: 5ms
- Improvement: 2000x faster

## Case Study 6: Bloated Table

### Problem

Table has 1 million rows but uses 50GB disk space. Queries are slow.

### Analysis

```sql
SELECT 
    pg_size_pretty(pg_total_relation_size('table_name')) AS total,
    pg_size_pretty(pg_relation_size('table_name')) AS table,
    pg_size_pretty(pg_indexes_size('table_name')) AS indexes;
```

Check dead tuples:
```sql
SELECT 
    relname,
    n_live_tup,
    n_dead_tup,
    round(100 * n_dead_tup / nullif(n_live_tup + n_dead_tup, 0), 2) AS dead_pct
FROM pg_stat_user_tables
WHERE relname = 'table_name';
```

Shows 90% dead tuples.

### Solution

```sql
VACUUM FULL table_name;
REINDEX TABLE table_name;
```

Configure autovacuum:
```sql
ALTER TABLE table_name SET (
    autovacuum_vacuum_threshold = 100,
    autovacuum_vacuum_scale_factor = 0.05
);
```

### Result

- Before: 50GB
- After: 5GB
- Query improvement: 3x faster

## Case Study 7: Suboptimal Query Plan Due to Statistics

### Problem

```sql
SELECT * FROM orders o
JOIN order_items oi ON o.id = oi.order_id
WHERE o.status = 'pending';
```

Slow despite indexes existing.

### Analysis

EXPLAIN shows estimated 1000 rows but actual 500,000 rows.

### Solution

Update statistics:
```sql
ANALYZE orders;
ANALYZE order_items;
```

For specific columns:
```sql
ALTER TABLE orders ALTER COLUMN status SET STATISTICS 1000;
ANALYZE orders;
```

### Result

- Before: 30 seconds (wrong join strategy)
- After: 500ms (correct join strategy)
- Improvement: 60x faster

## Case Study 8: Lock Contention

### Problem

Multiple processes updating same rows cause timeouts.

### Analysis

```sql
SELECT 
    pg_blocking_pids(pid) AS blocked_by,
    query
FROM pg_stat_activity
WHERE cardinality(pg_blocking_pids(pid)) > 0;
```

### Solution

1. Use SELECT FOR UPDATE SKIP LOCKED:
```sql
WITH batch AS (
    SELECT id FROM queue_table
    WHERE status = 'pending'
    LIMIT 100
    FOR UPDATE SKIP LOCKED
)
UPDATE queue_table
SET status = 'processing', processor_id = 'worker-1'
WHERE id IN (SELECT id FROM batch);
```

2. Reduce transaction scope:
```sql
BEGIN;
UPDATE accounts SET balance = balance - 100 WHERE id = 1;
COMMIT;

BEGIN;
UPDATE accounts SET balance = balance + 100 WHERE id = 2;
COMMIT;
```

### Result

- Before: Lock waits up to 30 seconds
- After: No lock waits
- Throughput: 10x improvement

## Case Study 9: Aggregate Query Optimization

### Problem

```sql
SELECT 
    DATE(created_at) AS date,
    COUNT(*) AS count,
    SUM(amount) AS total
FROM transactions
WHERE created_at >= '2024-01-01'
GROUP BY DATE(created_at)
ORDER BY date;
```

30 million rows, takes 2 minutes.

### Solution

1. Create partial index:
```sql
CREATE INDEX idx_transactions_2024 ON transactions(created_at)
WHERE created_at >= '2024-01-01';
```

2. Create materialized view for reporting:
```sql
CREATE MATERIALIZED VIEW daily_transaction_summary AS
SELECT 
    DATE(created_at) AS date,
    COUNT(*) AS count,
    SUM(amount) AS total
FROM transactions
GROUP BY DATE(created_at);

CREATE INDEX idx_summary_date ON daily_transaction_summary(date);

REFRESH MATERIALIZED VIEW CONCURRENTLY daily_transaction_summary;
```

3. Schedule refresh:
```sql
SELECT cron.schedule('refresh-daily', '0 1 * * *', 
    'REFRESH MATERIALIZED VIEW CONCURRENTLY daily_transaction_summary');
```

### Result

- Before: 2 minutes
- After: 10ms (from materialized view)
- Trade-off: Data is up to 24 hours old

## Case Study 10: Full-Text Search Optimization

### Problem

```sql
SELECT * FROM articles
WHERE title LIKE '%machine learning%'
   OR content LIKE '%machine learning%';
```

1 million articles, takes 45 seconds.

### Solution

1. Add full-text search column:
```sql
ALTER TABLE articles ADD COLUMN search_vector tsvector;

UPDATE articles SET search_vector = 
    setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(content, '')), 'B');

CREATE INDEX idx_articles_fts ON articles USING GIN(search_vector);
```

2. Create trigger for updates:
```sql
CREATE FUNCTION articles_search_trigger() RETURNS trigger AS $$
BEGIN
    NEW.search_vector := 
        setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(NEW.content, '')), 'B');
    RETURN NEW;
END $$ LANGUAGE plpgsql;

CREATE TRIGGER tsvector_update BEFORE INSERT OR UPDATE
ON articles FOR EACH ROW EXECUTE FUNCTION articles_search_trigger();
```

3. Query with FTS:
```sql
SELECT *, ts_rank(search_vector, query) AS rank
FROM articles, to_tsquery('english', 'machine & learning') AS query
WHERE search_vector @@ query
ORDER BY rank DESC
LIMIT 20;
```

### Result

- Before: 45 seconds
- After: 20ms
- Improvement: 2250x faster

## Performance Monitoring Queries

### Most Time-Consuming Queries

```sql
SELECT 
    round(total_time::numeric, 2) AS total_time_ms,
    calls,
    round((total_time / calls)::numeric, 2) AS avg_time_ms,
    query
FROM pg_stat_statements
ORDER BY total_time DESC
LIMIT 20;
```

### Table Bloat Estimation

```sql
WITH constants AS (
    SELECT current_setting('block_size')::numeric AS bs
),
table_stats AS (
    SELECT
        schemaname,
        tablename,
        reltuples::bigint AS row_count,
        relpages::bigint AS page_count,
        (SELECT bs FROM constants) * relpages AS table_bytes
    FROM pg_class c
    JOIN pg_stat_user_tables t ON c.relname = t.relname
    WHERE c.relkind = 'r'
)
SELECT
    schemaname,
    tablename,
    pg_size_pretty(table_bytes) AS size,
    row_count,
    page_count,
    CASE WHEN row_count > 0 
        THEN round(table_bytes / row_count, 2) 
        ELSE 0 
    END AS bytes_per_row
FROM table_stats
ORDER BY table_bytes DESC;
```

### Index Health Check

```sql
SELECT
    indexrelname AS index,
    relname AS table,
    idx_scan AS scans,
    idx_tup_read AS tuples_read,
    idx_tup_fetch AS tuples_fetched,
    pg_size_pretty(pg_relation_size(indexrelid)) AS size,
    CASE 
        WHEN idx_scan = 0 THEN 'UNUSED'
        WHEN idx_tup_read / nullif(idx_scan, 0) > 1000 THEN 'LOW SELECTIVITY'
        ELSE 'OK'
    END AS status
FROM pg_stat_user_indexes
ORDER BY pg_relation_size(indexrelid) DESC;
```
