# Extreme Imbalance Playbook (< ~100 positives or < 0.5%)

## 1. Make the numbers honest

- Report counts, not just rates: "18 of 34 frauds caught at 50 alerts".
- Confidence intervals on every metric (stratified bootstrap).
- Leave-one-positive-out style analysis is more informative than 5-fold means.

## 2. Simplify the model

- Few positives cannot support many parameters: regularised logistic regression on a handful of strong,
  domain-driven features; shallow GBMs with large `min_child_samples`.
- Prefer features that generalise (ratios, deviations from an entity's own history) over IDs and rare
  categories.

## 3. Use unsupervised signal

- Anomaly detection (Isolation Forest, robust z-scores per entity, LOF) ranks candidates without labels.
- Use known positives to *evaluate* the anomaly ranking (precision@k), not to train it.
- Combine: anomaly score as a feature in a supervised model once labels accumulate.

## 4. Collect labels deliberately

- Review the top-k anomaly or model scores daily; each review is a label.
- Add a small random sample of unflagged cases to the review queue to learn about misses (selection bias).
- Active learning: review cases where the model is most uncertain.

## 5. Two-stage systems

```
stage 1: cheap, high-recall filter (rules or a simple model)      -> keeps 5% of traffic, recall 98%
stage 2: precise model trained on the filtered population          -> positives are now 20x more frequent
```
Train stage 2 only on rows stage 1 passes, and evaluate the full system end to end.

## 6. Pool data

- Extend the time window (with time-aware validation).
- Pool related segments (countries, products) with a segment feature.
- Transfer: train on a related, label-rich task and fine-tune or use its score as a feature.

## 7. Decide with the business

When the expected value at the achievable precision/recall does not justify the review cost, rules plus label
collection may be the right product for now (ml-vs-rules-decision-advisor).
