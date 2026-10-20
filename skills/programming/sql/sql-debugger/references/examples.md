# SQL Debugger Examples

Real-world debugging scenarios with step-by-step solutions.

## Scenario 1: Query Returns No Results

### Problem

```sql
SELECT c.name, o.order_date, o.total
FROM customers c
JOIN orders o ON c.id = o.customer_id
WHERE c.status = 'active'
  AND o.order_date = '2024-01-15';
```

User says: "I know there are orders on this date, but the query returns nothing."

### Debugging Steps

Step 1: Check if customers exist
```sql
SELECT COUNT(*) FROM customers WHERE status = 'active';
```

Step 2: Check if orders exist for that date
```sql
SELECT COUNT(*) FROM orders WHERE order_date = '2024-01-15';
```

Step 3: Check data type of order_date
```sql
SELECT order_date, pg_typeof(order_date) FROM orders LIMIT 1;
```

Step 4: Check actual values
```sql
SELECT DISTINCT order_date::date FROM orders 
WHERE order_date >= '2024-01-15' AND order_date < '2024-01-16';
```

### Root Cause

`order_date` is a TIMESTAMP, not DATE. Comparing `'2024-01-15'` only matches exactly midnight.

### Solution

```sql
SELECT c.name, o.order_date, o.total
FROM customers c
JOIN orders o ON c.id = o.customer_id
WHERE c.status = 'active'
  AND o.order_date >= '2024-01-15'
  AND o.order_date < '2024-01-16';
```

Or:
```sql
  AND DATE(o.order_date) = '2024-01-15';
```

## Scenario 2: Aggregate Values Too High

### Problem

```sql
SELECT 
    c.id,
    c.name,
    COUNT(o.id) AS order_count,
    SUM(oi.quantity) AS total_items
FROM customers c
JOIN orders o ON c.id = o.customer_id
JOIN order_items oi ON o.id = oi.order_id
GROUP BY c.id, c.name;
```

User says: "The total_items count is way higher than it should be."

### Debugging Steps

Step 1: Check a single customer manually
```sql
SELECT c.id, c.name, o.id AS order_id, oi.id AS item_id, oi.quantity
FROM customers c
JOIN orders o ON c.id = o.customer_id
JOIN order_items oi ON o.id = oi.order_id
WHERE c.id = 123;
```

Step 2: Count distinct values
```sql
SELECT 
    c.id,
    COUNT(o.id) AS counted_orders,
    COUNT(DISTINCT o.id) AS distinct_orders
FROM customers c
JOIN orders o ON c.id = o.customer_id
JOIN order_items oi ON o.id = oi.order_id
WHERE c.id = 123
GROUP BY c.id;
```

### Root Cause

Each order with multiple items creates multiple rows, inflating the order count.

### Solution

```sql
SELECT 
    c.id,
    c.name,
    COUNT(DISTINCT o.id) AS order_count,
    SUM(oi.quantity) AS total_items
FROM customers c
JOIN orders o ON c.id = o.customer_id
JOIN order_items oi ON o.id = oi.order_id
GROUP BY c.id, c.name;
```

Or use subqueries:
```sql
SELECT 
    c.id,
    c.name,
    (SELECT COUNT(*) FROM orders WHERE customer_id = c.id) AS order_count,
    (SELECT SUM(oi.quantity) 
     FROM orders o 
     JOIN order_items oi ON o.id = oi.order_id 
     WHERE o.customer_id = c.id) AS total_items
FROM customers c;
```

## Scenario 3: NULL Values Causing Issues

### Problem

```sql
SELECT 
    employee_id,
    base_salary + bonus + commission AS total_compensation
FROM employees;
```

User says: "Some employees show NULL for total_compensation even though they have a salary."

### Debugging Steps

Step 1: Check for NULLs
```sql
SELECT 
    employee_id,
    base_salary,
    bonus,
    commission,
    base_salary + bonus + commission AS total
FROM employees
WHERE base_salary + bonus + commission IS NULL
LIMIT 10;
```

### Root Cause

Any arithmetic with NULL produces NULL. Some employees have NULL bonus or commission.

### Solution

```sql
SELECT 
    employee_id,
    COALESCE(base_salary, 0) + COALESCE(bonus, 0) + COALESCE(commission, 0) AS total_compensation
FROM employees;
```

## Scenario 4: Division by Zero

### Problem

```sql
SELECT 
    product_id,
    total_sales / total_orders AS avg_sale
FROM product_stats;
```

Error: `division by zero`

