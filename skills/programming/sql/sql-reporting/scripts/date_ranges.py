#!/usr/bin/env python3
"""Generate correct, index-friendly date filters for reporting periods.

Every period is a half-open range  col >= start AND col < end , which works for
DATE and TIMESTAMP columns, never misses the last day's afternoon, and lets the
database use an index on the column.

Two modes:
    dynamic (default)  SQL expressions relative to the current date, per dialect
    --literal          concrete dates computed for --as-of (default: today)

Periods: today, yesterday, last_7_days, last_30_days, last_n_days (with --n),
wtd, mtd, qtd, ytd, previous_week, previous_month, previous_quarter,
previous_year, mtd_last_year, ytd_last_year. Weeks start on Monday.

Usage:
    python date_ranges.py mtd --column created_at --dialect postgres
    python date_ranges.py previous_month ytd --column o.order_date --dialect tsql
    python date_ranges.py last_n_days --n 90 --column ts --literal --as-of 2026-10-20
    python date_ranges.py --all --column created_at --dialect mysql
"""

import argparse
import datetime as dt
import sys

PERIODS = ["today", "yesterday", "last_7_days", "last_30_days", "last_n_days", "wtd", "mtd", "qtd", "ytd",
           "previous_week", "previous_month", "previous_quarter", "previous_year", "mtd_last_year", "ytd_last_year"]


class Dialect:
    """Date primitives that each return a SQL DATE expression."""

    def __init__(self, name, as_of=None):
        self.name = name
        self.as_of = as_of

    def today(self):
        if self.as_of:
            return {"tsql": f"CAST('{self.as_of}' AS DATE)", "sqlite": f"date('{self.as_of}')",
                    "oracle": f"DATE '{self.as_of}'"}.get(self.name, f"DATE '{self.as_of}'")
        return {"postgres": "CURRENT_DATE", "mysql": "CURDATE()", "tsql": "CAST(GETDATE() AS DATE)",
                "sqlite": "date('now')", "oracle": "TRUNC(SYSDATE)"}[self.name]

    def start(self, unit, e):
        n = self.name
        if n == "postgres":
            return f"CAST(DATE_TRUNC('{unit}', {e}) AS DATE)"
        if n == "oracle":
            fmt = {"week": "IW", "month": "MM", "quarter": "Q", "year": "YYYY"}[unit]
            return f"TRUNC({e}, '{fmt}')"
        if n == "mysql":
            return {"week": f"DATE_SUB({e}, INTERVAL WEEKDAY({e}) DAY)",
                    "month": f"DATE_SUB({e}, INTERVAL DAYOFMONTH({e}) - 1 DAY)",
                    "quarter": f"MAKEDATE(YEAR({e}), 1) + INTERVAL (QUARTER({e}) - 1) QUARTER",
                    "year": f"MAKEDATE(YEAR({e}), 1)"}[unit]
        if n == "tsql":
            return {"week": f"DATEADD(DAY, -((DATEPART(WEEKDAY, {e}) + @@DATEFIRST - 2) % 7), {e})",
                    "month": f"DATEFROMPARTS(YEAR({e}), MONTH({e}), 1)",
                    "quarter": f"DATEFROMPARTS(YEAR({e}), (DATEPART(QUARTER, {e}) - 1) * 3 + 1, 1)",
                    "year": f"DATEFROMPARTS(YEAR({e}), 1, 1)"}[unit]
        return {"week": f"date({e}, 'weekday 0', '-6 days')", "month": f"date({e}, 'start of month')",
                "quarter": f"date({e}, 'start of month', '-' || ((CAST(strftime('%m', {e}) AS INTEGER) - 1) % 3) || ' months')",
                "year": f"date({e}, 'start of year')"}[unit]

    def add(self, e, n, unit):
        if n == 0:
            return e
        d = self.name
        if unit == "week":
            n, unit = n * 7, "day"
        if unit == "quarter" and d in ("sqlite", "oracle"):
            n, unit = n * 3, "month"
        if unit == "year" and d == "oracle":
            n, unit = n * 12, "month"
        if d == "postgres":
            return f"CAST({e} + INTERVAL '{n} {unit}' AS DATE)"
        if d == "mysql":
            return f"DATE_ADD({e}, INTERVAL {n} {unit.upper()})"
        if d == "tsql":
            return f"DATEADD({unit.upper()}, {n}, {e})"
        if d == "oracle":
            return f"({e} + {n})" if unit == "day" else f"ADD_MONTHS({e}, {n})"
        return f"date({e}, '{n:+d} {unit}s')"


