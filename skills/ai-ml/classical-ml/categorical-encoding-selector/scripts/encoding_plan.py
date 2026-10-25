#!/usr/bin/env python3
"""Choose an encoder for every categorical column and emit the scikit-learn ColumnTransformer.

For each non-numeric column (and numeric-looking codes such as zip) it measures:
  cardinality, rows per level, rare-level share (< --min-count rows), the share of holdout
  rows whose level never appears in training ("unseen rate", split by --time-col if given),
  an ordinal hint (low/medium/high, S/M/L, grade letters, ordered numbers), and how much the
  target varies across levels (out-of-fold).
Then recommends per --model:
  linear | knn | nn   one-hot (<= 15 levels), one-hot with infrequent grouping (<= 100),
                      target encoding (cross-fitted) or hashing above that; ordinal for ordered
  tree               ordinal codes for low cardinality; target/frequency encoding for high
  gbm                native categorical support (LightGBM / HistGradientBoosting) up to ~255 levels,
                      target encoding beyond
  catboost           pass as cat_features (ordered target statistics), always

Usage:
    python encoding_plan.py data.csv --target churned --model linear
    python encoding_plan.py data.csv --target is_fraud --model gbm --time-col timestamp --drop txn_id
    python encoding_plan.py data.csv --target price --model linear --code > prep.py

Exit codes: 0 plan printed, 2 usage or read error.
"""

import argparse
import csv
import json
import math
import re
import sys
import zlib
from collections import Counter, defaultdict

MISSING = {"", "na", "n/a", "nan", "null", "none", "?"}
ORDINAL_SETS = [
    ["very low", "low", "medium", "high", "very high"], ["low", "medium", "high"], ["low", "mid", "high"],
    ["xs", "s", "m", "l", "xl", "xxl"], ["small", "medium", "large"], ["basic", "standard", "premium"],
    ["bronze", "silver", "gold", "platinum"], ["a", "b", "c", "d", "e", "f"], ["never", "rarely", "sometimes", "often", "always"],
    ["strongly disagree", "disagree", "neutral", "agree", "strongly agree"], ["poor", "fair", "good", "very good", "excellent"],
]
DATE_RE = re.compile(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}")
CODE_NAMES = re.compile(r"(zip|postcode|postal|area_code|naics|sic|icd|fips|_code$|^code$)", re.I)


def num(v):
    try:
        return math.isfinite(float(v))
    except ValueError:
        return False


def ordinal_order(levels):
    low = {l.lower() for l in levels}
    for seq in ORDINAL_SETS:
        if low <= set(seq) and len(low) >= 2:
            return [l for s in seq for l in levels if l.lower() == s]
    return None


def target_spread(vals, ys, prior):
    """Out-of-fold: weighted std of smoothed level means, relative to the target's std."""
    folds = [zlib.crc32(str(i).encode()) % 2 for i in range(len(vals))]
    enc = []
    for f in (0, 1):
        st = defaultdict(lambda: [0.0, 0])
        for v, y, k in zip(vals, ys, folds):
            if k != f:
                st[v][0] += y
                st[v][1] += 1
        for v, y, k in zip(vals, ys, folds):
            if k == f:
                s, n = st.get(v, (0.0, 0))
                enc.append(((s + 20 * prior) / (n + 20), y))
    m = sum(e for e, _ in enc) / len(enc)
    sd_e = math.sqrt(sum((e - m) ** 2 for e, _ in enc) / len(enc))
    my = sum(y for _, y in enc) / len(enc)
    sd_y = math.sqrt(sum((y - my) ** 2 for _, y in enc) / len(enc)) or 1.0
    return sd_e / sd_y


