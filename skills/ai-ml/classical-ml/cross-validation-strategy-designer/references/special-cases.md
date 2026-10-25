# Special Cases

## Multilabel stratification

Standard stratification works on one label. For multilabel targets use iterative stratification
(`iterstrat.ml_stratifiers.MultilabelStratifiedKFold`, or scikit-multilearn) so rare label combinations appear
in every fold.

## Hierarchical groups

Patients within hospitals, images within subjects within sites: group at the level you want to generalise to.
Generalise to new hospitals -> group by hospital; to new patients in known hospitals -> group by patient.

## Spatial data

Nearby locations are correlated: random folds leak spatial information. Group by spatial blocks (grid cells,
regions, k-means clusters of coordinates) with a buffer between train and test blocks when autocorrelation is
long-range.

## Duplicates and near-duplicates

Exact duplicates across folds inflate scores. Deduplicate, or group duplicates together (group id = hash of the
feature row). Near-duplicates (same text with small edits, the same image resized) need fuzzy matching
(MinHash, perceptual hashes) to build groups. See train-test-split-auditor.

## Distribution shift: adversarial validation

Train a classifier to distinguish training rows from test/production rows. AUC near 0.5: similar distributions;
AUC well above 0.5: shift. Use the classifier's most important features to understand the shift and, if needed,
validate on the training rows that look most like production.

## Small data

- Repeated stratified K-fold (5x10) or leave-one-out for tiny data with cheap models.
- Keep the model simple; report intervals; avoid nested CV with large grids (too few rows per inner fold).

## Imbalanced targets

Stratify; ensure several minority rows per test fold; for very rare events consider fewer folds and repeats.

## The final holdout

- Build it with the same rules as the folds (latest period, unseen entities).
- Lock it away: use it once, after model and threshold choices are final.
- If you look at it repeatedly, it becomes a validation set; set aside a new one.
- Report the holdout result next to the CV estimate; a large gap signals leakage or drift.
