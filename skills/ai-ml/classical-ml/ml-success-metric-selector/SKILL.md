---
name: ml-success-metric-selector
description: "Choose the metric that defines success for an ML model, and the guardrails around it, from the decision it serves: precision/recall@K for capacity-bound actions, expected cost at the cost-optimal threshold for asymmetric errors, PR-AUC vs ROC-AUC for rare events, log loss/Brier/ECE when probabilities are consumed, macro- vs weighted-F1 for multiclass, MAE vs RMSE vs WAPE vs MAPE vs Poisson deviance for regression, MASE/RMSSE and pinball loss for forecasts, NDCG/MRR/recall@k for ranking and recommendation, concordance for survival, Qini/AUUC for uplift. Computes the full metric panel from a predictions CSV (scikit-learn-identical numbers) and finds the cost-minimising threshold. Use when someone asks which metric to use, whether accuracy/AUC/F1/MAPE is right, how to set a threshold from costs, how to turn a business KPI into an offline metric, or wants every metric for a set of predictions."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# ML Success Metric Selector

Pick the metric from the decision, not from habit. One **primary** metric measured at the operating point
the business will use (top K, a threshold, a service level), a few **secondary** metrics that explain it, and
**guardrails** that must not get worse. `scripts/pick_metric.py` recommends all three from the problem's
traits with the reasons and the metrics to avoid; `scripts/metric_report.py` computes the full panel from a
predictions file, including precision/recall@K, calibration, and the cost-minimising threshold.

## Trigger Conditions

Activate this skill when the user:
- Asks "which metric should I use?", "is accuracy / AUC / F1 / MAPE right here?", "why is my 98% accurate model useless?"
- Needs to choose a threshold from costs, a review capacity or a target precision
- Must translate a KPI (revenue, saved customers, stock-outs, fraud losses) into an offline metric
- Wants every metric for a predictions file, or numbers that disagree with another tool explained
- Is writing the success criteria for a project brief, a model card or a launch review

Deep dives elsewhere: thresholds and class imbalance in
[imbalanced-class-handler](../imbalanced-class-handler/SKILL.md); comparing models statistically in
[ml-model-comparison-reporter](../ml-model-comparison-reporter/SKILL.md); ranking metrics in
[learning-to-rank-model-builder](../learning-to-rank-model-builder/SKILL.md).

## Workflow

```
1. DECISION  -> what action, at what capacity, with which error costs (from the framing)
2. PICK      -> python scripts/pick_metric.py --task binary --prevalence 0.02 --capacity 400 --cost-fp 8 --cost-fn 600
3. BASELINE  -> compute the same metric for the current rule / dummy (ml-baseline-model-builder)
4. MEASURE   -> python scripts/metric_report.py preds.csv --k 400 --cost-fp 8 --cost-fn 600
5. THRESHOLD -> from capacity (top K), costs (cost-optimal), or a constraint (precision >= x); fix it on validation
6. GUARD     -> slice metrics by segment; check calibration if probabilities are used
7. WRITE     -> "Primary: recall@400 >= 0.45 on the Q3 holdout (rule: 0.30); guardrails: ..."
```

## Classification: Decision -> Metric

| The decision looks like | Primary metric | Why not the usual one |
|-------------------------|----------------|-----------------------|
| Act on the top K cases (calls, reviews, audits) | precision@K / recall@K, lift@K | AUC averages over all thresholds you will never use |
| Act when the score crosses a threshold; FP/FN costs known | expected cost or net value at the cost-optimal threshold | F1 ignores true negatives and assumes equal costs |
| Rare positives (< ~10%), no fixed K yet | PR-AUC (average precision) | ROC-AUC stays high while precision collapses |
| Need "catch at least 90% of fraud" | precision at recall = 0.90 (or the reverse) | a single summary hides the constraint |
| Probability is consumed (pricing, expected loss, risk bands) | log loss + calibration (Brier, ECE, reliability curve) | AUC is blind to calibration |
| Balanced classes, ranking quality, no operating point | ROC-AUC | fine here; still report the threshold metrics you will use |
| Several classes, all equally important | macro-F1, per-class recall | accuracy is dominated by frequent classes |
| Several classes, frequency = importance | accuracy or weighted-F1 | macro-F1 over-weights rare classes |
| Humans pick from suggestions | top-k accuracy | top-1 accuracy undervalues a useful shortlist |