### Debugging Steps

Step 1: Find rows with zero orders
```sql
SELECT * FROM product_stats WHERE total_orders = 0;
```

### Solution

```sql
SELECT 
    product_id,
    CASE 
        WHEN total_orders = 0 THEN 0
        ELSE total_sales / total_orders 
    END AS avg_sale
FROM product_stats;
```

Or:
```sql
SELECT 
    product_id,
    total_sales / NULLIF(total_orders, 0) AS avg_sale
FROM product_stats;
```

## Scenario 5: Missing Rows After LEFT JOIN

### Problem

```sql
SELECT c.name, COUNT(o.id) AS order_count
FROM customers c
LEFT JOIN orders o ON c.id = o.customer_id
WHERE o.status = 'completed'
GROUP BY c.name;
```

User says: "Customers with no orders are missing from results."

### Debugging Steps

Step 1: Remove the WHERE and check
```sql
SELECT c.name, o.id, o.status
FROM customers c
LEFT JOIN orders o ON c.id = o.customer_id
WHERE c.id IN (SELECT id FROM customers WHERE id NOT IN (SELECT customer_id FROM orders))
LIMIT 10;
```

### Root Cause

WHERE clause filters out NULL rows from LEFT JOIN. Customers without orders have `o.status = NULL`, which fails the `= 'completed'` check.

### Solution

Move filter to JOIN condition:
```sql
SELECT c.name, COUNT(o.id) AS order_count
FROM customers c
LEFT JOIN orders o ON c.id = o.customer_id AND o.status = 'completed'
GROUP BY c.name;
```

## Scenario 6: Duplicate Results

### Problem

```sql
SELECT u.id, u.email, r.name AS role_name
FROM users u
JOIN user_roles ur ON u.id = ur.user_id
JOIN roles r ON ur.role_id = r.id
WHERE u.id = 123;
```

User says: "This returns 3 rows for one user. I expected 1 row."

### Debugging Steps

Step 1: Check user_roles
```sql
SELECT * FROM user_roles WHERE user_id = 123;
```

### Root Cause

User has multiple roles assigned. The query correctly returns one row per role.

### Solution (depends on requirement)

If you want one row with all roles:
```sql
SELECT u.id, u.email, STRING_AGG(r.name, ', ') AS roles
FROM users u
JOIN user_roles ur ON u.id = ur.user_id
JOIN roles r ON ur.role_id = r.id
WHERE u.id = 123
GROUP BY u.id, u.email;
```

If you want just the primary role:
```sql
SELECT u.id, u.email, r.name AS role_name
FROM users u
JOIN user_roles ur ON u.id = ur.user_id AND ur.is_primary = true
JOIN roles r ON ur.role_id = r.id
WHERE u.id = 123;
```

## Scenario 7: Incorrect String Matching

### Problem

```sql
SELECT * FROM products WHERE name = 'Widget';
```

User says: "Returns nothing, but I can see 'Widget' in the table."

### Debugging Steps

Step 1: Check for whitespace or encoding
```sql
SELECT 
    name,
    LENGTH(name) AS len,
    name = 'Widget' AS matches
FROM products
WHERE name LIKE '%Widget%';
```

Step 2: Check for invisible characters
```sql
SELECT 
    name,
    encode(name::bytea, 'hex') AS hex_value
FROM products
WHERE name LIKE '%Widget%';
```

### Root Cause

Leading/trailing whitespace or non-printable characters.

### Solution

```sql
SELECT * FROM products WHERE TRIM(name) = 'Widget';
```

Or fix the data:
```sql
UPDATE products SET name = TRIM(name);
```

## Scenario 8: Subquery Returns Multiple Rows

### Problem

```sql
SELECT 
    p.name,
    (SELECT c.name FROM categories c WHERE c.id = p.category_id) AS category_name
FROM products p;
```

Error: `more than one row returned by a subquery used as an expression`

### Debugging Steps

Step 1: Find products with multiple category matches
```sql
SELECT p.id, p.category_id, COUNT(*)
FROM products p
JOIN categories c ON c.id = p.category_id
GROUP BY p.id, p.category_id
HAVING COUNT(*) > 1;
```

Step 2: Check for duplicate category IDs
```sql
SELECT id, COUNT(*) FROM categories GROUP BY id HAVING COUNT(*) > 1;
```

### Root Cause

Duplicate rows in categories table (data integrity issue) or wrong comparison logic.

### Solution

