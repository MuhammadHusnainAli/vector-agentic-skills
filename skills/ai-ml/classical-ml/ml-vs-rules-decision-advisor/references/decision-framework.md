# Rules vs ML: Decision Framework

## The factors in depth

### Labelled data and labels
Supervised ML needs examples of the outcome. Ask: how many labelled positives exist, how long until more
arrive, are labels trustworthy, and were they produced by the current rules (selection bias)? Without labels
the options are rules, unsupervised aids (anomaly scores to help analysts write rules), or a labelling
programme.

### Signal complexity
If the outcome depends on one or two conditions an expert can name, rules are as good as a model and far
cheaper. If it depends on many weak signals and their interactions (fraud from device, velocity, merchant,
geography and time), people cannot write those rules, and ML wins. `rule_learner.py` measures this directly:
the AUC gap between a depth-2/3 tree and the model.

### Change rate
Adversarial domains (fraud, spam, bots) shift weekly; rules lag. Stable policy domains (eligibility,
compliance thresholds) do not change unless the policy does, and when it does the rule must change exactly,
which ML cannot guarantee.

### Rule maintenance pain
Signs the rule base is the bottleneck: hundreds of rules, rule order matters, overlapping and contradictory
rules, nobody knows why a rule exists, every change causes surprises.

### Scale
At low volume, total cost of ownership dominates: an ML lifecycle (data pipelines, retraining, monitoring,
on-call) costs the same whether it makes 100 or 10 million decisions. At high volume small precision gains
are large in money.

### Error cost
If one wrong decision is catastrophic (safety, legal exposure), keep a deterministic rule as the last line,
even with ML upstream.

### Explainability and regulation
Credit, insurance, employment and housing decisions often require specific reasons (adverse-action notices).
Options: rules, points-based scorecards (logistic regression on binned features), monotone-constrained
GBMs with reason codes from SHAP. Exact, legally reviewed rules beat models when the reason must be
deterministic.

### Latency and infrastructure
A rule in the application costs microseconds and no infrastructure. A model needs feature computation,
serving, versioning. If there is no serving path, a model can still be compiled into rules (tree extraction)
or a lookup table.

### Team maturity
A model nobody can retrain, monitor or debug decays silently. Rules decay too, but visibly.

## Annual cost comparison (template)

| Item | Rules | ML |
|------|-------|----|
| Initial build | analyst + engineer weeks | data + ML engineer months |
| Infrastructure | none / rule engine licence | feature store, serving, monitoring |
| Maintenance | rule edits per month x hours | retraining, drift investigation, on-call |
| Error cost | FP x cost + FN x cost at rule precision | same at model precision |
| Total | | |

ML is justified when `(error cost rules − error cost ML) > (ML build + run − rules build + run)` with margin
for the uncertainty in the error-cost estimate.

## Worked decisions

### Invoice reminder when payment is overdue
Signal: one condition (days overdue). Labels: plenty, but no learning needed. Verdict: **RULES**. A model
could optimise *when* to remind (uplift), a different decision.

### Card fraud review queue
Signal: many weak interacting features; adversarial drift; millions of transactions. Verdict: **HYBRID**
leaning ML: model ranks the review queue; hard rules for sanctions, blocklists, velocity limits; analysts
can add emergency rules during an attack.

### Support ticket routing
Signal: text plus metadata; 30 queues; rules are keyword lists that conflict. Labels: resolving queue
(noisy). Verdict: **ML** with a keyword-rule fallback and human correction logging.

### Loan eligibility
Policy thresholds (age, residency, minimum income) are law/policy: **RULES**. Risk ranking among eligible
applicants: interpretable model (scorecard or monotone GBM) with reason codes. Overall: **HYBRID**.

### Infrastructure alerting
Known failure modes have clear thresholds: **RULES**. Unknown anomalies across thousands of metrics:
anomaly detection to *suggest* alerts, analysts promote them into rules: **HYBRID**.

### Product recommendations
Personalisation over thousands of items: **ML**; rules for business constraints (out-of-stock, age
restrictions, contractual placements).
