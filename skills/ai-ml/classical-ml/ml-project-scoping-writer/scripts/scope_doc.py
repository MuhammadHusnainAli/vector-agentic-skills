#!/usr/bin/env python3
"""Render an ML project scoping document (Markdown) from a JSON spec.

Every section of a good ML scope is generated from the spec; anything missing is written as a
visible `TODO(owner)` so gaps cannot hide. Print a complete example spec with --template.

Sections: summary, decision and users, success criteria (primary metric, target, baseline,
guardrails, online metric), data and labels, approach (phased, simplest first), in scope / out of
scope, milestones with exit criteria, risks with mitigations, team and costs, go/no-go criteria,
open questions.

Usage:
    python scope_doc.py --template > scope.json
    python scope_doc.py scope.json > SCOPE.md
    python scope_doc.py scope.json -o SCOPE.md --strict     # exit 1 if any TODO remains

Exit codes: 0 rendered (no TODOs, or not --strict), 1 TODOs remain with --strict, 2 usage error.
"""

import argparse
import json
import sys

TEMPLATE = {
    "title": "Churn retention targeting",
    "owner": "Data Science - Retention",
    "date": "2026-11-01",
    "status": "draft",
    "summary": "Rank active subscribers weekly by risk of cancelling in the next 30 days so the retention team "
               "calls the 400 most at-risk customers.",
    "problem": "Voluntary churn is 2.1% per month; the retention team calls customers whose contract ends this "
               "month, which misses most churners.",
    "decision": "Which 400 customers the retention team calls each Monday",
    "users": ["Retention team leads (consume the list)", "Retention analysts (review weekly)"],
    "success": {
        "primary_metric": "recall@400 of customers cancelling within 30 days",
        "target": ">= 0.45 on the latest 3-month time holdout",
        "baseline": "0.30 for the current contract-end rule on the same holdout",
        "guardrails": ["complaint rate of called customers <= 1.5%", "recall@400 per region >= 0.35"],
        "online_metric": "saves per 400 calls vs a 5% untreated random holdout over 6 weeks",
    },
    "data": {
        "sources": [
            {"name": "billing.subscriptions", "owner": "finance", "freshness": "hourly", "available_at_prediction": True},
            {"name": "support.tickets", "owner": "support", "freshness": "daily", "available_at_prediction": True},
        ],
        "label": "voluntary cancellation within 30 days after the Monday scoring date",
        "history": "24 months of weekly snapshots, ~50k active customers per week",
        "known_issues": ["cancellation_reason is written after cancellation (excluded)"],
    },
    "approach": [
        {"phase": "Baseline", "work": "current rule, dummy, logistic regression on a time holdout"},
        {"phase": "Model", "work": "LightGBM with point-in-time features; calibrate; pick K=400"},
        {"phase": "Shadow", "work": "score live for 4 weeks without acting; check drift and latency"},
        {"phase": "Test", "work": "randomised test: model top-400 vs rule top-400, 6 weeks"},
    ],
    "in_scope": ["weekly batch scoring", "voluntary churn", "consumer plans"],
    "out_of_scope": ["involuntary churn (failed payments)", "real-time scoring", "offer personalisation"],
    "milestones": [
        {"name": "Baseline table", "date": "2026-11-15", "exit": "rule, dummy and logistic regression measured"},
        {"name": "Model ready", "date": "2026-12-13", "exit": "recall@400 >= 0.45 offline with CI"},
        {"name": "Shadow complete", "date": "2027-01-17", "exit": "feature availability >= 98%, PSI < 0.2"},
        {"name": "Test readout", "date": "2027-03-07", "exit": "go/no-go decision"},
    ],
    "risks": [
        {"risk": "calling customers changes their labels (feedback loop)", "likelihood": "high",
         "impact": "medium", "mitigation": "5% random untreated holdout; log calls"},
        {"risk": "support tickets arrive with a 24 h delay", "likelihood": "medium", "impact": "low",
         "mitigation": "use ticket counts up to the previous day only"},
    ],
    "team": [{"role": "Data scientist", "fte": 1.0}, {"role": "Data engineer", "fte": 0.5},
             {"role": "Retention lead (product owner)", "fte": 0.1}],
    "costs": "about 4 person-months to the test readout; serving on the existing batch platform",
    "go_no_go": ["offline recall@400 >= 0.45 with the 95% CI above the rule",
                 "online: +5 saves per week vs the rule with the CI excluding 0"],
    "open_questions": ["Can the retention team handle 500 calls in December?"],
}


class Doc:
    def __init__(self):
        self.lines, self.todos = [], []

    def add(self, *lines):
        self.lines.extend(lines)

    def val(self, v, what):
        if v in (None, "", [], {}):
            self.todos.append(what)
            return f"`TODO(owner): {what}`"
        return v


