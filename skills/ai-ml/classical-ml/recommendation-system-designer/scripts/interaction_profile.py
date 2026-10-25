#!/usr/bin/env python3
"""Profile a user-item interaction log to choose a recommendation approach and evaluation protocol.

Input: CSV with user, item and optionally rating/value and timestamp columns (auto-detected or set with
--user-col/--item-col/--rating-col/--time-col).

Reports:
  size         users, items, interactions, density (interactions / users x items)
  activity     interactions per user and per item: median, 90th percentile, max; cold users/items with
               fewer than --cold interactions
  popularity   Gini coefficient of item counts and the share of interactions on the top 1% / 10% / 20% of
               items (long tail): high concentration means popularity is a strong baseline and recommenders
               need popularity-bias checks
  feedback     explicit (a rating scale) or implicit (counts/clicks/plays or no value column); rating
               distribution; repeat interactions (same user-item more than once)
  time         time span, and whether a temporal split is possible
  advice       baseline(s), candidate model families, the split protocol and the metrics

Usage:
    python interaction_profile.py ratings.csv
    python interaction_profile.py events.csv --user-col visitor --item-col product --time-col ts --cold 5 --json

Exit codes: 0 profiled, 2 usage or read error.
"""

import argparse
import csv
import datetime as dt
import json
import math
import sys
from collections import Counter


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def pct(xs, q):
    s = sorted(xs)
    return s[min(len(s) - 1, int(q * (len(s) - 1) + 0.5))]


def gini(counts):
    xs = sorted(counts)
    n = len(xs)
    tot = sum(xs)
    if n == 0 or tot == 0:
        return 0.0
    cum = sum((i + 1) * x for i, x in enumerate(xs))
    return (2 * cum) / (n * tot) - (n + 1) / n


def detect(cols, given, names):
    if given:
        return given
    return next((c for c in cols if c.lower() in names), None)


def to_time(v):
    x = num(v)
    if x is not None:
        return x if x < 1e11 else x / 1000                  # seconds or milliseconds
    try:
        return dt.datetime.fromisoformat(v.replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError):
        return None


def profile(rows, ucol, icol, rcol, tcol, cold):
    users = Counter(r[ucol] for r in rows)
    items = Counter(r[icol] for r in rows)
    pairs = Counter((r[ucol], r[icol]) for r in rows)
    n = len(rows)
    res = {"users": len(users), "items": len(items), "interactions": n,
           "density": n / (len(users) * len(items)) if users and items else 0.0}
    uc, ic = list(users.values()), list(items.values())
    res["per_user"] = {"median": pct(uc, 0.5), "p90": pct(uc, 0.9), "max": max(uc)}
    res["per_item"] = {"median": pct(ic, 0.5), "p90": pct(ic, 0.9), "max": max(ic)}
    res["cold_users"] = sum(1 for v in uc if v < cold)
    res["cold_items"] = sum(1 for v in ic if v < cold)
    res["gini_items"] = gini(ic)
    srt = sorted(ic, reverse=True)
    res["top_share"] = {f"top_{int(q * 100)}pct": sum(srt[:max(1, int(len(srt) * q))]) / n for q in (0.01, 0.1, 0.2)}
    res["repeat_pairs"] = sum(1 for v in pairs.values() if v > 1)
    if rcol:
        vals = [num(r[rcol]) for r in rows]
        vals = [v for v in vals if v is not None]
        distinct = sorted(set(vals))
        explicit = 1 < len(distinct) <= 11 and all(float(v).is_integer() or v * 2 == int(v * 2) for v in distinct)
        res["feedback"] = "explicit" if explicit else "implicit (weighted)"
        res["rating_dist"] = {str(int(v) if float(v).is_integer() else v): c for v, c in sorted(Counter(vals).items())} if explicit else None
        res["rating_mean"] = sum(vals) / len(vals) if vals else None
    else:
        res["feedback"] = "implicit"
    if tcol:
        ts = [to_time(r[tcol]) for r in rows]
        ts = [t for t in ts if t is not None]
        if ts:
            res["time_span_days"] = (max(ts) - min(ts)) / 86400
    res["advice"] = advise(res, cold, bool(tcol))
    return res


