#!/usr/bin/env python3
"""Translate SQL from one dialect to another with sqlglot.

Requires: pip install sqlglot

Usage:
    python translate_sql.py query.sql --from mysql --to postgres
    echo "SELECT TOP 10 * FROM t" | python translate_sql.py - --from tsql --to mysql

Always review the output: constructs with no equivalent in the target dialect
are reported as warnings on stderr and must be fixed by hand.

Exit code: 0 = translated, 1 = parse/translation error, 2 = bad usage or sqlglot missing.
"""

import argparse
import logging
import sys

DIALECTS = {
    "postgres": "postgres", "postgresql": "postgres",
    "mysql": "mysql", "mariadb": "mysql",
    "tsql": "tsql", "sqlserver": "tsql", "mssql": "tsql",
    "oracle": "oracle",
    "sqlite": "sqlite",
    "bigquery": "bigquery", "snowflake": "snowflake", "duckdb": "duckdb",
    "redshift": "redshift", "spark": "spark",
}


def resolve(ap, name):
    dialect = DIALECTS.get(name.lower())
    if not dialect:
        ap.error(f"unknown dialect {name!r}; choose from {', '.join(sorted(set(DIALECTS)))}")
    return dialect


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", help="SQL file path, or - for stdin")
    ap.add_argument("--from", dest="src", required=True, help="source dialect")
    ap.add_argument("--to", dest="dst", required=True, help="target dialect")
    ap.add_argument("--compact", action="store_true", help="do not pretty-print output")
    args = ap.parse_args()
    src, dst = resolve(ap, args.src), resolve(ap, args.dst)

    try:
        import sqlglot
        from sqlglot.errors import ErrorLevel, SqlglotError
    except ImportError:
        print("sqlglot is not installed. Run: pip install sqlglot", file=sys.stderr)
        sys.exit(2)

    logging.basicConfig(format="warning: %(message)s", level=logging.WARNING, stream=sys.stderr)
    sql = sys.stdin.read() if args.file == "-" else open(args.file, encoding="utf-8").read()
    try:
        out = sqlglot.transpile(sql, read=src, write=dst, pretty=not args.compact,
                                unsupported_level=ErrorLevel.WARN)
    except SqlglotError as e:
        print(f"Translation failed: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"-- Translated from {src} to {dst} with sqlglot {sqlglot.__version__}; review before running")
    print(";\n\n".join(out) + ";")


if __name__ == "__main__":
    main()
