---
name: optuna-study-writer
description: "Write correct, resumable Optuna hyperparameter studies for scikit-learn, LightGBM, XGBoost and CatBoost: an objective with a search space sized to the data, fixed CV folds built once (stratified, grouped or time-ordered), early stopping inside each fold, trial.report and should_prune for MedianPruner / HyperbandPruner, seeded multivariate TPESampler, SQLite storage with study_name and load_if_exists for resuming, stale-study stopping callbacks, user attributes (best iteration, fold std), trials export, parameter importances, conditional spaces, multi-objective studies, and refitting the best configuration with a lower learning rate. Generates verified study scripts for six model families and lints Optuna code: unprunable objectives, inconsistent parameters, per-trial folds, wrong direction, constant-returning handlers, missing seeds or storage, deprecated APIs. Use when someone writes or reviews an Optuna study, wants Bayesian hyperparameter optimisation, pruning, or a resumable tuning job."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# Optuna Study Writer

Optuna makes Bayesian search easy to write and easy to get subtly wrong: folds that change between trials,
pruners that never fire because nothing is reported, a parameter whose range silently changes, an exception
handler that feeds the sampler fake scores, or a two-hour study that cannot resume after a crash.
`scripts/gen_optuna_study.py` writes a complete study script (verified end to end for LightGBM, XGBoost,
CatBoost, HistGradientBoosting, random forest and logistic regression, grouped and time-ordered folds, both
pruners, and resuming from storage); `scripts/optuna_lint.py` reviews existing Optuna code for eleven classes of
mistakes.

## Trigger Conditions

Activate this skill when the user:
- Wants to tune a model with Optuna, or asks for Bayesian / TPE hyperparameter optimisation
- Needs pruning, resumable studies, parallel workers, or multi-objective (accuracy vs latency) search
- Shares an Optuna objective for review, or sees pruning never happen / results that do not reproduce
- Wants the final model refit from the best trial

Strategy and budget questions: [hyperparameter-search-planner](../hyperparameter-search-planner/SKILL.md);
GBM parameter meaning: [xgboost-lightgbm-tuner](../xgboost-lightgbm-tuner/SKILL.md); fold design:
[cross-validation-strategy-designer](../cross-validation-strategy-designer/SKILL.md).

## Workflow

```
1. FOLDS      -> decide the splitter (stratified / grouped / time); build folds ONCE
2. GENERATE   -> python scripts/gen_optuna_study.py data.csv --target y --model lgbm --metric average_precision -o study.py
3. REVIEW     -> python scripts/optuna_lint.py study.py      (also for hand-written studies)
4. SMOKE      -> python study.py --trials 5        (seconds-scale check that everything runs)
5. RUN        -> python study.py --trials 200 --timeout 14400   (rerun the same command to resume)
6. ANALYSE    -> study_trials.csv -> hyperparameter-search-planner/scripts/analyze_search.py; importances
7. REFIT      -> best params, lower learning rate, scaled iterations; confirm on a holdout
```

## Anatomy of a Correct Study

```python
import numpy as np, optuna
FOLDS = list(StratifiedKFold(5, shuffle=True, random_state=0).split(X, y))      # fixed once

def objective(trial):
    params = {"num_leaves": trial.suggest_int("num_leaves", 7, 127, log=True),
              "min_child_samples": trial.suggest_int("min_child_samples", 5, 300, log=True),
              "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 30.0, log=True)}
    scores, iters = [], []
    for k, (tr, te) in enumerate(FOLDS):
        m = lgb.LGBMClassifier(**params, learning_rate=0.05, n_estimators=5000, verbose=-1, random_state=0)
        m.fit(X.iloc[tr], y.iloc[tr], eval_set=[(X.iloc[te], y.iloc[te])],
              callbacks=[lgb.early_stopping(100, verbose=False)])
        scores.append(average_precision_score(y.iloc[te], m.predict_proba(X.iloc[te])[:, 1]))
        iters.append(m.best_iteration_)
        trial.report(float(np.mean(scores)), step=k)        # intermediate value per fold
        if trial.should_prune():
            raise optuna.TrialPruned()
    trial.set_user_attr("best_iteration_mean", float(np.mean(iters)))
    return float(np.mean(scores))

study = optuna.create_study(study_name="lgbm_churn", storage="sqlite:///lgbm_churn.db", load_if_exists=True,
                            direction="maximize",
                            sampler=optuna.samplers.TPESampler(seed=0, multivariate=True, n_startup_trials=10),
                            pruner=optuna.pruners.MedianPruner(n_startup_trials=10, n_warmup_steps=1))
study.optimize(objective, n_trials=200, timeout=4 * 3600, gc_after_trial=True)
```

