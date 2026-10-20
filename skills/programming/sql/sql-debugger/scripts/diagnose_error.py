#!/usr/bin/env python3
"""Explain a database error message and list the likely fixes.

Recognises common errors from PostgreSQL, MySQL/MariaDB, SQL Server, Oracle
and SQLite (by message text or error code), names the dialect, explains the
cause in plain language and gives ordered fixes. Pass the failing query with
--sql to get hints that point at the exact identifier. No dependencies.

Usage:
    python diagnose_error.py "ERROR: column \\"o.total\\" must appear in the GROUP BY clause"
    python diagnose_error.py "ORA-00942: table or view does not exist" --json
    python diagnose_error.py "$(cat error.txt)" --sql query.sql
    python diagnose_error.py --list
"""

import argparse
import json
import re
import sys

# (id, pattern, dialect, cause, fixes)
PATTERNS = [
    ("group-by", r"must appear in the GROUP BY clause|isn't in GROUP BY|not in GROUP BY|ONLY_FULL_GROUP_BY|"
     r"is invalid in the select list because it is not contained in either an aggregate|ORA-00979|not a GROUP BY expression",
     None, "A selected column is neither aggregated nor listed in GROUP BY, so the database can't pick one value per group.",
     ["Add the column to GROUP BY if you want one row per value of it.",
      "Wrap it in an aggregate (MAX, MIN, ANY_VALUE, STRING_AGG) if any value per group is fine.",
      "If you need detail rows next to totals, use a window function: SUM(x) OVER (PARTITION BY ...)."]),
    ("unknown-column", r"column \"?[\w.]+\"? does not exist|Unknown column|Invalid column name|ORA-00904|no such column",
     None, "The query references a column that doesn't exist in that table, or under that alias.",
     ["Check spelling and case: PostgreSQL folds unquoted names to lowercase, so \"UserId\" and userid differ.",
      "Check the table alias: o.customer_id when customer_id lives on c.",
      "A SELECT alias can't be used in WHERE of the same query; repeat the expression or wrap in a subquery/CTE.",
      "List the real columns: information_schema.columns, DESCRIBE t, or PRAGMA table_info(t)."]),
    ("unknown-table", r"relation \"?[\w.]+\"? does not exist|Table '[\w.]+' doesn't exist|Invalid object name|ORA-00942|no such table",
     None, "The table or view isn't visible: wrong name, wrong schema, or missing permissions.",
     ["Qualify it with the schema (sales.orders) or check search_path / current database.",
      "Check case-sensitive quoting: \"Orders\" is not orders in PostgreSQL.",
      "Confirm the migration that creates it has run in this environment.",
      "In Oracle and SQL Server, missing SELECT permission looks the same as a missing table."]),
    ("ambiguous", r"ambiguous|Ambiguous column name|ORA-00918|column ambiguously defined",
     None, "A column name exists in more than one joined table and isn't qualified.",
     ["Prefix the column with its table alias everywhere it appears (SELECT, WHERE, ORDER BY, GROUP BY).",
      "With USING (col) joins, refer to the column without an alias."]),
    ("divide-by-zero", r"division by zero|Divide by zero|ORA-01476", None,
     "A denominator evaluated to 0 for at least one row.",
     ["Use NULLIF(denominator, 0) so the result becomes NULL instead of failing.",
      "Wrap with COALESCE(..., 0) if a zero result is wanted.",
      "MySQL returns NULL silently unless ERROR_FOR_DIVISION_BY_ZERO is set; check for that difference."]),
    ("type-mismatch", r"invalid input syntax for (type )?[\w ]+|operator does not exist|Conversion failed|"
     r"Truncated incorrect|ORA-01722|invalid number|datatype mismatch|cannot be cast", None,
     "Values of different types are compared or converted, e.g. a text column holding non-numeric strings compared to a number.",
     ["Compare like with like: cast the literal, not the column, to keep indexes usable.",
      "Find bad rows first: WHERE col !~ '^[0-9]+$' (PostgreSQL) or TRY_CAST(col AS INT) IS NULL (SQL Server).",
      "Use explicit ISO dates ('2026-10-20') instead of locale-dependent formats."]),
    ("unique-violation", r"duplicate key value violates unique constraint|Duplicate entry|Violation of (PRIMARY KEY|UNIQUE KEY)|"
     r"Cannot insert duplicate key|ORA-00001|UNIQUE constraint failed", None,
     "An INSERT/UPDATE would create a second row with the same key.",
     ["Check whether the row already exists; use an upsert: ON CONFLICT (PostgreSQL/SQLite), "
      "ON DUPLICATE KEY UPDATE (MySQL), MERGE (SQL Server/Oracle).",
      "If ids come from a sequence, it may be behind the data: reset it to MAX(id)+1.",
      "Deduplicate the source rows before inserting (ROW_NUMBER() OVER (PARTITION BY key ...) = 1)."]),
    ("fk-violation", r"violates foreign key constraint|foreign key constraint fails|conflicted with the (FOREIGN KEY|REFERENCE) constraint|"
     r"ORA-02291|ORA-02292|FOREIGN KEY constraint failed", None,
     "The row references a parent that doesn't exist, or you're deleting a parent that still has children.",
     ["Insert the parent row first (or in the same transaction, before the child).",
      "For deletes, delete children first or define ON DELETE CASCADE / SET NULL deliberately.",
      "Find orphans: SELECT c.* FROM child c LEFT JOIN parent p ON p.id = c.parent_id WHERE p.id IS NULL."]),
    ("not-null", r"null value in column .* violates not-null|cannot be null|Cannot insert the value NULL|ORA-01400|NOT NULL constraint failed",
     None, "A NOT NULL column received NULL.",
     ["Provide a value or a DEFAULT for the column.",
      "Check INSERT ... SELECT sources and LEFT JOINs that produce NULLs.",
      "Use COALESCE(source_col, fallback) in the SELECT feeding the insert."]),
    ("syntax", r"syntax error at or near|You have an error in your SQL syntax|Incorrect syntax near|ORA-00933|ORA-00936|"
     r"missing expression|near \".*\": syntax error", None,
     "The parser hit a token it didn't expect. The real mistake is usually just before the reported position.",
     ["Look for a missing or trailing comma just before the reported token.",
      "Check reserved words used as names (order, user, group): quote them or rename.",
      "Check dialect features: LIMIT vs TOP vs FETCH FIRST, || vs CONCAT, ILIKE (PostgreSQL only).",
      "Run the syntax checker skill's check_sql.py with the right --dialect."]),
    ("subquery-rows", r"more than one row returned by a subquery|Subquery returns more than 1 row|"
     r"Subquery returned more than 1 value|ORA-01427", None,
     "A scalar subquery (used with = or in SELECT) returned several rows.",
     ["Use IN / EXISTS instead of = if several matches are valid.",
      "Aggregate or limit inside the subquery (MAX(...), LIMIT 1 with ORDER BY).",
      "Fix the correlation condition so it identifies exactly one row."]),
    ("deadlock", r"deadlock detected|Deadlock found|was deadlocked on lock|ORA-00060", None,
     "Two transactions each held a lock the other needed; the database killed one.",
     ["Retry the transaction: deadlocks are expected under concurrency and should be handled in code.",
      "Access tables and rows in the same order in every code path.",
      "Keep transactions short and index the columns used in UPDATE/DELETE WHERE clauses."]),
    ("lock-timeout", r"lock timeout|Lock wait timeout exceeded|canceling statement due to lock timeout|ORA-00054|database is locked",
     None, "The statement waited too long for a lock held by another session.",
     ["Find the blocker: pg_stat_activity / pg_locks, SHOW PROCESSLIST, sys.dm_exec_requests.",
      "Look for idle-in-transaction sessions and long-running migrations.",
      "SQLite: one writer at a time; use WAL mode and a busy_timeout."]),
    ("statement-timeout", r"canceling statement due to statement timeout|Query execution was interrupted|Execution Timeout Expired|ORA-01013",
     None, "The query ran longer than the configured timeout.",
     ["Run EXPLAIN ANALYZE to find the slow step (see the sql-performance-tuning skill).",
      "Add indexes for the filters and joins, and limit the rows processed.",
      "Only raise the timeout after the query plan is reasonable."]),
    ("permission", r"permission denied|command denied|Access denied|The SELECT permission was denied|ORA-01031|insufficient privileges",
     None, "The current user lacks the privilege for this object or operation.",
     ["GRANT the needed privilege (SELECT/INSERT/UPDATE/USAGE on schema) to the role.",
      "Check which user the application actually connects as.",
      "In PostgreSQL also grant USAGE on the schema, not just the table."]),
    ("value-too-long", r"value too long for type|Data too long for column|String or binary data would be truncated|ORA-12899",
     None, "A value is longer than the column allows.",
     ["Find offending rows: WHERE LENGTH(col) > N (LEN in SQL Server).",
      "Widen the column or truncate intentionally with LEFT(col, N)."]),
    ("numeric-overflow", r"numeric field overflow|out of range|Arithmetic overflow|ORA-01438", None,
     "A number doesn't fit the column's precision or the integer type.",
     ["Use a wider type (BIGINT, NUMERIC with larger precision).",
      "Cast to a wider type before SUM/multiplication: SUM(CAST(x AS BIGINT))."]),
    ("window-in-where", r"window functions are not allowed in WHERE|Windowed functions can only appear in the SELECT or ORDER BY|"
     r"misuse of window function|ORA-30483", None,
     "Window functions run after WHERE, so they can't be filtered there.",
     ["Compute the window function in a CTE/subquery, then filter in the outer query.",
      "Or use QUALIFY where supported (Snowflake, BigQuery, DuckDB)."]),
    ("aggregate-in-where", r"aggregate functions are not allowed in WHERE|Invalid use of group function|"
     r"An aggregate may not appear in the WHERE clause|ORA-00934|misuse of aggregate", None,
     "Aggregates are computed after WHERE.",
     ["Move the condition to HAVING.", "Or aggregate in a subquery/CTE and filter outside it."]),
    ("set-op-columns", r"each (UNION|INTERSECT|EXCEPT) query must have the same number of columns|"
     r"used SELECT statements have a different number of columns|must have an equal number of expressions|ORA-01789",
     None, "The branches of a UNION/INTERSECT/EXCEPT return different column counts.",
     ["Make every branch return the same columns in the same order; pad with NULL AS col where needed.",
      "Check column types line up too (cast if necessary)."]),
]

