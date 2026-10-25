---
name: ml-problem-framing-advisor
description: "Turn a vague business ask (\"use AI to reduce churn\", \"predict demand\", \"find fraud\") into a precise, buildable ML problem: the decision and action the prediction drives, who acts and with what capacity, the unit and moment of prediction, the label with its observation and outcome windows, label delay, features available at prediction time, task type (binary, multiclass, ordinal, regression, count, forecasting, ranking, anomaly, clustering, uplift), the baseline to beat and the metric at the operating point. Flags leakage-by-framing, proxy labels, feedback loops, selection bias and unactionable predictions. Use when someone asks how to frame an ML problem, what the target should be, whether something is classification or regression, how to define churn or a label window, or wants a framing review before modelling starts."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# ML Problem Framing Advisor

Most failed ML projects predict the wrong thing well: a target nobody can act on, a label that leaks the
answer, a horizon shorter than the time needed to respond. This skill turns a business goal into a framing
you can build, measure and ship: one decision, one action, one prediction made at a known moment for a known
unit, a label defined as an observable event in a window, and a baseline plus metric that show whether the
model is worth running. `scripts/frame_check.py` reviews a framing spec for 14 classic gaps;
`scripts/target_profile.py` reads a candidate label column and says which task it implies.

## Trigger Conditions