| Element | Why |
|---------|-----|
| Folds built once outside the objective | trials are compared on identical splits; pruning compares like with like |
| `trial.report` + `should_prune` + `raise TrialPruned` | the pruner needs all three |
| Seeded `TPESampler(multivariate=True)` | reproducible; models parameter interactions |
| `storage` + `study_name` + `load_if_exists=True` | crash-safe and resumable; several workers can share it |
| Early stopping inside folds; learning rate fixed | number of trees is not a search dimension |
| `set_user_attr` | keep best iteration and fold std for the refit and the report |
| `gc_after_trial=True` | frees memory between heavy trials |

Every API detail (samplers, pruners, distributions, callbacks, ask-and-tell, multi-objective):
[optuna-api-guide.md](references/optuna-api-guide.md).

## Mistakes the Linter Catches

| Code | Mistake | Consequence |
|------|---------|-------------|
| OP001 | pruner configured, objective never reports | no pruning: full cost for every trial |
| OP002 | report without should_prune, or should_prune without raising TrialPruned | same |
| OP003 | one name suggested with different types/ranges | Optuna raises `ValueError` (verified on 5.0) |
| OP004 | dynamic names in loops (`f"units_{i}"`) | search space changes shape between trials |
| OP005 | shuffled splitter without seed inside the objective | each trial sees different folds |
| OP006 | direction does not match the metric (maximize a loss) | the study optimises the wrong way |
| OP007 | `except Exception: return 0` | the sampler learns from fake values |
| OP008 | sampler without seed | not reproducible |
| OP009 | no storage / study_name | cannot resume after a crash |
| OP010 | `suggest_uniform`/`suggest_loguniform`/`suggest_discrete_uniform`, `optuna.integration.*` callbacks | deprecated / moved to optuna-integration |
| OP011 | objective reads `study.best_*` | trials depend on each other |

## Conditional and Multi-Objective Spaces

```python
boot = trial.suggest_categorical("bootstrap_type", ["Bayesian", "Bernoulli"])
if boot == "Bayesian":
    params["bagging_temperature"] = trial.suggest_float("bagging_temperature", 0.0, 1.0)
else:
    params["subsample"] = trial.suggest_float("subsample", 0.6, 1.0)

study = optuna.create_study(directions=["maximize", "minimize"])          # PR-AUC vs latency
pareto = study.best_trials
```
Patterns for model selection inside one study, constrained optimisation and warm-starting with known good
configurations (`study.enqueue_trial`): [study-patterns.md](references/study-patterns.md).

## Refit and Report

- Boosting: refit on all training data with the best parameters, half the learning rate and about
  2 x 1.1 x the mean best iteration (the generated script does this), or early-stop on a final validation split.
- The best value is the maximum over trials (optimistic): confirm on a holdout or with nested CV.
- Report trials completed/pruned, best value ± fold std, importances, the budget, and the holdout result.

## Output Format

When writing or reviewing a study, deliver:
1. **Study design** - model, metric and direction, folds, sampler, pruner, storage, budget.
2. **Code** - the generated or corrected script.
3. **Lint result** - `optuna_lint.py` findings fixed.
4. **Run summary** - trials complete/pruned, best value ± std, best params, importances.
5. **Refit and validation** - final model settings and holdout comparison against the untuned baseline.

## Scripts

```bash
python scripts/gen_optuna_study.py data.csv --target churned --model lgbm --metric average_precision -o study.py
python scripts/gen_optuna_study.py data.csv --target price --model xgb --metric neg_root_mean_squared_error --trials 100
python scripts/gen_optuna_study.py data.csv --target churned --model catboost --group-col customer_id --pruner hyperband
python scripts/gen_optuna_study.py data.csv --target churned --model hgb --time-col signup_date --patience 20
```
Models: lgbm, xgb, catboost, hgb, rf, logreg. Metrics: roc_auc, average_precision, neg_log_loss, accuracy,
neg_mean_absolute_error, neg_root_mean_squared_error, r2 (direction set automatically). The script builds fixed
StratifiedKFold/KFold, StratifiedGroupKFold/GroupKFold (`--group-col`) or TimeSeriesSplit (`--time-col`) folds,
data-sized ranges, early stopping per fold, per-fold reporting, Median/Hyperband/no pruner, SQLite storage with
resume, a stale-study callback (`--patience`), trials CSV, importances and a joblib refit. Exit codes: 0 written,
2 usage error.

```bash
python scripts/optuna_lint.py study.py
python scripts/optuna_lint.py src/*.py --json
```
Rules OP001-OP011 above. Exit codes: 0 no high findings, 1 high findings, 2 read or syntax error.

## Additional Resources

| File | Content |
|------|---------|
| [optuna-api-guide.md](references/optuna-api-guide.md) | create_study, samplers (TPE, GP, CMA-ES, random, grid, NSGA-II), pruners, suggest_* API, storage and parallel workers, callbacks, ask-and-tell, visualisation |
| [study-patterns.md](references/study-patterns.md) | CV objectives, boosting with early stopping, conditional spaces, model selection, multi-objective, constraints, enqueue_trial, timeouts, refitting |
