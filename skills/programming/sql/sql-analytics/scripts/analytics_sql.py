#!/usr/bin/env python3
"""Generate tested SQL for common analytics questions, in your dialect.

Patterns:
    cohort       monthly cohort retention (users active N months after first activity)
    funnel       ordered conversion funnel across event steps
    growth       period totals with previous-period change and % change
    percentiles  p50/p90/p99 (any list), optionally per group

Dialects: postgres, mysql, tsql (SQL Server), sqlite. Output is a single
query you can paste and adapt. No dependencies.

Usage:
    python analytics_sql.py cohort --table events --user user_id --ts created_at --dialect postgres
    python analytics_sql.py funnel --table events --user user_id --ts created_at \\
        --event-col event_name --steps signup activate purchase --dialect mysql
    python analytics_sql.py growth --table orders --ts created_at --value total --metric sum --period month
    python analytics_sql.py percentiles --table orders --value total --group region --p 50 90 99 --dialect tsql

Add --where "status = 'paid'" to any pattern to filter the source rows.
"""

import argparse
import re
import sys

DIALECTS = ("postgres", "mysql", "tsql", "sqlite")


def ident(name):
    if not re.fullmatch(r"[A-Za-z_][\w.]*", name):
        raise argparse.ArgumentTypeError(f"invalid identifier: {name!r}")
    return name


def lit(s):
    return "'" + s.replace("'", "''") + "'"


def period_start(d, ts, period):
    table = {
        "postgres": {"day": f"CAST({ts} AS DATE)", "week": f"CAST(DATE_TRUNC('week', {ts}) AS DATE)",
                     "month": f"CAST(DATE_TRUNC('month', {ts}) AS DATE)", "quarter": f"CAST(DATE_TRUNC('quarter', {ts}) AS DATE)",
                     "year": f"CAST(DATE_TRUNC('year', {ts}) AS DATE)"},
        "mysql": {"day": f"DATE({ts})", "week": f"DATE_SUB(DATE({ts}), INTERVAL WEEKDAY({ts}) DAY)",
                  "month": f"CAST(DATE_FORMAT({ts}, '%Y-%m-01') AS DATE)",
                  "quarter": f"MAKEDATE(YEAR({ts}), 1) + INTERVAL (QUARTER({ts}) - 1) QUARTER",
                  "year": f"MAKEDATE(YEAR({ts}), 1)"},
        "tsql": {"day": f"CAST({ts} AS DATE)",
                 "week": f"DATEADD(DAY, -((DATEPART(WEEKDAY, {ts}) + @@DATEFIRST - 2) % 7), CAST({ts} AS DATE))",
                 "month": f"DATEFROMPARTS(YEAR({ts}), MONTH({ts}), 1)",
                 "quarter": f"DATEFROMPARTS(YEAR({ts}), (DATEPART(QUARTER, {ts}) - 1) * 3 + 1, 1)",
                 "year": f"DATEFROMPARTS(YEAR({ts}), 1, 1)"},
        "sqlite": {"day": f"date({ts})", "week": f"date({ts}, 'weekday 0', '-6 days')",
                   "month": f"date({ts}, 'start of month')",
                   "quarter": f"date({ts}, 'start of month', '-' || ((CAST(strftime('%m', {ts}) AS INTEGER) - 1) % 3) || ' months')",
                   "year": f"date({ts}, 'start of year')"},
    }
    return table[d][period]


def months_between(d, later, earlier):
    if d == "mysql":
        return f"TIMESTAMPDIFF(MONTH, {earlier}, {later})"
    if d == "tsql":
        return f"DATEDIFF(MONTH, {earlier}, {later})"
    if d == "postgres":
        return (f"CAST((EXTRACT(YEAR FROM {later}) - EXTRACT(YEAR FROM {earlier})) * 12"
                f" + EXTRACT(MONTH FROM {later}) - EXTRACT(MONTH FROM {earlier}) AS INTEGER)")
    return (f"((CAST(strftime('%Y', {later}) AS INTEGER) - CAST(strftime('%Y', {earlier}) AS INTEGER)) * 12"
            f" + CAST(strftime('%m', {later}) AS INTEGER) - CAST(strftime('%m', {earlier}) AS INTEGER))")


