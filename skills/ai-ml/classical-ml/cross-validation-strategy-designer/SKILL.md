---
name: cross-validation-strategy-designer
description: "Design the cross-validation scheme that mirrors how a model will be used, and check the folds before trusting any score: StratifiedKFold and repeated CV for i.i.d. data, GroupKFold / StratifiedGroupKFold / LeaveOneGroupOut when entities repeat (customers, patients, devices, sessions), TimeSeriesSplit with gaps and expanding or sliding windows for forward prediction, purging and embargo for overlapping label windows, nested CV for tuning, spatial and hierarchical grouping, multilabel stratification, small-data choices (repeats, LOO) and the final untouched holdout. Detects repeated-entity and time columns from the data, recommends a splitter with scikit-learn code, and previews or audits folds for group overlap, time-order violations, label-window gaps and missing classes. Use when someone asks how to split data or set up CV, why CV scores are better than production, how to cross-validate time series or grouped data, or wants existing folds checked for leakage."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# Cross-Validation Strategy Designer

A CV score estimates performance **under the conditions the folds simulate**. If production predicts new
customers, folds must hold out whole customers; if it predicts next month, folds must train on the past and
test on the future, with a gap when labels look ahead. Random K-fold on such data measures something easier
than the real task, so scores look better than production delivers. `scripts/cv_advisor.py` reads the data
(repeated-entity columns, time columns, target balance) and recommends a splitter with code;
`scripts/fold_preview.py` builds or audits folds and reports group overlap, time-order and gap violations,
and missing classes.

## Trigger Conditions

Activate this skill when the user:
- Asks how to split data, how many folds to use, or which scikit-learn splitter fits
- Sees CV scores much better than holdout or production performance
- Has repeated rows per entity (customer snapshots, patient visits, sessions, images per subject)
- Works with time-ordered data (churn snapshots, transactions, forecasts) or overlapping label windows
- Tunes hyperparameters and needs nested CV
- Wants existing fold assignments audited

Holdout-split audits (duplicates, drift between train and test): [train-test-split-auditor](../train-test-split-auditor/SKILL.md);
leakage in features and code: [target-leakage-detector](../target-leakage-detector/SKILL.md).

## Workflow

```
1. DEPLOYMENT -> how will predictions be made? new entities / same entities later / next period / i.i.d.
2. ADVISE     -> python scripts/cv_advisor.py data.csv --target y [--group-col id --time-col ts --label-window 30]
3. PREVIEW    -> python scripts/fold_preview.py data.csv --target y --strategy stratified-group --group-col id
4. HOLDOUT    -> keep a final untouched set built the same way (latest period / unseen entities)
5. TUNE       -> nested: inner splitter with the same rules; outer scores are the estimate
6. REPORT     -> scheme, folds, repeats, mean ± sd, and the holdout confirmation
```

## Scheme by Deployment

| Production predicts | Splitter | Notes |
|---------------------|----------|-------|
| i.i.d. rows (no time, no repeated entities) | `StratifiedKFold(5, shuffle=True)` (classification), `KFold` (regression) | repeat (`RepeatedStratifiedKFold`) for small data |
| New entities (unseen customers, patients, devices) | `StratifiedGroupKFold` / `GroupKFold` with `groups=entity` | one entity's rows never on both sides |
| Each entity has one held-out group of its own (sites, hospitals) | `LeaveOneGroupOut` | estimates transfer to a new site |
| The next period | `TimeSeriesSplit(n_splits, gap, test_size)` on time-sorted rows | expanding window; `max_train_size` for sliding |
| Next period with look-ahead labels (churn in 30 d) | time split with gap >= label window (purging) | prevents training labels that overlap test time |
| Same entities, later time | time split (entities may appear in both) | do not group by entity unless new entities matter |
| Spatial generalisation | group by region / spatial blocks | nearby points are correlated |
| Fixed, pre-defined validation set | `PredefinedSplit` | e.g. a validation month |

`cv_advisor.py` on the transactions fixture: detects `card_id` repeats (~10 rows/card) and the `timestamp`
column, recommends `StratifiedGroupKFold` for new-card generalisation and warns that forward prediction needs
time folds.

## What the Fold Preview Catches

```
stratified (random) folds on transactions:
PROBLEM: fold 2: 133 card_id value(s) shared between train and test (random folds with repeated entities)
stratified-group folds:   group overlap 0 in every fold; minority rate 0.017-0.036 per fold
time folds, label window 2 days, gap 0:
PROBLEM: fold 1: gap 0.0 days < label window 2: training labels overlap the test period
time folds with --gap 120 rows:  gap 2.38 d  -> sound
```
Audit someone else's folds with `--fold-col fold`.

