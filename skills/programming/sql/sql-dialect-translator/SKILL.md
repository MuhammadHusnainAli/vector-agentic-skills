---
name: sql-dialect-translator
description: Translate SQL between dialects — PostgreSQL, MySQL, SQL Server (T-SQL), Oracle, SQLite — covering data types, functions, pagination, date handling, upserts and identity columns. Use when migrating queries between databases or the user asks to convert SQL to another dialect. Includes a sqlglot-based translation script.
metadata:
  category: programming
  subcategory: sql
  version: "1.0.0"
---

# SQL Dialect Translator

Convert SQL queries between different database dialects (PostgreSQL, MySQL, SQL Server, Oracle, SQLite).

## Trigger Conditions

Activate this skill when the user:
- Says "convert to PostgreSQL/MySQL/etc."
- Asks to migrate queries between databases
- Needs help with dialect-specific syntax
- Asks about differences between SQL dialects
- Has queries failing after database migration

## Translation Workflow

```
1. IDENTIFY    -> Detect source dialect
2. ANALYZE     -> Find dialect-specific features
3. MAP         -> Identify equivalent features in target
4. TRANSLATE   -> Convert syntax
5. VALIDATE    -> Verify correctness
6. OPTIMIZE    -> Apply target dialect best practices
```

## Dialect Feature Comparison

### Data Types

| Feature | PostgreSQL | MySQL | SQL Server | Oracle | SQLite |
|---------|------------|-------|------------|--------|--------|
| Auto-increment | SERIAL, BIGSERIAL | AUTO_INCREMENT | IDENTITY | SEQUENCE | INTEGER PRIMARY KEY |
| Boolean | BOOLEAN | TINYINT(1), BOOLEAN | BIT | NUMBER(1) | INTEGER |
| Text (unlimited) | TEXT | LONGTEXT | VARCHAR(MAX) | CLOB | TEXT |
| Binary | BYTEA | BLOB | VARBINARY(MAX) | BLOB | BLOB |
| JSON | JSON, JSONB | JSON | NVARCHAR(MAX) | JSON (21c+) | TEXT |
| UUID | UUID | CHAR(36) | UNIQUEIDENTIFIER | RAW(16) | TEXT |
| Date | DATE | DATE | DATE | DATE | TEXT |
| Timestamp | TIMESTAMP | DATETIME | DATETIME2 | TIMESTAMP | TEXT |
| Array | ARRAY[] | JSON | N/A | VARRAY | N/A |

### String Functions

| Operation | PostgreSQL | MySQL | SQL Server | Oracle |
|-----------|------------|-------|------------|--------|
| Concatenate | `\|\|` or CONCAT | CONCAT | + or CONCAT | `\|\|` |
| Substring | SUBSTRING(s, start, len) | SUBSTRING(s, start, len) | SUBSTRING(s, start, len) | SUBSTR(s, start, len) |
| Length | LENGTH | LENGTH, CHAR_LENGTH | LEN | LENGTH |
| Lowercase | LOWER | LOWER | LOWER | LOWER |
| Uppercase | UPPER | UPPER | UPPER | UPPER |
| Trim | TRIM | TRIM | LTRIM, RTRIM | TRIM |
| Position | POSITION(x IN y) | LOCATE(x, y) | CHARINDEX(x, y) | INSTR(y, x) |
| Replace | REPLACE | REPLACE | REPLACE | REPLACE |
| Pad left | LPAD | LPAD | RIGHT(REPLICATE...) | LPAD |
| Regex match | ~ | REGEXP | LIKE (limited) | REGEXP_LIKE |

### Date/Time Functions

| Operation | PostgreSQL | MySQL | SQL Server | Oracle |
|-----------|------------|-------|------------|--------|
| Current date | CURRENT_DATE | CURDATE() | GETDATE() | SYSDATE |
| Current timestamp | CURRENT_TIMESTAMP | NOW() | GETDATE() | SYSTIMESTAMP |
| Extract part | EXTRACT(part FROM date) | EXTRACT(part FROM date) | DATEPART(part, date) | EXTRACT(part FROM date) |
| Date add | date + INTERVAL '1 day' | DATE_ADD(date, INTERVAL 1 DAY) | DATEADD(day, 1, date) | date + 1 |
| Date diff | date1 - date2 | DATEDIFF(date1, date2) | DATEDIFF(day, date1, date2) | date1 - date2 |
| Format date | TO_CHAR(date, 'fmt') | DATE_FORMAT(date, 'fmt') | FORMAT(date, 'fmt') | TO_CHAR(date, 'fmt') |
| Parse date | TO_DATE(str, 'fmt') | STR_TO_DATE(str, 'fmt') | CONVERT(date, str) | TO_DATE(str, 'fmt') |
| Truncate | DATE_TRUNC('month', date) | DATE_FORMAT(date, '%Y-%m-01') | DATETRUNC(month, date) | TRUNC(date, 'MM') |

