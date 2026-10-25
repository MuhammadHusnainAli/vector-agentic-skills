#!/usr/bin/env python3
"""Profile a time series before forecasting: frequency, gaps, seasonality, trend, intermittency.

Input: CSV with a time column and a value column (auto-detected or --time-col / --value-col).

Reports:
  grid         inferred frequency, length, missing periods (gaps) and duplicated timestamps
  seasonality  autocorrelation at the candidate seasonal lags for the frequency (daily: 7, 365; weekly: 52;
               monthly: 12; hourly: 24, 168); the strongest lag with ACF >= 0.3 is the season length
  strength     trend and seasonal strength in [0, 1] from a moving-average decomposition
               (Wang, Smith & Hyndman 2006): F = max(0, 1 - var(remainder) / var(component + remainder))
  calendar     for daily data, mean by weekday and by month relative to the overall mean
  demand type  share of zeros; ADI (average interval between non-zero values) and CV^2 of the non-zero
               sizes -> Syntetos-Boylan class: smooth (ADI < 1.32, CV^2 < 0.49), erratic, intermittent,
               lumpy
  outliers     points more than 4 robust sds (MAD) from the decomposition's fit
  advice       baseline to beat, model families that fit the profile, backtest horizon and folds

Usage:
    python ts_profile.py sales.csv
    python ts_profile.py demand.csv --time-col week --value-col qty --horizon 8 --json

Exit codes: 0 profiled, 2 usage or read error.
"""

import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _ts_io import fill, infer_step, load_series, regularise  # noqa: E402

CANDIDATES = {"hourly": [24, 168], "daily": [7, 30, 365], "weekly": [4, 13, 52], "monthly": [3, 12],
              "quarterly": [4], "yearly": []}


def acf(x, lag):
    n = len(x)
    if lag >= n - 2:
        return None
    m = sum(x) / n
    den = sum((v - m) ** 2 for v in x)
    if den == 0:
        return 0.0
    return sum((x[i] - m) * (x[i + lag] - m) for i in range(n - lag)) / den


def centred_ma(x, w):
    n = len(x)
    h = w // 2
    out = [None] * n
    for i in range(h, n - h):
        if w % 2:
            out[i] = sum(x[i - h:i + h + 1]) / w
        else:                                            # 2xw MA for even windows
            out[i] = (sum(x[i - h:i + h]) + sum(x[i - h + 1:i + h + 1])) / (2 * w)
    return out


def var(xs):
    xs = [v for v in xs if v is not None]
    if len(xs) < 2:
        return 0.0
    m = sum(xs) / len(xs)
    return sum((v - m) ** 2 for v in xs) / (len(xs) - 1)


def decompose(x, period):
    trend = centred_ma(x, period if period > 1 else 3)
    detr = [v - t if t is not None else None for v, t in zip(x, trend)]
    if period > 1:
        means = []
        for k in range(period):
            vals = [detr[i] for i in range(k, len(x), period) if detr[i] is not None]
            means.append(sum(vals) / len(vals) if vals else 0.0)
        adj = sum(means) / period
        seas = [means[i % period] - adj for i in range(len(x))]
    else:
        seas = [0.0] * len(x)
    rem = [v - t - s if t is not None else None for v, t, s in zip(x, trend, seas)]
    return trend, seas, rem


