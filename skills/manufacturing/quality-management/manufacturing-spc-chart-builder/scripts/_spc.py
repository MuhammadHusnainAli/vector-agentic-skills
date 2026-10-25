"""Control chart calculations shared by control_limits.py and plot_chart.py (stdlib only).

Charts: imr, xbar-r, xbar-s (variables); p, np, c, u (attributes).
Constants: d2, d3 tabulated for n = 2..10; c4 computed exactly, so S charts work for any n.
"""

import csv
import math
from statistics import mean

D2 = {2: 1.128, 3: 1.693, 4: 2.059, 5: 2.326, 6: 2.534, 7: 2.704, 8: 2.847, 9: 2.970, 10: 3.078}
D3 = {2: 0.853, 3: 0.888, 4: 0.880, 5: 0.864, 6: 0.848, 7: 0.833, 8: 0.820, 9: 0.808, 10: 0.797}


def c4(n):
    return math.sqrt(2 / (n - 1)) * math.exp(math.lgamma(n / 2) - math.lgamma((n - 1) / 2))


def read_rows(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def to_float(v, what):
    try:
        return float(v)
    except (TypeError, ValueError):
        raise ValueError(f"non-numeric {what}: {v!r}")


def subgroups(rows, value, subgroup=None, size=None):
    vals = [to_float(r[value], value) for r in rows if (r.get(value) or "").strip() != ""]
    if subgroup:
        groups, order = {}, []
        for r in rows:
            if (r.get(value) or "").strip() == "":
                continue
            k = r[subgroup]
            if k not in groups:
                groups[k] = []
                order.append(k)
            groups[k].append(to_float(r[value], value))
        return [groups[k] for k in order], order
    size = size or 1
    groups = [vals[i:i + size] for i in range(0, len(vals) - len(vals) % size, size)]
    return groups, [str(i + 1) for i in range(len(groups))]


def choose(n, attribute=None, varying=False):
    if attribute == "defectives":
        return "p" if varying else "np"
    if attribute == "defects":
        return "u" if varying else "c"
    return "imr" if n == 1 else "xbar-r" if n <= 9 else "xbar-s"


def variables(groups, chart):
    """Return dict with main and secondary series and limits."""
    n = len(groups[0])
    if any(len(g) != n for g in groups):
        raise ValueError("subgroups must have equal size for X-bar charts (drop or complete short subgroups)")
    if chart == "imr":
        x = [g[0] for g in groups]
        mr = [abs(b - a) for a, b in zip(x, x[1:])]
        mrbar = mean(mr)
        sigma = mrbar / D2[2]
        xbar = mean(x)
        return {"main": ("Individuals", x, xbar, xbar + 3 * sigma, xbar - 3 * sigma),
                "second": ("Moving range", [None] + mr, mrbar, 3.267 * mrbar, 0.0), "sigma": sigma, "n": 1}
    means = [mean(g) for g in groups]
    xbb = mean(means)
    if chart == "xbar-r":
        if n not in D2:
            raise ValueError("X-bar/R needs subgroup size 2-10; use xbar-s for larger subgroups")
        r = [max(g) - min(g) for g in groups]
        rbar = mean(r)
        d2, d3 = D2[n], D3[n]
        a2 = 3 / (d2 * math.sqrt(n))
        return {"main": ("X-bar", means, xbb, xbb + a2 * rbar, xbb - a2 * rbar),
                "second": ("Range", r, rbar, (1 + 3 * d3 / d2) * rbar, max(0.0, 1 - 3 * d3 / d2) * rbar),
                "sigma": rbar / d2, "n": n}
    s = [math.sqrt(sum((v - m) ** 2 for v in g) / (n - 1)) for g, m in zip(groups, means)]
    sbar = mean(s)
    k = c4(n)
    a3 = 3 / (k * math.sqrt(n))
    b = 3 * math.sqrt(1 - k * k) / k
    return {"main": ("X-bar", means, xbb, xbb + a3 * sbar, xbb - a3 * sbar),
            "second": ("Std dev", s, sbar, (1 + b) * sbar, max(0.0, 1 - b) * sbar), "sigma": sbar / k, "n": n}


def attributes(counts, sizes, chart):
    """Per-point limits (lists) because p and u limits vary with sample size."""
    if chart in ("p", "np"):
        pbar = sum(counts) / sum(sizes)
        if chart == "np":
            n = sizes[0]
            c = n * pbar
            w = 3 * math.sqrt(c * (1 - pbar))
            return {"main": ("np (defectives)", counts, c, [c + w] * len(counts), [max(0.0, c - w)] * len(counts))}
        pts = [k / n for k, n in zip(counts, sizes)]
        ucl = [pbar + 3 * math.sqrt(pbar * (1 - pbar) / n) for n in sizes]
        lcl = [max(0.0, pbar - 3 * math.sqrt(pbar * (1 - pbar) / n)) for n in sizes]
        return {"main": ("p (fraction defective)", pts, pbar, ucl, lcl)}
    ubar = sum(counts) / sum(sizes)
    if chart == "c":
        c = mean(counts)
        return {"main": ("c (defects)", counts, c, [c + 3 * math.sqrt(c)] * len(counts), [max(0.0, c - 3 * math.sqrt(c))] * len(counts))}
    pts = [k / n for k, n in zip(counts, sizes)]
    return {"main": ("u (defects per unit)", pts, ubar, [ubar + 3 * math.sqrt(ubar / n) for n in sizes],
                     [max(0.0, ubar - 3 * math.sqrt(ubar / n)) for n in sizes])}


def beyond(series):
    """Indexes (0-based) of points outside the limits; limits may be scalars or lists."""
    name, pts, cl, ucl, lcl = series
    out = []
    for i, v in enumerate(pts):
        if v is None:
            continue
        u = ucl[i] if isinstance(ucl, list) else ucl
        lo = lcl[i] if isinstance(lcl, list) else lcl
        if v > u + 1e-12 or v < lo - 1e-12:
            out.append(i)
    return out
