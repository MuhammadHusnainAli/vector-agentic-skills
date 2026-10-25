#!/usr/bin/env python3
"""Compute point-in-time velocity and behaviour features per entity (card, account, device) for fraud models.

Every feature for a transaction uses ONLY that entity's earlier transactions (strictly before its timestamp),
so it can be computed identically in real time and never leaks the future or the transaction itself.

Features added (per --entity, windows from --windows, default 1h 24h 7d):
  cnt_<w>, sum_<w>       number and total amount of the entity's previous transactions within the window
  secs_since_prev        seconds since the entity's previous transaction (blank for the first)
  amt_vs_mean            amount / mean amount of the entity's previous transactions (blank without history)
  amt_z                  (amount - mean) / std of previous amounts (needs >= 3 previous)
  n_prev                 number of previous transactions (history depth; low = new entity)
  new_<col>              1 if the value of --categorical columns (e.g. merchant_category, country) has never
                         been seen for this entity before
  distinct_<col>_24h     distinct values of those columns in the previous 24 hours

Usage:
    python fraud_velocity_features.py transactions.csv --entity card_id --time-col timestamp --amount-col amount \\
        --categorical merchant_category country -o features.csv
    python fraud_velocity_features.py tx.csv --entity account_id --windows 10m 1h 1d 30d -o feats.csv

Exit codes: 0 written, 2 usage or read error.
"""

import argparse
import bisect
import csv
import datetime as dt
import math
import sys
from collections import defaultdict


def parse_window(s):
    unit = s[-1]
    mult = {"s": 1, "m": 60, "h": 3600, "d": 86400}.get(unit)
    if mult is None:
        raise ValueError(f"window {s!r}: use a number with s, m, h or d (e.g. 1h, 7d)")
    return float(s[:-1]) * mult


def parse_time(v):
    try:
        x = float(v)
        return x if x < 1e11 else x / 1000
    except ValueError:
        return dt.datetime.fromisoformat(v.replace("Z", "+00:00")).timestamp()


def fmt(x):
    if x is None:
        return ""
    return str(int(x)) if float(x).is_integer() else f"{x:.6g}"


def main():
    ap = argparse.ArgumentParser(description="Point-in-time velocity features for fraud models.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--entity", required=True, help="entity column, e.g. card_id")
    ap.add_argument("--time-col", default="timestamp")
    ap.add_argument("--amount-col", default="amount")
    ap.add_argument("--windows", nargs="+", default=["1h", "24h", "7d"])
    ap.add_argument("--categorical", nargs="*", default=[])
    ap.add_argument("-o", "--output")
    a = ap.parse_args()
    try:
        windows = [(w, parse_window(w)) for w in a.windows]
        with open(a.csv, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            header = list(reader.fieldnames or [])
            rows = list(reader)
        for c in [a.entity, a.time_col, a.amount_col] + a.categorical:
            if c not in header:
                raise ValueError(f"column {c!r} not found (have: {', '.join(header)})")
        for r in rows:
            r["__t"] = parse_time(r[a.time_col])
            r["__a"] = float(r[a.amount_col])
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    order = sorted(range(len(rows)), key=lambda i: rows[i]["__t"])
    hist_t = defaultdict(list)          # per entity: sorted previous timestamps
    hist_a = defaultdict(list)          # amounts aligned with hist_t
    prefix = defaultdict(lambda: [0.0])  # prefix sums of amounts
    stats = defaultdict(lambda: [0, 0.0, 0.0])   # n, sum, sum of squares
    seen_vals = defaultdict(set)
    cat_hist = defaultdict(list)        # per (entity, col): (t, value) of previous transactions
    new_cols = ([f"cnt_{w}" for w, _ in windows] + [f"sum_{w}" for w, _ in windows]
                + ["secs_since_prev", "amt_vs_mean", "amt_z", "n_prev"]
                + [f"new_{c}" for c in a.categorical] + [f"distinct_{c}_24h" for c in a.categorical])
    i = 0
    while i < len(order):
        # transactions with the same entity and timestamp do not see each other
        j = i
        t0 = rows[order[i]]["__t"]
        while j < len(order) and rows[order[j]]["__t"] == t0:
            j += 1
        batch = order[i:j]
        for idx in batch:
            r = rows[idx]
            e, t, amt = r[a.entity], r["__t"], r["__a"]
            ts, ps = hist_t[e], prefix[e]
            for w, secs in windows:
                lo = bisect.bisect_left(ts, t - secs)
                hi = bisect.bisect_left(ts, t)                 # strictly before t
                r[f"cnt_{w}"] = hi - lo
                r[f"sum_{w}"] = ps[hi] - ps[lo]
            n, s, ss = stats[e]
            r["secs_since_prev"] = t - ts[-1] if ts else None   # history holds strictly earlier timestamps only
            mean = s / n if n else None
            r["amt_vs_mean"] = amt / mean if mean else None
            if n >= 3:
                var = max(ss / n - mean * mean, 0.0) * n / (n - 1)
                r["amt_z"] = (amt - mean) / math.sqrt(var) if var > 0 else 0.0
            else:
                r["amt_z"] = None
            r["n_prev"] = n
            for c in a.categorical:
                v = r[c]
                r[f"new_{c}"] = 0 if v in seen_vals[(e, c)] else 1
                h = cat_hist[(e, c)]
                r[f"distinct_{c}_24h"] = len({val for tt, val in h if t - 86400 <= tt < t})
        for idx in batch:                                    # update history after the whole timestamp batch
            r = rows[idx]
            e, t, amt = r[a.entity], r["__t"], r["__a"]
            hist_t[e].append(t)
            hist_a[e].append(amt)
            prefix[e].append(prefix[e][-1] + amt)
            st = stats[e]
            st[0] += 1
            st[1] += amt
            st[2] += amt * amt
            for c in a.categorical:
                seen_vals[(e, c)].add(r[c])
                cat_hist[(e, c)].append((t, r[c]))
                cat_hist[(e, c)] = [x for x in cat_hist[(e, c)] if x[0] >= t - 86400]
        i = j
    f = open(a.output, "w", newline="", encoding="utf-8") if a.output else sys.stdout
    w = csv.writer(f)
    w.writerow(header + new_cols)
    for r in rows:
        w.writerow([r[c] for c in header] + [fmt(r[c]) if not isinstance(r[c], str) else r[c] for c in new_cols])
    if a.output:
        f.close()
        print(f"wrote {a.output}: {len(rows)} rows, {len(new_cols)} point-in-time features per {a.entity}",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
