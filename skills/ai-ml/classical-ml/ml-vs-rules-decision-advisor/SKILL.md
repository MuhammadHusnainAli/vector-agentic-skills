---
name: ml-vs-rules-decision-advisor
description: "Decide whether a problem should be solved with hand-written rules, machine learning, a hybrid of both, or not yet: score twelve factors (labelled data volume, label availability, signal complexity, change rate, rule maintenance pain, scale, error cost, explainability and regulation, latency, team ML maturity, personalisation, feedback speed) with hard gates, learn a shallow readable rule set from a CSV with pure-Python CART and compare its holdout AUC with the ML model, emit the rule as a deployable SQL CASE, and design hybrids (rules as filters, guardrails, model score inside rules, ML-suggested rules). Use when someone asks \"do we even need ML?\", \"rules or a model?\", wants to replace a sprawling rule engine, justify an ML project against existing business rules, or plan a migration from rules to ML."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# ML vs Rules Decision Advisor

Rules are cheaper, faster, auditable and need no labels; ML wins when the signal is spread over many weak,
interacting features, patterns shift faster than people can edit rules, or the rule base has become
unmaintainable. Most production systems end up as **hybrids**: hard rules for policy and catastrophic cases,
a model for ranking the rest. `scripts/rules_vs_ml.py` scores twelve factors with hard gates and
recommends RULES, HYBRID, ML or NOT YET; `scripts/rule_learner.py` learns the best small rule set from your
data and shows how close it gets to a model, with a deployable SQL rule.

## Trigger Conditions

Activate this skill when the user:
- Asks "do we need ML for this?", "rules or a model?", "is a heuristic good enough?"
- Maintains a large rule engine (fraud, routing, pricing, eligibility, alerting) and wants to know whether ML
  should replace or augment it
- Must justify an ML project against the existing business rules, or a stakeholder insists rules are enough
- Wants interpretable rules extracted from data (to deploy, to audit a model, or to seed a rule base)
- Is planning a migration from rules to ML without breaking policy constraints

Framing comes first ([ml-problem-framing-advisor](../ml-problem-framing-advisor/SKILL.md)); data
sufficiency in [ml-feasibility-assessor](../ml-feasibility-assessor/SKILL.md); the baseline table that
includes the rule in [ml-baseline-model-builder](../ml-baseline-model-builder/SKILL.md).

## Workflow

```
1. DECISION   -> what is decided, how often, by whom today; current rules and their measured performance
2. SCORE      -> python scripts/rules_vs_ml.py --template > a.json; edit; python scripts/rules_vs_ml.py a.json
3. EVIDENCE   -> python scripts/rule_learner.py data.csv --target y --time-col ts --ml-auc <model AUC>
4. COMPARE    -> current rules vs learned rules vs ML on the same holdout and metric (precision@K, cost)
5. DECIDE     -> RULES / HYBRID / ML / NOT YET, with the gating reasons
6. DESIGN     -> for HYBRID: which rules stay hard, where the model sits, how overrides work
7. MIGRATE    -> shadow mode, champion/challenger, rollback; keep logging for labels
```

## Decision Factors

| Factor | Favours rules | Favours ML |
|--------|---------------|------------|
| Labelled data | none, or a few dozen positives | thousands of labelled outcomes |
| Signal | one or two obvious conditions ("overdue > 30 days") | many weak, interacting signals |
| Change rate | stable policy | adversarial or trending patterns (fraud, spam, demand) |
| Rule base | a handful of clear rules | hundreds of overlapping rules nobody understands |
| Scale | dozens of decisions per day | millions; small accuracy gains add up |
| Error cost | one error is catastrophic (safety, legal) | errors are cheap and reversible |
| Explainability | must cite the exact rule (regulation, adverse action) | reasons are nice-to-have |
| Latency / infra | microseconds, no serving stack | model serving exists |
| Team | nobody can retrain or monitor | MLOps in place |
| Personalisation | one policy for everyone | per-user decisions |
| Feedback speed | labels after months | labels in minutes |

**Hard gates** in `rules_vs_ml.py`: no data -> NOT YET (deploy rules and log outcomes); no labels and no path
to labels -> RULES (supervised ML impossible); regulated decision requiring exact reasons -> RULES or
interpretable scorecards; simple signal with a small rule set -> RULES.

## Get Evidence: How Far Do Rules Go?

Opinions about "rules are enough" settle quickly with numbers on the same holdout:

```bash
python scripts/rule_learner.py data.csv --target churned --time-col signup_date --max-depth 3 --min-leaf 20 \
    --drop customer_id zip_code refund_issued cancellation_reason --ml-auc 0.87
```

```
  FLAG IF support_calls >= 2 AND tenure_months < 16 (or missing)
         THEN rate 0.682  (n=22, lift 3.03x)
  ...
Holdout (120 rows): ROC-AUC 0.655  PR-AUC 0.222 ...
ML model AUC 0.870 vs rules 0.655 (gap +0.215): ML clearly ahead (> 0.08 AUC): the signal is beyond a few rules
```

| Gap (ML AUC − learned-rule AUC) | Reading |
|---------------------------------|---------|
| < 0.03 | rules capture the signal: prefer rules unless ML adds other value (automation of upkeep, personalisation) |
| 0.03 - 0.08 | moderate lift: hybrid, or ML if the lift at the operating point pays its running cost |
| > 0.08 | signal lives in interactions and many weak features: ML earns its cost |

