---
name: sql-query-writer
description: Write correct, readable SQL from natural-language requirements — SELECT, INSERT, UPDATE, DELETE, JOINs, subqueries, CTEs and DDL (CREATE/ALTER/DROP). Use when the user asks to write, create or generate a query, describes data they want to retrieve, or provides a schema and wants queries against it.
metadata:
  category: programming
  subcategory: sql
  version: "1.0.0"
---

# SQL Query Writer

Write SQL queries from natural language requirements with proper syntax, structure, and best practices.

## Trigger Conditions

Activate this skill when the user:
- Says "write a query", "create SQL", "generate SQL"
- Describes data they want to retrieve
- Asks for INSERT, UPDATE, DELETE statements
- Needs DDL (CREATE, ALTER, DROP) statements
- Provides a schema and asks for queries against it

## Query Writing Workflow

```
1. UNDERSTAND  -> Parse requirements, identify tables/columns needed
2. IDENTIFY    -> Determine query type (SELECT, INSERT, UPDATE, etc.)
3. STRUCTURE   -> Plan JOINs, subqueries, CTEs as needed
4. WRITE       -> Generate syntactically correct SQL
5. VALIDATE    -> Check for common issues
6. OPTIMIZE    -> Suggest indexes or improvements if relevant
```

## Pre-Flight Checklist

Before writing any query:

```
- [ ] Identified the target database dialect
- [ ] Understood the table schema (columns, types, relationships)
- [ ] Clarified any ambiguous requirements
- [ ] Determined if query needs to handle NULLs
- [ ] Identified any performance considerations
```

## SELECT Query Patterns

### Basic SELECT

```sql
SELECT column1, column2, column3
FROM table_name
WHERE condition
ORDER BY column1;
```

### SELECT with JOINs

```sql
SELECT 
    a.column1,
    b.column2,
    c.column3
FROM table_a a
INNER JOIN table_b b ON a.id = b.a_id
LEFT JOIN table_c c ON b.id = c.b_id
WHERE a.status = 'active'
ORDER BY a.created_at DESC;
```

### SELECT with Aggregation

```sql
SELECT 
    category,
    COUNT(*) AS total_count,
    SUM(amount) AS total_amount,
    AVG(amount) AS avg_amount
FROM transactions
WHERE transaction_date >= '2024-01-01'
GROUP BY category
HAVING SUM(amount) > 1000
ORDER BY total_amount DESC;
```

### SELECT with Subquery

```sql
SELECT *
FROM employees
WHERE department_id IN (
    SELECT id 
    FROM departments 
    WHERE budget > 100000
);
```

### SELECT with CTE

```sql
WITH active_customers AS (
    SELECT customer_id, SUM(order_total) AS total_spent
    FROM orders
    WHERE order_date >= CURRENT_DATE - INTERVAL '1 year'
    GROUP BY customer_id
),
customer_tiers AS (
    SELECT 
        customer_id,
        total_spent,
        CASE 
            WHEN total_spent >= 10000 THEN 'Gold'
            WHEN total_spent >= 5000 THEN 'Silver'
            ELSE 'Bronze'
        END AS tier
    FROM active_customers
)
SELECT c.name, c.email, ct.tier, ct.total_spent
FROM customers c
JOIN customer_tiers ct ON c.id = ct.customer_id
ORDER BY ct.total_spent DESC;
```

## INSERT Patterns

### Single Row Insert

```sql
INSERT INTO table_name (column1, column2, column3)
VALUES ('value1', 'value2', 'value3');
```

### Multi-Row Insert

```sql
INSERT INTO table_name (column1, column2, column3)
VALUES 
    ('value1a', 'value2a', 'value3a'),
    ('value1b', 'value2b', 'value3b'),
    ('value1c', 'value2c', 'value3c');
```

### Insert from SELECT

```sql
INSERT INTO archive_table (id, name, created_at)
SELECT id, name, created_at
FROM source_table
WHERE created_at < '2023-01-01';
```

### Insert with Returning (PostgreSQL)

