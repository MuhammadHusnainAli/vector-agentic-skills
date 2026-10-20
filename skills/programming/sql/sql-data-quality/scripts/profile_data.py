#!/usr/bin/env python3
"""Profile data quality, either by generating SQL or by reading a CSV directly.

sql mode   Generate one profiling query per column (row count, NULLs, blanks,
           distinct values, min/max, min/max length) plus duplicate-key and
           orphan checks, for the table and columns you name.
csv mode   Profile a CSV export locally: per-column type guess, NULL/blank %,
           distinct count, min/max, top values, plus duplicate rows and
           duplicate keys. Exit code 1 if --fail-on thresholds are breached,
           so it can gate a pipeline.

Usage:
    python profile_data.py sql --table customers --columns id email country created_at --key id --dialect postgres
    python profile_data.py sql --table orders --columns id customer_id --fk customer_id=customers.id
    python profile_data.py csv customers.csv --key id
    python profile_data.py csv customers.csv --key email --fail-on null_pct=5 duplicate_keys=0 --json

No dependencies.
"""

import argparse
import collections
import csv
import datetime as dt
import json
import re
import sys


def ident(name):
    if not re.fullmatch(r"[A-Za-z_][\w.]*", name):
        raise argparse.ArgumentTypeError(f"invalid identifier: {name!r}")
    return name


def length_fn(dialect):
    return {"tsql": "LEN", "oracle": "LENGTH"}.get(dialect, "LENGTH")


def text_cast(col, dialect):
    return {"tsql": f"CAST({col} AS NVARCHAR(MAX))", "mysql": f"CAST({col} AS CHAR)",
            "oracle": f"TO_CHAR({col})"}.get(dialect, f"CAST({col} AS TEXT)")


def sql_mode(a):
    L = length_fn(a.dialect)
    blocks = []
    for col in a.columns:
        txt = text_cast(col, a.dialect)
        blocks.append(f"""SELECT '{col}' AS column_name,
       COUNT(*) AS row_count,
       SUM(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END) AS null_count,
       ROUND(100.0 * SUM(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS null_pct,
       SUM(CASE WHEN TRIM({txt}) = '' THEN 1 ELSE 0 END) AS blank_count,
       COUNT(DISTINCT {col}) AS distinct_count,
       MIN({txt}) AS min_value,
       MAX({txt}) AS max_value,
       MIN({L}({txt})) AS min_length,
       MAX({L}({txt})) AS max_length
FROM {a.table}""")
    out = ["-- Column profile: one row per column", "\nUNION ALL\n".join(blocks) + ";"]
    if a.key:
        keys = ", ".join(a.key)
        out.append(f"""
-- Duplicate keys ({keys}): should return no rows
SELECT {keys}, COUNT(*) AS copies
FROM {a.table}
GROUP BY {keys}
HAVING COUNT(*) > 1
ORDER BY copies DESC;""")
        out.append(f"""
-- NULL keys: should be 0
SELECT COUNT(*) AS null_keys
FROM {a.table}
WHERE {' OR '.join(f'{k} IS NULL' for k in a.key)};""")
    for fk in a.fk or []:
        col, _, ref = fk.partition("=")
        ref_table, _, ref_col = ref.rpartition(".")
        if not (col and ref_table and ref_col):
            raise SystemExit(f"--fk expects column=table.column, got {fk!r}")
        out.append(f"""
-- Orphans: {a.table}.{col} values with no matching {ref_table}.{ref_col}
SELECT c.{col}, COUNT(*) AS rows_affected
FROM {a.table} c
LEFT JOIN {ref_table} p ON p.{ref_col} = c.{col}
WHERE c.{col} IS NOT NULL AND p.{ref_col} IS NULL
GROUP BY c.{col}
ORDER BY rows_affected DESC;""")
    print("\n".join(out))


NUM = re.compile(r"-?\d+(\.\d+)?([eE]-?\d+)?")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?")
EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
NULLS = {"", "null", "none", "nan", "n/a", "na", "\\n"}


def valid_date(v):
    try:
        dt.date.fromisoformat(v[:10])
        return True
    except ValueError:
        return False


def guess(values):
    vals = [v for v in values if v.strip().lower() not in NULLS]
    if not vals:
        return "empty"
    for name, rx in (("integer", re.compile(r"-?\d+")), ("number", NUM), ("date", DATE), ("email", EMAIL)):
        hits = sum(bool(rx.fullmatch(v.strip())) for v in vals)
        if name == "date" and hits == len(vals):
            invalid = sum(not valid_date(v.strip()) for v in vals)
            return f"date ({invalid} invalid)" if invalid else "date"
        if hits == len(vals):
            return name
        if hits >= 0.95 * len(vals):
            return f"mostly {name} ({len(vals) - hits} outliers)"
    return "text"


