---
name: ml-feasibility-assessor
description: "Decide GO, GO WITH RISKS or NO-GO for an ML project before building it: enough labelled rows and minority examples, events per feature, label quality and coverage, history length and drift, single-feature signal (out-of-fold AUC / Spearman) and suspicious near-perfect predictors, data availability at prediction time, latency and serving constraints, the value ceiling given action capacity, and the cost of being wrong. Includes sample-size arithmetic for metric confidence intervals, AUC standard errors (Hanley-McNeil), McNemar test sizes and data collection time. Use when someone asks whether ML can work for a problem, whether there is enough data, how many labels or positives are needed, whether a dataset has signal, or wants a feasibility review, pilot plan or go/no-go recommendation."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# ML Feasibility Assessor

Feasibility is a set of cheap checks that kill bad projects in a day instead of a quarter. Given a framed
problem (see [ml-problem-framing-advisor](../ml-problem-framing-advisor/SKILL.md)), check whether the data
can support it, whether there is any signal, whether the metric can even be measured precisely, whether
production can serve it, and whether the value at the action's capacity justifies the cost.
`scripts/feasibility_scan.py` scores a CSV on volume, labels, signal and coverage;
`scripts/sample_size.py` answers "how many rows / positives do we need?".

## Trigger Conditions

Activate this skill when the user:
- Asks "can ML solve this?", "do we have enough data?", "is there signal in this dataset?"
- Asks how many labels, positives or months of history are needed, or how long collection will take
- Wants a go/no-go recommendation, a pilot plan or a feasibility section for a proposal
- Has a dataset and wants a quick sanity pass before modelling (label rate, missingness, single-feature AUC)
- Got an implausibly good first result and wants to know if it is real

## Workflow

```
1. FRAMING   -> confirm decision, unit, prediction time, label window (send gaps back to framing)
2. DATA      -> python scripts/feasibility_scan.py data.csv --target y --time-col ts --drop id
3. VOLUME    -> labelled rows, minority count, EPV; python scripts/sample_size.py epv/auc/metric
4. SIGNAL    -> best out-of-fold single-feature signal; > 0.9 AUC means "leak?", < 0.55 means "weak"
5. LABELS    -> missing labels, drift by month, noise estimate, label delay
6. SERVING   -> features available at prediction time, latency budget, data freshness
7. VALUE     -> capacity x lift x value per correct action - cost of errors - build/run cost
8. DECIDE    -> GO / GO WITH RISKS (named mitigations) / NO-GO (what would change the answer)
```

## The Seven Feasibility Dimensions

| Dimension | Question | Quick check | NO-GO signal |
|-----------|----------|-------------|--------------|
| Framing | Is there a decision, unit, prediction time and label? | `frame_check.py` from the framing skill | any blocking framing gap |
| Volume | Enough labelled rows and positives? | rows, minority count, EPV | < 50 minority examples; < 100 rows |
| Labels | Are labels correct, complete, stable? | missing share, monthly rate, double-label agreement | label definition changes; > 20% noise |
| Signal | Does anything predict the label? | out-of-fold single-feature AUC / Spearman | best < 0.55 AUC and no domain hypothesis |
| Availability | Do features exist at prediction time, at serving latency? | feature-source table | key signal only available after the event |
| Measurability | Can the metric be estimated precisely enough to decide? | CI of the metric (`sample_size.py`) | CI wider than the lift you need |
| Value | Does lift x capacity pay for build and run cost? | value model below | ceiling below cost even at perfect accuracy |

## Volume Rules of Thumb

| Situation | Rough minimum | Why |
|-----------|---------------|-----|
| Binary classification, logistic / linear | 10-20 minority events per feature (EPV), count one-hot levels | stable coefficients |
| Gradient boosting on tabular data | a few hundred minority events; thousands of rows | trees need many examples per split |
| Evaluating precision/recall to +/-3 points | ~900 cases in the metric's denominator | binomial CI |
| AUC CI half-width 0.03 | ~300+ positives (depends on AUC and class ratio) | Hanley-McNeil |
| Telling two models apart by 2-3 points accuracy | ~1,000-3,000 paired test rows | McNemar |
| Forecasting with yearly seasonality | >= 2 full seasonal cycles per series, or pool many series | estimate the seasonal pattern |
| Multiclass | >= 50-100 examples of the rarest class you care about | per-class metrics |

