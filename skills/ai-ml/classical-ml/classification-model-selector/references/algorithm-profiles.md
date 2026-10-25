# Classifier Profiles

## Logistic regression
Linear log-odds model fitted by maximum likelihood with a penalty.
- **Key params:** `C` (inverse regularisation, tune on a log grid 1e-3..1e2), `penalty` (`"l2"`, `"l1"`,
  `"elasticnet"` with `l1_ratio`), `solver` (`lbfgs` default; `saga` for L1/elastic net and large sparse data;
  `liblinear` for small L1), `class_weight`, `max_iter` (raise to 2000+).
- **Needs:** scaled numerics, one-hot categoricals, explicit non-linearity (splines, bins, interactions).
- **Fails when:** effects are strongly non-linear or interacting and nobody engineered features for it.
- **Bonus:** good probabilities without class weights; coefficients map to odds ratios.

## Linear SVM
Maximum-margin linear classifier (hinge loss).
- **Key params:** `C`, `loss` (hinge / squared hinge), `dual="auto"`.
- **Use:** text and very wide sparse data. Wrap in `CalibratedClassifierCV` for probabilities.

## Naive Bayes
Per-feature likelihoods combined with Bayes' rule.
- `MultinomialNB` / `ComplementNB` for counts and TF-IDF; `GaussianNB` for continuous features; `alpha`
  smoothing. Instant, decent text baseline; probabilities are overconfident.

## k-nearest neighbours
Vote among the k closest training rows.
- **Key params:** `n_neighbors` (15-50 for probabilities), `weights="distance"`, `metric`.
- **Needs:** scaling, few features, small/medium data (prediction cost grows with n).

## SVM with RBF kernel
- **Key params:** `C`, `gamma` (`"scale"`), tune jointly on log grids.
- **Use:** small dense data (< ~20k rows). Training is O(n²)-O(n³). `probability=True` runs internal CV
  (slow); prefer `CalibratedClassifierCV`.

## Decision tree
Recursive axis-aligned splits.
- **Key params:** `max_depth`, `min_samples_leaf`, `ccp_alpha` (cost-complexity pruning).
- **Use:** readable rules, surrogates, SQL deployment. High variance alone.

## Random forest
Bagged deep trees with random feature subsets.
- **Key params:** `n_estimators` (300-1000; more never hurts accuracy, only cost), `max_features` (`"sqrt"`,
  or 0.2-0.5), `min_samples_leaf` (1-10), `max_samples` (bootstrap fraction), `class_weight="balanced_subsample"`.
- **Strengths:** robust defaults, out-of-bag estimate (`oob_score=True`).
- **Weaknesses:** probabilities squashed toward 0.5 (calibrate), large models, impurity importances biased.

## Extra trees
Like RF but with random split thresholds: faster, often similar accuracy, smoother probability surface.

## HistGradientBoosting (scikit-learn)
Histogram-based gradient boosting (LightGBM-like) in scikit-learn.
- **Key params:** `learning_rate` (0.03-0.1), `max_leaf_nodes` (15-63), `min_samples_leaf` (20-200),
  `l2_regularization`, `max_iter` with `early_stopping=True`, `categorical_features`, `monotonic_cst`,
  `class_weight`.
- **Strengths:** native NaN and categoricals (< 256 levels), no extra dependency.

## LightGBM
Leaf-wise histogram GBM.
- **Key params:** `learning_rate`, `num_leaves` (main capacity knob), `min_child_samples` (raise for small or
  noisy data), `feature_fraction`/`colsample_bytree`, `bagging_fraction`/`subsample` + `bagging_freq`,
  `lambda_l1/l2`, `n_estimators` with early stopping, `categorical_feature`, `monotone_constraints`.
- **Fails when:** small data with defaults (leaf-wise growth overfits): increase `min_child_samples`, lower
  `num_leaves`.

## XGBoost
Level-wise (default) or loss-guided histogram GBM.
- **Key params:** `max_depth` (4-8), `min_child_weight`, `eta`/`learning_rate`, `subsample`,
  `colsample_bytree`, `gamma`, `reg_lambda`, `reg_alpha`, `tree_method="hist"`, `enable_categorical`,
  `monotone_constraints`, `scale_pos_weight`.

## CatBoost
Oblivious (symmetric) trees with ordered boosting and ordered target statistics for categoricals.
- **Key params:** `iterations`, `learning_rate`, `depth` (4-8), `l2_leaf_reg`, `cat_features`,
  `one_hot_max_size`, `auto_class_weights`, `od_type`/`od_wait` (early stopping).
- **Strengths:** excellent defaults, categoricals without preprocessing, fast inference (symmetric trees).

## Explainable boosting machine (EBM)
A GAM learned by cyclic boosting of one feature at a time, plus a few pairwise interactions.
- **Key params:** `interactions` (number of pairs), `max_bins`, `outer_bags`, `learning_rate`.
- **Strengths:** exact per-feature contribution curves; editable; competitive accuracy on many tabular tasks.

## MLP
Feed-forward neural network.
- **Key params:** layer sizes, `alpha` (L2), `learning_rate_init`, `early_stopping=True`.
- **Use:** large data, combined with embeddings; otherwise rarely the best tabular choice.

## Rough expectations (tabular, medium data)

| Model | Accuracy rank | Training speed | Inference speed | Tuning effort |
|-------|---------------|----------------|-----------------|---------------|
| Tuned GBM (LightGBM / XGBoost / CatBoost) | 1 | fast | fast | medium |
| Default CatBoost / HistGBM | 2 | medium / fast | fast | low |
| EBM | 2-3 | slow | fast | low |
| Random forest | 3 | medium | slow-medium | low |
| Logistic regression with good features | 3-4 | very fast | very fast | low |
| k-NN / SVM | 4-5 | varies | slow | medium |
