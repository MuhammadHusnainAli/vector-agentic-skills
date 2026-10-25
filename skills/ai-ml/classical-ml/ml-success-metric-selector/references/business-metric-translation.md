# From Business KPI to Offline Metric

## The chain

```
KPI  ->  decision metric  ->  offline proxy  ->  online confirmation
```

| KPI | Decision | Offline metric | Online metric |
|-----|----------|----------------|---------------|
| Monthly churn rate | who gets a retention call (400/week) | recall@400 of 30-day churners (time holdout) | saves per 400 calls vs holdout group |
| Fraud losses | block / step-up at authorisation | value-weighted recall at 0.2% FPR | fraud $ per $1M volume; false-decline rate |
| Gross margin from promotions | who gets a coupon | Qini / uplift@K | incremental margin in an A/B test |
| Revenue from sales pipeline | rep queue order | opportunities in top 750 leads/day | pipeline $ per rep-hour |
| Stock-outs and waste | order quantity | pinball loss at the service quantile, bias | stock-out rate, waste rate |
| Support resolution time | ticket routing | top-1 accuracy, reassignment rate | median time to resolution |
| Search conversion | ranking | NDCG@10 on judged queries | conversion per search session |
| Credit losses | approve / limit | AUC + calibration by score band | default rate per band, approval rate |

## Cost matrix workshop

Fill with the business owner; use ranges when unsure and test the threshold's sensitivity.

| | Predicted no action | Predicted action |
|-|---------------------|------------------|
| **Event would not happen** | 0 | C_fp: action cost + side effects (annoyance, discount given away) |
| **Event would happen** | C_fn: loss not prevented | C_tp: action cost − value saved x success rate |

Example (retention): call cost $8; annoyance cost $2; saved-customer value $600 x 30% save rate = $180.
C_fp = $10, C_tp = $8 − $180 = −$172, C_fn = $0 relative to doing nothing (the loss happens either way).
Act when `p·(C_fn − C_tp) > (1 − p)·C_fp` -> `p·172 > (1 − p)·10` -> p > 0.055.

## Threshold policies

| Policy | When | Implementation |
|--------|------|----------------|
| Top-K per period | fixed capacity | rank, take K; re-evaluate K when capacity changes |
| Cost-optimal | costs known, capacity flexible | calibrated p > C_fp / (C_fp + C_fn − C_tp) |
| Constraint | regulation or SLA ("≥ 95% recall") | highest threshold meeting it on validation |
| Bands | human tiers (auto-approve / review / decline) | two thresholds; measure each band's precision |
| Per-segment | different costs per segment | segment-specific thresholds; check fairness rules first |

Recheck the threshold after retraining: a new model's score distribution shifts even at the same AUC.

## Guardrail catalogue

| Area | Guardrail |
|------|-----------|
| Fairness | TPR/FPR ratio between groups within 0.8-1.25; per-group calibration |
| Customer | complaint rate, unsubscribe rate, false-decline rate |
| Operations | alerts per analyst per day, queue backlog |
| Business | margin, approval rate, average order value |
| Model health | PSI of scores and top features < 0.2, metric by week, latency p99 |

## Offline/online disagreement

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Offline better, online flat | the action does not change outcomes for the selected cases | uplift framing, better action |
| Offline better, online worse | leakage or train/serve skew | check features at serving time; shadow mode |
| Online effect shrinks over weeks | feedback loop or novelty effect | holdout groups, longer test |
| Offline metric noisy | small test set | CI, longer holdout window |

## Writing the success criteria

```
Primary: recall@400 per week of customers who cancel within 30 days, on the Apr-Jun 2024 time holdout.
  Target >= 0.45 (current rule 0.30). Threshold: top 400 by score each Monday.
Secondary: PR-AUC, ROC-AUC, lift@400.
Guardrails: complaint rate of called customers <= 1.5%; recall@400 for each region >= 0.35;
  score PSI vs training < 0.2.
Online: saves per 400 calls vs a 5% untreated random holdout over 6 weeks; launch if +5 saves/week with
  95% CI excluding 0.
```