**Accuracy is almost never the primary metric.** At 2% prevalence, "always no" is 98% accurate.

## Thresholds Come From the Decision

| Source | Rule | Example |
|--------|------|---------|
| Capacity | take the top K by score per period | 400 calls/week -> threshold = 400th highest score |
| Costs, calibrated probabilities | act if `p > C_fp / (C_fp + C_fn)` | FP $8, FN $600 -> p > 0.013 |
| Costs, uncalibrated scores | scan thresholds on validation, minimise `FP*C_fp + FN*C_fn` | `metric_report.py --cost-fp 8 --cost-fn 600` |
| Constraint | highest threshold meeting recall >= r (or precision >= p) | "catch 90% of fraud" |
| Fairness | per-group thresholds only when policy allows | equal opportunity constraint |

Fix the threshold on validation data, report the metric on the test set. Choosing it on the test set makes
the reported number optimistic. When `metric_report.py` prints a "best threshold" far from the Bayes
threshold `C_fp/(C_fp+C_fn)`, the scores are not calibrated (see the ECE line).

## Regression and Forecasting: Error Shape -> Metric

| Situation | Primary | Avoid |
|-----------|---------|-------|
| Typical error in units, robust to outliers | MAE | RMSE as primary when outliers are noise |
| Large errors are disproportionately costly | RMSE | MAE (hides rare big misses) |
| Business reporting across products of different size | WAPE = Σ|e| / Σ|y| | MAPE averaged over items (small items dominate) |
| Targets near or at zero | MAE, WAPE | MAPE (undefined / explodes), sMAPE (asymmetric, unstable) |
| Counts or Tweedie-like targets (claims, visits) | Poisson / Tweedie deviance | RMSE (dominated by large counts) |
| Many series of different scales | MASE or RMSSE vs seasonal naive | per-series MAE averages |
| Intervals, service levels, safety stock | pinball (quantile) loss, coverage | point metrics only |
| Systematic over/under-forecasting matters | bias = Σe / Σy as a guardrail | absolute-error metrics alone (hide bias) |
| Comparing models on one dataset | R² as a secondary | R² across datasets or for business reporting |

MAE is minimised by the median, RMSE by the mean: train with the loss that matches the metric (L1 / quantile
vs squared error), or the model optimises something else than you report.

## Other Tasks

| Task | Primary | Secondary / guardrails |
|------|---------|------------------------|
| Ranking / search | NDCG@k (k = visible results) | MRR, MAP, recall@k; zero-result rate; online CTR |
| Recommendation | recall@k or NDCG@k on a time-based holdout | coverage, novelty, popularity bias; online conversion |
| Anomaly detection | precision@k on reviewed alerts (alert budget) | recall on known incidents, time to detect |
| Survival | concordance (Harrell's C; Uno's C under heavy censoring) | time-dependent AUC at the decision horizon, integrated Brier |
| Uplift | Qini coefficient / AUUC on randomised data | uplift@K, incremental outcome per treatment cost |
| Clustering | stability + business usefulness | silhouette, Davies-Bouldin as diagnostics only |

## From KPI to Offline Metric

```
KPI (what leadership tracks)      ->  decision metric (what the model changes)  ->  offline metric (what you can compute today)
saved revenue per month           ->  saves per 400 retention calls             ->  recall@400 on churners, time-based holdout
fraud losses                      ->  fraud $ blocked at 0.2% false-decline rate ->  value-weighted recall at FPR 0.2%
stock-outs and waste              ->  safety stock for a 95% service level      ->  pinball loss at q=0.95, WAPE, bias
```

Every offline metric needs an online counterpart (A/B test or holdout) because offline metrics ignore the
action's effect. Templates and worked translations: [business-metric-translation.md](references/business-metric-translation.md).

