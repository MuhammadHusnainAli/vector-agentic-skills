#!/usr/bin/env python3
"""Split an interaction log into train and test the way a recommender is used: by time.

Modes:
  leave-last   the last --n interactions of every user (by timestamp) go to test; users need at least
               --min-train interactions left in train, otherwise all their rows stay in train
  global       every interaction at or after a cut-off (--cutoff timestamp, or the --test-frac quantile of
               time) goes to test; this matches deployment (train on the past, recommend the future) and is
               the stricter protocol
With --min-rating, test rows below the threshold are dropped (only positive interactions are relevance
targets); train keeps everything.

Writes <prefix>_train.csv and <prefix>_test.csv and reports sizes, users in test that are cold in train
(should be evaluated separately) and test items never seen in train (unrecommendable by pure CF).

Usage:
    python temporal_split.py ratings.csv --mode leave-last --n 2 --prefix ratings
    python temporal_split.py events.csv --mode global --test-frac 0.2 --time-col ts --prefix events
    python temporal_split.py ratings.csv --mode leave-last --n 1 --min-rating 4 --prefix pos

Exit codes: 0 written, 2 usage or read error.
"""

import argparse
import csv
import datetime as dt
import math
import sys
from collections import defaultdict


def to_time(v):
    try:
        x = float(v)
        if math.isfinite(x):
            return x
    except (TypeError, ValueError):
        pass
    try:
        return dt.datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()
    except ValueError:
        raise ValueError(f"cannot parse timestamp {v!r}")


def main():
    ap = argparse.ArgumentParser(description="Temporal train/test split for recommenders.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--mode", choices=["leave-last", "global"], default="leave-last")
    ap.add_argument("--n", type=int, default=1, help="test interactions per user (leave-last)")
    ap.add_argument("--min-train", type=int, default=2)
    ap.add_argument("--cutoff", help="timestamp for --mode global")
    ap.add_argument("--test-frac", type=float, default=0.2)
    ap.add_argument("--user-col", default="user_id")
    ap.add_argument("--item-col", default="item_id")
    ap.add_argument("--time-col", default="timestamp")
    ap.add_argument("--rating-col", default="rating")
    ap.add_argument("--min-rating", type=float)
    ap.add_argument("--prefix", default="split")
    a = ap.parse_args()
    try:
        with open(a.csv, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames or []
            rows = list(reader)
        for c in (a.user_col, a.item_col, a.time_col):
            if c not in header:
                raise ValueError(f"column {c!r} not found (have: {', '.join(header)})")
        if a.min_rating is not None and a.rating_col not in header:
            raise ValueError(f"--min-rating needs the rating column {a.rating_col!r}")
        for r in rows:
            r["__t"] = to_time(r[a.time_col])
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    train, test = [], []
    if a.mode == "leave-last":
        by_user = defaultdict(list)
        for r in rows:
            by_user[r[a.user_col]].append(r)
        for u, rs in by_user.items():
            rs.sort(key=lambda r: r["__t"])
            if len(rs) - a.n >= a.min_train:
                train += rs[:-a.n]
                test += rs[-a.n:]
            else:
                train += rs
    else:
        ts = sorted(r["__t"] for r in rows)
        cut = to_time(a.cutoff) if a.cutoff else ts[int(len(ts) * (1 - a.test_frac))]
        for r in rows:
            (test if r["__t"] >= cut else train).append(r)
    if a.min_rating is not None:
        test = [r for r in test if float(r[a.rating_col] or 0) >= a.min_rating]
    train_users = defaultdict(int)
    for r in train:
        train_users[r[a.user_col]] += 1
    train_items = {r[a.item_col] for r in train}
    test_users = {r[a.user_col] for r in test}
    cold_test_users = [u for u in test_users if train_users.get(u, 0) < 5]
    unseen_items = {r[a.item_col] for r in test} - train_items
    for name, part in (("train", train), ("test", test)):
        with open(f"{a.prefix}_{name}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=header)
            w.writeheader()
            for r in part:
                w.writerow({k: r[k] for k in header})
    print(f"{a.mode}: train {len(train)} rows, test {len(test)} rows ({len(test_users)} users) -> "
          f"{a.prefix}_train.csv, {a.prefix}_test.csv")
    print(f"test users with < 5 train interactions: {len(cold_test_users)}   test items unseen in train: "
          f"{len(unseen_items)}" + (" (pure CF cannot recommend these)" if unseen_items else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
