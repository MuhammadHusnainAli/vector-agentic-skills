#!/usr/bin/env python3
"""Rank classification algorithms for a dataset and its constraints, with starting settings and cautions.

Traits come from a CSV (--csv data.csv --target y) or flags; constraints always come from flags:
  data       rows, features, share of categorical / high-cardinality columns, missing share,
             minority-class share, number of classes, free-text columns
  needs      --interpretable (coefficients / shape functions a regulator can read),
             --monotone (monotonic constraints), --calibrated (probabilities are used),
             --latency-ms N (per-row budget at serving time), --tiny-model (edge / SQL deploy)

Candidates: logistic regression (L2 / L1), linear SVM, Gaussian/multinomial naive Bayes,
k-nearest neighbours, RBF SVM, decision tree, random forest, extra trees, HistGradientBoosting,
LightGBM, XGBoost, CatBoost, explainable boosting machine (EBM / GAM), MLP.
Each gets a score from fit-to-data rules; the top 3-4 are the bake-off shortlist.

Usage:
    python select_classifier.py --csv data.csv --target churned --drop customer_id
    python select_classifier.py --rows 2000000 --features 300 --cat-share 0.4 --minority 0.002 --latency-ms 5
    python select_classifier.py --csv data.csv --target y --interpretable --monotone --json

Exit codes: 0 ranking printed, 2 usage or read error.
"""

import argparse
import csv
import json
import math
import sys
from collections import Counter

MISSING = {"", "na", "n/a", "nan", "null", "none", "?"}


def traits_from_csv(path, target, drop):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames or []
        rows = list(reader)
    if target not in header:
        raise ValueError(f"target {target!r} not found")
    feats = [c for c in header if c != target and c not in drop]
    cat = hc = text = 0
    miss = 0
    for c in feats:
        vals = [(r.get(c) or "").strip() for r in rows]
        present = [v for v in vals if v.lower() not in MISSING]
        miss += len(vals) - len(present)
        nums = 0
        for v in present:
            try:
                float(v)
                nums += 1
            except ValueError:
                pass
        if present and nums / len(present) < 0.95:
            k = len(set(present))
            mean_len = sum(len(v) for v in present) / len(present)
            if mean_len > 30 and k > 0.5 * len(present):
                text += 1
            elif k > 50:
                hc += 1
                cat += 1
            else:
                cat += 1
    y = Counter((r.get(target) or "").strip() for r in rows if (r.get(target) or "").strip())
    n = sum(y.values())
    return {"rows": len(rows), "features": len(feats), "cat_share": cat / max(1, len(feats)),
            "hc_share": hc / max(1, len(feats)), "missing_share": miss / max(1, len(rows) * len(feats)),
            "minority": min(y.values()) / n if n else 0.5, "classes": len(y), "text_cols": text}


