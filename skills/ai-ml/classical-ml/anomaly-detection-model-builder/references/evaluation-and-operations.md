# Evaluation and Operations

## With a few labels

- precision@k at the real alert budget ("of the 20 daily alerts, how many are real?");
- recall on the catalogue of known incidents;
- PR-AUC for a threshold-free summary;
- report counts and intervals: with 6 known incidents, recall moves in steps of 17%.

Labels from past incidents are biased toward what was detectable before; add newly confirmed alerts and a
random sample of unflagged rows reviewed for misses.

## Without labels

| Method | How |
|--------|-----|
| Synthetic injection | add known anomalies (spikes, swapped columns, impossible combinations, duplicated bursts) to a clean sample; measure recall at the budget |
| Detector agreement | Spearman of scores, Jaccard of top-k sets (anomaly_eval.py); low agreement = different anomaly types, not necessarily errors |
| Stability | fit on two reference periods; compare top-k sets on a common scoring set |
| Reviewer feedback | confirmation rate of alerts; the operational metric that matters |

## Choosing the alert budget

Budget = review capacity per period. Check the score distribution: if the k-th score is barely above the bulk
of normal scores, alerts beyond a smaller k are mostly noise; lower the budget or improve features.

## Review loop

1. Alerts go to a queue with explanations (deviating features, context, detector).
2. Reviewers label each (true issue / benign / data error) with a reason code.
3. Labels feed evaluation weekly, and eventually a supervised or semi-supervised model.
4. Benign patterns that recur become features or allow-list rules.

## Drift and retraining

- Refit the reference model on a rolling window that excludes confirmed anomalies.
- Monitor alert volume and the confirmation rate; a jump in volume often means drift or a pipeline bug.
- Version detectors, thresholds and reference windows.

## From unsupervised to supervised

Once a few hundred confirmed anomalies exist, train a classifier on reviewer labels (with the anomaly scores as
features); evaluate on a time-ordered holdout. Keep the unsupervised detector for novel patterns the classifier
has not seen.
