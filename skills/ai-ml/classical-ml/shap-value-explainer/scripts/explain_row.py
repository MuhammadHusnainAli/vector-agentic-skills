#!/usr/bin/env python3
"""Explain one prediction from its SHAP values: a text waterfall and a plain-language summary.

Inputs: a SHAP CSV (feature columns + base_value [+ prediction]) and optionally the aligned feature values.
Pick the row with --row (0-based), or --select highest|lowest to explain the most extreme prediction.

Output:
  waterfall   base value, the --top contributions ordered by |SHAP| with the feature value, the sum of the
              remaining features, and the prediction; with --link logit the log-odds are also shown as
              probabilities (the cumulative probability column depends on the order: log-odds add up,
              probabilities do not)
  summary     two or three sentences for a non-technical reader: prediction vs average, the strongest pushes
              up and down
  check       base + sum(SHAP) = prediction for this row (exit 1 if not)

Usage:
    python explain_row.py shap_values.csv --features shap_features.csv --row 17 --link logit
    python explain_row.py shap_values.csv --features x.csv --select highest --top 5 --label "churn probability"
    python explain_row.py shap_values.csv --row 0 --json

Exit codes: 0 explained, 1 additivity mismatch for the row, 2 usage or read error.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shap_io import load_shap, sigmoid  # noqa: E402


def explain(feats, shap, base, pred, xs, row, top, link):
    sv = shap[row]
    b = base[row] if base[row] is not None else 0.0
    total = b + sum(sv)
    p = pred[row] if pred[row] is not None else total
    order = sorted(range(len(feats)), key=lambda j: -abs(sv[j]))
    items = [{"feature": feats[j], "value": xs[row][j] if xs else None, "shap": sv[j]} for j in order[:top]]
    rest = order[top:]
    res = {"row": row, "base_value": b, "prediction": p, "sum_check": total, "items": items,
           "other_count": len(rest), "other_sum": sum(sv[j] for j in rest), "link": link,
           "additive": abs(total - p) <= 1e-3 * max(1.0, abs(p))}
    if link == "logit":
        res["base_prob"], res["pred_prob"] = sigmoid(b), sigmoid(p)
    return res


def show(v):
    if v is None:
        return ""
    try:
        f = float(v)
        return f"{int(f)}" if f.is_integer() else f"{f:.4g}"
    except ValueError:
        return str(v) if v != "" else "missing"


def fmt(x):
    return f"{x:+.4g}"


def report(r, label):
    logit = r["link"] == "logit"
    lines = [f"row {r['row']}", ""]
    hdr = f"{'':<34} {'SHAP':>9} {'cumulative':>11}" + (f" {'prob':>7}" if logit else "")
    lines.append(hdr)
    cum = r["base_value"]
    lines.append(f"{'base value (average log-odds)' if logit else 'base value (average output)':<34} {'':>9} {cum:>11.4g}" + (f" {sigmoid(cum):>7.1%}" if logit else ""))
    for it in r["items"]:
        cum += it["shap"]
        name = it["feature"] + (f" = {show(it['value'])}" if it["value"] is not None else "")
        lines.append(f"{name[:34]:<34} {fmt(it['shap']):>9} {cum:>11.4g}" + (f" {sigmoid(cum):>7.1%}" if logit else ""))
    if r["other_count"]:
        cum += r["other_sum"]
        other = f"{r['other_count']} other features"
        lines.append(f"{other:<34} {fmt(r['other_sum']):>9} {cum:>11.4g}"
                     + (f" {sigmoid(cum):>7.1%}" if logit else ""))
    lines.append(f"{'prediction':<34} {'':>9} {r['prediction']:>11.4g}" + (f" {sigmoid(r['prediction']):>7.1%}" if logit else ""))
    lines.append("")
    if not r["additive"]:
        lines.append(f"CHECK FAILED: base + sum(SHAP) = {r['sum_check']:.6g} but prediction = {r['prediction']:.6g}")
    else:
        lines.append("check: base + sum(SHAP) = prediction")
    lines.append("")
    if logit:
        head = (f"Predicted {label or 'probability'}: {r['pred_prob']:.1%} for this case, against a baseline of "
                f"{r['base_prob']:.1%} (the average log-odds converted to a probability).")
    else:
        head = (f"Predicted {label or 'value'}: {r['prediction']:.4g} for this case, against an average of "
                f"{r['base_value']:.4g}.")
    ups = [it for it in r["items"] if it["shap"] > 0][:3]
    downs = [it for it in r["items"] if it["shap"] < 0][:3]
    unit = " log-odds" if logit else ""
    def phrase(its):
        return ", ".join((f"{it['feature']} = {show(it['value'])}" if it["value"] is not None else it["feature"])
                         + f" ({fmt(it['shap'])}{unit})" for it in its)
    lines.append(head)
    if ups:
        lines.append(f"Pushing it up: {phrase(ups)}.")
    if downs:
        lines.append(f"Pushing it down: {phrase(downs)}.")
    lines.append("These are contributions to this model's output relative to the average case, not causes.")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Explain one prediction from SHAP values.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("shap_csv")
    ap.add_argument("--features")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--row", type=int)
    g.add_argument("--select", choices=["highest", "lowest"])
    ap.add_argument("--top", type=int, default=6)
    ap.add_argument("--link", choices=["identity", "logit"], default="identity",
                    help="logit: SHAP values are log-odds; also show probabilities")
    ap.add_argument("--label", help="what the output means, e.g. 'churn probability'")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        feats, shap, base, pred, xs = load_shap(a.shap_csv, a.features)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    n = len(shap)
    if a.select:
        outs = [(pred[i] if pred[i] is not None else (base[i] or 0.0) + sum(shap[i])) for i in range(n)]
        row = max(range(n), key=outs.__getitem__) if a.select == "highest" else min(range(n), key=outs.__getitem__)
    else:
        row = a.row if a.row is not None else 0
    if not 0 <= row < n:
        print(f"error: --row {row} out of range (0..{n - 1})", file=sys.stderr)
        return 2
    r = explain(feats, shap, base, pred, xs, row, a.top, a.link)
    print(json.dumps(r, indent=2) if a.json else report(r, a.label))
    return 0 if r["additive"] else 1


if __name__ == "__main__":
    sys.exit(main())
