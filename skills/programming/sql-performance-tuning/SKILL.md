---
name: sql-performance-tuning
description: Database-level SQL performance tuning — index design and maintenance, query profiling, statistics, partitioning, schema design, locking and configuration bottlenecks. Use when the problem is the database or workload as a whole rather than one query, or when the user asks about indexing strategy or profiling.
metadata:
  category: programming
  version: "1.0.0"
---

# SQL Performance Tuning

Database-level performance optimization including indexing strategies, query profiling, schema design, and bottleneck identification.

## Trigger Conditions

Activate this skill when the user:
- Asks about database performance or slow queries
- Needs help with indexing strategies
- Wants to understand query execution plans
- Has database bottlenecks to investigate
- Needs schema optimization advice
- Asks about database configuration tuning

## Performance Tuning Workflow

```
1. BASELINE    -> Measure current performance
2. IDENTIFY    -> Find bottlenecks and slow queries
3. ANALYZE     -> Understand root causes
4. OPTIMIZE    -> Apply improvements
5. VERIFY      -> Confirm improvements
6. MONITOR     -> Set up ongoing monitoring
```

## Indexing Strategies

### Index Types

| Type | Use Case | Example |
|------|----------|---------|
| B-Tree | Default, equality/range queries | `CREATE INDEX idx ON table(col)` |
| Hash | Equality only (PostgreSQL) | `CREATE INDEX idx ON table USING HASH(col)` |
| GIN | Arrays, JSONB, full-text | `CREATE INDEX idx ON table USING GIN(col)` |
| GiST | Geometric, full-text, ranges | `CREATE INDEX idx ON table USING GIST(col)` |
| BRIN | Large tables with sorted data | `CREATE INDEX idx ON table USING BRIN(col)` |

### When to Create Indexes

```
DO create indexes on:
- Primary keys (automatic)
- Foreign keys (for JOINs)
- Columns in WHERE clauses
- Columns in ORDER BY
- Columns in GROUP BY
- Columns in JOIN conditions

DON'T over-index:
- Tables with frequent writes
- Low-cardinality columns (few unique values)
- Small tables (full scan may be faster)
- Columns rarely used in queries
```

### Composite Index Guidelines

```sql
CREATE INDEX idx_orders_customer_date ON orders(customer_id, order_date);
```

**Column Order Matters**:
- Put equality columns first
- Put range/inequality columns last
- Most selective columns first

```
Good for:  WHERE customer_id = 123 AND order_date > '2024-01-01'
Good for:  WHERE customer_id = 123
Bad for:   WHERE order_date > '2024-01-01' (can't use leading column)
```

### Covering Indexes

Include non-key columns to enable index-only scans:

PostgreSQL:
```sql
CREATE INDEX idx_orders_covering ON orders(customer_id) 
INCLUDE (order_date, total);
```

SQL Server:
```sql
CREATE INDEX idx_orders_covering ON orders(customer_id) 
INCLUDE (order_date, total);
```

### Partial/Filtered Indexes

Index only relevant rows:

```sql
CREATE INDEX idx_active_users ON users(email) WHERE status = 'active';
CREATE INDEX idx_recent_orders ON orders(customer_id) WHERE order_date >= '2024-01-01';
```

### Expression/Functional Indexes

Index computed values:

```sql
CREATE INDEX idx_users_email_lower ON users(LOWER(email));
CREATE INDEX idx_orders_year ON orders(EXTRACT(YEAR FROM order_date));
```

## Query Profiling

### PostgreSQL

Enable timing:
```sql
\timing on
```

Execution plan:
```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) SELECT ...;
```

Key metrics to watch:
- **actual time**: Real execution time
- **rows**: Estimated vs actual (large difference = statistics issue)
- **buffers shared hit/read**: Cache efficiency
- **loops**: Iteration count for nested operations

Find slow queries:
```sql
SELECT 
    query,
    calls,
    total_time / 1000 AS total_seconds,
    mean_time / 1000 AS mean_seconds,
    rows
FROM pg_stat_statements
ORDER BY total_time DESC
LIMIT 20;
```

### MySQL

Enable profiling:
```sql
SET profiling = 1;
SHOW PROFILES;
SHOW PROFILE FOR QUERY 1;
```

Execution plan:
```sql
EXPLAIN ANALYZE SELECT ...;
```

Find slow queries:
```sql
SELECT * FROM performance_schema.events_statements_summary_by_digest
ORDER BY SUM_TIMER_WAIT DESC
LIMIT 20;
```

### SQL Server

Execution plan:
```sql
SET STATISTICS IO ON;
SET STATISTICS TIME ON;
```

Find slow queries:
```sql
SELECT TOP 20
    qs.total_elapsed_time / qs.execution_count AS avg_elapsed,
    qs.execution_count,
    SUBSTRING(qt.text, qs.statement_start_offset / 2, 
        CASE WHEN qs.statement_end_offset = -1 THEN LEN(qt.text)
        ELSE (qs.statement_end_offset - qs.statement_start_offset) / 2 END) AS query
FROM sys.dm_exec_query_stats qs
CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) qt
ORDER BY avg_elapsed DESC;
```

## Execution Plan Analysis

### Common Operations

| Operation | Description | Concern Level |
|-----------|-------------|---------------|
| Seq Scan / Table Scan | Reads entire table | High for large tables |
| Index Scan | Uses index, fetches from table | Good |
| Index Only Scan | Uses index only, no table fetch | Best |
| Bitmap Index Scan | Uses multiple indexes | Good for OR conditions |
| Nested Loop | For each outer row, scan inner | Okay for small inner |
| Hash Join | Build hash, probe | Good for equality joins |
| Merge Join | Sort both, merge | Good for sorted data |
| Sort | Orders result set | Watch memory usage |

