#!/usr/bin/env python3
"""Write a model card (Markdown) from a JSON spec, with slice metrics from slice_metrics.py.

The card follows Mitchell et al. (2019) "Model Cards for Model Reporting" and the Hugging Face model card
layout: YAML metadata, model details, intended use and out-of-scope use, data, evaluation (overall metrics
with CIs, baseline, threshold, per-slice table), fairness, explainability, limitations, ethical
considerations, risks and mitigations, monitoring and maintenance, caveats, and how to cite.

Spec keys (all optional except name; see references/card-spec.md for the full schema):
  name, version, date, owners [{name, contact}], model_type, task, framework, license, description,
  intended_use {primary_uses [], primary_users [], out_of_scope []},
  training_data / evaluation_data {source, period, rows, label_definition, preprocessing, known_gaps},
  metrics [{name, value, ci [lo, hi], split}], threshold {value, rationale}, baseline {name, metrics {}},
  fairness {attributes [], assessment}, explainability, limitations [], ethical_considerations [],
  risks [{risk, mitigation}], monitoring {metrics [], drift, retraining, owner}, caveats [], citation
Required sections that are missing are written as "**TODO:** ..." so the gap is visible; --strict exits 1
when any TODO remains.

Usage:
    python model_card.py spec.json -o MODEL_CARD.md
    python model_card.py spec.json --slices slices.json -o MODEL_CARD.md --strict

Exit codes: 0 written, 1 TODOs remain with --strict, 2 usage or read error.
"""

import argparse
import json
import sys

REQUIRED = {
    "description": "one paragraph: what the model predicts, for whom, and how it is used",
    "owners": "owner team and contact",
    "intended_use.primary_uses": "the decisions or workflows this model supports",
    "intended_use.out_of_scope": "uses the model must not be used for",
    "training_data": "source, period, size and label definition of the training data",
    "evaluation_data": "source, period and size of the evaluation data (held out from training)",
    "metrics": "overall metrics on the evaluation data, with confidence intervals",
    "limitations": "known failure modes and conditions where the model is unreliable",
    "ethical_considerations": "affected groups, sensitive features and proxies, potential harms",
    "monitoring": "what is monitored after deployment, retraining trigger and owner",
}


def get(spec, path):
    cur = spec
    for k in path.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur if cur not in ("", [], {}) else None


def todo(key):
    return f"**TODO:** {REQUIRED[key]}."


def bullets(items):
    return "\n".join(f"- {x}" for x in items)


def data_block(d):
    if isinstance(d, str):
        return d
    labels = [("source", "Source"), ("period", "Period"), ("rows", "Rows"), ("label_definition", "Label definition"),
              ("preprocessing", "Preprocessing"), ("known_gaps", "Known gaps")]
    out = [f"- **{lab}:** {d[k]}" for k, lab in labels if d.get(k) not in (None, "", [])]
    return "\n".join(out) if out else ""


def fmt_val(v):
    return f"{v:.3f}" if isinstance(v, float) else str(v)


def slice_table(sl):
    thr = sl.get("threshold")
    lines = []
    if thr is not None:
        lines.append(f"Decision threshold for rate metrics: {thr}.\n")
    reg = "mae" in sl["overall"]
    if reg:
        lines += ["| Slice | n | MAE [95% CI] | RMSE | Bias |", "|---|---|---|---|---|"]
    else:
        lines += ["| Slice | n | Positives | ROC AUC [95% CI] | TPR [95% CI] | FPR | Positive rate |",
                  "|---|---|---|---|---|---|---|"]

    def row(name, m):
        def c(key):
            v = m.get(key)
            ci = m.get(key + "_ci")
            s = "n/a" if v is None else f"{v:.3f}"
            return s + (f" [{ci[0]:.3f}, {ci[1]:.3f}]" if ci else "")
        flag = " (low n)" if m.get("low_n") else ""
        if reg:
            return f"| {name}{flag} | {m['n']} | {c('mae')} | {c('rmse')} | {c('bias')} |"
        return (f"| {name}{flag} | {m['n']} | {m['positives']} | {c('auc')} | {c('tpr')} | {c('fpr')} | "
                f"{c('positive_rate')} |")

    lines.append(row("**Overall**", sl["overall"]))
    for col, d in sl.get("slices", {}).items():
        for lv, m in d["levels"].items():
            lines.append(row(f"{col} = {lv}", m))
    gaps = []
    for col, d in sl.get("slices", {}).items():
        if d.get("gaps"):
            gaps.append(f"- **{col}:** " + ", ".join(f"{k.replace('_', ' ')} {v:.3f}" for k, v in d["gaps"].items()))
    if gaps:
        lines += ["", "Gaps between slices (max - min; positive rate ratio = min / max):", *gaps]
    flags = [f for f in sl.get("flags", []) if f.get("flag") != "LOW-N"]
    if flags:
        lines += ["", "Findings:"] + [f"- {f['flag']}: {f['detail']}" + (f" ({f['column']} = {f['level']})"
                                                                         if f["flag"] == "UNDERPERFORMS" else "")
                                      for f in flags]
    return "\n".join(lines)