## Time-Series CV

- Sort by time; train on everything before the test block (expanding) or a fixed window (sliding,
  `max_train_size`) when old data is stale.
- **Gap / purge**: if a row's label covers [t, t + w], drop training rows whose label window overlaps the test
  start (gap >= w). **Embargo**: also drop rows just after the test block when training on both sides
  (finance-style combinatorial CV).
- Test blocks should match the deployment horizon (one month if retrained monthly).
- Weight recent folds more in the decision; report per-fold scores, not only the mean.

Detail (rolling origin for forecasting, purged K-fold, multiple horizons): [time-series-cv.md](references/time-series-cv.md).

## How Many Folds and Repeats

| Data | Choice |
|------|--------|
| < 1,000 rows | 5-fold x 5-10 repeats (or 10-fold); report the spread |
| 1k-100k | 5-fold (x 2-3 repeats if comparing close models) |
| > 1M | 3-fold or a single large holdout |
| < ~30 minority rows per fold | fewer folds, repeats, stratification, intervals |
| Expensive models | 3-fold for search, 5-fold to confirm finalists |

More folds lower the bias (larger training sets) and raise the cost; repeats lower the variance of the estimate.
Leave-one-out is rarely worth it (high variance, expensive) except for tiny datasets with cheap models.
Nested CV and variance estimates: [nested-cv-and-variance.md](references/nested-cv-and-variance.md).

## Special Cases

Multilabel stratification (iterative stratification), hierarchical groups (patients within hospitals),
duplicates and near-duplicates, spatial blocking, very small data, distribution-shift-aware validation
(adversarial validation), and the final holdout: [special-cases.md](references/special-cases.md).

## Output Format

When designing CV, deliver:
1. **Deployment assumption** - what the folds simulate (new entities, next period, i.i.d.).
2. **Splitter** - class and parameters (folds, repeats, gap, groups) with code (`cv_advisor.py`).
3. **Fold audit** - per-fold sizes, class rates, group overlap, time ranges (`fold_preview.py`).
4. **Tuning plan** - nested CV or validation split inside training folds.
5. **Holdout** - how the final test set is built and when it is used (once).
6. **Reporting** - mean ± sd across folds, per-fold scores for time splits, holdout result.

## Scripts

```bash
python scripts/cv_advisor.py data.csv --target churned
python scripts/cv_advisor.py snapshots.csv --target churned --group-col customer_id --time-col score_date --label-window 30
python scripts/cv_advisor.py data.csv --target price --deploy iid --tuning --json
```
Detects repeated-entity columns (ID-like names with repeats) and date columns, profiles the target, applies
`--deploy` (forward, new-entities, same-entities, iid; auto by default) and prints the splitter, folds/repeats,
gap, nested-CV advice, warnings (random folds with repeated entities, time columns ignored, missing gap for
look-ahead labels, tiny classes) and scikit-learn code. Exit codes: 0 printed, 2 usage error.

```bash
python scripts/fold_preview.py data.csv --target churned --strategy stratified --folds 5
python scripts/fold_preview.py txns.csv --target is_fraud --strategy stratified-group --group-col card_id
python scripts/fold_preview.py snaps.csv --target churned --strategy time --time-col score_date --label-window 30 --gap 200
python scripts/fold_preview.py data.csv --target y --fold-col fold --group-col customer_id --time-col ts
```
Generates kfold / stratified / group / stratified-group / time folds (scikit-learn-like logic) or audits an
existing fold column; per fold: sizes, minority rate or target mean, group overlap, train max vs test min time and
gap; problems for overlap, time-order violations, gaps shorter than `--label-window`, missing classes and tiny
folds. Exit codes: 0 sound, 1 problems found, 2 usage error.

## Additional Resources

| File | Content |
|------|---------|
| [time-series-cv.md](references/time-series-cv.md) | Expanding vs sliding windows, gaps, purging and embargo, rolling-origin evaluation, multiple horizons, panel data |
| [nested-cv-and-variance.md](references/nested-cv-and-variance.md) | Nested CV code, inner/outer rules, number of folds vs bias/variance, repeats, confidence intervals for CV scores |
| [special-cases.md](references/special-cases.md) | Multilabel and hierarchical stratification, spatial blocking, duplicates, adversarial validation, small data, final holdout policy |
