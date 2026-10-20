# SQL Syntax Checker Examples

Common syntax errors with explanations and corrections.

## Structural Errors

### Missing FROM Clause

Error:
```sql
SELECT id, name WHERE status = 'active';
```

Fixed:
```sql
SELECT id, name FROM users WHERE status = 'active';
```

Explanation: SELECT requires a FROM clause to specify the source table.

### Wrong Clause Order

Error:
```sql
SELECT * FROM users ORDER BY name WHERE status = 'active';
```

Fixed:
```sql
SELECT * FROM users WHERE status = 'active' ORDER BY name;
```

Explanation: WHERE must come before ORDER BY. Correct order: FROM -> WHERE -> GROUP BY -> HAVING -> ORDER BY -> LIMIT.

### Missing Semicolon (Multi-Statement)

Error:
```sql
SELECT * FROM users
SELECT * FROM orders
```

Fixed:
```sql
SELECT * FROM users;
SELECT * FROM orders;
```

Explanation: When running multiple statements, each must be terminated with a semicolon.

## Quote and Literal Errors

### Wrong String Quotes

Error (Standard SQL):
```sql
SELECT * FROM users WHERE name = "John";
```

Fixed:
```sql
SELECT * FROM users WHERE name = 'John';
```

Explanation: Standard SQL uses single quotes for string literals. Double quotes are for identifiers (or backticks in MySQL).

### Unescaped Quote in String

Error:
```sql
SELECT * FROM posts WHERE title = 'It's a test';
```

Fixed:
```sql
SELECT * FROM posts WHERE title = 'It''s a test';
```

Or with escape (PostgreSQL, MySQL):
```sql
SELECT * FROM posts WHERE title = 'It\'s a test';
```

Explanation: Single quotes inside strings must be escaped by doubling them.

### Missing Quotes on String

Error:
```sql
SELECT * FROM users WHERE status = active;
```

Fixed:
```sql
SELECT * FROM users WHERE status = 'active';
```

Explanation: String values must be enclosed in quotes; otherwise they're interpreted as column names.

## Column and Reference Errors

### Misspelled Column Name

Error:
```sql
SELECT id, nmae, email FROM users;
```

Fixed:
```sql
SELECT id, name, email FROM users;
```

Explanation: Column names must match exactly (case-sensitivity depends on dialect and configuration).

### Missing Comma in Column List

Error:
```sql
SELECT 
    id
    name
    email
FROM users;
```

Fixed:
```sql
SELECT 
    id,
    name,
    email
FROM users;
```

Explanation: Columns in SELECT must be separated by commas.

### Extra Comma at End

Error:
```sql
SELECT id, name, email, FROM users;
```

Fixed:
```sql
SELECT id, name, email FROM users;
```

Explanation: Trailing comma before FROM is not allowed.

### Ambiguous Column in JOIN

Error:
```sql
SELECT id, name, order_date 
FROM users u 
JOIN orders o ON u.id = o.user_id;
```

Fixed:
```sql
SELECT u.id, u.name, o.order_date 
FROM users u 
JOIN orders o ON u.id = o.user_id;
```

Explanation: When joining tables, columns that exist in multiple tables must be qualified with table alias.

## JOIN Errors

### Missing ON Condition

Error:
```sql
SELECT * FROM users u JOIN orders o;
```

Fixed:
```sql
SELECT * FROM users u JOIN orders o ON u.id = o.user_id;
```

Explanation: INNER/LEFT/RIGHT JOIN requires an ON clause specifying the join condition.

### CROSS JOIN with ON

Error:
```sql
SELECT * FROM users CROSS JOIN roles ON users.role_id = roles.id;
```

Fixed (if you want filtered join):
```sql
SELECT * FROM users JOIN roles ON users.role_id = roles.id;
```

Fixed (if you want cartesian product):
```sql
SELECT * FROM users CROSS JOIN roles;
```

Explanation: CROSS JOIN produces cartesian product and doesn't use ON clause.

### Using WHERE Instead of ON

Technically valid but poor practice:
```sql
SELECT * FROM users u, orders o WHERE u.id = o.user_id;
```

Better:
```sql
SELECT * FROM users u JOIN orders o ON u.id = o.user_id;
```

Explanation: Explicit JOIN syntax is clearer and prevents accidental cartesian products.

## GROUP BY Errors

