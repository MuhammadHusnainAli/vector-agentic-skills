#!/usr/bin/env python3
"""Fit a Cox proportional hazards model (stdlib) and check its assumptions.

Input: CSV with duration, event (1/0) and covariate columns. Numeric covariates are used as they are;
non-numeric ones are one-hot encoded with the first level (sorted) as reference.

Fitting: Newton-Raphson on the partial likelihood with Efron's method for tied event times (the default in
lifelines and R's coxph), covariates centred internally for stability, optional ridge --penalizer.
Reports:
  coefficients  coef, hazard ratio exp(coef), 95% CI, z, p for every covariate
  fit           log partial likelihood, likelihood-ratio test against the null model, Harrell's concordance
  PH check      Grambsch-Therneau test per covariate: correlation of scaled Schoenfeld residuals with the
                rank of event time (as lifelines' proportional_hazard_test(time_transform="rank") and R's
                cox.zph). p < 0.05 means the hazard ratio changes over time: stratify on the variable, add a
                time interaction, or report time-specific effects
  warnings      events per covariate < 10 (overfitting), separation (|coef| > 10), non-convergence

Usage:
    python cox_fit.py survival.csv --duration-col duration_days --event-col event --covariates plan age
    python cox_fit.py data.csv --duration-col t --event-col died --covariates age sex stage --penalizer 0.1 --json

Exit codes: 0 fitted and PH holds, 1 PH violated for at least one covariate (p < --ph-alpha), 2 usage error or
no convergence.
"""

import argparse
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _surv_io import chi2_sf, load, norm_sf, num  # noqa: E402


def design(rows, covs):
    cols, cats = [], {}
    for c in covs:
        vals = [r[c] for _, _, r in rows]
        if all(num(v) is not None for v in vals):
            cols.append((c, None))
        else:
            levels = sorted(set(vals))
            if len(levels) < 2:
                continue
            cats[c] = levels
            cols += [(c, lv) for lv in levels[1:]]
    X = []
    for _, _, r in rows:
        X.append([float(r[c]) if lv is None else (1.0 if r[c] == lv else 0.0) for c, lv in cols])
    names = [c if lv is None else f"{c}={lv}" for c, lv in cols]
    return names, X, cats