def recommend(info, model):
    k, order = info["levels"], info["ordinal"]
    if model == "catboost":
        return "catboost_native", "pass in cat_features; CatBoost's ordered target statistics avoid leakage"
    if order and model in ("linear", "knn", "nn", "tree"):
        return "ordinal", f"ordered levels {order}: OrdinalEncoder(categories=[...]) keeps the order in one column"
    if model == "gbm":
        if k <= 255:
            return "native", "LightGBM categorical_feature / HistGradientBoosting categorical_features (< 256 levels)"
        return "target", "too many levels for native handling: cross-fitted TargetEncoder (or frequency encoding)"
    if model == "tree":
        if k <= 30:
            return "ordinal", "trees split on arbitrary integer codes well enough at low cardinality"
        return "target", "high cardinality: cross-fitted TargetEncoder or frequency encoding"
    # linear, knn, nn
    if k <= 15 and info["rare_share"] < 0.05:
        return "onehot", "few levels: one-hot is exact and interpretable"
    if k <= 100:
        return "onehot_infrequent", "group rare levels (min_frequency) then one-hot"
    if info["unseen_rate"] > 0.2:
        return "hashing", "many unseen levels at prediction time: hashing or frequency encoding degrade gracefully"
    return "target", "high cardinality: cross-fitted TargetEncoder (one column per class) plus a frequency feature"


def analyse(rows, header, target, drop, time_col, min_count):
    if time_col:
        rows = sorted(rows, key=lambda r: r.get(time_col, ""))
        split = "time"
    else:
        rows = [r for _, r in sorted((zlib.crc32(str(i).encode()), r) for i, r in enumerate(rows))]
        split = "hash"
    cut = int(len(rows) * 0.8)
    tvals = [(r.get(target) or "").strip() for r in rows] if target else []
    ys = None
    if target:
        classes = Counter(v for v in tvals if v.lower() not in MISSING)
        if len(classes) == 2:
            pos = min(classes, key=classes.get)
            ys = [1.0 if v == pos else 0.0 for v in tvals]
        elif all(num(v) for v in classes):
            ys = [float(v) if num(v) else 0.0 for v in tvals]
    out = []
    for c in header:
        if c in (target, time_col) or c in drop:
            continue
        vals = [(r.get(c) or "").strip() for r in rows]
        present = [v for v in vals if v.lower() not in MISSING]
        if not present:
            continue
        is_code = CODE_NAMES.search(c) and all(num(v) for v in present)
        if all(num(v) for v in present) and not is_code:
            continue
        if sum(bool(DATE_RE.match(v)) for v in present) / len(present) > 0.9:
            out.append({"column": c, "levels": len(set(present)), "encoder": "skip",
                        "why": "datetime: build date features (feature-engineering-idea-generator), do not encode"})
            continue
        counts = Counter(present)
        k = len(counts)
        if k > 0.9 * len(present) and len(present) > 50:
            if is_code:
                out.append({"column": c, "levels": k, "encoder": "prefix",
                            "why": "near-unique code: encode a prefix level instead (zip3 / NAICS-2), then re-run"})
            else:
                out.append({"column": c, "levels": k, "encoder": "drop", "why": "near-unique: an ID, not a category"})
            continue
        train_levels = set(v for v in vals[:cut] if v.lower() not in MISSING)
        hold = [v for v in vals[cut:] if v.lower() not in MISSING]
        info = {"column": c, "levels": k, "rows_per_level": round(len(present) / k, 1),
                "missing": round(1 - len(present) / len(vals), 4),
                "rare_share": round(sum(n for n in counts.values() if n < min_count) / len(present), 4),
                "rare_levels": sum(1 for n in counts.values() if n < min_count),
                "unseen_rate": round(sum(v not in train_levels for v in hold) / len(hold), 4) if hold else 0.0,
                "ordinal": ordinal_order(list(counts)) if k <= 12 else None, "code": bool(is_code)}
        if ys is not None:
            info["target_signal"] = round(target_spread(vals, ys, sum(ys) / len(ys)), 4)
        out.append(info)
    return out, split


