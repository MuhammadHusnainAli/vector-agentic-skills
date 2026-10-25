"""Shared helpers for the forecasting scripts: load a series, infer its frequency, regularise it (stdlib only)."""

import csv
import datetime as dt
import math
import sys

FREQS = [(1 / 24, "hourly", 24), (1, "daily", 7), (7, "weekly", 52), (30.4, "monthly", 12), (91.3, "quarterly", 4),
         (365.25, "yearly", 1)]


def parse_time(s):
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m", "%Y/%m/%d",
                "%d/%m/%Y", "%Y-%m-%dT%H:%M"):
        try:
            return dt.datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"cannot parse time {s!r}")


def load_series(path, time_col, value_col):
    f = sys.stdin if path == "-" else open(path, newline="", encoding="utf-8")
    with f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError("no rows")
    cols = list(rows[0])
    time_col = time_col or next((c for c in cols if c.lower() in ("date", "ds", "time", "timestamp", "datetime",
                                                                  "period", "month", "week")), cols[0])
    value_col = value_col or next((c for c in cols if c != time_col), None)
    for c in (time_col, value_col):
        if c not in cols:
            raise ValueError(f"column {c!r} not found (have: {', '.join(cols)})")
    pts = []
    for r in rows:
        try:
            v = float(r[value_col]) if r[value_col] not in ("", "NA", "nan") else None
        except ValueError:
            v = None
        pts.append((parse_time(r[time_col]), v))
    pts.sort(key=lambda p: p[0])
    return time_col, value_col, pts


def infer_step(pts):
    diffs = sorted((b[0] - a[0]).total_seconds() / 86400 for a, b in zip(pts, pts[1:]) if b[0] > a[0])
    if not diffs:
        raise ValueError("need at least two distinct timestamps")
    med = diffs[len(diffs) // 2]
    name, period, step = min(FREQS, key=lambda f: abs(math.log(med / f[0])))[1:] + (med,)
    return name, period, step


def advance(t, name, k=1):
    if name == "monthly":
        m = t.month - 1 + k
        return t.replace(year=t.year + m // 12, month=m % 12 + 1, day=min(t.day, 28))
    if name == "quarterly":
        return advance(t, "monthly", 3 * k)
    if name == "yearly":
        return t.replace(year=t.year + k)
    days = {"hourly": 1 / 24, "daily": 1, "weekly": 7}[name]
    return t + dt.timedelta(days=days * k)


def regularise(pts, name):
    """Return (times, values) on a complete grid; missing periods get None. Duplicates keep the last value."""
    by = {}
    for t, v in pts:
        by[t] = v
    times, values = [], []
    t, end = pts[0][0], pts[-1][0]
    guard = 0
    while t <= end and guard < 10_000_000:
        times.append(t)
        values.append(by.get(t))
        t = advance(t, name)
        guard += 1
    return times, values


def fill(values):
    """Linear interpolation over None (edges use the nearest value)."""
    out = list(values)
    idx = [i for i, v in enumerate(out) if v is not None]
    if not idx:
        raise ValueError("series has no values")
    for i in range(len(out)):
        if out[i] is None:
            left = max((j for j in idx if j < i), default=None)
            right = min((j for j in idx if j > i), default=None)
            if left is None:
                out[i] = out[right]
            elif right is None:
                out[i] = out[left]
            else:
                w = (i - left) / (right - left)
                out[i] = out[left] * (1 - w) + out[right] * w
    return out