def score_models(t, need):
    n, p = t["rows"], t["features"]
    small, big = n < 2_000, n > 1_000_000
    wide = p > 0.5 * n or p > 5_000
    cats, hc, miss = t["cat_share"], t["hc_share"], t["missing_share"]
    rare = t["minority"] < 0.05
    out = []

    def add(name, score, why, start, caution):
        out.append({"model": name, "score": round(score, 1), "why": why, "start": start, "caution": caution})

    s = 6 + (2 if small else 0) + (2 if wide else 0) + (3 if need["interpretable"] else 0) + (1 if need["calibrated"] else 0) \
        + (2 if need["tiny_model"] else 0) + (1 if need["latency_ms"] and need["latency_ms"] < 1 else 0) - (1 if big and not wide else 0)
    add("Logistic regression (L2)", s, "strong, fast, calibrated-ish baseline; coefficients are explainable; handles wide sparse data",
        "LogisticRegression(C=1.0, max_iter=5000) on scaled numerics + one-hot; tune C on a log grid",
        "needs scaling, explicit interactions/splines for non-linear effects; class_weight distorts probabilities")
    add("Logistic regression (L1 / elastic net)", s - 0.5 + (1.5 if wide else 0),
        "sparse, self-selecting model for many features", "LogisticRegression(penalty='elasticnet', solver='saga', l1_ratio=0.5, C=0.1)",
        "unstable choice among correlated features; slower solver")
    gb = 8 + (1 if cats > 0.2 else 0) + (1 if miss > 0.05 else 0) - (3 if small else 0) - (2 if wide else 0) \
        - (2 if need["interpretable"] else 0) + (0.5 if need["monotone"] else 0)
    add("HistGradientBoosting (scikit-learn)", gb, "best default for tabular data in pure scikit-learn; native NaN and categoricals",
        "HistGradientBoostingClassifier(learning_rate=0.05, max_leaf_nodes=31, early_stopping=True)",
        "categoricals < 256 levels; monotonic_cst for constraints; tune min_samples_leaf for small data")
    add("LightGBM", gb + (1 if big else 0) + (0.5 if cats > 0.2 else 0),
        "fastest GBM at scale; native categoricals; strong accuracy", "LGBMClassifier(n_estimators=5000, learning_rate=0.03, num_leaves=31, "
        "min_child_samples=50, subsample=0.8, subsample_freq=1, colsample_bytree=0.8) + early stopping",
        "overfits small data (raise min_child_samples); see xgboost-lightgbm-tuner")
    add("XGBoost", gb + (0.5 if big else 0), "robust GBM, excellent with tuned regularisation; GPU support",
        "XGBClassifier(tree_method='hist', n_estimators=5000, learning_rate=0.03, max_depth=6, min_child_weight=5, "
        "subsample=0.8, colsample_bytree=0.8, early_stopping_rounds=200)", "enable_categorical needs pandas category dtype")
    add("CatBoost", gb + (2 if cats > 0.3 else 0) + (1.5 if hc > 0.05 else 0) + (0.5 if small else 0),
        "strongest out of the box with many / high-cardinality categoricals; ordered boosting resists overfitting",
        "CatBoostClassifier(iterations=5000, learning_rate=0.05, depth=6, od_type='Iter', od_wait=200, cat_features=[...])",
        "slower training than LightGBM; see catboost-model-builder")
    rf = 7 - (1 if big else 0) + (1 if small else 0) - (2 if need["calibrated"] else 0) - (1 if need["latency_ms"] and need["latency_ms"] < 2 else 0)
    add("Random forest", rf, "hard to break, little tuning, good for small/medium data and as a sanity check",
        "RandomForestClassifier(n_estimators=500, max_features='sqrt', min_samples_leaf=5, n_jobs=-1)",
        "probabilities are poorly calibrated; large models; usually below a tuned GBM")
    add("Extra trees", rf - 0.5, "faster, more randomised forest; good with noisy features",
        "ExtraTreesClassifier(n_estimators=500, min_samples_leaf=3, n_jobs=-1)", "same calibration caveats as RF")
    if need["interpretable"] or need["monotone"]:
        add("Explainable boosting machine (EBM / GAM)", 9 + (1 if need["monotone"] else 0) - (2 if big else 0),
            "glass-box: one shape function per feature (+ few pairwise interactions); near-GBM accuracy on many tabular tasks",
            "interpret.glassbox.ExplainableBoostingClassifier(interactions=10)",
            "slower to train; shape functions need review for monotonicity (or constrain)")
        add("Points scorecard (binned logistic regression)", 7 + (2 if need["tiny_model"] else 0),
            "regulated credit-style decisions: integer points per bin, monotone by construction",
            "KBinsDiscretizer or WoE binning -> LogisticRegression; scale to points", "coarser; binning choices matter")
    add("Decision tree (shallow)", 4 + (3 if need["tiny_model"] else 0) + (1 if need["interpretable"] else 0),
        "a readable rule set; deployable as SQL", "DecisionTreeClassifier(max_depth=4, min_samples_leaf=50)",
        "usually much weaker than ensembles; unstable")
    if t["text_cols"]:
        add("Linear model on TF-IDF (logistic / linear SVM)", 10.5, "text columns: sparse linear models are the strong, fast baseline",
            "TfidfVectorizer(ngram_range=(1,2), min_df=3) -> LogisticRegression(C=4) or LinearSVC", "sentence embeddings + GBM for semantic tasks")
        add("Multinomial naive Bayes", 5 + (2 if small else 0), "very fast text baseline", "MultinomialNB(alpha=0.5) on counts / TF-IDF",
            "probabilities are overconfident")
    add("k-nearest neighbours", 3 + (2 if small and not wide else 0) - (3 if big else 0) - (2 if need["latency_ms"] and need["latency_ms"] < 10 else 0),
        "local similarity, no training", "KNeighborsClassifier(n_neighbors=25, weights='distance') after scaling",
        "slow at prediction time, degrades with many features, needs scaling")
    add("SVM (RBF kernel)", 5 + (2 if small and not wide else 0) - (5 if n > 50_000 else 0),
        "strong on small, dense, well-scaled data", "SVC(C=1, gamma='scale', probability=False) on scaled features",
        "O(n^2) training; probability=True is slow and needs calibration")
    add("MLP (neural net)", 4 + (1 if big else 0) - (2 if small else 0) - (1 if need["interpretable"] else 0),
        "useful mainly with very large data or embeddings", "MLPClassifier(hidden_layer_sizes=(128, 64), early_stopping=True)",
        "rarely beats GBMs on tabular data; needs scaling and tuning")
    if rare:
        for m in out:
            if "Logistic" in m["model"] or "Boost" in m["model"] or m["model"] in ("LightGBM", "XGBoost", "CatBoost"):
                m["caution"] += "; rare positives: evaluate with PR-AUC, keep the natural test prevalence (imbalanced-class-handler)"
    if need["latency_ms"] is not None and need["latency_ms"] < 1:
        for m in out:
            if m["model"] in ("LightGBM", "XGBoost", "CatBoost", "Random forest", "Extra trees", "HistGradientBoosting (scikit-learn)"):
                m["score"] -= 1.5
                m["caution"] += "; sub-millisecond budget: cap trees/depth or compile (treelite, ONNX)"
    return sorted(out, key=lambda m: -m["score"])


