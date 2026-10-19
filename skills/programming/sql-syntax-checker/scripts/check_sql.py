#!/usr/bin/env python3
"""Check SQL for syntax errors and common mistakes.

Runs dependency-free structural checks (unbalanced parentheses, unterminated
quotes, trailing commas, UPDATE/DELETE without WHERE, `= NULL`, SELECT *).
If `sqlglot` is installed (`pip install sqlglot`), every statement is also
parsed with the chosen dialect's grammar.

Usage:
    python check_sql.py query.sql --dialect postgres
    echo "SELECT a, FROM t" | python check_sql.py - --dialect mysql
    python check_sql.py query.sql --json

Exit code: 0 = no errors, 1 = errors found, 2 = bad usage.
"""

import argparse
import json
import re
import sys

DIALECTS = {
    "postgres": "postgres", "postgresql": "postgres",
    "mysql": "mysql", "mariadb": "mysql",
    "tsql": "tsql", "sqlserver": "tsql", "mssql": "tsql",
    "oracle": "oracle",
    "sqlite": "sqlite",
    "bigquery": "bigquery", "snowflake": "snowflake", "duckdb": "duckdb",
}


def mask(sql):
    """Blank out string literals, quoted identifiers and comments.

    Returns (masked_sql, errors). Masked text keeps offsets and newlines so
    line numbers stay correct.
    """
    out, errors = list(sql), []
    i, n = 0, len(sql)
    while i < n:
        c = sql[i]
        if sql.startswith("--", i):
            j = sql.find("\n", i)
            j = n if j == -1 else j
            out[i:j] = " " * (j - i)
            i = j
        elif sql.startswith("/*", i):
            j = sql.find("*/", i + 2)
            if j == -1:
                errors.append((line_of(sql, i), "Unterminated block comment /* ..."))
                j = n
            else:
                j += 2
            out[i:j] = [ch if ch == "\n" else " " for ch in sql[i:j]]
            i = j
        elif c in "'\"`":
            j = i + 1
            while j < n:
                if sql[j] == c:
                    if j + 1 < n and sql[j + 1] == c:  # doubled quote escape
                        j += 2
                        continue
                    break
                j += 1
            if j >= n:
                kind = "string literal" if c == "'" else "quoted identifier"
                errors.append((line_of(sql, i), f"Unterminated {kind} starting with {c}"))
            out[i + 1:j] = [ch if ch == "\n" else " " for ch in sql[i + 1:j]]
            i = j + 1
        else:
            i += 1
    return "".join(out), errors


def line_of(text, offset):
    return text.count("\n", 0, offset) + 1


def split_statements(masked):
    """Yield (start_offset, statement_text) for each ;-separated statement."""
    start = 0
    for m in re.finditer(";", masked):
        yield start, masked[start:m.start()]
        start = m.end()
    yield start, masked[start:]


def structural_checks(sql):
    masked, errors = mask(sql)
    warnings = []

    stack = []
    for m in re.finditer(r"[()]", masked):
        if m.group() == "(":
            stack.append(m.start())
        elif stack:
            stack.pop()
        else:
            errors.append((line_of(sql, m.start()), "Unmatched closing parenthesis ')'"))
    for pos in stack:
        errors.append((line_of(sql, pos), "Unclosed parenthesis '('"))

    for m in re.finditer(r",\s*(FROM|WHERE|GROUP\s+BY|ORDER\s+BY|HAVING|LIMIT|\))", masked, re.I):
        errors.append((line_of(sql, m.start()), f"Trailing comma before {m.group(1).upper()}"))

    for m in re.finditer(r"(?<![<>!])(=|<>|!=)\s*NULL\b", masked, re.I):
        errors.append((line_of(sql, m.start()),
                       f"'{m.group(1)} NULL' is never true; use IS NULL / IS NOT NULL"))

    for start, stmt in split_statements(masked):
        body = stmt.strip()
        if not body:
            continue
        line = line_of(sql, start + len(stmt) - len(stmt.lstrip()))
        head = body.split(None, 1)[0].upper()
        if head in ("UPDATE", "DELETE") and not re.search(r"\bWHERE\b", body, re.I):
            warnings.append((line, f"{head} without WHERE affects every row in the table"))
        if re.search(r"\bSELECT\s+(DISTINCT\s+)?\*", body, re.I):
            warnings.append((line, "SELECT * - list columns explicitly"))
        if re.search(r"\bFROM\s+\w+(\s+\w+)?\s*,\s*\w+", body, re.I) and not re.search(r"\bWHERE\b", body, re.I):
            warnings.append((line, "Comma-separated FROM without WHERE produces a cartesian product"))

    return errors, warnings


def parser_checks(sql, dialect):
    """Parse with sqlglot when available. Returns (errors, parser_used)."""
    try:
        import sqlglot
        from sqlglot.errors import ParseError, TokenError
    except ImportError:
        return [], False
    errors = []
    try:
        sqlglot.parse(sql, read=dialect)
    except ParseError as e:
        for err in e.errors or [{"description": str(e), "line": None}]:
            errors.append((err.get("line"), f"Parser: {err.get('description')}"))
    except TokenError as e:
        errors.append((None, f"Tokenizer: {e}"))
    return errors, True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", help="SQL file path, or - for stdin")
    ap.add_argument("--dialect", default="postgres", help="postgres|mysql|tsql|oracle|sqlite|... (default: postgres)")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args()

    dialect = DIALECTS.get(args.dialect.lower())
    if not dialect:
        ap.error(f"unknown dialect {args.dialect!r}; choose from {', '.join(sorted(set(DIALECTS)))}")
    sql = sys.stdin.read() if args.file == "-" else open(args.file, encoding="utf-8").read()

    errors, warnings = structural_checks(sql)
    parse_errors, parsed = parser_checks(sql, dialect)
    errors += parse_errors
    status = "INVALID" if errors else "VALID"

    if args.json:
        print(json.dumps({
            "status": status,
            "dialect": dialect,
            "parser": "sqlglot" if parsed else None,
            "errors": [{"line": l, "message": m} for l, m in errors],
            "warnings": [{"line": l, "message": m} for l, m in warnings],
        }, indent=2))
    else:
        print(f"Status: {status}  (dialect: {dialect}, parser: {'sqlglot' if parsed else 'structural checks only'})")
        for title, items in (("Errors", errors), ("Warnings", warnings)):
            if items:
                print(f"\n{title}:")
                for k, (line, msg) in enumerate(items, 1):
                    print(f"{k}. {'Line ' + str(line) + ': ' if line else ''}{msg}")
        if not parsed:
            print("\nTip: pip install sqlglot for full grammar validation.")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
