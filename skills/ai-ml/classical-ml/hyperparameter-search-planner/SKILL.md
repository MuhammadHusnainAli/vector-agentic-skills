---
name: hyperparameter-search-planner
description: "Plan hyperparameter searches that fit the compute budget and read their results correctly: choose grid, random, successive halving (HalvingRandomSearchCV), Bayesian/TPE (Optuna) or Hyperband/ASHA from fit cost, trial budget, parallel workers and the number of continuous parameters; define search spaces with log scales, conditional parameters and sensible ranges for logistic regression, elastic net, SVM, k-NN, random forest, extra trees, HistGradientBoosting, LightGBM, XGBoost, CatBoost and MLPs; fix what early stopping handles; then analyse cv_results_ or Optuna trials for best configurations, parameters at the edge of their range, sensitivity (including peaked effects), configurations within one standard error, and whether more trials would help. Use when someone asks how to tune a model, grid vs random vs Bayesian search, what ranges to search, how many trials are needed, or how to interpret search results."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# Hyperparameter Search Planner

A good search is mostly decided before it runs: measure one fit, compute how many trials the budget allows,
fix what early stopping or common sense decides, put multiplicative parameters on log scales, and choose
the strategy that matches cost and dimensionality. After it runs, look for **boundaries** (the best value
at the edge of the range), **sensitivity** (which parameters matter at all), the **1-SE set** (simpler
configurations as good as the best), and the **progress curve** (whether more trials would help).
`scripts/search_planner.py` produces the plan with ready-to-run distributions (scikit-learn) or `suggest_*`
calls (Optuna); `scripts/analyze_search.py` reads scikit-learn `cv_results_` or Optuna trials.

## Trigger Conditions

Activate this skill when the user:
- Asks how to tune hyperparameters, grid vs random vs Bayesian search, or how many trials to run
- Needs search ranges for a model family, or wonders whether to search on a log scale
- Has a fixed compute budget (hours, GPUs, workers) and a slow model
- Shows search results and asks what they mean, whether the range was right, or which configuration to pick
- Sees a tuned model barely beat defaults, or a tuned score that does not hold on the test set

GBM-specific tuning detail: [xgboost-lightgbm-tuner](../xgboost-lightgbm-tuner/SKILL.md) and
[catboost-model-builder](../catboost-model-builder/SKILL.md); complete Optuna study scripts:
[optuna-study-writer](../optuna-study-writer/SKILL.md); validation design and nested CV:
[cross-validation-strategy-designer](../cross-validation-strategy-designer/SKILL.md).

## Workflow

```
1. VALIDATE  -> folds that mirror deployment; fix them for all trials; untouched holdout aside
2. MEASURE   -> time ONE fit on one training fold (seconds); note parallel workers
3. PLAN      -> python scripts/search_planner.py --model lgbm --rows N --fit-seconds S --budget-hours H --workers W
4. RUN       -> RandomizedSearchCV / HalvingRandomSearchCV / Optuna with the generated space
5. ANALYSE   -> python scripts/analyze_search.py cv_results.csv --folds 5 --simpler "max_leaf_nodes:low"
6. ITERATE   -> widen ranges at boundaries, drop insensitive parameters, narrow around the optimum
7. CONFIRM   -> nested CV or the holdout; compare with the untuned baseline; report the budget used
```

## Choosing the Strategy

| Situation | Strategy | Why |
|-----------|----------|-----|
| Few discrete options (<= ~30 combinations) | grid | exhaustive, simple |
| Cheap fits, 1-3 parameters | random (20-60 trials) | covers continuous ranges better than grids |
| Many candidates, partial fits informative (rows or trees) | successive halving / Hyperband | discards bad configs early |
| Expensive fits, 3+ continuous parameters | TPE / Bayesian (Optuna) | uses past trials to propose good ones |
| Boosting with early stopping or CV folds as steps | TPE + pruning (Median/Hyperband pruner) | stops bad trials after one or two folds |
| Huge budget, many workers | random or ASHA in parallel | Bayesian methods parallelise less efficiently |

Random search beats grid search when only a few parameters matter (Bergstra & Bengio 2012): a 60-point random
search covers each important parameter with 60 distinct values, a 60-point grid with 3-4.

## Budget Arithmetic

```
seconds per trial   = fit_seconds x folds
affordable trials   = budget_seconds / seconds per trial x workers
```
`search_planner.py` on LightGBM, 200k rows, 40 s per fit, 5 folds, 4 hours, 4 workers: 200 s per trial, ~288
trials affordable -> TPE with pruning, 200 trials, ~2.8 h. With fewer than ~20 affordable trials: fix more
parameters, search on a row sample with 3 folds, and expect a good region, not an optimum.