These are starting points, not laws: a learning curve on your data beats any rule
([learning-curve-diagnoser](../learning-curve-diagnoser/SKILL.md)).

```bash
python scripts/sample_size.py epv --events 82 --features 25          # too many features for 82 positives?
python scripts/sample_size.py auc --auc 0.80 --pos 82 --neg 318      # CI of the AUC you would report
python scripts/sample_size.py metric --p 0.6 --margin 0.05 --base-rate 0.02
python scripts/sample_size.py rate --needed 500 --rows-per-period 4000 --positive-rate 0.02
```

## Reading the Signal Check

`feasibility_scan.py` scores every column alone, out-of-fold, against the target:

| Best single-feature signal | Binary AUC | Read it as |
|----------------------------|-----------|------------|
| < 0.05 | < 0.525 | nothing measurable; only interactions could help - get new data or reframe |
| 0.05 - 0.15 | 0.525 - 0.575 | weak; expect modest lift; check the baseline first |
| 0.15 - 0.5 | 0.575 - 0.75 | typical real-world tabular signal: GO |
| 0.5 - 0.8 | 0.75 - 0.9 | strong; verify it is available at prediction time |
| > 0.8 | > 0.9 | **probably leakage** (outcome-side field, post-event timestamp, missingness filled after the event) |

It also scores *missingness* as a feature: a column that is filled only after the event (cancellation reason,
resolution code) gives a near-perfect "is missing" AUC. Treat every > 0.9 result as a leak until proven
otherwise with [target-leakage-detector](../target-leakage-detector/SKILL.md).

Weak univariate signal does not prove NO-GO: interactions, sequences and text can carry signal one column
cannot. It does mean the next step is a cheap baseline model
([ml-baseline-model-builder](../ml-baseline-model-builder/SKILL.md)), not a big build.

## Label Quality

| Check | How | Action |
|-------|-----|--------|
| Missing labels | share of rows with no label | find out why (censored? filtered?) before dropping |
| Label drift | label rate by month (`--time-col`) | definition change or real drift: validate on the latest period |
| Label noise | double-label 200 rows; Cohen's kappa | kappa < 0.6: fix guidelines before modelling |
| Label delay | time from prediction to known label | sets evaluation and retraining cadence |
| Selection | are labels only on reviewed/approved cases? | plan exploration or restrict the claim |

## Serving Feasibility

| Constraint | Ask | Typical blocker |
|------------|-----|-----------------|
| Latency | p99 budget at request time? | features need a 2-second warehouse query |
| Freshness | how stale can features be? | nightly batch but decisions every minute |
| Availability | is every feature present for every scored row? | key feature missing for new customers (cold start) |
| Volume | rows per second / per batch | expensive model per request |
| Explainability | regulated decision? | need adverse-action reasons: prefer monotone GBMs or GLMs |
| Integration | where does the score go? | no system can consume it |

## Value Ceiling

Do the arithmetic before modelling; a perfect model bounds the value.

```
value/period = capacity x precision_at_capacity x value_per_true_positive
             - capacity x (1 - precision_at_capacity) x cost_per_false_positive
             - run_cost/period
lift         = value(model) - value(baseline)        # always against the current process
ceiling      = value with precision_at_capacity = min(1, positives / capacity)
```

Example: 400 calls/week, 30% of called churners saved, a saved customer is worth $600, a call costs $8.
Baseline precision in the top 400 = 0.25, model = 0.40. Weekly saves rise from 400 x 0.25 x 0.3 = 30 to 48;
lift = 18 x $600 = $10,800 per week against the same call cost. The ceiling (precision 1.0) is 120 saves: even a
perfect model is worth at most ~$54k/week more than the baseline, so cap spend accordingly.