### Limiting Results

| Dialect | Syntax |
|---------|--------|
| PostgreSQL | `LIMIT 10 OFFSET 20` |
| MySQL | `LIMIT 10 OFFSET 20` or `LIMIT 20, 10` |
| SQL Server | `OFFSET 20 ROWS FETCH NEXT 10 ROWS ONLY` (2012+) or `TOP 10` |
| Oracle | `OFFSET 20 ROWS FETCH NEXT 10 ROWS ONLY` (12c+) or `ROWNUM` |
| SQLite | `LIMIT 10 OFFSET 20` |

### Identifier Quoting

| Dialect | Syntax |
|---------|--------|
| PostgreSQL | Double quotes: `"table"` |
| MySQL | Backticks: \`table\` |
| SQL Server | Square brackets: `[table]` or double quotes |
| Oracle | Double quotes: `"TABLE"` (case-sensitive) |
| SQLite | Double quotes, backticks, or square brackets |

### NULL Handling

| Operation | PostgreSQL | MySQL | SQL Server | Oracle |
|-----------|------------|-------|------------|--------|
| Coalesce | COALESCE, NULLIF | COALESCE, IFNULL, NULLIF | COALESCE, ISNULL, NULLIF | COALESCE, NVL, NULLIF |
| NULL-safe equal | IS NOT DISTINCT FROM | <=> | N/A | N/A |
| First non-null | COALESCE | COALESCE | COALESCE | NVL, COALESCE |

### Conditional Logic

| Operation | PostgreSQL | MySQL | SQL Server | Oracle |
|-----------|------------|-------|------------|--------|
| If-then | CASE WHEN | CASE WHEN, IF() | CASE WHEN, IIF() | CASE WHEN, DECODE |
| Null check | NULLIF, COALESCE | NULLIF, IFNULL | NULLIF, ISNULL | NVL, NVL2 |

### Upsert/Merge

PostgreSQL:
```sql
INSERT INTO table (id, name) VALUES (1, 'test')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name;
```

MySQL:
```sql
INSERT INTO table (id, name) VALUES (1, 'test')
ON DUPLICATE KEY UPDATE name = VALUES(name);
```

SQL Server:
```sql
MERGE INTO table AS target
USING (VALUES (1, 'test')) AS source (id, name)
ON target.id = source.id
WHEN MATCHED THEN UPDATE SET name = source.name
WHEN NOT MATCHED THEN INSERT (id, name) VALUES (source.id, source.name);
```

Oracle:
```sql
MERGE INTO table target
USING (SELECT 1 AS id, 'test' AS name FROM dual) source
ON (target.id = source.id)
WHEN MATCHED THEN UPDATE SET target.name = source.name
WHEN NOT MATCHED THEN INSERT (id, name) VALUES (source.id, source.name);
```

### Common Table Expressions

All modern versions support standard CTE syntax:
```sql
WITH cte AS (
    SELECT ...
)
SELECT * FROM cte;
```

Recursive CTEs:
- PostgreSQL: `WITH RECURSIVE`
- MySQL 8.0+: `WITH RECURSIVE`
- SQL Server: `WITH` (recursive by default when self-referencing)
- Oracle: `WITH` (use CONNECT BY for older versions)

### Window Functions

All modern databases support standard window functions. Key differences:

| Feature | PostgreSQL | MySQL | SQL Server | Oracle |
|---------|------------|-------|------------|--------|
| FILTER clause | Yes | No | No | No |
| Frame: GROUPS | Yes | Yes (8.0+) | No | Yes |
| PERCENTILE_CONT | Yes | No (use variable) | Yes | Yes |
| STRING_AGG | STRING_AGG | GROUP_CONCAT | STRING_AGG | LISTAGG |

### JSON Support

PostgreSQL:
```sql
SELECT data->>'name' FROM table;
SELECT data->'nested'->>'field' FROM table;
SELECT data @> '{"key": "value"}' FROM table;
```

MySQL:
```sql
SELECT JSON_EXTRACT(data, '$.name') FROM table;
SELECT data->'$.name' FROM table;
SELECT JSON_CONTAINS(data, '"value"', '$.key') FROM table;
```

SQL Server:
```sql
SELECT JSON_VALUE(data, '$.name') FROM table;
SELECT JSON_QUERY(data, '$.nested') FROM table;
```

## Translation Examples

### LIMIT/OFFSET Translation

PostgreSQL:
```sql
SELECT * FROM users ORDER BY id LIMIT 10 OFFSET 20;
```

To SQL Server:
```sql
SELECT * FROM users ORDER BY id OFFSET 20 ROWS FETCH NEXT 10 ROWS ONLY;
```

To Oracle (12c+):
```sql
SELECT * FROM users ORDER BY id OFFSET 20 ROWS FETCH NEXT 10 ROWS ONLY;
```

To Oracle (11g):
```sql
SELECT * FROM (
    SELECT t.*, ROWNUM rn FROM (
        SELECT * FROM users ORDER BY id
    ) t WHERE ROWNUM <= 30
) WHERE rn > 20;
```

### Auto-Increment Translation

PostgreSQL:
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100)
);
```