### Warning Signs

```
- Seq Scan on large table -> Add index
- High estimated vs actual rows -> Run ANALYZE
- Sort with external merge -> Increase work_mem
- Nested Loop with many iterations -> Check indexes on inner table
- Hash/Sort spilling to disk -> Increase memory settings
```

## Schema Optimization

### Data Types

```
Use appropriate sizes:
- SMALLINT (2 bytes) vs INT (4 bytes) vs BIGINT (8 bytes)
- VARCHAR(50) vs VARCHAR(255) vs TEXT
- TIMESTAMP vs DATE
- DECIMAL(10,2) vs FLOAT

Avoid:
- TEXT/BLOB for small known-length strings
- VARCHAR(MAX) when length is known
- FLOAT for money (use DECIMAL)
```

### Normalization vs Denormalization

```
Normalize for:
- Data integrity
- Reduced redundancy
- Write-heavy workloads

Denormalize for:
- Read-heavy workloads
- Eliminating expensive JOINs
- Reporting/analytics queries
```

### Table Partitioning

PostgreSQL range partitioning:
```sql
CREATE TABLE orders (
    id SERIAL,
    order_date DATE,
    total DECIMAL(10,2)
) PARTITION BY RANGE (order_date);

CREATE TABLE orders_2024_q1 PARTITION OF orders
    FOR VALUES FROM ('2024-01-01') TO ('2024-04-01');
```

Benefits:
- Partition pruning (skip irrelevant partitions)
- Easier data archival/deletion
- Parallel query execution

## Connection and Resource Management

### Connection Pooling

```
Use connection pooler (PgBouncer, ProxySQL):
- Reduces connection overhead
- Limits max connections
- Reuses existing connections
```

### Memory Settings

PostgreSQL:
```sql
shared_buffers = 25% of RAM
work_mem = 256MB (per operation, careful with concurrency)
maintenance_work_mem = 1GB
effective_cache_size = 75% of RAM
```

MySQL:
```sql
innodb_buffer_pool_size = 70% of RAM
query_cache_size = 0 (disabled in MySQL 8.0+)
sort_buffer_size = 4MB
join_buffer_size = 4MB
```

## Lock and Concurrency Issues

### Identifying Locks

PostgreSQL:
```sql
SELECT 
    pid,
    usename,
    pg_blocking_pids(pid) AS blocked_by,
    query
FROM pg_stat_activity
WHERE cardinality(pg_blocking_pids(pid)) > 0;
```

MySQL:
```sql
SELECT * FROM information_schema.INNODB_LOCK_WAITS;
SHOW ENGINE INNODB STATUS;
```

### Lock Prevention

```sql
SELECT ... FOR UPDATE SKIP LOCKED;

UPDATE ... WHERE id IN (
    SELECT id FROM table 
    WHERE condition 
    LIMIT 100 
    FOR UPDATE SKIP LOCKED
);
```

### Deadlock Prevention

- Access tables in consistent order
- Keep transactions short
- Use appropriate isolation levels
- Implement retry logic

## Maintenance Tasks

### Statistics Updates

PostgreSQL:
```sql
ANALYZE table_name;
ANALYZE;
```

MySQL:
```sql
ANALYZE TABLE table_name;
```

SQL Server:
```sql
UPDATE STATISTICS table_name;
```

### Index Maintenance

Reindex bloated indexes:
```sql
REINDEX INDEX idx_name;
REINDEX TABLE table_name;
```

Rebuild (SQL Server):
```sql
ALTER INDEX idx_name ON table_name REBUILD;
```

### Vacuuming (PostgreSQL)

```sql
VACUUM table_name;
VACUUM FULL table_name;
VACUUM ANALYZE table_name;
```

Autovacuum settings:
```sql
autovacuum = on
autovacuum_vacuum_threshold = 50
autovacuum_analyze_threshold = 50
autovacuum_vacuum_scale_factor = 0.1
```

## Monitoring Queries

### Table Size

```sql
SELECT 
    relname AS table,
    pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
    pg_size_pretty(pg_relation_size(relid)) AS table_size,
    pg_size_pretty(pg_indexes_size(relid)) AS index_size
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC;
```

### Index Usage

```sql
SELECT 
    relname AS table,
    indexrelname AS index,
    idx_scan AS scans,
    idx_tup_read AS tuples_read,
    idx_tup_fetch AS tuples_fetched,
    pg_size_pretty(pg_relation_size(indexrelid)) AS size
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;
```

### Unused Indexes

```sql
SELECT 
    relname AS table,
    indexrelname AS index,
    pg_size_pretty(pg_relation_size(indexrelid)) AS size
FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND indexrelid NOT IN (
      SELECT conindid FROM pg_constraint WHERE contype = 'p'
  )
ORDER BY pg_relation_size(indexrelid) DESC;
```

### Cache Hit Ratio

```sql
SELECT 
    sum(heap_blks_hit) / nullif(sum(heap_blks_hit) + sum(heap_blks_read), 0) AS table_hit_ratio,
    sum(idx_blks_hit) / nullif(sum(idx_blks_hit) + sum(idx_blks_read), 0) AS index_hit_ratio
FROM pg_statio_user_tables;
```

## Output Format

When providing performance recommendations:

1. **Current Issue**: What's causing poor performance
2. **Impact**: How it affects the system
3. **Solution**: Specific actions to take
4. **Implementation**: SQL/commands to run
5. **Verification**: How to confirm improvement
6. **Trade-offs**: Any downsides to consider

## Additional Resources

| File | Content |
|------|---------|
| [examples.md](references/examples.md) | Performance tuning case studies |