def where(clause, extra=None):
    conds = [c for c in (clause, extra) if c]
    return f"\n    WHERE {' AND '.join(f'({c})' for c in conds)}" if conds else ""


def cohort(a):
    month = period_start(a.dialect, a.ts, "month")
    diff = months_between(a.dialect, "a.activity_month", "c.cohort_month")
    return f"""-- Monthly cohort retention: users grouped by first active month,
-- counted again in each later month they were active.
WITH activity AS (
    SELECT DISTINCT {a.user} AS user_id, {month} AS activity_month
    FROM {a.table}{where(a.where, f"{a.ts} IS NOT NULL")}
),
cohorts AS (
    SELECT user_id, MIN(activity_month) AS cohort_month
    FROM activity
    GROUP BY user_id
),
retention AS (
    SELECT c.cohort_month,
           {diff} AS month_number,
           COUNT(DISTINCT a.user_id) AS users
    FROM activity a
    JOIN cohorts c ON c.user_id = a.user_id
    GROUP BY c.cohort_month, {diff}
)
SELECT r.cohort_month,
       r.month_number,
       r.users,
       s.users AS cohort_size,
       ROUND(100.0 * r.users / s.users, 2) AS retention_pct
FROM retention r
JOIN retention s ON s.cohort_month = r.cohort_month AND s.month_number = 0
ORDER BY r.cohort_month, r.month_number;"""


def funnel(a):
    if not a.steps or len(a.steps) < 2:
        raise SystemExit("funnel needs --steps with at least two event names")
    ctes = [f"""step1 AS (
    SELECT {a.user} AS user_id, MIN({a.ts}) AS reached_at
    FROM {a.table}{where(a.where, f"{a.event_col} = {lit(a.steps[0])}")}
    GROUP BY {a.user}
)"""]
    for i, step in enumerate(a.steps[1:], 2):
        source = f"(SELECT * FROM {a.table} WHERE {a.where}) e" if a.where else f"{a.table} e"
        ctes.append(f"""step{i} AS (
    SELECT e.{a.user} AS user_id, MIN(e.{a.ts}) AS reached_at
    FROM {source}
    JOIN step{i - 1} p ON p.user_id = e.{a.user} AND e.{a.ts} >= p.reached_at
    WHERE e.{a.event_col} = {lit(step)}
    GROUP BY e.{a.user}
)""")
    union = "\n    UNION ALL\n".join(
        f"    SELECT {i} AS step, {lit(s)} AS step_name, COUNT(*) AS users FROM step{i}" for i, s in enumerate(a.steps, 1))
    return f"""-- Ordered funnel: each step counts users who did it after the previous step.
WITH {(',' + chr(10)).join(ctes)},
funnel AS (
{union}
)
SELECT step,
       step_name,
       users,
       ROUND(100.0 * users / NULLIF(FIRST_VALUE(users) OVER (ORDER BY step), 0), 2) AS pct_of_first,
       ROUND(100.0 * users / NULLIF(LAG(users) OVER (ORDER BY step), 0), 2) AS pct_of_previous
FROM funnel
ORDER BY step;"""


def growth(a):
    p = period_start(a.dialect, a.ts, a.period)
    agg = {"sum": f"SUM({a.value})", "count": "COUNT(*)", "count_distinct": f"COUNT(DISTINCT {a.value})",
           "avg": f"AVG({a.value})"}[a.metric]
    if a.metric != "count" and not a.value:
        raise SystemExit(f"--metric {a.metric} needs --value")
    return f"""-- {a.period.title()}-over-{a.period} change in {agg}.
WITH periods AS (
    SELECT {p} AS period, {agg} AS total
    FROM {a.table}{where(a.where)}
    GROUP BY {p}
)
SELECT period,
       total,
       LAG(total) OVER (ORDER BY period) AS previous,
       total - LAG(total) OVER (ORDER BY period) AS change,
       ROUND(100.0 * (total - LAG(total) OVER (ORDER BY period))
             / NULLIF(LAG(total) OVER (ORDER BY period), 0), 2) AS change_pct
FROM periods
ORDER BY period;"""