To MySQL:
```sql
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100)
);
```

To SQL Server:
```sql
CREATE TABLE users (
    id INT IDENTITY(1,1) PRIMARY KEY,
    name VARCHAR(100)
);
```

To Oracle:
```sql
CREATE TABLE users (
    id NUMBER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    name VARCHAR2(100)
);
```

### String Concatenation Translation

PostgreSQL:
```sql
SELECT first_name || ' ' || last_name AS full_name FROM users;
```

To MySQL:
```sql
SELECT CONCAT(first_name, ' ', last_name) AS full_name FROM users;
```

To SQL Server:
```sql
SELECT first_name + ' ' + last_name AS full_name FROM users;
SELECT CONCAT(first_name, ' ', last_name) AS full_name FROM users;
```

### Date Arithmetic Translation

PostgreSQL:
```sql
SELECT created_at + INTERVAL '30 days' FROM users;
SELECT DATE_TRUNC('month', created_at) FROM users;
```

To MySQL:
```sql
SELECT DATE_ADD(created_at, INTERVAL 30 DAY) FROM users;
SELECT DATE_FORMAT(created_at, '%Y-%m-01') FROM users;
```

To SQL Server:
```sql
SELECT DATEADD(day, 30, created_at) FROM users;
SELECT DATETRUNC(month, created_at) FROM users;  -- SQL Server 2022+
SELECT DATEFROMPARTS(YEAR(created_at), MONTH(created_at), 1) FROM users;  -- Earlier
```

To Oracle:
```sql
SELECT created_at + 30 FROM users;
SELECT TRUNC(created_at, 'MM') FROM users;
```

### Boolean Translation

PostgreSQL:
```sql
SELECT * FROM users WHERE is_active = TRUE;
```

To MySQL:
```sql
SELECT * FROM users WHERE is_active = 1;
SELECT * FROM users WHERE is_active = TRUE;  -- Also works
```

To SQL Server:
```sql
SELECT * FROM users WHERE is_active = 1;
```

To Oracle:
```sql
SELECT * FROM users WHERE is_active = 1;
```

## Output Format

When translating queries:

1. **Source**: Original query with identified dialect
2. **Target**: Translated query for target dialect
3. **Changes Made**: List of modifications
4. **Caveats**: Any functionality differences or limitations
5. **Alternatives**: Other approaches if applicable

## Scripts

Use the translator for a first draft, then review it against the feature comparison above:

```bash
pip install sqlglot
python scripts/translate_sql.py query.sql --from mysql --to postgres
echo "SELECT TOP 10 * FROM t" | python scripts/translate_sql.py - --from tsql --to oracle
```

Constructs with no equivalent in the target dialect are printed as warnings on stderr. Fix those by hand and list them under **Caveats**.

## Additional Resources

| File | Content |
|------|---------|
| [examples.md](references/examples.md) | Complete translation examples |
