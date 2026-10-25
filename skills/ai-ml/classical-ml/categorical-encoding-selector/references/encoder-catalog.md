# Encoder Catalog

## One-hot (indicator) encoding
One binary column per level.
- **Use:** linear models, k-NN, SVM, neural nets; low/moderate cardinality.
- **scikit-learn:** `OneHotEncoder(handle_unknown=..., min_frequency=..., max_categories=..., drop=..., sparse_output=...)`.
- **pandas:** `pd.get_dummies` only for exploration: it does not remember categories, so train and serving
  columns can differ.
- **Pitfalls:** width explodes with cardinality; perfect collinearity without regularisation (use
  `drop="first"` or `"if_binary"`); trees split one level at a time (inefficient for many levels).

## Ordinal encoding
One integer per level, optionally in a given order.
- **Use:** ordered categories for any model; nominal categories for tree models at low cardinality.
- `OrdinalEncoder(categories=[["low", "medium", "high"]], handle_unknown="use_encoded_value", unknown_value=-1,
  encoded_missing_value=-1)`.
- **Pitfalls:** for linear models a nominal column encoded as 0..k-1 imposes a fake order and spacing.
  `LabelEncoder` is for targets, not features.

## Target encoding family
Replace a level by a statistic of the target for that level.

| Variant | Formula / idea |
|---------|----------------|
| Mean (smoothed) | (Σy + m·prior) / (n + m) |
| M-estimate | same with a fixed m |
| Empirical Bayes ("auto") | shrinkage weight from within-level vs between-level variance (sklearn `smooth="auto"`) |
| James-Stein | shrink toward the prior by a variance-based factor |
| Leave-one-out | exclude the row's own label: still leaks through the row count; avoid |
| Weight of evidence (WoE) | ln(P(level|y=1) / P(level|y=0)); classic in credit scorecards |
| CatBoost ordered | statistics over preceding rows in a random permutation |

- **Use:** high cardinality with enough rows per level; all model families.
- **Must be cross-fitted** (see target-encoding-and-leakage.md).
- Multiclass: one encoded column per class (sklearn does this). Regression: mean of y (or median for robustness).

## Frequency / count encoding
Replace a level by its count or share in the training data.
- **Use:** high cardinality where popularity matters (merchant size, product popularity); handles unseen
  levels (count 0) and needs no target.
- **Pitfalls:** different levels with the same count become indistinguishable; counts drift as data grows
  (use shares, or recompute on retrain).

```python
freq = train["merchant"].value_counts(normalize=True)
X["merchant_freq"] = X["merchant"].map(freq).fillna(0.0)
```

## Feature hashing
Hash each level into one of N buckets.
- **Use:** very high or unbounded cardinality, streaming/online learning, many unseen levels.
- `FeatureHasher(n_features=2**10, input_type="string")` (needs a list of lists of strings per row).
- **Pitfalls:** collisions (choose N so collisions are rare for frequent levels); not invertible (hard to
  explain).

## Binary / base-N encoding
Ordinal code written in binary digits (log2(k) columns). Compact but arbitrary; rarely better than target or
frequency encoding. Available in category_encoders.

## Entity embeddings
Learned dense vectors per level (neural nets), optionally reused as features in GBMs. Useful for very high
cardinality with lots of data (users, products). Requires a training pipeline; overkill for most tabular
projects.

## Hierarchical / prefix encoding
For codes with structure: zip -> zip3 -> state; NAICS 6 -> 4 -> 2 digits; ICD-10 code -> category -> chapter.
Encode each level of the hierarchy (one-hot for coarse, target for fine) so rare fine levels borrow strength
from their parent.

## Missing values as a level
For one-hot and target encoding, replace missing with an explicit "__missing__" level before encoding (or
let the encoder handle NaN: `OneHotEncoder` treats NaN as a category since 1.0; `TargetEncoder` treats it
as its own category). GBMs handle missing natively.

## Quick reference: scikit-learn parameters

| Encoder | Key parameters |
|---------|----------------|
| `OneHotEncoder` | `handle_unknown` ("error", "ignore", "infrequent_if_exist", "warn" in 1.6+), `min_frequency`, `max_categories`, `drop`, `sparse_output` |
| `OrdinalEncoder` | `categories`, `handle_unknown="use_encoded_value"`, `unknown_value`, `encoded_missing_value`, `min_frequency`, `max_categories` |
| `TargetEncoder` | `target_type` ("auto", "binary", "multiclass", "continuous"), `smooth` ("auto" or float), `cv` (int or splitter) |
| `FeatureHasher` | `n_features`, `input_type` ("dict", "pair", "string"), `alternate_sign` |