If duplicates are valid, limit to one:
```sql
SELECT 
    p.name,
    (SELECT c.name FROM categories c WHERE c.id = p.category_id LIMIT 1) AS category_name
FROM products p;
```

Better - use JOIN:
```sql
SELECT p.name, c.name AS category_name
FROM products p
LEFT JOIN categories c ON c.id = p.category_id;
```

## Scenario 9: GROUP BY Error

### Problem

```sql
SELECT customer_id, name, SUM(total) AS total_spent
FROM orders o
JOIN customers c ON o.customer_id = c.id
GROUP BY customer_id;
```

Error: `column "c.name" must appear in GROUP BY clause`

### Root Cause

`name` is not in GROUP BY but also not aggregated.

### Solution

```sql
SELECT o.customer_id, c.name, SUM(o.total) AS total_spent
FROM orders o
JOIN customers c ON o.customer_id = c.id
GROUP BY o.customer_id, c.name;
```

Or if customer_id determines name (functional dependency):
```sql
SELECT o.customer_id, MAX(c.name) AS name, SUM(o.total) AS total_spent
FROM orders o
JOIN customers c ON o.customer_id = c.id
GROUP BY o.customer_id;
```

## Scenario 10: Date Comparison Issues

### Problem

```sql
SELECT * FROM events
WHERE event_date BETWEEN '2024-01-01' AND '2024-01-31';
```

User says: "Missing events from January 31st."

### Debugging Steps

Step 1: Check data type and values
```sql
SELECT event_date, pg_typeof(event_date)
FROM events
WHERE event_date >= '2024-01-31'
ORDER BY event_date
LIMIT 5;
```

### Root Cause

`event_date` is TIMESTAMP. `'2024-01-31'` is interpreted as `'2024-01-31 00:00:00'`, excluding later times on Jan 31.

### Solution

```sql
SELECT * FROM events
WHERE event_date >= '2024-01-01'
  AND event_date < '2024-02-01';
```

Or be explicit:
```sql
SELECT * FROM events
WHERE event_date BETWEEN '2024-01-01 00:00:00' AND '2024-01-31 23:59:59';
```

## Scenario 11: Case Sensitivity Issues

### Problem

```sql
SELECT * FROM users WHERE email = 'John@Example.com';
```

User says: "User exists but query returns nothing."

### Debugging Steps

```sql
SELECT email FROM users WHERE LOWER(email) = LOWER('John@Example.com');
```

### Root Cause

PostgreSQL string comparison is case-sensitive by default.

### Solution

```sql
SELECT * FROM users WHERE LOWER(email) = LOWER('John@Example.com');
```

Or use case-insensitive comparison:
```sql
SELECT * FROM users WHERE email ILIKE 'John@Example.com';
```

Or create a functional index:
```sql
CREATE INDEX idx_users_email_lower ON users(LOWER(email));
```

## Scenario 12: Circular Reference in CTE

### Problem

```sql
WITH RECURSIVE tree AS (
    SELECT id, parent_id, name, 0 AS depth
    FROM categories
    WHERE parent_id IS NULL
    
    UNION ALL
    
    SELECT c.id, c.parent_id, c.name, t.depth + 1
    FROM categories c
    JOIN tree t ON c.parent_id = t.id
)
SELECT * FROM tree;
```

Query runs forever or hits recursion limit.

### Debugging Steps

Step 1: Check for circular references
```sql
WITH RECURSIVE check_circular AS (
    SELECT id, parent_id, ARRAY[id] AS path, false AS is_cycle
    FROM categories
    
    UNION ALL
    
    SELECT c.id, c.parent_id, cc.path || c.id, c.id = ANY(cc.path)
    FROM categories c
    JOIN check_circular cc ON c.parent_id = cc.id
    WHERE NOT cc.is_cycle
)
SELECT * FROM check_circular WHERE is_cycle;
```

### Root Cause

A category has itself as an ancestor (circular reference in data).

### Solution

Add cycle detection:
```sql
WITH RECURSIVE tree AS (
    SELECT id, parent_id, name, 0 AS depth, ARRAY[id] AS path
    FROM categories
    WHERE parent_id IS NULL
    
    UNION ALL
    
    SELECT c.id, c.parent_id, c.name, t.depth + 1, t.path || c.id
    FROM categories c
    JOIN tree t ON c.parent_id = t.id
    WHERE NOT (c.id = ANY(t.path))
)
SELECT * FROM tree;
```

Or fix the data:
```sql
UPDATE categories SET parent_id = NULL WHERE id = [circular_id];
```
