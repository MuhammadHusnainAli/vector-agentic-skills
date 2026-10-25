#!/usr/bin/env python3
"""Check an ML problem framing spec for gaps and contradictions before any modelling starts.

The spec is a JSON object (print a blank one with --template). The checker
looks for the questions that sink ML projects when nobody answers them:
which decision the prediction changes, who acts on it and how often, the unit
and moment of prediction, the label definition and its delay, whether the
features exist at prediction time, the baseline to beat and the metric.

Findings:
  FR001 blocking  no decision/action the prediction drives
  FR002 blocking  prediction target missing or not a measurable quantity
  FR003 blocking  unit of prediction (row = what?) missing
  FR004 blocking  prediction time missing ("when do we score?")
  FR005 high      horizon missing or shorter than the time needed to act
  FR006 high      label delay longer than the horizon (cannot retrain/monitor quickly)
  FR007 high      a feature is only known after prediction time (leakage by framing)
  FR008 high      no baseline / current process to compare against
  FR009 medium    success metric missing or not tied to the decision
  FR010 medium    action capacity missing (how many cases can be acted on)
  FR011 medium    label is a proxy; proxy risk not written down
  FR012 medium    prediction changes the future label (feedback loop) but no holdout plan
  FR013 low       no owner / consumer named
  FR014 low       task type disagrees with the target description

Usage:
    python frame_check.py spec.json
    python frame_check.py spec.json --json
    python frame_check.py --template > spec.json
    cat spec.json | python frame_check.py -

Exit codes: 0 no blocking/high findings, 1 blocking or high findings, 2 usage or read error.
"""

import argparse
import json
import re
import sys

TEMPLATE = {
    "problem": "Reduce voluntary churn of monthly subscribers",
    "decision": "Which customers get a retention call this week",
    "action": "Retention team calls the top-scored customers",
    "action_capacity": "400 calls per week",
    "owner": "Head of Retention",
    "unit_of_prediction": "one active subscriber on the scoring date",
    "prediction_time": "every Monday 06:00 UTC",
    "target": "customer cancels within 30 days after the scoring date",
    "task_type": "binary_classification",
    "horizon_days": 30,
    "time_to_act_days": 7,
    "label_delay_days": 30,
    "label_is_proxy": False,
    "proxy_risk": "",
    "features": [
        {"name": "tenure_months", "available_at": "prediction_time"},
        {"name": "support_calls_90d", "available_at": "prediction_time"},
    ],
    "baseline": "Call customers whose contract ends this month (current rule)",
    "success_metric": "Recall of churners in the top 400 per week vs the current rule",
    "guardrail_metrics": ["calls per saved customer", "complaint rate"],
    "prediction_affects_label": True,
    "holdout_plan": "5% random holdout never called, to measure uplift and retrain on unbiased labels",
}

TASK_WORDS = {
    "binary_classification": r"\b(whether|will|cancel|churn|default|fraud|click|convert|yes|no|flag)\b",
    "regression": r"\b(how much|amount|value|price|revenue|spend|duration|time to|number of|count)\b",
    "forecasting": r"\b(forecast|demand|next (week|month|day)s?|per day|per week|daily|weekly)\b",
    "ranking": r"\b(rank|order|top|recommend|relevance|which items)\b",
    "multiclass_classification": r"\b(which (category|class|type|team|queue)|route|categor)",
}
LATE_WORDS = ("after", "outcome", "result", "label", "final", "resolution", "closed", "refund", "cancel", "future")
VAGUE_TARGET = re.compile(r"^\s*(better|improve|optimi[sz]e|understand|insights?|ai|ml)\b", re.I)


