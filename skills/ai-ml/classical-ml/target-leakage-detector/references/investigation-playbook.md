# Leakage Investigation Playbook

## Step 1: rank suspects

Run both scans; list every high finding plus the top 5 features by importance/SHAP. A feature is a suspect if
any of these hold:
- single-feature AUC > 0.9 or far above domain expectations;
- outcome-like name, or comes from a system that acts on outcomes (CRM cases, collections, refunds);
- built from a table without history (current-state);
- its importance is much higher than the business can explain.

## Step 2: establish the write time

For each suspect, answer with the data owner:
| Question | Leak if |
|----------|---------|
| Which process writes the field? | a process triggered by the outcome |
| When relative to the event? | at or after the event |
| Is it overwritten? | yes, and you read the current value |
| Is it backfilled? | yes, historical rows were filled later |

## Step 3: look at the timeline

Plot the feature against days before the outcome for positives, and against days before the scoring date for
negatives:
```python
pos = df[df.y == 1].assign(days_before=(df.event_date - df.feature_date).dt.days)
pos.groupby(pos.days_before.clip(-30, 90))["feature"].mean().plot()
```
Values that change sharply at day 0 or after are written by the outcome.

## Step 4: rebuild as-of and compare

Recompute the suspect strictly from data before the prediction time and compare:
| Version | Single-feature AUC | Model AUC (time holdout) |
|---------|--------------------|--------------------------|
| As delivered | 0.95 | 0.97 |
| Rebuilt as-of | 0.62 | 0.81 |

A collapse confirms leakage; the rebuilt version is the one to keep (if it still helps).

## Step 5: ablation on a time-ordered holdout

Drop the feature (or its group), retrain, evaluate on the latest period. Leaky features often add a lot on
random CV and little on the future window.

## Step 6: shadow comparison

In shadow mode, log the feature's value at prediction time and compare with the value the training pipeline
produces for the same entity and timestamp. Any difference is train/serve skew, often caused by leakage.

## Step 7: fix and guard

- Remove or rebuild the feature; add it to a `KNOWN_LEAKS` list in the training code with a comment.
- Add `leakage_scan.py` (data) and `code_leak_lint.py` (code) to CI:
  ```yaml
  - run: python scripts/leakage_scan.py data/train_sample.csv --target churned --time-col score_date --drop customer_id
  - run: python scripts/code_leak_lint.py src/train.py
  ```
- Data contracts: the owning team documents write times and history semantics for each source.

## Decision table

| Evidence | Decision |
|----------|----------|
| Written after the event | drop |
| Current-state value, history available | rebuild as-of |
| Current-state value, no history | drop, or start snapshotting now and add later |
| Proxy of the label but available at prediction time | keep only if acting on it is legitimate (e.g. "customer requested cancellation" when the decision is a save offer) |
| Pipeline leak | fix the code; re-run evaluation |