A leaf with a positive rate of 1.000 on a single column (`IF cancellation_reason != ''`) is a leak, not a
rule: drop the column and refit. Always compare at the operating point too (precision@K, cost), not only AUC; rules produce few distinct
scores, so their AUC understates what a single well-placed rule threshold achieves at one K.

## Hybrid Patterns

| Pattern | Shape | Use when |
|---------|-------|----------|
| Rules as hard guardrails | `if blocklisted or amount > limit: decline` before or after the model | legal/policy limits, catastrophic cases |
| Rules as eligibility filter | model scores only rows rules allow | out-of-scope populations, cold start |
| Model inside a rule | `if score > 0.8 and amount > 500: review` | humans want rules but need better signal |
| Rules for cold start, ML when data exists | rule for new users, model after 30 days | sparse early data |
| ML proposes, humans approve | mine rules from data/SHAP, analysts promote them | regulated or adversarial domains |
| Rules override with logging | analysts can force decisions; overrides become labels | trust building, feedback |
| Champion/challenger | rules = champion, model = challenger on a traffic slice | migration with a safety net |

Code and diagrams: [hybrid-patterns.md](references/hybrid-patterns.md).

## When Rules Are the Right Answer

- The policy *is* the rule (eligibility thresholds, compliance limits, contractual terms).
- No labels exist and the cost of errors is high: encode expert knowledge, log outcomes, revisit later.
- Volume is small: a person or a rule handles it at lower total cost than an ML lifecycle.
- A single interpretable threshold captures most of the value (check with `rule_learner.py --max-depth 1`).

Treat rules as software: owner, tests with examples, version control, a review date, metrics on hit rate,
precision and conflicts. Details: [rules-engineering.md](references/rules-engineering.md).

## When ML Is the Right Answer

- Rule maintenance is the bottleneck (hundreds of rules, frequent conflicts, nobody can explain the order).
- Fraud/spam/abuse patterns shift weekly and rules lag the adversary.
- Ranking or personalisation over many items or users.
- Large volume where 1-2 points of precision are worth real money.

Keep guardrail rules outside the model even then; a model should never be the only thing standing between a
request and a legally prohibited outcome.

## Migration From Rules to ML

1. **Measure the rules** as if they were a model (precision, recall, volume) on a labelled period.
2. **Learn from rule-generated labels carefully:** if labels only exist where rules fired, the model inherits
   the rules' blind spots (selection bias); add random exploration or review samples.
3. **Shadow mode:** run the model alongside rules, compare decisions, review disagreements.
4. **Champion/challenger:** give the model a small traffic share with guardrail rules still active.
5. **Retire rules gradually**, keeping a rule-only fallback for model outages.

Checklist and pitfalls: [migration-rules-to-ml.md](references/migration-rules-to-ml.md).

## Output Format

When advising, answer with:
1. **Recommendation** - RULES, HYBRID, ML or NOT YET, with the gating factor or the strongest factors.
2. **Evidence** - current rules' metrics, learned-rule metrics (`rule_learner.py`), the ML model's metrics, on
   the same holdout and operating point.
3. **Design** - for RULES: the rule set (SQL/pseudocode) with owners and review dates; for HYBRID: which rules
   stay hard, where the model sits, override handling; for ML: the guardrail rules that remain.
4. **Costs** - build, run and maintenance for each option, and the lift that would justify ML.
5. **Migration or revisit plan** - shadow mode, champion/challenger, what data to log, when to reassess.

## Scripts

```bash
python scripts/rules_vs_ml.py --template > answers.json   # example answers to edit
python scripts/rules_vs_ml.py answers.json
python scripts/rules_vs_ml.py answers.json --json
```
Twelve factors scored 1 (favours rules) to 5 (favours ML), weighted and centred into a score from -1 to +1;
hard gates for no data, no labels, regulated decisions needing exact reasons, and simple signal with few
rules. Prints the recommendation, the gate or strongest factors with reasons, and next steps for that
option. Exit codes: 0 printed, 2 usage error (missing or out-of-range factors).

```bash
python scripts/rule_learner.py data.csv --target churned --drop customer_id --time-col signup_date
python scripts/rule_learner.py data.csv --target is_fraud --max-depth 2 --min-leaf 30 --ml-auc 0.91
python scripts/rule_learner.py data.csv --target churned --flag-rate 0.4 --json
```
Pure-Python CART (Gini) on a binary target: numeric thresholds on up to 32 quantile candidates, categorical
equality splits on the top 20 levels, depth and minimum-leaf limits, missing numeric values routed to the
"below" branch. Prints IF/THEN rules simplified into one interval per column, each leaf's positive rate, size
and lift, holdout ROC-AUC, PR-AUC, precision and recall when flagging leaves above `--flag-rate` (default
twice the base rate), a NULL-safe SQL `CASE` for the flagged leaves, and a verdict against `--ml-auc`. Exit
codes: 0 fitted, 2 usage error or non-binary target.

## Additional Resources

| File | Content |
|------|---------|
| [decision-framework.md](references/decision-framework.md) | The factors in depth, cost comparison of rules vs ML over a year, worked decisions (invoice reminders, fraud, ticket routing, eligibility, alerting) |
| [hybrid-patterns.md](references/hybrid-patterns.md) | Guardrails, filters, score-in-rule, cold-start rules, ML-suggested rules, overrides, champion/challenger, with code |
| [rules-engineering.md](references/rules-engineering.md) | Rules as code: representation, testing, versioning, conflict detection, metrics, decision tables, rule extraction from models |
| [migration-rules-to-ml.md](references/migration-rules-to-ml.md) | Step-by-step migration, selection bias from rule-generated labels, shadow mode, rollback, retiring rules |
