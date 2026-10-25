# CatBoost Essentials

## Ordered target statistics (how categoricals are encoded)

Naive target encoding uses each row's own label (leakage). CatBoost instead:
1. draws a random permutation of the training rows (several, for different trees);
2. encodes row i's category using only rows **before i** in the permutation:
   `ctr = (count_positive_before + prior) / (count_before + 1)`;
3. at prediction time uses statistics from all training rows.

This is the "CTR" (click-through-rate-style) feature. Several CTR types exist (`Borders`, `Buckets`,
`Counter` for frequency, `BinarizedTargetMeanValue` for regression); defaults are sensible.
`simple_ctr`, `combinations_ctr` and `per_feature_ctr` configure them.

## Feature combinations

When a tree splits on a categorical CTR, CatBoost greedily adds combinations of categoricals (and binarised
numerics) for later splits, up to `max_ctr_complexity` features per combination (default 4). This captures
interactions like `plan x region` without manual crosses. Lower `max_ctr_complexity` (1-2) speeds training
on many categoricals.

## Ordered boosting

Classic boosting computes gradients for a row with a model that was trained on that row (prediction shift).
CatBoost's ordered boosting (`boosting_type="Ordered"`) uses models trained on preceding rows only. It costs
time and is the default only for small datasets; `"Plain"` is used otherwise. The ordered target statistics
apply in both modes.

## Symmetric (oblivious) trees

Default `grow_policy="SymmetricTree"`: every node at a depth uses the same split. Benefits: strong
regularisation, very fast inference (a depth-d tree is a lookup with d comparisons), good with
`depth` 4-8. `Depthwise` and `Lossguide` grow ordinary trees (more flexible, slower inference).

## Text features

`text_features=[...]`: CatBoost tokenises (by default lowercase, split on space), builds dictionaries, and
computes estimators such as BoW (bag of words), NaiveBayes and BM25 per class. Configure with
`text_processing` (tokenizers, dictionaries, feature calcers). Strong enough for short text fields
(titles, descriptions, ticket bodies); for semantic tasks precompute sentence embeddings.

## Embedding features

`embedding_features=[...]` for columns that hold vectors (numpy arrays). Estimators: LDA and KNN
(class-conditional). Useful for precomputed text/image embeddings combined with tabular data.

## Pool

```python
from catboost import Pool
pool = Pool(data=X, label=y, cat_features=CAT, text_features=TEXT, embedding_features=EMB,
            weight=w, group_id=query_ids, baseline=offset, timestamp=ts)
```
- `group_id` for ranking (rows of a group must be contiguous);
- `baseline` for offsets (exposure in Poisson/Tweedie);
- `weight` for sample weights;
- `timestamp` with `has_time=True` for time-ordered processing.

## Missing values

Numeric NaN: `nan_mode="Min"` (treated as smaller than all values) or `"Max"` / `"Forbidden"`.
Categorical NaN: not allowed; convert to a string token.