def build(spec, slices):
    todos = []

    def need(key, content):
        if content:
            return content
        todos.append(key)
        return todo(key)

    name = spec["name"]
    meta = ["---"]
    for k in ("license", "framework", "task"):
        if spec.get(k):
            meta.append(f"{k}: {spec[k]}")
    meta.append(f"model_name: {name}")
    if spec.get("version"):
        meta.append(f"version: {spec['version']}")
    meta.append("---")
    out = meta + ["", f"# Model Card: {name}", ""]
    details = [f"- **Version:** {spec.get('version', 'unversioned')}", f"- **Date:** {spec.get('date', 'undated')}"]
    for k, lab in (("model_type", "Model type"), ("task", "Task"), ("framework", "Framework"), ("license", "License")):
        if spec.get(k):
            details.append(f"- **{lab}:** {spec[k]}")
    owners = get(spec, "owners")
    details.append("- **Owners:** " + (", ".join(f"{o.get('name')} ({o.get('contact')})" if isinstance(o, dict) else str(o)
                                                 for o in owners) if owners else todo("owners")))
    if not owners:
        todos.append("owners")
    out += ["## Model Details", "", need("description", spec.get("description")), "", *details, ""]

    iu = spec.get("intended_use", {})
    out += ["## Intended Use", "", "### Primary uses", "",
            need("intended_use.primary_uses", bullets(iu["primary_uses"]) if iu.get("primary_uses") else None), ""]
    if iu.get("primary_users"):
        out += ["### Primary users", "", bullets(iu["primary_users"]), ""]
    out += ["### Out-of-scope uses", "",
            need("intended_use.out_of_scope", bullets(iu["out_of_scope"]) if iu.get("out_of_scope") else None), ""]

    out += ["## Data", "", "### Training data", "",
            need("training_data", data_block(spec["training_data"]) if spec.get("training_data") else None), "",
            "### Evaluation data", "",
            need("evaluation_data", data_block(spec["evaluation_data"]) if spec.get("evaluation_data") else None), ""]

    out += ["## Evaluation", "", "### Overall metrics", ""]
    ms = spec.get("metrics")
    if ms:
        out += ["| Metric | Value | 95% CI | Data |", "|---|---|---|---|"]
        for m in ms:
            ci = m.get("ci")
            out.append(f"| {m['name']} | {fmt_val(m['value'])} | "
                       f"{f'{ci[0]:.3f} - {ci[1]:.3f}' if ci else 'not reported'} | {m.get('split', 'evaluation')} |")
    else:
        todos.append("metrics")
        out.append(todo("metrics"))
    out.append("")
    if spec.get("baseline"):
        b = spec["baseline"]
        out += [f"**Baseline ({b.get('name', 'baseline')}):** "
                + ", ".join(f"{k} {fmt_val(v)}" for k, v in b.get("metrics", {}).items()), ""]
    if spec.get("threshold"):
        t = spec["threshold"]
        out += [f"**Decision threshold:** {t.get('value')}" + (f" - {t['rationale']}" if t.get("rationale") else ""), ""]
    out += ["### Performance across groups", ""]
    if slices:
        out += [slice_table(slices), ""]
    else:
        out += ["Not evaluated. Run slice_metrics.py on the evaluation predictions for the relevant groups.", ""]

    fair = spec.get("fairness")
    out += ["## Fairness", ""]
    if fair:
        if fair.get("attributes"):
            out.append("- **Attributes assessed:** " + ", ".join(fair["attributes"]))
        if fair.get("assessment"):
            out.append(f"- **Assessment:** {fair['assessment']}")
    else:
        out.append("No fairness assessment recorded.")
    out.append("")
    if spec.get("explainability"):
        out += ["## Explainability", "", spec["explainability"], ""]
    out += ["## Limitations", "", need("limitations", bullets(spec["limitations"]) if spec.get("limitations") else None), "",
            "## Ethical Considerations", "",
            need("ethical_considerations", bullets(spec["ethical_considerations"])
                 if spec.get("ethical_considerations") else None), ""]
    if spec.get("risks"):
        out += ["## Risks and Mitigations", "", "| Risk | Mitigation |", "|---|---|"]
        out += [f"| {r.get('risk')} | {r.get('mitigation', '**TODO**')} |" for r in spec["risks"]]
        out.append("")
    mon = spec.get("monitoring")
    out += ["## Monitoring and Maintenance", ""]
    if mon:
        for k, lab in (("metrics", "Monitored"), ("drift", "Drift checks"), ("retraining", "Retraining"),
                       ("owner", "Owner")):
            if mon.get(k):
                v = mon[k]
                out.append(f"- **{lab}:** " + (", ".join(v) if isinstance(v, list) else str(v)))
    else:
        todos.append("monitoring")
        out.append(todo("monitoring"))
    out.append("")
    if spec.get("caveats"):
        out += ["## Caveats and Recommendations", "", bullets(spec["caveats"]), ""]
    if spec.get("citation"):
        out += ["## Citation", "", "```", spec["citation"], "```", ""]
    return "\n".join(out).rstrip() + "\n", todos


def main():
    ap = argparse.ArgumentParser(description="Write a model card from a JSON spec.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("--slices", help="JSON written by slice_metrics.py --json")
    ap.add_argument("-o", "--output")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any required section is missing")
    a = ap.parse_args()
    try:
        with open(a.spec, encoding="utf-8") as f:
            spec = json.load(f)
        if not isinstance(spec, dict) or not spec.get("name"):
            raise ValueError("spec must be a JSON object with a 'name'")
        slices = None
        if a.slices:
            with open(a.slices, encoding="utf-8") as f:
                slices = json.load(f)
            if "overall" not in slices:
                raise ValueError("slices file must come from slice_metrics.py --json")
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    card, todos = build(spec, slices)
    if a.output:
        with open(a.output, "w", encoding="utf-8") as f:
            f.write(card)
    else:
        sys.stdout.write(card)
    msg = f"{len(todos)} required section(s) missing: {', '.join(todos)}" if todos else "all required sections present"
    print(("wrote " + a.output + ": " if a.output else "") + msg, file=sys.stderr)
    return 1 if (a.strict and todos) else 0


if __name__ == "__main__":
    sys.exit(main())