```sql
INSERT INTO users (name, email)
VALUES ('John Doe', 'john@example.com')
RETURNING id, created_at;
```

### Upsert / Insert or Update

PostgreSQL:
```sql
INSERT INTO products (sku, name, price)
VALUES ('ABC123', 'Widget', 29.99)
ON CONFLICT (sku) 
DO UPDATE SET 
    name = EXCLUDED.name,
    price = EXCLUDED.price,
    updated_at = CURRENT_TIMESTAMP;
```

MySQL:
```sql
INSERT INTO products (sku, name, price)
VALUES ('ABC123', 'Widget', 29.99)
ON DUPLICATE KEY UPDATE 
    name = VALUES(name),
    price = VALUES(price),
    updated_at = CURRENT_TIMESTAMP;
```

SQL Server:
```sql
MERGE INTO products AS target
USING (VALUES ('ABC123', 'Widget', 29.99)) AS source (sku, name, price)
ON target.sku = source.sku
WHEN MATCHED THEN
    UPDATE SET name = source.name, price = source.price
WHEN NOT MATCHED THEN
    INSERT (sku, name, price) VALUES (source.sku, source.name, source.price);
```

## UPDATE Patterns

### Basic Update

```sql
UPDATE table_name
SET column1 = 'new_value',
    column2 = column2 + 1,
    updated_at = CURRENT_TIMESTAMP
WHERE id = 123;
```

### Update with JOIN

PostgreSQL:
```sql
UPDATE orders o
SET status = 'shipped',
    shipped_at = CURRENT_TIMESTAMP
FROM shipments s
WHERE s.order_id = o.id
  AND s.status = 'delivered';
```

MySQL:
```sql
UPDATE orders o
JOIN shipments s ON s.order_id = o.id
SET o.status = 'shipped',
    o.shipped_at = CURRENT_TIMESTAMP
WHERE s.status = 'delivered';
```

SQL Server:
```sql
UPDATE o
SET status = 'shipped',
    shipped_at = GETDATE()
FROM orders o
JOIN shipments s ON s.order_id = o.id
WHERE s.status = 'delivered';
```

### Update with Subquery

```sql
UPDATE products
SET price = price * 1.10
WHERE category_id IN (
    SELECT id FROM categories WHERE name = 'Electronics'
);
```

## DELETE Patterns

### Basic Delete

```sql
DELETE FROM table_name
WHERE condition;
```

### Delete with JOIN

PostgreSQL:
```sql
DELETE FROM order_items oi
USING orders o
WHERE oi.order_id = o.id
  AND o.status = 'cancelled';
```

MySQL:
```sql
DELETE oi
FROM order_items oi
JOIN orders o ON oi.order_id = o.id
WHERE o.status = 'cancelled';
```

### Soft Delete Pattern

```sql
UPDATE records
SET deleted_at = CURRENT_TIMESTAMP,
    deleted_by = 'user_id'
WHERE id = 123;
```

### Truncate (Remove All Rows)

```sql
TRUNCATE TABLE table_name;
TRUNCATE TABLE table_name RESTART IDENTITY CASCADE; -- PostgreSQL
```

## DDL Patterns

### Create Table

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,                    -- PostgreSQL
    -- id INT AUTO_INCREMENT PRIMARY KEY,     -- MySQL
    -- id INT IDENTITY(1,1) PRIMARY KEY,      -- SQL Server
    
    email VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    balance DECIMAL(10, 2) DEFAULT 0.00,
    metadata JSONB,                           -- PostgreSQL
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT chk_status CHECK (status IN ('active', 'inactive', 'suspended'))
);
```

### Create Index

```sql
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_status_created ON users(status, created_at);
CREATE UNIQUE INDEX idx_users_email_unique ON users(email);
CREATE INDEX idx_users_name_lower ON users(LOWER(name)); -- Functional index
```

### Alter Table

```sql
ALTER TABLE users ADD COLUMN phone VARCHAR(20);
ALTER TABLE users DROP COLUMN deprecated_field;
ALTER TABLE users ALTER COLUMN name TYPE VARCHAR(200);
ALTER TABLE users ADD CONSTRAINT fk_department 
    FOREIGN KEY (department_id) REFERENCES departments(id);
