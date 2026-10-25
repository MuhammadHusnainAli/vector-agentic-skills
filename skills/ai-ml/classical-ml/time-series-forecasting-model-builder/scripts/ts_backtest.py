#!/usr/bin/env python3
"""Rolling-origin backtest of forecasting baselines (and your own forecasts) with scale-free metrics.

Baselines (stdlib, refit at every origin on the data before it):
  naive            last observed value
  snaive           value one season earlier (season from --season or the profile: daily 7, weekly 52,
                   monthly 12, quarterly 4, hourly 24)
  drift            last value + average historical change per step
  window_mean      mean of the last season (or 7 values)
  ses              simple exponential smoothing, alpha chosen by one-step in-sample SSE
  holt_winters     additive trend + additive season, parameters from a small grid by in-sample SSE
  croston, sba, tsb  intermittent-demand methods (only when the series has zeros)
Forecasts are clipped at 0 when the training history is non-negative.
Protocol: --folds origins spaced --step periods apart (default: the horizon), each forecasting --horizon
periods ahead; models never see data after the origin.

Metrics per model (over all folds and horizons):
  MAE, RMSE, WAPE (sum |e| / sum |y|), bias (sum e / sum y; positive = over-forecast), MASE (MAE divided
  by the in-sample MAE of the one-step seasonal naive on the training part of each fold) and RMSSE (the
  squared-error version used in the M5 competition). Multi-step MASE above 1 is normal; compare models.
  Skill vs snaive = 1 - metric(model) / metric(snaive). Models are ranked by MASE, or by RMSSE when more
  than 30% of the values are zero (MAE-type metrics reward forecasting zero for intermittent demand).
With --forecasts (CSV: origin,date,model,forecast; origin = the last training date), your own models are
scored on the same actuals and scales and ranked together with the baselines.

Usage:
    python ts_backtest.py sales.csv --horizon 28 --folds 6
    python ts_backtest.py demand.csv --horizon 8 --season 52 --forecasts my_forecasts.csv --json
    python ts_backtest.py sales.csv --horizon 28 --folds 4 --write-origins origins.csv

Exit codes: 0 backtested, 2 usage or read error.
"""

import argparse
import csv
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _ts_io import fill, infer_step, load_series, parse_time, regularise  # noqa: E402

SEASON = {"hourly": 24, "daily": 7, "weekly": 52, "monthly": 12, "quarterly": 4, "yearly": 1}


def naive(y, h, m):
    return [y[-1]] * h


def snaive(y, h, m):
    if m <= 1 or len(y) < m:
        return naive(y, h, m)
    return [y[len(y) - m + (k % m)] for k in range(h)]


def drift(y, h, m):
    slope = (y[-1] - y[0]) / (len(y) - 1) if len(y) > 1 else 0.0
    return [y[-1] + slope * (k + 1) for k in range(h)]


def window_mean(y, h, m):
    w = y[-max(m, 7):]
    return [sum(w) / len(w)] * h


def ses(y, h, m):
    best = None
    for a in (0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9):
        level, sse = y[0], 0.0
        for v in y[1:]:
            sse += (v - level) ** 2
            level = a * v + (1 - a) * level
        if best is None or sse < best[0]:
            best = (sse, level)
    return [best[1]] * h


def holt_winters(y, h, m):
    if m <= 1 or len(y) < 2 * m + 2:
        return drift(y, h, m)
    best = None
    first = sum(y[:m]) / m
    second = sum(y[m:2 * m]) / m
    for a in (0.1, 0.3, 0.5):
        for b in (0.01, 0.05, 0.15):
            for g in (0.05, 0.15, 0.3):
                level, trend = first, (second - first) / m
                season = [y[i] - first for i in range(m)]
                sse = 0.0
                for t in range(m, len(y)):
                    s = season[t % m]
                    pred = level + trend + s
                    sse += (y[t] - pred) ** 2
                    new_level = a * (y[t] - s) + (1 - a) * (level + trend)
                    trend = b * (new_level - level) + (1 - b) * trend
                    season[t % m] = g * (y[t] - new_level) + (1 - g) * s
                    level = new_level
                if best is None or sse < best[0]:
                    best = (sse, level, trend, list(season), len(y))
    _, level, trend, season, n = best
    return [level + trend * (k + 1) + season[(n + k) % m] for k in range(h)]


