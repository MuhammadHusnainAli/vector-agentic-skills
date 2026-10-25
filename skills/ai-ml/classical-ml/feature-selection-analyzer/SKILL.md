---
name: feature-selection-analyzer
description: "Select features for tabular ML without fooling yourself: filter methods (missingness, near-zero variance, ID-like columns, univariate out-of-fold AUC / Spearman / mutual information, correlation-based redundancy groups keeping the strongest member), embedded methods (L1/elastic net, tree and GBM importance, SelectFromModel), wrapper methods (RFE/RFECV, sequential feature selection, Boruta), permutation importance on held-out data, stability selection across folds and bootstraps, and the cardinal rule that selection happens inside cross-validation. Flags near-perfect single features as probable leaks and measures importance stability across runs. Use when someone asks which features to keep or drop, how to reduce dimensionality before modelling, whether feature importance is trustworthy, why selected features change between folds, or how to avoid selection bias in CV."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# Feature Selection Analyzer

Feature selection is worth doing for four reasons: fewer features to compute and serve, less overfitting
when rows are scarce, easier explanations, and catching junk (IDs, leaks, duplicates). It is not a free
accuracy boost: modern regularised models and gradient boosting tolerate many weak features, and selection
done **outside** cross-validation silently inflates scores. `scripts/filter_select.py` runs the model-free
first pass (missing, constant, ID-like, univariate signal, redundancy groups, probable leaks);
`scripts/importance_stability.py` checks whether model-based selections agree across folds and seeds.

## Trigger Conditions

Activate this skill when the user:
- Asks which features to keep or drop, or wants to reduce hundreds of columns to a manageable set
- Has more features than rows (genomics, text-derived, wide event tables) or few positives per feature
- Asks whether feature importance, SHAP ranking or RFE output can be trusted
- Sees selected features change between folds, seeds or retrains
- Wants to cut serving cost or latency by removing expensive features
- Suspects their CV score is optimistic because selection used the full data

Leak hunting goes deeper in [target-leakage-detector](../target-leakage-detector/SKILL.md); explaining the
final model in [feature-importance-reporter](../feature-importance-reporter/SKILL.md) and
[shap-value-explainer](../shap-value-explainer/SKILL.md); dimensionality reduction without a target in
[pca-dimensionality-reducer](../pca-dimensionality-reducer/SKILL.md).

## Workflow

```
1. JUNK      -> python scripts/filter_select.py data.csv --target y --drop id time
                (missing, constant, ID-like, probable leaks, redundant groups)
2. BASELINE  -> CV score with all remaining features (same folds for everything after)
3. EMBEDDED  -> L1 / elastic net path, or GBM with permutation importance on validation folds
4. WRAPPER   -> RFECV or SequentialFeatureSelector only if the feature count must shrink a lot
5. INSIDE CV -> every selection step lives in the Pipeline; nested CV when selection is tuned
6. STABILITY -> python scripts/importance_stability.py importances.csv --top-k 20
7. DECIDE    -> keep the smallest set within noise of the best score; document dropped features
```

## Method Families

| Family | Methods | Pros | Cons |
|--------|---------|------|------|
| Filter | variance threshold, missingness, univariate AUC/F-test/chi²/mutual information, correlation redundancy | fast, model-free, good junk removal | ignores interactions; univariate ≠ useful in a model |
| Embedded | L1 (lasso, L1-logistic), elastic net, tree/GBM importance, `SelectFromModel` | uses the model; one fit | L1 picks one of a correlated group arbitrarily; impurity importance is biased |
| Wrapper | RFE / RFECV, sequential forward/backward, Boruta | optimises the actual metric | expensive; overfits the selection on small data |
| Permutation importance | drop in held-out score when a feature is shuffled | model-agnostic, honest | correlated features share (and hide) importance |
| Stability selection | selection frequency over subsamples/bootstraps | controls false selections | more compute; needs a base selector |

Code for each with scikit-learn: [selection-methods.md](references/selection-methods.md).

## The Rule: Select Inside Cross-Validation

Selecting features on the full dataset and then cross-validating the reduced model leaks the test folds'
labels into the selection. With many features and few rows this can turn pure noise into an "AUC 0.8"
model.

```python
from sklearn.pipeline import Pipeline
from sklearn.feature_selection import SelectFromModel, SelectKBest, mutual_info_classif
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score, StratifiedKFold

pipe = Pipeline([
    ("prep", prep),                                                      # imputers, encoders, scalers
    ("select", SelectFromModel(LogisticRegression(penalty="l1", solver="liblinear", C=0.1))),
    ("model", LogisticRegression(max_iter=2000)),
])
cv = StratifiedKFold(5, shuffle=True, random_state=0)
print(cross_val_score(pipe, X, y, cv=cv, scoring="average_precision").mean())
```