```

### Create View

```sql
CREATE VIEW active_users_summary AS
SELECT 
    u.id,
    u.name,
    u.email,
    COUNT(o.id) AS order_count,
    COALESCE(SUM(o.total), 0) AS total_spent
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE u.status = 'active'
GROUP BY u.id, u.name, u.email;
```

## Complex Query Patterns

### Pagination

Offset-based (simple but slow for large offsets):
```sql
SELECT * FROM products
ORDER BY created_at DESC
LIMIT 20 OFFSET 40;
```

Cursor-based (efficient for large datasets):
```sql
SELECT * FROM products
WHERE created_at < '2024-01-15 10:30:00'
ORDER BY created_at DESC
LIMIT 20;
```

### Hierarchical Data (Recursive CTE)

```sql
WITH RECURSIVE org_tree AS (
    SELECT id, name, manager_id, 1 AS level
    FROM employees
    WHERE manager_id IS NULL
    
    UNION ALL
    
    SELECT e.id, e.name, e.manager_id, ot.level + 1
    FROM employees e
    JOIN org_tree ot ON e.manager_id = ot.id
)
SELECT * FROM org_tree
ORDER BY level, name;
```

### Pivot Data

PostgreSQL:
```sql
SELECT 
    product_id,
    SUM(CASE WHEN month = 1 THEN sales ELSE 0 END) AS jan,
    SUM(CASE WHEN month = 2 THEN sales ELSE 0 END) AS feb,
    SUM(CASE WHEN month = 3 THEN sales ELSE 0 END) AS mar
FROM monthly_sales
GROUP BY product_id;
```

SQL Server:
```sql
SELECT product_id, [1] AS jan, [2] AS feb, [3] AS mar
FROM monthly_sales
PIVOT (SUM(sales) FOR month IN ([1], [2], [3])) AS pvt;
```

### Dynamic Date Ranges

```sql
SELECT 
    date_trunc('month', order_date) AS month,
    COUNT(*) AS order_count,
    SUM(total) AS revenue
FROM orders
WHERE order_date >= date_trunc('year', CURRENT_DATE)
GROUP BY date_trunc('month', order_date)
ORDER BY month;
```

## Anti-Patterns to Avoid

| Anti-Pattern | Problem | Better Approach |
|--------------|---------|-----------------|
| SELECT * | Returns unnecessary data | List specific columns |
| N+1 queries | Multiple round trips | Use JOINs or batch queries |
| Functions on indexed columns | Prevents index usage | Move function to value side |
| Implicit type conversion | Performance and accuracy issues | Use explicit CAST |
| Missing WHERE on UPDATE/DELETE | Affects all rows | Always include WHERE |
| Correlated subqueries | Executes per row | Use JOINs or CTEs |

## Output Format

When writing queries, provide:

1. The SQL query with proper formatting
2. Brief explanation of what the query does
3. Any assumptions made about the schema
4. Performance considerations if relevant
5. Alternative approaches if applicable

## Scripts

Given the schema, let the planner find join paths instead of guessing them:

```bash
python scripts/plan_joins.py schema.sql --list                       # tables, keys, relationships
python scripts/plan_joins.py schema.sql --tables customers products \
    --columns customers.email,products.name                           # adds bridge tables automatically
```

It parses CREATE TABLE statements (PostgreSQL, MySQL, SQL Server, SQLite), follows foreign keys with a shortest-path search and prints a SELECT skeleton with aliases and ON clauses. Exit code `1` means there is no foreign-key path, so ask the user how the tables relate rather than inventing a join.

## Additional Resources

| File | Content |
|------|---------|
| [examples.md](references/examples.md) | Production-ready query examples by use case |
| [sql-quick-reference.md](references/sql-quick-reference.md) | Dialects, clause order, JOIN types, operators, best practices and the pre-output checklist |
