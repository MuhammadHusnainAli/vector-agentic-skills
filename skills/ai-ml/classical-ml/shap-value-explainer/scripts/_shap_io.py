"""Shared loading helpers for the SHAP scripts (stdlib only).

SHAP CSV layout: one column per feature with its SHAP value, plus optional `base_value` (expected value) and
`prediction` (model output in the same space as the SHAP values, e.g. log-odds). The features CSV, when
given, has the same feature columns and the same row order.
"""

import csv
import math
import sys

META = ("base_value", "expected_value", "prediction", "output", "row_id", "id")


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def read_csv(path):
    f = sys.stdin if path == "-" else open(path, newline="", encoding="utf-8")
    with f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError(f"{path}: no rows")
    return rows


def load_shap(path, features_path=None):
    rows = read_csv(path)
    cols = list(rows[0])
    feats = [c for c in cols if c.lower() not in META]
    if not feats:
        raise ValueError("no feature columns in the SHAP file")
    shap = [[num(r[c]) or 0.0 for c in feats] for r in rows]
    base = [num(r.get("base_value", r.get("expected_value"))) for r in rows]
    pred = [num(r.get("prediction", r.get("output"))) for r in rows]
    xs = None
    if features_path:
        xr = read_csv(features_path)
        if len(xr) != len(rows):
            raise ValueError(f"features file has {len(xr)} rows, SHAP file has {len(rows)}: they must align")
        missing = [c for c in feats if c not in xr[0]]
        if missing:
            raise ValueError(f"features file lacks SHAP columns: {', '.join(missing)}")
        xs = [[r[c] for c in feats] for r in xr]
    return feats, shap, base, pred, xs


def sigmoid(z):
    return 1 / (1 + math.exp(-z)) if z >= -700 else 0.0
