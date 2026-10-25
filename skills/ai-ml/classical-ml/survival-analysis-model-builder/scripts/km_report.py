#!/usr/bin/env python3
"""Kaplan-Meier survival report: curves, medians, survival at chosen times, log-rank test and RMST.

Input: CSV with a duration column (time from start to event or censoring) and an event column (1 = event
observed, 0 = censored); optional --group column.

Reports per group (and overall):
  n, events, censored share
  survival S(t) at --at times with 95% CIs (Greenwood variance, log(-log) transform, as in lifelines and R)
  median survival time with its 95% CI (Brookmeyer-Crowley style: where the CI band crosses 0.5), or
  "not reached" when fewer than half had the event
  restricted mean survival time (RMST) up to --tau (default: the smallest group's largest follow-up), the
  average event-free time in [0, tau], with the difference between groups
  number at risk at the --at times
Across groups:
  log-rank test (chi-square with k-1 df) for equal survival curves
Warnings: heavy censoring (> 70%), groups with < 10 events, curves that cross (proportional hazards is
doubtful: prefer RMST or time-specific comparisons over a single hazard ratio).

Usage:
    python km_report.py survival.csv --duration-col duration_days --event-col event
    python km_report.py survival.csv --duration-col duration_days --event-col event --group plan --at 90 180 365
    python km_report.py data.csv --duration-col t --event-col died --group arm --tau 365 --json

Exit codes: 0 reported, 2 usage or read error.
"""

import argparse
import json
import math
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _surv_io import chi2_sf, load  # noqa: E402


def km(data):
    """data: list of (t, e). Returns step points [(t, S, var_greenwood_sum, n_at_risk, d)]."""
    times = sorted({t for t, e in data if e == 1})
    n = len(data)
    by_t = defaultdict(lambda: [0, 0])
    for t, e in data:
        by_t[t][0 if e else 1] += 1
    at_risk = n
    s, gw = 1.0, 0.0
    steps = []
    for t in sorted(by_t):
        d, c = by_t[t]
        if d:
            s *= 1 - d / at_risk
            if at_risk > d:
                gw += d / (at_risk * (at_risk - d))
            steps.append((t, s, gw, at_risk, d))
        at_risk -= d + c
    return steps


def s_at(steps, t):
    s, gw = 1.0, 0.0
    for st, sv, g, _, _ in steps:
        if st <= t:
            s, gw = sv, g
        else:
            break
    return s, gw


def ci_loglog(s, gw, z=1.959964):
    if s <= 0 or s >= 1 or gw == 0:
        return (s, s)
    se = math.sqrt(gw) / abs(math.log(s))
    lo = s ** math.exp(z * se)
    hi = s ** math.exp(-z * se)
    return lo, hi


def median(steps):
    def cross(f):
        for st, sv, g, _, _ in steps:
            if f(sv, g) <= 0.5:
                return st
        return None
    est = cross(lambda s, g: s)
    lo = cross(lambda s, g: ci_loglog(s, g)[0])
    hi = cross(lambda s, g: ci_loglog(s, g)[1])
    return est, lo, hi


def rmst(steps, tau):
    area, prev_t, prev_s = 0.0, 0.0, 1.0
    for st, sv, _, _, _ in steps:
        if st > tau:
            break
        area += prev_s * (st - prev_t)
        prev_t, prev_s = st, sv
    return area + prev_s * (tau - prev_t)


def at_risk(data, t):
    return sum(1 for d, _ in data if d >= t)


def logrank(groups):
    names = list(groups)
    all_data = [(t, e, g) for g in names for t, e in groups[g]]
    times = sorted({t for t, e, _ in all_data if e})
    k = len(names)
    O = [0.0] * k
    E = [0.0] * k
    V = [[0.0] * k for _ in range(k)]
    for t in times:
        n_j = [sum(1 for d, _ in groups[g] if d >= t) for g in names]
        d_j = [sum(1 for d, e in groups[g] if d == t and e) for g in names]
        n, d = sum(n_j), sum(d_j)
        if n < 2:
            continue
        for i in range(k):
            O[i] += d_j[i]
            E[i] += d * n_j[i] / n
            for j in range(k):
                cov = d * (n - d) / (n * n * (n - 1)) * (n_j[i] * (n if i == j else 0) - n_j[i] * n_j[j])
                V[i][j] += cov
    m = k - 1
    if m < 1:
        return None
    u = [O[i] - E[i] for i in range(m)]
    A = [row[:m] for row in V[:m]]
    # solve A x = u (Gauss-Jordan)
    M = [A[i] + [u[i]] for i in range(m)]
    for c in range(m):
        piv = max(range(c, m), key=lambda r: abs(M[r][c]))
        if abs(M[piv][c]) < 1e-12:
            return None
        M[c], M[piv] = M[piv], M[c]
        for r in range(m):
            if r != c:
                f = M[r][c] / M[c][c]
                M[r] = [a - f * b for a, b in zip(M[r], M[c])]
    x = [M[i][m] / M[i][i] for i in range(m)]
    chi2 = sum(ui * xi for ui, xi in zip(u, x))
    return {"chi2": chi2, "df": m, "p": chi2_sf(chi2, m), "observed": dict(zip(names, O)), "expected": dict(zip(names, E))}


