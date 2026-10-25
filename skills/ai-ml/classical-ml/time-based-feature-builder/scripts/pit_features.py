#!/usr/bin/env python3
"""Compute leakage-safe, point-in-time window features from an event log.

Two modes:
  --spine FILE    one output row per (entity, cutoff) in FILE (snapshot / scoring table); features use
                  events with time < anchor, anchor = cutoff - latency (strictly before); windows and
                  secs_since_last are measured back from the anchor
  --event-level   one output row per event; features use the entity's events strictly before that event
                  (the current event never counts itself)

Per window (--windows, e.g. 1h 24h 7d 30d) and per entity:
  n_<w>              number of events in [cutoff - w, cutoff)
  sum_<w>, mean_<w>, max_<w>   of --value (if given)
  nuniq_<col>_<w>    distinct values of each --distinct column
Plus: secs_since_last (time since the previous event), n_prior (all-time count before cutoff), and
ratio_<value>_<w1>_<w2> = mean over the shortest window / mean over the longest (trend / burstiness).

Times: ISO dates or datetimes (2024-03-01, 2024-03-01T12:30:00, with 'Z' or offsets) or unix seconds.
Rows with unparsable times are skipped and counted.

Usage:
    python pit_features.py --events txns.csv --entity card_id --time timestamp --value amount \
        --event-level --windows 1h 24h 7d --distinct merchant_category country -o feats.csv
    python pit_features.py --events events.csv --entity customer_id --time ts --value amount \
        --spine snapshots.csv --cutoff-col score_date --windows 7d 30d 90d --latency 6h

Exit codes: 0 written, 2 usage or read error.
"""

import argparse
import bisect
import csv
import datetime as dt
import re
import sys
from collections import defaultdict

UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}


def parse_window(w):
    m = re.fullmatch(r"(\d+)([smhdw])", w.strip())
    if not m:
        raise ValueError(f"bad window {w!r}; use forms like 30m, 1h, 7d, 4w")
    return int(m.group(1)) * UNITS[m.group(2)]


def parse_time(v):
    v = (v or "").strip()
    if not v:
        return None
    try:
        x = float(v)
        return x / 1000 if x > 1e11 else x
    except ValueError:
        pass
    try:
        t = dt.datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return t.timestamp()


def to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def load_events(path, entity, tcol, vcol, distinct):
    by_entity = defaultdict(list)
    skipped = 0
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        need = [entity, tcol] + ([vcol] if vcol else []) + distinct
        missing = [c for c in need if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"events file lacks column(s) {missing}")
        rows = []
        for i, r in enumerate(reader):
            t = parse_time(r[tcol])
            if t is None:
                skipped += 1
                continue
            rows.append(r)
            by_entity[r[entity]].append((t, i, to_float(r[vcol]) if vcol else None,
                                         tuple(r[c] for c in distinct)))
    for ev in by_entity.values():
        ev.sort()
    return rows, by_entity, skipped


def features(ev, times, cutoff, windows, has_value, distinct, exclude_idx=None):
    """Features for one entity at one cutoff; events with time < cutoff only (and not exclude_idx)."""
    hi = bisect.bisect_left(times, cutoff)          # events strictly before cutoff
    out = {"n_prior": hi, "secs_since_last": (cutoff - times[hi - 1]) if hi else None}
    for name, w in windows:
        lo = bisect.bisect_left(times, cutoff - w)
        win = [e for e in ev[lo:hi] if e[1] != exclude_idx]
        out[f"n_{name}"] = len(win)
        if has_value:
            vals = [e[2] for e in win if e[2] is not None]
            out[f"sum_{name}"] = round(sum(vals), 6) if vals else 0.0
            out[f"mean_{name}"] = round(sum(vals) / len(vals), 6) if vals else None
            out[f"max_{name}"] = max(vals) if vals else None
        for j, col in enumerate(distinct):
            out[f"nuniq_{col}_{name}"] = len({e[3][j] for e in win})
    return out


def main():
    ap = argparse.ArgumentParser(description="Point-in-time window features from an event log.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--events", required=True)
    ap.add_argument("--entity", required=True)
    ap.add_argument("--time", required=True, help="event time column")
    ap.add_argument("--value", help="numeric column to aggregate (sum/mean/max)")
    ap.add_argument("--distinct", nargs="*", default=[], help="columns to count distinct values of")
    ap.add_argument("--windows", nargs="+", default=["1d", "7d", "30d"])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--spine", help="CSV with entity + cutoff columns (one output row each)")
    mode.add_argument("--event-level", action="store_true")
    ap.add_argument("--cutoff-col", default="cutoff", help="cutoff column in the spine (default 'cutoff')")
    ap.add_argument("--latency", default="0s", help="data latency: only events older than cutoff - latency count")
    ap.add_argument("-o", "--output", help="output CSV (default stdout)")
    a = ap.parse_args()
    try:
        windows = sorted(((w, parse_window(w)) for w in a.windows), key=lambda x: x[1])
        latency = parse_window(a.latency)
        rows, by_entity, skipped = load_events(a.events, a.entity, a.time, a.value, a.distinct)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    times = {k: [e[0] for e in ev] for k, ev in by_entity.items()}
    out_rows = []
    if a.event_level:
        for k, ev in by_entity.items():
            for t, idx, _, _ in ev:
                f = features(ev, times[k], t - latency, windows, bool(a.value), a.distinct, exclude_idx=idx)
                out_rows.append((idx, f))
        out_rows.sort(key=lambda p: p[0])                      # back to the input order
        out_rows = [{**rows[i], **f} for i, f in out_rows]
    else:
        try:
            with open(a.spine, newline="", encoding="utf-8-sig") as fh:
                reader = csv.DictReader(fh)
                if a.entity not in (reader.fieldnames or []) or a.cutoff_col not in (reader.fieldnames or []):
                    raise ValueError(f"spine needs columns {a.entity!r} and {a.cutoff_col!r}")
                spine = list(reader)
        except (OSError, ValueError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        for r in spine:
            c = parse_time(r[a.cutoff_col])
            k = r[a.entity]
            if c is None:
                skipped += 1
                continue
            ev = by_entity.get(k, [])
            f = features(ev, times.get(k, []), c - latency, windows, bool(a.value), a.distinct)
            out_rows.append({**r, **f})
    if len(windows) >= 2 and a.value:
        s, l = windows[0][0], windows[-1][0]
        for r in out_rows:
            ms, ml = r.get(f"mean_{s}"), r.get(f"mean_{l}")
            r[f"ratio_{a.value}_{s}_{l}"] = round(ms / ml, 6) if ms is not None and ml else None
    if not out_rows:
        print("error: no output rows", file=sys.stderr)
        return 2
    keys = list(out_rows[0].keys())
    fh = open(a.output, "w", newline="", encoding="utf-8") if a.output else sys.stdout
    w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
    w.writeheader()
    for r in out_rows:
        w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in keys})
    if a.output:
        fh.close()
    print(f"{len(out_rows)} rows, {len(keys)} columns; windows {', '.join(n for n, _ in windows)}; latency {a.latency}"
          + (f"; skipped {skipped} rows with unparsable times" if skipped else ""), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
