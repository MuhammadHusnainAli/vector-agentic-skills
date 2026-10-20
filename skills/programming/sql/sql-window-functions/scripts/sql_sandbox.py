#!/usr/bin/env python3
"""Run a SQL query against CSV files in an in-memory SQLite database.

Use it to prove a window-function query returns what you claim before handing
it over: load sample rows, run the query, check rankings, running totals and
frame boundaries row by row. SQLite (3.25+) supports ROW_NUMBER, RANK,
DENSE_RANK, NTILE, LAG/LEAD, FIRST_VALUE/LAST_VALUE/NTH_VALUE, aggregate
windows and ROWS/RANGE/GROUPS frames. No dependencies.

Usage:
    python sql_sandbox.py --demo --query "SELECT region, month, revenue,
        SUM(revenue) OVER (PARTITION BY region ORDER BY month) AS running FROM sales"
    python sql_sandbox.py --csv sales.csv --query-file query.sql
    python sql_sandbox.py --csv orders.csv --csv customers=clients.csv --query "SELECT ..."
    python sql_sandbox.py --demo --schema          # show tables and column types

--csv path loads into a table named after the file; use name=path to rename.
Column types are inferred (INTEGER, REAL, TEXT). Exit code 1 on SQL errors.
"""

import argparse
import csv
import io
import json
import re
import sqlite3
import sys

DEMO = """region,month,rep,revenue
North,2026-01,Ana,1200
North,2026-02,Ana,1500
North,2026-03,Ben,900
North,2026-04,Ben,1500
South,2026-01,Cy,800
South,2026-02,Cy,950
South,2026-03,Dee,950
South,2026-04,Dee,1300
West,2026-01,Eve,400
West,2026-02,Eve,
West,2026-03,Fay,700
West,2026-04,Fay,1100
"""


def infer(values):
    vals = [v for v in values if v not in ("", None)]
    if not vals:
        return "TEXT"
    if all(re.fullmatch(r"-?\d+", v) for v in vals):
        return "INTEGER"
    if all(re.fullmatch(r"-?\d*\.?\d+(e-?\d+)?", v, re.I) for v in vals):
        return "REAL"
    return "TEXT"


def load_csv(conn, table, handle):
    rows = list(csv.reader(handle))
    if not rows:
        raise ValueError(f"{table}: empty CSV")
    header = [re.sub(r"\W+", "_", h.strip()).strip("_").lower() or f"col{i}" for i, h in enumerate(rows[0])]
    data = rows[1:]
    types = [infer([r[i] if i < len(r) else "" for r in data]) for i in range(len(header))]
    cols = ", ".join(f'"{h}" {t}' for h, t in zip(header, types))
    conn.execute(f'CREATE TABLE "{table}" ({cols})')

    def convert(v, t):
        if v == "":
            return None
        return int(v) if t == "INTEGER" else float(v) if t == "REAL" else v

    conn.executemany(
        f'INSERT INTO "{table}" VALUES ({", ".join("?" * len(header))})',
        [[convert(r[i] if i < len(r) else "", t) for i, t in enumerate(types)] for r in data],
    )
    return len(data)


def print_table(cursor, rows, max_width):
    headers = [d[0] for d in cursor.description]
    cells = [["NULL" if v is None else (f"{v:.4g}" if isinstance(v, float) else str(v)) for v in r] for r in rows]
    widths = [min(max([len(h)] + [len(r[i]) for r in cells]), max_width) for i, h in enumerate(headers)]

    def fmt(vals):
        return " | ".join(v[:w].ljust(w) for v, w in zip(vals, widths))

    print(fmt(headers))
    print("-+-".join("-" * w for w in widths))
    for r in cells:
        print(fmt(r))
    print(f"({len(rows)} row{'s' if len(rows) != 1 else ''})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", action="append", default=[], help="CSV to load: path or table=path (repeatable)")
    ap.add_argument("--demo", action="store_true", help="load a demo 'sales' table (region, month, rep, revenue)")
    ap.add_argument("--query", help="SQL to run (several statements allowed; the last result is shown)")
    ap.add_argument("--query-file", help="file containing the SQL to run")
    ap.add_argument("--schema", action="store_true", help="print loaded tables and column types")
    ap.add_argument("--json", action="store_true", help="print results as JSON rows")
    ap.add_argument("--max-width", type=int, default=40, help="truncate columns wider than this (default 40)")
    args = ap.parse_args()

    conn = sqlite3.connect(":memory:")
    try:
        if args.demo:
            load_csv(conn, "sales", io.StringIO(DEMO))
        for spec in args.csv:
            table, _, path = spec.rpartition("=")
            table = table or re.sub(r"\W+", "_", path.rsplit("/", 1)[-1].rsplit(".", 1)[0]).lower()
            with open(path, newline="", encoding="utf-8-sig") as fh:
                n = load_csv(conn, table, fh)
            print(f"loaded {n} rows into {table}", file=sys.stderr)
    except (OSError, ValueError, sqlite3.Error) as e:
        print(f"Load error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.schema:
        for (name, sql) in conn.execute("SELECT name, sql FROM sqlite_master WHERE type = 'table'"):
            print(sql + ";")
    query = open(args.query_file, encoding="utf-8").read() if args.query_file else args.query
    if not query:
        if not args.schema:
            ap.error("pass --query or --query-file (or --schema)")
        return

    statements = [s for s in re.split(r";\s*(?=(?:[^']*'[^']*')*[^']*$)", query) if s.strip()]
    try:
        cur = None
        for stmt in statements:
            cur = conn.execute(stmt)
        rows = cur.fetchall() if cur and cur.description else []
    except sqlite3.Error as e:
        print(f"SQL error: {e}", file=sys.stderr)
        if "OVER" in query.upper() and sqlite3.sqlite_version_info < (3, 25):
            print(f"SQLite {sqlite3.sqlite_version} has no window functions (needs 3.25+).", file=sys.stderr)
        sys.exit(1)

    if not cur or not cur.description:
        print("Statement executed (no result set).")
    elif args.json:
        cols = [d[0] for d in cur.description]
        print(json.dumps([dict(zip(cols, r)) for r in rows], indent=2))
    else:
        print_table(cur, rows, args.max_width)


if __name__ == "__main__":
    main()