### Non-Aggregated Column Not in GROUP BY

Error:
```sql
SELECT department, employee_name, COUNT(*)
FROM employees
GROUP BY department;
```

Fixed (aggregate the column):
```sql
SELECT department, STRING_AGG(employee_name, ', '), COUNT(*)
FROM employees
GROUP BY department;
```

Or (add to GROUP BY):
```sql
SELECT department, employee_name, COUNT(*)
FROM employees
GROUP BY department, employee_name;
```

Explanation: All columns in SELECT must either be in GROUP BY or be aggregated.

### HAVING Without GROUP BY

Warning (valid but suspicious):
```sql
SELECT * FROM orders HAVING total > 100;
```

Probably meant:
```sql
SELECT * FROM orders WHERE total > 100;
```

Or:
```sql
SELECT customer_id, SUM(total) 
FROM orders 
GROUP BY customer_id 
HAVING SUM(total) > 100;
```

Explanation: HAVING is for filtering groups; use WHERE for row-level filtering.

### Using Column Alias in HAVING

Error (most dialects):
```sql
SELECT department, COUNT(*) AS emp_count
FROM employees
GROUP BY department
HAVING emp_count > 5;
```

Fixed:
```sql
SELECT department, COUNT(*) AS emp_count
FROM employees
GROUP BY department
HAVING COUNT(*) > 5;
```

Explanation: Column aliases defined in SELECT are not available in HAVING (except MySQL).

## Subquery Errors

### Subquery Returns Multiple Rows with = Operator

Error:
```sql
SELECT * FROM products 
WHERE category_id = (SELECT id FROM categories WHERE active = true);
```

Fixed (if expecting multiple):
```sql
SELECT * FROM products 
WHERE category_id IN (SELECT id FROM categories WHERE active = true);
```

Fixed (if expecting one):
```sql
SELECT * FROM products 
WHERE category_id = (SELECT id FROM categories WHERE active = true LIMIT 1);
```

Explanation: When using = with subquery, the subquery must return exactly one value.

### Subquery Column Not Accessible

Error:
```sql
SELECT * FROM users 
WHERE id IN (SELECT user_id, amount FROM orders WHERE amount > 100);
```

Fixed:
```sql
SELECT * FROM users 
WHERE id IN (SELECT user_id FROM orders WHERE amount > 100);
```

Explanation: Subquery used with IN must return exactly one column.

### Correlated Subquery Reference Error

Error:
```sql
SELECT * FROM orders o 
WHERE total > (SELECT AVG(total) FROM orders WHERE customer_id = c.id);
```

Fixed:
```sql
SELECT * FROM orders o 
WHERE total > (SELECT AVG(total) FROM orders WHERE customer_id = o.customer_id);
```

Explanation: Correlated subqueries must reference columns from the outer query using correct alias.

## NULL Handling Errors

### Using = NULL Instead of IS NULL

Error:
```sql
SELECT * FROM users WHERE deleted_at = NULL;
```

Fixed:
```sql
SELECT * FROM users WHERE deleted_at IS NULL;
```

Explanation: NULL comparisons must use IS NULL or IS NOT NULL; = NULL always returns unknown.

### NOT IN with NULL Values

Problematic:
```sql
SELECT * FROM products 
WHERE id NOT IN (SELECT product_id FROM discontinued);
```

If discontinued.product_id contains NULL, this returns no rows.

Fixed:
```sql
SELECT * FROM products 
WHERE id NOT IN (SELECT product_id FROM discontinued WHERE product_id IS NOT NULL);
```

Or better:
```sql
SELECT * FROM products p
WHERE NOT EXISTS (SELECT 1 FROM discontinued d WHERE d.product_id = p.id);
```

## Type Mismatch Errors

### Comparing String to Number

Error:
```sql
SELECT * FROM users WHERE id = 'abc';
```

Fixed (if id is numeric):
```sql
SELECT * FROM users WHERE id = 123;
```

Fixed (if looking for string):
```sql
SELECT * FROM users WHERE username = 'abc';
```

### Date Format Issues

Error (ambiguous):
```sql
SELECT * FROM orders WHERE order_date = '01/02/2024';
```

Fixed (use ISO format):
```sql
SELECT * FROM orders WHERE order_date = '2024-01-02';
```

Explanation: ISO 8601 format (YYYY-MM-DD) is unambiguous and works across all dialects.

