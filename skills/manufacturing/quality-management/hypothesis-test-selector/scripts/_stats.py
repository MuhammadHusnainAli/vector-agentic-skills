"""Distribution functions for run_test.py (stdlib only): Student t, F, chi-square via incomplete beta/gamma."""

import math
from statistics import NormalDist

NORMAL = NormalDist()


def _betacf(a, b, x):
    c, d = 1.0, 1 - (a + b) * x / (a + 1)
    d = 1 / (d or 1e-300)
    h = d
    for m in range(1, 400):
        for aa in (m * (b - m) * x / ((a - 1 + 2 * m) * (a + 2 * m)), -(a + m) * (a + b + m) * x / ((a + 2 * m) * (a + 1 + 2 * m))):
            d = 1 / ((1 + aa * d) or 1e-300)
            c = (1 + aa / c) or 1e-300
            h *= d * c
        if abs(d * c - 1) < 1e-13:
            break
    return h


def betainc(a, b, x):
    """Regularized incomplete beta I_x(a, b)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbt = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x)
    if x < (a + 1) / (a + b + 2):
        return math.exp(lbt) * _betacf(a, b, x) / a
    return 1 - math.exp(lbt) * _betacf(b, a, 1 - x) / b


def gammainc_upper(s, x):
    """Regularized upper incomplete gamma Q(s, x)."""
    if x <= 0:
        return 1.0
    if x < s + 1:
        term = total = 1 / s
        for n in range(1, 500):
            term *= x / (s + n)
            total += term
            if abs(term) < abs(total) * 1e-14:
                break
        return 1 - total * math.exp(-x + s * math.log(x) - math.lgamma(s))
    b, c, d = x + 1 - s, 1e300, 1 / (x + 1 - s)
    h = d
    for i in range(1, 500):
        an = -i * (i - s)
        b += 2
        d = 1 / ((an * d + b) or 1e-300)
        c = (b + an / c) or 1e-300
        h *= d * c
        if abs(d * c - 1) < 1e-14:
            break
    return math.exp(-x + s * math.log(x) - math.lgamma(s)) * h


def t_sf2(t, df):
    """Two-sided p-value for Student t."""
    return betainc(df / 2, 0.5, df / (df + t * t))


def t_ppf(q, df):
    lo, hi = -200.0, 200.0
    for _ in range(200):
        mid = (lo + hi) / 2
        cdf = 1 - t_sf2(mid, df) / 2 if mid >= 0 else t_sf2(mid, df) / 2
        lo, hi = (mid, hi) if cdf < q else (lo, mid)
    return (lo + hi) / 2


def f_sf(f, d1, d2):
    return 1 - betainc(d1 / 2, d2 / 2, d1 * f / (d1 * f + d2)) if f > 0 else 1.0


def chi2_sf(x, df):
    return gammainc_upper(df / 2, x / 2)