def ranges(d, n_days):
    t = d.today()
    tomorrow = d.add(t, 1, "day")
    out = {
        "today": (t, tomorrow),
        "yesterday": (d.add(t, -1, "day"), t),
        "last_7_days": (d.add(t, -6, "day"), tomorrow),
        "last_30_days": (d.add(t, -29, "day"), tomorrow),
        "last_n_days": (d.add(t, -(n_days - 1), "day"), tomorrow),
    }
    for unit, key in (("week", "wtd"), ("month", "mtd"), ("quarter", "qtd"), ("year", "ytd")):
        start = d.start(unit, t)
        out[key] = (start, tomorrow)
        out[f"previous_{unit}"] = (d.add(start, -1, unit), start)
    out["mtd_last_year"] = (d.add(d.start("month", t), -1, "year"), d.add(tomorrow, -1, "year"))
    out["ytd_last_year"] = (d.add(d.start("year", t), -1, "year"), d.add(tomorrow, -1, "year"))
    return out


def add_months(day, n):
    m = day.month - 1 + n
    y, m = day.year + m // 12, m % 12 + 1
    last = [31, 29 if y % 4 == 0 and (y % 100 or y % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
    return day.replace(year=y, month=m, day=min(day.day, last))


def literal_ranges(today, n_days):
    D = dt.timedelta
    tomorrow = today + D(days=1)
    week = today - D(days=today.weekday())
    month = today.replace(day=1)
    quarter = today.replace(month=(today.month - 1) // 3 * 3 + 1, day=1)
    year = today.replace(month=1, day=1)
    return {
        "today": (today, tomorrow),
        "yesterday": (today - D(days=1), today),
        "last_7_days": (today - D(days=6), tomorrow),
        "last_30_days": (today - D(days=29), tomorrow),
        "last_n_days": (today - D(days=n_days - 1), tomorrow),
        "wtd": (week, tomorrow), "previous_week": (week - D(days=7), week),
        "mtd": (month, tomorrow), "previous_month": (add_months(month, -1), month),
        "qtd": (quarter, tomorrow), "previous_quarter": (add_months(quarter, -3), quarter),
        "ytd": (year, tomorrow), "previous_year": (add_months(year, -12), year),
        "mtd_last_year": (add_months(month, -12), add_months(tomorrow, -12)),
        "ytd_last_year": (add_months(year, -12), add_months(tomorrow, -12)),
    }


def literal_sql(d, dialect):
    s = d.isoformat()
    return {"tsql": f"'{s}'", "sqlite": f"'{s}'"}.get(dialect, f"DATE '{s}'")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("periods", nargs="*", metavar="period", help=", ".join(PERIODS))
    ap.add_argument("--all", action="store_true", help="print every period")
    ap.add_argument("--column", default="created_at", help="date/timestamp column (default created_at)")
    ap.add_argument("--dialect", choices=["postgres", "mysql", "tsql", "sqlite", "oracle"], default="postgres")
    ap.add_argument("--n", type=int, default=90, help="days for last_n_days (default 90)")
    ap.add_argument("--literal", action="store_true", help="emit concrete dates instead of expressions")
    ap.add_argument("--as-of", help="reference date YYYY-MM-DD (default today); also pins dynamic mode")
    args = ap.parse_args()

    unknown = [p for p in args.periods if p not in PERIODS]
    if unknown:
        ap.error(f"unknown period(s) {', '.join(unknown)}; choose from {', '.join(PERIODS)}")
    periods = PERIODS if args.all or not args.periods else args.periods
    as_of = dt.date.fromisoformat(args.as_of) if args.as_of else None
    if args.literal:
        today = as_of or dt.date.today()
        table = {k: (literal_sql(a, args.dialect), literal_sql(b, args.dialect), f"{a} .. {b - dt.timedelta(days=1)}")
                 for k, (a, b) in literal_ranges(today, args.n).items()}
    else:
        table = {k: (a, b, None) for k, (a, b) in ranges(Dialect(args.dialect, args.as_of), args.n).items()}

    for p in periods:
        start, end, span = table[p]
        label = p.replace("last_n_days", f"last_{args.n}_days")
        print(f"-- {label}{f' ({span})' if span else ''}")
        print(f"{args.column} >= {start}\n  AND {args.column} < {end}\n")


if __name__ == "__main__":
    sys.exit(main())