### Boolean Comparison

Error (Oracle has no boolean):
```sql
SELECT * FROM users WHERE is_active = TRUE;
```

Fixed (Oracle):
```sql
SELECT * FROM users WHERE is_active = 1;
```

Fixed (PostgreSQL, most others):
```sql
SELECT * FROM users WHERE is_active = true;
```

Or simply:
```sql
SELECT * FROM users WHERE is_active;
```

## Pagination Errors

### OFFSET Without LIMIT

Error (PostgreSQL):
```sql
SELECT * FROM products OFFSET 10;
```

Fixed:
```sql
SELECT * FROM products LIMIT 100 OFFSET 10;
```

### MySQL LIMIT Syntax Mix-up

Error:
```sql
SELECT * FROM products LIMIT 10, 20 OFFSET 0;
```

Fixed (choose one syntax):
```sql
SELECT * FROM products LIMIT 20 OFFSET 10;
```

Or:
```sql
SELECT * FROM products LIMIT 10, 20;
```

Explanation: MySQL's `LIMIT offset, count` and `LIMIT count OFFSET offset` shouldn't be mixed.

## CTE Errors

### Missing CTE Name

Error:
```sql
WITH AS (
    SELECT * FROM users WHERE status = 'active'
)
SELECT * FROM active_users;
```

Fixed:
```sql
WITH active_users AS (
    SELECT * FROM users WHERE status = 'active'
)
SELECT * FROM active_users;
```

### CTE Not Used

Warning:
```sql
WITH active_users AS (
    SELECT * FROM users WHERE status = 'active'
)
SELECT * FROM users;
```

Fixed:
```sql
WITH active_users AS (
    SELECT * FROM users WHERE status = 'active'
)
SELECT * FROM active_users;
```

### Recursive CTE Missing UNION

Error:
```sql
WITH RECURSIVE org_tree AS (
    SELECT id, name, manager_id FROM employees WHERE manager_id IS NULL
)
SELECT * FROM org_tree;
```

Fixed:
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
SELECT * FROM org_tree;
```

## INSERT/UPDATE/DELETE Errors

### INSERT Column Count Mismatch

Error:
```sql
INSERT INTO users (id, name, email)
VALUES (1, 'John');
```

Fixed:
```sql
INSERT INTO users (id, name, email)
VALUES (1, 'John', 'john@example.com');
```

### UPDATE Without WHERE

Warning (affects all rows):
```sql
UPDATE users SET status = 'inactive';
```

Probably meant:
```sql
UPDATE users SET status = 'inactive' WHERE last_login < '2023-01-01';
```

### DELETE Without WHERE

Warning (deletes all rows):
```sql
DELETE FROM users;
```

Probably meant:
```sql
DELETE FROM users WHERE status = 'deleted';
```

Or:
```sql
TRUNCATE TABLE users;
```

### SET Using Wrong Operator

Error:
```sql
UPDATE users SET status == 'active' WHERE id = 1;
```

Fixed:
```sql
UPDATE users SET status = 'active' WHERE id = 1;
```

Explanation: Assignment in SET uses single equals =, not comparison ==.

## Window Function Errors

### Window Function in WHERE

Error:
```sql
SELECT * FROM employees 
WHERE ROW_NUMBER() OVER (ORDER BY salary DESC) <= 10;
```

Fixed:
```sql
SELECT * FROM (
    SELECT *, ROW_NUMBER() OVER (ORDER BY salary DESC) AS rn
    FROM employees
) ranked
WHERE rn <= 10;
```

Explanation: Window functions cannot be used in WHERE; use a subquery or CTE.

### Missing OVER Clause

Error:
```sql
SELECT id, name, ROW_NUMBER() FROM employees;
```

Fixed:
```sql
SELECT id, name, ROW_NUMBER() OVER (ORDER BY id) FROM employees;
```

Explanation: Window functions require an OVER clause.

### Invalid Frame Specification

Error:
```sql
SELECT id, SUM(amount) OVER (ORDER BY date ROWS UNBOUNDED) 
FROM transactions;
```

Fixed:
```sql
SELECT id, SUM(amount) OVER (ORDER BY date ROWS UNBOUNDED PRECEDING) 
FROM transactions;
```

Explanation: Frame specification needs PRECEDING or FOLLOWING keyword.