DIALECT_HINTS = [
    ("PostgreSQL", r"^ERROR:|SQLSTATE|relation \"|psql|pg_"),
    ("MySQL/MariaDB", r"ERROR \d{4}|Unknown column|Duplicate entry|You have an error in your SQL syntax"),
    ("SQL Server", r"Msg \d+|Invalid object name|Incorrect syntax near|Invalid column name"),
    ("Oracle", r"ORA-\d{5}"),
    ("SQLite", r"no such (table|column)|SQLITE_|constraint failed|near \".*\": syntax error"),
]


def quoted_names(err):
    return sorted(set(re.findall(r"[\"'`\[]([\w.]+)[\"'`\]]", err)))


def diagnose(err, sql=None):
    dialect = next((d for d, p in DIALECT_HINTS if re.search(p, err, re.I)), "unknown")
    matches = [p for p in PATTERNS if re.search(p[1], err, re.I)]
    names = quoted_names(err)
    hints = []
    if sql and names:
        for n in names:
            short = n.split(".")[-1]
            lines = [i + 1 for i, line in enumerate(sql.splitlines()) if re.search(rf"\b{re.escape(short)}\b", line, re.I)]
            if lines:
                hints.append(f"'{n}' appears on line(s) {', '.join(map(str, lines))} of the query")
            else:
                hints.append(f"'{n}' does not appear in the query text; the error may come from a view, trigger or default")
    return {
        "dialect": dialect,
        "identifiers": names,
        "matches": [{"id": i, "cause": c, "fixes": f} for i, _, _, c, f in matches],
        "query_hints": hints,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("error", nargs="?", help="error message text (or - to read stdin)")
    ap.add_argument("--sql", help="file with the failing query, to locate identifiers")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ap.add_argument("--list", action="store_true", help="list the error families this script knows")
    args = ap.parse_args()

    if args.list:
        for pid, _, _, cause, _ in PATTERNS:
            print(f"{pid:<20} {cause}")
        return
    if not args.error:
        ap.error("pass an error message, or - to read it from stdin")
    err = sys.stdin.read() if args.error == "-" else args.error
    sql = open(args.sql, encoding="utf-8").read() if args.sql else None
    result = diagnose(err, sql)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Dialect: {result['dialect']}")
        if result["identifiers"]:
            print(f"Identifiers in message: {', '.join(result['identifiers'])}")
        if not result["matches"]:
            print("\nNo known pattern matched. Reduce the query step by step (remove joins/filters) until the error goes away;")
            print("the last thing removed is the culprit.")
        for m in result["matches"]:
            print(f"\nDiagnosis ({m['id']}): {m['cause']}")
            for i, f in enumerate(m["fixes"], 1):
                print(f"  {i}. {f}")
        for h in result["query_hints"]:
            print(f"\nHint: {h}")
    sys.exit(0 if result["matches"] else 1)


if __name__ == "__main__":
    main()
