#!/usr/bin/env python3
"""Generate leakage-safe SQL for point-in-time window features (PostgreSQL, BigQuery, Snowflake, DuckDB).

Produces one query that joins a spine (entity, cutoff) to an event table and computes, per window,
COUNT / SUM / AVG / MAX of a value and COUNT(DISTINCT ...) of chosen columns over events with
anchor - window <= event_time < anchor, where anchor = cutoff - latency (the newest data that has
arrived), plus days from the last event to the anchor (same convention as pit_features.py). The strict "<" on the cutoff is the point: an event at the cutoff instant belongs to
the outcome side, never to the features.

With --event-level the spine is the event table itself and the current event is excluded by its id.

Usage:
    python gen_window_sql.py --dialect postgres --events payments.transactions --entity card_id \
        --time txn_ts --value amount --windows 1h 24h 7d --distinct merchant_id --event-level --id txn_id
    python gen_window_sql.py --dialect bigquery --events `proj.ds.events` --entity customer_id --time event_ts \
        --spine `proj.ds.snapshots` --cutoff score_ts --value revenue --windows 7d 30d 90d --latency 6h

Exit codes: 0 printed, 2 usage error.
"""

import argparse
import re
import sys

UNITS = {"m": ("minute", 60), "h": ("hour", 3600), "d": ("day", 86400), "w": ("week", 604800)}


def window(w):
    m = re.fullmatch(r"(\d+)([mhdw])", w)
    if not m:
        raise ValueError(f"bad window {w!r}: use 30m, 1h, 7d, 4w")
    return int(m.group(1)), UNITS[m.group(2)][0]


def minus(dialect, col, n, unit):
    if n == 0:
        return col
    if dialect == "bigquery":
        u = {"week": "DAY", "minute": "MINUTE", "hour": "HOUR", "day": "DAY"}[unit]
        k = n * 7 if unit == "week" else n
        return f"TIMESTAMP_SUB({col}, INTERVAL {k} {u})"
    if dialect == "snowflake":
        return f"DATEADD({unit}, -{n}, {col})"
    return f"{col} - INTERVAL '{n} {unit}'"            # postgres, duckdb


def days_between(dialect, a, b):
    if dialect == "bigquery":
        return f"TIMESTAMP_DIFF({b}, {a}, SECOND) / 86400.0"
    if dialect == "snowflake":
        return f"DATEDIFF(second, {a}, {b}) / 86400.0"
    return f"EXTRACT(EPOCH FROM ({b} - {a})) / 86400.0"


def main():
    ap = argparse.ArgumentParser(description="Generate point-in-time window-feature SQL.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dialect", choices=["postgres", "duckdb", "bigquery", "snowflake"], default="postgres")
    ap.add_argument("--events", required=True)
    ap.add_argument("--entity", required=True)
    ap.add_argument("--time", required=True)
    ap.add_argument("--value")
    ap.add_argument("--distinct", nargs="*", default=[])
    ap.add_argument("--windows", nargs="+", default=["7d", "30d"])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--spine", help="snapshot table with entity + cutoff columns")
    g.add_argument("--event-level", action="store_true")
    ap.add_argument("--cutoff", default="cutoff_ts", help="cutoff column in the spine")
    ap.add_argument("--id", help="event id column (required with --event-level)")
    ap.add_argument("--latency", default="0m", help="ignore events newer than cutoff - latency (e.g. 6h)")
    a = ap.parse_args()
    try:
        wins = sorted(((w, *window(w)) for w in a.windows), key=lambda x: x[1] * UNITS[x[0][-1]][1])
        lat_n, lat_u = window(a.latency) if a.latency not in ("0", "0s", "0m") else (0, "minute")
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if a.event_level and not a.id:
        print("error: --event-level needs --id to exclude the current event", file=sys.stderr)
        return 2
    d = a.dialect
    if a.event_level:
        spine, ent, cut = f"{a.events}", f"s.{a.entity}", f"s.{a.time}"
        spine_cols = f"s.{a.id}, s.{a.entity}, s.{a.time}"
    else:
        spine, ent, cut = a.spine, f"s.{a.entity}", f"s.{a.cutoff}"
        spine_cols = f"s.{a.entity}, s.{a.cutoff}"
    upper = minus(d, cut, lat_n, lat_u)
    longest = wins[-1]
    sel = [spine_cols]
    for name, n, unit in wins:
        lower = minus(d, upper, n, unit)
        cond = f"e.{a.time} >= {lower}"
        sel.append(f"COUNT(CASE WHEN {cond} THEN 1 END) AS n_{name}")
        if a.value:
            sel.append(f"COALESCE(SUM(CASE WHEN {cond} THEN e.{a.value} END), 0) AS sum_{name}")
            sel.append(f"AVG(CASE WHEN {cond} THEN e.{a.value} END) AS mean_{name}")
            sel.append(f"MAX(CASE WHEN {cond} THEN e.{a.value} END) AS max_{name}")
        for c in a.distinct:
            sel.append(f"COUNT(DISTINCT CASE WHEN {cond} THEN e.{c} END) AS nuniq_{c}_{name}")
    sel.append(f"{days_between(d, f'MAX(e.{a.time})', upper)} AS days_since_last")
    join = [f"e.{a.entity} = {ent}", f"e.{a.time} < {upper}",
            f"e.{a.time} >= {minus(d, upper, longest[1], longest[2])}"]
    if a.event_level:
        join.append(f"e.{a.id} <> s.{a.id}")
    group = ", ".join(spine_cols.split(", "))
    sql = (f"-- Point-in-time window features ({d}); events strictly before the cutoff"
           f"{' minus ' + a.latency + ' latency' if lat_n else ''}.\n"
           f"-- days_since_last is relative to events inside the longest window ({longest[0]}); for all-time recency\n"
           f"-- or n_prior use a separate LEFT JOIN without the lower bound (it scans more data).\n"
           f"SELECT\n    " + ",\n    ".join(sel) +
           f"\nFROM {spine} s\nLEFT JOIN {a.events} e\n  ON " + "\n AND ".join(join) +
           f"\nGROUP BY {group};\n")
    print(sql, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
