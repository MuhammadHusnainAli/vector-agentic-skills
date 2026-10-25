# Ranking, Recommendation, Survival, Uplift and Anomaly Metrics

## Ranking

### DCG and NDCG@k
```
DCG@k  = Σ_{i=1..k} (2^{rel_i} − 1) / log2(i + 1)      # exponential gain (common in LTR)
IDCG@k = DCG@k of the ideal ordering
NDCG@k = DCG@k / IDCG@k                                  # per query, then averaged over queries
```
Queries with no relevant items have IDCG = 0: decide explicitly whether they count as 0, 1 or are excluded
(LightGBM's `lambdarank` counts them as 1 by default). Linear gain `rel_i` instead of `2^{rel}-1` is the other
convention: state which one you use.

### MRR
Mean of 1 / rank of the first relevant item. Use when one right answer matters (navigational search, QA).

### MAP@k
Mean over queries of average precision within the top k. Binary relevance.

### Recall@k / hit rate@k
Share of relevant items (or of queries with at least one relevant item) appearing in the top k.

```python
import numpy as np
from sklearn.metrics import ndcg_score
ndcg_score([true_relevance_per_query], [scores_per_query], k=10)   # one query per row; pads must be equal length
```

## Recommendation

| Metric | Measures | Caveat |
|--------|----------|--------|
| Recall@k | future interactions retrieved in the list | needs a time-based holdout, not random |
| NDCG@k | position-aware retrieval | graded relevance from ratings or dwell time |
| Coverage | share of catalogue ever recommended | popularity recommenders score low |
| Novelty | mean −log2(popularity) of recommended items | trades off with accuracy |
| Diversity | 1 − mean pairwise similarity in a list | needs item features |
| Popularity bias | share of recommendations from the head | monitor drift toward popular items |

Offline gains in recall@k often do not transfer online; treat CTR/conversion/retention from an A/B test as
the real success metric.

## Survival

### Concordance index
Share of comparable pairs (the earlier time is an observed event) where the model ranks risk correctly.
- **Harrell's C:** biased under heavy censoring.
- **Uno's C:** inverse-probability-of-censoring weighted; preferred when censoring is heavy or depends on time.
```python
from lifelines.utils import concordance_index
concordance_index(durations, -risk_scores, events)       # higher risk -> shorter time, so negate
from sksurv.metrics import concordance_index_ipcw         # Uno's C
```

### Time-dependent AUC and integrated Brier score
- `cumulative_dynamic_auc` (scikit-survival) at the decision horizon (e.g. 90 days).
- Integrated Brier score over [t_min, t_max]: calibration + discrimination of the survival curve.

## Uplift

### Uplift curve and Qini
Sort by predicted uplift; at each fraction φ of the population:
```
Qini(φ) = Y_T(φ) − Y_C(φ) · N_T(φ) / N_C(φ)          # incremental positives among the top φ
```
- **Qini coefficient:** area between the Qini curve and the random-targeting line, normalised by the area for
  the ideal model.
- **AUUC:** area under the uplift curve (conversion-rate difference version).
- **Uplift@K:** (conversion_T − conversion_C) among the top K.

Valid only on randomised data (RCT or proper randomisation). See uplift-model-builder for code.

## Anomaly detection

| Metric | When |
|--------|------|
| Precision@k (k = alert budget) | analysts review k alerts per day |
| Recall on known incidents | a catalogue of past incidents exists |
| Time to detect | streaming detection |
| Alert volume, alert fatigue | always a guardrail |
| PR-AUC | once a labelled set exists |

## Clustering (diagnostics, not success)

| Metric | Higher is better? | Notes |
|--------|-------------------|-------|
| Silhouette | yes (−1..1) | favours convex, similar-sized clusters |
| Calinski-Harabasz | yes | same bias |
| Davies-Bouldin | no (lower) | same bias |
| Adjusted Rand / NMI vs labels | yes | only with ground truth |
| Bootstrap stability (ARI between runs) | yes | the most useful check |

Success for clustering is that segments lead to different actions and remain stable over time.
