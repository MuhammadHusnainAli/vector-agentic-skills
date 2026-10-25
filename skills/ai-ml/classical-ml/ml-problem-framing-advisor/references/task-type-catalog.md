# Task Type Catalog

For each task: what the label looks like, the loss to train with, the metric to report, a sensible first model,
and the traps that make teams pick the wrong framing.

## Binary classification
- **Label:** 0/1 event in a window (`defaulted_12m`, `churned_30d`, `clicked`).
- **Loss:** log loss (cross-entropy). Class weights only if you will not use calibrated probabilities.
- **Metrics:** ROC-AUC (ranking quality, insensitive to prevalence), PR-AUC / average precision (rare positives),
  recall or precision at capacity (top-K), expected cost at a threshold, Brier and calibration when the
  probability itself drives a decision (pricing, expected loss).
- **First model:** logistic regression with one-hot categoricals and scaled numerics; then gradient boosting.
- **Traps:** accuracy on imbalanced data; threshold 0.5 by default; probabilities distorted by resampling.

## Multiclass classification
- **Label:** one of K mutually exclusive classes.
- **Loss:** softmax cross-entropy.
- **Metrics:** macro-F1 (every class counts), weighted-F1 / accuracy (frequent classes dominate), top-k
  accuracy (routing with a human picking from suggestions), confusion matrix for costly swaps.
- **Traps:** classes that are not mutually exclusive (use multilabel: one binary per label); long tail of rare
  classes (merge into "other" or a hierarchy).

## Multilabel classification
- **Label:** any subset of labels (tags, symptoms).
- **Loss:** one binary cross-entropy per label.
- **Metrics:** micro/macro F1, Hamming loss, per-label PR-AUC.

## Ordinal
- **Label:** ordered classes (1-5 stars, severity grades).
- **Options:** regression on the scale then round (often good enough), ordinal logistic (cumulative link),
  or K-1 binary "greater than k" models.
- **Metrics:** MAE on the scale, quadratic weighted kappa, Spearman.
- **Traps:** treating as nominal multiclass throws away the order.

## Regression
- **Label:** continuous quantity in a window (`spend_next_90d`, `delivery_minutes`).
- **Loss choice:**
  | Target shape | Loss |
  |--------------|------|
  | Symmetric, few outliers | squared error |
  | Outliers you do not want to chase | Huber or absolute error |
  | Strictly positive, right-skewed | log1p target + squared error, or Gamma |
  | Many exact zeros plus a positive tail | Tweedie (power 1.1-1.9) or hurdle model |
  | Need an interval / a percentile | quantile (pinball) loss |
- **Metrics:** MAE, RMSE, WAPE/MAPE (business), R² (comparison only), calibration by decile.
- **Traps:** log-target models predict the geometric mean (biased low) unless corrected; MAPE explodes near 0.

## Count regression
- **Label:** non-negative integers (claims, visits, defects).
- **Loss:** Poisson; negative binomial when variance >> mean; Tweedie for zero-heavy counts with exposure.
- **Exposure:** model rate per unit exposure (`log(exposure)` offset in GLMs, `sample_weight`/base margin in GBMs).
- **Metrics:** Poisson deviance, MAE.

## Forecasting
- **Label:** future values of a series at horizons h = 1..H.
- **Framings:** local statistical models per series (ETS, ARIMA), global ML models on lag features across many
  series (LightGBM), hierarchical reconciliation.
- **Metrics:** MASE (scale-free, vs seasonal naive), WAPE, sMAPE, pinball loss for quantiles, bias.
- **Traps:** random CV (must be rolling-origin); features known only in hindsight (actual weather); censored
  demand during stock-outs.

## Ranking / learning to rank
- **Label:** graded relevance per (query, item), or implicit feedback (clicks, purchases).
- **Loss:** pointwise (regression/classification), pairwise (RankNet), listwise (LambdaMART on NDCG).
- **Metrics:** NDCG@k, MAP, MRR, recall@k.
- **Traps:** position bias in clicks; evaluating per row instead of per query.

## Time-to-event (survival)
- **Label:** `(duration, event_observed)`; censored rows still carry information.
- **Models:** Kaplan-Meier (descriptive), Cox PH, accelerated failure time, random survival forest, GBM with
  Cox or AFT objective.
- **Metrics:** concordance index, time-dependent AUC, integrated Brier score.
- **Use when:** windows cannot be fully observed, or "when" matters more than "whether".

## Uplift / treatment effect
- **Label:** outcome plus treatment indicator, ideally from a randomised experiment.
- **Models:** two-model (T-learner), S-learner, X-learner, class transformation, causal forests.
- **Metrics:** Qini coefficient, AUUC, uplift at top-k.
- **Use when:** the decision is whether to intervene and the intervention changes the outcome.

## Anomaly detection
- **Label:** none, or very few confirmed anomalies.
- **Models:** robust statistics (median/MAD), Isolation Forest, LOF, one-class SVM, autoencoders, forecasting
  residuals for time series.
- **Metrics:** precision@k on a reviewed sample, alert volume, time to detect.
- **Reframe as classification** once you have a few hundred labelled positives.

## Clustering
- **Label:** none. An exploratory tool, not a decision.
- **Make it actionable:** a segment must map to a different action; validate stability and business meaning.

## Recommendation
- **Label:** user-item interactions (explicit ratings or implicit events).
- **Models:** popularity, item-kNN, matrix factorisation (ALS, BPR), two-tower retrieval plus a ranker.
- **Metrics:** recall@k, NDCG@k, coverage, novelty; online CTR/conversion.

## Choosing between neighbours

| Choice | Prefer the first when | Prefer the second when |
|--------|----------------------|------------------------|
| Classification vs regression | the decision is a yes/no or a threshold on a quantity | the size of the outcome changes the action |
| Classification vs survival | the window is fully observed for all training rows | many rows are censored or timing matters |
| Classification vs ranking | each case is judged independently | only the order within a query/list matters |
| Classification vs uplift | the action does not change the outcome | the action is the intervention you are deciding on |
| Regression vs forecasting | rows are independent units | the same series continues over time |
| Anomaly vs classification | < ~100 confirmed positives | enough labelled positives to learn from |
| Clustering vs classification | no outcome to predict, exploring structure | a label exists (use it) |
