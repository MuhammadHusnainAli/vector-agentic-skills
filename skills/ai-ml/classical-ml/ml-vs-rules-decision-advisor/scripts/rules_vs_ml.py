#!/usr/bin/env python3
"""Score the rules-vs-ML decision from twelve factors and recommend RULES, HYBRID, ML or NOT YET.

Each factor is answered on a 1-5 scale in a JSON file (print one with --template). Low scores
favour hand-written rules, high scores favour ML. Hard gates override the total:
  - labels < 2 (no labels and no way to get them)   -> rules or anomaly heuristics, not supervised ML
  - explainability 5 with regulated decision         -> rules, scorecards or monotone GLM/GBM only
  - signal_complexity <= 2 and rule_maintenance <= 2 -> rules are enough today
  - data_volume <= 1                                 -> NOT YET (collect data with rules first)

Factors (1 = favours rules ... 5 = favours ML):
  data_volume          labelled examples: 1 none / 3 thousands / 5 hundreds of thousands
  labels               label availability: 1 none / 3 delayed or noisy / 5 plentiful and clean
  signal_complexity    1 one or two obvious conditions / 5 many weak interacting signals
  change_rate          how fast patterns change: 1 rarely / 5 weekly (adversarial, trends)
  rule_maintenance     pain of current rules: 1 a few stable rules / 5 hundreds, conflicting
  scale                decisions per day: 1 dozens / 5 millions
  error_cost_tolerance 1 a single error is catastrophic / 5 errors are cheap and reversible
  explainability       need for exact reasons: 1 none / 5 must state the precise rule (regulation)
  latency_budget       1 microseconds, no infra / 5 seconds, serving infra exists
  team_ml_maturity     1 no one can retrain/monitor / 5 MLOps in place
  personalization      1 one policy for all / 5 per-user decisions
  feedback_speed       1 labels arrive after months / 5 within minutes

Usage:
    python rules_vs_ml.py --template > answers.json
    python rules_vs_ml.py answers.json
    python rules_vs_ml.py answers.json --json

Exit codes: 0 recommendation printed, 2 usage error (missing or out-of-range factors).
"""

import argparse
import json
import sys

FACTORS = {
    "data_volume": (1.5, "more labelled data lets ML find patterns rules miss"),
    "labels": (1.5, "supervised ML needs labels; rules need only domain knowledge"),
    "signal_complexity": (2.0, "many weak interacting signals are where ML beats hand-written logic"),
    "change_rate": (1.0, "fast-changing patterns favour retrainable models over hand-edited rules"),
    "rule_maintenance": (1.0, "a sprawling, conflicting rule base is a strong reason to learn the logic"),
    "scale": (0.75, "at high volume small accuracy gains pay for ML's fixed costs"),
    "error_cost_tolerance": (1.0, "ML errs statistically; catastrophic single errors favour hard rules"),
    "explainability": (-1.25, "exact, auditable reasons favour rules or interpretable models"),
    "latency_budget": (0.5, "tight latency without serving infra favours rules"),
    "team_ml_maturity": (1.0, "ML needs retraining, monitoring and on-call; rules need an editor"),
    "personalization": (0.75, "per-user decisions are hard to express as rules"),
    "feedback_speed": (0.5, "fast labels make it cheap to evaluate and retrain ML"),
}

TEMPLATE = {"decision": "Flag card transactions for manual review", "regulated": False,
            "data_volume": 4, "labels": 4, "signal_complexity": 4, "change_rate": 5, "rule_maintenance": 4,
            "scale": 5, "error_cost_tolerance": 3, "explainability": 2, "latency_budget": 3,
            "team_ml_maturity": 3, "personalization": 3, "feedback_speed": 3}


