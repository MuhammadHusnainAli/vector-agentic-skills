---
name: anomaly-detection-model-builder
description: "Build and evaluate anomaly detection for tabular, sensor and transaction data with few or no labels: define the anomaly type (point, contextual, collective), choose detectors (robust z-score/MAD and IQR rules, Mahalanobis with robust covariance, k-NN distance, LOF, Isolation Forest, one-class SVM, PCA reconstruction / autoencoders, forecasting residuals for time series), combine them by rank, explain each alert by its deviating features, set thresholds from an alert budget or the score distribution, and evaluate with precision@k, PR-AUC and recall on known incidents, or detector agreement when no labels exist. Includes pure-Python detectors (robust z, Mahalanobis, kNN, Isolation Forest, ensemble) and an evaluation script. Use when someone wants to find outliers, unusual transactions, faulty sensors or abnormal behaviour, asks Isolation Forest vs LOF vs one-class SVM, how to set the contamination or threshold, or how to evaluate an anomaly detector."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# Anomaly Detection Model Builder

Anomaly detection is ranking rows by how unusual they are and deciding how many to look at. The hard parts
are not the algorithm: defining **unusual relative to what** (a feature's normal range, the usual
combination of features, the entity's own history, the time of day), choosing the **alert budget**, and
**evaluating** with almost no labels. `scripts/anomaly_scores.py` scores rows with four complementary
detectors (robust z, Mahalanobis, k-NN distance, Isolation Forest) plus a rank ensemble, and explains each
alert; `scripts/anomaly_eval.py` measures precision at the alert budget when labels exist and detector
agreement and thresholds when they do not.

## Trigger Conditions

Activate this skill when the user:
- Wants to find outliers, unusual transactions, faulty sensors, abnormal user behaviour or data-quality errors
- Has few or no labels for the bad events (fraud before labels, new failure modes)
- Asks Isolation Forest vs LOF vs one-class SVM vs autoencoder, or how to set `contamination`
- Needs to explain why a row was flagged, or to choose a threshold for an alert queue
- Wants to evaluate an anomaly detector or compare detectors

Supervised fraud models (enough labels): [fraud-detection-model-designer](../fraud-detection-model-designer/SKILL.md);
PCA-based process monitoring (T², Q): [pca-dimensionality-reducer](../pca-dimensionality-reducer/SKILL.md);
rare-positive classification: [imbalanced-class-handler](../imbalanced-class-handler/SKILL.md); time-series
anomalies via forecasts: [time-series-forecasting-model-builder](../time-series-forecasting-model-builder/SKILL.md).

## Workflow

```
1. DEFINE     -> what is anomalous: point / contextual (given time, entity, segment) / collective (a sequence)
2. NORMAL     -> a reference period / population that is mostly normal; remove known incidents
3. FEATURES   -> deviations from the right context (vs own history, vs peer group, vs time of day)
4. SCORE      -> python scripts/anomaly_scores.py --train ref.csv --score new.csv --drop id --out scores.csv
5. BUDGET     -> how many alerts per day can be reviewed? threshold = score of the k-th row
6. EVALUATE   -> python scripts/anomaly_eval.py scores.csv --scores ... --label known --k 10 20 50
7. EXPLAIN    -> deviating features per alert; route to the owner; collect review outcomes as labels
8. ITERATE    -> labels accumulate -> semi-supervised -> supervised model (fraud-detection skill)
```

## Anomaly Types and Features

| Type | Example | Make it detectable by |
|------|---------|-----------------------|
| Point | a sensor reading of 999 | per-feature robust z / IQR, Isolation Forest |
| Combination | temperature and pressure each normal, together impossible | Mahalanobis, k-NN, Isolation Forest, PCA Q residual |
| Contextual | 3 a.m. login, high spend on a normally small card | features relative to context: ratio to entity mean, hour-of-day baselines |
| Collective | 50 small transactions in 5 minutes | window aggregates (velocity), sequence models |
| Drift / new regime | gradual sensor drift | residuals vs a forecast, change-point detection |

The best detector cannot see a contextual anomaly if the context is not in the features. Build "relative to
normal for this entity / time" features first (time-based-feature-builder).

## Detector Guide

| Detector | Finds | Scale | Notes |
|----------|-------|-------|-------|
| Robust z (median/MAD), IQR fences | extreme single features | any | transparent; misses combinations |
| Mahalanobis (robust covariance: MinCovDet) | unusual combinations, elliptical normal data | p < ~50 | assumes one Gaussian-ish blob |
| k-NN distance | isolated points | n < ~10^6 with an index | scale features; k 5-20 |
| Local Outlier Factor | points less dense than their neighbours | n < ~10^5 | handles varying density; `novelty=True` to score new data |
| Isolation Forest | easy-to-isolate points, mixed shapes | large n, many features | robust default; `contamination` only sets the threshold |
| One-class SVM | boundary of normal data | n < ~10^4 | sensitive to `nu`, `gamma`, scaling |
| PCA reconstruction / autoencoder | rows that break correlation structure | high-dimensional | autoencoders need lots of normal data |
| Forecast residuals | time-series spikes and level shifts | per series | seasonality-aware baselines |

On the sensor fixture (6 planted anomalies, one contextual) every detector reaches ROC-AUC >= 0.99; the
contextual one (temperature 76 and pressure 26.5, each plausible alone) is ranked high mainly by Mahalanobis.
The pure-Python Isolation Forest's PR-AUC (0.976) is in line with scikit-learn's (0.944) on the same data.

Code for each detector in scikit-learn / PyOD: [detector-recipes.md](references/detector-recipes.md).

## Thresholds and Alert Budgets

| Method | Use |
|--------|-----|
| Alert budget (top k per period) | analysts review a fixed number: threshold = score of the k-th row |
| Score percentile (99th, 99.5th) | expected anomaly rate known roughly |
| median + 3 MAD of the score | robust cut on raw (not rank-normalised) scores |
| `contamination=` | scikit-learn's way to place the threshold at a percentile; does not change the scores |
| Cost-based | expected loss per missed anomaly vs review cost, once some labels exist |

`anomaly_eval.py` prints each of these per score column.

## Evaluation With and Without Labels

| Situation | Measure |
|-----------|---------|
| Some labelled incidents | precision@k at the alert budget, recall on known incidents, PR-AUC |
| No labels | detector agreement (Spearman, top-k Jaccard), stability across reference periods, reviewer feedback rate |
| Synthetic checks | inject known anomalies (spikes, swapped columns, combinations) and measure recall |
| Online | share of alerts confirmed by reviewers; time to detect real incidents |

Few labels mean wide intervals: report counts ("caught 5 of 6 known incidents at 10 alerts/day"). Evaluation
design and label collection loops: [evaluation-and-operations.md](references/evaluation-and-operations.md).

## Explaining Alerts

For each alert show the features that deviate most (robust z per feature), the detector(s) that flagged it,
and the context (entity history, peer group). `anomaly_scores.py` lists the top three deviating features per
row; for Isolation Forest models in production, SHAP's TreeExplainer also works.

## Output Format

When building an anomaly detector, deliver:
1. **Definition** - anomaly type(s), unit (row / entity / window), reference period.
2. **Features** - context-relative features and scaling.
3. **Detectors** - chosen detectors and why; scores from `anomaly_scores.py`.
4. **Threshold** - alert budget and the matching cut-off.
5. **Evaluation** - precision@k / recall on known incidents (or agreement and synthetic recall).
6. **Explanations and workflow** - per-alert reasons, review queue, how labels feed back.

## Scripts

```bash
python scripts/anomaly_scores.py --train sensors.csv --drop reading_id is_anomaly --top 10
python scripts/anomaly_scores.py --train reference.csv --score new.csv --drop id --out scores.csv
python scripts/anomaly_scores.py --train data.csv --columns temperature pressure --k 10 --trees 200 --json
```
Fits on `--train` (the normal reference) and scores `--score` (default: the training rows): robust z (max |x −
median| / 1.4826 MAD), Mahalanobis with covariance from the central 90% of rows, distance to the k-th nearest
neighbour on standardised features, Isolation Forest (`--trees`, subsamples of 256), and the mean of rank-normalised
scores; top rows with their three most deviating features; `--out` writes every score. Exit codes: 0 scored, 2
usage error.

```bash
python scripts/anomaly_eval.py scores.csv --scores score_iforest score_knn score_ensemble --label is_anomaly --k 5 10 20
python scripts/anomaly_eval.py scores.csv --scores score_robust_z score_mahalanobis --k 10
```
With `--label`: ROC-AUC, PR-AUC, precision@k and recall@k per score and the best detector per budget (ties
listed). Without labels: Spearman agreement and top-k Jaccard between detectors. Always: thresholds at each budget,
99th/99.5th percentiles and median + 3 MAD with the number of rows each flags. Exit codes: 0 evaluated, 2 usage
error.

## Additional Resources

| File | Content |
|------|---------|
| [detector-recipes.md](references/detector-recipes.md) | scikit-learn and PyOD code: robust z, MinCovDet, LOF (novelty), IsolationForest, OneClassSVM, PCA/autoencoder reconstruction, ensembles |
| [contextual-and-time-series.md](references/contextual-and-time-series.md) | Context-relative features, peer groups, seasonal baselines, forecast residuals, change points, collective anomalies |
| [evaluation-and-operations.md](references/evaluation-and-operations.md) | Precision@k with few labels, synthetic injection, agreement, alert budgets, review loops, drift and retraining |