Activate this skill when the user:
- Has a business goal and asks how to turn it into an ML problem ("use ML to reduce churn / predict demand /
  catch fraud / prioritise leads / route tickets")
- Asks what the target or label should be, how to define churn, default, conversion or "active", or how long
  the label window should be
- Asks whether a problem is classification, regression, ranking, forecasting, clustering or anomaly detection
- Wants a framing review of a project brief, notebook or PRD before modelling starts
- Has a model with good offline scores that nobody uses, or that degraded after launch because acting on it
  changed the data

Feasibility of the framed problem goes to [ml-feasibility-assessor](../ml-feasibility-assessor/SKILL.md);
picking the metric to [ml-success-metric-selector](../ml-success-metric-selector/SKILL.md); whether you need
ML at all to [ml-vs-rules-decision-advisor](../ml-vs-rules-decision-advisor/SKILL.md); the written scope
document to [ml-project-scoping-writer](../ml-project-scoping-writer/SKILL.md).

## Workflow

```
1. DECISION   -> who will do what differently because of the prediction, how often, at what capacity
2. UNIT/TIME  -> one row = which entity at which moment; when is the model called (batch or event)
3. LABEL      -> observable event or quantity, outcome window, label delay; write it as a query
4. TASK       -> map label to task type; python scripts/target_profile.py data.csv --target y
5. FEATURES   -> only data that exists at prediction time; mark when each source is written
6. BASELINE   -> today's rule or human process, measured on the same rows
7. METRIC     -> the decision's operating point (top-K, threshold, cost), plus guardrails
8. RISKS      -> proxy gap, feedback loop, selection bias, fairness, label drift
9. CHECK      -> python scripts/frame_check.py spec.json   (fill --template first)
```

## The Framing Canvas

Answer every line before writing model code. A blank line is a finding.

| Field | Question | Good answer | Bad answer |
|-------|----------|-------------|------------|
| Decision | What changes because of the prediction? | "Which 400 customers the retention team calls each Monday" | "Understand churn" |
| Action + capacity | Who acts, how, how many per period? | "Agents call; 400 calls/week" | "Marketing will use it" |
| Unit of prediction | One row is what? | "An active subscriber on the scoring date" | "A customer" (which snapshot?) |
| Prediction time | When is the model called? | "Mondays 06:00 UTC, batch" / "at checkout" | missing |
| Target | Observable event/quantity + window | "Cancels within 30 days after scoring" | "Will churn" |
| Horizon vs time-to-act | Is there time to act before the outcome? | horizon 30 d, act within 7 d | horizon 3 d, calls take a week |
| Label delay | When do we know the label? | 30 d after scoring | 6 months (no fast feedback) |
| Features | Available at prediction time? | as-of snapshots, event logs before scoring | "final status", "refund issued" |
| Baseline | What happens today? | "Call customers whose contract ends this month" | none |
| Metric | Measured at the operating point | "Recall in the top 400 vs the rule" | "accuracy" |
| Guardrails | What must not get worse? | complaint rate, cost per save | none |
| Feedback | Does acting change future labels? | random 5% holdout, log actions | ignored |

Domain-by-domain filled canvases (churn, demand, fraud, lead scoring, ticket routing, predictive maintenance,
credit, pricing) are in [framing-canvas.md](references/framing-canvas.md).

## Business Ask -> Task Type

| The ask sounds like | Task | Label example | Typical first model |
|---------------------|------|---------------|---------------------|
| "Will X happen?" (churn, default, click, fraud) | binary classification | `cancelled_within_30d` | logistic regression, gradient boosting |
| "Which of these categories?" (route ticket, product type) | multiclass | `queue` | gradient boosting, linear on TF-IDF |
| "How satisfied / which grade?" (1-5) | ordinal | `rating` | regression on the scale or ordinal logit |
| "How much / how long?" (spend, LTV, delivery time) | regression | `spend_next_90d` | gradient boosting with a fitting loss |
| "How many?" (claims, visits) | count regression | `claims_next_year` | Poisson/Tweedie GBM or GLM |
| "How much per day/week?" over time | forecasting | `units[t+1..t+28]` | seasonal naive, ETS, GBM on lags |
| "Which items first?" (search, feed, leads) | ranking / LTR | graded relevance per query | LambdaMART |
| "When will it happen?" with censoring | survival / time-to-event | `(duration, event)` | Kaplan-Meier, Cox, GBM survival |
| "Who should we treat?" (coupon, call) | uplift / causal | outcome under treatment vs control | two-model / X-learner on an RCT |
| "What is unusual?" with few or no labels | anomaly detection | none or a handful | robust z-score, Isolation Forest |
| "What groups exist?" | clustering (exploratory) | none | k-means, HDBSCAN |
| "Which products together?" | recommendation | interactions | popularity, item-kNN, ALS |

Two re-framings fix most bad projects:
- **Predict the decision's input, not the KPI.** "Increase revenue" is a KPI; "probability this lead converts in
  14 days" feeds a ranking that sales acts on.
- **Predict who to treat, not who will churn.** If calling a customer changes the outcome, a churn score ranks
  people who leave anyway (lost causes) and people who never would (sure things) next to the persuadable ones.
  When treatment effect is the decision, frame it as uplift ([uplift-model-builder](../uplift-model-builder/SKILL.md)).

Full catalog with label shapes, losses, metrics and traps per task: [task-type-catalog.md](references/task-type-catalog.md).

## Define the Label as a Query

Write the label as the SQL or code that produces it. If you cannot, the label is not defined.

```
          observation window          gap      outcome window
  |----------------------------------|  |  |------------------------|
  features built from here           ^  scoring date (prediction time)
                                     |
                                     `- nothing after this line may enter a feature
```

```sql
-- One row per active subscriber per weekly scoring date; label = cancels within 30 days.
SELECT s.customer_id,
       d.score_date,
       CASE WHEN c.cancel_date >  d.score_date
             AND c.cancel_date <= d.score_date + INTERVAL '30 days' THEN 1 ELSE 0 END AS churned_30d
FROM scoring_dates d
JOIN subscriptions s
  ON s.start_date <= d.score_date
 AND (s.end_date IS NULL OR s.end_date > d.score_date)          -- active at prediction time only
LEFT JOIN cancellations c ON c.customer_id = s.customer_id
WHERE d.score_date <= CURRENT_DATE - INTERVAL '30 days';          -- outcome window fully observed
```

Rules that keep labels honest:
- **Population = who you would score.** Only rows that were eligible at prediction time (active, not already
  churned, not already flagged). Training on everyone inflates scores and breaks at deployment.
- **Window fully observed.** Drop scoring dates whose outcome window is not over yet; otherwise recent rows look
  negative (right censoring). If waiting is not an option, use survival analysis.
- **Voluntary vs involuntary.** "Cancelled" mixes customers who chose to leave with failed payments; split them
  if the action differs.
- **Snapshot repetition.** Weekly snapshots of the same customer are correlated; group by customer in CV
  ([cross-validation-strategy-designer](../cross-validation-strategy-designer/SKILL.md)).
- **Label delay** sets the retraining and monitoring cadence; if it is months, add a faster leading indicator.

Window sizing, censoring, label delay, proxy labels and multi-snapshot designs:
[label-design-and-windows.md](references/label-design-and-windows.md).

## Features Must Exist at Prediction Time

For every source ask: *when is this field written, and can it change after the prediction?*

| Smell | Example | Why it leaks |
|-------|---------|--------------|
| Outcome-side fields | `cancellation_reason`, `refund_issued`, `chargeback_flag` | written because the event happened |
| Final/current-state columns | `account_status`, `last_login` read today for an old snapshot | values overwritten after prediction time |
| Aggregates over all time | `total_tickets` computed today | includes the future relative to old scoring dates |
| IDs and timestamps that encode order | sequential IDs, `created_at` of the label record | correlated with the label by construction |
| Human decisions made with the outcome | "escalated", "manual review result" | the reviewer saw the answer |

Build features as-of the scoring date from event logs or point-in-time snapshots
([time-based-feature-builder](../time-based-feature-builder/SKILL.md)); scan a dataset for suspicious
predictors with [target-leakage-detector](../target-leakage-detector/SKILL.md).

## Framing Pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| Unactionable prediction | great AUC, no change in the KPI | start from the decision; drop predictions nobody can act on |
| Horizon shorter than reaction time | flagged customers have already left when called | predict earlier or longer horizon |
| Leakage by framing | AUC 0.99 in the notebook, 0.6 in production | rebuild features as-of prediction time |
| Proxy label drift | model optimises clicks, revenue falls | name the proxy gap; add a guardrail on the real goal |
| Feedback loop | model looks worse each retrain; labels shaped by past actions | random holdout, log actions and scores, uplift framing |
| Selection bias | trained on approved loans only, scoring all applicants | reject inference, randomised exploration, or restrict scope |
| Population mismatch | trained on all users, scored on new users only | train on the scored population |
| Too many decisions in one model | one score for call, email and discount | one model per decision, or a multi-output design |
| Goodhart | team games the metric (closes tickets early) | pair metric with guardrails; audit samples |
| Fairness blind spot | protected group gets more false positives | slice metrics by group from day one |

Long-form explanations with detection steps: [framing-pitfalls.md](references/framing-pitfalls.md).

## Output Format

When framing a problem, answer with:
1. **One-sentence framing** - "At `<prediction time>`, for each `<unit>`, predict `<label in a window>` so that
   `<who>` can `<action>` for the top `<capacity>`."
2. **Framing canvas** - the table above filled in, with unknowns marked `TBD (owner)`.
3. **Label definition** - SQL/pandas producing the label, the population filter and the outcome window.
4. **Task type and why**, plus the rejected alternatives (e.g. why not regression, why not uplift).
5. **Feature availability table** - source, when it is written, safe/unsafe.
6. **Baseline and metric** - today's process, the primary metric at the operating point, guardrails.
7. **Risks** - leakage, proxy gap, feedback loop, selection bias, fairness, each with a mitigation.
8. **Next steps** - feasibility check, baseline, first model; paste `frame_check.py` output when a spec exists.

## Scripts

```bash
python scripts/frame_check.py --template > spec.json     # filled-in example spec to edit
python scripts/frame_check.py spec.json                  # human-readable findings
python scripts/frame_check.py spec.json --json           # machine-readable
cat spec.json | python scripts/frame_check.py -          # stdin
```
Checks 14 rules: FR001-FR004 blocking (no decision, unmeasurable target, no unit, no prediction time),
FR005-FR008 high (no horizon or horizon shorter than time to act, label delay far longer than horizon, features
written after prediction time or named like outcomes, no baseline), FR009-FR012 medium (model-score metric
instead of a decision metric, unknown action capacity, unexplained proxy label, feedback loop without a
holdout), FR013-FR014 low (no owner, task type disagrees with the target wording). Verdict: NOT READY, NEEDS
WORK or READY TO PROTOTYPE. Exit codes: 0 no blocking/high findings, 1 blocking or high findings, 2 usage or
read error.

```bash
python scripts/target_profile.py data.csv --target churned
python scripts/target_profile.py data.csv --target price --json
python scripts/target_profile.py - --target label < data.csv
```
Infers the label kind (binary, multiclass, ordinal, count, continuous, ID-like, constant) and the task type,
prints the class balance or the distribution (quantiles, skew, zero share) and the metric family, and warns
about too few minority examples, missing labels, rare classes, heavy skew, zero inflation and extreme values.
Standard library only. Exit codes: 0 usable target, 1 blocking problem (constant, ID-like, < 30 minority
examples), 2 usage or read error.

## Additional Resources

| File | Content |
|------|---------|
| [framing-canvas.md](references/framing-canvas.md) | The canvas field by field, plus filled canvases for churn, demand, fraud, lead scoring, ticket routing, maintenance, credit and pricing |
| [task-type-catalog.md](references/task-type-catalog.md) | Every task type: label shape, loss, metrics, first model, traps, when to reframe |
| [label-design-and-windows.md](references/label-design-and-windows.md) | Observation/outcome windows, gaps, censoring, label delay, proxies, multi-snapshot datasets, label SQL patterns |
| [framing-pitfalls.md](references/framing-pitfalls.md) | Unactionable predictions, leakage by framing, feedback loops, selection bias, Goodhart, fairness, with detection steps |
| [framing-review-checklist.md](references/framing-review-checklist.md) | Interview questions for stakeholders, review checklist, spec fields for `frame_check.py` |