def evaluate(ans):
    bad = [k for k in FACTORS if not isinstance(ans.get(k), (int, float)) or not 1 <= ans[k] <= 5]
    if bad:
        raise ValueError(f"factors missing or not in 1..5: {', '.join(bad)}")
    contrib = []
    for k, (w, why) in FACTORS.items():
        c = w * (ans[k] - 3)                 # centred: 3 is neutral
        contrib.append((k, ans[k], c, why))
    total = sum(c for _, _, c, _ in contrib)
    max_abs = sum(abs(w) * 2 for w, _ in FACTORS.values())
    score = total / max_abs                  # -1 (rules) .. +1 (ML)
    gates = []
    if ans["data_volume"] <= 1:
        gates.append(("NOT YET", "almost no data: deploy rules now and log decisions and outcomes as future labels"))
    if ans["labels"] < 2:
        gates.append(("RULES", "no labels and no path to labels: supervised ML is not possible; consider anomaly "
                               "detection or clustering only as aids to rule writing"))
    if ans["explainability"] >= 5 and ans.get("regulated"):
        gates.append(("RULES", "regulated decision needing exact reasons: rules, points scorecards or monotone "
                               "GLM/GBM with reason codes; no black boxes"))
    if ans["signal_complexity"] <= 2 and ans["rule_maintenance"] <= 2:
        gates.append(("RULES", "simple signal and a manageable rule set: rules are enough today"))
    if gates:
        verdict = gates[0][0]
    elif score >= 0.25:
        verdict = "ML"
    elif score <= -0.15:
        verdict = "RULES"
    else:
        verdict = "HYBRID"
    return verdict, score, contrib, gates


ADVICE = {
    "RULES": ["Write rules with owners, tests and a review date; version them like code.",
              "Log inputs, rule hits and outcomes so labels exist if you revisit ML.",
              "Measure the rules like a model: precision, recall, alert volume (rule_learner.py helps)."],
    "HYBRID": ["Keep hard rules for policy and catastrophic cases (blocklists, legal limits); let ML rank the rest.",
               "Common shapes: rules as filters before the model, the model score as one input to a rule, or ML "
               "to suggest new rules that humans approve.",
               "Run the model in shadow mode next to the rules before switching any traffic."],
    "ML": ["Start with the baseline ladder (ml-baseline-model-builder) and keep the current rules as the bar.",
           "Keep guardrail rules (hard limits) outside the model.",
           "Budget for monitoring, retraining and drift detection from day one."],
    "NOT YET": ["Deploy simple rules now; design them to generate labelled data (log every decision and outcome).",
                "Revisit when there are a few hundred labelled positives (ml-feasibility-assessor)."],
}


def main():
    ap = argparse.ArgumentParser(description="Recommend rules, ML or a hybrid from 12 scored factors.",
                                 epilog=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("answers", nargs="?", help="JSON answers file or - for stdin")
    ap.add_argument("--template", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.template:
        print(json.dumps(TEMPLATE, indent=2))
        return 0
    if not a.answers:
        print("error: give an answers file (or --template)", file=sys.stderr)
        return 2
    try:
        ans = json.loads(sys.stdin.read() if a.answers == "-" else open(a.answers, encoding="utf-8").read())
        verdict, score, contrib, gates = evaluate(ans)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps({"verdict": verdict, "score": round(score, 3), "gates": [g[1] for g in gates],
                          "factors": [{"factor": k, "answer": v, "contribution": round(c, 2)} for k, v, c, _ in contrib],
                          "advice": ADVICE[verdict]}, indent=2))
        return 0
    print(f"Recommendation: {verdict}   (score {score:+.2f} on -1 = rules .. +1 = ML)")
    if ans.get("decision"):
        print(f"Decision: {ans['decision']}")
    for _, why in gates:
        print(f"gate: {why}")
    print("\nStrongest factors:")
    for k, v, c, why in sorted(contrib, key=lambda x: -abs(x[2]))[:6]:
        side = "ML" if c > 0 else ("rules" if c < 0 else "neutral")
        print(f"  {k:<22} {v}  -> {side:<7} {why}")
    print("\nNext:")
    for line in ADVICE[verdict]:
        print(f"  - {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
