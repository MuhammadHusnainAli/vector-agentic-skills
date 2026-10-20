# SQL Quick Reference

Dialect support, clause order, JOIN types, operators, best practices and the validation checklist to run before returning any SQL.

## Supported Database Dialects

| Dialect | Version Support | Key Differences |
|---------|-----------------|-----------------|
| PostgreSQL | 12+ | Rich functions, JSONB, arrays, CTEs |
| MySQL | 8.0+ | AUTO_INCREMENT, backticks, LIMIT syntax |
| SQL Server | 2016+ | TOP, IDENTITY, T-SQL extensions |
| Oracle | 19c+ | ROWNUM, sequences, PL/SQL |
| SQLite | 3.35+ | Lightweight, limited types, file-based |

## Query Structure Reference

### SELECT Statement Components

```sql
SELECT [DISTINCT] columns
FROM table
[JOIN other_table ON condition]
[WHERE filter_condition]
[GROUP BY grouping_columns]
[HAVING aggregate_condition]
[ORDER BY sort_columns]
[LIMIT n OFFSET m]
```

### Common Clause Order

1. SELECT - What columns to return
2. FROM - Source table(s)
3. JOIN - Additional tables with relationships
4. WHERE - Row-level filtering (before grouping)
5. GROUP BY - Aggregate grouping
6. HAVING - Aggregate filtering (after grouping)
7. ORDER BY - Result sorting
8. LIMIT/OFFSET - Pagination

## Best Practices Summary

### Query Writing
- Use explicit column names, avoid SELECT *
- Alias tables and complex expressions
- Use parameterized queries to prevent SQL injection
- Format queries for readability

### Performance
- Index columns used in WHERE, JOIN, ORDER BY
- Avoid functions on indexed columns in WHERE
- Use EXISTS instead of IN for subqueries
- Limit result sets with appropriate filtering

### Maintainability
- Use CTEs for complex multi-step queries
- Add meaningful aliases
- Break complex logic into views or functions
- Document business logic in comments

## Error Handling Pattern

```sql
-- PostgreSQL
BEGIN;
    -- your queries here
    IF condition THEN
        RAISE EXCEPTION 'Error message';
    END IF;
COMMIT;

-- SQL Server
BEGIN TRY
    BEGIN TRANSACTION;
    -- your queries here
    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    ROLLBACK TRANSACTION;
    THROW;
END CATCH;
```

## Quick Reference Cards

### Aggregation Functions
| Function | Purpose |
|----------|---------|
| COUNT(*) | Total rows |
| COUNT(col) | Non-NULL values |
| SUM(col) | Total of values |
| AVG(col) | Average value |
| MIN(col) | Minimum value |
| MAX(col) | Maximum value |
| GROUP_CONCAT / STRING_AGG | Concatenate values |

### JOIN Types
| Type | Returns |
|------|---------|
| INNER JOIN | Matching rows only |
| LEFT JOIN | All left + matching right |
| RIGHT JOIN | All right + matching left |
| FULL OUTER JOIN | All rows from both |
| CROSS JOIN | Cartesian product |

### Common Operators
| Operator | Usage |
|----------|-------|
| = | Exact match |
| <> or != | Not equal |
| LIKE | Pattern match |
| IN | Value in list |
| BETWEEN | Range inclusive |
| IS NULL | NULL check |
| EXISTS | Subquery has results |

## Validation Checklist

Before outputting any SQL:

- [ ] Syntax is valid for target dialect
- [ ] Table and column names exist
- [ ] JOIN conditions are complete (no cartesian products)
- [ ] WHERE clause has appropriate filters
- [ ] GROUP BY includes all non-aggregated columns
- [ ] ORDER BY columns are in SELECT or valid
- [ ] Parameters are properly escaped/parameterized
- [ ] Query handles NULL values appropriately
