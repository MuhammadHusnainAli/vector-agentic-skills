"""Shared helpers for the uplift scripts: number parsing and the chi-square tail (stdlib only)."""

import math


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def chi2_sf(x, df):
    """P(Chi2_df > x) via the regularised upper incomplete gamma function."""
    if x <= 0:
        return 1.0
    a, y = df / 2, x / 2
    if y < a + 1:
        s = term = 1.0 / a
        ap = a
        for _ in range(500):
            ap += 1
            term *= y / ap
            s += term
            if abs(term) < abs(s) * 1e-14:
                break
        return 1 - s * math.exp(-y + a * math.log(y) - math.lgamma(a))
    b, c, d = y + 1 - a, 1e300, 1 / (y + 1 - a)
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
    return math.exp(-y + a * math.log(y) - math.lgamma(a)) * h