def profile(times, raw, name, period_default, horizon):
    n = len(raw)
    missing = sum(v is None for v in raw)
    x = fill(raw)
    res = {"frequency": name, "length": n, "start": times[0].isoformat(), "end": times[-1].isoformat(),
           "missing_periods": missing}
    cands = [c for c in CANDIDATES[name] if c < n // 2]
    acfs = {c: acf(x, c) for c in cands}
    res["acf"] = acfs
    strong = [(v, c) for c, v in acfs.items() if v is not None and v >= 0.3]
    period = max(strong)[1] if strong else (cands[0] if cands and acfs[cands[0]] and acfs[cands[0]] > 0.15 else 1)
    if name == "daily" and 7 in acfs and acfs[7] is not None and acfs[7] >= 0.3:
        period = 7                                        # weekly cycle first; yearly handled by features
    res["season_length"] = period
    trend, seas, rem = decompose(x, period)
    tr = [t + r for t, r in zip(trend, rem) if t is not None]
    sr = [s + r for s, r, t in zip(seas, rem, trend) if t is not None]
    vr = var([r for r in rem if r is not None])
    res["trend_strength"] = max(0.0, 1 - vr / var(tr)) if var(tr) else 0.0
    res["seasonal_strength"] = max(0.0, 1 - vr / var(sr)) if period > 1 and var(sr) else 0.0
    resid = [r for r in rem if r is not None]
    med = sorted(resid)[len(resid) // 2] if resid else 0.0
    mad = sorted(abs(r - med) for r in resid)[len(resid) // 2] if resid else 0.0
    out_idx = [i for i, r in enumerate(rem) if r is not None and mad > 0 and abs(r - med) > 4 * 1.4826 * mad]
    res["outliers"] = [times[i].isoformat() for i in out_idx][:20]
    nz = [v for v in raw if v is not None and v != 0]
    zeros = sum(1 for v in raw if v == 0)
    res["zero_share"] = zeros / max(1, n - missing)
    if nz and zeros:
        positions = [i for i, v in enumerate(raw) if v not in (None, 0)]
        intervals = [b - a for a, b in zip(positions, positions[1:])]
        adi = sum(intervals) / len(intervals) if intervals else float(n)
        m = sum(nz) / len(nz)
        cv2 = var(nz) / (m * m) if m else 0.0
        res["adi"], res["cv2"] = adi, cv2
        res["demand_class"] = ("smooth" if adi < 1.32 and cv2 < 0.49 else "erratic" if adi < 1.32 else
                               "intermittent" if cv2 < 0.49 else "lumpy")
    else:
        res["demand_class"] = "continuous"
    if name == "daily" and n >= 28:
        overall = sum(x) / n
        wd = [[] for _ in range(7)]
        mo = [[] for _ in range(12)]
        for t, v in zip(times, x):
            wd[t.weekday()].append(v)
            mo[t.month - 1].append(v)
        res["weekday_index"] = [round(sum(w) / len(w) / overall, 3) if w and overall else None for w in wd]
        res["month_index"] = [round(sum(m) / len(m) / overall, 3) if m and overall else None for m in mo]
    h = horizon or {"hourly": 48, "daily": 28, "weekly": 8, "monthly": 6, "quarterly": 4, "yearly": 2}[name]
    res["horizon"] = h
    res["folds"] = max(1, min(8, (n - 3 * max(period, 1)) // max(h, 1) - 1))
    res["advice"] = advise(res, period)
    return res


def advise(r, period):
    out = []
    cls = r["demand_class"]
    if cls in ("intermittent", "lumpy"):
        out.append("intermittent demand: baseline Croston/SBA or TSB; evaluate with MASE or scaled MAE, not MAPE "
                   "(zeros); consider forecasting cumulative demand over the lead time or a probabilistic model")
    else:
        out.append(f"baseline to beat: seasonal naive (lag {period})" if period > 1 else "baseline to beat: naive / drift")
        if r["seasonal_strength"] >= 0.6:
            out.append("strong seasonality: ETS / TBATS / MSTL, or gradient boosting with seasonal lags and calendar "
                       "features")
        if r["trend_strength"] >= 0.6:
            out.append("strong trend: tree models cannot extrapolate it - detrend/difference the target or use "
                       "linear/ETS components")
        if r["length"] < 3 * max(period, 1) * 2:
            out.append("short history for the season length: prefer simple statistical models over ML")
        else:
            out.append("enough history for a global ML model (LightGBM on lags/rolling/calendar features) if many "
                       "related series exist")
    if r["missing_periods"]:
        out.append(f"{r['missing_periods']} missing period(s): fill explicitly (zero for no sales, interpolate for "
                   "sensor data) before building lags")
    if r["outliers"]:
        out.append(f"{len(r['outliers'])} outlier(s): check for promotions, stock-outs or data errors; model events "
                   "explicitly rather than deleting them")
    if ("month_index" in r and r["length"] >= 700 and cls not in ("intermittent", "lumpy")   # ~2 years per month
            and max(v for v in r["month_index"] if v) > 1.15):
        out.append("a calendar month runs > 15% above average: add month / holiday features (or yearly seasonality)")
    out.append(f"backtest: rolling origin, horizon {r['horizon']}, {r['folds']} folds (ts_backtest.py)")
    return out


def report(r):
    lines = [f"frequency: {r['frequency']}   length: {r['length']}   {r['start'][:10]} -> {r['end'][:10]}   "
             f"missing periods: {r['missing_periods']}"]
    lines.append("ACF at candidate lags: " + ", ".join(f"{k}: {v:.2f}" for k, v in r["acf"].items() if v is not None))
    lines.append(f"season length: {r['season_length']}   trend strength: {r['trend_strength']:.2f}   "
                 f"seasonal strength: {r['seasonal_strength']:.2f}")
    if "weekday_index" in r:
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        lines.append("weekday index: " + " ".join(f"{d} {v:.2f}" for d, v in zip(days, r["weekday_index"]) if v))
        lines.append("month index:   " + " ".join(f"{i + 1}:{v:.2f}" for i, v in enumerate(r["month_index"]) if v))
    dc = f"demand type: {r['demand_class']}   zeros: {r['zero_share']:.0%}"
    if "adi" in r:
        dc += f"   ADI {r['adi']:.2f}   CV^2 {r['cv2']:.2f}"
    lines.append(dc)
    if r["outliers"]:
        lines.append(f"outliers ({len(r['outliers'])}): " + ", ".join(o[:10] for o in r["outliers"][:8]))
    lines.append("")
    for a in r["advice"]:
        lines.append(f"- {a}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Profile a time series.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--time-col")
    ap.add_argument("--value-col")
    ap.add_argument("--horizon", type=int)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        _, _, pts = load_series(a.csv, a.time_col, a.value_col)
        name, period, _ = infer_step(pts)
        dup = len(pts) - len({p[0] for p in pts})
        times, values = regularise(pts, name)
        if len(times) < 10:
            raise ValueError("need at least 10 periods")
        r = profile(times, values, name, period, a.horizon)
        r["duplicate_timestamps"] = dup
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(json.dumps(r, indent=2) if a.json else report(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