def percentiles(a):
    ps = a.p or [50, 90, 99]
    name = lambda p: "p" + str(p).replace(".", "_")
    g = a.group
    if a.dialect == "postgres":
        cols = ",\n       ".join(f"PERCENTILE_CONT({p / 100}) WITHIN GROUP (ORDER BY {a.value}) AS {name(p)}" for p in ps)
        return (f"SELECT {g + ', ' if g else ''}COUNT({a.value}) AS n,\n       {cols}\nFROM {a.table}{where(a.where)}"
                + (f"\nGROUP BY {g}\nORDER BY {g};" if g else ";"))
    if a.dialect == "tsql":
        part = f"PARTITION BY {g}" if g else ""
        cols = ",\n       ".join(f"PERCENTILE_CONT({p / 100}) WITHIN GROUP (ORDER BY {a.value}) OVER ({part}) AS {name(p)}"
                                   for p in ps)
        return (f"SELECT DISTINCT {g + ', ' if g else ''}COUNT({a.value}) OVER ({part}) AS n,\n       {cols}\n"
                f"FROM {a.table}{where(a.where, f'{a.value} IS NOT NULL')}" + (f"\nORDER BY {g};" if g else ";"))
    part = f"PARTITION BY {g} " if g else ""
    cols = ",\n       ".join(f"MIN(CASE WHEN rn >= {p / 100} * n THEN v END) AS {name(p)}" for p in ps)
    return f"""-- Nearest-rank percentiles ({a.dialect} has no PERCENTILE_CONT).
WITH ranked AS (
    SELECT {g + ' AS grp, ' if g else ''}{a.value} AS v,
           ROW_NUMBER() OVER ({part}ORDER BY {a.value}) AS rn,
           COUNT(*) OVER ({part.strip()}) AS n
    FROM {a.table}{where(a.where, f'{a.value} IS NOT NULL')}
)
SELECT {'grp AS ' + g + ', ' if g else ''}MAX(n) AS n,
       {cols}
FROM ranked{chr(10) + 'GROUP BY grp' + chr(10) + 'ORDER BY grp' if g else ''};"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pattern", choices=["cohort", "funnel", "growth", "percentiles"])
    ap.add_argument("--table", required=True, type=ident)
    ap.add_argument("--dialect", choices=DIALECTS, default="postgres")
    ap.add_argument("--user", type=ident, help="user id column (cohort, funnel)")
    ap.add_argument("--ts", type=ident, help="timestamp column (cohort, funnel, growth)")
    ap.add_argument("--event-col", type=ident, help="event name column (funnel)")
    ap.add_argument("--steps", nargs="+", help="ordered event names (funnel)")
    ap.add_argument("--value", type=ident, help="numeric column (growth, percentiles)")
    ap.add_argument("--metric", choices=["sum", "count", "count_distinct", "avg"], default="sum", help="growth metric")
    ap.add_argument("--period", choices=["day", "week", "month", "quarter", "year"], default="month")
    ap.add_argument("--group", type=ident, help="group column (percentiles)")
    ap.add_argument("--p", nargs="+", type=float, help="percentiles, e.g. 50 90 99 (default)")
    ap.add_argument("--where", help="extra filter applied to source rows, e.g. \"status = 'paid'\"")
    a = ap.parse_args()

    needs = {"cohort": ["user", "ts"], "funnel": ["user", "ts", "event_col", "steps"], "growth": ["ts"],
             "percentiles": ["value"]}[a.pattern]
    missing = [f"--{n.replace('_', '-')}" for n in needs if not getattr(a, n)]
    if missing:
        ap.error(f"{a.pattern} needs {', '.join(missing)}")
    if a.p:
        a.p = [int(p) if p.is_integer() else p for p in a.p]
    print({"cohort": cohort, "funnel": funnel, "growth": growth, "percentiles": percentiles}[a.pattern](a))


if __name__ == "__main__":
    sys.exit(main())