def code_for(plan, model):
    groups = defaultdict(list)
    for p in plan:
        if p["encoder"] not in ("drop", "skip", "prefix"):
            groups[p["encoder"]].append(p)
    lines = ["from sklearn.compose import ColumnTransformer",
             "from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, TargetEncoder, FunctionTransformer",
             "from sklearn.feature_extraction import FeatureHasher",
             "from sklearn.pipeline import make_pipeline", ""]
    if groups.get("hashing"):
        lines += ["", "def as_string_lists(X):", "    return X.astype(str).values.tolist()   # named, so the pipeline pickles", ""]
    lines.append("categorical_steps = [")
    if groups.get("onehot"):
        lines.append(f'    ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False), '
                     f'{[p["column"] for p in groups["onehot"]]!r}),')
    if groups.get("onehot_infrequent"):
        lines.append(f'    ("onehot_rare", OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=20, '
                     f'sparse_output=False), {[p["column"] for p in groups["onehot_infrequent"]]!r}),')
    for p in groups.get("ordinal", []):
        cats = f"categories=[{p['ordinal']!r}], " if p.get("ordinal") else ""
        lines.append(f'    ("ord_{p["column"]}", OrdinalEncoder({cats}handle_unknown="use_encoded_value", unknown_value=-1, '
                     f'encoded_missing_value=-1), [{p["column"]!r}]),')
    if groups.get("target"):
        lines.append(f'    ("target", TargetEncoder(cv=5, smooth="auto"), '
                     f'{[p["column"] for p in groups["target"]]!r}),   # cross-fitted inside fit_transform')
    if groups.get("hashing"):
        for p in groups["hashing"]:
            lines.append(f'    ("hash_{p["column"]}", make_pipeline(FunctionTransformer(as_string_lists), '
                         f'FeatureHasher(n_features=256, input_type="string")), [{p["column"]!r}]),')
    native = [p["column"] for p in groups.get("native", []) + groups.get("catboost_native", [])]
    lines.append("]")
    if native:
        lines += ["", f"NATIVE_CATEGORICAL = {native!r}",
                  "# GBM/CatBoost: cast to 'category' (LightGBM, HistGradientBoosting with categorical_features="
                  "'from_dtype') or pass cat_features=NATIVE_CATEGORICAL (CatBoost); no encoder needed."]
    lines += ["", "prep = ColumnTransformer(categorical_steps, remainder=\"passthrough\")",
              "# Use inside a Pipeline so every encoder is fitted on training folds only."]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Recommend categorical encoders per column.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--target")
    ap.add_argument("--model", choices=["linear", "knn", "nn", "tree", "gbm", "catboost"], default="linear")
    ap.add_argument("--time-col", help="measure unseen levels on the latest 20%% of rows by this column")
    ap.add_argument("--drop", nargs="*", default=[])
    ap.add_argument("--min-count", type=int, default=20, help="levels with fewer rows count as rare (default 20)")
    ap.add_argument("--code", action="store_true", help="print only the ColumnTransformer code")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        with (sys.stdin if a.csv == "-" else open(a.csv, newline="", encoding="utf-8-sig")) as fh:
            reader = csv.DictReader(fh)
            header = reader.fieldnames or []
            rows = list(reader)
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    for col in (a.target, a.time_col):
        if col and col not in header:
            print(f"error: column {col!r} not found", file=sys.stderr)
            return 2
    plan, split = analyse(rows, header, a.target, set(a.drop), a.time_col, a.min_count)
    for p in plan:
        if "encoder" not in p:
            p["encoder"], p["why"] = recommend(p, a.model)
    if a.code:
        print(code_for(plan, a.model))
        return 0
    if a.json:
        print(json.dumps({"model": a.model, "unseen_split": split, "columns": plan}, indent=2))
        return 0
    print(f"Encoding plan for model family '{a.model}' ({len(plan)} categorical column(s); unseen rate measured on "
          f"the {'latest' if split == 'time' else 'hashed'} 20% of rows)")
    print(f"{'column':<22} {'levels':>6} {'rare%':>6} {'unseen%':>8} {'signal':>7}  encoder")
    for p in plan:
        if p["encoder"] in ("drop", "skip", "prefix"):
            print(f"{p['column']:<22} {p['levels']:>6} {'':>6} {'':>8} {'':>7}  {p['encoder']:<18} {p['why']}")
            continue
        sig = f"{p['target_signal']:.3f}" if "target_signal" in p else "-"
        print(f"{p['column']:<22} {p['levels']:>6} {p['rare_share']:>6.1%} {p['unseen_rate']:>8.1%} {sig:>7}  "
              f"{p['encoder']:<18} {p['why']}")
        if p["unseen_rate"] > 0.05:
            print(f"{'':<22} note: {p['unseen_rate']:.0%} of recent rows have levels unseen in training; the encoder "
                  "must handle unknowns (handle_unknown, smoothing to the prior)")
        if p["code"]:
            print(f"{'':<22} note: numeric-looking code; never feed it as a number. Consider prefix levels (zip3).")
    print("\nRun with --code for the ColumnTransformer. Fit encoders inside a Pipeline (train folds only).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
