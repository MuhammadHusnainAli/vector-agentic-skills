# Pilot Design and the Go/No-Go Write-up

## Feasibility scorecard template

| Dimension | Status | Evidence | Mitigation / owner |
|-----------|--------|----------|--------------------|
| Framing | ok | decision, unit, label window agreed (link) | - |
| Volume | risk | 82 positives, EPV 7.5 | restrict to 8 features; pool 6 more months (data eng, 2 wks) |
| Labels | ok | label rate stable by month; kappa 0.78 | - |
| Signal | ok | best OOF AUC 0.69 (tenure) | - |
| Leak suspects | blocking until resolved | refund_issued AUC 0.95; cancellation_reason missingness AUC 1.0 | drop; confirm write times |
| Availability | risk | support tickets only in warehouse (24 h lag) | accept 24 h staleness |
| Measurability | risk | AUC CI half-width 0.06 | report recall@400 with CI; extend test window |
| Value | ok | lift ~$10k/week at prec@400 0.40 vs 0.25 | - |

Verdict rule: any blocking -> NO-GO (or "GO after X"); any risk -> GO WITH RISKS with named mitigations; all ok
-> GO.

## Pilot stages

### Stage 0: desk check (1-3 days)
- Framing check, feasibility scan, sample-size arithmetic, value model.
- Output: scorecard and the decision to spend on stage 1.

### Stage 1: offline prototype (1-2 weeks)
- Time-based holdout mirroring deployment (train on months 1-12, test on 13-15).
- Baseline (current rule, dummy, single feature) and one simple model (logistic regression or a small GBM).
- Report the primary metric at the operating point with a CI.
- Kill if: model lift over the baseline is within the CI, or the lift is below break-even.

### Stage 2: shadow mode (2-4 weeks)
- Score live traffic without acting. Log features, scores, latency.
- Check: feature availability rate, latency p99, score distribution vs offline, drift.
- Kill if: key features missing for > X% of rows, latency over budget, or live scores look very different from
  offline ones.

### Stage 3: controlled test (4-8 weeks)
- Randomise: act on the model's top-K in the treatment arm, the baseline's top-K in control (or a random
  holdout with no action, to measure the action's effect).
- Primary metric: the business outcome (saves, fraud $ prevented), with guardrails.
- Decide with a pre-registered analysis plan and sample size.

## Kill criteria examples

- "Recall@400 under the model is not at least 20% higher than the rule, with the CI excluding 0."
- "Fewer than 90% of scored rows have the top-5 features populated in shadow mode."
- "p99 latency > 50 ms after optimisation."
- "Uplift in saves per 400 calls < 5 in the controlled test."
- "Fairness: false positive rate ratio between regions outside 0.8-1.25."

## Go/No-Go write-up template

```
# Feasibility: <project>

Verdict: GO WITH RISKS - signal and value are adequate; two probable leaks must be removed and volume is thin.

## Framing
<one-sentence framing>; label = <definition>; horizon <h>; capacity <K>.

## Scorecard
<table above>

## Data needed
<rows/positives/months>; collection time <x weeks> (sample_size.py rate ...).

## Value
Baseline <metric>, model target <metric>; lift <$/period>; ceiling <$/period>; break-even prec@K <x>.

## Pilot plan
Stage 1 by <date>, stage 2 by <date>, kill criteria: <list>.

## What would change the answer
<for NO-GO: new data source, longer window, rules first>
```

## Common NO-GO outcomes and the alternative

| Reason | Alternative |
|--------|-------------|
| Too few positives | rules + label collection; anomaly detection; widen the event definition |
| No signal | new data sources; qualitative research into what drives the outcome |
| Signal only after the event | reframe to a later decision point, or a different decision |
| Capacity too small for value | improve the action (better offer) before the targeting |
| Labels unreliable | fix the labelling process; measure kappa again |
| No consumer system | integration work first; the model can wait |