def solve(A, b):
    n = len(b)
    M = [A[i][:] + [b[i]] for i in range(n)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        if abs(M[piv][c]) < 1e-14:
            raise ValueError("singular information matrix (collinear covariates or separation)")
        M[c], M[piv] = M[piv], M[c]
        for r in range(n):
            if r != c:
                f = M[r][c] / M[c][c]
                M[r] = [x - f * y for x, y in zip(M[r], M[c])]
    return [M[i][n] / M[i][i] for i in range(n)]


def inverse(A):
    n = len(A)
    return [list(col) for col in zip(*[solve(A, [1.0 if i == j else 0.0 for i in range(n)]) for j in range(n)])]


def efron(times, events, X, beta, pen):
    """Log partial likelihood, gradient and Hessian with Efron ties."""
    n, p = len(X), len(beta)
    order = sorted(range(n), key=lambda i: -times[i])
    eta = [sum(b * x for b, x in zip(beta, X[i])) for i in range(n)]
    w = [math.exp(min(e, 700)) for e in eta]
    S0, S1, S2 = 0.0, [0.0] * p, [[0.0] * p for _ in range(p)]
    ll, g, H = 0.0, [0.0] * p, [[0.0] * p for _ in range(p)]
    i = 0
    while i < n:
        t = times[order[i]]
        j = i
        tied = []
        while j < n and times[order[j]] == t:
            k = order[j]
            S0 += w[k]
            for a in range(p):
                S1[a] += w[k] * X[k][a]
                for b in range(p):
                    S2[a][b] += w[k] * X[k][a] * X[k][b]
            if events[k]:
                tied.append(k)
            j += 1
        d = len(tied)
        if d:
            T0 = sum(w[k] for k in tied)
            T1 = [sum(w[k] * X[k][a] for k in tied) for a in range(p)]
            T2 = [[sum(w[k] * X[k][a] * X[k][b] for k in tied) for b in range(p)] for a in range(p)]
            for k in tied:
                ll += eta[k]
                for a in range(p):
                    g[a] += X[k][a]
            for l in range(d):
                c = l / d
                s0 = S0 - c * T0
                s1 = [S1[a] - c * T1[a] for a in range(p)]
                ll -= math.log(s0)
                for a in range(p):
                    g[a] -= s1[a] / s0
                    for b in range(p):
                        H[a][b] -= (S2[a][b] - c * T2[a][b]) / s0 - s1[a] * s1[b] / (s0 * s0)
        i = j
    if pen:
        ll -= 0.5 * pen * sum(b * b for b in beta)
        for a in range(p):
            g[a] -= pen * beta[a]
            H[a][a] -= pen
    return ll, g, H


def fit(times, events, X, pen=0.0, max_iter=50):
    p = len(X[0])
    beta = [0.0] * p
    ll, g, H = efron(times, events, X, beta, pen)
    ll0 = ll
    for it in range(max_iter):
        step = solve([[-v for v in row] for row in H], g)
        t = 1.0
        while True:
            nb = [b + t * s for b, s in zip(beta, step)]
            nll, ng, nH = efron(times, events, X, nb, pen)
            if nll >= ll - 1e-12 or t < 1e-8:
                break
            t /= 2
        converged = abs(nll - ll) < 1e-10
        beta, ll, g, H = nb, nll, ng, nH
        if converged:
            return beta, ll, ll0, H, it + 1
    raise ValueError("Newton-Raphson did not converge (separation or collinearity?)")


def schoenfeld(times, events, X, beta):
    """Schoenfeld residuals (x_i - risk-set weighted mean) for each event, in time order."""
    n, p = len(X), len(beta)
    w = [math.exp(min(sum(b * x for b, x in zip(beta, X[i])), 700)) for i in range(n)]
    ev = sorted((times[i], i) for i in range(n) if events[i])
    out = []
    for t, i in ev:
        risk = [k for k in range(n) if times[k] >= t]
        s0 = sum(w[k] for k in risk)
        mean = [sum(w[k] * X[k][a] for k in risk) / s0 for a in range(p)]
        out.append((t, [X[i][a] - mean[a] for a in range(p)]))
    return out


def ph_test(res_s, V, p):
    d = len(res_s)
    times = [t for t, _ in res_s]
    order = sorted(range(d), key=lambda k: times[k])
    rank = [0.0] * d
    for r, k in enumerate(order):
        rank[k] = r + 1.0
    gbar = sum(rank) / d
    T = [r - gbar for r in rank]
    scaled = [[d * sum(res[b] * V[b][a] for b in range(p)) for a in range(p)] for _, res in res_s]
    out = []
    for a in range(p):
        numer = sum(T[k] * scaled[k][a] for k in range(d)) ** 2
        denom = d * sum(x * x for x in T) * V[a][a]
        stat = numer / denom if denom > 0 else 0.0
        out.append((stat, chi2_sf(stat, 1)))
    return out


def concordance(times, events, risk, limit=3000):
    idx = list(range(len(times)))
    note = None
    if len(idx) > limit:
        idx = random.Random(0).sample(idx, limit)
        note = f"computed on a random sample of {limit} rows"
    conc = disc = tied = 0
    for a in idx:
        if not events[a]:
            continue
        for b in idx:
            if times[b] > times[a]:
                if risk[a] > risk[b]:
                    conc += 1
                elif risk[a] < risk[b]:
                    disc += 1
                else:
                    tied += 1
    tot = conc + disc + tied
    return ((conc + 0.5 * tied) / tot if tot else None), note


def main():
    ap = argparse.ArgumentParser(description="Fit a Cox PH model and check proportional hazards.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--duration-col", required=True)
    ap.add_argument("--event-col", required=True)
    ap.add_argument("--covariates", nargs="+", required=True)
    ap.add_argument("--penalizer", type=float, default=0.0)
    ap.add_argument("--ph-alpha", type=float, default=0.05)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        rows = load(a.csv, a.duration_col, a.event_col)
        missing = [c for c in a.covariates if c not in rows[0][2]]
        if missing:
            raise ValueError(f"covariates not found: {', '.join(missing)}")
        rows = [r for r in rows if all(r[2][c] not in ("", None) for c in a.covariates)]
        names, X, cats = design(rows, a.covariates)
        if not names:
            raise ValueError("no usable covariates")
        times = [t for t, _, _ in rows]
        events = [e for _, e, _ in rows]
        means = [sum(x[j] for x in X) / len(X) for j in range(len(names))]
        Xc = [[x[j] - means[j] for j in range(len(names))] for x in X]
        beta, ll, ll0, H, iters = fit(times, events, Xc, a.penalizer)
        V = inverse([[-v for v in row] for row in H])
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    p = len(names)
    coefs = []
    for j, nme in enumerate(names):
        se = math.sqrt(max(V[j][j], 0.0))
        z = beta[j] / se if se else 0.0
        coefs.append({"covariate": nme, "coef": beta[j], "hr": math.exp(beta[j]), "se": se,
                      "hr_lo": math.exp(beta[j] - 1.959964 * se), "hr_hi": math.exp(beta[j] + 1.959964 * se),
                      "z": z, "p": 2 * norm_sf(abs(z))})
    lr = 2 * (ll - ll0)
    risk = [sum(b * x for b, x in zip(beta, xr)) for xr in Xc]
    cidx, cnote = concordance(times, events, risk)
    ph = ph_test(schoenfeld(times, events, Xc, beta), V, p)
    n_events = sum(events)
    res = {"n": len(rows), "events": n_events, "iterations": iters, "log_likelihood": ll,
           "lr_test": {"chi2": lr, "df": p, "p": chi2_sf(lr, p)}, "concordance": cidx, "coefficients": coefs,
           "ph_test": [{"covariate": nme, "stat": s, "p": pv} for nme, (s, pv) in zip(names, ph)],
           "reference_levels": {c: lv[0] for c, lv in cats.items()}, "warnings": []}
    if n_events / p < 10:
        res["warnings"].append(f"{n_events} events for {p} covariates (< 10 per covariate): coefficients may be "
                               "unstable; use --penalizer or fewer covariates")
    for c in coefs:
        if abs(c["coef"]) > 10:
            res["warnings"].append(f"{c['covariate']}: |coef| > 10 - separation or a covariate on a tiny scale")
    if cnote:
        res["warnings"].append(f"concordance {cnote}")
    violated = [r for r in res["ph_test"] if r["p"] < a.ph_alpha]
    if a.json:
        print(json.dumps(res, indent=2))
    else:
        lines = [f"n={res['n']} events={n_events} iterations={iters}   log partial likelihood {ll:.4f}   "
                 f"LR test chi2={lr:.3f} df={p} p={res['lr_test']['p']:.4g}   concordance {cidx:.3f}",
                 "" if not cats else "reference levels: " + ", ".join(f"{c}={lv}" for c, lv in res["reference_levels"].items()),
                 f"{'covariate':<22} {'coef':>8} {'HR':>7} {'95% CI':>17} {'z':>7} {'p':>9}   PH p"]
        for c, r in zip(coefs, res["ph_test"]):
            lines.append(f"{c['covariate'][:22]:<22} {c['coef']:>8.4f} {c['hr']:>7.3f} "
                         f"{'[' + format(c['hr_lo'], '.3f') + ', ' + format(c['hr_hi'], '.3f') + ']':>17} "
                         f"{c['z']:>7.2f} {c['p']:>9.3g}   {r['p']:.3g}" + ("  PH VIOLATED" if r["p"] < a.ph_alpha else ""))
        lines.append("")
        if violated:
            lines.append("PH assumption violated for: " + ", ".join(r["covariate"] for r in violated)
                         + " - stratify, add covariate x time, or report time-specific effects")
        else:
            lines.append(f"proportional hazards: no evidence against it (all PH p >= {a.ph_alpha})")
        for w in res["warnings"]:
            lines.append(f"WARNING: {w}")
        print("\n".join(ln for ln in lines if ln != ""))
    return 1 if violated else 0


if __name__ == "__main__":
    sys.exit(main())