Worked models for fraud, demand and lead scoring: [value-and-cost-models.md](references/value-and-cost-models.md).

## Pilot Design

When the verdict is GO WITH RISKS, de-risk with a time-boxed pilot:
1. Two weeks: baseline + one simple model on a time-based holdout; report metric with CI.
2. Shadow mode: score live traffic without acting; check feature availability, latency and drift.
3. Controlled test: act on a random half of the top-K; measure the business outcome against the other half.
4. Kill criteria written up front: e.g. "lift < 10% over the rule at capacity" or "CI includes zero".

Templates and kill-criteria examples: [pilot-and-go-no-go.md](references/pilot-and-go-no-go.md).

## Output Format

When assessing feasibility, answer with:
1. **Verdict** - GO, GO WITH RISKS or NO-GO, in one sentence with the deciding reason.
2. **Scorecard** - the seven dimensions with status (ok / risk / blocking) and evidence (numbers from
   `feasibility_scan.py` and `sample_size.py`).
3. **Suspicious signals** - any > 0.9 AUC feature or missingness pattern, marked "probable leak".
4. **Data needed** - rows/positives/months required and how long collection takes.
5. **Value estimate** - capacity x lift x value, the ceiling, and the break-even lift.
6. **Pilot plan and kill criteria** - for GO WITH RISKS.
7. **What would change the answer** - for NO-GO (new data source, longer window, reframing, rules).

## Scripts

```bash
python scripts/feasibility_scan.py data.csv --target churned
python scripts/feasibility_scan.py data.csv --target churned --time-col signup_date --drop customer_id
python scripts/feasibility_scan.py data.csv --target price --top 20 --json
cat data.csv | python scripts/feasibility_scan.py - --target y
```
Reports rows, labelled rows, minority count and share, events per feature, history span; ranks every column by
out-of-fold single-feature signal (AUC for binary targets, |Spearman| for numeric, smoothed target means for
categoricals, plus an "is missing" AUC that catches columns filled only after the event); flags blocking
volume (< 100 rows, < 50 minority), weak signal, probable leaks (> 0.9 AUC), missing labels, monthly label
drift (> 3 standard errors), heavy missingness, near-constant columns and duplicates. Verdict GO, GO WITH
RISKS or NO-GO. Exit codes: 0 GO / GO WITH RISKS, 1 NO-GO, 2 usage or read error.

```bash
python scripts/sample_size.py metric --p 0.7 --margin 0.03 [--base-rate 0.05]
python scripts/sample_size.py auc --auc 0.80 --pos 82 --neg 318
python scripts/sample_size.py auc --auc 0.80 --half-width 0.03 --neg-per-pos 4
python scripts/sample_size.py compare --p-disagree 0.10 --diff 0.03 [--power 0.9]
python scripts/sample_size.py epv --events 82 --features 25 [--epv 20]
python scripts/sample_size.py rate --needed 500 --rows-per-period 4000 --positive-rate 0.02 --period week
```
Proportion-metric sample sizes, AUC confidence intervals and required positives (Hanley-McNeil), McNemar
paired test sizes, events-per-variable checks and collection time. `--confidence` 0.8/0.9/0.95/0.99. Exit
codes: 0 computed (and EPV met), 1 EPV not met, 2 usage error.

## Additional Resources

| File | Content |
|------|---------|
| [data-volume-and-sample-size.md](references/data-volume-and-sample-size.md) | Formulas and tables: EPV, binomial CIs, AUC SE, McNemar, learning-curve extrapolation, rare events, multiclass |
| [signal-and-label-checks.md](references/signal-and-label-checks.md) | Single-feature screens, why out-of-fold, leak signatures, label noise and kappa, drift by period, selection bias |
| [value-and-cost-models.md](references/value-and-cost-models.md) | Value-at-capacity models for churn, fraud, demand, lead scoring; break-even lift; cost of errors |
| [pilot-and-go-no-go.md](references/pilot-and-go-no-go.md) | Feasibility scorecard template, pilot stages, shadow mode, kill criteria, write-up template |