## Guardrails

Always state what must not get worse while the primary improves:
- **Segments:** the primary metric per key segment and protected group (no group below a floor).
- **Calibration:** ECE or reliability curve when probabilities are used.
- **Load:** false positives per period handed to people.
- **Stability:** score distribution drift (PSI) and metric over time.
- **Business side effects:** complaints, approval rate, margin, latency.

## Output Format

When selecting metrics, answer with:
1. **Primary metric** at the operating point, with the target value and the baseline value.
2. **Why** - one sentence tying it to the decision; the tempting metric it replaces and why that misleads.
3. **Threshold rule** - capacity, cost-optimal or constraint, chosen on validation.
4. **Secondary metrics** that explain movements in the primary.
5. **Guardrails** with limits.
6. **Measured panel** - `metric_report.py` output for the current model and the baseline, when predictions exist.
7. **Online metric** that confirms the offline one after launch.

## Scripts

```bash
python scripts/pick_metric.py --task binary --prevalence 0.02 --capacity 400 --population 50000
python scripts/pick_metric.py --task binary --cost-fp 8 --cost-fn 600 --probabilities
python scripts/pick_metric.py --task multiclass --classes-equal
python scripts/pick_metric.py --task regression --outliers --near-zero --quantiles
python scripts/pick_metric.py --task forecast --many-series --near-zero --json
```
Tasks: binary, multiclass, multilabel, regression, count, forecast, ranking, recommendation, anomaly,
survival, uplift. Prints PRIMARY with the reason, the Bayes threshold when costs are given, secondary metrics,
guardrails, and metrics to avoid with the reason (accuracy at low prevalence, F1 at 0.5, MAPE near zero, ROC-AUC
alone for rare events, RMSE on ratings for top-k recommendation, response AUC for uplift). Exit codes: 0
printed, 2 usage error.

```bash
python scripts/metric_report.py preds.csv                                # y_true, y_score columns
python scripts/metric_report.py preds.csv --k 400 --threshold 0.3 --beta 2
python scripts/metric_report.py preds.csv --cost-fp 8 --cost-fn 600 --json
python scripts/metric_report.py preds.csv --true-col label --score-col p_churn
python scripts/metric_report.py reg.csv --regression --pred-col y_pred --segment region
```
Binary: ROC-AUC, tie-aware PR-AUC, log loss, Brier, ECE with the reliability table (JSON), precision /
recall / lift at top-K (default K = number of positives), confusion matrix, precision, recall, F1, F-beta,
balanced accuracy and flagged share at the threshold, expected cost per row, the cost-minimising threshold
(scanned on this data: optimistic if this is the test set), the cost of flagging nobody / everybody, and the
positive rate per score decile. Regression: MAE, RMSE, MedAE, bias, R2, WAPE, MAPE (zeros skipped and
counted), sMAPE, and per-segment MAE and bias. Values match scikit-learn. Exit codes: 0 computed, 2 usage or
data error.

## Additional Resources

| File | Content |
|------|---------|
| [classification-metrics.md](references/classification-metrics.md) | Definitions, formulas and when each misleads: accuracy, balanced accuracy, precision/recall/F-beta, ROC-AUC, PR-AUC, log loss, Brier, ECE, MCC, kappa, top-k, multiclass averaging, sklearn calls |
| [regression-and-forecast-metrics.md](references/regression-and-forecast-metrics.md) | MAE, RMSE, MedAE, R2, MAPE, sMAPE, WAPE, MASE, RMSSE, pinball, coverage, deviances, bias; loss/metric alignment |
| [ranking-and-other-metrics.md](references/ranking-and-other-metrics.md) | NDCG, MAP, MRR, recall@k, coverage, concordance, time-dependent AUC, Qini/AUUC, anomaly alert metrics |
| [business-metric-translation.md](references/business-metric-translation.md) | KPI -> decision -> offline metric chains, cost matrices, threshold policies, guardrails, offline/online agreement |