def croston(y, h, m, variant="croston", a=0.1):
    nz = [i for i, v in enumerate(y) if v > 0]
    if not nz:
        return [0.0] * h
    z, p = y[nz[0]], (nz[0] + 1)
    last = nz[0]
    for i in nz[1:]:
        z = a * y[i] + (1 - a) * z
        p = a * (i - last) + (1 - a) * p
        last = i
    f = z / p
    return [f * (1 - a / 2) if variant == "sba" else f] * h


def tsb(y, h, m, a=0.1, b=0.1):
    prob = 1.0 if y[0] > 0 else 0.0
    size = next((v for v in y if v > 0), 0.0)
    for v in y[1:]:
        occ = 1.0 if v > 0 else 0.0
        prob = b * occ + (1 - b) * prob
        if v > 0:
            size = a * v + (1 - a) * size
    return [prob * size] * h


MODELS = {"naive": naive, "snaive": snaive, "drift": drift, "window_mean": window_mean, "ses": ses,
          "holt_winters": holt_winters}
INTERMITTENT = {"croston": croston, "sba": lambda y, h, m: croston(y, h, m, "sba"), "tsb": tsb}


def scale(train, m):
    """(MAE, MSE) of the one-step seasonal naive on the training part: the MASE and RMSSE denominators."""
    lag = m if len(train) > m else 1
    d = [train[i] - train[i - lag] for i in range(lag, len(train))]
    if not d or not any(d):
        return None
    return sum(abs(x) for x in d) / len(d), sum(x * x for x in d) / len(d)


def score(errors):
    out = {}
    for name, rows in errors.items():
        if not rows:
            continue
        e = [r[0] for r in rows]
        yv = [r[1] for r in rows]
        sc = [abs(r[0]) / r[2][0] for r in rows if r[2]]
        sq = [r[0] ** 2 / r[2][1] for r in rows if r[2]]
        out[name] = {"mae": sum(abs(x) for x in e) / len(e), "rmse": math.sqrt(sum(x * x for x in e) / len(e)),
                     "rmsse": math.sqrt(sum(sq) / len(sq)) if sq else None,
                     "wape": sum(abs(x) for x in e) / sum(abs(v) for v in yv) if sum(abs(v) for v in yv) else None,
                     "bias": sum(e) / sum(yv) if sum(yv) else None,
                     "mase": sum(sc) / len(sc) if sc else None, "n": len(e)}
    return out


def add_skill(out, key):
    base = out.get("snaive", {}).get(key)
    for v in out.values():
        v["skill_vs_snaive"] = 1 - v[key] / base if base and v[key] is not None else None


def backtest(times, y, h, folds, step, m, forecasts):
    n = len(y)
    origins = [n - h - (folds - 1 - i) * step for i in range(folds)]
    origins = [o for o in origins if o >= max(2 * m, 10)]
    if not origins:
        raise ValueError("series too short for this horizon / folds / season")
    models = dict(MODELS)
    if any(v == 0 for v in y):
        models.update(INTERMITTENT)
    errors = {k: [] for k in models}
    per_h = {k: [[] for _ in range(h)] for k in models}
    for o in origins:
        train, test = y[:o], y[o:o + h]
        sc = scale(train, m)
        nonneg = min(train) >= 0
        for name, fn in models.items():
            fc = fn(train, len(test), m)
            if nonneg:
                fc = [max(0.0, f) for f in fc]                  # non-negative history: no negative forecasts
            for k, (f, a) in enumerate(zip(fc, test)):
                errors[name].append((f - a, a, sc))
                per_h[name][k].append(abs(f - a))
    if forecasts:
        index = {t: i for i, t in enumerate(times)}
        for (origin, model), pts in forecasts.items():
            oi = index.get(origin)
            if oi is None:
                continue
            sc = scale(y[:oi + 1], m)
            errors.setdefault(model, [])
            per_h.setdefault(model, [[] for _ in range(h)])
            for t, f in pts:
                ti = index.get(t)
                if ti is None or ti <= oi:
                    continue
                errors[model].append((f - y[ti], y[ti], sc))
                k = ti - oi - 1
                if k < h:
                    per_h[model][k].append(abs(f - y[ti]))
    res = score(errors)
    intermittent = sum(1 for v in y if v == 0) / len(y) > 0.3
    add_skill(res, "rmsse" if intermittent else "mase")
    for name, v in res.items():
        v["mae_by_horizon"] = [sum(b) / len(b) if b else None for b in per_h.get(name, [])]
    return res, [times[o - 1].isoformat() for o in origins], intermittent


