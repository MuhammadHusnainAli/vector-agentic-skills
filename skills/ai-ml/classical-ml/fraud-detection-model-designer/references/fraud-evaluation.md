# Fraud Evaluation

## Why not accuracy or ROC AUC alone

At 0.5% fraud, predicting "never fraud" is 99.5% accurate. ROC AUC is dominated by the huge negative class:
0.98 can still mean most alerts are false. Average precision (area under the PR curve) and metrics at the
operating point reflect what analysts and customers experience. The random-baseline AP equals the fraud
rate.

## Operating-point metrics

| Metric | Definition | Audience |
|--------|------------|----------|
| Precision (hit rate) | true frauds / alerts | analysts: share of useful work |
| Recall (detection rate) | frauds caught / all frauds | risk teams |
| Value detection rate | fraud amount caught / total fraud amount | finance: the money metric |
| FPR / false-positive ratio | good transactions alerted / good transactions, or false : true alerts | customer experience |
| Alerts per day | volume at the threshold | operations capacity |

Report them at business-relevant cut-offs: the top 0.5-5% of scores, FPR 0.1% / 1%, or the capacity limit.

## Cost model (fraud_eval.py)

```
cost(threshold) = sum over missed frauds of amount x loss_rate
                + number of alerts x review_cost
                + number of false alerts x friction_cost
```
- `loss_rate`: share of the fraud amount actually lost (recoveries and liability shift lower it).
- `review_cost`: analyst minutes x cost per minute, or the cost of step-up authentication.
- `friction_cost`: lost sales, support calls and churn from declining or challenging good customers. It is
  often underestimated, so ask the business.
Compare with "no model" (lose all fraud) and "review everything". Report the savings and the sensitivity of
the optimal threshold to the cost assumptions (rerun with different `--friction-cost`).

## Capacity

Analyst teams handle a fixed number of alerts per day. `--alerts-per-day` finds the cheapest threshold within
the capacity. When the cost-optimal threshold exceeds it, quantify the money left on the table. That is the
case for more analysts, or for automating the clear cases.

## Label delay in evaluation

- Evaluate only on periods whose labels have matured (for example, 60-90 days after the transactions for
  chargebacks).
- Recent weeks show artificially low fraud rates and recall. `fraud_eval.py` prints the fraud rate by week,
  and a sudden drop near the end usually means immature labels, not success.

## Stability

Average precision per week varies a lot when frauds per week are few (it ranged 0.44-0.97 on the fixture).
Use rolling 4-week windows or confidence intervals (bootstrap over days) before calling a degradation.

## Comparing models

Use the same out-of-time test period and the same label maturity. Compare AP, the value detection rate at
the same alert volume, and the cost at each model's own optimal threshold. Use paired bootstrap over days for
significance.
