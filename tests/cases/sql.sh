# SQL skill script cases. Syntax: see tests/run_tests.sh.

t 'plan_joins: bridge tables' 0 'JOIN order_items AS oi' \
  "$SQL/sql-query-writer/scripts/plan_joins.py" "$FX/schema.sql" --tables customers products
t 'plan_joins: no path' 1 'no foreign-key path' \
  "$SQL/sql-query-writer/scripts/plan_joins.py" "$FX/schema.sql" --tables customers audit_log
t 'check_sql: catches errors' 1 'Trailing comma before FROM' \
  "$SQL/sql-syntax-checker/scripts/check_sql.py" "$FX/bad.sql"
STDIN='SELECT id FROM users WHERE active = 1' t 'check_sql: clean query' 0 'Status: VALID' \
  "$SQL/sql-syntax-checker/scripts/check_sql.py" -
t 'outline_query: execution order' 0 'LEFT OUTER JOIN: segments s USING (customer_id)' \
  "$SQL/sql-query-explainer/scripts/outline_query.py" "$FX/query.sql"
t 'find_antipatterns: slow query' 1 'NOT IN with a subquery' \
  "$SQL/sql-optimizer/scripts/find_antipatterns.py" "$FX/slow.sql" --strict
t 'analyze_plan: spills and scans' 0 'Sort spilled to disk' \
  "$SQL/sql-performance-tuning/scripts/analyze_plan.py" "$FX/plan.json"
t 'diagnose_error: postgres group by' 0 'Dialect: PostgreSQL' \
  "$SQL/sql-debugger/scripts/diagnose_error.py" 'ERROR: column "o.total" must appear in the GROUP BY clause'
t 'diagnose_error: oracle code' 0 unknown-column \
  "$SQL/sql-debugger/scripts/diagnose_error.py" 'ORA-00904: invalid identifier'
t 'sql_sandbox: running total' 0 11300 \
  "$SQL/sql-window-functions/scripts/sql_sandbox.py" --demo --query 'SELECT SUM(revenue) OVER (ORDER BY month, region ROWS UNBOUNDED PRECEDING) AS r FROM sales ORDER BY r DESC LIMIT 1'
t 'analytics_sql: funnel runs in sqlite' 0 pct_of_previous \
  "$SQL/sql-analytics/scripts/analytics_sql.py" funnel --table events --user user_id --ts created_at --event-col event_name --steps signup activate purchase --dialect sqlite
t 'date_ranges: literal mtd' 0 "created_at >= DATE '2026-10-01'" \
  "$SQL/sql-reporting/scripts/date_ranges.py" mtd --literal --as-of 2026-10-20
t 'profile_data: csv gate' 1 '2 duplicate keys' \
  "$SQL/sql-data-quality/scripts/profile_data.py" csv "$FX/customers.csv" --key id --fail-on duplicate_keys=0
t 'profile_data: sql mode' 0 'HAVING COUNT(*) > 1' \
  "$SQL/sql-data-quality/scripts/profile_data.py" sql --table t --columns a --key a

# translate_sql.py needs the optional sqlglot package; without it it must fail with an install hint.
if python3 -c 'import sqlglot' 2>/dev/null; then
  STDIN='SELECT TOP 5 name FROM users' t 'translate_sql: tsql to postgres' 0 'LIMIT 5' \
    "$SQL/sql-dialect-translator/scripts/translate_sql.py" - --from tsql --to postgres
else
  STDIN='SELECT 1' t 'translate_sql: missing sqlglot hint' 2 'pip install sqlglot' \
    "$SQL/sql-dialect-translator/scripts/translate_sql.py" - --from tsql --to postgres
fi
