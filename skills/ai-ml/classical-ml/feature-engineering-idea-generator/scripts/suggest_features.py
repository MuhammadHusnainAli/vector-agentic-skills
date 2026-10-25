#!/usr/bin/env python3
"""Suggest concrete, leakage-aware feature ideas for a CSV and emit pandas code for them.

Uses profile_columns.py (same folder) to infer column roles, then proposes:
  per column   date parts + cyclical encodings + elapsed time, year -> age, log1p for skewed
               amounts, missing indicators, clipping, frequency encoding for high-cardinality,
               rare-level grouping, text length / word counts / TF-IDF, code prefixes (zip3)
  across       ratios and per-unit rates between amount/count columns (total / tenure),
               differences between datetime columns, distance from lat/lon pairs
  per entity   with --entity: count, mean, std, min, max, last, days-since per entity using only
               rows before each row's time (--time-col), i.e. point-in-time aggregates
  risk flags   columns whose names suggest they are written after the outcome (status, reason,
               refund, cancel, outcome, result, resolution, chargeback, closed)

Ideas are ranked: P1 cheap and usually useful, P2 worth testing, P3 situational.

Usage:
    python suggest_features.py data.csv --target churned
    python suggest_features.py txns.csv --target is_fraud --entity card_id --time-col timestamp
    python suggest_features.py data.csv --target price --code > features.py
    python suggest_features.py data.csv --target churned --json

Exit codes: 0 suggestions printed, 2 usage or read error.
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from profile_columns import profile  # noqa: E402

LEAK_WORDS = re.compile(r"(status|reason|refund|cancel|outcome|result|resolution|chargeback|closed|churn|"
                        r"_after|post_|final_|label|target)", re.I)


def ideas_for(p, ref_col):
    c, role = p["column"], p["role"]
    out = []

    def add(prio, idea, code):
        out.append({"column": c, "priority": prio, "idea": idea, "code": code})

    if role == "datetime":
        parse = f'pd.to_datetime(df["{c}"], unit="s")' if "epoch" in p.get("note", "") else f'pd.to_datetime(df["{c}"], errors="coerce")'
        has_time = "epoch" in p.get("note", "") or any(ch in str(p.get("max", "")) for ch in "T:")
        add("P1", "calendar parts: month, day of week, is_weekend" + (", hour" if has_time else ""),
            f'd = {parse}\ndf["{c}_month"] = d.dt.month\ndf["{c}_dow"] = d.dt.day_of_week\n'
            f'df["{c}_is_weekend"] = (d.dt.day_of_week >= 5).astype(int)' + (f'\ndf["{c}_hour"] = d.dt.hour' if has_time else ""))
        add("P2", "cyclical encoding of month / hour for linear and distance-based models",
            f'df["{c}_month_sin"] = np.sin(2 * np.pi * d.dt.month / 12)\n'
            f'df["{c}_month_cos"] = np.cos(2 * np.pi * d.dt.month / 12)')
        if ref_col and ref_col != c:
            add("P1", f"elapsed days between {c} and the prediction time ({ref_col})",
                f'df["days_since_{c}"] = (pd.to_datetime(df["{ref_col}"]) - d).dt.days')
        else:
            add("P1", "elapsed time to a fixed reference date (age of the record at prediction time)",
                f'REF = pd.Timestamp("2026-01-01")   # use the scoring date in production\n'
                f'df["days_since_{c}"] = (REF - d).dt.days')
    elif role == "year":
        add("P1", "convert year to age at prediction time", f'df["{c}_age"] = REF_YEAR - df["{c}"]   # e.g. 2026')
    elif role == "amount":
        if p.get("skew", 0) > 1:
            add("P1", f"log1p transform (skew {p['skew']:.1f}) for linear / distance models",
                f'df["log_{c}"] = np.log1p(df["{c}"].clip(lower=0))')
        add("P2", "cap extreme values at the 1st/99th percentile learned on train",
            f'lo, hi = train["{c}"].quantile([0.01, 0.99])\ndf["{c}_clip"] = df["{c}"].clip(lo, hi)')
    elif role == "count":
        if p.get("skew", 0) > 1:
            add("P2", f"log1p or binned version of a skewed count (skew {p['skew']:.1f})",
                f'df["log_{c}"] = np.log1p(df["{c}"])')
        if p.get("min") == 0:
            add("P3", "zero indicator for counts where 'none' differs from 'few'",
                f'df["{c}_is_zero"] = (df["{c}"] == 0).astype(int)')
    elif role == "categorical":
        if p.get("rare_levels"):
            add("P1", f"group {p['rare_levels']} rare level(s) into 'other' (learned on train)",
                f'keep = train["{c}"].value_counts()\nkeep = keep[keep >= 20].index\n'
                f'df["{c}"] = df["{c}"].where(df["{c}"].isin(keep), "other")')
    elif role == "high_card":
        add("P1", "frequency encoding (count of the level in train)",
            f'freq = train["{c}"].value_counts()\ndf["{c}_freq"] = df["{c}"].map(freq).fillna(0)')
        add("P2", "out-of-fold target encoding (see categorical-encoding-selector)",
            f'# sklearn >= 1.3: TargetEncoder(cv=5) inside the Pipeline, never fitted on the full data')
    elif role == "code":
        add("P1", "treat as categorical; use the prefix as a coarser level (e.g. zip3 region)",
            f'df["{c}_prefix3"] = df["{c}"].astype(str).str[:3]')
    elif role == "text":
        add("P1", "length and word count", f'df["{c}_len"] = df["{c}"].str.len()\ndf["{c}_words"] = df["{c}"].str.split().str.len()')
        add("P2", "TF-IDF (word 1-2 grams, min_df=5) inside the pipeline, or sentence embeddings",
            f'# ColumnTransformer: ("txt", TfidfVectorizer(ngram_range=(1, 2), min_df=5), "{c}")')
    elif role == "percentage":
        add("P3", "logit transform for proportions near 0/1 in linear models",
            f'q = df["{c}"].clip(1e-4, 1 - 1e-4)\ndf["logit_{c}"] = np.log(q / (1 - q))')
    if p.get("missing", 0) > 0.01 and role not in ("id", "constant", "target"):
        add("P1", f"missing indicator ({p['missing']:.0%} missing): missingness is often informative",
            f'df["{c}_missing"] = df["{c}"].isna().astype(int)')
    return out


def cross_ideas(prof, entity, time_col):
    out = []
    amounts = [p["column"] for p in prof if p["role"] in ("amount", "count")]
    counts = [p["column"] for p in prof if p["role"] == "count"]
    dates = [p["column"] for p in prof if p["role"] == "datetime" and p["column"] != time_col]
    for a in amounts:
        for b in counts:
            # cumulative totals divided by an exposure (tenure, age, number of orders) give a rate
            if a != b and re.search(r"(total|sum|cum|lifetime)", a, re.I) and \
                    re.search(r"(tenure|age|duration|exposure|active|^n_|num_|_count$|orders)", b, re.I):
                out.append({"column": f"{a}/{b}", "priority": "P1",
                            "idea": f"rate: {a} per unit of {b} (removes the size effect)",
                            "code": f'df["{a}_per_{b}"] = df["{a}"] / df["{b}"].replace(0, np.nan)'})
    for i, a in enumerate(dates):
        for b in dates[i + 1:]:
            out.append({"column": f"{a}-{b}", "priority": "P2", "idea": f"days between {a} and {b}",
                        "code": f'df["days_{a}_to_{b}"] = (pd.to_datetime(df["{b}"]) - pd.to_datetime(df["{a}"])).dt.days'})
    lat = [p["column"] for p in prof if p["role"] == "geo_lat"]
    lon = [p["column"] for p in prof if p["role"] == "geo_lon"]
    if lat and lon:
        out.append({"column": f"{lat[0]},{lon[0]}", "priority": "P2",
                    "idea": "distance to a reference point (store, city centre) and coarse grid cell",
                    "code": f'R = 6371.0\nla, lo = np.radians(df["{lat[0]}"]), np.radians(df["{lon[0]}"])\n'
                            f'la0, lo0 = np.radians(40.71), np.radians(-74.01)   # reference point\n'
                            f'df["dist_km"] = 2 * R * np.arcsin(np.sqrt(np.sin((la - la0) / 2) ** 2 + '
                            f'np.cos(la) * np.cos(la0) * np.sin((lo - lo0) / 2) ** 2))'})
    if entity:
        nums = [p["column"] for p in prof if p["role"] in ("amount", "count", "continuous")][:3]
        if time_col:
            code = [f'df = df.sort_values(["{entity}", "{time_col}"])',
                    f'g = df.groupby("{entity}")',
                    f'df["{entity}_n_prior"] = g.cumcount()                          # rows before this one']
            for n in nums:
                code.append(f'df["{entity}_{n}_mean_prior"] = g["{n}"].transform(lambda s: s.shift().expanding().mean())')
            code.append(f't = pd.to_datetime(df["{time_col}"])')
            code.append(f'df["{entity}_secs_since_prev"] = t.groupby(df["{entity}"]).diff().dt.total_seconds()')
            if nums:
                code.append(f'# windowed velocity (needs a DatetimeIndex): rolling("1h") count / sum of {nums[0]} per {entity}')
            out.append({"column": entity, "priority": "P1",
                        "idea": f"point-in-time aggregates per {entity}: prior count, prior means, time since previous "
                                "row (only rows strictly before each row; see time-based-feature-builder)",
                        "code": "\n".join(code)})
        else:
            out.append({"column": entity, "priority": "P2",
                        "idea": f"aggregates per {entity} (count, mean) - only safe if every row is at the same "
                                "prediction time; otherwise give --time-col",
                        "code": f'agg = train.groupby("{entity}")[{nums!r}].agg(["count", "mean"])'})
    return out


def main():
    ap = argparse.ArgumentParser(description="Suggest feature ideas and pandas code for a CSV.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--target")
    ap.add_argument("--entity", help="repeated key for per-entity aggregates (customer_id, card_id)")
    ap.add_argument("--time-col", help="prediction-time / event-time column for point-in-time features")
    ap.add_argument("--sample", type=int, default=20000)
    ap.add_argument("--code", action="store_true", help="print only a pandas script with the P1/P2 ideas")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        header, _, prof = profile(a.csv, a.sample)
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    for col in (a.target, a.entity, a.time_col):
        if col and col not in header:
            print(f"error: column {col!r} not found", file=sys.stderr)
            return 2
    for p in prof:
        if p["column"] == a.target:
            p["role"] = "target"
    leaks = [p["column"] for p in prof if p["role"] != "target" and LEAK_WORDS.search(p["column"])]
    ideas = []
    for p in prof:
        if p["role"] not in ("target", "id", "constant", "entity_key") and p["column"] not in leaks:
            ideas += ideas_for(p, a.time_col)
    ideas += cross_ideas([p for p in prof if p["column"] not in leaks], a.entity, a.time_col)
    ideas.sort(key=lambda i: i["priority"])
    if a.json:
        print(json.dumps({"roles": {p["column"]: p["role"] for p in prof}, "possible_leaks": leaks, "ideas": ideas},
                         indent=2))
        return 0
    if a.code:
        print('"""Feature ideas generated by suggest_features.py - review each block before use.\n\n'
              '`train` is the training split: statistics (quantiles, frequencies, kept levels) must be learned on it\n'
              'and applied to validation/test/production rows, never computed on the full data."""\n'
              'import numpy as np\nimport pandas as pd\n\nREF_YEAR = 2026\n\n\ndef add_features(df, train):\n'
              '    df = df.copy()')
        for i in ideas:
            if i["priority"] in ("P1", "P2"):
                print(f"    # {i['priority']} {i['column']}: {i['idea']}")
                for line in i["code"].splitlines():
                    print(f"    {line}")
        print("    return df")
        return 0
    print("Column roles: " + ", ".join(f"{p['column']}={p['role']}" for p in prof))
    if leaks:
        print(f"\nPOSSIBLE LEAKS (excluded from ideas; check when they are written): {', '.join(leaks)}")
    for prio in ("P1", "P2", "P3"):
        sel = [i for i in ideas if i["priority"] == prio]
        if sel:
            print(f"\n{prio}:")
            for i in sel:
                print(f"  - [{i['column']}] {i['idea']}")
    print("\nRun with --code for a pandas add_features(df, train) function; validate each idea with CV, "
          "keep only those that help on the validation metric.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