def load_forecasts(path):
    out = {}
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for c in ("origin", "date", "model", "forecast"):
        if not rows or c not in rows[0]:
            raise ValueError(f"forecasts file needs columns origin,date,model,forecast (missing {c!r})")
    for r in rows:
        out.setdefault((parse_time(r["origin"]), r["model"]), []).append((parse_time(r["date"]), float(r["forecast"])))
    return out


def report(res, origins, h, m, intermittent):
    key = "rmsse" if intermittent else "mase"
    lines = [f"origins: {len(origins)} ({origins[0][:10]} .. {origins[-1][:10]})   horizon: {h}   season: {m}   "
             f"ranked by {key.upper()}" + ("  (intermittent: MAE/MASE reward forecasting zero)" if intermittent else ""),
             "", f"{'model':<16} {'MASE':>7} {'RMSSE':>7} {'skill':>7} {'MAE':>9} {'RMSE':>9} {'WAPE':>7} {'bias':>7}"]
    order = sorted(res, key=lambda k: (res[k][key] is None, res[k][key] or 0))
    for k in order:
        v = res[k]
        sk = "" if v["skill_vs_snaive"] is None else f"{v['skill_vs_snaive']:+.1%}"
        lines.append(f"{k:<16} {(v['mase'] or 0):>7.3f} {(v['rmsse'] or 0):>7.3f} {sk:>7} {v['mae']:>9.4g} "
                     f"{v['rmse']:>9.4g} {(v['wape'] or 0):>7.1%} {(v['bias'] or 0):>+7.1%}")
    best = order[0]
    lines.append("")
    lines.append(f"best: {best} ({key.upper()} {res[best][key]:.3f}; skill is 1 - {key.upper()} / {key.upper()} of snaive)")
    for k in order:
        if res[k]["bias"] is not None and res[k]["bias"] <= -0.9:
            lines.append(f"WARNING: {k} forecasts almost nothing (bias {res[k]['bias']:+.0%}): "
                         "useless for stocking decisions even if its MAE looks good")
    mh = res[best]["mae_by_horizon"]
    if mh and all(x is not None for x in mh):
        marks = sorted({0, len(mh) // 4, len(mh) // 2, len(mh) - 1})
        lines.append(f"{best} MAE by horizon: " + ", ".join(f"h{k + 1} {mh[k]:.4g}" for k in marks))
    lines.append("A candidate model is worth deploying only if it beats the best baseline here, on the same origins.")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Rolling-origin backtest of forecasting baselines.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--time-col")
    ap.add_argument("--value-col")
    ap.add_argument("--horizon", type=int, required=True)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--step", type=int, help="periods between origins (default: horizon)")
    ap.add_argument("--season", type=int)
    ap.add_argument("--forecasts", help="CSV origin,date,model,forecast to score alongside the baselines")
    ap.add_argument("--write-origins", help="write the origin dates used (one per line) for your own models")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        _, _, pts = load_series(a.csv, a.time_col, a.value_col)
        name, _, _ = infer_step(pts)
        times, raw = regularise(pts, name)
        y = fill(raw)
        m = a.season or SEASON[name]
        if a.horizon < 1 or a.folds < 1:
            raise ValueError("--horizon and --folds must be >= 1")
        fc = load_forecasts(a.forecasts) if a.forecasts else None
        res, origins, intermittent = backtest(times, y, a.horizon, a.folds, a.step or a.horizon, m, fc)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if a.write_origins:
        with open(a.write_origins, "w", encoding="utf-8") as f:
            f.write("\n".join(origins) + "\n")
    print(json.dumps({"origins": origins, "season": m, "models": res}, indent=2) if a.json
          else report(res, origins, a.horizon, m, intermittent))
    return 0


if __name__ == "__main__":
    sys.exit(main())