def main():
    ap = argparse.ArgumentParser(description="Rank classifiers for a dataset and constraints.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv")
    ap.add_argument("--target")
    ap.add_argument("--drop", nargs="*", default=[])
    ap.add_argument("--rows", type=int)
    ap.add_argument("--features", type=int)
    ap.add_argument("--cat-share", type=float, default=0.0)
    ap.add_argument("--hc-share", type=float, default=0.0)
    ap.add_argument("--missing-share", type=float, default=0.0)
    ap.add_argument("--minority", type=float, default=0.5)
    ap.add_argument("--text-cols", type=int, default=0)
    ap.add_argument("--interpretable", action="store_true")
    ap.add_argument("--monotone", action="store_true")
    ap.add_argument("--calibrated", action="store_true")
    ap.add_argument("--latency-ms", type=float)
    ap.add_argument("--tiny-model", action="store_true")
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        if a.csv:
            if not a.target:
                raise ValueError("--csv needs --target")
            t = traits_from_csv(a.csv, a.target, set(a.drop))
        elif a.rows and a.features:
            t = {"rows": a.rows, "features": a.features, "cat_share": a.cat_share, "hc_share": a.hc_share,
                 "missing_share": a.missing_share, "minority": a.minority, "classes": 2, "text_cols": a.text_cols}
        else:
            raise ValueError("give --csv/--target or --rows and --features")
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    need = {"interpretable": a.interpretable, "monotone": a.monotone, "calibrated": a.calibrated,
            "latency_ms": a.latency_ms, "tiny_model": a.tiny_model}
    ranked = score_models(t, need)[:a.top]
    if a.json:
        print(json.dumps({"traits": t, "needs": need, "ranking": ranked}, indent=2))
        return 0
    print(f"Data: {t['rows']:,} rows, {t['features']} features, categorical {t['cat_share']:.0%} "
          f"(high-cardinality {t['hc_share']:.0%}), missing {t['missing_share']:.1%}, minority {t['minority']:.1%}, "
          f"text columns {t['text_cols']}")
    print("Needs: " + (", ".join(k for k, v in need.items() if v) or "none"))
    for i, m in enumerate(ranked, 1):
        print(f"\n{i}. {m['model']}  (score {m['score']})\n   why:     {m['why']}\n   start:   {m['start']}\n"
              f"   caution: {m['caution']}")
    print("\nShortlist the top 3-4 plus a logistic-regression baseline; compare them on identical CV folds "
          "(python scripts/bakeoff_scaffold.py) before choosing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