def csv_mode(a):
    with open(a.file, newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        if not header:
            raise SystemExit("empty CSV")
        rows = [r + [""] * (len(header) - len(r)) for r in reader]
    n = len(rows)
    report = {"file": a.file, "rows": n, "columns": [], "duplicate_rows": 0, "duplicate_keys": None}

    for i, name in enumerate(header):
        vals = [r[i] for r in rows]
        nulls = sum(v.strip().lower() in NULLS for v in vals)
        present = [v for v in vals if v.strip().lower() not in NULLS]
        kind = guess(vals)
        cast = int if kind == "integer" else float
        nums = [cast(v) for v in present if NUM.fullmatch(v.strip())] if "integer" in kind or "number" in kind else []
        counts = collections.Counter(present)
        report["columns"].append({
            "name": name,
            "type": kind,
            "null_pct": round(100 * nulls / n, 2) if n else 0,
            "distinct": len(counts),
            "unique": len(counts) == len(present) and bool(present),
            "min": min(nums) if nums else (min(present) if present else None),
            "max": max(nums) if nums else (max(present) if present else None),
            "max_length": max((len(v) for v in present), default=0),
            "top_values": counts.most_common(3),
            "untrimmed": sum(v != v.strip() for v in present),
        })

    seen = collections.Counter(tuple(r) for r in rows)
    report["duplicate_rows"] = sum(c - 1 for c in seen.values() if c > 1)
    if a.key:
        missing = [k for k in a.key if k not in header]
        if missing:
            raise SystemExit(f"key column(s) not in CSV: {', '.join(missing)}")
        idx = [header.index(k) for k in a.key]
        keys = collections.Counter(tuple(r[i] for i in idx) for r in rows)
        dupes = {k: c for k, c in keys.items() if c > 1}
        report["duplicate_keys"] = sum(c - 1 for c in dupes.values())
        report["duplicate_key_examples"] = [list(k) for k in list(dupes)[:5]]

    breaches = []
    for rule in a.fail_on or []:
        metric, _, limit = rule.partition("=")
        limit = float(limit)
        if metric == "null_pct":
            breaches += [f"{c['name']}: null_pct {c['null_pct']} > {limit}" for c in report["columns"] if c["null_pct"] > limit]
        elif metric in ("duplicate_rows", "duplicate_keys"):
            if (report[metric] or 0) > limit:
                breaches.append(f"{metric} {report[metric]} > {limit}")
        else:
            raise SystemExit(f"unknown --fail-on metric {metric!r} (null_pct, duplicate_rows, duplicate_keys)")
    report["breaches"] = breaches

    if a.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(f"{a.file}: {n} rows, {len(header)} columns, {report['duplicate_rows']} duplicate rows"
              + (f", {report['duplicate_keys']} duplicate keys on ({', '.join(a.key)})" if a.key else ""))
        print(f"\n{'column':<20} {'type':<26} {'null%':>6} {'distinct':>8}  min .. max")
        for c in report["columns"]:
            rng = f"{c['min']} .. {c['max']}" if c["min"] is not None else "-"
            flag = "  (unique)" if c["unique"] else ""
            print(f"{c['name'][:20]:<20} {c['type'][:26]:<26} {c['null_pct']:>6} {c['distinct']:>8}  {rng[:40]}{flag}")
            if c["untrimmed"]:
                print(f"{'':<20} ! {c['untrimmed']} value(s) with leading/trailing spaces")
        if report.get("duplicate_key_examples"):
            print(f"\nDuplicate key examples: {report['duplicate_key_examples']}")
        for b in breaches:
            print(f"FAIL {b}")
    return 1 if breaches else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)
    s = sub.add_parser("sql", help="generate profiling SQL")
    s.add_argument("--table", required=True, type=ident)
    s.add_argument("--columns", nargs="+", required=True, type=ident)
    s.add_argument("--key", nargs="+", type=ident, help="column(s) that should be unique")
    s.add_argument("--fk", nargs="+", help="foreign keys to check, as column=table.column")
    s.add_argument("--dialect", choices=["postgres", "mysql", "tsql", "sqlite", "oracle"], default="postgres")
    c = sub.add_parser("csv", help="profile a CSV file")
    c.add_argument("file")
    c.add_argument("--key", nargs="+", help="column(s) that should be unique")
    c.add_argument("--fail-on", nargs="+", help="thresholds: null_pct=5 duplicate_rows=0 duplicate_keys=0")
    c.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.mode == "sql":
        sql_mode(a)
        return 0
    return csv_mode(a)


if __name__ == "__main__":
    sys.exit(main())