## Search Spaces

| Rule | Example |
|------|---------|
| Log scale for multiplicative effects | C, alpha, learning_rate, reg_lambda, gamma: `loguniform(1e-4, 1e2)` |
| Integer log scale for sizes | num_leaves 7-255, min_child_samples 5-500 |
| Fix what early stopping decides | n_estimators / iterations: early stopping, not search |
| Fix the learning rate during search (GBMs) | 0.05-0.1; lower it for the final fit |
| Conditional parameters | CatBoost bagging_temperature only with Bayesian bootstrap; l1_ratio only with elastic net |
| Do not tune what does not matter | random_state, n_jobs, n_estimators for forests (more is just slower) |
| Start wide, then narrow | first pass over decades, second pass around the best region |

Per-family ranges with reasons: [search-spaces.md](references/search-spaces.md).

## Reading the Results

```
sensitivity (score range across quartile bins; Spearman for direction):
  l2_regularization      effect 0.0287  spearman +0.294  (log scale)  higher is better
  learning_rate          effect 0.0280  spearman -0.430  (log scale)  lower is better
  max_leaf_nodes         effect 0.0149  spearman +0.035  (linear scale)
BOUNDARY: best learning_rate=0.0175 sits at the low end of [0.0114, 0.277] - extend the range on that side
9 configuration(s) within 1 SE (0.0239) of the best; pick: ... max_leaf_nodes=9 ... (score 0.7831)
```
- **Boundary** -> widen the range on that side and rerun.
- **Low effect** -> fix that parameter at a sensible value; spend trials elsewhere.
- **Within 1 SE** -> pick the simplest / cheapest configuration (`--simpler param:low|high`).
- **No gain in the second half of trials** -> more trials will not help; change features or the model.
- The best CV score of a search is optimistic (maximum over trials): confirm on held-out data.

Interpretation details, overfitting the validation set, and reporting: [reading-search-results.md](references/reading-search-results.md).

## Output Format

When planning or reviewing a search, deliver:
1. **Budget** - seconds per fit, folds, workers, affordable trials.
2. **Strategy** - and why, with the pruning/early-stopping setup.
3. **Space** - parameters, ranges, scales, fixed values, conditionals; code from `search_planner.py`.
4. **Results** - best configurations, sensitivity, boundaries, 1-SE pick, progress (`analyze_search.py`).
5. **Next iteration** - widened/narrowed ranges or a decision to stop.
6. **Validation** - nested CV or holdout score of the chosen configuration vs the default.

## Scripts

```bash
python scripts/search_planner.py --model lgbm --rows 200000 --fit-seconds 40 --budget-hours 4 --folds 5 --workers 4
python scripts/search_planner.py --model logreg --rows 5000 --fit-seconds 0.5 --trials 60
python scripts/search_planner.py --model rf --rows 50000 --fit-seconds 20 --budget-hours 1 --format optuna --json
```
Families: logreg, elasticnet, svm, knn, rf, et, hgb, lgbm, xgb, catboost, mlp. Prints seconds per trial,
affordable trials, the strategy (grid, random, successive halving, TPE with or without pruning), trial count and
estimated hours, what to fix, the space with types and scales, warnings (tiny budgets, huge data, grids larger
than the budget) and either scikit-learn `param_distributions` (with an integer log-uniform helper) or Optuna
`suggest_*` lines. Exit codes: 0 printed, 2 usage error.

```bash
python scripts/analyze_search.py cv_results.csv --folds 5
python scripts/analyze_search.py trials.csv --simpler "max_leaf_nodes:low" "min_samples_leaf:high"
python scripts/analyze_search.py trials.csv --lower-better --json
```
Reads scikit-learn `cv_results_` (param_* columns) or Optuna `trials_dataframe()` (params_*, COMPLETE trials),
reports the top configurations, per-parameter effect range across quartile bins with Spearman direction and a
peaked-optimum flag, categorical level means, parameters whose best value sits in the outer 15% of the searched
range, the set within one standard error and its simplest member, and the best-so-far progress. Exit codes: 0
analysed, 2 usage error.

## Additional Resources

| File | Content |
|------|---------|
| [search-strategies.md](references/search-strategies.md) | Grid, random, successive halving, Hyperband/ASHA, TPE/GP Bayesian, CMA-ES, multi-fidelity; parallelism; scikit-learn and Optuna code |
| [search-spaces.md](references/search-spaces.md) | Ranges and scales per model family, conditional spaces, what to fix, two-stage coarse-to-fine searches |
| [reading-search-results.md](references/reading-search-results.md) | Boundaries, sensitivity and interactions, 1-SE rule, validation-set overfitting, nested CV, reporting the search |