def empty(v):
    return v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, (list, dict)) and not v)


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def check(spec):
    out = []

    def add(code, sev, msg, fix):
        out.append({"code": code, "severity": sev, "message": msg, "fix": fix})

    if empty(spec.get("decision")) and empty(spec.get("action")):
        add("FR001", "blocking", "no decision or action is named; a prediction nobody acts on has no value",
            "write the sentence 'Because of this prediction, <who> will <do what> <how often>'")
    target = spec.get("target") or ""
    if empty(target) or VAGUE_TARGET.match(target):
        add("FR002", "blocking", f"target {target!r} is missing or not measurable",
            "state the label as an observable event or quantity with a window, e.g. 'cancels within 30 days of scoring'")
    if empty(spec.get("unit_of_prediction")):
        add("FR003", "blocking", "unit of prediction is missing (one row = one what?)",
            "name the entity and moment: 'one active customer on the scoring date', 'one order at checkout'")
    if empty(spec.get("prediction_time")):
        add("FR004", "blocking", "prediction time is missing; leakage and feature availability cannot be judged",
            "say when the model scores (batch schedule or the real-time trigger)")

    horizon, act = num(spec.get("horizon_days")), num(spec.get("time_to_act_days"))
    delay = num(spec.get("label_delay_days"))
    task = (spec.get("task_type") or "").strip()
    needs_horizon = task in ("", "binary_classification", "multiclass_classification", "regression", "forecasting")
    if needs_horizon and horizon is None and not re.search(r"\b(within|next|in the following)\b", target, re.I):
        add("FR005", "high", "no prediction horizon; 'will churn' is not a label until you say by when",
            "set horizon_days and put the window in the target text")
    elif horizon is not None and act is not None and act >= horizon:
        add("FR005", "high", f"time to act ({act:g} d) >= horizon ({horizon:g} d): the outcome happens before anyone can act",
            "lengthen the horizon, predict earlier, or speed up the action")
    if delay is not None and horizon is not None and delay > max(horizon, 1) * 3:
        add("FR006", "high", f"label delay {delay:g} d is far longer than the horizon {horizon:g} d; feedback and retraining will lag",
            "add a faster proxy label for monitoring, or accept slow iteration explicitly")

    for f in spec.get("features") or []:
        if not isinstance(f, dict):
            continue
        avail = str(f.get("available_at", "")).lower()
        name = str(f.get("name", "?"))
        if avail and avail not in ("prediction_time", "before_prediction_time", "static"):
            add("FR007", "high", f"feature {name!r} becomes available at {avail!r}, after prediction time",
                "drop it, or rebuild it as an as-of value computed only from data before prediction time")
        elif not avail and any(w in name.lower() for w in LATE_WORDS):
            add("FR007", "high", f"feature {name!r} sounds like an outcome; availability at prediction time is not stated",
                "set available_at and confirm with the data owner when the field is written")

    if empty(spec.get("baseline")):
        add("FR008", "high", "no baseline or current process; you cannot show the model is worth running",
            "describe today's rule or human process and measure it on the same data (see ml-baseline-model-builder)")
    metric = spec.get("success_metric") or ""
    if empty(metric):
        add("FR009", "medium", "no success metric", "pick one primary metric tied to the decision (see ml-success-metric-selector)")
    elif re.fullmatch(r"\s*(accuracy|auc|roc[- ]?auc|f1|rmse|r2)\s*", metric, re.I):
        add("FR009", "medium", f"metric {metric!r} is a model score, not a decision outcome",
            "phrase it at the action's operating point, e.g. 'recall in the top 400 per week' or 'cost per saved customer'")
    if empty(spec.get("action_capacity")) and task in ("", "binary_classification", "ranking"):
        add("FR010", "medium", "action capacity is unknown, so the operating threshold cannot be chosen",
            "write how many cases can be handled per period (calls, reviews, emails)")
    if spec.get("label_is_proxy") and empty(spec.get("proxy_risk")):
        add("FR011", "medium", "label is a proxy but the gap between proxy and goal is not written down",
            "describe when the proxy and the real goal disagree and how you will check it")
    if spec.get("prediction_affects_label") and empty(spec.get("holdout_plan")):
        add("FR012", "medium", "acting on predictions changes the labels you will retrain on (feedback loop)",
            "keep a random untreated holdout, log scores and actions, and consider uplift modelling")
    if empty(spec.get("owner")):
        add("FR013", "low", "no owner or consumer of the predictions", "name the person or system that consumes them")
    if task and target:
        hits = [t for t, pat in TASK_WORDS.items() if re.search(pat, target, re.I)]
        if hits and task not in hits and not (task == "binary_classification" and "regression" in hits and "will" in target.lower()):
            add("FR014", "low", f"task_type {task!r} but the target reads like {hits[0]!r}",
                "check the framing; the task-type catalog in references/task-type-catalog.md lists the options")
    return out


def suggest_task(spec):
    task = (spec.get("task_type") or "").strip()
    if task:
        return task
    target = spec.get("target") or ""
    for t, pat in TASK_WORDS.items():
        if re.search(pat, target, re.I):
            return t
    return "unknown"


def main():
    ap = argparse.ArgumentParser(description="Check an ML problem framing spec (JSON) for gaps. "
                                 "Prints usage examples with --help.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", nargs="?", help="framing spec JSON file, or - for stdin")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--template", action="store_true", help="print a filled-in example spec and exit")
    a = ap.parse_args()
    if a.template:
        print(json.dumps(TEMPLATE, indent=2))
        return 0
    if not a.spec:
        ap.print_usage(sys.stderr)
        print("error: give a spec file, - for stdin, or --template", file=sys.stderr)
        return 2
    try:
        text = sys.stdin.read() if a.spec == "-" else open(a.spec, encoding="utf-8").read()
        spec = json.loads(text)
        if not isinstance(spec, dict):
            raise ValueError("top level must be a JSON object")
    except (OSError, ValueError) as e:
        print(f"error: cannot read spec: {e}", file=sys.stderr)
        return 2

    findings = check(spec)
    order = {"blocking": 0, "high": 1, "medium": 2, "low": 3}
    findings.sort(key=lambda f: (order[f["severity"]], f["code"]))
    bad = [f for f in findings if f["severity"] in ("blocking", "high")]
    verdict = "NOT READY" if any(f["severity"] == "blocking" for f in findings) else (
        "NEEDS WORK" if bad else "READY TO PROTOTYPE")
    if a.json:
        print(json.dumps({"verdict": verdict, "task_type": suggest_task(spec), "findings": findings}, indent=2))
    else:
        print(f"Framing check: {verdict}   (task type: {suggest_task(spec)})")
        if not findings:
            print("No gaps found. Next: feasibility (ml-feasibility-assessor) and a baseline.")
        for f in findings:
            print(f"{f['code']} [{f['severity']}] {f['message']}\n      fix: {f['fix']}")
        print(f"\n{len(findings)} finding(s): " + ", ".join(
            f"{sum(f['severity'] == s for f in findings)} {s}" for s in order))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