If the number of features or the selector's strength is tuned, wrap it in `GridSearchCV` and evaluate the
whole search with an outer CV (nested CV). Demonstration of the bias and nested-CV code:
[selection-bias-and-nested-cv.md](references/selection-bias-and-nested-cv.md).

## Correlated Features

Correlated features split importance and make selections unstable: with `total_charges` ≈ f(tenure, price),
L1 or a tree keeps one of them in some folds and the other in other folds.

| Goal | Approach |
|------|----------|
| Smaller, stable set | cluster features by |Spearman| (filter_select `--corr 0.9`) or hierarchical clustering; keep one per cluster |
| Honest importance | permutation importance per *cluster* (shuffle the group together), or grouped SHAP |
| Prediction only | keep them; GBMs and ridge handle redundancy fine |
| Interpretation | keep the most interpretable member, or a composite (PCA of the group, a ratio) |

`importance_stability.py` makes this visible: correlated pairs show up as "unstable" features selected in
40-60% of runs while the overall ranking agreement stays high.

## Choosing How Many Features

1. Plot CV score vs number of features (RFECV `cv_results_`, or a forward-selection curve).
2. Find the best mean score and its standard error across folds.
3. Choose the **smallest** set whose score is within one standard error of the best (one-SE rule).
4. Re-check on a time-based holdout; a set chosen on random folds can rely on features that drift.

## Junk and Leak Signals

| Signal | Interpretation | Action |
|--------|----------------|--------|
| Single-feature AUC > 0.9 | leak until proven otherwise | target-leakage-detector |
| Missing for > 95% of rows | almost no information | drop (or keep a "has value" flag if missingness is informative) |
| One value in > 99.5% of rows | near-constant | drop |
| Near-unique text | ID | drop (aggregate by it instead) |
| Random noise column ranks above real features | importance method is biased (impurity) or the model overfits | use permutation importance; add a noise probe |
| Feature only useful on random folds, not on time holdout | time leakage or drift | drop or rebuild as-of |

**Noise probe:** add 1-3 columns of random numbers before computing importances; any real feature ranking
below the probes is not distinguishable from noise (the idea behind Boruta's shadow features).

## Output Format

When advising on feature selection, answer with:
1. **Junk removed** - the `filter_select.py` table: dropped columns with reasons, probable leaks, redundancy
   groups and the member kept.
2. **Method** - filter/embedded/wrapper/permutation chosen for this data size and model, inside a Pipeline.
3. **Curve** - CV score vs number of features, the one-SE choice.
4. **Stability** - selection frequency across folds/seeds (`importance_stability.py`), unstable groups.
5. **Final set** - kept features, dropped features with the score cost of dropping them, serving cost saved.

## Scripts

```bash
python scripts/filter_select.py data.csv --target churned --drop customer_id signup_date
python scripts/filter_select.py data.csv --target price --corr 0.85 --min-signal 0.05 --drop-weak
python scripts/filter_select.py data.csv --target churned --keep-list > features.txt
python scripts/filter_select.py data.csv --target churned --json
```
Drops columns that are mostly missing (`--max-missing`, default 0.95), near-constant (`--max-top-share`,
0.995) or near-unique text; scores univariate signal (AUC for binary targets, |Spearman| for numeric, smoothed
out-of-fold level means for categoricals) and flags single-feature AUC > 0.9 as a possible leak; groups
numeric features with |Spearman| >= `--corr` and keeps the strongest of each group; marks or drops features
below `--min-signal`. Exit codes: 0 done, 2 usage or read error.

```bash
python scripts/importance_stability.py importances.csv --top-k 10
python scripts/importance_stability.py imp.csv --run-col fold --feature-col name --importance-col gain --json
```
Input: long CSV (run, feature, importance) from folds, bootstraps or seeds. Prints per feature the mean
importance, mean rank, rank standard deviation and top-K selection frequency; groups features into stable
(>= `--stable`, default 0.8), unstable and never selected; and the mean pairwise Spearman agreement between
runs. Exit codes: 0 agreement >= `--min-agreement` (0.6), 1 unstable, 2 usage error.

## Additional Resources

| File | Content |
|------|---------|
| [selection-methods.md](references/selection-methods.md) | scikit-learn code for VarianceThreshold, SelectKBest/mutual information, L1 and elastic net, SelectFromModel, RFECV, SequentialFeatureSelector, permutation importance, Boruta-style shadow features, stability selection |
| [selection-bias-and-nested-cv.md](references/selection-bias-and-nested-cv.md) | How selection outside CV inflates scores (with a noise-only demonstration), nested CV, time-based validation of feature sets |
| [correlated-features.md](references/correlated-features.md) | Redundancy clustering, grouped permutation importance, VIF, choosing representatives, effects on L1 and trees |
| [selection-reporting.md](references/selection-reporting.md) | One-SE rule, score-vs-features curves, cost-aware selection, documenting dropped features |