def advise(r, cold, has_time):
    out = []
    out.append("baselines first: global popularity (and recent popularity if time matters); every model must beat "
               "them on the same split")
    if r["gini_items"] >= 0.6 or r["top_share"]["top_10pct"] >= 0.5:
        out.append(f"strong popularity concentration (Gini {r['gini_items']:.2f}, top 10% of items = "
                   f"{r['top_share']['top_10pct']:.0%} of interactions): report coverage and novelty next to "
                   "accuracy, or the 'best' model will just recommend bestsellers")
    if r["interactions"] < 100_000:
        out.append("small log: item-item kNN and ALS/EASE are strong and cheap; deep models rarely pay off here")
    else:
        out.append("large log: ALS / BPR / EASE for candidates, then a learning-to-rank re-ranker with features; "
                   "two-tower models when features and scale justify them")
    if r["feedback"].startswith("implicit") or r["feedback"] == "implicit":
        out.append("implicit feedback: optimise ranking (ALS with confidence weights, BPR), evaluate with "
                   "recall@k / NDCG@k; no RMSE")
    else:
        out.append("explicit ratings: rating prediction (RMSE) rarely matches the product goal; evaluate the "
                   "ranking (NDCG@k with ratings >= 4 as relevant) and treat low ratings as negative signal")
    if r["cold_users"] / max(1, r["users"]) > 0.1 or r["cold_items"] / max(1, r["items"]) > 0.2:
        out.append(f"cold start: {r['cold_users']} users and {r['cold_items']} items with < {cold} interactions; "
                   "add a content/metadata model or a popularity fallback for them and evaluate them separately")
    if r["repeat_pairs"]:
        out.append(f"{r['repeat_pairs']} repeated user-item pairs: decide whether re-recommending seen items is "
                   "allowed (groceries, music) or not (movies); aggregate repeats into confidence weights")
    if has_time:
        out.append("split by time (global cut-off or leave-last-n per user) - random splits leak the future: "
                   "temporal_split.py")
    else:
        out.append("no timestamp: random per-user holdout is the only option and will overstate performance")
    return out


def report(r):
    lines = [f"users {r['users']}   items {r['items']}   interactions {r['interactions']}   density {r['density']:.3%}",
             f"per user: median {r['per_user']['median']}, p90 {r['per_user']['p90']}, max {r['per_user']['max']}   "
             f"per item: median {r['per_item']['median']}, p90 {r['per_item']['p90']}, max {r['per_item']['max']}",
             f"cold users: {r['cold_users']}   cold items: {r['cold_items']}",
             f"item popularity Gini {r['gini_items']:.2f}; share of interactions on top 1% / 10% / 20% of items: "
             + " / ".join(f"{v:.0%}" for v in r["top_share"].values()),
             f"feedback: {r['feedback']}" + (f"   ratings: {r['rating_dist']}  mean {r['rating_mean']:.2f}"
                                             if r.get("rating_dist") else "")
             + f"   repeated pairs: {r['repeat_pairs']}"]
    if "time_span_days" in r:
        lines.append(f"time span: {r['time_span_days']:.1f} days")
    lines.append("")
    lines += [f"- {a}" for a in r["advice"]]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Profile an interaction log for recommendations.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--user-col")
    ap.add_argument("--item-col")
    ap.add_argument("--rating-col")
    ap.add_argument("--time-col")
    ap.add_argument("--cold", type=int, default=5, help="interactions below which a user/item is cold")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        with open(a.csv, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            raise ValueError("no rows")
        cols = list(rows[0])
        ucol = detect(cols, a.user_col, ("user_id", "user", "userid", "customer_id", "visitor_id"))
        icol = detect(cols, a.item_col, ("item_id", "item", "itemid", "product_id", "movie_id", "sku"))
        rcol = detect(cols, a.rating_col, ("rating", "score", "value", "count", "plays", "quantity"))
        tcol = detect(cols, a.time_col, ("timestamp", "ts", "time", "date", "event_time"))
        for c, nm in ((ucol, "user"), (icol, "item")):
            if c is None or c not in cols:
                raise ValueError(f"cannot find the {nm} column; pass --{nm}-col")
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    r = profile(rows, ucol, icol, rcol, tcol, a.cold)
    print(json.dumps(r, indent=2) if a.json else report(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