def report(res, at):
    lines = []
    for g, r in res["groups"].items():
        med = r["median"]
        mtxt = "not reached" if med[0] is None else (
            f"{med[0]:.4g} (95% CI {med[1]:.4g} - " + ("NR" if med[2] is None else f"{med[2]:.4g}") + ")"
            if med[1] is not None else f"{med[0]:.4g}")
        lines.append(f"[{g}] n={r['n']} events={r['events']} censored={r['censored_share']:.0%}   median survival: {mtxt}   "
                     f"RMST({res['tau']:.4g}) = {r['rmst']:.4g}")
        for t, s in zip(at, r["at"]):
            lines.append(f"    S({t:g}) = {s['s']:.3f} [{s['lo']:.3f}, {s['hi']:.3f}]   at risk: {s['at_risk']}")
    lr = res.get("logrank")
    if lr:
        lines.append("")
        lines.append(f"log-rank test: chi2 = {lr['chi2']:.3f}, df = {lr['df']}, p = {lr['p']:.4g}")
        lines.append("  observed / expected events: " + ", ".join(f"{g} {lr['observed'][g]:.0f}/{lr['expected'][g]:.1f}"
                                                                for g in lr["observed"]))
    if len(res["groups"]) == 3 and "overall" in res["groups"]:
        pass
    diffs = res.get("rmst_diff")
    if diffs:
        lines.append("RMST difference vs " + diffs["reference"] + ": " +
                     ", ".join(f"{g} {d:+.4g}" for g, d in diffs["diff"].items()))
    for w in res["warnings"]:
        lines.append(f"WARNING: {w}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Kaplan-Meier survival report.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--duration-col", required=True)
    ap.add_argument("--event-col", required=True)
    ap.add_argument("--group")
    ap.add_argument("--at", type=float, nargs="*", help="times at which to report S(t) (default: quartiles of follow-up)")
    ap.add_argument("--tau", type=float, help="RMST horizon")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        rows = load(a.csv, a.duration_col, a.event_col)
        if a.group and a.group not in rows[0][2]:
            raise ValueError(f"group column {a.group!r} not found")
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    groups = defaultdict(list)
    for t, e, r in rows:
        groups[r[a.group] if a.group else "all"].append((t, e))
    groups = dict(sorted(groups.items()))
    follow = sorted(t for t, _, _ in rows)
    at = a.at or [round(follow[int(q * (len(follow) - 1))], 1) for q in (0.25, 0.5, 0.75)]
    tau = a.tau or min(max(t for t, _ in g) for g in groups.values())
    res = {"groups": {}, "tau": tau, "warnings": []}
    curves = {}
    for g, data in groups.items():
        steps = km(data)
        curves[g] = steps
        ev = sum(e for _, e in data)
        r = {"n": len(data), "events": ev, "censored_share": 1 - ev / len(data), "median": median(steps),
             "rmst": rmst(steps, tau), "at": []}
        for t in at:
            s, gw = s_at(steps, t)
            lo, hi = ci_loglog(s, gw)
            r["at"].append({"t": t, "s": s, "lo": lo, "hi": hi, "at_risk": at_risk(data, t)})
        res["groups"][g] = r
        if r["censored_share"] > 0.7:
            res["warnings"].append(f"{g}: {r['censored_share']:.0%} censored - estimates beyond early times are uncertain")
        if ev < 10:
            res["warnings"].append(f"{g}: only {ev} events - curves and tests are unreliable")
    if len(groups) > 1:
        res["logrank"] = logrank(groups)
        ref = next(iter(groups))
        res["rmst_diff"] = {"reference": ref, "diff": {g: res["groups"][g]["rmst"] - res["groups"][ref]["rmst"]
                                                       for g in groups if g != ref}}
        grid = sorted({st for steps in curves.values() for st, *_ in steps})
        names = list(groups)
        if len(names) == 2 and grid:
            sign = [s_at(curves[names[0]], t)[0] - s_at(curves[names[1]], t)[0] for t in grid]
            sig = [x for x in sign if abs(x) > 0.05]
            if sig and min(sig) < 0 < max(sig):
                res["warnings"].append("the survival curves cross: a single hazard ratio misrepresents the difference; "
                                       "report RMST or survival at specific times")
    print(json.dumps(res, indent=2) if a.json else report(res, at))
    return 0


if __name__ == "__main__":
    sys.exit(main())
