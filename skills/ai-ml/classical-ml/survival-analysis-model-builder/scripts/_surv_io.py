"""Shared helpers for the survival scripts: loading duration/event data and chi-square p-values (stdlib)."""

import csv
import math


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def load(path, duration_col, event_col):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError("no rows")
    for c in (duration_col, event_col):
        if c not in rows[0]:
            raise ValueError(f"column {c!r} not found (have: {', '.join(rows[0])})")
    out = []
    for r in rows:
        t, e = num(r[duration_col]), num(r[event_col])
        if t is None or e is None:
            continue
        if t < 0:
            raise ValueError(f"negative duration {t} - durations must be time from start to event or censoring")
        if e not in (0, 1):
            raise ValueError(f"event must be 0 (censored) or 1 (event), got {r[event_col]!r}")
        out.append((t, int(e), r))
    if len(out) < 10:
        raise ValueError("need at least 10 rows with duration and event")
    return out


def _gser(a, x):
    s = term = 1.0 / a
    ap = a
    for _ in range(500):
        ap += 1
        term *= x / ap
        s += term
        if abs(term) < abs(s) * 1e-14:
            break
    return s * math.exp(-x + a * math.log(x) - math.lgamma(a))


def _gcf(a, x):
    b = x + 1 - a
    c = 1e300
    d = 1 / b
    h = d
    for i in range(1, 500):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-14:
            break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def chi2_sf(x, df):
    """P(Chi2_df > x) via the regularised upper incomplete gamma function."""
    if x <= 0:
        return 1.0
    a, y = df / 2, x / 2
    return 1 - _gser(a, y) if y < a + 1 else _gcf(a, y)


def norm_sf(z):
    return 0.5 * math.erfc(z / math.sqrt(2))