def render(spec):
    d = Doc()
    v = d.val
    d.add(f"# {v(spec.get('title'), 'title')}", "",
          f"| Owner | Date | Status |", "|-------|------|--------|",
          f"| {v(spec.get('owner'), 'owner')} | {v(spec.get('date'), 'date')} | {spec.get('status', 'draft')} |", "",
          "## Summary", "", v(spec.get("summary"), "one-paragraph summary: decision, prediction, value"), "",
          "## Problem and decision", "", v(spec.get("problem"), "the business problem with a number"), "",
          f"**Decision this model changes:** {v(spec.get('decision'), 'decision')}", "",
          "**Users:**", "")
    users = spec.get("users") or []
    d.add(*([f"- {u}" for u in users] or [f"- {v(None, 'who consumes the predictions')}"]), "")
    s = spec.get("success") or {}
    d.add("## Success criteria", "", "| Item | Value |", "|------|-------|",
          f"| Primary metric | {v(s.get('primary_metric'), 'primary metric at the operating point')} |",
          f"| Target | {v(s.get('target'), 'target value and evaluation split')} |",
          f"| Baseline | {v(s.get('baseline'), 'current process measured on the same split')} |",
          f"| Guardrails | {'; '.join(s.get('guardrails') or []) or v(None, 'guardrail metrics')} |",
          f"| Online metric | {v(s.get('online_metric'), 'how success is confirmed after launch')} |", "")
    data = spec.get("data") or {}
    d.add("## Data and labels", "", f"**Label:** {v(data.get('label'), 'label definition with window')}", "",
          f"**History:** {v(data.get('history'), 'rows, time span, entities')}", "",
          "| Source | Owner | Freshness | Available at prediction time |", "|--------|-------|-----------|------------------|")
    srcs = data.get("sources") or []
    if not srcs:
        d.add(f"| {v(None, 'data sources')} | | | |")
    for src in srcs:
        avail = src.get("available_at_prediction")
        d.add(f"| {src.get('name', '?')} | {src.get('owner', '?')} | {src.get('freshness', '?')} | "
              f"{'yes' if avail else 'NO' if avail is False else v(None, 'availability of ' + src.get('name', '?'))} |")
    if data.get("known_issues"):
        d.add("", "**Known data issues:**", "", *[f"- {i}" for i in data["known_issues"]])
    d.add("", "## Approach", "", "Simplest credible option first; each phase has an exit criterion in Milestones.", "")
    phases = spec.get("approach") or []
    d.add(*([f"{i}. **{p.get('phase', '?')}** - {p.get('work', '')}" for i, p in enumerate(phases, 1)]
            or [f"1. {v(None, 'phased approach (baseline first)')}"]), "")
    d.add("## Scope", "", "| In scope | Out of scope |", "|----------|--------------|")
    ins, outs = spec.get("in_scope") or [], spec.get("out_of_scope") or []
    if not outs:
        outs = [v(None, "out-of-scope items (say what you will NOT do)")]
    if not ins:
        ins = [v(None, "in-scope items")]
    for i in range(max(len(ins), len(outs))):
        d.add(f"| {ins[i] if i < len(ins) else ''} | {outs[i] if i < len(outs) else ''} |")
    d.add("", "## Milestones", "", "| Milestone | Date | Exit criterion |", "|-----------|------|----------------|")
    ms = spec.get("milestones") or []
    if not ms:
        d.add(f"| {v(None, 'milestones with dates and exit criteria')} | | |")
    for m in ms:
        d.add(f"| {m.get('name', '?')} | {v(m.get('date'), 'date for ' + m.get('name', '?'))} | "
              f"{v(m.get('exit'), 'exit criterion for ' + m.get('name', '?'))} |")
    d.add("", "## Risks", "", "| Risk | Likelihood | Impact | Mitigation |", "|------|------------|--------|------------|")
    risks = spec.get("risks") or []
    if not risks:
        d.add(f"| {v(None, 'risks (leakage, labels, adoption, feedback loops)')} | | | |")
    for r in risks:
        d.add(f"| {r.get('risk', '?')} | {r.get('likelihood', '?')} | {r.get('impact', '?')} | "
              f"{v(r.get('mitigation'), 'mitigation for: ' + r.get('risk', '?'))} |")
    d.add("", "## Team and costs", "")
    team = spec.get("team") or []
    d.add(*([f"- {t.get('role', '?')}: {t.get('fte', '?')} FTE" for t in team] or [f"- {v(None, 'team and FTE')}"]))
    d.add("", f"**Cost estimate:** {v(spec.get('costs'), 'effort and run cost')}", "", "## Go / no-go criteria", "")
    gng = spec.get("go_no_go") or []
    d.add(*([f"- {g}" for g in gng] or [f"- {v(None, 'kill criteria written before the work starts')}"]), "")
    oq = spec.get("open_questions") or []
    if oq:
        d.add("## Open questions", "", *[f"- {q}" for q in oq], "")
    return "\n".join(d.lines).rstrip() + "\n", d.todos


def main():
    ap = argparse.ArgumentParser(description="Render an ML scoping document from a JSON spec.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", nargs="?", help="JSON spec, or - for stdin")
    ap.add_argument("-o", "--output")
    ap.add_argument("--template", action="store_true")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any TODO remains")
    a = ap.parse_args()
    if a.template:
        print(json.dumps(TEMPLATE, indent=2))
        return 0
    if not a.spec:
        print("error: give a spec file (see --template)", file=sys.stderr)
        return 2
    try:
        spec = json.loads(sys.stdin.read() if a.spec == "-" else open(a.spec, encoding="utf-8").read())
        if not isinstance(spec, dict):
            raise ValueError("spec must be a JSON object")
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    text, todos = render(spec)
    if a.output:
        with open(a.output, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        sys.stdout.write(text)
    if todos:
        print(f"{len(todos)} TODO(s): " + "; ".join(todos), file=sys.stderr)
    return 1 if todos and a.strict else 0


if __name__ == "__main__":
    sys.exit(main())
